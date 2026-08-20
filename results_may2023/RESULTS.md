# Results — 2023-05-11/12 mainnet finality incidents under EIP-7716

Event epochs **200551–200760** (210 epochs, 2023-05-11 20:06Z and 2023-05-12 17:20Z), mainnet.
Total active balance 18.13M ETH; `base_reward_per_increment` = 475 gwei; measured CL APR 3.90%.

Moving average seeded from epochs **200359–200550** (baseline): mean per-slot offline balance 2,799 ETH, = 0.495% of stake. `NET_EXCESS_PENALTIES` warmed on the same window to 1.

## 1. Penalty factors actually produced

| | revised (381 / 128) | as drafted (4096 / 4) |
|---|---|---|
| peak per-slot factor | **128x** | **4x** |
| mean over the 6720 event slots | 9.2x | 1.002x |
| slots pinned at the cap | 314 / 6720 | 1126 / 6720 |
| slots at factor 0 (discount) | 0 | 3506 / 6720 |
| mean factor *as experienced by an offline validator* | 100.6x | 1.254x |

Peak per-slot offline share was 100.0% of stake — below the one-third saturation point, so the revised cap never binds and the factor discriminates on event size rather than pinning.

## 2. Days-to-recoup, unattributed — event window only

554,865 validators were offline for at least one epoch; mean 8.6 offline epochs each. Every validator is normalised to a 32 ETH stake before averaging.

| Line | mean loss / 32 ETH | days-to-recoup (mean) | median | p95 | vs status quo |
|---|---|---|---|---|---|
| Status quo | 0.14 mETH | **35 min** | 28 min | 60 min | 1.00x |
| EIP-7716 as drafted (4096 / 4) | 0.16 mETH | **40 min** | 33 min | 1.1 h | 1.15x |
| EIP-7716 revised (381 / 128 / 2^17) | 5.41 mETH | **23.3 h** | 1.00 d | 1.73 d | 39.84x |

## 3. Days-to-recoup, unattributed — event plus recovery tail

557,214 validators were offline for at least one epoch; mean 11.2 offline epochs each. Every validator is normalised to a 32 ETH stake before averaging.

| Line | mean loss / 32 ETH | days-to-recoup (mean) | median | p95 | vs status quo |
|---|---|---|---|---|---|
| Status quo | 0.19 mETH | **50 min** | 31 min | 1.6 h | 1.00x |
| EIP-7716 as drafted (4096 / 4) | 0.22 mETH | **56 min** | 37 min | 1.7 h | 1.12x |
| EIP-7716 revised (381 / 128 / 2^17) | 5.56 mETH | **23.9 h** | 1.00 d | 1.79 d | 28.62x |

## 5. Network-wide accounting under today's rules (cross-check)

Not a 7716 quantity. This is what the network gave up, for comparison with the postmortem's headline. The dominant term is not the offline cohort's own loss: attestation rewards carry a `participating_increments / active_increments` factor, so every *online* validator's reward is quadratic in participation and falls too.

| Component | ETH |
|---|---|
| forgone attestation rewards (all validators, vs pre-Fusaka baseline) | 88.7 |
| excess attestation penalties | 41.9 |
| forgone proposer rewards, CL (206 excess missed slots) | 6.9 |
| forgone proposer rewards, EL/MEV | 6.3 |
| forgone sync-committee rewards | 2.3 |
| **total** | **146** |

Missed-slot rate 4.6% (308 of 6720 slots) against a 1.51% pre-Fusaka baseline.

## 6. Distributed-validator archetype — HYPOTHETICAL

This is a **construction, not an observation**. Nothing in the data identifies a distributed validator. It models a validator whose key is split across nodes running different clients, so a client-specific bug removes only part of the cluster; if the survivors still meet threshold it attests normally and pays nothing. `survival` is the fraction of the event during which threshold held.

| survival | epochs offline | days-to-recoup today | days-to-recoup revised |
|---|---|---|---|
| 0% | 210 | 20.1 h | 2.75 d |
| 50% | 105 | 10.1 h | 1.38 d |
| 100% | 0 | 0 min | 0 min |

