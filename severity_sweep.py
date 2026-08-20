#!/usr/bin/env python3
"""Severity sweep: how much harder could the curve hit, and what would the
worst cases look like, on the real events?

Two families:
  A. cap-scaled  -- slope = 3*(cap-1), saturation stays at 1/3, the
                    worst-case bleed rate rises with the cap
  B. slope-only  -- cap stays 128 (bleed unchanged), slope raised so the
                    curve is steeper and saturates below 1/3

For each (variant, event): mean/p95 days-to-recoup, vs status quo, network
extra burn, cost of a fully-offline operator per 1% of stake, and the May
2023 bystander cost (validators swept in for 1-2 epochs during the storms).
"""

import json

import numpy as np

import events as events_mod
from eip7716_historical import (
    ChainContext, EventData, days_to_recoup,
    EFFECTIVE_BALANCE_INCREMENT,
    TIMELY_SOURCE_WEIGHT, TIMELY_TARGET_WEIGHT, TIMELY_HEAD_WEIGHT,
    WEIGHT_DENOMINATOR,
)
from window_sweep import warm_seed, asym_factors
from eip7716_model import EPOCHS_PER_DAY

# (label, slope, cap)
VARIANTS = [
    ("A: 381/128 (current)", 381, 128),
    ("A: 573/192", 573, 192),
    ("A: 765/256", 765, 256),
    ("A: 1149/384", 1149, 384),
    ("A: 1533/512", 1533, 512),
    ("B: 762/128", 762, 128),
    ("B: 1143/128", 1143, 128),
    ("B: 1524/128", 1524, 128),
]
SMOOTH = 2**17


def run_event(key):
    ev = events_mod.get(key)
    data = EventData.load(ev.derived_dir)
    df = data.con.sql(
        "SELECT slot, epoch, slot_index, offline_bal, assigned_bal, "
        "total_active_balance, slot_reference_balance FROM slots ORDER BY slot"
    ).df()
    offline = df.offline_bal.to_numpy(dtype=np.int64)
    ref = df.slot_reference_balance.to_numpy(dtype=np.int64)
    seed = ((df.epoch >= ev.seed_lo) & (df.epoch <= ev.seed_hi)).to_numpy()
    tab = int(df.loc[df.epoch.between(ev.event_lo, ev.event_hi),
                     "total_active_balance"].median())
    ctx = ChainContext(tab, el_apr_bonus=ev.el_bonus, eth_price_usd=ev.eth_price)

    # EMA path is slope/cap independent: compute once
    ema0 = warm_seed(offline[seed], ref[seed], SMOOTH, SMOOTH)
    _, emas = asym_factors(offline, ref, ema0, SMOOTH, SMOOTH)
    excess = np.maximum(offline - np.minimum(offline, emas), 0)

    fdf = df[["epoch", "slot_index"]].copy()
    names = []
    for label, slope, cap in VARIANTS:
        col = f"v{slope}_{cap}"
        names.append((label, slope, cap, col))
        fdf[col] = np.minimum(1 + slope * excess // ref, cap).astype(np.int64)

    con = data.con
    con.register("sev_factors", fdf)
    part = con.sql(
        "SELECT epoch, total_active_balance, "
        "(source_only_bal + both_bal)::HUGEINT AS src_bal, "
        "(target_only_bal + both_bal)::HUGEINT AS tgt_bal, "
        "head_bal::HUGEINT AS head_bal FROM epochs").df()
    con.register("sev_part", part)
    sums = ",".join(f'sum(f."{c}") AS "s_{c}"' for _, _, _, c in names)
    rows = con.sql(f"""
        SELECT o.validator, count(*) AS n, any_value(o.effective_balance) AS eb,
               {sums},
               sum(p.src_bal * 1.0 / p.total_active_balance) AS ssrc,
               sum(p.tgt_bal * 1.0 / p.total_active_balance) AS stgt,
               sum(p.head_bal * 1.0 / p.total_active_balance) AS shead
        FROM offline_validators o
        JOIN sev_factors f ON f.epoch = o.epoch AND f.slot_index = o.slot_index
        JOIN sev_part p ON p.epoch = o.epoch
        WHERE o.epoch BETWEEN {ev.event_lo} AND {ev.event_hi}
        GROUP BY o.validator
    """).df()

    eb = rows.eb.to_numpy(dtype=np.int64)
    br = (eb // EFFECTIVE_BALANCE_INCREMENT) * ctx.base_reward_per_increment
    n = rows.n.to_numpy(dtype=np.int64)
    forgone = br * (TIMELY_SOURCE_WEIGHT * rows.ssrc.to_numpy()
                    + TIMELY_TARGET_WEIGHT * rows.stgt.to_numpy()
                    + TIMELY_HEAD_WEIGHT * rows.shead.to_numpy()) / WEIGHT_DENOMINATOR
    pen_src = br * n * TIMELY_SOURCE_WEIGHT / WEIGHT_DENOMINATOR
    loss_sq = forgone + pen_src + br * n * TIMELY_TARGET_WEIGHT / WEIGHT_DENOMINATOR
    per32 = 32_000_000_000
    norm_sq = loss_sq * per32 / eb
    dtr_sq = days_to_recoup(norm_sq.mean(), ctx)

    n_event_epochs = ev.event_hi - ev.event_lo + 1
    # a fully-offline archetype meets the mean per-slot factor of the window
    ev_mask = ((fdf.epoch >= ev.event_lo) & (fdf.epoch <= ev.event_hi)).to_numpy()
    vals_per_1pct = 0.01 * tab / per32

    out = {"event": key, "dtr_sq_days": float(dtr_sq), "variants": {}}
    for label, slope, cap, col in names:
        pen_t = br * rows[f"s_{col}"].to_numpy() * TIMELY_TARGET_WEIGHT / WEIGHT_DENOMINATOR
        loss = forgone + pen_src + pen_t
        norm = loss * per32 / eb
        # fully-offline archetype: down all event epochs at the mean factor
        mf = float(fdf.loc[ev_mask, col].mean())
        arch_loss = (ctx.att_reward_ideal_per_epoch()
                     + ctx.base_reward() * (TIMELY_SOURCE_WEIGHT + mf * TIMELY_TARGET_WEIGHT)
                     / WEIGHT_DENOMINATOR) * n_event_epochs
        out["variants"][label] = {
            "mean_dtr": float(days_to_recoup(norm.mean(), ctx)),
            "p95_dtr": float(days_to_recoup(np.quantile(norm, 0.95), ctx)),
            "vs_sq": float(norm.mean() / norm_sq.mean()),
            "extra_burn_eth": float((pen_t - br * n * TIMELY_TARGET_WEIGHT
                                     / WEIGHT_DENOMINATOR).sum() / 1e9),
            "mean_principal_pct": float(norm.mean() / per32 * 100),
            "archetype_eth_per_1pct_stake": float(arch_loss * vals_per_1pct / 1e9),
            "archetype_usd_per_1pct_stake": float(arch_loss * vals_per_1pct / 1e9
                                                  * ctx.eth_price_usd),
        }
        if key == "may2023":
            m = rows.n.to_numpy() <= 2
            out["variants"][label]["bystander_dtr"] = float(
                days_to_recoup((loss[m] * per32 / eb[m]).mean(), ctx))
    return out


def main():
    results = {k: run_event(k) for k in ("may2023", "besu", "nethermind", "prysm")}
    with open("results_sweep/severity_sweep.json", "w") as fh:
        json.dump(results, fh, indent=1)

    # ---- rendering
    print("worst-case bleed (fully offline validator, cap pinned):")
    for label, slope, cap in VARIANTS:
        bleed = (TIMELY_SOURCE_WEIGHT + cap * TIMELY_TARGET_WEIGHT) / WEIGHT_DENOMINATOR
        # base rewards/epoch -> % principal/day at ~40M ETH staked (br/32eth ~ 10144 gwei/ep July 2026 anchor: use prysm ctx)
        ev = events_mod.get("prysm")
        ctx = ChainContext(ev.total_active_balance_gwei, el_apr_bonus=ev.el_bonus)
        pct_day = bleed * ctx.base_reward() * EPOCHS_PER_DAY / 32_000_000_000 * 100
        sat = 100 * (cap - 1) / slope
        print(f"  {label:22s} saturates at {sat:4.1f}% offline, bleed {pct_day:.2f}%/day")
    print()
    hdr = f"{'variant':22s}" + "".join(f"{k:>16s}" for k in results)
    for metric, fmt in (("mean_dtr", "{:.2f}d"), ("vs_sq", "{:.1f}x"),
                        ("p95_dtr", "{:.2f}d"), ("mean_principal_pct", "{:.3f}%"),
                        ("extra_burn_eth", "{:,.0f}"),
                        ("archetype_usd_per_1pct_stake", "${:,.0f}")):
        print(metric)
        print(hdr)
        for label, slope, cap in VARIANTS:
            row = f"{label:22s}"
            for k, r in results.items():
                row += f"{fmt.format(r['variants'][label][metric]):>16s}"
            print(row)
        print()
    print("may2023 bystander (swept in 1-2 epochs), days-to-recoup:")
    for label, _, _ in VARIANTS:
        print(f"  {label:22s} {results['may2023']['variants'][label]['bystander_dtr']:.2f}d")


if __name__ == "__main__":
    main()
