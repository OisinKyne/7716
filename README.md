# EIP-7716: anti-correlation attestation penalties — model, calibration & figures

Supporting materials for the 2026 revival of [EIP-7716](https://eips.ethereum.org/EIPS/eip-7716) (anti-correlation attestation penalties): an exact-integer simulation of the originally drafted mechanism, the quantitative case for restructuring it, the calibration of the revised mechanism, and the figure-generation code for the accompanying write-up.

## The proposal, in one block

```
offline           = balance in a slot's committees missing BOTH
                    timely source AND timely target      # the "offline indicator"
committee_balance = total_active_balance // 32
factor            = min(1 + PENALTY_SLOPE * max(0, offline − smoothed_offline_balance)
                          // committee_balance,
                        MAX_PENALTY_FACTOR)    # cap 128, slope = 3·(cap−1) = 381
smoothed_offline_balance += (offline − smoothed_offline_balance)
                          // OFFLINE_BALANCE_SMOOTHING_FACTOR    # 2**17, ~12.6d half-life
```

The factor scales only the timely-**target** penalty of validators that produced no timely attestation at all. Uncorrelated failures pay exactly today's penalties; the factor is never below 1; the cap binds at exactly one third of stake — where the inactivity leak takes over — by the slope identity, at any baseline participation rate.

![Onset penalty factor scales linearly with the size of the correlated failure, saturating at the finality threshold](figures/f3_onset_vs_size.png)

## Where the proposal lives

| Artifact | Link |
| --- | --- |
| EIP update PR (Stagnant → Draft, restructured mechanism) | [ethereum/EIPs#11962](https://github.com/ethereum/EIPs/pull/11962) |
| Executable consensus-specs feature (built on Heze) | [ethereum/consensus-specs#5452](https://github.com/ethereum/consensus-specs/pull/5452) |
| Analysis write-up (comment on the original thread) | [ethresear.ch/t/…/19116](https://ethresear.ch/t/supporting-decentralized-staking-through-more-anti-correlation-incentives/19116) — source in [`ethresearch-comment.md`](ethresearch-comment.md) |
| Hardfork tracking (PFI for Hegotá) | [forkcast.org/upgrade/hegota](https://forkcast.org/upgrade/hegota/#eip-7716) |
| EIP discussion thread | [ethereum-magicians.org/t/…/20137](https://ethereum-magicians.org/t/eip-7716-anti-correlation-attestation-penalties/20137) |

Prior work this builds on: Vitalik's [anti-correlation incentives analysis](https://ethresear.ch/t/supporting-decentralized-staking-through-more-anti-correlation-incentives/19116) and [concrete proposal](https://ethresear.ch/t/a-concrete-proposal-for-correlated-attester-penalties/19341), Toni's [backtest](https://ethresear.ch/t/analysis-on-correlated-attestation-penalties/19244), the [2024 explainer](https://ethresear.ch/t/diseconomies-of-scale-anti-correlation-penalties-eip-7716/20114), [FAQ](https://github.com/dapplion/anti-correlation-penalties-faq), and the [draft Lighthouse implementation](https://github.com/igorline/lighthouse/pull/1).

## Headline numbers

Per 32 eth validator, July 2026 parameters (~40.7M eth staked, eth ≈ $1,840, ~0.3% baseline offline rate — though the normalisation makes the results baseline-independent), cohort offline 24h:

| Event | Today | Revised | Payback |
| --- | --- | --- | --- |
| uncorrelated failure | $6.17 | $6.17 (1.0x) | 1.2 d |
| 10% correlated | $6.17 | $69 (11.3x) | ~2 wk |
| 20% correlated | $6.17 | $133 (21.5x) | ~3.7 wk |
| 40% down 3 days (finality lost) | $819 | $1,469 (1.8x) | ~9.5 mo ≈ 2.5% of principal |

Under the *originally drafted* mechanism every one of these events costs within a few percent of $6.17, at any cap — the update rule has a fixed excess-penalty budget, `Σ(factor−1) = PAF·Δmiss/32`, independent of `MAX_PENALTY_FACTOR` and outage duration. That invariant is why the mechanism was restructured rather than retuned; see the write-up for the full argument.

![What a validator caught in a 10% correlated outage loses: the drafted mechanism overlaps the status quo line, the revision is meaningful but flattens once the cohort recovers](figures/f4_cost_vs_rectification.png)

*The as-drafted mechanism (green) is indistinguishable from having no mechanism at all (grey, underneath it); the revision (blue) charges an amount operators will notice, front-loaded so that slow-recovering solo stakers aren't the ones who pay.*

## Files

| File | What it is |
| --- | --- |
| `eip7716_model.py` | Network anchors (stake, rewards, penalties) and an exact-integer simulation of the originally drafted `NET_EXCESS_PENALTIES` mechanism |
| `gen_figures.py` | The **final** revised mechanism (slope 381 / cap 128 / 2¹⁷ smoothing) plus the inactivity-leak model, and generation of all seven figures in `figures/` |
| `ethresearch-comment.md` | Source of the analysis write-up (image paths are local; swap for Discourse uploads) |
| `figures/` | The seven figures referenced by the write-up |
| `eip7716_variants.py` | *Design evolution:* cap/PAF sweeps proving the fixed-budget invariant, and an early slow-EMA-ratio design |
| `eip7716_frontloaded.py` | *Design evolution:* retuned-counter vs fast-EMA designs under heterogeneous recovery times, with the inactivity-leak model |
| `eip7716_aggressive.py` | *Design evolution:* EMA-relative excess-ratio calibration (superseded by the baseline-invariant absolute slope) |
| `eip7716_report.py` | *Design evolution:* early scenario tables |

The three *design evolution* scripts implement superseded parameterisations and are kept as the record of how the final design was reached (and why the alternatives — duration-punishing leaks, EMA-relative slopes, counter retuning, non-linear factors — were rejected). `gen_figures.py` is the source of truth for the proposed mechanism's behaviour.

## Reproduce

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python gen_figures.py     # regenerates figures/*.png
.venv/bin/python eip7716_model.py   # original-mechanism scenario tables
```

Network parameters are embedded in `eip7716_model.Network` (defaults are the July 2026 snapshot); change them there to rerun the calibration under different assumptions of stake, price, or baseline offline rate.
