#!/usr/bin/env python3
"""
Figures for the EIP-7716 ethresear.ch post.
Light-surface styling; validated categorical palette:
  blue  #2a78d6 -> the revised mechanism (this proposal)
  green #008300 -> EIP-7716 as currently specced (PAF=4096, cap=4)
  gray  #52514e -> status quo (no correlation penalties)
Color follows the entity across every figure.
"""
import math
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from eip7716_model import Network, simulate, SLOTS_PER_EPOCH, EPOCHS_PER_DAY

# ---------------------------------------------------------------- constants
net = Network()
BR = net.base_reward_gwei_per_32eth()
REW = net.att_reward_per_epoch_gwei()
PEN_T = BR * 26 / 64
PEN_S = BR * 14 / 64
FULL = net.full_reward_per_epoch_gwei()
M0 = net.baseline_miss
USD = net.eth_price_usd
EP_H = EPOCHS_PER_DAY / 24
CAP, HL_D = 256, 12.6
SLOPE = 3 * (CAP - 1)   # 765: cap binds at exactly 1/3
ALPHA = 1 - 0.5 ** (1 / (HL_D * EPOCHS_PER_DAY * 32))

BLUE, GREEN, GRAY = "#2a78d6", "#008300", "#52514e"
INK, MUTED, GRID, AXIS, SURF = "#0b0b0b", "#898781", "#e1e0d9", "#c3c2b7", "#fcfcfb"

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
import os
os.makedirs(FIGDIR, exist_ok=True)


# ------------------------------------------------------------- mechanisms
def factors_new(spike, agg_h, total_h, recovery_hl_h=None):
    """Per-epoch mean factor, revised mechanism (absolute slope)."""
    n = int(total_h * EP_H) * 32
    dn = int(agg_h * EP_H) * 32
    ema, pfs = M0, []
    for s in range(n):
        if s < dn:
            m = M0 + spike
        elif recovery_hl_h:
            t_h = (s - dn) / 32 / EP_H
            m = M0 + spike * 0.5 ** (t_h / recovery_hl_h)
        else:
            m = M0
        pfs.append(min(1 + SLOPE * max(0.0, m - ema), CAP))
        ema += ALPHA * (m - ema)
    return np.array([np.mean(pfs[i:i+32]) for i in range(0, n - 31, 32)])


def factors_old(spike, agg_h, total_h, paf=4096, cap=4):
    """Per-epoch mean factor, EIP-7716 as specced (exact integer sim)."""
    n = int(total_h * EP_H) * 32
    dn = int(agg_h * EP_H) * 32
    sched = [M0] + [M0 + spike] * dn + [M0] * (n - dn)
    res = simulate(sched, paf=paf, maxf=cap)[1:]
    pfs = [pf for pf, _ in res]
    return np.array([np.mean(pfs[i:i+32]) for i in range(0, n - 31, 32)])


def cost_new(spike, r_h, agg_h):
    f = factors_new(spike, agg_h, max(r_h, agg_h) + 240)
    r = int(round(r_h * EP_H))
    return sum(REW + PEN_S + (f[e] if e < len(f) else 1.0) * PEN_T for e in range(r))


def cost_old(spike, r_h, agg_h):
    f = factors_old(spike, agg_h, max(r_h, agg_h) + 240)
    r = int(round(r_h * EP_H))
    # old spec scaled source+target (Lighthouse scope): apply factor to 40/64
    return sum(REW + (f[e] if e < len(f) else 1.0) * (PEN_S + PEN_T) for e in range(r))


def cost_now(r_h):
    return int(round(r_h * EP_H)) * (REW + PEN_S + PEN_T)


def leak_cost(spike, r_h, agg_h):
    if spike < 1 / 3:
        return 0.0
    r_ep, leak_ep = int(round(r_h * EP_H)), int(agg_h * EP_H)
    score, total = 0, 0.0
    for e in range(r_ep + 2000):
        down, in_leak = e < r_ep, e < leak_ep
        score = score + 4 if down else score - min(1, score)
        if not in_leak:
            score -= min(16, score)
        if down and score > 0:
            total += 32e9 * score / (4 * 2**24)
        if score == 0 and not down:
            break
    return total


def gwei_to_usd(g):
    return g / 1e9 * USD


# ---------------------------------------------------- F1: factor trajectory
def fig1():
    hours = 84
    x = np.arange(int(hours * EP_H)) / EP_H
    new = factors_new(0.10, 72, hours + 12)[:len(x)]
    old = factors_old(0.10, 72, hours + 12)[:len(x)]
    stag = factors_new(0.10, 72, hours + 12, recovery_hl_h=6)[:len(x)]
    fig, ax = plt.subplots(figsize=(8.4, 4.5))
    ax.plot(x, new, color=BLUE, lw=2, label="Revised mechanism")
    ax.plot(x, stag, color=BLUE, lw=1.4, ls=(0, (3, 2)), alpha=0.7,
            label="…with staggered recovery (6h half-life)")
    ax.plot(x, old, color=GREEN, lw=2, label="EIP-7716 as specced (4096 / 4)")
    ax.set_yscale("log")
    ax.set_ylim(0.55, 300)
    ax.set_yticks([1, 4, 16, 64])
    ax.set_yticklabels(["1x", "4x", "16x", "64x"])
    ax.axvspan(0, 72, color=GRID, alpha=0.35, zorder=0)
    ax.text(36, 88, "10% of stake offline for 3 days", ha="center", color=MUTED, fontsize=10)
    ax.annotate("renormalises to 1x within ~2 minutes\n(and gives a discount window at recovery)",
                xy=(1.2, 1.06), xytext=(8, 2.6), color=GREEN, fontsize=9.5, ha="left",
                arrowprops=dict(arrowstyle="-", color=GREEN, lw=1))
    ax.annotate(f"opens at {min(1 + SLOPE * 0.10, CAP):.0f}x, proportional to the event size;\nthe EMA absorbs the anomaly over ~2 weeks",
                xy=(20, 36), xytext=(22, 4.7), color=BLUE, fontsize=9.5,
                arrowprops=dict(arrowstyle="-", color=BLUE, lw=1))
    ax.annotate("collapses to 1x when\nthe cohort recovers", xy=(72.5, 5), xytext=(74, 11),
                color=BLUE, fontsize=9.5,
                arrowprops=dict(arrowstyle="-", color=BLUE, lw=1))
    ax.set_xlabel("hours since outage onset")
    ax.set_ylabel("penalty factor")
    ax.set_title("Penalty factor during a 10%-of-stake, 3-day correlated outage")
    ax.legend(loc="upper right", fontsize=10)
    fig.tight_layout()
    fig.savefig(f"{FIGDIR}/f1_factor_trajectory.png")
    plt.close(fig)


# ------------------------------------------- F2: the cap was the wrong knob
def fig2():
    caps = [4, 16, 64, 256]
    old_costs = [gwei_to_usd(cost_old_cap(0.10, 24, 24, cap)) for cap in caps]
    new_cost = gwei_to_usd(cost_new(0.10, 24, 24))
    now = gwei_to_usd(cost_now(24))
    fig, ax = plt.subplots(figsize=(8, 4.2))
    xs = np.arange(len(caps) + 1)
    vals = old_costs + [new_cost]
    colors = [GREEN] * len(caps) + [BLUE]
    bars = ax.bar(xs, vals, width=0.62, color=colors, zorder=3)
    ax.axhline(now, color=GRAY, lw=1.6, ls=(0, (4, 3)), zorder=2)
    ax.set_xticks(xs)
    ax.set_xticklabels([f"cap {c}" for c in caps] + ["revised\n(cap 128)"])
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, v + 2.5, f"${v:.0f}",
                ha="center", fontsize=10.5, color=INK)
    ax.set_ylabel("loss per 32 ETH validator (USD)")
    ax.set_title("Raising the cap alone does nothing: 10% outage, 24h, current update rule")
    note = ("Dashed line: status quo ($6.17, no correlation penalty). The current rule has a fixed "
            "excess-penalty\nbudget, Σ(factor−1) = PAF·Δmiss/32 — the cap only "
            "redistributes it. The revised mechanism replaces\nthe budget with a curve.")
    ax.text(0, -0.24, note, transform=ax.transAxes, color=MUTED, fontsize=9, va="top")
    fig.tight_layout()
    fig.savefig(f"{FIGDIR}/f2_cap_invariance.png", bbox_inches="tight")
    plt.close(fig)


def cost_old_cap(spike, r_h, agg_h, cap):
    f = factors_old(spike, agg_h, max(r_h, agg_h) + 240, cap=cap)
    r = int(round(r_h * EP_H))
    return sum(REW + (f[e] if e < len(f) else 1.0) * (PEN_S + PEN_T) for e in range(r))


# --------------------------------------------- F3: onset factor vs event size
def fig3():
    spikes = np.linspace(0.001, 0.45, 300)
    onset = np.minimum(1 + SLOPE * spikes, CAP)
    fig, ax = plt.subplots(figsize=(8, 4.2))
    ax.plot(spikes * 100, onset, color=BLUE, lw=2)
    ax.axhline(CAP, color=AXIS, lw=1)
    ax.axvline(100 / 3, color=GRAY, lw=1.4, ls=(0, (4, 3)))
    ax.text(100 / 3 + 0.7, 55, "finality threshold —\ninactivity leak activates,\nquadratic principal-level\nlosses take over",
            color=GRAY, fontsize=9.5, va="center")
    ax.text(2, CAP + 3, f"MAX_PENALTY_FACTOR = {CAP}: slope = 3·(cap−1) pins saturation at exactly one third",
            color=MUTED, fontsize=9.5)
    for s in (0.01, 0.05, 0.10, 0.20):
        y = min(1 + SLOPE * s, CAP)
        lbl = f"{s:.0%} → {y:.0f}x"
        ax.plot([s * 100], [y], "o", color=BLUE, ms=7, mec=SURF, mew=1.5)
        ax.annotate(lbl, xy=(s * 100, y), xytext=(s * 100 + 1.2, y - 18),
                    color=INK, fontsize=10)
    ax.set_xlabel("stake newly offline in the same slot (%)")
    ax.set_ylabel("onset penalty factor")
    ax.set_ylim(0, 288)
    ax.set_title("Onset severity scales with the size of the correlated failure")
    fig.tight_layout()
    fig.savefig(f"{FIGDIR}/f3_onset_vs_size.png")
    plt.close(fig)


# ------------------------------------------- F4: cost vs rectification time
def fig4():
    rects = np.array([1, 2, 3, 4, 6, 9, 12, 18, 24, 36, 48, 72])
    now = np.array([gwei_to_usd(cost_now(r)) for r in rects])
    old = np.array([gwei_to_usd(cost_old(0.10, r, 24)) for r in rects])
    new = np.array([gwei_to_usd(cost_new(0.10, r, 24)) for r in rects])
    fig, ax = plt.subplots(figsize=(8, 4.4))
    ax.plot(rects, new, color=BLUE, lw=2, marker="o", ms=4, label="Revised mechanism", zorder=3)
    ax.plot(rects, old, color=GREEN, lw=2.4, marker="o", ms=4, label="EIP-7716 as specced", zorder=3)
    ax.plot(rects, now, color=GRAY, lw=1.5, ls=(0, (4, 3)), label="Status quo", zorder=4)
    ax.annotate("as-specced is indistinguishable\nfrom no mechanism at all",
                xy=(30, 8.4), xytext=(24, 24), color=GREEN, fontsize=10,
                arrowprops=dict(arrowstyle="-", color=GREEN, lw=1))
    ax.annotate("cost is front-loaded: the curve\nflattens once the cohort recovers",
                xy=(46, 76), xytext=(4.5, 70), color=BLUE, fontsize=10, va="center",
                arrowprops=dict(arrowstyle="-", color=BLUE, lw=1))
    ax.set_xscale("log")
    ax.set_xticks([1, 3, 6, 12, 24, 48, 72])
    ax.set_xticklabels(["1h", "3h", "6h", "12h", "24h", "48h", "72h"])
    ax.minorticks_off()
    ax.set_xlabel("individual recovery time (cohort offline for 24h)")
    ax.set_ylabel("loss per 32 ETH validator (USD)")
    ax.set_title("What a validator caught in a 10% correlated outage loses")
    ax.legend(loc="center left", fontsize=10)
    fig.tight_layout()
    fig.savefig(f"{FIGDIR}/f4_cost_vs_rectification.png")
    plt.close(fig)


# ----------------------------------------------- F5: marginal cost per hour
def fig5():
    f = factors_new(0.10, 24, 24 + 240)
    per_epoch = np.array([REW + PEN_S + fe * PEN_T for fe in f])
    cum = np.concatenate([[0.0], np.cumsum(per_epoch)])
    def cum_at(h):
        e = h * EP_H
        i = int(e)
        return cum[i] + (e - i) * per_epoch[min(i, len(per_epoch) - 1)]
    hours = np.arange(0, 48)
    new = np.array([gwei_to_usd(cum_at(h + 1) - cum_at(h)) for h in hours])
    now = gwei_to_usd(cost_now(1))
    fig, ax = plt.subplots(figsize=(8, 4.2))
    ax.bar(hours + 0.5, new, width=0.86, color=BLUE, zorder=3)
    ax.axhline(now, color=GRAY, lw=1.6, ls=(0, (4, 3)))
    ax.text(31.5, now + 0.16, "status quo: $0.25 / hour", color=GRAY, fontsize=10)
    ax.axvline(24, color=AXIS, lw=1)
    ax.text(24.7, 2.1, "cohort recovers", color=MUTED, fontsize=9.5, rotation=90, va="center")
    ax.set_xlabel("hour of downtime (10% correlated outage)")
    ax.set_ylabel("marginal cost of that hour (USD)")
    ax.set_title("Front-loading: each additional hour offline costs less, not more")
    ax.set_xticks([0, 6, 12, 18, 24, 30, 36, 42, 48])
    fig.tight_layout()
    fig.savefig(f"{FIGDIR}/f5_marginal_hours.png")
    plt.close(fig)


# --------------------------------- F6: total cost vs event size (leak stack)
def fig6():
    spikes = np.concatenate([np.linspace(0.005, 0.333, 45), np.linspace(0.3334, 0.45, 20)])
    att = np.array([gwei_to_usd(cost_new(s, 24, 24)) for s in spikes])
    leak = np.array([gwei_to_usd(leak_cost(s, 24, 24)) for s in spikes])
    now = np.array([gwei_to_usd(cost_now(24) + leak_cost(s, 24, 24)) for s in spikes])
    fig, ax = plt.subplots(figsize=(8, 4.6))
    ax.fill_between(spikes * 100, 0, att, color=BLUE, alpha=0.85,
                    label="attestation penalties (this proposal)", lw=0)
    ax.fill_between(spikes * 100, att, att + leak, color=GREEN, alpha=0.85,
                    label="inactivity leak (unchanged)", lw=0)
    ax.plot(spikes * 100, now, color=GRAY, lw=1.6, ls=(0, (4, 3)), label="status quo total")
    ax.axvline(100 / 3, color=GRAY, lw=1, alpha=0.6)
    ax.text(100 / 3 - 0.8, 610, "finality\nthreshold", color=MUTED, fontsize=9.5, ha="right")
    ax.text(4, 560, "this proposal prices the 1–33% band\nthe protocol currently ignores",
            color=INK, fontsize=10)
    ax.set_ylim(0, 660)
    ax.set_xlabel("stake offline for 24 hours (%)")
    ax.set_ylabel("loss per fully-offline 32 ETH validator (USD)")
    ax.set_title("Layering with the inactivity leak: 24-hour outage, by event size")
    ax.legend(loc="upper left", fontsize=10)
    fig.tight_layout()
    fig.savefig(f"{FIGDIR}/f6_leak_layering.png")
    plt.close(fig)


# --------------------------------------------------- F7: re-arm / sawtooth
def fig7():
    # re-arm after a MAJOR crisis: 40% of stake down for 3 days
    gaps = np.linspace(0.25, 60, 240)
    ema_end = M0
    for s in range(int(72 * EP_H) * 32):
        ema_end += ALPHA * ((M0 + 0.40) - ema_end)
    onset2 = []
    for g in gaps:
        ema = M0 + (ema_end - M0) * math.exp(-math.log(2) * g / HL_D)
        onset2.append(min(1 + SLOPE * max(0.0, M0 + 0.10 - ema), CAP))  # 10% repeat event
    fig, ax = plt.subplots(figsize=(8, 4.1))
    ax.plot(gaps, onset2, color=BLUE, lw=2, label="Revised mechanism")
    fresh = 1 + SLOPE * 0.10
    ax.axhline(fresh, color=AXIS, lw=1)
    ax.text(1, fresh + 1.2, f"fresh-event onset: {fresh:.0f}x", color=MUTED, fontsize=10)
    ax.annotate("a counter-based design at equivalent deterrence\n(PAF ≈ 2²⁷) stays fully disarmed for ~8 months",
                xy=(41, 5.5), color=GREEN, fontsize=9.5, ha="center")
    ax.plot([0, 60], [1, 1], color=GREEN, lw=2)
    ax.axvline(HL_D, color=AXIS, lw=1)
    ax.text(HL_D + 0.8, 3, f"EMA half-life ({HL_D:.0f} days)", color=MUTED, fontsize=9.5, rotation=90, va="bottom")
    ax.set_ylim(0, 92)
    ax.set_xlim(0, 60)
    ax.set_xlabel("days since a major crisis (40% of stake down for 3 days)")
    ax.set_ylabel("onset factor of a new 10% event")
    ax.set_title("Re-arming the deterrent after a major crisis")
    fig.tight_layout()
    fig.savefig(f"{FIGDIR}/f7_rearm.png")
    plt.close(fig)


if __name__ == "__main__":
    for f in [fig1, fig2, fig3, fig4, fig5, fig6, fig7]:
        f()
        print(f"{f.__name__} done")
