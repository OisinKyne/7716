#!/usr/bin/env python3
"""
Window-length and skew sweep for the revised EIP-7716 mechanism, driven by the
real per-slot offline series from `xatu_ingest.py`.

The question this answers
-------------------------
The smoothing window (`OFFLINE_BALANCE_SMOOTHING_FACTOR`, currently 2^17 slots
of division constant = 12.6-day half-life) sets how fast the reference balance
absorbs an outage. Two families of alternatives:

  * symmetric   -- one constant, swept 2^14..2^18 (half-life 1.6d..25.2d)
  * asymmetric  -- separate rise/fall constants. A fast RISE makes the
                   reference chase the spike, so the factor decays with time
                   since onset even if the cohort has not recovered: mechanical
                   front-loading that does not depend on cohort behaviour.
                   A fast FALL re-arms quickly after events.

For each (event, variant) this reports, from real data:

  severity        mean days-to-recoup over the event cohort, vs status quo
  straggler curve mean cost by *personal* recovery hour (last offline epoch),
                  chronic validators excluded -- the "patch at 8h, fixed at
                  24h" question, answered against actual recovery behaviour
  tail share      fraction of total scaled penalties paid after the cohort was
                  90% recovered
  quiet noise     factor behaviour over the pre-event seed window

and, synthetically on each event's own baseline:

  sustained       cost of a 10%-of-stake cohort staying down 7 days
  re-arm          onset factor a repeat event would meet +3/+7/+14 days out

Usage: .venv/bin/python window_sweep.py --event prysm [--out results_sweep]
"""

from __future__ import annotations

import argparse
import json
import os

import duckdb
import numpy as np
import pandas as pd

import events as events_mod
from eip7716_historical import (
    ChainContext,
    EventData,
    days_to_recoup,
    EFFECTIVE_BALANCE_INCREMENT,
    MAX_PENALTY_FACTOR,
    PENALTY_SLOPE,
    TIMELY_SOURCE_WEIGHT,
    TIMELY_TARGET_WEIGHT,
    TIMELY_HEAD_WEIGHT,
    WEIGHT_DENOMINATOR,
)
from eip7716_model import EPOCHS_PER_DAY, SLOTS_PER_EPOCH

SLOTS_PER_DAY = int(EPOCHS_PER_DAY * SLOTS_PER_EPOCH)  # 7200
LN2 = float(np.log(2.0))


def hl_days(constant: int) -> float:
    """Half-life in days of the integer-division EMA with this constant."""
    return constant * LN2 / SLOTS_PER_DAY


# ---------------------------------------------------------------- variants
# (name, rise_constant, fall_constant). rise applies when offline > smoothed.
VARIANTS = [
    ("sym_2^14", 2**14, 2**14),
    ("sym_2^15", 2**15, 2**15),
    ("sym_2^16", 2**16, 2**16),
    ("sym_2^17", 2**17, 2**17),  # current draft
    ("sym_2^18", 2**18, 2**18),
    # fast rise, current fall: reference chases the spike -> time-based decay
    # 2^9 is the near-limit case: HL ~1.2h, prices going-down not staying-down
    ("rise_2^9_fall_2^17", 2**9, 2**17),
    ("rise_2^11_fall_2^17", 2**11, 2**17),
    ("rise_2^12_fall_2^17", 2**12, 2**17),
    ("rise_2^13_fall_2^17", 2**13, 2**17),
    ("rise_2^15_fall_2^17", 2**15, 2**17),
    # current rise, fast fall: quick re-arm between events
    ("fall_2^15_rise_2^17", 2**17, 2**15),
    ("fall_2^13_rise_2^17", 2**17, 2**13),
]


def asym_factors(offline: np.ndarray, reference: np.ndarray, ema0: int,
                 rise: int, fall: int):
    """Per-slot factors with separate rise/fall smoothing constants.

    rise == fall reproduces `revised_factors` exactly.
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
            ema += (ob - ema) // rise
        else:
            ema -= (ema - ob) // fall
    return factors, emas


def warm_seed(offline_seed: np.ndarray, reference_seed: np.ndarray,
              rise: int, fall: int, passes: int = 3) -> int:
    """Warm the EMA on the seed window until it settles.

    Matters for asymmetric variants: with a fast rise and slow fall the
    steady-state EMA sits above the window mean (it ratchets up on noise
    spikes and releases slowly). Seeding at the mean would overstate the
    onset factor for those variants.
    """
    ema = int(round(float(np.mean(offline_seed))))
    for _ in range(passes):
        _, emas = asym_factors(offline_seed, reference_seed, ema, rise, fall)
        # advance one more step past the last recorded pre-update value
        ob = int(offline_seed[-1])
        ema = int(emas[-1])
        ema = ema + (ob - ema) // rise if ob > ema else ema - (ema - ob) // fall
    return ema


# ---------------------------------------------------------------- per-validator
def sweep_validator_costs(data: EventData, factors_df: pd.DataFrame,
                          ctx: ChainContext, names, epoch_lo, epoch_hi):
    """Per-validator loss for every variant in one duckdb pass.

    Also returns last/first offline epoch inside the window (for the
    straggler curve) and the count of seed-window offline epochs (to flag
    chronic validators).
    """
    con = data.con
    con.register("factors_sweep", factors_df)

    part = con.sql(
        """
        SELECT epoch, total_active_balance,
               (source_only_bal + both_bal)::HUGEINT AS src_bal,
               (target_only_bal + both_bal)::HUGEINT AS tgt_bal,
               head_bal::HUGEINT AS head_bal
        FROM epochs
        """
    ).df()
    con.register("part_sweep", part)

    factor_sums = ",\n               ".join(
        f'sum(f."{n}") AS "sum_{n}"' for n in names
    )
    rows = con.sql(
        f"""
        SELECT o.validator,
               count(*) AS offline_epochs,
               min(o.epoch) AS first_offline_epoch,
               max(o.epoch) AS last_offline_epoch,
               any_value(o.effective_balance) AS effective_balance,
               {factor_sums},
               sum(p.src_bal * 1.0 / p.total_active_balance) AS sum_src_scale,
               sum(p.tgt_bal * 1.0 / p.total_active_balance) AS sum_tgt_scale,
               sum(p.head_bal * 1.0 / p.total_active_balance) AS sum_head_scale
        FROM offline_validators o
        JOIN factors_sweep f ON f.epoch = o.epoch AND f.slot_index = o.slot_index
        JOIN part_sweep p ON p.epoch = o.epoch
        WHERE o.epoch BETWEEN {epoch_lo} AND {epoch_hi}
        GROUP BY o.validator
        """
    ).df()

    eb = rows["effective_balance"].to_numpy(dtype=np.int64)
    br = (eb // EFFECTIVE_BALANCE_INCREMENT) * ctx.base_reward_per_increment
    n = rows["offline_epochs"].to_numpy(dtype=np.int64)

    forgone = br * (
        TIMELY_SOURCE_WEIGHT * rows["sum_src_scale"].to_numpy()
        + TIMELY_TARGET_WEIGHT * rows["sum_tgt_scale"].to_numpy()
        + TIMELY_HEAD_WEIGHT * rows["sum_head_scale"].to_numpy()
    ) / WEIGHT_DENOMINATOR
    pen_source = br * n * TIMELY_SOURCE_WEIGHT / WEIGHT_DENOMINATOR
    pen_target_1x = br * n * TIMELY_TARGET_WEIGHT / WEIGHT_DENOMINATOR

    out = rows[["validator", "offline_epochs", "first_offline_epoch",
                "last_offline_epoch", "effective_balance"]].copy()
    out["loss_status_quo"] = forgone + pen_source + pen_target_1x
    for name in names:
        pen_t = br * rows[f"sum_{name}"].to_numpy() * TIMELY_TARGET_WEIGHT / WEIGHT_DENOMINATOR
        out[f"loss_{name}"] = forgone + pen_source + pen_t
        out[f"scaled_pen_{name}"] = pen_t
    return out


def chronic_validators(data: EventData, seed_lo, seed_hi) -> set:
    """Validators offline in most of the seed window -- not 'recovering'."""
    n_seed = seed_hi - seed_lo + 1
    df = data.con.sql(
        f"""
        SELECT validator FROM offline_validators
        WHERE epoch BETWEEN {seed_lo} AND {seed_hi}
        GROUP BY validator HAVING count(*) >= {n_seed} * 0.5
        """
    ).df()
    return set(df.validator.to_numpy())


# ---------------------------------------------------------------- main sweep
def run(event_key: str, out_dir: str):
    ev = events_mod.get(event_key)
    data = EventData.load(ev.derived_dir)
    df = data.con.sql(
        "SELECT slot, epoch, slot_index, offline_bal, assigned_bal, "
        "total_active_balance, slot_reference_balance FROM slots ORDER BY slot"
    ).df()

    offline = df["offline_bal"].to_numpy(dtype=np.int64)
    ref = df["slot_reference_balance"].to_numpy(dtype=np.int64)
    seed_mask = ((df["epoch"] >= ev.seed_lo) & (df["epoch"] <= ev.seed_hi)).to_numpy()
    ev_mask = ((df["epoch"] >= ev.event_lo) & (df["epoch"] <= ev.event_hi)).to_numpy()

    tab = int(df.loc[df.epoch.between(ev.event_lo, ev.event_hi),
                     "total_active_balance"].median())
    ctx = ChainContext(tab, el_apr_bonus=ev.el_bonus, eth_price_usd=ev.eth_price)

    # cohort recovery timeline: excess offline share by epoch, relative to seed
    ep = data.con.sql(
        f"""
        SELECT epoch, sum(offline_bal) AS off, sum(assigned_bal) AS asg
        FROM slots WHERE epoch BETWEEN {ev.event_lo} AND {ev.tail_hi}
        GROUP BY epoch ORDER BY epoch
        """
    ).df()
    base_share = float(offline[seed_mask].sum() / df.loc[seed_mask, "assigned_bal"].sum())
    excess_share = (ep["off"] / ep["asg"] - base_share).clip(lower=0.0).to_numpy()
    peak = excess_share.max()

    def epochs_to_recovery(frac):
        below = np.nonzero(excess_share <= (1 - frac) * peak)[0]
        # first epoch at/after the peak where the excess has fallen this far
        i_peak = int(np.argmax(excess_share))
        after = below[below >= i_peak]
        return int(after[0]) if len(after) else None

    rec = {f"epochs_to_{int(f*100)}pct_recovered": epochs_to_recovery(f)
           for f in (0.5, 0.9, 0.99)}
    e90 = rec["epochs_to_90pct_recovered"]

    # ---------------- factors for every variant
    names = [v[0] for v in VARIANTS]
    fdf = df[["epoch", "slot_index"]].copy()
    trajectories = {}
    seeds = {}
    quiet = {}
    for name, rise, fall in VARIANTS:
        ema0 = warm_seed(offline[seed_mask], ref[seed_mask], rise, fall)
        seeds[name] = ema0
        f, emas = asym_factors(offline, ref, ema0, rise, fall)
        fdf[name] = f
        trajectories[name] = (f, emas)
        fs = f[seed_mask]
        quiet[name] = {
            "share_slots_factor_gt1": float((fs > 1).mean()),
            "p99_factor": int(np.percentile(fs, 99)),
            "max_factor": int(fs.max()),
        }

    # ---------------- per-validator costs over event + tail
    costs = sweep_validator_costs(data, fdf, ctx, names, ev.event_lo, ev.tail_hi)
    chronic = chronic_validators(data, ev.seed_lo, ev.seed_hi)
    costs["chronic"] = costs.validator.isin(chronic)

    per32 = 32_000_000_000
    hours_per_epoch = SLOTS_PER_EPOCH * 12 / 3600

    # straggler curve: bucket by personal recovery hour since onset
    fresh = costs[~costs.chronic].copy()
    fresh["recovery_hour"] = (
        (fresh.last_offline_epoch + 1 - ev.event_lo) * hours_per_epoch
    )
    edges = [0, 2, 4, 6, 8, 12, 18, 24, 36, 48, 72, 1e9]
    labels = ["0-2h", "2-4h", "4-6h", "6-8h", "8-12h", "12-18h", "18-24h",
              "24-36h", "36-48h", "48-72h", "72h+"]
    fresh["bucket"] = pd.cut(fresh.recovery_hour, bins=edges, labels=labels,
                             right=False)
    # density: how contiguous the validator's outage was between its first and
    # last offline epoch. Flappers (nodes bouncing in and out) have low
    # density and pollute the recovery-hour buckets; the "slow to patch"
    # population the fairness question is about is the dense one.
    fresh["density"] = fresh.offline_epochs / (
        fresh.last_offline_epoch - fresh.first_offline_epoch + 1)

    def bucket_curve(sub):
        curve = {}
        for name in ["status_quo"] + names:
            col = sub[f"loss_{name}"] * per32 / sub["effective_balance"]
            g = col.groupby(sub.bucket, observed=True)
            eg = sub.offline_epochs.groupby(sub.bucket, observed=True).mean()
            curve[name] = {
                str(b): {"n": int(cnt), "mean_dtr": float(days_to_recoup(m, ctx)),
                         "mean_offline_epochs": float(eg[b])}
                for b, m, cnt in zip(g.mean().index, g.mean().to_numpy(),
                                     g.count().to_numpy())
            }
        return curve

    straggler = bucket_curve(fresh)
    straggler_contiguous = bucket_curve(fresh[fresh.density >= 0.8])

    # ---------------- summary per variant
    results = {}
    for name, rise, fall in VARIANTS:
        f, emas = trajectories[name]
        fe = f[ev_mask]
        norm = costs[f"loss_{name}"] * per32 / costs["effective_balance"]
        norm_sq = costs["loss_status_quo"] * per32 / costs["effective_balance"]
        dtr = float(days_to_recoup(norm.mean(), ctx))
        dtr_sq = float(days_to_recoup(norm_sq.mean(), ctx))

        # tail share of scaled penalties: paid after cohort 90% recovery
        if e90 is not None:
            e90_epoch = ev.event_lo + e90
            tail_pen = data.con.sql(
                f"""
                SELECT sum(f."{name}") FILTER (WHERE o.epoch >= {e90_epoch}) * 1.0
                       / sum(f."{name}")
                FROM offline_validators o
                JOIN factors_sweep f ON f.epoch = o.epoch AND f.slot_index = o.slot_index
                WHERE o.epoch BETWEEN {ev.event_lo} AND {ev.tail_hi}
                """
            ).fetchone()[0]
        else:
            tail_pen = None

        # synthetic: sustained 10% cohort for 7 days on this event's baseline.
        # offline balances are per-slot committee sums: share * (tab/32) = share * ref
        ref_med = int(df["slot_reference_balance"].median())
        base_off = int(base_share * ref_med)
        sus_off = np.full(7 * SLOTS_PER_DAY, base_off + int(0.10 * ref_med), dtype=np.int64)
        sus_ref = np.full_like(sus_off, ref_med)
        sf, _ = asym_factors(sus_off, sus_ref, seeds[name], rise, fall)
        # per-epoch cost for a member: source pen + factor * target pen + forgone
        br = ctx.base_reward()
        per_epoch_flat = br * (TIMELY_SOURCE_WEIGHT + TIMELY_SOURCE_WEIGHT
                               + TIMELY_TARGET_WEIGHT + TIMELY_HEAD_WEIGHT) / WEIGHT_DENOMINATOR
        # (source pen + forgone src+tgt+head reward) is factor-independent
        mean_daily_factor = [float(sf[d*SLOTS_PER_DAY:(d+1)*SLOTS_PER_DAY].mean())
                             for d in range(7)]
        sus_cost = sum(
            EPOCHS_PER_DAY * (per_epoch_flat
                              + br * mf * TIMELY_TARGET_WEIGHT / WEIGHT_DENOMINATOR)
            for mf in mean_daily_factor
        )
        # re-arm: decay the end-of-tail EMA forward at baseline, then hit it
        # with this event's own peak excess again
        ema_end = int(emas[-1])
        ob = int(base_off)
        rearm = {}
        # peak is a share of assigned stake; per-slot excess = share * (tab/32)
        onset_excess = int(peak * ref_med)
        ema_at_onset = int(emas[int(np.argmax(ev_mask))])
        f_onset_orig = min(1 + PENALTY_SLOPE * max(0, onset_excess + base_off - ema_at_onset)
                           // int(np.median(ref)), MAX_PENALTY_FACTOR)
        for days in (3, 7, 14):
            e = ema_end
            for _ in range(days * SLOTS_PER_DAY):
                e = e + (ob - e) // rise if ob > e else e - (e - ob) // fall
            f2 = min(1 + PENALTY_SLOPE * max(0, onset_excess + base_off - e)
                     // int(np.median(ref)), MAX_PENALTY_FACTOR)
            rearm[f"+{days}d"] = {"factor": int(f2),
                                  "vs_original_onset": float(f2 / max(1, f_onset_orig))}

        results[name] = {
            "rise_constant": rise, "fall_constant": fall,
            "rise_half_life_days": round(hl_days(rise), 2),
            "fall_half_life_days": round(hl_days(fall), 2),
            "seed_ema_eth": seeds[name] / 1e9,
            "peak_factor": int(fe.max()),
            "mean_factor_event": float(fe.mean()),
            "mean_days_to_recoup": dtr,
            "vs_status_quo": dtr / dtr_sq,
            "tail_share_of_scaled_penalties": (
                float(tail_pen) if tail_pen is not None else None),
            "quiet_window": quiet[name],
            "synthetic_sustained_10pct_7d_dtr": float(days_to_recoup(sus_cost, ctx)),
            "synthetic_sustained_daily_mean_factor": [round(x, 1) for x in mean_daily_factor],
            "rearm": rearm,
        }

    out = {
        "event": ev.key,
        "title": ev.title,
        "event_epochs": [ev.event_lo, ev.event_hi],
        "tail_hi": ev.tail_hi,
        "baseline_offline_share": base_share,
        "peak_excess_offline_share": float(peak),
        "cohort_recovery_epochs_from_onset": rec,
        "cohort_recovery_hours_from_onset": {
            k: (round(v * hours_per_epoch, 1) if v is not None else None)
            for k, v in rec.items()},
        "n_validators": int(len(costs)),
        "n_chronic_excluded_from_straggler": int(costs.chronic.sum()),
        "variants": results,
        "straggler_curve": straggler,
        "straggler_curve_contiguous": straggler_contiguous,
        "n_contiguous": int((fresh.density >= 0.8).sum()),
    }
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"sweep_{ev.key}.json")
    with open(path, "w") as fh:
        json.dump(out, fh, indent=1)
    print(f"wrote {path}")
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    events_mod.add_event_arg(ap)
    ap.add_argument("--out", default="results_sweep")
    args = ap.parse_args()
    run(args.event, args.out)


if __name__ == "__main__":
    main()
