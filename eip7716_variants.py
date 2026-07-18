#!/usr/bin/env python3
"""
Parameter sweeps + alternative designs for EIP-7716.

Key analytic invariant of the EIP's update rule:
  NEP_{t+1} = max(1, NEP_t + pf_t) - 1   =>   sum_t (pf_t - 1) = NEP_end - NEP_start
So for a step change in miss rate, the TOTAL excess penalty budget
(sum of factor-above-1 over all slots) is fixed at
  dNEP = PENALTY_ADJUSTMENT_FACTOR * (m1 - m0) / 32
regardless of MAX_PENALTY_FACTOR. The cap only spreads that budget over
more slots. Raising the cap does NOT materially raise total penalties.
"""
import math
from eip7716_model import (Network, simulate, outage_cost, fmt_days,
                           SLOTS_PER_EPOCH, EPOCHS_PER_DAY,
                           ATT_REWARD_W, ATT_PENALTY_W, WEIGHT_DEN)

net = Network()


def scenario_row(spike, dur_epochs, paf, maxf):
    return outage_cost(net, spike, dur_epochs, paf=paf, maxf=maxf)


def ema_alternative(spike, dur_epochs, maxf, halflife_days, m0=None):
    """
    Alternative design: penalty_factor = clamp(m_t / m_ref, 0..maxf), where
    m_ref is a slow EMA of the per-slot miss rate with given halflife.
    Sustained deviations stay punished until the EMA catches up.
    Returns avg factor over outage + payback days.
    """
    m0 = m0 if m0 is not None else net.baseline_miss
    m1 = m0 + spike
    alpha = 1 - 0.5 ** (1 / (halflife_days * EPOCHS_PER_DAY * SLOTS_PER_EPOCH))
    mref = m0
    dur_slots = int(round(dur_epochs * SLOTS_PER_EPOCH))
    pfs = []
    for _ in range(dur_slots):
        pf = min(m1 / max(mref, 1e-9), maxf)
        pfs.append(pf)
        mref = mref + alpha * (m1 - mref)
    avg_pf = sum(pfs) / len(pfs)
    rew = net.att_reward_per_epoch_gwei()
    pen = net.att_penalty_per_epoch_gwei()
    loss = dur_epochs * (rew + avg_pf * pen)
    payback = loss / net.full_reward_per_epoch_gwei() / EPOCHS_PER_DAY
    return avg_pf, payback, loss


if __name__ == "__main__":
    print("=== Sweep: does raising MAX_PENALTY_FACTOR or PAF help? ===")
    print("Scenario: 10% of stake offline for 1 day (225 epochs)\n")
    hdr = f"{'PAF':>9} {'MAXF':>5} {'avgPF':>7} {'payback':>9} {'vs now':>7}"
    print(hdr); print("-" * len(hdr))
    base = scenario_row(0.10, 225, 4096, 4)
    for paf in [4096, 65536, 2**20, 2**23]:
        for maxf in [4, 16, 64]:
            r = scenario_row(0.10, 225, paf, maxf)
            print(f"{paf:>9} {maxf:>5} {r['avg_pf']:>7.2f} "
                  f"{fmt_days(r['payback_days_7716']):>9} "
                  f"{r['payback_days_7716']/base['payback_days_now']:>6.2f}x")
    print()

    print("=== Recovery discount window (factor==0 after outage ends) ===")
    for paf in [4096, 2**20, 2**23]:
        r = scenario_row(0.10, 225, paf, 4)
        print(f"PAF={paf:>8}: zero-penalty slots after recovery: "
              f"{r['zero_pf_slots_after']} ({r['zero_pf_slots_after']/SLOTS_PER_EPOCH/EPOCHS_PER_DAY:.2f} days)")
    print()

    print("=== Alternative: slow-EMA reference (factor = miss / EMA(miss)) ===")
    print("Scenario grid, EMA halflife = 14 days, cap varies\n")
    hdr = f"{'spike':>6} {'duration':>8} {'cap':>4} {'avgPF':>6} {'payback':>9}"
    print(hdr); print("-" * len(hdr))
    for spike in [0.10, 0.40]:
        for dur, dl in [(225, "1 day"), (1575, "1 week")]:
            for cap in [4, 16, 64]:
                avg_pf, payback, _ = ema_alternative(spike, dur, cap, 14)
                print(f"{spike:>6.0%} {dl:>8} {cap:>4} {avg_pf:>6.1f} {fmt_days(payback):>9}")
        print()
