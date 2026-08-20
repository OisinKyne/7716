# Results — 2025-12-04 post-Fusaka correlated outage under EIP-7716

Event epochs **411439–411480** (42 epochs, 2025-12-04 02:49:59Z → 07:18:47Z), mainnet.
Total active balance 35.63M ETH; `base_reward_per_increment` = 339 gwei; measured CL APR 2.79%.

Moving average seeded from epochs **411200–411391** (pre-Fusaka): mean per-slot offline balance 3,519 ETH, = 0.316% of stake. `NET_EXCESS_PENALTIES` warmed on the same window to 1.

## 1. Penalty factors actually produced

| | revised (381 / 128) | as drafted (4096 / 4) |
|---|---|---|
| peak per-slot factor | **112x** | **3x** |
| mean over the 1344 event slots | 56.7x | 1.000x |
| slots pinned at the cap | 0 / 1344 | 0 / 1344 |
| slots at factor 0 (discount) | 0 | 24 / 1344 |
| mean factor *as experienced by an offline validator* | 68.9x | 1.012x |

Peak per-slot offline share was 29.8% of stake — below the one-third saturation point, so the revised cap never binds and the factor discriminates on event size rather than pinning.

## 2. Days-to-recoup, unattributed — event window only

328,835 validators were offline for at least one epoch; mean 20.1 offline epochs each. Every validator is normalised to a 32 ETH stake before averaging.

| Line | mean loss / 32 ETH | days-to-recoup (mean) | median | p95 | vs status quo |
|---|---|---|---|---|---|
| Status quo | 0.28 mETH | **2.5 h** | 2.7 h | 5.4 h | 1.00x |
| EIP-7716 as drafted (4096 / 4) | 0.28 mETH | **2.5 h** | 2.7 h | 5.3 h | 1.01x |
| EIP-7716 revised (381 / 128 / 2^17) | 6.30 mETH | **2.40 d** | 2.91 d | 4.12 d | 22.74x |

## 3. Days-to-recoup, unattributed — event plus recovery tail

351,275 validators were offline for at least one epoch; mean 32.5 offline epochs each. Every validator is normalised to a 32 ETH stake before averaging.

| Line | mean loss / 32 ETH | days-to-recoup (mean) | median | p95 | vs status quo |
|---|---|---|---|---|---|
| Status quo | 0.47 mETH | **4.3 h** | 2.6 h | 1.04 d | 1.00x |
| EIP-7716 as drafted (4096 / 4) | 0.48 mETH | **4.3 h** | 2.6 h | 1.04 d | 1.01x |
| EIP-7716 revised (381 / 128 / 2^17) | 6.53 mETH | **2.48 d** | 2.82 d | 5.79 d | 13.82x |

## 4. Attributed cut — behavioural, with `unknown` carried explicitly

No client split is claimed. There is no on-chain fingerprint for either consensus or execution clients, and the ethPandaOps entity/client tables are Clickhouse-only. What follows is what the p2p record *can* establish.

Weighted by **offline validator-epochs** — what the offline stake was doing at any given moment:

| signature | % of offline stake | validator-epochs | distinct validators |
|---|---|---|---|
| `silent` | 76.8% | 5,102,216 | 283,830 |
| `desynced` | 15.2% | 988,848 | 199,294 |
| `uncollected` | 4.7% | 307,233 | 170,255 |
| `wrong-target` | 2.1% | 134,348 | 93,468 |
| `chronic` | 1.2% | 87,907 | 2,190 |

The distinct-validator counts sum well past the 328,835 validators actually affected, because nodes flapped between states — restarting, resyncing, falling behind again. Weighting by validator instead of by validator-epoch therefore gives a different picture, and both are reported.

Weighted by **validator**, each assigned the signature it showed in most of its offline epochs. `purity` is how dominant that mode was; low purity means the node flapped.

| Bucket | what it means | validators | % of offline stake | purity | days-to-recoup: today | drafted | revised |
|---|---|---|---|---|---|---|---|
| `silent` | nothing on the p2p network either | 273,453 | 82.1% | 0.84 | 2.9 h | 2.9 h | **2.73 d** |
| `desynced` | signing on a stale justified checkpoint | 10,635 | 4.4% | 0.61 | 2.8 h | 2.8 h | **2.28 d** |
| `wrong-target` | correct source, non-canonical target | 3,859 | 1.2% | 0.99 | 8 min | 9 min | **3.1 h** |
| `uncollected` | valid attestation gossiped, never included | 38,698 | 11.7% | 0.96 | 14 min | 15 min | **5.1 h** |
| `chronic` | already offline before Fusaka | 2,190 | 0.6% | 1.00 | 5.2 h | 5.2 h | **3.97 d** |

### 4a. Client attribution

| Client | share of the offline cohort |
|---|---|
| `unknown` | **100%** |

That row is the finding, not a placeholder. Consensus-client attribution requires proposal-fingerprinting (blockprint), which is not in the public Xatu Parquet mirror; execution-client attribution has no on-chain signal at all. Any "Nethermind was N% of the validator set" number is a self-reported survey, not a measurement, and multiplying the results above by one would give the survey's error bars the appearance of chain data. The behavioural buckets are the strongest cut the public record supports: `desynced` is the signature the Nethermind → Nimbus fake-invalid path would leave, and `silent` is what attestation resource exhaustion looks like from outside — but both are also what an ordinary hard-down node of any client looks like.

## 5. Network-wide accounting under today's rules (cross-check)

Not a 7716 quantity. This is what the network gave up, for comparison with the postmortem's headline. The dominant term is not the offline cohort's own loss: attestation rewards carry a `participating_increments / active_increments` factor, so every *online* validator's reward is quadratic in participation and falls too.

| Component | ETH |
|---|---|
| forgone attestation rewards (all validators, vs pre-Fusaka baseline) | 140.3 |
| excess attestation penalties | 47.7 |
| forgone proposer rewards, CL (235 excess missed slots) | 11.1 |
| forgone proposer rewards, EL/MEV | 7.2 |
| forgone sync-committee rewards | 2.4 |
| **total** | **209** |

Missed-slot rate 18.5% (248 of 1344 slots) against a 0.96% pre-Fusaka baseline.

## 6. Distributed-validator archetype — HYPOTHETICAL

This is a **construction, not an observation**. Nothing in the data identifies a distributed validator. It models a validator whose key is split across nodes running different clients, so a client-specific bug removes only part of the cluster; if the survivors still meet threshold it attests normally and pays nothing. `survival` is the fraction of the event during which threshold held.

| survival | epochs offline | days-to-recoup today | days-to-recoup revised |
|---|---|---|---|
| 0% | 42 | 6.1 h | 4.18 d |
| 50% | 21 | 3.1 h | 2.09 d |
| 100% | 0 | 0 min | 0 min |

