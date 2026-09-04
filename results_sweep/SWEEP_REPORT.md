# Window-length and skew sweep — real-event results

## 2023-05-11/12 mainnet finality incidents

Event epochs 200551–200760, tail to 201000. Peak excess offline **68.8%** of stake against a 0.49% baseline. Cohort recovery: 50% at 22.2 h, 90% at 22.5 h, 99% at 25.6 h from onset. 557,214 validators affected (72,425 with contiguous outages).

| variant | rise HL | fall HL | peak factor | mean days-to-recoup | vs status quo | tail share | quiet >1x | sustained 10%·7d | re-arm +3d | +7d | +14d |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `sym_2^14` | 1.6 d | 1.6 d | 256x | 1.95 d | 56.1x | 1.3% | 16.6% | 46.70 d | 1.00 | 1.00 | 1.00 |
| `sym_2^15` | 3.1 d | 3.1 d | 256x | 1.96 d | 56.3x | 1.5% | 16.6% | 73.43 d | 1.00 | 1.00 | 1.00 |
| `sym_2^16` | 6.3 d | 6.3 d | 256x | 1.96 d | 56.4x | 1.6% | 16.6% | 98.37 d | 1.00 | 1.00 | 1.00 |
| `sym_2^17` | 12.6 d | 12.6 d | 256x | 1.96 d | 56.5x | 1.7% | 16.6% | 116.04 d | 1.00 | 1.00 | 1.00 |
| `sym_2^18` | 25.2 d | 25.2 d | 256x | 1.97 d | 56.6x | 1.8% | 16.6% | 126.64 d | 1.00 | 1.00 | 1.00 |
| `rise_2^9_fall_2^17` | 0.1 d | 12.6 d | 256x | 1.76 d | 50.7x | 0.7% | 0.4% | 7.35 d | 1.00 | 1.00 | 1.00 |
| `rise_2^11_fall_2^17` | 0.2 d | 12.6 d | 256x | 1.89 d | 54.3x | 0.8% | 1.7% | 11.14 d | 1.00 | 1.00 | 1.00 |
| `rise_2^12_fall_2^17` | 0.4 d | 12.6 d | 256x | 1.91 d | 55.1x | 0.8% | 5.4% | 16.28 d | 1.00 | 1.00 | 1.00 |
| `rise_2^13_fall_2^17` | 0.8 d | 12.6 d | 256x | 1.93 d | 55.6x | 1.0% | 8.1% | 26.62 d | 1.00 | 1.00 | 1.00 |
| `rise_2^15_fall_2^17` | 3.1 d | 12.6 d | 256x | 1.95 d | 56.2x | 1.4% | 14.3% | 73.10 d | 1.00 | 1.00 | 1.00 |
| `fall_2^15_rise_2^17` | 12.6 d | 3.1 d | 256x | 1.97 d | 56.6x | 1.8% | 18.2% | 116.51 d | 1.00 | 1.00 | 1.00 |
| `fall_2^13_rise_2^17` | 12.6 d | 0.8 d | 256x | 1.97 d | 56.7x | 1.9% | 21.6% | 117.46 d | 1.00 | 1.00 | 1.00 |

### Cost by recovery hour — validators down from the original onset

Mean days-to-recoup per 32 ETH, bucketed by the hour (from onset) at which the validator's outage ended. Only contiguous outages that began at event onset are included; validators that went offline later (second waves, restart flapping) are excluded here for clarity — their downtime landed after the factor collapsed and is priced near today's rates. The final column is the ratio of the scaled cost to today's cost for the same bucket: it *falls* with recovery time because the penalty is front-loaded, so being down 4x longer costs far less than 4x more relative to a fast responder.

| recovered by | n | `status_quo` | `sym_2^14` | `sym_2^17` | `sym_2^18` | `rise_2^12_fall_2^17` | `rise_2^13_fall_2^17` | `sym_2^17` vs today |
|---|---|---|---|---|---|---|---|---|
| 0-2h | 9,930 | 0.1 h | 8.3 h | 8.3 h | 8.3 h | 8.3 h | 8.3 h | **98x** |
| 2-4h | 4 | 2.7 h | 23.8 h | 1.05 d | 1.05 d | 21.2 h | 22.1 h | **9x** |
| 4-6h | 159 | 4.1 h | 9.5 h | 11.4 h | 11.6 h | 7.7 h | 8.1 h | **3x** |
| 6-8h | 1 | 6.0 h | 1.26 d | 1.34 d | 1.35 d | 1.14 d | 1.18 d | **5x** |
| 12-18h | 1 | 13.2 h | 1.48 d | 1.63 d | 1.64 d | 1.31 d | 1.35 d | **3x** |
| 18-24h | 26 | 18.2 h | 3.63 d | 3.81 d | 3.83 d | 3.43 d | 3.49 d | **5x** |
| 24-36h | 27 | 1.03 d | 4.78 d | 5.23 d | 5.30 d | 4.36 d | 4.50 d | **5x** |
| 36-48h | 68 | 1.50 d | 5.44 d | 6.03 d | 6.17 d | 4.96 d | 5.12 d | **4x** |
| 48-72h | 160 | 1.69 d | 5.60 d | 6.20 d | 6.36 d | 5.12 d | 5.27 d | **4x** |

## 2024-01-06 Besu mainnet halt

Event epochs 254470–254594, tail to 254850. Peak excess offline **3.6%** of stake against a 0.37% baseline. Cohort recovery: 50% at 13.4 h, 90% at 15.8 h, 99% at None h from onset. 266,282 validators affected (181,307 with contiguous outages).

| variant | rise HL | fall HL | peak factor | mean days-to-recoup | vs status quo | tail share | quiet >1x | sustained 10%·7d | re-arm +3d | +7d | +14d |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `sym_2^14` | 1.6 d | 1.6 d | 92x | 4.6 h | 3.2x | 27.8% | 10.3% | 59.86 d | 1.00 | 1.00 | 1.00 |
| `sym_2^15` | 3.1 d | 3.1 d | 92x | 4.8 h | 3.3x | 29.0% | 10.4% | 94.05 d | 1.00 | 1.00 | 1.00 |
| `sym_2^16` | 6.3 d | 6.3 d | 92x | 4.9 h | 3.4x | 30.1% | 10.4% | 125.99 d | 1.00 | 1.00 | 1.00 |
| `sym_2^17` | 12.6 d | 12.6 d | 92x | 5.0 h | 3.5x | 30.8% | 10.4% | 148.60 d | 1.00 | 1.00 | 1.00 |
| `sym_2^18` | 25.2 d | 25.2 d | 92x | 5.0 h | 3.5x | 31.3% | 10.4% | 162.18 d | 1.00 | 1.00 | 1.00 |
| `rise_2^9_fall_2^17` | 0.1 d | 12.6 d | 81x | 3.1 h | 2.1x | 33.3% | 1.2% | 9.52 d | 0.76 | 0.94 | 1.18 |
| `rise_2^11_fall_2^17` | 0.2 d | 12.6 d | 88x | 3.6 h | 2.5x | 30.9% | 2.8% | 14.41 d | 0.88 | 0.96 | 1.00 |
| `rise_2^12_fall_2^17` | 0.4 d | 12.6 d | 90x | 3.8 h | 2.7x | 29.5% | 3.9% | 21.02 d | 0.92 | 0.92 | 1.00 |
| `rise_2^13_fall_2^17` | 0.8 d | 12.6 d | 91x | 4.1 h | 2.9x | 28.2% | 5.3% | 34.30 d | 0.93 | 0.96 | 1.00 |
| `rise_2^15_fall_2^17` | 3.1 d | 12.6 d | 92x | 4.7 h | 3.3x | 28.8% | 9.0% | 93.78 d | 0.96 | 0.96 | 1.00 |
| `fall_2^15_rise_2^17` | 12.6 d | 3.1 d | 93x | 5.1 h | 3.6x | 31.3% | 11.8% | 148.98 d | 0.97 | 0.97 | 0.97 |
| `fall_2^13_rise_2^17` | 12.6 d | 0.8 d | 93x | 5.3 h | 3.7x | 32.0% | 16.2% | 149.79 d | 1.00 | 1.00 | 0.97 |

### Cost by recovery hour — validators down from the original onset

Mean days-to-recoup per 32 ETH, bucketed by the hour (from onset) at which the validator's outage ended. Only contiguous outages that began at event onset are included; validators that went offline later (second waves, restart flapping) are excluded here for clarity — their downtime landed after the factor collapsed and is priced near today's rates. The final column is the ratio of the scaled cost to today's cost for the same bucket: it *falls* with recovery time because the penalty is front-loaded, so being down 4x longer costs far less than 4x more relative to a fast responder.

| recovered by | n | `status_quo` | `sym_2^14` | `sym_2^17` | `sym_2^18` | `rise_2^12_fall_2^17` | `rise_2^13_fall_2^17` | `sym_2^17` vs today |
|---|---|---|---|---|---|---|---|---|
| 0-2h | 16,471 | 0.6 h | 4.1 h | 4.1 h | 4.1 h | 3.6 h | 3.8 h | **6x** |
| 2-4h | 684 | 3.5 h | 13.9 h | 14.2 h | 14.2 h | 10.7 h | 12.3 h | **4x** |
| 4-6h | 510 | 5.4 h | 18.8 h | 19.5 h | 19.6 h | 13.8 h | 16.3 h | **4x** |
| 6-8h | 204 | 7.5 h | 23.5 h | 1.03 d | 1.03 d | 16.4 h | 19.9 h | **3x** |
| 8-12h | 619 | 11.4 h | 1.32 d | 1.41 d | 1.42 d | 21.3 h | 1.08 d | **3x** |
| 12-18h | 837 | 16.2 h | 1.66 d | 1.82 d | 1.83 d | 1.12 d | 1.34 d | **3x** |
| 18-24h | 130 | 23.7 h | 2.09 d | 2.37 d | 2.39 d | 1.46 d | 1.69 d | **2x** |
| 24-36h | 880 | 1.40 d | 2.63 d | 3.07 d | 3.10 d | 1.92 d | 2.17 d | **2x** |
| 36-48h | 2,873 | 1.90 d | 3.20 d | 3.74 d | 3.80 d | 2.46 d | 2.71 d | **2x** |

## 2024-01-21 Nethermind consensus bug

Event epochs 257907–257943, tail to 258200. Peak excess offline **8.4%** of stake against a 0.30% baseline. Cohort recovery: 50% at 2.0 h, 90% at 9.3 h, 99% at None h from onset. 241,815 validators affected (159,942 with contiguous outages).

| variant | rise HL | fall HL | peak factor | mean days-to-recoup | vs status quo | tail share | quiet >1x | sustained 10%·7d | re-arm +3d | +7d | +14d |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `sym_2^14` | 1.6 d | 1.6 d | 141x | 14.2 h | 6.7x | 6.1% | 8.4% | 60.81 d | 0.98 | 1.00 | 1.00 |
| `sym_2^15` | 3.1 d | 3.1 d | 142x | 14.8 h | 7.0x | 8.4% | 8.4% | 95.56 d | 0.98 | 0.98 | 1.00 |
| `sym_2^16` | 6.3 d | 6.3 d | 142x | 15.2 h | 7.2x | 9.8% | 8.3% | 128.00 d | 0.98 | 0.98 | 1.00 |
| `sym_2^17` | 12.6 d | 12.6 d | 142x | 15.4 h | 7.3x | 10.6% | 8.4% | 150.98 d | 0.98 | 0.98 | 1.00 |
| `sym_2^18` | 25.2 d | 25.2 d | 142x | 15.5 h | 7.3x | 11.1% | 8.4% | 164.77 d | 1.00 | 1.00 | 1.00 |
| `rise_2^9_fall_2^17` | 0.1 d | 12.6 d | 113x | 7.2 h | 3.4x | 4.9% | 1.2% | 9.75 d | 0.60 | 0.71 | 0.84 |
| `rise_2^11_fall_2^17` | 0.2 d | 12.6 d | 132x | 10.5 h | 4.9x | 3.8% | 3.0% | 14.74 d | 0.82 | 0.87 | 0.92 |
| `rise_2^12_fall_2^17` | 0.4 d | 12.6 d | 137x | 11.9 h | 5.6x | 3.8% | 4.8% | 21.47 d | 0.89 | 0.92 | 0.95 |
| `rise_2^13_fall_2^17` | 0.8 d | 12.6 d | 139x | 13.0 h | 6.1x | 4.1% | 5.8% | 34.97 d | 0.92 | 0.94 | 0.97 |
| `rise_2^15_fall_2^17` | 3.1 d | 12.6 d | 141x | 14.7 h | 6.9x | 8.1% | 7.6% | 95.36 d | 0.97 | 0.97 | 0.98 |
| `fall_2^15_rise_2^17` | 12.6 d | 3.1 d | 142x | 15.5 h | 7.3x | 10.9% | 9.6% | 151.26 d | 1.00 | 1.00 | 1.00 |
| `fall_2^13_rise_2^17` | 12.6 d | 0.8 d | 142x | 15.7 h | 7.4x | 11.3% | 12.7% | 151.85 d | 1.00 | 1.00 | 1.00 |

### Cost by recovery hour — validators down from the original onset

Mean days-to-recoup per 32 ETH, bucketed by the hour (from onset) at which the validator's outage ended. Only contiguous outages that began at event onset are included; validators that went offline later (second waves, restart flapping) are excluded here for clarity — their downtime landed after the factor collapsed and is priced near today's rates. The final column is the ratio of the scaled cost to today's cost for the same bucket: it *falls* with recovery time because the penalty is front-loaded, so being down 4x longer costs far less than 4x more relative to a fast responder.

| recovered by | n | `status_quo` | `sym_2^14` | `sym_2^17` | `sym_2^18` | `rise_2^12_fall_2^17` | `rise_2^13_fall_2^17` | `sym_2^17` vs today |
|---|---|---|---|---|---|---|---|---|
| 0-2h | 33,648 | 1.0 h | 18.4 h | 18.6 h | 18.6 h | 17.3 h | 18.0 h | **18x** |
| 2-4h | 10,362 | 2.8 h | 1.64 d | 1.68 d | 1.68 d | 1.47 d | 1.57 d | **15x** |
| 4-6h | 2,870 | 5.4 h | 2.17 d | 2.27 d | 2.28 d | 1.77 d | 2.00 d | **10x** |
| 6-8h | 1,473 | 7.8 h | 2.50 d | 2.67 d | 2.68 d | 1.90 d | 2.24 d | **8x** |
| 8-12h | 844 | 10.8 h | 2.79 d | 3.05 d | 3.07 d | 2.04 d | 2.43 d | **7x** |
| 12-18h | 993 | 16.5 h | 3.19 d | 3.65 d | 3.69 d | 2.29 d | 2.69 d | **5x** |
| 18-24h | 1,247 | 1.04 d | 3.66 d | 4.42 d | 4.48 d | 2.65 d | 3.07 d | **4x** |
| 24-36h | 3,788 | 1.45 d | 4.14 d | 5.16 d | 5.26 d | 3.08 d | 3.51 d | **4x** |

## 2025-12-04 post-Fusaka correlated outage

Event epochs 411439–411480, tail to 411700. Peak excess offline **23.5%** of stake against a 0.32% baseline. Cohort recovery: 50% at 2.8 h, 90% at 6.7 h, 99% at None h from onset. 351,275 validators affected (214,563 with contiguous outages).

| variant | rise HL | fall HL | peak factor | mean days-to-recoup | vs status quo | tail share | quiet >1x | sustained 10%·7d | re-arm +3d | +7d | +14d |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `sym_2^14` | 1.6 d | 1.6 d | 221x | 4.47 d | 24.9x | 1.5% | 10.0% | 70.86 d | 0.99 | 1.01 | 1.01 |
| `sym_2^15` | 3.1 d | 3.1 d | 222x | 4.66 d | 25.9x | 3.0% | 10.0% | 111.35 d | 0.99 | 1.00 | 1.01 |
| `sym_2^16` | 6.3 d | 6.3 d | 223x | 4.77 d | 26.5x | 4.0% | 10.0% | 149.15 d | 0.98 | 0.99 | 0.99 |
| `sym_2^17` | 12.6 d | 12.6 d | 224x | 4.83 d | 26.9x | 4.6% | 10.1% | 175.93 d | 0.99 | 0.99 | 0.99 |
| `sym_2^18` | 25.2 d | 25.2 d | 224x | 4.86 d | 27.1x | 4.9% | 10.1% | 192.00 d | 0.99 | 0.99 | 0.99 |
| `rise_2^9_fall_2^17` | 0.1 d | 12.6 d | 176x | 2.00 d | 11.1x | 1.0% | 0.4% | 11.44 d | 0.51 | 0.62 | 0.77 |
| `rise_2^11_fall_2^17` | 0.2 d | 12.6 d | 205x | 3.33 d | 18.6x | 0.6% | 1.0% | 17.29 d | 0.78 | 0.83 | 0.90 |
| `rise_2^12_fall_2^17` | 0.4 d | 12.6 d | 213x | 3.83 d | 21.3x | 0.6% | 2.7% | 25.13 d | 0.87 | 0.90 | 0.94 |
| `rise_2^13_fall_2^17` | 0.8 d | 12.6 d | 218x | 4.20 d | 23.4x | 0.7% | 4.8% | 40.86 d | 0.92 | 0.94 | 0.97 |
| `rise_2^15_fall_2^17` | 3.1 d | 12.6 d | 222x | 4.65 d | 25.9x | 2.9% | 8.6% | 111.19 d | 0.97 | 0.98 | 0.99 |
| `fall_2^15_rise_2^17` | 12.6 d | 3.1 d | 224x | 4.84 d | 26.9x | 4.7% | 11.4% | 176.16 d | 0.99 | 1.00 | 1.00 |
| `fall_2^13_rise_2^17` | 12.6 d | 0.8 d | 224x | 4.85 d | 27.0x | 4.8% | 15.2% | 176.71 d | 1.00 | 1.00 | 1.00 |

### Cost by recovery hour — validators down from the original onset

Mean days-to-recoup per 32 ETH, bucketed by the hour (from onset) at which the validator's outage ended. Only contiguous outages that began at event onset are included; validators that went offline later (second waves, restart flapping) are excluded here for clarity — their downtime landed after the factor collapsed and is priced near today's rates. The final column is the ratio of the scaled cost to today's cost for the same bucket: it *falls* with recovery time because the penalty is front-loaded, so being down 4x longer costs far less than 4x more relative to a fast responder.

| recovered by | n | `status_quo` | `sym_2^14` | `sym_2^17` | `sym_2^18` | `rise_2^12_fall_2^17` | `rise_2^13_fall_2^17` | `sym_2^17` vs today |
|---|---|---|---|---|---|---|---|---|
| 0-2h | 51,680 | 0.7 h | 1.54 d | 1.57 d | 1.57 d | 1.44 d | 1.50 d | **57x** |
| 2-4h | 72,938 | 3.0 h | 6.02 d | 6.21 d | 6.23 d | 5.39 d | 5.78 d | **49x** |
| 4-6h | 11,063 | 5.5 h | 7.47 d | 7.94 d | 7.97 d | 6.14 d | 6.96 d | **34x** |
| 6-8h | 12,902 | 7.4 h | 8.01 d | 8.67 d | 8.72 d | 6.27 d | 7.29 d | **28x** |
| 8-12h | 3,809 | 10.9 h | 8.37 d | 9.43 d | 9.51 d | 6.37 d | 7.44 d | **21x** |
| 12-18h | 2,622 | 17.6 h | 8.98 d | 10.78 d | 10.92 d | 6.76 d | 7.86 d | **15x** |
| 18-24h | 1,141 | 1.06 d | 9.47 d | 12.02 d | 12.25 d | 7.14 d | 8.26 d | **11x** |
| 24-36h | 6,911 | 1.46 d | 9.96 d | 13.15 d | 13.48 d | 7.60 d | 8.73 d | **9x** |
