# Results — 2024-01-21 Nethermind consensus bug under EIP-7716

Event epochs **257907–257943** (37 epochs, 2024-01-21, bad block 19056922), mainnet.
Total active balance 28.98M ETH; `base_reward_per_increment` = 375 gwei; measured CL APR 3.08%.

Moving average seeded from epochs **257715–257906** (baseline): mean per-slot offline balance 2,710 ETH, = 0.299% of stake. `NET_EXCESS_PENALTIES` warmed on the same window to 3.

## 1. Penalty factors actually produced

| | revised (381 / 128) | as drafted (4096 / 4) |
|---|---|---|
| peak per-slot factor | **71x** | **4x** |
| mean over the 1184 event slots | 18.3x | 0.999x |
| slots pinned at the cap | 0 / 1184 | 6 / 1184 |
| slots at factor 0 (discount) | 0 | 42 / 1184 |
| mean factor *as experienced by an offline validator* | 23.1x | 1.026x |

Peak per-slot offline share was 18.8% of stake — below the one-third saturation point, so the revised cap never binds and the factor discriminates on event size rather than pinning.

## 2. Days-to-recoup, unattributed — event window only

132,823 validators were offline for at least one epoch; mean 12.6 offline epochs each. Every validator is normalised to a 32 ETH stake before averaging.

| Line | mean loss / 32 ETH | days-to-recoup (mean) | median | p95 | vs status quo |
|---|---|---|---|---|---|
| Status quo | 0.21 mETH | **1.5 h** | 56 min | 4.4 h | 1.00x |
| EIP-7716 as drafted (4096 / 4) | 0.21 mETH | **1.5 h** | 59 min | 4.4 h | 1.01x |
| EIP-7716 revised (381 / 128 / 2^17) | 1.58 mETH | **11.2 h** | 9.4 h | 1.11 d | 7.45x |

## 3. Days-to-recoup, unattributed — event plus recovery tail

241,815 validators were offline for at least one epoch; mean 17.5 offline epochs each. Every validator is normalised to a 32 ETH stake before averaging.

| Line | mean loss / 32 ETH | days-to-recoup (mean) | median | p95 | vs status quo |
|---|---|---|---|---|---|
| Status quo | 0.30 mETH | **2.1 h** | 15 min | 10.4 h | 1.00x |
| EIP-7716 as drafted (4096 / 4) | 0.31 mETH | **2.2 h** | 18 min | 10.3 h | 1.02x |
| EIP-7716 revised (381 / 128 / 2^17) | 1.21 mETH | **8.6 h** | 1.4 h | 1.51 d | 4.04x |

## 5. Network-wide accounting under today's rules (cross-check)

Not a 7716 quantity. This is what the network gave up, for comparison with the postmortem's headline. The dominant term is not the offline cohort's own loss: attestation rewards carry a `participating_increments / active_increments` factor, so every *online* validator's reward is quadratic in participation and falls too.

| Component | ETH |
|---|---|
| forgone attestation rewards (all validators, vs pre-Fusaka baseline) | 41.3 |
| excess attestation penalties | 12.2 |
| forgone proposer rewards, CL (82 excess missed slots) | 3.5 |
| forgone proposer rewards, EL/MEV | 2.5 |
| forgone sync-committee rewards | 0.6 |
| **total** | **60** |

Missed-slot rate 7.3% (87 of 1184 slots) against a 0.44% pre-Fusaka baseline.

## 6. Distributed-validator archetype — HYPOTHETICAL

This is a **construction, not an observation**. Nothing in the data identifies a distributed validator. It models a validator whose key is split across nodes running different clients, so a client-specific bug removes only part of the cluster; if the survivors still meet threshold it attests normally and pays nothing. `survival` is the fraction of the event during which threshold held.

| survival | epochs offline | days-to-recoup today | days-to-recoup revised |
|---|---|---|---|
| 0% | 37 | 4.6 h | 1.12 d |
| 50% | 18 | 2.3 h | 13.4 h |
| 100% | 0 | 0 min | 0 min |

