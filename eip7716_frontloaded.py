#!/usr/bin/env python3
"""
Front-loaded correlation penalty analysis.

Scenario: at t=0 a correlated event knocks `spike` of total stake offline.
The aggregate cohort stays down for AGG_HOURS (24h), then recovers en masse.
Individual operators within the cohort rectify after R hours (R may exceed
24h for stragglers). The chain's penalty-factor timeline is driven by the
aggregate; each operator pays for its own down epochs at the prevailing
factor, plus spec inactivity-leak penalties when participation < 2/3.

Designs compared:
  NOW      factor == 1 (status quo)
  EIP      EIP-7716 as specced: PAF=4096, cap=4
  RETUNED  same update rule, PAF=2^23, cap=16, applied factor floored at 1
           (floor removes the post-recovery free-miss discount window)
  EMA      factor = clamp(miss / EMA_tau(miss), 0, 16), tau = 6h halflife
           (no floor: stragglers get the natural post-event discount)

Inactivity leak (Altair/Bellatrix spec, per epoch):
  down:            score += 4        else: score -= min(1, score)
  if not in leak:  score -= min(16, score)
  if down:         penalty += bal * score // (4 * 2**24)
  leak active while aggregate participation < 2/3.
  During leak, NO attestation rewards are paid to anyone (participants
  earn 0); missers still pay attestation penalties.
"""
from eip7716_model import (Network, simulate, fmt_days, SLOTS_PER_EPOCH,
                           EPOCHS_PER_DAY, WEIGHT_DEN, ATT_PENALTY_W)

net = Network()
BR = net.base_reward_gwei_per_32eth()
REW = net.att_reward_per_epoch_gwei()
SCALED_PEN = BR * ATT_PENALTY_W / WEIGHT_DEN     # 40/64, Lighthouse scope
FULL = net.full_reward_per_epoch_gwei()
M0 = net.baseline_miss
AGG_HOURS = 24
EP_H = EPOCHS_PER_DAY / 24                       # 9.375 epochs/hour
POST_EPOCHS = 4 * 225                            # simulate 4 days past recovery

CAP = 16
PAF_RETUNED = 2**23
TAU_H = 6


def slot_schedule(spike):
    # first slot is baseline: simulate() warms NEP up at schedule[0]; callers
    # must drop the first result so epoch 0 is the true outage onset
    agg_slots = int(AGG_HOURS * EP_H * SLOTS_PER_EPOCH)
    return ([M0] + [M0 + spike] * agg_slots
            + [M0] * (POST_EPOCHS * SLOTS_PER_EPOCH)), agg_slots


def epoch_mean(factors_per_slot):
    out = []
    for i in range(0, len(factors_per_slot) - SLOTS_PER_EPOCH + 1, SLOTS_PER_EPOCH):
        out.append(sum(factors_per_slot[i:i + SLOTS_PER_EPOCH]) / SLOTS_PER_EPOCH)
    return out


def factors_eip(spike, paf, cap, floor1=False):
    sched, _ = slot_schedule(spike)
    res = simulate(sched, paf=paf, maxf=cap)[1:]   # drop baseline warmup slot
    pfs = [max(1, pf) if floor1 else pf for pf, _ in res]
    return epoch_mean(pfs)


def factors_ema(spike, tau_h, cap):
    sched, _ = slot_schedule(spike)
    alpha = 1 - 0.5 ** (1 / (tau_h * EP_H * SLOTS_PER_EPOCH))
    mref = M0
    pfs = []
    for m in sched:
        pfs.append(min(m / max(mref, 1e-9), cap))
        mref += alpha * (m - mref)
    return epoch_mean(pfs[1:])                     # drop baseline warmup slot


def leak_cost(spike, r_epochs):
    """Inactivity-leak penalties (gwei) for a validator down r_epochs,
    with leak active for the aggregate outage window (spike >= 1/3)."""
    if spike < 1 / 3:
        return 0.0
    leak_epochs = int(AGG_HOURS * EP_H)
    score, total = 0, 0.0
    for e in range(int(r_epochs) + 600):
        down = e < r_epochs
        in_leak = e < leak_epochs
        if down:
            score += 4
        else:
            score -= min(1, score)
        if not in_leak:
            score -= min(16, score)
        if down and score > 0:
            total += 32e9 * score / (4 * 2**24)
        if score == 0 and not down:
            break
    return total


def cost(spike, r_hours, factors_by_epoch):
    """Total loss (gwei) for a validator down r_hours."""
    r_ep = int(round(r_hours * EP_H))
    att = 0.0
    for e in range(r_ep):
        f = factors_by_epoch[e] if e < len(factors_by_epoch) else 1.0
        att += REW + f * SCALED_PEN
    return att + leak_cost(spike, r_ep)


def payback(loss_gwei):
    return loss_gwei / FULL / EPOCHS_PER_DAY


if __name__ == "__main__":
    print(f"Anchors: reward {REW:.0f} gwei/ep, 1x penalty {SCALED_PEN:.0f} gwei/ep, "
          f"full earnings {FULL:.0f} gwei/ep (${FULL/1e9*net.eth_price_usd*EPOCHS_PER_DAY:.2f}/day)")
    print(f"Designs: RETUNED = EIP rule, PAF=2^23, cap {CAP}, floor 1; "
          f"EMA = miss/EMA(6h halflife), cap {CAP}")
    print(f"Aggregate outage: full spike for {AGG_HOURS}h, then mass recovery.\n")

    for spike in [0.10, 0.20, 0.40]:
        f_eip = factors_eip(spike, 4096, 4)
        f_ret = factors_eip(spike, PAF_RETUNED, CAP, floor1=True)
        f_ema = factors_ema(spike, TAU_H, CAP)

        # onset shape diagnostics
        def shape(f):
            hrs = [f[0], f[int(1*EP_H)], f[int(6*EP_H)], f[int(12*EP_H)], f[int(23*EP_H)]]
            return " / ".join(f"{x:.1f}" for x in hrs)
        print(f"### Spike {spike:.0%}  (factor at epoch 0 / 1h / 6h / 12h / 23h)")
        print(f"    EIP as-specced: {shape(f_eip)}")
        print(f"    RETUNED:        {shape(f_ret)}")
        print(f"    EMA 6h:         {shape(f_ema)}")
        leak_note = "  [inactivity leak ACTIVE 24h]" if spike >= 1/3 else ""
        print(f"| Rectified in | Loss now | Payback now | RETUNED | Payback | EMA | Payback |{leak_note}")
        print("|---|---|---|---|---|---|---|")
        for r_h, rl in [(1, "1 h"), (6, "6 h"), (24, "24 h"), (72, "72 h")]:
            l_now = cost(spike, r_h, [1.0] * 10000)
            l_ret = cost(spike, r_h, f_ret)
            l_ema = cost(spike, r_h, f_ema)
            print(f"| {rl} | ${l_now/1e9*net.eth_price_usd:.2f} | {fmt_days(payback(l_now))} "
                  f"| ${l_ret/1e9*net.eth_price_usd:.2f} ({l_ret/l_now:.1f}x) | {fmt_days(payback(l_ret))} "
                  f"| ${l_ema/1e9*net.eth_price_usd:.2f} ({l_ema/l_now:.1f}x) | {fmt_days(payback(l_ema))} |")
        print()

    # marginal cost of the straggler tail (hours 24-72) vs first hours
    print("### Marginal cost per additional hour down (10% spike, RETUNED / EMA)")
    f_ret = factors_eip(0.10, PAF_RETUNED, CAP, floor1=True)
    f_ema = factors_ema(0.10, TAU_H, CAP)
    for a, b in [(0, 1), (5, 6), (23, 24), (47, 48)]:
        mr = cost(0.10, b, f_ret) - cost(0.10, a, f_ret)
        me = cost(0.10, b, f_ema) - cost(0.10, a, f_ema)
        mn = cost(0.10, b, [1.0]*10000) - cost(0.10, a, [1.0]*10000)
        print(f"  hour {a:>2}->{b:<2}: now ${mn/1e9*net.eth_price_usd:.3f}  "
              f"RETUNED ${mr/1e9*net.eth_price_usd:.3f}  EMA ${me/1e9*net.eth_price_usd:.3f}")
