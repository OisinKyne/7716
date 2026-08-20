# Window-length and skew sweep — real-event results

## 2023-05-11/12 mainnet finality incidents

Event epochs 200551–200760, tail to 201000. Peak excess offline **68.8%** of stake against a 0.49% baseline. Cohort recovery: 50% at 22.2 h, 90% at 22.5 h, 99% at 25.6 h from onset. 557,214 validators affected (72,425 with contiguous outages).

| variant | rise HL | fall HL | peak factor | mean days-to-recoup | vs status quo | tail share | quiet >1x | sustained 10%·7d | re-arm +3d | +7d | +14d |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `sym_2^14` | 1.6 d | 1.6 d | 128x | 23.7 h | 28.4x | 1.4% | 11.5% | 25.98 d | 1.00 | 1.00 | 1.00 |
| `sym_2^15` | 3.1 d | 3.1 d | 128x | 23.8 h | 28.5x | 1.6% | 11.6% | 39.29 d | 1.00 | 1.00 | 1.00 |
| `sym_2^16` | 6.3 d | 6.3 d | 128x | 23.8 h | 28.6x | 1.7% | 11.7% | 51.71 d | 1.00 | 1.00 | 1.00 |
| `sym_2^17` | 12.6 d | 12.6 d | 128x | 23.9 h | 28.6x | 1.8% | 11.7% | 60.52 d | 1.00 | 1.00 | 1.00 |
| `sym_2^18` | 25.2 d | 25.2 d | 128x | 23.9 h | 28.6x | 1.9% | 11.6% | 65.77 d | 1.00 | 1.00 | 1.00 |
| `rise_2^9_fall_2^17` | 0.1 d | 12.6 d | 128x | 21.5 h | 25.7x | 0.8% | 0.4% | 6.80 d | 1.00 | 1.00 | 1.00 |
| `rise_2^11_fall_2^17` | 0.2 d | 12.6 d | 128x | 23.0 h | 27.5x | 0.9% | 1.2% | 8.63 d | 1.00 | 1.00 | 1.00 |
| `rise_2^12_fall_2^17` | 0.4 d | 12.6 d | 128x | 23.3 h | 27.9x | 1.0% | 3.9% | 11.10 d | 1.00 | 1.00 | 1.00 |
| `rise_2^13_fall_2^17` | 0.8 d | 12.6 d | 128x | 23.5 h | 28.2x | 1.1% | 6.0% | 16.08 d | 1.00 | 1.00 | 1.00 |
| `rise_2^15_fall_2^17` | 3.1 d | 12.6 d | 128x | 23.8 h | 28.5x | 1.6% | 9.7% | 39.13 d | 1.00 | 1.00 | 1.00 |
| `fall_2^15_rise_2^17` | 12.6 d | 3.1 d | 128x | 23.9 h | 28.6x | 1.9% | 13.4% | 60.76 d | 1.00 | 1.00 | 1.00 |
| `fall_2^13_rise_2^17` | 12.6 d | 0.8 d | 128x | 23.9 h | 28.7x | 1.9% | 17.0% | 61.23 d | 1.00 | 1.00 | 1.00 |

### Cost by personal recovery hour (contiguous outages only)

Mean days-to-recoup per 32 ETH, bucketed by the hour (from onset) at which the validator's outage ended.

| recovered by | n | `status_quo` | `sym_2^14` | `sym_2^17` | `sym_2^18` | `rise_2^12_fall_2^17` | `rise_2^13_fall_2^17` |
|---|---|---|---|---|---|---|---|
| 0-2h | 9,975 | 0.1 h | 4.2 h | 4.2 h | 4.2 h | 4.2 h | 4.2 h |
| 2-4h | 390 | 0.1 h | 3.4 h | 3.4 h | 3.4 h | 3.4 h | 3.4 h |
| 4-6h | 202 | 3.3 h | 5.4 h | 6.1 h | 6.1 h | 4.8 h | 4.9 h |
| 6-8h | 50 | 0.2 h | 0.6 h | 0.6 h | 0.6 h | 0.5 h | 0.5 h |
| 8-12h | 224 | 0.1 h | 0.5 h | 0.5 h | 0.5 h | 0.4 h | 0.4 h |
| 12-18h | 261 | 0.2 h | 0.5 h | 0.5 h | 0.5 h | 0.4 h | 0.4 h |
| 18-24h | 59,476 | 0.2 h | 12.6 h | 12.6 h | 12.6 h | 12.6 h | 12.6 h |
| 24-36h | 977 | 1.7 h | 5.0 h | 5.4 h | 5.5 h | 4.5 h | 4.7 h |
| 36-48h | 657 | 4.1 h | 9.7 h | 10.4 h | 10.6 h | 8.9 h | 9.2 h |
| 48-72h | 213 | 1.41 d | 3.02 d | 3.24 d | 3.29 d | 2.83 d | 2.90 d |

## 2024-01-06 Besu mainnet halt

Event epochs 254470–254594, tail to 254850. Peak excess offline **3.6%** of stake against a 0.37% baseline. Cohort recovery: 50% at 13.4 h, 90% at 15.8 h, 99% at None h from onset. 266,282 validators affected (181,307 with contiguous outages).

| variant | rise HL | fall HL | peak factor | mean days-to-recoup | vs status quo | tail share | quiet >1x | sustained 10%·7d | re-arm +3d | +7d | +14d |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `sym_2^14` | 1.6 d | 1.6 d | 46x | 2.9 h | 2.1x | 29.7% | 5.7% | 33.30 d | 1.00 | 1.00 | 1.00 |
| `sym_2^15` | 3.1 d | 3.1 d | 46x | 3.0 h | 2.1x | 30.3% | 5.7% | 50.33 d | 1.00 | 1.00 | 1.00 |
| `sym_2^16` | 6.3 d | 6.3 d | 46x | 3.1 h | 2.1x | 31.1% | 5.7% | 66.23 d | 1.00 | 1.00 | 1.00 |
| `sym_2^17` | 12.6 d | 12.6 d | 46x | 3.1 h | 2.2x | 31.7% | 5.7% | 77.50 d | 1.00 | 1.00 | 1.00 |
| `sym_2^18` | 25.2 d | 25.2 d | 46x | 3.1 h | 2.2x | 32.0% | 5.7% | 84.23 d | 1.00 | 1.00 | 1.00 |
| `rise_2^9_fall_2^17` | 0.1 d | 12.6 d | 41x | 2.2 h | 1.6x | 36.0% | 1.0% | 8.76 d | 0.78 | 0.89 | 1.11 |
| `rise_2^11_fall_2^17` | 0.2 d | 12.6 d | 44x | 2.5 h | 1.7x | 33.5% | 2.3% | 11.12 d | 0.92 | 1.00 | 1.00 |
| `rise_2^12_fall_2^17` | 0.4 d | 12.6 d | 45x | 2.6 h | 1.8x | 32.2% | 3.1% | 14.30 d | 0.92 | 0.92 | 1.00 |
| `rise_2^13_fall_2^17` | 0.8 d | 12.6 d | 46x | 2.7 h | 1.9x | 31.0% | 3.9% | 20.70 d | 0.93 | 0.93 | 0.93 |
| `rise_2^15_fall_2^17` | 3.1 d | 12.6 d | 46x | 3.0 h | 2.1x | 30.3% | 5.2% | 50.20 d | 1.00 | 1.00 | 1.00 |
| `fall_2^15_rise_2^17` | 12.6 d | 3.1 d | 46x | 3.1 h | 2.2x | 32.0% | 6.4% | 77.70 d | 1.00 | 1.00 | 1.00 |
| `fall_2^13_rise_2^17` | 12.6 d | 0.8 d | 47x | 3.2 h | 2.3x | 32.7% | 8.5% | 78.10 d | 0.93 | 0.93 | 0.93 |

### Cost by personal recovery hour (contiguous outages only)

Mean days-to-recoup per 32 ETH, bucketed by the hour (from onset) at which the validator's outage ended.

| recovered by | n | `status_quo` | `sym_2^14` | `sym_2^17` | `sym_2^18` | `rise_2^12_fall_2^17` | `rise_2^13_fall_2^17` |
|---|---|---|---|---|---|---|---|
| 0-2h | 20,806 | 0.5 h | 2.0 h | 2.0 h | 2.0 h | 1.8 h | 1.9 h |
| 2-4h | 6,664 | 0.5 h | 1.4 h | 1.4 h | 1.4 h | 1.2 h | 1.3 h |
| 4-6h | 6,418 | 0.6 h | 1.3 h | 1.3 h | 1.3 h | 1.0 h | 1.2 h |
| 6-8h | 10,883 | 0.3 h | 0.6 h | 0.6 h | 0.6 h | 0.5 h | 0.5 h |
| 8-12h | 16,837 | 0.6 h | 1.2 h | 1.3 h | 1.3 h | 1.0 h | 1.1 h |
| 12-18h | 35,563 | 0.5 h | 3.1 h | 3.1 h | 3.2 h | 2.9 h | 3.0 h |
| 18-24h | 26,883 | 0.2 h | 1.8 h | 1.8 h | 1.8 h | 1.7 h | 1.7 h |
| 24-36h | 34,344 | 1.1 h | 1.7 h | 1.9 h | 1.9 h | 1.5 h | 1.6 h |
| 36-48h | 22,909 | 6.0 h | 7.9 h | 8.6 h | 8.7 h | 6.9 h | 7.3 h |

## 2024-01-21 Nethermind consensus bug

Event epochs 257907–257943, tail to 258200. Peak excess offline **8.4%** of stake against a 0.30% baseline. Cohort recovery: 50% at 2.0 h, 90% at 9.3 h, 99% at None h from onset. 241,815 validators affected (159,942 with contiguous outages).

| variant | rise HL | fall HL | peak factor | mean days-to-recoup | vs status quo | tail share | quiet >1x | sustained 10%·7d | re-arm +3d | +7d | +14d |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `sym_2^14` | 1.6 d | 1.6 d | 70x | 8.0 h | 3.8x | 7.2% | 5.6% | 33.83 d | 0.97 | 1.00 | 1.00 |
| `sym_2^15` | 3.1 d | 3.1 d | 71x | 8.3 h | 3.9x | 9.2% | 5.6% | 51.14 d | 0.97 | 0.97 | 1.00 |
| `sym_2^16` | 6.3 d | 6.3 d | 71x | 8.5 h | 4.0x | 10.6% | 5.6% | 67.29 d | 0.97 | 0.97 | 0.97 |
| `sym_2^17` | 12.6 d | 12.6 d | 71x | 8.6 h | 4.0x | 11.2% | 5.6% | 78.74 d | 0.97 | 0.97 | 0.97 |
| `sym_2^18` | 25.2 d | 25.2 d | 71x | 8.6 h | 4.1x | 11.7% | 5.6% | 85.57 d | 0.97 | 0.97 | 0.97 |
| `rise_2^9_fall_2^17` | 0.1 d | 12.6 d | 57x | 4.6 h | 2.2x | 8.6% | 1.0% | 8.94 d | 0.62 | 0.72 | 0.86 |
| `rise_2^11_fall_2^17` | 0.2 d | 12.6 d | 66x | 6.2 h | 2.9x | 6.3% | 2.2% | 11.34 d | 0.84 | 0.87 | 0.94 |
| `rise_2^12_fall_2^17` | 0.4 d | 12.6 d | 68x | 6.9 h | 3.2x | 6.0% | 3.2% | 14.58 d | 0.88 | 0.91 | 0.94 |
| `rise_2^13_fall_2^17` | 0.8 d | 12.6 d | 70x | 7.5 h | 3.5x | 5.9% | 4.4% | 21.09 d | 0.94 | 0.94 | 0.97 |
| `rise_2^15_fall_2^17` | 3.1 d | 12.6 d | 71x | 8.2 h | 3.9x | 8.9% | 5.3% | 51.04 d | 1.00 | 1.00 | 1.00 |
| `fall_2^15_rise_2^17` | 12.6 d | 3.1 d | 71x | 8.6 h | 4.1x | 11.4% | 5.8% | 78.89 d | 0.97 | 1.00 | 1.00 |
| `fall_2^13_rise_2^17` | 12.6 d | 0.8 d | 71x | 8.8 h | 4.1x | 12.0% | 6.5% | 79.19 d | 1.00 | 1.00 | 1.00 |

### Cost by personal recovery hour (contiguous outages only)

Mean days-to-recoup per 32 ETH, bucketed by the hour (from onset) at which the validator's outage ended.

| recovered by | n | `status_quo` | `sym_2^14` | `sym_2^17` | `sym_2^18` | `rise_2^12_fall_2^17` | `rise_2^13_fall_2^17` |
|---|---|---|---|---|---|---|---|
| 0-2h | 44,378 | 0.8 h | 7.7 h | 7.8 h | 7.8 h | 7.3 h | 7.5 h |
| 2-4h | 19,782 | 1.5 h | 11.3 h | 11.6 h | 11.6 h | 10.2 h | 10.9 h |
| 4-6h | 9,604 | 1.7 h | 8.7 h | 9.1 h | 9.2 h | 7.2 h | 8.1 h |
| 6-8h | 13,548 | 1.0 h | 4.0 h | 4.2 h | 4.2 h | 3.1 h | 3.6 h |
| 8-12h | 15,975 | 0.7 h | 2.6 h | 2.8 h | 2.9 h | 2.0 h | 2.3 h |
| 12-18h | 13,794 | 1.4 h | 3.7 h | 4.1 h | 4.2 h | 2.8 h | 3.2 h |
| 18-24h | 19,675 | 1.8 h | 3.9 h | 4.5 h | 4.6 h | 3.1 h | 3.4 h |
| 24-36h | 23,186 | 5.9 h | 11.1 h | 13.0 h | 13.2 h | 9.1 h | 9.9 h |

## 2025-12-04 post-Fusaka correlated outage

Event epochs 411439–411480, tail to 411700. Peak excess offline **23.5%** of stake against a 0.32% baseline. Cohort recovery: 50% at 2.8 h, 90% at 6.7 h, 99% at None h from onset. 351,275 validators affected (214,563 with contiguous outages).

| variant | rise HL | fall HL | peak factor | mean days-to-recoup | vs status quo | tail share | quiet >1x | sustained 10%·7d | re-arm +3d | +7d | +14d |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `sym_2^14` | 1.6 d | 1.6 d | 110x | 2.31 d | 12.8x | 1.8% | 2.1% | 39.42 d | 0.99 | 1.01 | 1.01 |
| `sym_2^15` | 3.1 d | 3.1 d | 111x | 2.40 d | 13.3x | 3.2% | 2.1% | 59.59 d | 0.98 | 0.99 | 1.00 |
| `sym_2^16` | 6.3 d | 6.3 d | 111x | 2.45 d | 13.6x | 4.2% | 2.1% | 78.40 d | 0.99 | 0.99 | 1.00 |
| `sym_2^17` | 12.6 d | 12.6 d | 112x | 2.48 d | 13.8x | 4.8% | 2.1% | 91.75 d | 0.99 | 0.99 | 0.99 |
| `sym_2^18` | 25.2 d | 25.2 d | 112x | 2.50 d | 13.9x | 5.1% | 2.1% | 99.72 d | 0.99 | 1.00 | 1.00 |
| `rise_2^9_fall_2^17` | 0.1 d | 12.6 d | 88x | 1.08 d | 6.0x | 1.9% | 0.3% | 10.46 d | 0.50 | 0.62 | 0.77 |
| `rise_2^11_fall_2^17` | 0.2 d | 12.6 d | 103x | 1.74 d | 9.7x | 1.2% | 0.5% | 13.28 d | 0.79 | 0.84 | 0.91 |
| `rise_2^12_fall_2^17` | 0.4 d | 12.6 d | 106x | 1.99 d | 11.1x | 1.1% | 0.6% | 17.05 d | 0.87 | 0.90 | 0.94 |
| `rise_2^13_fall_2^17` | 0.8 d | 12.6 d | 109x | 2.17 d | 12.1x | 1.2% | 0.8% | 24.63 d | 0.92 | 0.94 | 0.97 |
| `rise_2^15_fall_2^17` | 3.1 d | 12.6 d | 111x | 2.39 d | 13.3x | 3.1% | 1.5% | 59.51 d | 0.98 | 0.99 | 0.99 |
| `fall_2^15_rise_2^17` | 12.6 d | 3.1 d | 112x | 2.49 d | 13.8x | 4.8% | 2.5% | 91.88 d | 0.99 | 1.00 | 1.00 |
| `fall_2^13_rise_2^17` | 12.6 d | 0.8 d | 112x | 2.49 d | 13.9x | 4.9% | 4.1% | 92.16 d | 1.00 | 1.00 | 1.00 |

### Cost by personal recovery hour (contiguous outages only)

Mean days-to-recoup per 32 ETH, bucketed by the hour (from onset) at which the validator's outage ended.

| recovered by | n | `status_quo` | `sym_2^14` | `sym_2^17` | `sym_2^18` | `rise_2^12_fall_2^17` | `rise_2^13_fall_2^17` |
|---|---|---|---|---|---|---|---|
| 0-2h | 65,625 | 0.6 h | 16.1 h | 16.4 h | 16.4 h | 15.0 h | 15.7 h |
| 2-4h | 91,949 | 2.4 h | 2.44 d | 2.52 d | 2.52 d | 2.19 d | 2.34 d |
| 4-6h | 14,142 | 4.4 h | 3.00 d | 3.18 d | 3.19 d | 2.47 d | 2.79 d |
| 6-8h | 14,324 | 6.7 h | 3.71 d | 4.01 d | 4.03 d | 2.94 d | 3.39 d |
| 8-12h | 6,551 | 6.4 h | 2.55 d | 2.86 d | 2.89 d | 1.97 d | 2.28 d |
| 12-18h | 8,829 | 5.5 h | 1.44 d | 1.71 d | 1.74 d | 1.11 d | 1.28 d |
| 18-24h | 4,286 | 7.0 h | 1.39 d | 1.73 d | 1.76 d | 1.09 d | 1.24 d |
| 24-36h | 8,857 | 1.15 d | 4.42 d | 5.63 d | 5.77 d | 3.53 d | 3.96 d |
