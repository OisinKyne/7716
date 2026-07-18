#!/usr/bin/env python3
"""
EIP-7716 anti-correlation penalty model.

Exact integer arithmetic per the EIP spec:

    penalty_factor = min(
        (non_attesting_balance * PENALTY_ADJUSTMENT_FACTOR)
            // (NET_EXCESS_PENALTIES * total_active_balance + 1),
        MAX_PENALTY_FACTOR,
    )
    NET_EXCESS_PENALTIES = max(1, NET_EXCESS_PENALTIES + penalty_factor) - 1

Computed once per slot; non_attesting_balance = balance of the slot's
committee (~1/32 of total) that failed to attest (per dapplion/Vitalik's
original proposal).

Reward/penalty context (Altair..Electra, unchanged):
  base_reward_per_increment = EBI * 64 // isqrt(total_active_balance_gwei)
  attestation reward weights: source 14 + target 26 + head 14 = 54/64
  missed-attestation penalty: (14+26)/64 = 40/64 of base_reward
  EIP-7716 scales the *penalty* by penalty_factor.
"""

import math
from dataclasses import dataclass

SLOTS_PER_EPOCH = 32
SECONDS_PER_SLOT = 12
EPOCHS_PER_DAY = 24 * 3600 / (SLOTS_PER_EPOCH * SECONDS_PER_SLOT)  # 225
EPOCHS_PER_YEAR = 365.25 * EPOCHS_PER_DAY

PAF_DEFAULT = 4096
MAXF_DEFAULT = 4

WEIGHT_DEN = 64
ATT_REWARD_W = 14 + 26 + 14   # 54: what you earn per epoch when attesting well
ATT_PENALTY_W = 14 + 26       # 40: what you lose per epoch when missing (pre-scaling)


@dataclass
class Network:
    # July 2026 snapshot: ~40.7M ETH staked, ETH ~$1,840, CL APR ~2.64%,
    # total APR incl EL tips/MEV ~3.2%  (=> EL bonus ~0.21 of CL)
    total_staked_eth: float = 40_700_000
    eth_price_usd: float = 1840.0
    baseline_miss: float = 0.003          # steady-state fraction of stake missing per epoch (30d uptime 99.72%, Jul 2026)
    el_apr_bonus: float = 0.21            # EL rewards as fraction on top of CL rewards

    @property
    def total_gwei(self) -> int:
        return int(self.total_staked_eth * 1e9)

    def base_reward_gwei_per_32eth(self) -> float:
        br_incr = (1e9 * 64) // math.isqrt(self.total_gwei)
        return 32 * br_incr

    def att_reward_per_epoch_gwei(self) -> float:
        # per 32 ETH validator, ideal attestation reward per epoch
        return self.base_reward_gwei_per_32eth() * ATT_REWARD_W / WEIGHT_DEN

    def att_penalty_per_epoch_gwei(self) -> float:
        return self.base_reward_gwei_per_32eth() * ATT_PENALTY_W / WEIGHT_DEN

    def cl_apr(self) -> float:
        # attestation-only APR approximation (ignore proposer/sync ~ +14%)
        yearly = self.att_reward_per_epoch_gwei() * EPOCHS_PER_YEAR
        return yearly / 32e9

    def full_reward_per_epoch_gwei(self) -> float:
        """Approx total earnings per epoch incl proposer+sync (64/54 of att) and EL."""
        cl = self.att_reward_per_epoch_gwei() * (64 / 54)  # proposer+sync gross-up
        return cl * (1 + self.el_apr_bonus)


def steady_state_nep(miss: float, paf: int = PAF_DEFAULT) -> float:
    """Analytic steady-state NET_EXCESS_PENALTIES for sustained miss rate."""
    return miss * paf / SLOTS_PER_EPOCH


def simulate(miss_schedule, paf=PAF_DEFAULT, maxf=MAXF_DEFAULT, nep0=None,
             total_balance=10**15):
    """
    miss_schedule: iterable of per-slot miss fractions (fraction of that slot's
                   committee balance that fails to attest).
    Returns list of (penalty_factor, nep_after) per slot. Exact integer math.
    """
    committee = total_balance // SLOTS_PER_EPOCH
    if nep0 is None:
        # warm up 10000 slots at the first schedule value
        m0 = miss_schedule[0]
        nep = 0
        for _ in range(10_000):
            nab = int(m0 * committee)
            pf = min(nab * paf // (nep * total_balance + 1), maxf)
            nep = max(1, nep + pf) - 1
    else:
        nep = nep0
    out = []
    for m in miss_schedule:
        nab = int(m * committee)
        pf = min(nab * paf // (nep * total_balance + 1), maxf)
        nep = max(1, nep + pf) - 1
        out.append((pf, nep))
    return out


def outage_cost(net: Network, spike: float, duration_epochs: float,
                paf=PAF_DEFAULT, maxf=MAXF_DEFAULT, scaled_weight=ATT_PENALTY_W,
                verbose=False):
    """
    Scenario: on top of baseline_miss, an extra `spike` fraction of total stake
    goes fully offline for `duration_epochs`, then recovers.

    Returns dict with per-affected-validator (32 ETH) costs:
      - avg penalty factor experienced during outage
      - total loss (missed rewards + scaled penalties) in gwei
      - loss expressed as days of normal full earnings ("time to make it back")
      - comparison with status quo (factor == 1)
    """
    m0 = net.baseline_miss
    m1 = m0 + spike
    dur_slots = int(round(duration_epochs * SLOTS_PER_EPOCH))
    # simulate: warmup at m0 (handled by nep0=None), outage at m1, recovery at m0
    post_slots = 20_000
    schedule = [m0] + [m1] * dur_slots + [m0] * post_slots
    res = simulate(schedule, paf=paf, maxf=maxf)
    outage_res = res[1:1 + dur_slots]

    # An affected validator attests once per epoch in a uniformly random slot;
    # average factor over all outage slots = expected factor applied per miss.
    avg_pf = sum(pf for pf, _ in outage_res) / len(outage_res)
    max_pf = max(pf for pf, _ in outage_res)
    slots_at_max = sum(1 for pf, _ in outage_res if pf == maxf)
    # zero-factor slots during recovery (discount window after outage ends)
    rec = res[1 + dur_slots:]
    zero_after = 0
    for pf, _ in rec:
        if pf == 0:
            zero_after += 1
        else:
            break

    pen = net.att_penalty_per_epoch_gwei()          # full 40/64 penalty, always applied
    rew = net.att_reward_per_epoch_gwei()
    # only `scaled_weight`/64 of base reward is subject to penalty_factor scaling;
    # the rest of the 40/64 penalty stays at 1x
    br = net.base_reward_gwei_per_32eth()
    scaled_pen = br * scaled_weight / WEIGHT_DEN
    unscaled_pen = pen - scaled_pen
    missed_epochs = duration_epochs

    loss_7716 = missed_epochs * (rew + unscaled_pen + avg_pf * scaled_pen)
    loss_now = missed_epochs * (rew + 1.0 * pen)
    loss_max = missed_epochs * (rew + unscaled_pen + maxf * scaled_pen)

    per_epoch_earn = net.full_reward_per_epoch_gwei()
    return {
        "spike": spike,
        "duration_epochs": duration_epochs,
        "avg_pf": avg_pf,
        "max_pf": max_pf,
        "slots_at_max": slots_at_max,
        "zero_pf_slots_after": zero_after,
        "loss_7716_gwei": loss_7716,
        "loss_now_gwei": loss_now,
        "loss_if_capped_whole_time_gwei": loss_max,
        "payback_days_7716": loss_7716 / per_epoch_earn / EPOCHS_PER_DAY,
        "payback_days_now": loss_now / per_epoch_earn / EPOCHS_PER_DAY,
        "payback_days_capped": loss_max / per_epoch_earn / EPOCHS_PER_DAY,
        "usd_7716": loss_7716 / 1e9 * net.eth_price_usd,
        "usd_now": loss_now / 1e9 * net.eth_price_usd,
    }


def fmt_days(d):
    if d < 1/24:
        return f"{d*24*60:.0f} min"
    if d < 1:
        return f"{d*24:.1f} h"
    if d < 14:
        return f"{d:.1f} d"
    if d < 90:
        return f"{d/7:.1f} wk"
    return f"{d/30.44:.1f} mo"


if __name__ == "__main__":
    net = Network()
    br = net.base_reward_gwei_per_32eth()
    print(f"Network: {net.total_staked_eth/1e6:.1f}M ETH staked, "
          f"base_reward={br:.0f} gwei/epoch per 32 ETH")
    print(f"  att reward/epoch = {net.att_reward_per_epoch_gwei():.0f} gwei, "
          f"penalty/epoch (1x) = {net.att_penalty_per_epoch_gwei():.0f} gwei")
    print(f"  CL(att-only) APR = {net.cl_apr()*100:.2f}%  | "
          f"assumed full earnings/epoch = {net.full_reward_per_epoch_gwei():.0f} gwei")
    print(f"  steady-state NEP at baseline miss {net.baseline_miss:.3%}: "
          f"{steady_state_nep(net.baseline_miss):.2f}")
    print()

    durations = [(1, "1 epoch (6.4 min)"), (round(EPOCHS_PER_DAY/24), "1 hour"),
                 (round(EPOCHS_PER_DAY), "1 day"), (round(7*EPOCHS_PER_DAY), "1 week")]
    spikes = [0.01, 0.05, 0.10, 0.20, 0.40]

    hdr = f"{'spike':>6} {'duration':>16} {'avgPF':>6} {'slots@max':>9} " \
          f"{'payback now':>12} {'payback 7716':>13} {'payback @cap':>13} {'USD 7716':>10}"
    print(hdr)
    print("-" * len(hdr))
    for sp in spikes:
        for d, label in durations:
            r = outage_cost(net, sp, d)
            print(f"{sp:>6.0%} {label:>16} {r['avg_pf']:>6.2f} {r['slots_at_max']:>9} "
                  f"{fmt_days(r['payback_days_now']):>12} {fmt_days(r['payback_days_7716']):>13} "
                  f"{fmt_days(r['payback_days_capped']):>13} {r['usd_7716']:>10.2f}")
        print()
