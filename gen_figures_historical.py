#!/usr/bin/env python3
"""
Figures for the historical backtest: 2025-12-04 post-Fusaka correlated outage.

Same styling and palette as `gen_figures.py`, so the two sets sit together:
  blue  #2a78d6 -> the revised mechanism (this proposal)
  green #008300 -> EIP-7716 as drafted (PAF=4096, cap=4)
  gray  #52514e -> status quo (no correlation penalties)
Color follows the entity across every figure.

Writes figures/h1..h5.
"""

import json
import os

import duckdb
import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

BLUE, GREEN, GRAY = "#2a78d6", "#008300", "#52514e"
INK, MUTED, GRID, AXIS, SURF = "#0b0b0b", "#898781", "#e1e0d9", "#c3c2b7", "#fcfcfb"
# sequential ramp for the behavioural buckets, keyed off the blue
RAMP = ["#12395f", "#2a78d6", "#7fb0e6", "#b9d3f2", "#c3c2b7"]

plt.rcParams.update({
    "figure.facecolor": SURF, "axes.facecolor": SURF, "savefig.facecolor": SURF,
    "text.color": INK, "axes.edgecolor": AXIS, "axes.labelcolor": "#52514e",
    "xtick.color": MUTED, "ytick.color": MUTED, "axes.grid": True,
    "grid.color": GRID, "grid.linewidth": 0.8, "axes.axisbelow": True,
    "axes.spines.top": False, "axes.spines.right": False,
    "font.family": "sans-serif", "font.size": 11,
    "axes.titlesize": 13, "axes.titleweight": "bold", "axes.titlelocation": "left",
    "legend.frameon": False, "figure.dpi": 150,
})

FIGDIR = "figures"
RESULTS = "results"
DERIVED = "data/derived"
os.makedirs(FIGDIR, exist_ok=True)

EVENT_LO, EVENT_HI = 411439, 411480
FUSAKA = 411392
GENESIS, SECONDS_PER_SLOT = 1_606_824_023, 12

con = duckdb.connect(config={"threads": 8})
SUMMARY = json.load(open(os.path.join(RESULTS, "summary.json")))
slots = con.sql(
    f"SELECT * FROM read_parquet('{RESULTS}/slot_factors.parquet') ORDER BY slot"
).df()
epochs = con.sql(f"SELECT * FROM read_parquet('{DERIVED}/epochs.parquet') ORDER BY epoch").df()


def hours_since_onset(epoch_or_slot, is_slot=False):
    # cast first: the parquet columns are uint32 and the pre-onset window would
    # underflow
    v = np.asarray(epoch_or_slot, dtype=np.int64)
    slot0 = EVENT_LO * 32
    return ((v if is_slot else v * 32).astype(np.float64) - slot0) * SECONDS_PER_SLOT / 3600.0


# --------------------------------------------- H1: the Step 0 answer, visually
def h1():
    e = epochs[(epochs.epoch >= FUSAKA - 12) & (epochs.epoch <= EVENT_HI + 20)].copy()
    x = hours_since_onset(e.epoch.to_numpy())
    tot = e.assigned_bal.to_numpy()
    offline = e.offline_bal.to_numpy() / tot * 100
    src_only = e.source_only_bal.to_numpy() / tot * 100
    tgt_only = e.target_only_bal.to_numpy() / tot * 100

    fig, ax = plt.subplots(figsize=(8.6, 4.6))
    ax.fill_between(x, 0, offline, color=BLUE, alpha=0.9, lw=0,
                    label="missed BOTH flags — offline, scaled by EIP-7716")
    ax.fill_between(x, offline, offline + src_only, color=GREEN, alpha=0.9, lw=0,
                    label="timely source, missed target — not scaled")
    ax.fill_between(x, offline + src_only, offline + src_only + tgt_only,
                    color=GRAY, alpha=0.9, lw=0, label="missed source, timely target — not scaled")
    ax.axvline(0, color=AXIS, lw=1)
    ax.axvline(hours_since_onset(FUSAKA), color=AXIS, lw=1)
    ax.text(hours_since_onset(FUSAKA) - 0.25, 7.5, "Fusaka activation", color=MUTED,
            fontsize=9.5, rotation=90, va="bottom", ha="center")
    ax.text(-0.25, 7.5, "postmortem window opens", color=MUTED, fontsize=9.5,
            rotation=90, va="bottom", ha="center")
    ax.annotate(
        "97.8% of the non-attesting stake\nat the plateau missed both flags:\ndark, not slow",
        xy=(1.6, 22.6), xytext=(3.3, 15.4), color=INK, fontsize=10,
        arrowprops=dict(arrowstyle="-", color=INK, lw=1))
    ax.text(-4.35, 5.0,
            "a smaller cohort went dark at\nFusaka activation, five hours\n"
            "before the main event:\ntwo root causes, one trigger",
            color=MUTED, fontsize=9, va="bottom")
    ax.set_xlabel("hours from the start of the postmortem window (2025-12-04 02:49:59Z)")
    ax.set_ylabel("share of active stake (%)")
    ax.set_ylim(0, 30)
    ax.set_xlim(-7, 7)
    ax.set_title("Step 0: the missing stake missed both flags, so the factor applies")
    ax.legend(loc="upper left", fontsize=9.5, bbox_to_anchor=(0.0, 1.0))
    fig.tight_layout()
    fig.savefig(f"{FIGDIR}/h1_flag_breakdown.png")
    plt.close(fig)


# ------------------------------------------- H2: factor trajectory, real data
def h2():
    s = slots[(slots.epoch >= FUSAKA - 10) & (slots.epoch <= EVENT_HI + 26)].copy()
    x = hours_since_onset(s.slot.to_numpy(), is_slot=True)
    FLOOR = 0.68
    # a validator attests once per epoch, in one slot of it, so the quantity it
    # meets in expectation is the epoch-mean factor; the per-slot series is drawn
    # faintly underneath
    ep_mean = s.groupby("epoch")[["factor_revised", "factor_original"]].mean()
    xe = hours_since_onset(ep_mean.index.to_numpy())

    fig, ax = plt.subplots(figsize=(8.6, 4.8))
    ax.axvspan(0, hours_since_onset(EVENT_HI + 1), color=GRID, alpha=0.35, zorder=0)
    ax.plot(x, np.maximum(s.factor_original, FLOOR), color=GREEN, lw=0.5, alpha=0.25, zorder=2)
    ax.plot(x, s.factor_revised, color=BLUE, lw=0.5, alpha=0.25, zorder=2)
    ax.plot(xe, np.maximum(ep_mean.factor_original, FLOOR), color=GREEN, lw=1.8,
            label="EIP-7716 as drafted (4096 / 4)", zorder=3)
    ax.plot(xe, ep_mean.factor_revised, color=BLUE, lw=1.8,
            label="Revised mechanism (381 / 128)", zorder=4)
    ax.plot(x, np.ones(len(x)), color=GRAY, lw=1.5, ls=(0, (4, 3)), label="Status quo", zorder=5)
    ax.axvline(hours_since_onset(FUSAKA), color=AXIS, lw=1, zorder=1)
    ax.set_yscale("log")
    ax.set_ylim(0.30, 900)
    ax.set_yticks([1, 4, 16, 64, 128])
    ax.set_yticklabels(["1x", "4x", "16x", "64x", "128x"])
    ax.axhline(128, color=AXIS, lw=1, zorder=1)
    ax.text(-5.6, 152, "MAX_PENALTY_FACTOR = 128 — never reached: peak offline 29.8% < 33%",
            color=MUTED, fontsize=9)
    ax.text(hours_since_onset(FUSAKA) + 0.12, 330, "Fusaka\nactivation", color=MUTED, fontsize=9)
    ax.annotate(f"peak {SUMMARY['factor_revised']['max']}x",
                xy=(0.55, SUMMARY["factor_revised"]["max"]), xytext=(-1.9, 300),
                color=BLUE, fontsize=10, arrowprops=dict(arrowstyle="-", color=BLUE, lw=1))
    ax.annotate("the first cohort alone already prices at ~8x",
                xy=(-3.0, 8.0), xytext=(-5.9, 26), color=BLUE, fontsize=9.5,
                arrowprops=dict(arrowstyle="-", color=BLUE, lw=1))
    ax.annotate("the counter renormalises inside one epoch and never leaves 1x again;\n"
                "faint: the per-slot series, which dithers 0x-4x even at baseline because\n"
                "NET_EXCESS_PENALTIES is an integer near 0.4 at a 0.3% offline rate",
                xy=(1.2, 1.0), xytext=(-4.6, 0.315), color=GREEN, fontsize=9,
                arrowprops=dict(arrowstyle="-", color=GREEN, lw=1))
    ax.set_xlabel("hours from onset (shaded: the 42 postmortem epochs); "
                  "bold = epoch mean, faint = per slot")
    ax.set_ylabel("penalty factor")
    ax.set_title("Penalty factor the two mechanisms would have produced")
    ax.legend(loc="upper right", fontsize=10)
    fig.tight_layout()
    fig.savefig(f"{FIGDIR}/h2_factor_trajectory_real.png")
    plt.close(fig)


# --------------------------------------------------- H3: days-to-recoup bars
def h3():
    ev, tail = SUMMARY["event"], SUMMARY["event_plus_tail"]
    keys = ["status_quo", "original", "revised"]
    labels = ["Status quo", "EIP-7716\nas drafted", "EIP-7716\nrevised"]
    colors = [GRAY, GREEN, BLUE]
    a = [ev[k]["mean_days_to_recoup"] for k in keys]
    b = [tail[k]["mean_days_to_recoup"] for k in keys]

    fig, ax = plt.subplots(figsize=(8, 4.4))
    xs = np.arange(3)
    ax.bar(xs - 0.19, a, width=0.36, color=colors, zorder=3)
    ax.bar(xs + 0.19, b, width=0.36, color=colors, alpha=0.45, zorder=3)
    for i, (va, vb) in enumerate(zip(a, b)):
        ax.text(i - 0.19, va + 0.06, f"{va * 24:.1f} h" if va < 1 else f"{va:.2f} d",
                ha="center", fontsize=10, color=INK)
        ax.text(i + 0.19, vb + 0.06, f"{vb * 24:.1f} h" if vb < 1 else f"{vb:.2f} d",
                ha="center", fontsize=10, color=MUTED)
    ax.set_xticks(xs)
    ax.set_xticklabels(labels)
    ax.set_ylim(0, 3.05)
    ax.set_ylabel("days of normal income to earn the loss back")
    ax.set_title("What the December 2025 outage cost a caught validator, per 32 ETH")
    ax.annotate("as drafted, the event costs 1.01x what it costs today —\n"
                "the counter absorbs it inside one epoch",
                xy=(1.0, 0.20), xytext=(0.05, 1.35), color=GREEN, fontsize=10,
                arrowprops=dict(arrowstyle="-", color=GREEN, lw=1))
    ax.annotate(f"{ev['revised']['mean_days_to_recoup'] / ev['status_quo']['mean_days_to_recoup']:.0f}x "
                "the status quo",
                xy=(1.81, 2.40), xytext=(1.02, 2.68), color=BLUE, fontsize=10,
                arrowprops=dict(arrowstyle="-", color=BLUE, lw=1))
    ax.text(0, -0.235,
            "Solid: the 42 postmortem epochs. Faded: through the full recovery tail "
            "(to epoch 411700).\nThe status-quo cost nearly doubles over the tail; the "
            "revised cost rises 3% — the charge is front-loaded onto\nthe correlated "
            "onset, not onto how long a solo staker takes to recover.",
            transform=ax.transAxes, color=MUTED, fontsize=9, va="top")
    fig.tight_layout()
    fig.savefig(f"{FIGDIR}/h3_days_to_recoup.png", bbox_inches="tight")
    plt.close(fig)


# ------------------------------------- H4: distribution of per-validator loss
def h4():
    costs = con.sql(
        f"SELECT * FROM read_parquet('{RESULTS}/validator_costs_event.parquet')"
    ).df()
    per32 = 32e9
    day = SUMMARY["event"]["status_quo"]["mean_loss_gwei_per_32eth"] / (
        SUMMARY["event"]["status_quo"]["mean_days_to_recoup"]
    )
    sq = costs.loss_status_quo * per32 / costs.effective_balance / day
    rv = costs.loss_revised * per32 / costs.effective_balance / day
    fig, ax = plt.subplots(figsize=(8.2, 4.4))
    for series, color, label in ((sq, GRAY, "Status quo"), (rv, BLUE, "Revised mechanism")):
        v = np.sort(series.to_numpy())
        ax.plot(v, np.arange(1, len(v) + 1) / len(v) * 100, color=color, lw=2, label=label)
    ax.set_xscale("log")
    ax.set_xlim(3e-3, 22)
    ax.set_xticks([0.01, 0.1, 1, 10])
    ax.set_xticklabels(["15 min", "2.4 h", "1 day", "10 days"])
    ax.minorticks_off()
    ax.set_xlabel("days of normal income to earn the loss back, per 32 ETH")
    ax.set_ylabel("share of affected validators (%)")
    ax.set_title(f"Spread across the {len(costs):,} validators caught in the outage")
    ax.legend(loc="upper left", fontsize=10)
    ax.text(0.44, 0.90,
            "the flat shelf near the bottom of each\ncurve is the ~20% of the cohort that\n"
            "missed only one or two epochs; the\nsteep rise at the top is the deep\n"
            "cohort, down for most of the event",
            transform=ax.transAxes, color=MUTED, fontsize=9, ha="left", va="top")
    fig.tight_layout()
    fig.savefig(f"{FIGDIR}/h4_loss_distribution.png")
    plt.close(fig)


# ----------------------------------- H5: behavioural attribution through time
def h5():
    path = os.path.join(RESULTS, "attribution_onset.csv")
    if not os.path.exists(path):
        print("h5 skipped (run attribution.py first)")
        return
    import pandas as pd
    d = pd.read_csv(path).fillna(0.0)
    x = hours_since_onset(d.epoch.to_numpy())
    tot = epochs.set_index("epoch").loc[d.epoch, "assigned_bal"].to_numpy() / 1e9
    silent = d.silent_eth.to_numpy() / tot * 100
    desy = d.desynced_eth.to_numpy() / tot * 100
    unc = d.uncollected_eth.to_numpy() / tot * 100

    total = epochs.set_index("epoch").loc[d.epoch, "offline_bal"].to_numpy() / 1e9 / tot * 100
    other = np.maximum(total - silent - desy - unc, 0)

    fig, ax = plt.subplots(figsize=(8.6, 4.7))
    ax.fill_between(x, 0, silent, color=RAMP[0], lw=0, label="silent — nothing on the p2p network")
    ax.fill_between(x, silent, silent + desy, color=RAMP[1], lw=0,
                    label="desynced — signing on a stale justified checkpoint")
    ax.fill_between(x, silent + desy, silent + desy + unc, color=RAMP[2], lw=0,
                    label="uncollected — valid attestation gossiped, never included")
    ax.fill_between(x, silent + desy + unc, silent + desy + unc + other, color=RAMP[4], lw=0,
                    label="wrong-target, and validators already offline before Fusaka")
    ax.set_xlabel("hours from onset")
    ax.set_ylabel("share of active stake scored offline (%)")
    ax.set_ylim(0, 31)
    ax.set_title("What the offline stake was actually doing, from the p2p record")
    ax.legend(loc="upper right", fontsize=9.5)
    ax.text(0.985, 0.62,
            "sentry recall control: 99.996% of validators the\nchain did count were also "
            "seen in gossip, so absence\nfrom gossip is evidence, not a coverage gap",
            transform=ax.transAxes, color=MUTED, fontsize=9, ha="right", va="top")
    fig.tight_layout()
    fig.savefig(f"{FIGDIR}/h5_attribution.png")
    plt.close(fig)


if __name__ == "__main__":
    for f in [h1, h2, h3, h4, h5]:
        f()
        print(f"{f.__name__} done")
