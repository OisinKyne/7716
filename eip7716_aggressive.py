#!/usr/bin/env python3
"""
Aggressive calibration: "excess-ratio" design.

  per slot, per flag:
    ratio  = miss_balance_fraction / EMA_slow          (slow EMA, ~14d halflife)
    factor = min(1 + K * max(0, ratio - 1), MAX_FACTOR)
    EMA_slow += (miss - EMA_slow) >> EMA_SHIFT         (integer shift in spec)

Constants under test: K = 4, MAX_FACTOR = 256, EMA halflife 14 days.
Targets: finality-losing outage (>=33%) -> 1-3% of principal incl. leak;
mild (5-10%) -> weeks-to-months of rewards. Front-loading preserved:
factor decays as EMA_slow absorbs the event; marginal late hours cheap-ish.

Baseline behavior: at steady state miss == EMA -> ratio 1 -> factor exactly 1
(no noise; strictly >= 1 so no discount windows to reason about).
"""
from eip7716_model import Network, EPOCHS_PER_DAY, ATT_PENALTY_W, WEIGHT_DEN
from eip7716_frontloaded import EP_H, fmt_days
import math

net = Network()
BR = net.base_reward_gwei_per_32eth()
REW = net.att_reward_per_epoch_gwei()
PEN = BR * ATT_PENALTY_W / WEIGHT_DEN          # 40/64 scope
FULL = net.full_reward_per_epoch_gwei()
M0 = net.baseline_miss
USD = net.eth_price_usd
K, CAP, HL_DAYS = 4, 256, 14
ALPHA = 1 - 0.5 ** (1 / (HL_DAYS * EPOCHS_PER_DAY * 32))
PRINCIPAL = 32e9


def factor_series(spike, agg_hours):
    """Per-epoch mean factor; aggregate down agg_hours then recovers."""
    n_slots = int((agg_hours * EP_H + 10 * EPOCHS_PER_DAY) * 32)
    down_slots = int(agg_hours * EP_H) * 32
    ema, pfs = M0, []
    for s in range(n_slots):
        m = M0 + spike if s < down_slots else M0
        ratio = m / ema
        pfs.append(min(1 + K * max(0.0, ratio - 1), CAP))
        ema += ALPHA * (m - ema)
    return [sum(pfs[i:i+32]) / 32 for i in range(0, len(pfs) - 31, 32)]


def leak_cost(spike, r_epochs, leak_epochs):
    if spike < 1 / 3:
        return 0.0
    score, total = 0, 0.0
    for e in range(int(r_epochs) + 2000):
        down, in_leak = e < r_epochs, e < leak_epochs
        score = score + 4 if down else score - min(1, score)
        if not in_leak:
            score -= min(16, score)
        if down and score > 0:
            total += PRINCIPAL * score / (4 * 2**24)
        if score == 0 and not down:
            break
    return total


def cost(spike, r_h, agg_h):
    f = factor_series(spike, agg_h)
    r_ep = int(round(r_h * EP_H))
    att = sum(REW + (f[e] if e < len(f) else 1.0) * PEN for e in range(r_ep))
    lk = leak_cost(spike, r_ep, int(agg_h * EP_H))
    return att, lk


if __name__ == "__main__":
    print(f"EXCESS-RATIO aggressive: K={K}, cap={CAP}, EMA halflife {HL_DAYS}d, "
          f"scope 40/64 (source+target)")
    print(f"onset factor by spike: " + ", ".join(
        f"{s:.0%}->{min(1 + K*((M0+s)/M0 - 1), CAP):.0f}x" for s in [.01, .05, .10, .20, .40]))
    print()
    hdr = (f"{'spike':>6} {'agg down':>9} {'rect':>5} {'7716 att':>10} {'leak':>9} "
           f"{'total':>10} {'% principal':>11} {'payback':>9} {'vs now':>7}")
    print(hdr); print("-" * len(hdr))
    scenarios = [
        (0.01, 24, [6, 24]),
        (0.05, 24, [6, 24, 72]),
        (0.10, 24, [6, 24, 72]),
        (0.20, 24, [6, 24, 72]),
        (0.40, 24, [1, 6, 24, 72]),
        (0.40, 72, [72]),          # finality-losing worst case: everyone down 3d
    ]
    for spike, agg_h, rects in scenarios:
        for r_h in rects:
            att, lk = cost(spike, r_h, agg_h)
            tot = att + lk
            now = int(round(r_h * EP_H)) * (REW + PEN) + lk * 0  # now: 1x att only
            now_lk = leak_cost(spike, int(r_h * EP_H), int(agg_h * EP_H))
            now_tot = now + now_lk
            pb = tot / FULL / EPOCHS_PER_DAY
            print(f"{spike:>6.0%} {agg_h:>7}h {r_h:>4}h "
                  f"${att/1e9*USD:>9.2f} ${lk/1e9*USD:>8.2f} ${tot/1e9*USD:>9.2f} "
                  f"{tot/PRINCIPAL*100:>10.3f}% {fmt_days(pb):>9} {tot/now_tot:>6.1f}x")
        print()

    # marginal hours: is front-loading preserved at 10%?
    f = factor_series(0.10, 24)
    print("marginal cost per hour, 10% spike (aggressive):")
    for a in [0, 5, 23, 47]:
        c1, _ = cost(0.10, a + 1, 24); c0, _ = cost(0.10, a, 24)
        print(f"  hour {a:>2}->{a+1:<3}: ${ (c1-c0)/1e9*USD:7.2f}  (now: $0.25)")
    # bystander: uncorrelated solo down 6h during a 40% crisis
    att, _ = cost(0.40, 6, 24)
    print(f"\nbystander cost (solo, 6h down during 40% crisis): ${att/1e9*USD:.2f} "
          f"(= {fmt_days(att/FULL/EPOCHS_PER_DAY)} of rewards)")
    # worst-case flow ceiling
    wc = (REW + CAP * PEN) * EPOCHS_PER_DAY
    print(f"hard ceiling at cap {CAP}: {wc/1e9:.3f} ETH/day = "
          f"{wc/PRINCIPAL*100:.2f}% of principal per day")
    # re-arm: onset factor of a 2nd 10% event N days after a 24h 10% event
    print("\nre-arm after a 24h 10% event (onset factor of an identical 2nd event):")
    for gap_d in [3, 7, 14, 28]:
        n_slots = int((24 * EP_H + gap_d * EPOCHS_PER_DAY) * 32)
        ema = M0
        for s in range(n_slots):
            m = M0 + 0.10 if s < int(24 * EP_H) * 32 else M0
            ema += ALPHA * (m - ema)
        f2 = min(1 + K * max(0.0, (M0 + 0.10) / ema - 1), CAP)
        print(f"  +{gap_d:>2}d: {f2:5.0f}x  (fresh: {1 + K*((M0+0.10)/M0-1):.0f}x)")
