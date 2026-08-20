# Redistribute or burn?

The original EIP-7716 draft was issuance-neutral by construction: the
`NET_EXCESS_PENALTIES` counter enforces that the long-run sum of penalties is
unchanged — extra penalties during a spike are repaid as factor-zero slots
afterwards. Toni stated both halves explicitly in the
[spec post](https://ethresear.ch/t/diseconomies-of-scale-anti-correlation-penalties-eip-7716/20114):
"the penalty factor…equals 1 on average *(notably, this is important to not
touch the issuance policy)*" and "the sum of penalties doesn't change with
this EIP—only the distribution does."

The revised curve is not neutral — the factor never goes below 1, so
correlated events strictly increase total penalties. Should it redistribute
instead of burn? **No.** Three reasons, in order of weight.

## 1. The original's neutrality is the no-op, not a lost feature

Issuance neutrality *within the penalty budget* is algebraically the
fixed-budget invariant, and the [backtest](BACKTEST.md) measures what that
buys on real incidents: 1.16x on May 2023, 1.04x on Besu, 1.01x on Nethermind
and post-Fusaka — inside the status quo's error bar on all four, including the
mechanism's own motivating events. Whatever a correlated cohort pays extra
must come from somewhere; if the mechanism gives it back, it isn't a
deterrent. A longer-horizon budget (repay via sub-1x factors over weeks) fails
differently: the December 2025 event's ~4,600 ETH of extra penalties (at the
adopted 765/256 constants) against a ~260 ETH/day baseline penalty flow means
zeroing *all* attestation penalties for over two weeks — a free-miss window,
advertised on-chain, opening exactly when the network is recovering, and paid
to whoever misses next rather than to the cohort that was charged.

## 2. Redistribution to online validators funds discouragement attacks

Paying the collected scaled penalties to correct attesters is the design the
discouragement-attack literature warns about
([Buterin 2018](https://eips.ethereum.org/assets/eip-2982/ef-Discouragement-Attacks.pdf)):
griefing becomes profitable when victims' losses recycle into survivors'
income; burning removes the recovery channel entirely. The pots are not
subtle: December 2025 would have created a **~4,600 ETH pool paid to online
validators** — a 30% staker that *caused* a competitor outage (infrastructure
DoS, eclipse, or the proposer-censorship path
[Elowsson flagged](https://ethresear.ch/t/practical-endgame-on-issuance-policy/20747))
would collect ~1,400 ETH of it. Under burn, zero. The revision as drafted
actually *improves* on today here: an attacker who takes itself offline to
hurt others pays the scaled factor on its own stake while online victims lose
only participation-scaled rewards — self-inflicted discouragement attacks get
strictly less profitable. Redistribution inverts that. It also makes rewards a
function of realized same-epoch penalties: a second accumulation pass over the
validator set, new rounding rules, and client reward caches becoming
state-dependent.

## 3. The burn is quantitatively not issuance policy

Network-wide extra penalties vs the status quo, replayed on the real events at
the adopted 765/256 constants (event + recovery tail):

| Event | extra burn | % of annual issuance (~940k ETH) |
|---|---|---|
| May 2023 finality incidents (both) | 6,005 ETH | 0.64% |
| Besu halt, 2024-01-06 | 136 ETH | 0.014% |
| Nethermind bug, 2024-01-21 | 454 ETH | 0.048% |
| Prysm post-Fusaka, 2025-12-04 | 4,625 ETH | 0.49% |

Expected value at historical event rates: ~0.1–0.3% of issuance per year,
conditional entirely on correlated failures happening. In steady state the
mechanism burns nothing — at the mainnet noise floor the factor is measurably
1 on every slot. EIP-1559 burns amounts of this order in days of ordinary fee
activity, and mass-slashing events (which nobody frames as issuance policy)
burn comparable amounts.

Precedent runs one way: every penalty in the current spec burns — attestation
penalties, sync-committee penalties, the inactivity leak, slashing including
its correlation term. The protocol's single redistribution channel (the
whistleblower/proposer reward on slashing) exists to incentivize *reporting*,
is capped at 1/4096 of the slashed balance, and still leaves net issuance
negative. A burn accrues to no one, so there is no beneficiary to lobby for
more of it and no pool to fight over.
