#!/usr/bin/env python3
"""
EIP-7716 driven by real chain data: the 2025-12-04 post-Fusaka correlated outage.

Consumes the per-slot offline balances produced by `xatu_ingest.py` and runs
three parameter sets over them:

  1. status quo      -- penalty_factor == 1 everywhere
  2. original EIP    -- PENALTY_ADJUSTMENT_FACTOR = 4096, MAX_PENALTY_FACTOR = 4,
                        the NET_EXCESS_PENALTIES counter
  3. revised EIP     -- PENALTY_SLOPE = 381, MAX_PENALTY_FACTOR = 128,
                        OFFLINE_BALANCE_SMOOTHING_FACTOR = 2**17

All three use the *same* offline series (missing both timely source and timely
target), so the comparison isolates the update rule rather than the trigger.

The revised recursion is a transcription of `get_slot_penalty_factors` +
`process_smoothed_offline_balance` from `specs/_features/eip7716/beacon-chain.md`.
Because `get_slot_penalty_factors` walks the previous epoch's 32 slots updating a
local copy of the moving average, and `process_smoothed_offline_balance` then
replays the identical walk onto the state, the two collapse to one chronological
per-slot recursion. `spec_check.py` verifies that against the spec functions.

Results are expressed in days-to-recoup per 32 ETH of stake -- days of normal
staking income needed to earn the loss back -- the unit of the EIP's own table.
"""

from __future__ import annotations

import argparse
import json
import math
import os
from dataclasses import dataclass, field

import duckdb
import numpy as np

from eip7716_model import EPOCHS_PER_DAY, SLOTS_PER_EPOCH

# ---------------------------------------------------------------- spec constants
# Adopted EIP constants (see SEVERITY.md). The committed results*/ record was
# generated at the initial calibration (--penalty-slope 381
# --max-penalty-factor 128), which run_all.sh pins; below the cap the two
# differ by exactly 2x.
MAX_PENALTY_FACTOR = 256
PENALTY_SLOPE = 765  # 3 * (MAX_PENALTY_FACTOR - 1)
OFFLINE_BALANCE_SMOOTHING_FACTOR = 2**17

PAF_ORIGINAL = 4096
MAXF_ORIGINAL = 4

TIMELY_SOURCE_WEIGHT = 14
TIMELY_TARGET_WEIGHT = 26
TIMELY_HEAD_WEIGHT = 14
WEIGHT_DENOMINATOR = 64
EFFECTIVE_BALANCE_INCREMENT = 1_000_000_000  # gwei

# The event, per the postmortem's epoch range.
EVENT_LO, EVENT_HI = 411439, 411480
FUSAKA_EPOCH = 411392
# Stable pre-Fusaka window used to seed the moving average. Deliberately ends
# before Fusaka activation: the fork itself perturbed participation, and seeding
# inside that perturbation would inflate the baseline and understate the excess.
SEED_LO, SEED_HI = 411200, FUSAKA_EPOCH - 1


# ---------------------------------------------------------------- mechanisms
def revised_factors(offline: np.ndarray, reference: np.ndarray, ema0: int):
    """Per-slot penalty factors under the revised mechanism. Exact integer math.

    Mirrors `get_slot_penalty_factors` / `get_updated_smoothed_offline_balance`.
    """
    n = len(offline)
    factors = np.empty(n, dtype=np.int64)
    emas = np.empty(n, dtype=np.int64)
    ema = int(ema0)
    for i in range(n):
        ob = int(offline[i])
        excess = ob - min(ob, ema)
        factors[i] = min(1 + PENALTY_SLOPE * excess // int(reference[i]), MAX_PENALTY_FACTOR)
        emas[i] = ema
        if ob > ema:
            ema += (ob - ema) // OFFLINE_BALANCE_SMOOTHING_FACTOR
        else:
            ema -= (ema - ob) // OFFLINE_BALANCE_SMOOTHING_FACTOR
    return factors, emas


def original_factors(offline: np.ndarray, total_active: np.ndarray, nep0: int = 0):
    """Per-slot penalty factors under EIP-7716 as drafted (NET_EXCESS_PENALTIES)."""
    n = len(offline)
    factors = np.empty(n, dtype=np.int64)
    neps = np.empty(n, dtype=np.int64)
    nep = int(nep0)
    for i in range(n):
        pf = min(
            int(offline[i]) * PAF_ORIGINAL // (nep * int(total_active[i]) + 1),
            MAXF_ORIGINAL,
        )
        factors[i] = pf
        nep = max(1, nep + pf) - 1
        neps[i] = nep
    return factors, neps


def seed_ema(offline: np.ndarray) -> int:
    """Seed `smoothed_offline_balance` from the mean per-slot offline balance."""
    return int(round(float(np.mean(offline))))


def seed_nep(offline: np.ndarray, total_active: np.ndarray, passes: int = 6) -> int:
    """Warm `NET_EXCESS_PENALTIES` on the real baseline series until it settles."""
    nep = 0
    for _ in range(passes):
        _, neps = original_factors(offline, total_active, nep0=nep)
        nep = int(neps[-1])
    return nep


# ---------------------------------------------------------------- reward context
@dataclass
class ChainContext:
    """December-2025 reward context, measured from the chain where possible."""

    total_active_balance_gwei: int
    # EL (tips + MEV) as a fraction on top of consensus-layer income. Measured
    # over the 21 days around the event from mev_relay_proposer_payload_delivered
    # (see `el_bonus.py`): 0.0737 spreading relay payments over every slot,
    # 0.0808 assuming locally-built blocks earned the same as relayed ones.
    # This was a quiet MEV period; the repo's July-2026 default is 0.21.
    el_apr_bonus: float = 0.077
    # ETH/USD during the event window (2025-12-04 02:49-07:18Z), CoinGecko.
    eth_price_usd: float = 3050.0

    @property
    def base_reward_per_increment(self) -> int:
        return (
            EFFECTIVE_BALANCE_INCREMENT * WEIGHT_DENOMINATOR
        ) // math.isqrt(self.total_active_balance_gwei)

    def base_reward(self, effective_balance_gwei: int = 32_000_000_000) -> int:
        return (
            effective_balance_gwei // EFFECTIVE_BALANCE_INCREMENT
        ) * self.base_reward_per_increment

    def att_reward_ideal_per_epoch(self, eb=32_000_000_000) -> float:
        w = TIMELY_SOURCE_WEIGHT + TIMELY_TARGET_WEIGHT + TIMELY_HEAD_WEIGHT
        return self.base_reward(eb) * w / WEIGHT_DENOMINATOR

    def full_earnings_per_epoch(self, eb=32_000_000_000) -> float:
        """Normal total income per epoch: attestation + proposer/sync + EL.

        Same gross-up convention as `eip7716_model.Network.full_reward_per_epoch_gwei`:
        attestation flags carry 54/64 of the base reward, the remaining 10/64
        (proposer 8/64 + sync 2/64) is earned in expectation.
        """
        cl = self.att_reward_ideal_per_epoch(eb) * (64 / 54)
        return cl * (1 + self.el_apr_bonus)

    def cl_apr(self, eb=32_000_000_000) -> float:
        cl = self.att_reward_ideal_per_epoch(eb) * (64 / 54)
        return cl * EPOCHS_PER_DAY * 365.25 / eb


# ---------------------------------------------------------------- data loading
@dataclass
class EventData:
    slots: "duckdb.DuckDBPyRelation" = field(repr=False)
    con: duckdb.DuckDBPyConnection = field(repr=False)
    derived_dir: str = "data/derived"

    @classmethod
    def load(cls, derived_dir="data/derived", threads=8):
        con = duckdb.connect(config={"threads": threads})
        con.execute(
            f"CREATE VIEW slots AS SELECT * FROM "
            f"read_parquet('{os.path.join(derived_dir, 'slots.parquet')}') ORDER BY slot"
        )
        con.execute(
            f"CREATE VIEW epochs AS SELECT * FROM "
            f"read_parquet('{os.path.join(derived_dir, 'epochs.parquet')}')"
        )
        con.execute(
            f"CREATE VIEW offline_validators AS SELECT * FROM "
            f"read_parquet('{os.path.join(derived_dir, 'offline_validators.parquet')}')"
        )
        return cls(con.sql("SELECT * FROM slots"), con, derived_dir)

    def arrays(self):
        df = self.con.sql(
            "SELECT slot, epoch, slot_index, offline_bal, assigned_bal, "
            "total_active_balance, slot_reference_balance FROM slots ORDER BY slot"
        ).df()
        return df


# ---------------------------------------------------------------- cost model
def run_mechanisms(df, seed_lo=SEED_LO, seed_hi=SEED_HI):
    """Attach per-slot penalty factors for all three parameter sets."""
    offline = df["offline_bal"].to_numpy(dtype=np.int64)
    ref = df["slot_reference_balance"].to_numpy(dtype=np.int64)
    tab = df["total_active_balance"].to_numpy(dtype=np.int64)
    seed_mask = (df["epoch"] >= seed_lo) & (df["epoch"] <= seed_hi)

    ema0 = seed_ema(offline[seed_mask.to_numpy()])
    nep0 = seed_nep(offline[seed_mask.to_numpy()], tab[seed_mask.to_numpy()])

    f_new, emas = revised_factors(offline, ref, ema0)
    f_old, neps = original_factors(offline, tab, nep0)

    df = df.copy()
    df["factor_revised"] = f_new
    df["ema"] = emas
    df["factor_original"] = f_old
    df["nep"] = neps
    df["factor_status_quo"] = 1
    return df, {"ema_seed_gwei": ema0, "nep_seed": nep0,
                "seed_window": (seed_lo, seed_hi),
                "seed_offline_share": float(
                    offline[seed_mask.to_numpy()].sum() / df.loc[seed_mask, "assigned_bal"].sum()
                )}


def validator_costs(data: EventData, df, ctx: ChainContext, epoch_lo, epoch_hi):
    """Per-validator loss over [epoch_lo, epoch_hi] under each mechanism.

    Loss = forgone attestation reward + timely-source penalty + timely-target
    penalty (scaled). Head misses are never penalised; the inactivity leak never
    engaged, so inactivity penalties are zero (outside a leak the score decays by
    16 per epoch against a +4 increment, so a validator entering at score 0 stays
    at 0 and pays nothing).

    Forgone reward uses the *realised* per-epoch participation weighting, i.e.
    what the validator would have earned had it alone attested while everyone
    else behaved as they actually did.
    """
    con = data.con
    factors = df[["epoch", "slot_index", "factor_revised", "factor_original"]]
    con.register("factors_df", factors)

    # realised participation scaling per epoch, per flag
    part = con.sql(
        """
        SELECT epoch, total_active_balance,
               (source_only_bal + both_bal)::HUGEINT AS src_bal,
               (target_only_bal + both_bal)::HUGEINT AS tgt_bal,
               head_bal::HUGEINT AS head_bal
        FROM epochs
        """
    ).df()
    con.register("part_df", part)

    rows = con.sql(
        f"""
        SELECT o.validator,
               count(*) AS offline_epochs,
               any_value(o.effective_balance) AS effective_balance,
               sum(f.factor_revised) AS sum_factor_revised,
               sum(f.factor_original) AS sum_factor_original,
               sum(p.src_bal * 1.0 / p.total_active_balance) AS sum_src_scale,
               sum(p.tgt_bal * 1.0 / p.total_active_balance) AS sum_tgt_scale,
               sum(p.head_bal * 1.0 / p.total_active_balance) AS sum_head_scale
        FROM offline_validators o
        JOIN factors_df f ON f.epoch = o.epoch AND f.slot_index = o.slot_index
        JOIN part_df p ON p.epoch = o.epoch
        WHERE o.epoch BETWEEN {epoch_lo} AND {epoch_hi}
        GROUP BY o.validator
        """
    ).df()

    eb = rows["effective_balance"].to_numpy(dtype=np.int64)
    br = (eb // EFFECTIVE_BALANCE_INCREMENT) * ctx.base_reward_per_increment
    n = rows["offline_epochs"].to_numpy(dtype=np.int64)

    # forgone attestation reward, realised-participation weighting
    forgone = br * (
        TIMELY_SOURCE_WEIGHT * rows["sum_src_scale"].to_numpy()
        + TIMELY_TARGET_WEIGHT * rows["sum_tgt_scale"].to_numpy()
        + TIMELY_HEAD_WEIGHT * rows["sum_head_scale"].to_numpy()
    ) / WEIGHT_DENOMINATOR
    forgone_ideal = br * n * (
        TIMELY_SOURCE_WEIGHT + TIMELY_TARGET_WEIGHT + TIMELY_HEAD_WEIGHT
    ) / WEIGHT_DENOMINATOR

    pen_source = br * n * TIMELY_SOURCE_WEIGHT / WEIGHT_DENOMINATOR
    pen_target_1x = br * n * TIMELY_TARGET_WEIGHT / WEIGHT_DENOMINATOR
    pen_target_rev = br * rows["sum_factor_revised"].to_numpy() * TIMELY_TARGET_WEIGHT / WEIGHT_DENOMINATOR
    # the drafted mechanism scaled source+target together (the scope taken by the
    # draft Lighthouse implementation); keeping that convention here makes the
    # comparison generous to the original design rather than dismissive of it.
    pen_both_orig = (
        br
        * rows["sum_factor_original"].to_numpy()
        * (TIMELY_SOURCE_WEIGHT + TIMELY_TARGET_WEIGHT)
        / WEIGHT_DENOMINATOR
    )

    out = rows[["validator", "offline_epochs", "effective_balance"]].copy()
    out["base_reward"] = br
    out["forgone_reward"] = forgone
    out["forgone_reward_ideal"] = forgone_ideal
    out["penalty_status_quo"] = pen_source + pen_target_1x
    out["penalty_revised"] = pen_source + pen_target_rev
    out["penalty_original"] = pen_both_orig
    out["mean_factor_revised"] = rows["sum_factor_revised"].to_numpy() / n
    out["mean_factor_original"] = rows["sum_factor_original"].to_numpy() / n
    for k in ("status_quo", "revised", "original"):
        out[f"loss_{k}"] = out["forgone_reward"] + out[f"penalty_{k}"]
    return out


def days_to_recoup(loss_gwei, ctx: ChainContext, eb=32_000_000_000):
    """Days of normal income needed to earn the loss back, normalised per 32 ETH."""
    per_day = ctx.full_earnings_per_epoch(eb) * EPOCHS_PER_DAY
    return loss_gwei / per_day


def network_accounting(data: EventData, ctx: ChainContext, epoch_lo, epoch_hi,
                       base_lo=SEED_LO, base_hi=SEED_HI, el_eth_per_block=0.0307):
    """Network-wide cost of the event, for cross-checking against the postmortem.

    Not a 7716 quantity -- this is what the network actually gave up under
    today's rules. The dominant term is not the offline cohort's own loss but the
    participation scaling every *online* validator suffered: attestation rewards
    carry a factor `participating_increments / active_increments`, so a reward
    for flag `f` is quadratic in that flag's participation rate.
    """
    con = data.con
    ep = con.sql(
        f"""
        SELECT epoch, assigned_bal,
               (source_only_bal + both_bal) * 1.0 / assigned_bal AS p_src,
               (target_only_bal + both_bal) * 1.0 / assigned_bal AS p_tgt,
               head_bal * 1.0 / assigned_bal AS p_head
        FROM epochs WHERE epoch BETWEEN {epoch_lo} AND {epoch_hi} ORDER BY epoch
        """
    ).df()
    base = con.sql(
        f"""
        SELECT avg((source_only_bal + both_bal) * 1.0 / assigned_bal) AS p_src,
               avg((target_only_bal + both_bal) * 1.0 / assigned_bal) AS p_tgt,
               avg(head_bal * 1.0 / assigned_bal) AS p_head
        FROM epochs WHERE epoch BETWEEN {base_lo} AND {base_hi}
        """
    ).df().iloc[0]

    bri = ctx.base_reward_per_increment
    base_total = ep.assigned_bal.to_numpy() / 1e9 * bri / 1e9  # ETH per epoch

    W = {"src": TIMELY_SOURCE_WEIGHT, "tgt": TIMELY_TARGET_WEIGHT, "head": TIMELY_HEAD_WEIGHT}
    rew_actual = sum(
        base_total * W[k] * ep[f"p_{k}"].to_numpy() ** 2 / WEIGHT_DENOMINATOR for k in W
    ).sum()
    rew_baseline = sum(
        base_total * W[k] * float(base[f"p_{k}"]) ** 2 / WEIGHT_DENOMINATOR for k in W
    ).sum()

    pen_actual = sum(
        base_total * W[k] * (1 - ep[f"p_{k}"].to_numpy()) / WEIGHT_DENOMINATOR
        for k in ("src", "tgt")
    ).sum()
    pen_baseline = sum(
        base_total * W[k] * (1 - float(base[f"p_{k}"])) / WEIGHT_DENOMINATOR
        for k in ("src", "tgt")
    ).sum()

    n_slots, produced = con.sql(
        f"SELECT count(*), count(*) FILTER (WHERE has_block) FROM slots "
        f"WHERE epoch BETWEEN {epoch_lo} AND {epoch_hi}"
    ).fetchone()
    missed = n_slots - produced
    base_missed_rate = con.sql(
        f"SELECT 1 - count(*) FILTER (WHERE has_block) * 1.0 / count(*) FROM slots "
        f"WHERE epoch BETWEEN {base_lo} AND {base_hi}"
    ).fetchone()[0]
    excess_missed = missed - n_slots * base_missed_rate
    # a proposer earns PROPOSER_WEIGHT (8/64) of the base-reward budget per epoch
    proposer_cl_per_slot = float(base_total.mean()) * 8 / WEIGHT_DENOMINATOR / SLOTS_PER_EPOCH
    forgone_proposer_cl = excess_missed * proposer_cl_per_slot
    forgone_proposer_el = excess_missed * el_eth_per_block
    # sync committee: 2/64 of the budget, missed in proportion to the offline share
    off_share = con.sql(
        f"SELECT sum(offline_bal) * 1.0 / sum(assigned_bal) FROM slots "
        f"WHERE epoch BETWEEN {epoch_lo} AND {epoch_hi}"
    ).fetchone()[0]
    sync_forgone = float(base_total.sum()) * 2 / WEIGHT_DENOMINATOR * float(off_share)

    return {
        "epochs": [int(epoch_lo), int(epoch_hi)],
        "baseline_participation": {k: float(base[f"p_{k}"]) for k in W},
        "attestation_rewards_paid_eth": float(rew_actual),
        "attestation_rewards_at_baseline_eth": float(rew_baseline),
        "forgone_attestation_rewards_eth": float(rew_baseline - rew_actual),
        "attestation_penalties_paid_eth": float(pen_actual),
        "attestation_penalties_at_baseline_eth": float(pen_baseline),
        "excess_attestation_penalties_eth": float(pen_actual - pen_baseline),
        "cl_issuance_budget_eth": float(base_total.sum()),
        "slots": int(n_slots),
        "blocks_produced": int(produced),
        "missed_slots": int(missed),
        "missed_slot_rate": float(missed / n_slots),
        "baseline_missed_slot_rate": float(base_missed_rate),
        "excess_missed_slots": float(excess_missed),
        "forgone_proposer_cl_eth": float(forgone_proposer_cl),
        "forgone_proposer_el_eth": float(forgone_proposer_el),
        "forgone_sync_eth": float(sync_forgone),
        "total_network_cost_eth": float(
            (rew_baseline - rew_actual)
            + (pen_actual - pen_baseline)
            + forgone_proposer_cl
            + forgone_proposer_el
            + sync_forgone
        ),
    }


def attributed_cut(data: EventData, costs, ctx: ChainContext, classified_path):
    """Same three lines, split by the behavioural buckets from `attribution.py`.

    A validator is assigned its modal bucket over the epochs it was offline;
    `bucket_purity` reports how dominant that mode was. `unknown` is carried
    explicitly: any offline validator the classifier could not place lands there.
    """
    con = data.con
    con.execute(
        f"CREATE OR REPLACE VIEW classified AS SELECT * FROM read_parquet('{classified_path}')"
    )
    modal = con.sql(
        """
        SELECT validator, bucket, purity FROM (
            SELECT validator, bucket, count(*) AS n,
                   count(*) * 1.0 / sum(count(*)) OVER (PARTITION BY validator) AS purity,
                   row_number() OVER (PARTITION BY validator ORDER BY count(*) DESC, bucket) AS rk
            FROM classified GROUP BY validator, bucket)
        WHERE rk = 1
        """
    ).df()

    merged = costs.merge(modal, on="validator", how="left")
    merged["bucket"] = merged["bucket"].fillna("unknown")
    merged["purity"] = merged["purity"].fillna(0.0)

    per32 = 32_000_000_000
    out = {}
    total_stake = merged.effective_balance.sum()
    for bucket, grp in merged.groupby("bucket"):
        rec = {
            "validators": int(len(grp)),
            "share_of_offline_validators": float(len(grp) / len(merged)),
            "share_of_offline_stake": float(grp.effective_balance.sum() / total_stake),
            "mean_offline_epochs": float(grp.offline_epochs.mean()),
            "mean_bucket_purity": float(grp.purity.mean()),
            "mean_factor_revised": float(
                (grp.mean_factor_revised * grp.offline_epochs).sum() / grp.offline_epochs.sum()
            ),
        }
        for k in ("status_quo", "original", "revised"):
            norm = grp[f"loss_{k}"] * per32 / grp["effective_balance"]
            rec[f"days_to_recoup_{k}"] = float(days_to_recoup(norm.mean(), ctx))
            rec[f"median_days_to_recoup_{k}"] = float(days_to_recoup(norm.median(), ctx))
        out[bucket] = rec
    return out


def dv_archetype(df, ctx: ChainContext, epoch_lo, epoch_hi, survival=(0.0, 0.5, 1.0)):
    """HYPOTHETICAL. Not observed anywhere in this data.

    A distributed validator splits its key across nodes running different
    clients, so a client-specific bug takes down only part of its cluster. If the
    surviving nodes still meet threshold, the validator attests normally and pays
    nothing; if they do not, it is offline like anyone else. This constructs the
    intermediate case by scaling the *number of epochs* the validator was down,
    holding the network-wide factor trajectory fixed -- the DV's own presence is
    far too small to move the penalty factor.
    """
    ev = df[df.epoch.between(epoch_lo, epoch_hi)]
    # a validator's committee sits in a uniformly random slot each epoch, so the
    # factor it meets is the mean over slots
    mean_factor = float(ev.factor_revised.mean())
    n_epochs = ev.epoch.nunique()
    br = ctx.base_reward()
    per32 = {}
    for s in survival:
        down = n_epochs * (1 - s)
        rew = ctx.att_reward_ideal_per_epoch() * down
        pen_sq = br * down * (TIMELY_SOURCE_WEIGHT + TIMELY_TARGET_WEIGHT) / WEIGHT_DENOMINATOR
        pen_rev = br * down * (
            TIMELY_SOURCE_WEIGHT + mean_factor * TIMELY_TARGET_WEIGHT
        ) / WEIGHT_DENOMINATOR
        per32[f"survival_{s:.2f}"] = {
            "epochs_offline": down,
            "days_to_recoup_status_quo": days_to_recoup(rew + pen_sq, ctx),
            "days_to_recoup_revised": days_to_recoup(rew + pen_rev, ctx),
        }
    return {
        "_label": "HYPOTHETICAL CONSTRUCTION -- not an observation",
        "mean_event_factor_revised": mean_factor,
        "cases": per32,
    }


def main():
    global PENALTY_SLOPE, MAX_PENALTY_FACTOR
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--derived-dir", default="data/derived")
    ap.add_argument("--out-dir", default="results")
    ap.add_argument("--event-lo", type=int, default=EVENT_LO)
    ap.add_argument("--event-hi", type=int, default=EVENT_HI)
    ap.add_argument("--tail-hi", type=int, default=411700,
                    help="upper epoch for the 'event + recovery tail' cost line")
    ap.add_argument("--seed-lo", type=int, default=SEED_LO)
    ap.add_argument("--seed-hi", type=int, default=SEED_HI)
    ap.add_argument("--el-bonus", type=float, default=0.077)
    ap.add_argument("--eth-price", type=float, default=3050.0)
    ap.add_argument("--penalty-slope", type=int, default=PENALTY_SLOPE)
    ap.add_argument("--max-penalty-factor", type=int, default=MAX_PENALTY_FACTOR)
    args = ap.parse_args()

    PENALTY_SLOPE = args.penalty_slope
    MAX_PENALTY_FACTOR = args.max_penalty_factor

    os.makedirs(args.out_dir, exist_ok=True)
    data = EventData.load(args.derived_dir)
    df = data.arrays()
    df, seeds = run_mechanisms(df, args.seed_lo, args.seed_hi)

    tab = int(df.loc[df.epoch.between(args.event_lo, args.event_hi), "total_active_balance"].median())
    ctx = ChainContext(tab, el_apr_bonus=args.el_bonus, eth_price_usd=args.eth_price)

    df.to_parquet(os.path.join(args.out_dir, "slot_factors.parquet"), index=False)

    ev = df[df.epoch.between(args.event_lo, args.event_hi)]
    summary = {
        "event_epochs": [args.event_lo, args.event_hi],
        "seed_window": seeds["seed_window"],
        "seed_ema_gwei": seeds["ema_seed_gwei"],
        "seed_ema_eth": seeds["ema_seed_gwei"] / 1e9,
        "seed_offline_share": seeds["seed_offline_share"],
        "seed_nep": seeds["nep_seed"],
        "total_active_balance_eth": tab / 1e9,
        "base_reward_per_increment_gwei": ctx.base_reward_per_increment,
        "cl_apr": ctx.cl_apr(),
        "peak_offline_share": float((ev.offline_bal / ev.assigned_bal).max()),
        "mean_offline_share_event": float(ev.offline_bal.sum() / ev.assigned_bal.sum()),
        "factor_revised": {
            "max": int(ev.factor_revised.max()),
            "mean": float(ev.factor_revised.mean()),
            "slots_at_cap": int((ev.factor_revised == MAX_PENALTY_FACTOR).sum()),
        },
        "factor_original": {
            "max": int(ev.factor_original.max()),
            "mean": float(ev.factor_original.mean()),
            "slots_at_cap": int((ev.factor_original == MAXF_ORIGINAL).sum()),
            "slots_at_zero": int((ev.factor_original == 0).sum()),
        },
    }

    for label, hi in (("event", args.event_hi), ("event_plus_tail", args.tail_hi)):
        costs = validator_costs(data, df, ctx, args.event_lo, hi)
        costs.to_parquet(os.path.join(args.out_dir, f"validator_costs_{label}.parquet"), index=False)
        per32 = 32_000_000_000
        block = {}
        for k in ("status_quo", "original", "revised"):
            # normalise every validator to a 32 ETH stake before averaging so the
            # headline is "per 32 ETH", not "per validator"
            norm = costs[f"loss_{k}"] * per32 / costs["effective_balance"]
            block[k] = {
                "mean_loss_gwei_per_32eth": float(norm.mean()),
                "median_loss_gwei_per_32eth": float(norm.median()),
                "p95_loss_gwei_per_32eth": float(norm.quantile(0.95)),
                "mean_days_to_recoup": float(days_to_recoup(norm.mean(), ctx)),
                "median_days_to_recoup": float(days_to_recoup(norm.median(), ctx)),
                "p95_days_to_recoup": float(days_to_recoup(norm.quantile(0.95), ctx)),
                "network_total_eth": float(costs[f"loss_{k}"].sum() / 1e9),
                "network_penalty_eth": float(costs[f"penalty_{k}"].sum() / 1e9),
            }
        block["n_validators_affected"] = int(len(costs))
        block["mean_offline_epochs"] = float(costs.offline_epochs.mean())
        block["forgone_reward_eth"] = float(costs.forgone_reward.sum() / 1e9)
        block["forgone_reward_ideal_eth"] = float(costs.forgone_reward_ideal.sum() / 1e9)
        block["mean_factor_revised"] = float(
            (costs.mean_factor_revised * costs.offline_epochs).sum() / costs.offline_epochs.sum()
        )
        block["mean_factor_original"] = float(
            (costs.mean_factor_original * costs.offline_epochs).sum() / costs.offline_epochs.sum()
        )
        summary[label] = block
        if label == "event":
            event_costs = costs

    summary["network_accounting"] = network_accounting(
        data, ctx, args.event_lo, args.event_hi, args.seed_lo, args.seed_hi
    )

    cls_path = os.path.join(args.out_dir, "offline_classified.parquet")
    if os.path.exists(cls_path):
        summary["attributed"] = attributed_cut(data, event_costs, ctx, cls_path)
    else:
        print(f"note: {cls_path} absent; run attribution.py for the attributed cut")

    summary["hypothetical_dv_archetype"] = dv_archetype(df, ctx, args.event_lo, args.event_hi)

    with open(os.path.join(args.out_dir, "summary.json"), "w") as fh:
        json.dump(summary, fh, indent=2)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
