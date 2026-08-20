*(Source of [this comment](https://ethresear.ch/t/supporting-decentralized-staking-through-more-anti-correlation-incentives/19116/18). Images use the Discourse `upload://` shortcodes from the published post, so pasting this file over the live post preserves them; the two new figures in the August update use GitHub URLs that Discourse will rehost on paste. Current vs live delta: the appended "Update, August 2026" section.)*

Reviving this thread two years on, with a model, a calibration, and a proposed restructuring of the mechanism it produced.

[Earlier in this thread](https://ethresear.ch/t/supporting-decentralized-staking-through-more-anti-correlation-incentives/19116/6) I commented that if a double-digit% liveness failure cost a month or more of lost rewards, it would have an impact on operator behaviour. Now that extra intelligence costs a hundred dollars a month on subscription, I've been able to spend the time to put together a model on the existing proposal, to ensure we are setting parameters that will appropriately influence change. Unfortunately it turns out that the EIP as written changed almost nothing for any outage of any size or duration, and the implicit fix (raising the cap, which was suggested at the time by [Vasiliy](https://ethresear.ch/t/a-concrete-proposal-for-correlated-attester-penalties/19341/4) and [ValarDragon](https://ethresear.ch/t/a-concrete-proposal-for-correlated-attester-penalties/19341/5)) turns out to be irrelevant due to an invariant in the update rule. This comment is 1) the case for why the mechanism needs restructuring rather than retuning, 2) a proposed replacement that keeps the per-slot structure but changes the reference variable, and 3) a calibration with simulated costs across outage scenarios to help build rough consensus in the community on how punitive a correlated downtime *should* be. It complements an update to EIP7716 as it seeks SFI for the Hegotá hardfork.

tl;dr: under the original 7716 mechanism, a validator caught in a 10%-of-stake, 24 hour correlated outage loses $6.17, identical to an uncorrelated failure, whether the cap is 4 or 256. Under the proposed revision it loses ~$69 (about two weeks of rewards), the penalty factor scales linearly with event size up to the finality threshold, and a multi-day finality-losing outage reaches 1-3% of principal in combination with the (unchanged) inactivity leak. Solo stakers failing on their own keep paying exactly what they pay today.

## Prior work

- The OP of this thread — Vitalik's analysis showing same-cluster validators co-fail far more than chance predicts.
- [Analysis on "Correlated Attestation Penalties"](https://ethresear.ch/t/analysis-on-correlated-attestation-penalties/19244) — Toni's backtest over ~40 days of attestation data: large operator clusters pay more under correlation-scaled penalties, solo stakers and Rocket Pool operators pay less.
- [A concrete proposal for correlated attester penalties](https://ethresear.ch/t/a-concrete-proposal-for-correlated-attester-penalties/19341) — the `NET_EXCESS_PENALTIES` mechanism that became [EIP-7716](https://eips.ethereum.org/EIPS/eip-7716), plus the [explainer thread](https://ethresear.ch/t/diseconomies-of-scale-anti-correlation-penalties-eip-7716/20114), [FAQ](https://github.com/dapplion/anti-correlation-penalties-faq), and a [draft Lighthouse implementation](https://github.com/igorline/lighthouse/pull/1).

I take the empirical motivation as settled and focus on the mechanism. Numbers below use July 2026 parameters (~40.7M eth staked, eth ≈ $1,840, base_reward ≈ 10,144 gwei/epoch per 32 eth, full CL+EL rewards ≈ $5.08/day per 32 eth validator) and a ~0.3% baseline offline rate (30-day network uptime is 99.72% at time of writing; the true both-flags-missing rate is somewhat lower still, and helpfully, under the proposed normalisation none of the numbers below depend on it). The simulations use exact spec integer arithmetic.

## What the drafted mechanism actually charges

EIP-7716 as drafted computes, per slot:

```
penalty_factor = min(non_attesting_balance * PENALTY_ADJUSTMENT_FACTOR
                       // (NET_EXCESS_PENALTIES * total_active_balance + 1),
                     MAX_PENALTY_FACTOR)                        # 4096, cap 4
NET_EXCESS_PENALTIES = max(1, NET_EXCESS_PENALTIES + penalty_factor) - 1
```

`NET_EXCESS_PENALTIES` chases the current miss rate, so the factor returns to 1 under any sustained participation level. For a 10% outage this takes about two minutes (Fig. 1). The mechanism prices the first few slots of an event and nothing after, and even hands out a small factor-0 discount window once the outage ends.

![Fig 1 — penalty factor trajectories](upload://90rQoNfU27rV8ukuQRGwuIr2RlJ.png)

The natural response is to raise the cap. It doesn't work. Each slot adds `penalty_factor − 1` to the counter, so across any step change in participation:

```
Σ (factor − 1)  =  ΔNET_EXCESS_PENALTIES  =  PAF · Δmiss / 32
```

The total excess penalty is a fixed budget, independent of `MAX_PENALTY_FACTOR` and of outage duration. A larger cap just concentrates the same budget into fewer slots (Fig. 2).

![Fig 2 — cap invariance](upload://xZTT88H2DTj9uUb4aVbVyaQlMN2.png)

Raising `PENALTY_ADJUSTMENT_FACTOR` does grow the budget, but the counter only decays at 1 per slot, so at constants large enough to matter (PAF ≈ 2^27 for percent-of-principal severity) the post-event recovery window stretches to roughly eight months, during which a second correlated event of any size lands at factor ~1. There are two further problems: at mainnet participation the counter's equilibrium sits below 1, so it bounces off zero and ordinary uncorrelated misses draw random factors between 0 and the cap (bad luck for solo stakers, who this EIP is meant to favour), and the original revenue-neutrality goal is itself what pins the total at a rounding error. These are properties of the update rule, not the constants, which is why I think the mechanism needs restructuring rather than retuning.

## What I think the penalty should look like

1) **Severity should scale with how much stake failed together, and the marginal cost of staying offline should decline quickly back towards the status quo.** Rectification speed correlates with operator size: professional operators restore service in hours, a solo staker might need days to recover or replace a machine. A duration-punishing design transfers the burden to exactly the operators this EIP is meant to protect. (For the same reason I looked at, and rejected, extending the quadratic inactivity leak below the finality threshold: its marginal cost per hour *grows* with consecutive downtime, the exact opposite shape. A quadratic leak-style penalty gated at 5% offline could charge a 72 hour recovery north of $800 while barely touching the 1 hour one.)

2) **Penalties should stay reward-relative.** Principal-level punishment already exists in the inactivity leak (≥1/3 offline) and slashing. Today the protocol prices correlation as a step function at 33%; the job for this EIP is bringing incentives into the 1-33% band that are measured as a function of the reward one might make staking for a year.

3) **The mechanism shouldn't misfire on things that aren't infrastructure failures**: relay/builder outages, late epoch-boundary blocks, proposers splitting views, or operators correctly staying on a minority client through a majority-client bug.

4) **The reference inactivity should forget events on a fixed timescale**, not one proportional to event size, so the deterrent is always armed.

## The proposed revision to EIP 7716

One new `Gwei` state field and effectively two constants (the slope is derived):

```
offline           = balance in this slot's committees missing BOTH
                    timely source AND timely target
committee_balance = total_active_balance // 32
factor            = min(1 + PENALTY_SLOPE * max(0, offline − smoothed_offline_balance)
                          // committee_balance,
                        MAX_PENALTY_FACTOR)   # cap 128, slope = 3·(cap−1) = 381
smoothed_offline_balance += (offline − smoothed_offline_balance)
                          // OFFLINE_BALANCE_SMOOTHING_FACTOR   # 2**17, ~12.6d half-life
```

The factor multiplies only the timely-target penalty, and only for validators missing both source and target. Source penalties stay at 1x and head votes remain penalty-free. `OFFLINE_BALANCE_SMOOTHING_FACTOR = 2**17` makes `smoothed_offline_balance` an exponential moving average (EMA) of the per-slot offline balance with a half-life of ~12.6 days (the same integer smoothing pattern as 4844's excess blob gas, so nothing novel for client teams). At steady state the factor is exactly 1 for every slot.

There are two normalisation details worth highlighting. The excess is divided by per-slot active balance, not by the EMA: an EMA-relative slope would make every onset factor (and the point where the cap binds) proportional to the baseline offline rate, so at the 99.7% participation we actually observe, a curve calibrated against a 99.5% assumption steepens by two thirds and saturates near 19% rather than a third. Dividing by active balance makes the curve invariant to participation drift, and setting `PENALTY_SLOPE = 3 × (MAX_PENALTY_FACTOR − 1)` makes the cap bind at exactly one third of stake as an identity, leaving the cap as the single severity knob. (One might worry that committee selection isn't stake-weighted post-7251, so realised per-slot committee balances wobble with the mix of 2048s and 32s — I checked, and it's ~1.2% relative std today and ~2% even under heavy consolidation, and the divisor is the deterministic per-slot average anyway, so the noise only enters the numerator where the EMA absorbs it.)

Onset factors are then baseline-independent: ~5x at a 1% event, 20x at 5%, 39x at 10%, 77x at 20%, cap at one third — the factor discriminates by size across the whole band it is responsible for, and hands over to the leak exactly where the leak activates (Fig. 3).

![Fig 3 — onset factor vs event size](upload://mK8Jn7dfI06WHFZsKe5EoPrXsg4.png)

The new scope restriction ("missing both source and target") is doing most of the security work. A missing block does not prevent anyone attesting: the committee votes the previous head and keeps full credit, so relay and builder failures don't register as attester faults at all. The one artifact they *can* cause (timely-source loss when 5+ consecutive slots are empty) is excluded, because scaling also requires a missed target, and target has the whole next epoch to be included. A validator that attested with a wrong target but a live, correct source (i.e a late boundary block, a split view, a correct minority client while a supermajority client forks off) was demonstrably online, so should pay only today's unscaled penalty. Getting scaled requires producing no timely attestation at all, **which a third party can't induce in a healthy validator without sustained censorship of its aggregates across a full epoch of inclusion opportunities**. In my eyes this closes the proposer view-splitting attack the original EIP left as TBD, and it answers the concern ([raised by jshufro in Toni's thread](https://ethresear.ch/t/analysis-on-correlated-attestation-penalties/19244/13)) that correlation penalties would punish operators for correctly staying on a canonical minority client.

## What it costs

Per 32 eth validator. The cohort is offline for 24 hours unless stated; "payback" is the time to re-earn the loss at full rewards.

| Event | Rectified in | Today | Revised | Payback |
|---|---|---|---|---|
| uncorrelated failure | 24 h | $6.17 | $6.17 (1.0x) | 1.2 d |
| 1% correlated | 24 h | $6.17 | $12 (2.0x) | 2.5 d |
| 5% correlated | 24 h | $6.17 | $38 (6.1x) | 7.4 d |
| 10% correlated | 6 h | $1.54 | $18 (11.5x) | 3.5 d |
| 10% correlated | 24 h | $6.17 | $69 (11.3x) | 2 wk |
| 10% correlated | 72 h | $18.50 | $82 (4.4x) | 2.3 wk |
| 20% correlated | 24 h | $6.17 | $133 (21.5x) | 3.7 wk |
| 40%, leak active | 24 h | $95 | $312 (3.3x) | 2 mo |
| 40% down 3 days (finality lost) | 72 h | $819 | $1,469 (1.8x) | 9.5 mo ≈ 2.5% of principal |

Fig. 4 compares mechanisms as a function of individual rectification time (the drafted mechanism literally overlaps the status quo line). Note the shape: exposure is meaningful but flattens once the cohort recovers, so the 72 hour straggler pays about $12 more than the 24 hour rectifier. Fig. 5 shows the same property as marginal cost per hour. Fig. 6 shows the layering with the leak across event sizes. (The clean gap-down at hour 24 in these charts is a modelling simplification; real events mostly do recover near-in-unison — a patch ships, operators restart — but if you model an exponentially staggered recovery instead, the aggregate anomaly persists a little longer and a 48h straggler pays ~10-25% more than the cliff model suggests, i.e. the cliff is the *optimistic* case for stragglers. Fig. 1 shows both. Nothing qualitative changes.)

![Fig 4 — cost vs rectification time](upload://w02CVGRWZlnxxfgiLqLw4BUpu45.png)

![Fig 5 — marginal cost per hour](upload://ll6l5RAwv3iIcvlfvu0j6VPFxfL.png)

![Fig 6 — layering with the inactivity leak](upload://7aNIQ142FLSN90jmI9VZhl1Jcvw.png)

Here are some key bounds worth considering as we review this proposal. The worst-case penalty flow is ~0.38% of a 32 eth principal per day, and only while roughly a third of stake is newly offline and the validator itself is fully offline (for calibration: the leak takes ~50% in 18 days, slashing can take everything). A useful conversion at current rates is that X months of rewards ≈ X × 0.26% of principal, so even the harshest scenario in the table is nowhere near stake-level punishment. An uncorrelated validator coincidentally down for six hours during a 40% crisis pays ~$55, about eleven days of rewards — bounded, but a real cost of any statistical mechanism, since the protocol can't observe cluster membership. Flapping outages cost *less* than the same downtime taken as isolated events, because the elevated EMA acts as a refractory period. And after a major crisis the reference decays on its fixed half-life (Fig. 7), where a counter-based design with an equivalent budget would report factor ~1 for the better part of a year.

![Fig 7 — re-arming after a crisis](upload://sQrC2wVujLk9IMvegZKKaAJPd2a.png)

My original gut-feel calibration was that a double-digit% liveness failure should cost "a month or more" to earn back. This proposal lands a 20%/24h event at ~3.7 weeks and a 10%/24h at ~2 weeks, which is about in range, without slamming into the cap at small event sizes (an earlier calibration I tried saturated at 5%, making a 10% event and a 30% event cost the same, which seems wrong). Also from [that 2024 comment](https://ethresear.ch/t/supporting-decentralized-staking-through-more-anti-correlation-incentives/19116/6): the suggestion that those offline during an outage should be hit harder than those who stay online through it — that's what this shape does, and the factor never drops below 1, so there are no discount windows subsidising missers during recovery.

## Departures from the original EIP-7716 2024 design, stated plainly

- **Revenue neutrality is dropped.** The original mechanism guaranteed unchanged average validator revenue at every participation level, and that guarantee is the direct cause of the fixed-budget behaviour above. Considering many in the community want staking to be less appealing, and for issuance to be lower, I infer this will be a positively received alteration.
- **One severity knob.** With the slope pinned to 3×(cap−1), `MAX_PENALTY_FACTOR` is the only free severity parameter: cap 128 gives the table above; cap 64 (slope 189) halves the curve (10%/24h ≈ $37, about a week of rewards) with saturation still at one third. The ~12.6 day half-life separately sets how long the EMA remembers an event, which is both the decay of an ongoing event's factor and the re-arm time.
- **Known residual issues**: an entity could suppress the reference by sustaining elevated misses for a couple of weeks before a planned failure, at the cost of paying full penalties on that stake the whole time, visibly on-chain; the bystander exposure above; and the implementation cost, which is dominated by per-slot participation bookkeeping at epoch processing (a 32×3 balance array and a validator-to-slot mapping — the draft Lighthouse PR built this already). No block-path changes, one state field.

## Open questions

1) Calibration: is ~2 weeks of lost rewards the right price for a 10%/24h correlated failure? Would the cap-64 variant (~1 week) still change operator behaviour? I don't have a rigorous model of operator elasticity here, just the [GCP SLA comparison ValarDragon made in 2024](https://ethresear.ch/t/a-concrete-proposal-for-correlated-attester-penalties/19341/5) (a 7-8 hour monthly outage earns you a 10% bill rebate from Google; the revised mechanism charges a 10% cohort roughly 3.5 days of gross revenue for the same downtime, which at typical operator commissions is a far larger fraction of *margin*).

2) Should the leak's own cliff at 33% be smoothed with a graded ramp? Out of scope here but adjacent.

3) Historical replay: I'd like to run the revised factor over past incidents (the May 2023 non-finality events in particular). The offline-signature scope needs per-flag participation history which public datasets don't consistently carry — pointers to a good source very welcome.

To conclude: the case for anti-correlation penalties was made two years ago and hasn't been rebutted; what was missing is a mechanism that charges an amount anyone would notice, without punishing the slow-recovery long tail or misfiring on relay outages and chain splits. I think the offline-pattern + EMA-reference design above addresses both concerns, and the constants are now a policy choice the community can argue about with the model in hand. The revised EIP text is up as a [PR](https://github.com/ethereum/EIPs/pull/11962), the simulation and figure code I have published [here](https://github.com/OisinKyne/7716), as well as a [PR](https://github.com/ethereum/consensus-specs/pull/5452) to the consensus-specs. Feedback is sought and appreciated on all of it, particularly from operators whose incident-response costs this is explicitly trying to shape, and core devs considering it for inclusion in Hegotá. Thanks for reading.

---

## Update, August 2026: backtested on five years of real outages

Open question 3 above is answered. The per-flag participation history I was missing is derivable from the ethPandaOps Xatu public Parquet (no key, mainnet from genesis) — [ksale001 contributed a backtest harness](https://github.com/OisinKyne/7716/pull/1) that reconstructs `get_slot_offline_balance` from raw attestation records, validates it by executing the consensus-specs Python straight out of the spec markdown, and reproduces each incident's published postmortem figures before scoring anything. We've now run status quo, the 2024 draft, and this revision over four real events, each under its own era's rules (the EIP-7045 target-flag change matters) and its own measured EL income:

| Event | peak offline | as drafted | revised | days-to-recoup (revised) |
| --- | --- | --- | --- | --- |
| May 11+12 2023 finality incidents | 69%, cap binds | **1.16x** | **39.8x** | 0.97 d |
| Besu halt, Jan 2024 | 12.4% | 1.04x | **2.2x** | 2.8 h |
| Nethermind bug, Jan 2024 | 18.8% | 1.01x | **7.5x** | 11.2 h |
| Prysm post-Fusaka, Dec 2025 | 29.8% | 1.01x | **22.7x** | 2.40 d |

Two things worth pulling out. The drafted mechanism is a measured no-op on all four — including May 2023, its own motivating incident — which is the fixed-budget invariant on chain data rather than in algebra. And the revision is proportionate: 2.2x for a moderate incident, the cap binding only in the one event that crossed a third of stake.

Because the ingest records each validator's offline epochs individually, we could also measure something no postmortem documents: **cost as a function of each operator's own recovery time**. This addresses the long-tail concern directly. On the December 2025 event, a validator that took 24–36 hours to come back paid 1.40x what the 6–8 hour crowd paid; under *today's* rules that same spread costs 4.1x. Besu's resync-stragglers — down 48 hours — paid 1.4x today's cost. The charge lands on being correlated at onset, not on how long the fix takes.

![cost by personal recovery hour, four real events](https://raw.githubusercontent.com/OisinKyne/7716/main/figures/w1_straggler_curves.png)

We also swept the smoothing half-life (2¹⁴–2¹⁸) and asymmetric fast-rise variants over all four events, since the window is the parameter I was least sure of. Result: window length barely moves any real event (they're all cliffs, hours-scale against a days-scale window) — what it actually prices is *sustained* outages, where 2¹⁷ charges a 10%-of-stake, 7-day cohort ~92 days of income. Fast-rise skews that decay the factor with time-since-onset were rejected with data: they buy a marginal fairness improvement (1.40x → ~1.2x) while letting a 20% operator sit out three days at mean factor 2.7. Straggler forgiveness and sustained-outage forgiveness turn out to be the same quantity for any global factor; the write-ups are [WINDOW_TUNING.md](https://github.com/OisinKyne/7716/blob/main/WINDOW_TUNING.md) and the full sweep tables in the repo.

![window length: real events flat, sustained outages priced](https://raw.githubusercontent.com/OisinKyne/7716/main/figures/w3_window_effect.png)

On the revenue-neutrality departure flagged above, there's now a quantified answer to "isn't this an issuance debate by proxy" ([REDISTRIBUTION.md](https://github.com/OisinKyne/7716/blob/main/REDISTRIBUTION.md)): the worst event since the Merge would have burned ~2,290 ETH extra — 0.24% of one year's issuance, once — and the steady-state burn is measurably zero. Redistributing instead would recreate either the fixed-budget no-op or a discouragement-attack bounty (that December event would have handed online validators a 2,290 ETH pot, ~690 ETH of it to any 30% staker who *caused* a competitor's outage). Every penalty in the current spec burns; this one should too.

Finally, on forward-compatibility: the [decoupled consensus / fast finality effort](https://consensus.ethereum.foundation/blog/upgrading-finality-edition-1) will split today's attestation into separate fork-choice and finality votes. This mechanism scales only the finality-vote penalty (timely target) and gates on the source+target pair, deliberately leaving head/fork-choice votes untouched — so the signal it prices lives entirely in the component that remains a full-validator-set FFG-style vote under decoupling, while the part that becomes a small-committee message is the part we never scaled. Nothing in the mechanism depends on epoch structure beyond the smoothing constant, which is a tunable. I've checked this framing with Ben Edgington, who is leading the decoupled consensus effort: the two proposals compose.
