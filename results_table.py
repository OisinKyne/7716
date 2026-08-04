#!/usr/bin/env python3
"""
Format `results/summary.json` into the deliverable tables (markdown + stdout).

Run after `xatu_ingest.py`, `attribution.py` and `eip7716_historical.py`.
"""

from __future__ import annotations

import argparse

import events
import json
import os

LINES = [("status_quo", "Status quo"),
         ("original", "EIP-7716 as drafted (4096 / 4)"),
         ("revised", "EIP-7716 revised (381 / 128 / 2^17)")]

BUCKET_ORDER = ["silent", "desynced", "wrong-target", "uncollected", "chronic", "unknown"]
BUCKET_NOTE = {
    "silent": "nothing on the p2p network either",
    "desynced": "signing on a stale justified checkpoint",
    "wrong-target": "correct source, non-canonical target",
    "uncollected": "valid attestation gossiped, never included",
    "chronic": "already offline before Fusaka",
    "unknown": "not classifiable from the gossip record",
}


def fmt_days(d):
    if d < 1 / 24:
        return f"{d * 24 * 60:.0f} min"
    if d < 1:
        return f"{d * 24:.1f} h"
    if d < 14:
        return f"{d:.2f} d"
    if d < 90:
        return f"{d / 7:.1f} wk"
    return f"{d / 30.44:.1f} mo"


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    events.add_event_arg(ap)
    ap.add_argument("--results-dir", default=None)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    ev = events.get(args.event)
    results_dir = args.results_dir or ev.results_dir
    out_path = args.out or os.path.join(results_dir, "RESULTS.md")

    s = json.load(open(os.path.join(results_dir, "summary.json")))
    L = []
    w = L.append

    lo, hi = s["event_epochs"]
    w(f"# Results — {ev.title} under EIP-7716\n")
    w(f"Event epochs **{lo}–{hi}** ({hi - lo + 1} epochs, {ev.subtitle}), mainnet.")
    w(f"Total active balance {s['total_active_balance_eth'] / 1e6:.2f}M ETH; "
      f"`base_reward_per_increment` = {s['base_reward_per_increment_gwei']} gwei; "
      f"measured CL APR {s['cl_apr'] * 100:.2f}%.\n")
    w(f"Moving average seeded from epochs **{s['seed_window'][0]}–{s['seed_window'][1]}** "
      f"({ev.seed_label}): mean per-slot offline balance {s['seed_ema_eth']:,.0f} ETH, "
      f"= {s['seed_offline_share'] * 100:.3f}% of stake. "
      f"`NET_EXCESS_PENALTIES` warmed on the same window to {s['seed_nep']}.\n")

    w("## 1. Penalty factors actually produced\n")
    w("| | revised (381 / 128) | as drafted (4096 / 4) |")
    w("|---|---|---|")
    fr, fo = s["factor_revised"], s["factor_original"]
    w(f"| peak per-slot factor | **{fr['max']}x** | **{fo['max']}x** |")
    nslots = (hi - lo + 1) * 32
    w(f"| mean over the {nslots} event slots | {fr['mean']:.1f}x | {fo['mean']:.3f}x |")
    w(f"| slots pinned at the cap | {fr['slots_at_cap']} / {nslots} | {fo['slots_at_cap']} / {nslots} |")
    w(f"| slots at factor 0 (discount) | 0 | {fo['slots_at_zero']} / {nslots} |")
    w(f"| mean factor *as experienced by an offline validator* | "
      f"{s['event']['mean_factor_revised']:.1f}x | "
      f"{s['event']['mean_factor_original']:.3f}x |")
    w("")
    w(f"Peak per-slot offline share was {s['peak_offline_share'] * 100:.1f}% of stake — "
      "below the one-third saturation point, so the revised cap never binds and the "
      "factor discriminates on event size rather than pinning.\n")

    for key, title in (("event", "2. Days-to-recoup, unattributed — event window only"),
                       ("event_plus_tail", "3. Days-to-recoup, unattributed — event plus recovery tail")):
        b = s[key]
        w(f"## {title}\n")
        w(f"{b['n_validators_affected']:,} validators were offline for at least one epoch; "
          f"mean {b['mean_offline_epochs']:.1f} offline epochs each. "
          "Every validator is normalised to a 32 ETH stake before averaging.\n")
        w("| Line | mean loss / 32 ETH | days-to-recoup (mean) | median | p95 | vs status quo |")
        w("|---|---|---|---|---|---|")
        ref = b["status_quo"]["mean_days_to_recoup"]
        for k, label in LINES:
            r = b[k]
            w(f"| {label} | {r['mean_loss_gwei_per_32eth'] / 1e6:.2f} mETH | "
              f"**{fmt_days(r['mean_days_to_recoup'])}** | {fmt_days(r['median_days_to_recoup'])} | "
              f"{fmt_days(r['p95_days_to_recoup'])} | {r['mean_days_to_recoup'] / ref:.2f}x |")
        w("")

    if "attributed" in s:
        w("## 4. Attributed cut — behavioural, with `unknown` carried explicitly\n")
        w("No client split is claimed. There is no on-chain fingerprint for either "
          "consensus or execution clients, and the ethPandaOps entity/client tables are "
          "Clickhouse-only. What follows is what the p2p record *can* establish.\n")

        att_path = os.path.join(results_dir, "attribution.json")
        if os.path.exists(att_path):
            a = json.load(open(att_path))
            w("Weighted by **offline validator-epochs** — what the offline stake was doing "
              "at any given moment:\n")
            w("| signature | % of offline stake | validator-epochs | distinct validators |")
            w("|---|---|---|---|")
            for r in a["buckets"]:
                w(f"| `{r['bucket']}` | {r['pct_of_offline_stake']:.1f}% | "
                  f"{int(r['validator_epochs']):,} | {int(r['validators']):,} |")
            w("")
            w(f"The distinct-validator counts sum well past the "
              f"{a['distinct_validators_ever']['offline_validators']:,} validators actually "
              "affected, because nodes flapped between states — restarting, resyncing, "
              "falling behind again. Weighting by validator instead of by validator-epoch "
              "therefore gives a different picture, and both are reported.\n")

        w("Weighted by **validator**, each assigned the signature it showed in most of its "
          "offline epochs. `purity` is how dominant that mode was; low purity means the "
          "node flapped.\n")
        w("| Bucket | what it means | validators | % of offline stake | purity | "
          "days-to-recoup: today | drafted | revised |")
        w("|---|---|---|---|---|---|---|---|")
        att = s["attributed"]
        for bucket in BUCKET_ORDER:
            if bucket not in att:
                continue
            r = att[bucket]
            w(f"| `{bucket}` | {BUCKET_NOTE[bucket]} | {r['validators']:,} | "
              f"{r['share_of_offline_stake'] * 100:.1f}% | {r['mean_bucket_purity']:.2f} | "
              f"{fmt_days(r['days_to_recoup_status_quo'])} | "
              f"{fmt_days(r['days_to_recoup_original'])} | "
              f"**{fmt_days(r['days_to_recoup_revised'])}** |")
        w("")
        w("### 4a. Client attribution\n")
        w("| Client | share of the offline cohort |")
        w("|---|---|")
        w("| `unknown` | **100%** |")
        w("")
        w("That row is the finding, not a placeholder. Consensus-client attribution "
          "requires proposal-fingerprinting (blockprint), which is not in the public "
          "Xatu Parquet mirror; execution-client attribution has no on-chain signal at "
          "all. Any \"Nethermind was N% of the validator set\" number is a self-reported "
          "survey, not a measurement, and multiplying the results above by one would "
          "give the survey's error bars the appearance of chain data. The behavioural "
          "buckets are the strongest cut the public record supports: `desynced` is the "
          "signature the Nethermind → Nimbus fake-invalid path would leave, and `silent` "
          "is what attestation resource exhaustion looks like from outside — but both "
          "are also what an ordinary hard-down node of any client looks like.\n")

    na = s["network_accounting"]
    w("## 5. Network-wide accounting under today's rules (cross-check)\n")
    w("Not a 7716 quantity. This is what the network gave up, for comparison with the "
      "postmortem's headline. The dominant term is not the offline cohort's own loss: "
      "attestation rewards carry a `participating_increments / active_increments` factor, "
      "so every *online* validator's reward is quadratic in participation and falls too.\n")
    w("| Component | ETH |")
    w("|---|---|")
    w(f"| forgone attestation rewards (all validators, vs pre-Fusaka baseline) | "
      f"{na['forgone_attestation_rewards_eth']:.1f} |")
    w(f"| excess attestation penalties | {na['excess_attestation_penalties_eth']:.1f} |")
    w(f"| forgone proposer rewards, CL ({na['excess_missed_slots']:.0f} excess missed slots) | "
      f"{na['forgone_proposer_cl_eth']:.1f} |")
    w(f"| forgone proposer rewards, EL/MEV | {na['forgone_proposer_el_eth']:.1f} |")
    w(f"| forgone sync-committee rewards | {na['forgone_sync_eth']:.1f} |")
    w(f"| **total** | **{na['total_network_cost_eth']:.0f}** |")
    w("")
    w(f"Missed-slot rate {na['missed_slot_rate'] * 100:.1f}% "
      f"({na['missed_slots']} of {na['slots']} slots) against a "
      f"{na['baseline_missed_slot_rate'] * 100:.2f}% pre-Fusaka baseline.\n")

    dv = s["hypothetical_dv_archetype"]
    w("## 6. Distributed-validator archetype — HYPOTHETICAL\n")
    w("This is a **construction, not an observation**. Nothing in the data identifies a "
      "distributed validator. It models a validator whose key is split across nodes "
      "running different clients, so a client-specific bug removes only part of the "
      "cluster; if the survivors still meet threshold it attests normally and pays "
      "nothing. `survival` is the fraction of the event during which threshold held.\n")
    w("| survival | epochs offline | days-to-recoup today | days-to-recoup revised |")
    w("|---|---|---|---|")
    for name, c in dv["cases"].items():
        w(f"| {float(name.split('_')[1]) * 100:.0f}% | {c['epochs_offline']:.0f} | "
          f"{fmt_days(c['days_to_recoup_status_quo'])} | "
          f"{fmt_days(c['days_to_recoup_revised'])} |")
    w("")

    text = "\n".join(L)
    with open(out_path, "w") as fh:
        fh.write(text + "\n")
    print(text)


if __name__ == "__main__":
    main()
