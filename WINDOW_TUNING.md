# Window length and skew, tested against five years of mainnet outages

Is `OFFLINE_BALANCE_SMOOTHING_FACTOR = 2^17` (12.6-day half-life) the right
smoothing window, and is there a skew of the update rule that keeps the
penalty meaningful for everyone caught in a correlated outage without
hammering operators who take 24 hours to apply an 8-hour patch?

Method: the historical backtest harness ([BACKTEST.md](BACKTEST.md)), extended
with [`window_sweep.py`](window_sweep.py), which replays every catalogued real
event under 12 update-rule variants — symmetric half-lives 2^14–2^18 (1.6–25.2
days) and asymmetric rise/fall splits down to a 1.2-hour rise — and, because
the ingest records every validator's offline epochs individually, computes
each validator's cost **as a function of its own measured recovery hour**. No
public postmortem documents per-operator recovery distributions; this measures
them from chain data. Full tables in
[`results_sweep/SWEEP_REPORT.md`](results_sweep/SWEEP_REPORT.md); reproduce
with `window_sweep.py --event <key>` after the ingest.

A fourth event joins the catalog for this analysis: the **May 11–12, 2023
finality incidents** (epochs 200551–554 and 200750–759, participation floors
~40% and 30.7% per the Prysm postmortem). It is the only recorded event that
binds the cap, the only one above the one-third saturation point, and — at 21
hours apart — the only real back-to-back test of re-arming. It is scored under
its era's own (pre-Deneb) target rule and its own measured economics: the EL
share of income over that window was **0.63 of CL** (the early-May 2023
memecoin MEV spike; measured from relay payloads by `el_bonus.py`, range
0.44–0.83).

## The event catalog

Event-window days-to-recoup per 32 ETH, each event under its era's measured
economics:

| Event | peak offline | cohort 50% / 90% recovered | patch available | revised | vs today |
|---|---|---|---|---|---|
| May 11+12 2023 finality incidents | 69% (cap-bound, 314 slots at 128x) | self-healed in ~26 / ~64 min | +31.5 h (after recovery) | 0.97 d | **39.8x** |
| Besu halt, 2024-01-06 | 12.4% | 13 h event + 48 h resync tail | +13 h | 2.8 h | **2.2x** |
| Nethermind bug, 2024-01-21 | 18.8% | fast (restart-only fix) | +3.9 h | 11.2 h | **7.5x** |
| Prysm post-Fusaka, 2025-12-04 | 29.8% | 50% at 2.8 h, 90% at 6.7 h | +1.8 h (runtime flag) | 2.40 d | **22.7x** |

The drafted (`NET_EXCESS_PENALTIES`) mechanism scores 1.16x on May 2023 — a
no-op on its own motivating incident, alongside the 1.04x / 1.01x / 1.01x
already measured on the other three.

Recovery in the wild is patch-gated in only half the catalog: May 2023
self-healed before any patch existed, and December 2025 recovered on a runtime
flag. Where a binary patch did gate recovery, the "8-hour patch, 24-hour
operator" spread is real — Besu's resync-required fix produced a 48-hour tail.

## What the window length controls, and what it doesn't

![window effect](figures/w3_window_effect.png)

**Window length is nearly irrelevant to real events.** Every recorded outage
is a cliff: hours-scale, short against even the shortest candidate window.
Sweeping 2^14 → 2^18 moves the December 2025 event only 12.8x → 13.9x and May
2023 not at all; the straggler curves are indistinguishable. During cap-bound
storms the cap sets severity and the window does nothing.

**The window prices exactly one thing: sustained outages.** A synthetic
10%-of-stake cohort holding down for 7 days costs 39 d (2^14) → 92 d (2^17) →
100 d (2^18) of income to recoup. That is the deterrent against a large
operator or region staying dark.

**Re-arm is a non-issue at these scales.** A repeat of December 2025 three
days later meets 0.99 of the original onset factor at 2^17; in the real May
2023 double event, incident B hit the cap under every variant tested.

**Quiet-window behaviour is benign.** At the 2025 noise floor ~2% of slots
tick factor 2 (one doubled 26/64-weight penalty — cents); p99 = 2 across all
symmetric variants.

## The straggler question, answered from chain data

![straggler curves](figures/w1_straggler_curves.png)

Tail-friendliness comes from the mechanism's structure, not the window: the
factor tracks *current excess* offline balance, so when the cohort recovers
the factor collapses and whoever is still down pays little. Measured on
December 2025 (contiguous outages only): a validator recovering at 24–36 h
paid **1.40x** one recovering at 6–8 h. Today's rules charge **4.1x** for the
same spread. Same-duration outages timed after cohort recovery cost ~40% of
peak-timed ones. Cross-event confirmation: Nethermind's 24–36 h stragglers
paid 2.2x its onset cohort (7.2x under current rules); Besu's 48-hour resync
victims paid 1.4x today's cost for the same downtime.

May 2023 is the stress test for innocents — finality stalled, so healthy
validators' attestations couldn't land and were recorded offline. A bystander
swept in for 1–2 epochs paid 0.22 days of income (0.0012 ETH, ~$2.25 at the
era price); 90% of the missing stake at the plateau was dark by every chain
measure, and the both-flags gate exempted a further 5.3% of live-but-slow
stake. Under EIP-7045's full-epoch target window and Electra's larger
inclusion capacity the same storm would register fewer false-offline
validators, so 0.22 d is an upper bound on today's equivalent.

## Skew variants: what they buy, what they surrender

![frontier](figures/w2_frontier.png)

A fast-rise / slow-fall split (the reference chases the spike upward with an
hours-scale half-life, releases at 12.6 d) is the only lever that materially
changes within-event fairness, and the improvement is modest — 1.40x → ~1.2x
straggler premium — because cohort recovery already does the work. The cost is
disqualifying:

- **Sustained deterrence collapses.** Under a 1.2-hour rise (`2^9`), a
  20%-of-stake operator can hold a 3-day outage at mean factor **2.7** —
  barely above today. Under the symmetric rule the same outage runs at mean
  factor ~71. Straggler forgiveness and sustained-outage forgiveness are the
  same physical quantity: a global factor cannot distinguish "still down
  because slow to patch" from "still down, period". The only separator is
  whether the cohort collapses, which is what the symmetric rule already keys
  on.
- **Ramp attacks don't beat it, but only trivially.** "Boil the frog"
  (ramp offline slowly so the fast reference tracks you, then hold) never
  costs less than the cliff (ramp/cliff total ≥ 1.0 on every variant) — but
  only because fast-rise variants price *every* sustained outage near 1x.
- **Re-arm blindness appears**: 0.84–0.94 of onset factor for a mid-size
  repeat within a week (the cap rescues large repeats).

## Conclusion

**Keep `OFFLINE_BALANCE_SMOOTHING_FACTOR = 2^17`, symmetric.** Anything in
2^16–2^18 is defensible for real events (they are indistinguishable there);
2^17 keeps the sustained-outage deterrent meaningful (~92 days of income for a
10%-of-stake week), re-arms fully within days of cliff events, and is exactly
16 sync-committee periods. Going shorter buys nothing on any recorded event
and halves the sustained deterrent; asymmetric skew improves the measured
straggler premium marginally while cutting sustained deterrence 4–10x and
adding a second constant to the spec.
