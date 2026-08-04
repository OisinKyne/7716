#!/usr/bin/env python3
"""
Cross-event comparison figure: what three real mainnet client-bug outages would
have cost under the drafted and revised forms of EIP-7716.

Same palette and rcParams as gen_figures.py / gen_figures_historical.py.
Writes figures/cmp1_ladder.png.
"""
import json
import os

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

import events  # noqa: E402

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

ORDER = ["besu", "nethermind", "prysm"]
LABEL = {
    "besu": "Besu halt\n2024-01-06",
    "nethermind": "Nethermind bug\n2024-01-21",
    "prysm": "Prysm / post-Fusaka\n2025-12-04",
}

rows = []
for k in ORDER:
    spec = events.get(k)
    s = json.load(open(os.path.join(spec.results_dir, "summary.json")))
    ev = s["event"]
    sq = ev["status_quo"]["mean_days_to_recoup"]
    rows.append({
        "key": k,
        "peak": s["peak_offline_share"] * 100,
        "drafted": ev["original"]["mean_days_to_recoup"] / sq,
        "revised": ev["revised"]["mean_days_to_recoup"] / sq,
    })

x = np.arange(len(rows))
w = 0.36
fig, ax = plt.subplots(figsize=(9.0, 5.0))

ax.axhline(1.0, color=GRAY, lw=1.5, ls=(0, (4, 3)), zorder=3)
ax.text(-0.46, 1.06, "status quo = 1x", color=GRAY, fontsize=9.5, va="bottom")

b1 = ax.bar(x - w / 2, [r["drafted"] for r in rows], w, color=GREEN, alpha=0.9,
            label="EIP-7716 as drafted (4096 / 4)", zorder=4)
b2 = ax.bar(x + w / 2, [r["revised"] for r in rows], w, color=BLUE, alpha=0.9,
            label="EIP-7716 revised (381 / 128 / 2^17)", zorder=4)

for r, rect in zip(rows, b1):
    ax.text(rect.get_x() + rect.get_width() / 2, rect.get_height() * 1.06,
            f"{r['drafted']:.2f}x", ha="center", color=GREEN, fontsize=10, fontweight="bold")
for r, rect in zip(rows, b2):
    ax.text(rect.get_x() + rect.get_width() / 2, rect.get_height() * 1.06,
            f"{r['revised']:.1f}x", ha="center", color=BLUE, fontsize=11, fontweight="bold")

ax.set_yscale("log")
ax.set_ylim(0.8, 60)
ax.set_yticks([1, 2, 5, 10, 25])
ax.set_yticklabels(["1x", "2x", "5x", "10x", "25x"])
ax.set_xticks(x)
ax.set_xticklabels([f"{LABEL[r['key']]}\n{r['peak']:.1f}% peak offline" for r in rows])
ax.set_ylabel("cost to a caught validator, relative to today")
ax.set_title("Three mainnet client-bug outages, priced by both versions of EIP-7716")
ax.legend(loc="upper left", fontsize=10)

ax.text(0, -0.30,
        "Each bar is the mean cost to a validator caught in that outage, per 32 ETH, "
        "as a multiple of what it actually paid.\n"
        "The revised mechanism scales with event size. The drafted mechanism does not "
        "move on any of the three — it sits inside\nthe status quo's own error bar "
        "throughout. Ratios are comparable across events; absolute days are not, "
        "because\nexecution-layer income differed by era.",
        transform=ax.transAxes, color=MUTED, fontsize=9, va="top")

fig.tight_layout()
os.makedirs("figures", exist_ok=True)
fig.savefig("figures/cmp1_ladder.png", bbox_inches="tight")
plt.close(fig)
print("wrote figures/cmp1_ladder.png")
