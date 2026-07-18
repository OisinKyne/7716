#!/usr/bin/env python3
"""Final report tables for EIP-7716 analysis (July 2026 parameters)."""
from eip7716_model import (Network, outage_cost, fmt_days, WEIGHT_DEN,
                           ATT_PENALTY_W, EPOCHS_PER_DAY)
from eip7716_variants import ema_alternative

net = Network()
BR = net.base_reward_gwei_per_32eth()
REW = net.att_reward_per_epoch_gwei()
PEN = net.att_penalty_per_epoch_gwei()
FULL = net.full_reward_per_epoch_gwei()

print("## Network anchors (July 2026)")
print(f"- {net.total_staked_eth/1e6:.1f}M ETH staked, ETH ${net.eth_price_usd:.0f}")
print(f"- base_reward per 32 ETH: {BR:.0f} gwei/epoch")
print(f"- ideal attestation reward: {REW:.0f} gwei/epoch; missed-att penalty (1x): {PEN:.0f} gwei/epoch")
print(f"- att-only CL APR: {net.cl_apr()*100:.2f}%; assumed full earnings {FULL:.0f} gwei/epoch "
      f"(~{FULL*EPOCHS_PER_DAY*365.25/32e9*100:.2f}% APR incl proposer/sync/EL)")
print(f"- per 32-ETH validator: full earnings ≈ {FULL*EPOCHS_PER_DAY/1e9:.6f} ETH/day "
      f"(${FULL*EPOCHS_PER_DAY/1e9*net.eth_price_usd:.2f}/day)")
print()

DUR = [(round(EPOCHS_PER_DAY/24), "1 hour"), (round(EPOCHS_PER_DAY), "1 day"),
       (round(7*EPOCHS_PER_DAY), "1 week"), (round(30.44*EPOCHS_PER_DAY), "1 month")]
SPIKES = [0.05, 0.10, 0.20, 0.40]

print("## Table 1: cost of a correlated outage per 32-ETH validator")
print("EIP-7716 as specced (PAF=4096, MAX=4), Lighthouse scope (source+target scaled)\n")
print("| Spike | Duration | Loss now (ETH / $) | Payback now | Loss 7716 (ETH / $) | Payback 7716 | Extra vs now | avg PF | slots at 4x |")
print("|---|---|---|---|---|---|---|---|---|")
for sp in SPIKES:
    for d, dl in DUR:
        r = outage_cost(net, sp, d)
        ln, l7 = r['loss_now_gwei']/1e9, r['loss_7716_gwei']/1e9
        print(f"| {sp:.0%} | {dl} | {ln:.5f} / ${ln*net.eth_price_usd:.2f} "
              f"| {fmt_days(r['payback_days_now'])} "
              f"| {l7:.5f} / ${l7*net.eth_price_usd:.2f} "
              f"| {fmt_days(r['payback_days_7716'])} "
              f"| +{(l7/ln-1)*100:.1f}% | {r['avg_pf']:.2f} | {r['slots_at_max']} |")
print()

print("## Table 1b: same, source-only scope (per EIP explainer post: 14/64 scaled)")
print("| Spike | Duration | Loss 7716 src-only (ETH) | Extra vs now |")
print("|---|---|---|---|")
for sp in [0.10, 0.40]:
    for d, dl in DUR[1:3]:
        r = outage_cost(net, sp, d, scaled_weight=14)
        ln, l7 = r['loss_now_gwei']/1e9, r['loss_7716_gwei']/1e9
        print(f"| {sp:.0%} | {dl} | {l7:.5f} | {(l7/ln-1)*100:+.2f}% |")
print()

print("## Table 2: required sustained penalty factor to hit deterrence targets")
print("(scope source+target; factor needed so total loss = target payback)\n")
print("| Spike duration | Target payback | Required avg factor |")
print("|---|---|---|")
scaled_pen = BR * ATT_PENALTY_W / WEIGHT_DEN
for d_days, dl in [(1, "1 day"), (7, "1 week")]:
    d_ep = d_days * EPOCHS_PER_DAY
    for tgt_days, tl in [(14, "2 weeks"), (30.44, "1 month"), (182.6, "6 months")]:
        F = (tgt_days * EPOCHS_PER_DAY * FULL / d_ep - REW) / scaled_pen
        print(f"| {dl} outage | {tl} of rewards | {F:.0f}x |")
print()

print("## Table 3: slow-EMA redesign (factor = miss_rate / 14-day-EMA, capped)")
print("| Spike | Duration | Cap | avg PF | Loss (ETH / $) | Payback |")
print("|---|---|---|---|---|---|")
for sp in [0.10, 0.20, 0.40]:
    for d_ep, dl in [(225, "1 day"), (1575, "1 week")]:
        for cap in [4, 16, 64]:
            avg_pf, payback, loss = ema_alternative(sp, d_ep, cap, 14)
            print(f"| {sp:.0%} | {dl} | {cap} | {avg_pf:.1f} "
                  f"| {loss/1e9:.4f} / ${loss/1e9*net.eth_price_usd:.2f} | {fmt_days(payback)} |")
