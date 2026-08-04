# Results — 2024-01-06 Besu mainnet halt under EIP-7716

Event epochs **254470–254594** (125 epochs, 2024-01-06 12:08Z → 2024-01-07 01:21Z), mainnet.
Total active balance 28.92M ETH; `base_reward_per_increment` = 376 gwei; measured CL APR 3.09%.

Moving average seeded from epochs **254278–254469** (baseline): mean per-slot offline balance 3,302 ETH, = 0.365% of stake. `NET_EXCESS_PENALTIES` warmed on the same window to 2.

## 1. Penalty factors actually produced

| | revised (381 / 128) | as drafted (4096 / 4) |
|---|---|---|
| peak per-slot factor | **46x** | **4x** |
| mean over the 4000 event slots | 3.8x | 1.000x |
| slots pinned at the cap | 0 / 4000 | 145 / 4000 |
| slots at factor 0 (discount) | 0 | 589 / 4000 |
| mean factor *as experienced by an offline validator* | 5.1x | 1.094x |

Peak per-slot offline share was 12.4% of stake — below the one-third saturation point, so the revised cap never binds and the factor discriminates on event size rather than pinning.

## 2. Days-to-recoup, unattributed — event window only

134,502 validators were offline for at least one epoch; mean 10.5 offline epochs each. Every validator is normalised to a 32 ETH stake before averaging.

| Line | mean loss / 32 ETH | days-to-recoup (mean) | median | p95 | vs status quo |
|---|---|---|---|---|---|
| Status quo | 0.18 mETH | **1.3 h** | 7 min | 14.1 h | 1.00x |
| EIP-7716 as drafted (4096 / 4) | 0.19 mETH | **1.3 h** | 14 min | 14.0 h | 1.04x |
| EIP-7716 revised (381 / 128 / 2^17) | 0.40 mETH | **2.8 h** | 36 min | 1.07 d | 2.16x |

## 3. Days-to-recoup, unattributed — event plus recovery tail

266,282 validators were offline for at least one epoch; mean 11.8 offline epochs each. Every validator is normalised to a 32 ETH stake before averaging.

| Line | mean loss / 32 ETH | days-to-recoup (mean) | median | p95 | vs status quo |
|---|---|---|---|---|---|
| Status quo | 0.21 mETH | **1.4 h** | 7 min | 2.9 h | 1.00x |
| EIP-7716 as drafted (4096 / 4) | 0.22 mETH | **1.5 h** | 16 min | 3.0 h | 1.05x |
| EIP-7716 revised (381 / 128 / 2^17) | 0.45 mETH | **3.1 h** | 40 min | 7.1 h | 2.17x |

## 4. Attributed cut — behavioural, with `unknown` carried explicitly

No client split is claimed. There is no on-chain fingerprint for either consensus or execution clients, and the ethPandaOps entity/client tables are Clickhouse-only. What follows is what the p2p record *can* establish.

Weighted by **offline validator-epochs** — what the offline stake was doing at any given moment:

| signature | % of offline stake | validator-epochs | distinct validators |
|---|---|---|---|
| `silent` | 74.0% | 1,048,382 | 55,030 |
| `chronic` | 15.2% | 216,648 | 1,844 |
| `uncollected` | 7.6% | 107,476 | 80,917 |
| `desynced` | 1.6% | 22,936 | 21,761 |
| `wrong-target` | 1.6% | 22,732 | 21,537 |

The distinct-validator counts sum well past the 134,502 validators actually affected, because nodes flapped between states — restarting, resyncing, falling behind again. Weighting by validator instead of by validator-epoch therefore gives a different picture, and both are reported.

Weighted by **validator**, each assigned the signature it showed in most of its offline epochs. `purity` is how dominant that mode was; low purity means the node flapped.

| Bucket | what it means | validators | % of offline stake | purity | days-to-recoup: today | drafted | revised |
|---|---|---|---|---|---|---|---|
| `silent` | nothing on the p2p network either | 51,856 | 38.6% | 0.89 | 2.5 h | 2.6 h | **5.2 h** |
| `desynced` | signing on a stale justified checkpoint | 2,033 | 1.5% | 0.60 | 15 min | 16 min | **55 min** |
| `wrong-target` | correct source, non-canonical target | 15,020 | 11.2% | 0.99 | 8 min | 13 min | **50 min** |
| `uncollected` | valid attestation gossiped, never included | 63,749 | 47.4% | 0.96 | 11 min | 15 min | **35 min** |
| `chronic` | already offline before Fusaka | 1,844 | 1.4% | 1.00 | 14.2 h | 14.2 h | **1.07 d** |

### 4a. Client attribution

| Client | share of the offline cohort |
|---|---|
| `unknown` | **100%** |

That row is the finding, not a placeholder. Consensus-client attribution requires proposal-fingerprinting (blockprint), which is not in the public Xatu Parquet mirror; execution-client attribution has no on-chain signal at all. Any "Nethermind was N% of the validator set" number is a self-reported survey, not a measurement, and multiplying the results above by one would give the survey's error bars the appearance of chain data. The behavioural buckets are the strongest cut the public record supports: `desynced` is the signature the Nethermind → Nimbus fake-invalid path would leave, and `silent` is what attestation resource exhaustion looks like from outside — but both are also what an ordinary hard-down node of any client looks like.

## 5. Network-wide accounting under today's rules (cross-check)

Not a 7716 quantity. This is what the network gave up, for comparison with the postmortem's headline. The dominant term is not the offline cohort's own loss: attestation rewards carry a `participating_increments / active_increments` factor, so every *online* validator's reward is quadratic in participation and falls too.

| Component | ETH |
|---|---|
| forgone attestation rewards (all validators, vs pre-Fusaka baseline) | 32.3 |
| excess attestation penalties | 7.9 |
| forgone proposer rewards, CL (67 excess missed slots) | 2.9 |
| forgone proposer rewards, EL/MEV | 2.1 |
| forgone sync-committee rewards | 0.5 |
| **total** | **46** |

Missed-slot rate 2.9% (114 of 4000 slots) against a 1.17% pre-Fusaka baseline.

## 6. Distributed-validator archetype — HYPOTHETICAL

This is a **construction, not an observation**. Nothing in the data identifies a distributed validator. It models a validator whose key is split across nodes running different clients, so a client-specific bug removes only part of the cluster; if the survivors still meet threshold it attests normally and pays nothing. `survival` is the fraction of the event during which threshold held.

| survival | epochs offline | days-to-recoup today | days-to-recoup revised |
|---|---|---|---|
| 0% | 125 | 15.4 h | 1.14 d |
| 50% | 62 | 7.7 h | 13.7 h |
| 100% | 0 | 0 min | 0 min |

