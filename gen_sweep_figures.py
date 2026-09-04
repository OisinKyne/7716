#!/usr/bin/env python3
"""Figures for the window/skew sweep. Reads results_sweep/sweep_*.json."""

import json
import os

import numpy as np
import matplotlib
matplotlib.use("Agg")
import numpy as np
import matplotlib.pyplot as plt

BLUE, GREEN, GRAY = "#2a78d6", "#008300", "#52514e"
ORANGE = "#c4590a"
AXIS_GRAY = "#c3c2b7"
SURFACE = "#fcfcfb"
plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
    "savefig.facecolor": SURFACE, "font.size": 10,
    "axes.spines.top": False, "axes.spines.right": False,
})

BUCKETS = ["0-2h", "2-4h", "4-6h", "6-8h", "8-12h", "12-18h", "18-24h",
           "24-36h", "36-48h", "48-72h", "72h+"]
EVENT_ORDER = ["may2023", "besu", "nethermind", "prysm"]


def load(out_dir="results_sweep"):
    out = {}
    for key in EVENT_ORDER:
        p = os.path.join(out_dir, f"sweep_{key}.json")
        if os.path.exists(p):
            out[key] = json.load(open(p))
    return out


def w1_straggler(data, out_dir):
    """Cost vs recovery hour for the down-from-onset cohort, per event.

    Events whose onset cohort recovered inside a single bucket (the May 2023
    cliff incidents) carry no straggler information and are skipped.
    """
    def populated(key):
        sc = data[key]["straggler_curve_onset"]["status_quo"]
        return sum(1 for b in BUCKETS if sc.get(b, {}).get("n", 0) >= 200) >= 3

    events = [k for k in EVENT_ORDER if k in data and populated(k)]
    fig, axes = plt.subplots(1, len(events), figsize=(4.2 * len(events), 4.4),
                             sharey=False)
    if len(events) == 1:
        axes = [axes]
    series = [("status_quo", GRAY, "status quo"),
              ("sym_2^17", BLUE, "revised (2$^{17}$, as drafted)"),
              ("rise_2^12_fall_2^17", ORANGE, "fast-rise skew (2$^{12}$ up)")]
    for ax, key in zip(axes, events):
        sc = data[key]["straggler_curve_onset"]
        for name, color, label in series:
            xs, ys = [], []
            for i, b in enumerate(BUCKETS):
                v = sc.get(name, {}).get(b)
                if v and v["n"] >= 200:
                    xs.append(i)
                    ys.append(v["mean_dtr"])
            ax.plot(xs, ys, "o-", color=color, label=label, lw=1.8, ms=4)
        ax.set_xticks(range(len(BUCKETS)))
        ax.set_xticklabels(BUCKETS, rotation=45, ha="right", fontsize=8)
        ax.set_title(data[key]["title"], fontsize=9)
        ax.set_xlabel("hour the outage ended, from onset")
        ax.grid(axis="y", alpha=0.25)
    axes[0].set_ylabel("mean days-to-recoup per 32 ETH")
    axes[0].legend(frameon=False, fontsize=8)
    fig.suptitle("What a validator down from the original onset paid, by when it recovered\n"
                 "(second-wave outages that began after the peak are excluded for clarity)",
                 y=1.05)
    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, "w1_straggler_curves.png"),
                dpi=160, bbox_inches="tight")
    plt.close(fig)


def w2_frontier(data, out_dir, event="prysm"):
    """Straggler premium vs sustained deterrence, one point per variant."""
    d = data[event]
    fig, ax = plt.subplots(figsize=(6.8, 5.0))
    for name, r in d["variants"].items():
        sc = d["straggler_curve_contiguous"][name]
        hi, lo = sc.get("24-36h"), sc.get("6-8h")
        if not (hi and lo):
            continue
        premium = hi["mean_dtr"] / lo["mean_dtr"]
        x = r["synthetic_sustained_10pct_7d_dtr"]
        if name.startswith("sym"):
            color, marker = BLUE, "o"
        elif name.startswith("rise"):
            color, marker = ORANGE, "s"
        else:
            color, marker = GREEN, "^"
        ax.scatter(x, premium, color=color, marker=marker, s=55, zorder=3)
        label = name.replace("_fall_2^17", "").replace("_rise_2^17", " fall")
        ax.annotate(label, (x, premium), textcoords="offset points",
                    xytext=(7, 4), fontsize=8, color=color)
    sq = d["straggler_curve_contiguous"]["status_quo"]
    sq_premium = sq["24-36h"]["mean_dtr"] / sq["6-8h"]["mean_dtr"]
    ax.axhline(sq_premium, color=GRAY, lw=1.2, ls="--")
    ax.text(ax.get_xlim()[1] * 0.98, sq_premium * 1.01,
            f"status quo premium ({sq_premium:.1f}x)", color=GRAY,
            ha="right", fontsize=8)
    ax.set_xlabel("deterrence: days-to-recoup for a sustained 10%-of-stake, "
                  "7-day outage (synthetic)")
    ax.set_ylabel("straggler premium: cost of 24–36 h recovery ÷ 6–8 h "
                  f"({d['title'].split(' ')[0]} event, measured)")
    ax.set_title("The trade-off the smoothing window actually controls")
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, "w2_frontier.png"),
                dpi=160, bbox_inches="tight")
    plt.close(fig)


def w3_window_effect(data, out_dir):
    """Symmetric window length: event severity flat, sustained scales."""
    syms = ["sym_2^14", "sym_2^15", "sym_2^16", "sym_2^17", "sym_2^18"]
    hls = [data[EVENT_ORDER[-1]]["variants"][s]["rise_half_life_days"] for s in syms]
    fig, ax1 = plt.subplots(figsize=(6.8, 4.6))
    for key, color in zip([k for k in EVENT_ORDER if k in data],
                          [GREEN, GRAY, "#8a5fbf", BLUE]):
        ys = [data[key]["variants"][s]["vs_status_quo"] for s in syms]
        ax1.plot(hls, ys, "o-", color=color, lw=1.8, ms=4,
                 label=f"{key} (event, vs status quo)")
    ax2 = ax1.twinx()
    ax2.spines.right.set_visible(True)
    ys = [data[EVENT_ORDER[-1]]["variants"][s]["synthetic_sustained_10pct_7d_dtr"]
          for s in syms]
    ax2.plot(hls, ys, "s--", color=ORANGE, lw=1.8, ms=5,
             label="sustained 10%·7d (synthetic)")
    ax2.set_ylabel("sustained-outage days-to-recoup", color=ORANGE)
    ax2.tick_params(axis="y", colors=ORANGE)
    ax1.set_xscale("log", base=2)
    ax1.set_xticks(hls)
    ax1.set_xticklabels([f"{h:.1f} d\n2^{14+i}" for i, h in enumerate(hls)])
    ax1.set_xlabel("smoothing half-life (symmetric)")
    ax1.set_ylabel("event severity, vs status quo")
    ax1.set_title("Window length barely moves real (cliff) events; "
                  "it prices sustained outages")
    ax1.legend(frameon=False, fontsize=8, loc="center left")
    ax1.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, "w3_window_effect.png"),
                dpi=160, bbox_inches="tight")
    plt.close(fig)


def w4_relative_multiple(data, out_dir):
    """The answer to 'does this hammer slow responders': the penalty multiple
    over today's rules, for validators down since event onset, by recovery
    hour. A duration-proportional design would be a flat line; front-loading
    makes it fall.
    """
    fig, ax = plt.subplots(figsize=(7.4, 5.0))
    colors = {"besu": GRAY, "nethermind": "#8a5fbf", "prysm": BLUE}
    for key in ("besu", "nethermind", "prysm"):
        if key not in data:
            continue
        sc = data[key]["straggler_curve_onset"]
        xs, ys = [], []
        for i, b in enumerate(BUCKETS):
            v0 = sc["status_quo"].get(b)
            v1 = sc["sym_2^17"].get(b)
            if v0 and v1 and v0["n"] >= 200 and v0["mean_dtr"] > 0:
                xs.append(i)
                ys.append(v1["mean_dtr"] / v0["mean_dtr"])
        ax.plot(xs, ys, "o-", color=colors[key], lw=2, ms=5,
                label=data[key]["title"])
        ax.annotate(f"{ys[0]:.0f}x", (xs[0], ys[0]), textcoords="offset points",
                    xytext=(-4, 8), color=colors[key], fontsize=10, ha="right")
        ax.annotate(f"{ys[-1]:.0f}x", (xs[-1], ys[-1]), textcoords="offset points",
                    xytext=(6, 4), color=colors[key], fontsize=10)
    ax.axhline(1, color=GRAY, lw=1.2, ls="--")
    ax.text(0.1, 1.15, "1x = today's rules", color=GRAY, fontsize=9)
    ax.set_yscale("log")
    ax.set_yticks([1, 2, 4, 8, 16, 32, 64])
    ax.set_yticklabels(["1x", "2x", "4x", "8x", "16x", "32x", "64x"])
    ax.set_xticks(range(len(BUCKETS)))
    ax.set_xticklabels(BUCKETS, rotation=45, ha="right", fontsize=9)
    ax.set_xlabel("hour the outage ended, from onset "
                  "(validators down since event onset)")
    ax.set_ylabel("penalty multiple vs today's rules")
    ax.set_title("The multiple falls as recovery stretches:\n"
                 "fast responders bear the deterrent, stragglers converge toward today")
    ax.legend(frameon=False, fontsize=9, loc="upper right")
    ax.grid(alpha=0.25, which="both")
    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, "w4_relative_multiple.png"),
                dpi=160, bbox_inches="tight")
    plt.close(fig)


def w5_cost_growth(data, out_dir):
    """Cost as a multiple of a ~2.5h responder's cost, vs hours actually down
    (linear axes, onset cohort). Today's rules are exactly proportional to
    time down — a straight line, identical for every event. The revised
    mechanism bends flat: staying down ~10x longer costs 2-3x more, not 10x.
    """
    fig, ax = plt.subplots(figsize=(7.6, 5.2))
    colors = {"besu": GRAY, "nethermind": "#8a5fbf", "prysm": BLUE}
    ref_bucket = "2-4h"
    max_h = 0.0
    for key in ("besu", "nethermind", "prysm"):
        if key not in data:
            continue
        sc = data[key]["straggler_curve_onset"]["sym_2^17"]
        ref = sc.get(ref_bucket)
        if not ref:
            continue
        ref_h = ref["mean_offline_epochs"] * 32 * 12 / 3600
        xs, ys = [], []
        for b in BUCKETS:
            v = sc.get(b)
            if v and v["n"] >= 200:
                xs.append(v["mean_offline_epochs"] * 32 * 12 / 3600)
                ys.append(v["mean_dtr"] / ref["mean_dtr"])
        ax.plot(xs, ys, "o-", color=colors[key], lw=2, ms=5,
                label=f'{data[key]["title"]} (revised)')
        max_h = max(max_h, max(xs))
        offsets = {"besu": (8, 2), "nethermind": (8, 10), "prysm": (8, -22)}
        ax.annotate(f"{xs[-1]/ref_h:.0f}x longer down,\n{ys[-1]:.1f}x the cost",
                    (xs[-1], ys[-1]), textcoords="offset points",
                    xytext=offsets[key], color=colors[key], fontsize=9)
        # today's rules: cost strictly proportional to time down, same for
        # every event — one reference line through (ref_h, 1)
        if key == "prysm":
            hh = np.linspace(0, max_h * 1.02, 50)
            ax.plot(hh, hh / ref_h, ls="--", color="#b3352b", lw=1.8,
                    label="today's rules (any event): cost ∝ time down")
            ax.annotate(f"{max_h/ref_h:.0f}x longer down,\n{max_h/ref_h:.0f}x the cost",
                        (max_h, max_h / ref_h), textcoords="offset points",
                        xytext=(-8, 4), color="#b3352b", fontsize=9, ha="right")
    ax.axhline(1, color=AXIS_GRAY, lw=1)
    ax.set_xlabel("hours actually offline (validators down since event onset)")
    ax.set_ylabel(f"cost, as a multiple of a ~2.5 h responder's cost")
    ax.set_title("Today, cost is proportional to how long you're down;\n"
                 "revised, the charge is front-loaded and the tail is nearly flat")
    ax.legend(frameon=False, fontsize=9, loc="upper left")
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, "w5_cost_growth.png"),
                dpi=160, bbox_inches="tight")
    plt.close(fig)


def main(out_dir="results_sweep"):
    data = load(out_dir)
    w1_straggler(data, out_dir)
    w2_frontier(data, out_dir)
    w3_window_effect(data, out_dir)
    w4_relative_multiple(data, out_dir)
    w5_cost_growth(data, out_dir)
    print("wrote w1/w2/w3/w4/w5 figures to", out_dir)


if __name__ == "__main__":
    main()
