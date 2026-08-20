# How severe? Choosing MAX_PENALTY_FACTOR from the real events

The four replayed incidents priced at the initial calibration (381/128) in
days-to-recoup: ~1 day for the May 2023 finality incidents, hours for the two
January 2024 client bugs, ~2.4 days for post-Fusaka. Meaningful, but arguably
light for the five worst correlated failures of the Merge era — the events
were all *short* (patches or flags landed within hours), and the mechanism
prices exposure, so brief events price low even at high multipliers. The
question: how much harder can the curve hit before the worst cases overreach?

Two honest levers, both swept over the real per-slot offline series
([`severity_sweep.py`](severity_sweep.py), results in
[`results_sweep/severity_sweep.json`](results_sweep/severity_sweep.json)):

- **Family A — raise the cap**, slope tied at `3·(cap−1)`: the whole curve
  scales together, saturation stays at one third, and every worst-case bound
  (bleed rate, bystander cost, griefing payoff) rises with it.
- **Family B — steepen the slope, keep cap 128**: the 5–20% band (single
  client / single operator, the deterrence target) prices like family A, but
  every tail-risk bound stays at the original level. The price: saturation
  falls below one third (a 17% and a 30% event price identically) and the
  slope becomes an arbitrary constant instead of an identity.

Mean days-to-recoup on the real events, per variant:

| variant | saturates | May 2023 | Besu | Nethermind | Fusaka | worst-case bleed |
|---|---|---|---|---|---|---|
| 381/128 (initial) | 33% | 0.97 d (40x) | 2.6 h | 11 h | 2.40 d (23x) | 0.40%/day |
| **A: 765/256 (adopted)** | 33% | 1.92 d (79x) | 4.3 h | 21 h | 4.73 d (45x) | 0.79%/day |
| A: 1533/512 | 33% | 3.83 d | 7.7 h | 1.71 d | 9.38 d (89x) | 1.59%/day |
| B: 762/128 | 16.7% | 1.02 d | 4.3 h | 21 h | 3.83 d (36x) | 0.40%/day |
| B: 1524/128 | 8.3% | 1.04 d | 7.7 h | 1.67 d | 4.25 d | 0.40%/day |

And the high-sigma worst cases, the "don't overdo it" check:

| scenario | 381/128 | **765/256** | 1533/512 |
|---|---|---|---|
| 10%/24h synthetic | ~2 wk rewards | ~3.7 wk | ~7.5 wk (0.5% principal) |
| 40%/72h finality loss, **total incl. unchanged leak** | 2.5% principal | 3.6% | 6.1% |
| — of which this mechanism / the pre-existing leak | 1.1% / 1.4% | 2.2% / 1.4% | 4.7% / 1.4% |
| innocent bystander, 1–2 epochs in a May-2023-style storm | 0.22 d ($2) | 0.44 d | 0.87 d |
| bystander down 6 h during a 40% crisis | ~11 d rewards | ~22 d | ~44 d |
| May 2023 network-wide extra burn | 2.9k ETH | 5.9k | 11.8k (1.25% of a year's issuance) |
| Fusaka cost per 1% of stake run | $373k | $729k | $1.44M |

The >33% rows are decomposed deliberately: the inactivity leak exists today
and this EIP does not touch it. Even at the adopted constants, over a third of
the three-day-finality-loss total is the leak — the outsized number above the
finality threshold is mostly the protocol's existing pricing, not this
mechanism's.

## The choice: 765/256

- **1533/512 overreaches.** A solo staker on the wrong majority client during
  a three-day finality loss approaches 6% of principal, and an innocent
  bystander offline six hours in a crisis pays six weeks of income. That
  profile loses the room.
- **Family B is surgical but lopsided.** Worst cases stay at initial levels
  and it directly answers the "aggressive penalties open discouragement
  attacks" objection (the damage-per-attacker-dollar bound never moves) — but
  it flattens exactly the severity-proportionality the backtest demonstrates
  (2.2x → 7.5x → 23x across event sizes), and it trades the
  saturation-at-one-third identity for a free parameter.
- **765/256 doubles the deterrent with every identity intact.** One severity
  knob, saturation at one third, cap-relative properties unchanged. Fusaka
  reprices from 2.4 to 4.7 days per validator (~$7.3M for a 10%-of-stake
  operator); a 10%/24h event costs just under a month of rewards; the
  three-day-finality-loss worst case lands at 3.6% of principal, well below
  the leak-dominated regime the protocol already accepts; and bystanders top
  out at half a day of income for storm-scale events.

Everything below the cap scales exactly ×2 from the initial calibration, so
the detailed backtest tables in `results*/` (computed at 381/128, kept as the
measured record alongside their attribution cuts) convert by doubling; the
adopted-constants replays are in `results_sweep/severity_sweep.json`.
