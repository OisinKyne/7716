#!/usr/bin/env python3
"""
Sensitivity of the headline to the four judgement calls in the pipeline.

  1. seeding window for `smoothed_offline_balance`
  2. execution-layer share of normal income (the days-to-recoup denominator)
  3. treating the `uncollected` cohort as online rather than offline -- the one
     place the chain's "offline" label is arguably wrong
  4. whether the drafted mechanism scales source+target or target only

Prints a table; writes results/sensitivity.json.
"""

from __future__ import annotations

import argparse
import json
import os

import duckdb

import events

from eip7716_historical import (
    ChainContext,
    EVENT_HI,
    EVENT_LO,
    EventData,
    days_to_recoup,
    run_mechanisms,
    validator_costs,
)

def seed_windows(spec):
    """Alternative baseline windows for this event, headline first."""
    out = {f"{spec.seed_label}, {spec.seed_hi - spec.seed_lo + 1} epochs (headline)":
           (spec.seed_lo, spec.seed_hi)}
    if spec.seed_hi - spec.seed_lo >= 48:
        out[f"{spec.seed_label}, last 48 epochs"] = (spec.seed_hi - 47, spec.seed_hi)
    if spec.marker_epoch is not None and spec.marker_epoch < spec.event_lo:
        out[f"post-{spec.marker_label}, immediately pre-event"] = (spec.marker_epoch, spec.event_lo - 1)
    out["full pull range before the event"] = (spec.pull_lo, spec.event_lo - 1)
    return out


def el_bonuses(spec):
    """EL-income sensitivity around this event's measured share."""
    m = spec.el_bonus
    return {
        f"{m:.3f} — measured, 21 days around the event": m,
        f"{m * 0.957:.3f} — lower bound (locally-built blocks earn nothing)": m * 0.957,
        f"{m * 1.049:.3f} — upper bound (locally-built earn like relayed)": m * 1.049,
        "0.21 — the repo's July-2026 default": 0.21,
    }


def headline(data, df, ctx, lo, hi, exclude_uncollected=None):
    costs = validator_costs(data, df, ctx, lo, hi)
    if exclude_uncollected is not None:
        costs = costs[~costs.validator.isin(exclude_uncollected)]
    per32 = 32_000_000_000
    out = {}
    for k in ("status_quo", "original", "revised"):
        norm = costs[f"loss_{k}"] * per32 / costs["effective_balance"]
        out[k] = float(days_to_recoup(norm.mean(), ctx))
    out["n"] = int(len(costs))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    events.add_event_arg(ap)
    ap.add_argument("--derived-dir", default=None)
    ap.add_argument("--results-dir", default=None)
    args = ap.parse_args()

    spec = events.get(args.event)
    args.derived_dir = args.derived_dir or spec.derived_dir
    args.results_dir = args.results_dir or spec.results_dir
    EV_LO, EV_HI = spec.event_lo, spec.event_hi
    SEED_WINDOWS = seed_windows(spec)
    EL_BONUSES = el_bonuses(spec)

    data = EventData.load(args.derived_dir)
    base_df = data.arrays()
    tab = int(
        base_df.loc[base_df.epoch.between(EV_LO, EV_HI), "total_active_balance"].median()
    )
    out = {}

    print("=== 1. seeding window for smoothed_offline_balance ===")
    print(f"{'window':<40}{'epochs':>16}{'seed (ETH/slot)':>18}{'baseline':>10}"
          f"{'peak factor':>13}{'days-to-recoup':>16}")
    out["seed_window"] = {}
    for name, (lo, hi) in SEED_WINDOWS.items():
        df, seeds = run_mechanisms(base_df, lo, hi)
        ctx = ChainContext(tab)
        h = headline(data, df, ctx, EV_LO, EV_HI)
        ev = df[df.epoch.between(EV_LO, EV_HI)]
        print(f"{name:<40}{f'{lo}-{hi}':>16}{seeds['ema_seed_gwei'] / 1e9:>18,.0f}"
              f"{seeds['seed_offline_share'] * 100:>9.3f}%{int(ev.factor_revised.max()):>13}"
              f"{h['revised']:>15.2f}d")
        out["seed_window"][name] = {
            "epochs": [lo, hi],
            "seed_eth": seeds["ema_seed_gwei"] / 1e9,
            "baseline_share": seeds["seed_offline_share"],
            "peak_factor": int(ev.factor_revised.max()),
            "days_to_recoup_revised": h["revised"],
        }

    df, _ = run_mechanisms(base_df, spec.seed_lo, spec.seed_hi)  # back to the headline seeding

    print("\n=== 2. execution-layer share of normal income (denominator only) ===")
    print(f"{'assumption':<56}{'status quo':>13}{'revised':>11}")
    out["el_bonus"] = {}
    for name, el in EL_BONUSES.items():
        ctx = ChainContext(tab, el_apr_bonus=el)
        h = headline(data, df, ctx, EV_LO, EV_HI)
        print(f"{name:<56}{h['status_quo'] * 24:>11.2f}h{h['revised']:>10.2f}d")
        out["el_bonus"][name] = h

    print("\n=== 3. counting the `uncollected` cohort as online ===")
    ctx = ChainContext(tab)
    cls_path = os.path.join(args.results_dir, "offline_classified.parquet")
    out["uncollected"] = {}
    base = headline(data, df, ctx, EV_LO, EV_HI)
    print(f"{'as measured (chain definition, headline)':<56}"
          f"{base['status_quo'] * 24:>11.2f}h{base['revised']:>10.2f}d  n={base['n']:,}")
    if os.path.exists(cls_path):
        con = duckdb.connect()
        # validators whose offline epochs were *all* `uncollected`: alive, correct,
        # and simply never included
        vs = con.sql(
            f"""
            SELECT validator FROM read_parquet('{cls_path}')
            GROUP BY validator
            HAVING bool_and(bucket = 'uncollected')
            """
        ).df().validator.to_numpy()
        alt = headline(data, df, ctx, EV_LO, EV_HI, exclude_uncollected=set(vs.tolist()))
        print(f"{'excluding validators that were only ever uncollected':<56}"
              f"{alt['status_quo'] * 24:>11.2f}h{alt['revised']:>10.2f}d  n={alt['n']:,}")
        out["uncollected"] = {"headline": base, "excluded": alt,
                              "n_excluded": int(len(vs))}
    else:
        print("  (run attribution.py first)")

    print("\n=== 4. what the drafted mechanism scales ===")
    print("The drafted EIP names only `penalty_factor`; the draft Lighthouse")
    print("implementation scaled source+target (40/64), the revision scales target")
    print("only (26/64). The headline uses the wider, more generous reading.")
    ctx = ChainContext(tab)
    costs = validator_costs(data, df, ctx, EV_LO, EV_HI)
    per32 = 32_000_000_000
    br = costs.base_reward.to_numpy()
    n = costs.offline_epochs.to_numpy()
    mf = costs.mean_factor_original.to_numpy()
    narrow = costs.forgone_reward.to_numpy() + br * n * 14 / 64 + br * mf * n * 26 / 64
    norm_n = narrow * per32 / costs.effective_balance.to_numpy()
    wide = float(days_to_recoup(
        (costs.loss_original * per32 / costs.effective_balance).mean(), ctx))
    print(f"  drafted, scaling source+target (headline): {wide * 24:.3f} h")
    print(f"  drafted, scaling target only:              "
          f"{days_to_recoup(norm_n.mean(), ctx) * 24:.3f} h")
    print(f"  status quo:                                {base['status_quo'] * 24:.3f} h")
    out["drafted_scope"] = {
        "source_plus_target_days": wide,
        "target_only_days": float(days_to_recoup(norm_n.mean(), ctx)),
        "status_quo_days": base["status_quo"],
    }

    with open(os.path.join(args.results_dir, "sensitivity.json"), "w") as fh:
        json.dump(out, fh, indent=2)


if __name__ == "__main__":
    main()
