#!/usr/bin/env python3
"""Render the window/skew sweep results as markdown tables.

Reads every results_sweep/sweep_<event>.json present and emits one report:
per-event variant tables, contiguous straggler curves, and a cross-event
summary. Pure formatting -- all numbers come from window_sweep.py output.
"""

import glob
import json
import os
import sys

ORDER = ["may2023", "besu", "nethermind", "prysm"]
SHOW = ["status_quo", "sym_2^14", "sym_2^15", "sym_2^16", "sym_2^17", "sym_2^18",
        "rise_2^9_fall_2^17", "rise_2^11_fall_2^17", "rise_2^12_fall_2^17",
        "rise_2^13_fall_2^17", "rise_2^15_fall_2^17",
        "fall_2^15_rise_2^17", "fall_2^13_rise_2^17"]
CURVE_KEYS = ["status_quo", "sym_2^14", "sym_2^17", "sym_2^18",
              "rise_2^12_fall_2^17", "rise_2^13_fall_2^17"]
BUCKETS = ["0-2h", "2-4h", "4-6h", "6-8h", "8-12h", "12-18h", "18-24h",
           "24-36h", "36-48h", "48-72h", "72h+"]


def fmt_d(x):
    if x is None:
        return "--"
    return f"{x*24:.1f} h" if x < 1 else f"{x:.2f} d"


def main(out_dir="results_sweep"):
    paths = {os.path.basename(p)[6:-5]: p
             for p in glob.glob(os.path.join(out_dir, "sweep_*.json"))
             if "smoke" not in p}
    lines = ["# Window-length and skew sweep — real-event results\n"]

    for key in [k for k in ORDER if k in paths] + sorted(set(paths) - set(ORDER)):
        d = json.load(open(paths[key]))
        rec = d["cohort_recovery_hours_from_onset"]
        lines += [
            f"## {d['title']}\n",
            f"Event epochs {d['event_epochs'][0]}–{d['event_epochs'][1]}, "
            f"tail to {d['tail_hi']}. Peak excess offline "
            f"**{100*d['peak_excess_offline_share']:.1f}%** of stake against a "
            f"{100*d['baseline_offline_share']:.2f}% baseline. Cohort recovery: "
            f"50% at {rec['epochs_to_50pct_recovered']} h, "
            f"90% at {rec['epochs_to_90pct_recovered']} h, "
            f"99% at {rec['epochs_to_99pct_recovered']} h from onset. "
            f"{d['n_validators']:,} validators affected "
            f"({d['n_contiguous']:,} with contiguous outages).\n",
            "| variant | rise HL | fall HL | peak factor | mean days-to-recoup "
            "| vs status quo | tail share | quiet >1x | sustained 10%·7d "
            "| re-arm +3d | +7d | +14d |",
            "|---|---|---|---|---|---|---|---|---|---|---|---|",
        ]
        for name in SHOW:
            if name == "status_quo" or name not in d["variants"]:
                continue
            r = d["variants"][name]
            q = r["quiet_window"]["share_slots_factor_gt1"]
            ts = r["tail_share_of_scaled_penalties"]
            ts_s = f"{100*ts:.1f}%" if ts is not None else "--"
            lines.append(
                f"| `{name}` | {r['rise_half_life_days']:.1f} d "
                f"| {r['fall_half_life_days']:.1f} d | {r['peak_factor']}x "
                f"| {fmt_d(r['mean_days_to_recoup'])} | {r['vs_status_quo']:.1f}x "
                f"| {ts_s} | {100*q:.1f}% "
                f"| {fmt_d(r['synthetic_sustained_10pct_7d_dtr'])} "
                f"| {r['rearm']['+3d']['vs_original_onset']:.2f} "
                f"| {r['rearm']['+7d']['vs_original_onset']:.2f} "
                f"| {r['rearm']['+14d']['vs_original_onset']:.2f} |"
            )

        lines += [
            "\n### Cost by personal recovery hour (contiguous outages only)\n",
            "Mean days-to-recoup per 32 ETH, bucketed by the hour (from onset) "
            "at which the validator's outage ended.\n",
            "| recovered by | n | " + " | ".join(f"`{k}`" for k in CURVE_KEYS) + " |",
            "|---|---|" + "---|" * len(CURVE_KEYS),
        ]
        sc = d["straggler_curve_contiguous"]
        for b in BUCKETS:
            v0 = sc["status_quo"].get(b)
            if not v0:
                continue
            row = f"| {b} | {v0['n']:,} |"
            for k in CURVE_KEYS:
                v = sc[k].get(b)
                row += f" {fmt_d(v['mean_dtr'])} |" if v else " -- |"
            lines.append(row)
        lines.append("")

    with open(os.path.join(out_dir, "SWEEP_REPORT.md"), "w") as fh:
        fh.write("\n".join(lines))
    print(f"wrote {os.path.join(out_dir, 'SWEEP_REPORT.md')}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "results_sweep")
