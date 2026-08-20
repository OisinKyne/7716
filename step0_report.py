#!/usr/bin/env python3
"""
STEP 0 -- the gating question. Were those validators dark, or merely slow?

EIP-7716 scales the timely-target penalty only for validators missing BOTH the
timely source flag and the timely target flag. A validator that lands a timely
source but a late or wrong target demonstrated liveness, is explicitly not
"offline" under the spec, and pays today's unscaled rate.

Prysm's failure mode on 2025-12-04 was attestation *resource exhaustion*, and an
exhausted node often still attests, just late. If most of the missing 22.7% had
produced timely sources, the penalty factor collapses toward 1x and the event is
not a usable case.

This prints the four-way flag breakdown over the event epochs, the participation
cross-check against the published floor, and -- if the p2p gossip partitions are
present -- the network-side control that separates "produced nothing" from
"produced something the chain never counted".
"""

from __future__ import annotations

import argparse

import events
import os

import duckdb


def fmt_pct(x):
    return f"{x * 100:7.3f}%"


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    events.add_event_arg(ap)
    ap.add_argument("--derived-dir", default=None)
    ap.add_argument("--data-dir", default="data/xatu")
    ap.add_argument("--event-lo", type=int, default=None)
    ap.add_argument("--event-hi", type=int, default=None)
    ap.add_argument("--baseline-lo", type=int, default=None)
    ap.add_argument("--baseline-hi", type=int, default=None)
    args = ap.parse_args()

    ev = events.get(args.event)
    args.derived_dir = args.derived_dir or ev.derived_dir
    args.event_lo = args.event_lo if args.event_lo is not None else ev.event_lo
    args.event_hi = args.event_hi if args.event_hi is not None else ev.event_hi
    args.baseline_lo = args.baseline_lo if args.baseline_lo is not None else ev.seed_lo
    args.baseline_hi = args.baseline_hi if args.baseline_hi is not None else ev.seed_hi

    con = duckdb.connect(config={"threads": 8})
    con.execute(
        f"CREATE VIEW epochs AS SELECT * FROM "
        f"read_parquet('{os.path.join(args.derived_dir, 'epochs.parquet')}')"
    )

    def window(lo, hi, title):
        r = con.sql(
            f"""
            SELECT sum(assigned_bal) AS tot, sum(assigned_n) AS n,
                   sum(both_bal) AS both_b, sum(both_n) AS both_n,
                   sum(source_only_bal) AS so_b, sum(source_only_n) AS so_n,
                   sum(target_only_bal) AS to_b, sum(target_only_n) AS to_n,
                   sum(offline_bal) AS off_b, sum(offline_n) AS off_n,
                   sum(no_att_bal) AS na_b, sum(no_att_n) AS na_n,
                   sum(late_and_wrong_bal) AS lw_b, sum(late_and_wrong_n) AS lw_n
            FROM epochs WHERE epoch BETWEEN {lo} AND {hi}
            """
        ).df().iloc[0]
        print(f"\n{title}  (epochs {lo}-{hi}, {hi - lo + 1} epochs)")
        print(f"{'':<48}{'share of stake':>16}{'share of validators':>21}")
        rows = [
            ("attested fully (timely source AND target)", r.both_b, r.both_n),
            ("timely source, missed target   [NOT scaled]", r.so_b, r.so_n),
            ("missed source, timely target   [NOT scaled]", r.to_b, r.to_n),
            ("missed BOTH  ->  OFFLINE       [SCALED]", r.off_b, r.off_n),
        ]
        for label, b, n in rows:
            print(f"{label:<48}{fmt_pct(b / r.tot):>16}{fmt_pct(n / r.n):>21}")
        print(f"{'    of which no attestation included at all':<48}"
              f"{fmt_pct(r.na_b / r.tot):>16}{fmt_pct(r.na_n / r.n):>21}")
        print(f"{'    of which attested late AND wrong target':<48}"
              f"{fmt_pct(r.lw_b / r.tot):>16}{fmt_pct(r.lw_n / r.n):>21}")

    window(args.baseline_lo, args.baseline_hi, ev.baseline_label)
    window(args.event_lo, args.event_hi, "EVENT WINDOW")

    print("\n--- per-epoch extremes, event window ---")
    print(
        con.sql(
            f"""
            SELECT
              min(target_participation) AS min_target_participation,
              arg_min(epoch, target_participation) AS at_epoch,
              max(offline_bal * 1.0 / assigned_bal) AS max_offline_share,
              arg_max(epoch, offline_bal * 1.0 / assigned_bal) AS peak_epoch,
              1 - sum(blocks) * 1.0 / (32 * count(*)) AS missed_slot_rate
            FROM epochs WHERE epoch BETWEEN {args.event_lo} AND {args.event_hi}
            """
        ).df().to_string(index=False)
    )
    if ev.postmortem_note:
        print(f"\ncross-check: {ev.postmortem_note}.")

    print(f"\n--- plateau detail (epochs where offline share > {ev.plateau_threshold*100:.0f}%) ---")
    print(
        con.sql(
            f"""
            SELECT count(*) AS epochs,
                   round(avg(offline_bal * 1.0 / assigned_bal) * 100, 2) AS mean_offline_pct,
                   round(avg(source_only_bal * 1.0 / assigned_bal) * 100, 3) AS mean_src_only_pct,
                   round(avg(target_only_bal * 1.0 / assigned_bal) * 100, 3) AS mean_tgt_only_pct,
                   round(avg(offline_bal * 1.0 /
                        (offline_bal + source_only_bal + target_only_bal)) * 100, 2)
                     AS pct_of_non_full_attesters_that_were_dark
            FROM epochs
            WHERE epoch BETWEEN {args.event_lo} AND {args.event_hi}
              AND offline_bal * 1.0 / assigned_bal > {ev.plateau_threshold}
            """
        ).df().to_string(index=False)
    )

    from xatu_ingest import _local_name, days_covering as _dc
    _gossip_days = [f"{d[:4]}-{int(d[5:7])}-{int(d[8:10])}" 
                    for d in _dc(args.event_lo, args.event_hi)]
    gossip = sorted(
        os.path.join(args.data_dir, f)
        for f in os.listdir(args.data_dir)
        if f.startswith("gossipatt_") and f.endswith(".parquet")
        and any(f.startswith("gossipatt_" + _d) for _d in _gossip_days)
    )
    if not gossip:
        print("\n(no gossipatt_*.parquet present -- skipping the p2p control)")
        return

    print("\n--- p2p control: was the offline cohort silent on the network too? ---")
    glist = ", ".join(repr(p) for p in gossip)
    OFF = os.path.join(args.derived_dir, "offline_validators.parquet")
    from xatu_ingest import _local_name, days_covering
    _days = days_covering(args.event_lo, args.event_hi)
    _cands = [os.path.join(args.data_dir, _local_name("committee", d)) for d in _days]
    _cands = [c for c in _cands if os.path.exists(c)]
    if not _cands:
        print(f"\n(no committee Parquet for {_days} -- skipping the p2p control)")
        return
    C = "read_parquet([" + ", ".join(repr(c) for c in _cands) + "])"
    lo, hi = con.sql(f"SELECT min(epoch), max(epoch) FROM read_parquet([{glist}])").fetchone()
    lo, hi = max(lo, args.event_lo), min(hi, args.event_hi)
    con.execute(
        f"""
        CREATE TABLE seen AS SELECT DISTINCT epoch, attesting_validator_index AS validator
        FROM read_parquet([{glist}])
        WHERE epoch BETWEEN {lo} AND {hi} AND attesting_validator_index IS NOT NULL
        """
    )
    con.execute(
        f"""
        CREATE TABLE assigned AS SELECT epoch, UNNEST(validators) AS validator
        FROM {C} WHERE epoch BETWEEN {lo} AND {hi}
        """
    )
    con.execute(
        f"""
        CREATE TABLE off AS SELECT epoch, validator FROM read_parquet('{OFF}')
        WHERE epoch BETWEEN {lo} AND {hi}
        """
    )
    ctrl = con.sql(
        """
        SELECT
          count(*) FILTER (WHERE o.validator IS NULL) AS online_validator_epochs,
          round(100.0 * count(*) FILTER (WHERE o.validator IS NULL AND s.validator IS NOT NULL)
                / count(*) FILTER (WHERE o.validator IS NULL), 3) AS pct_online_seen_in_gossip,
          count(*) FILTER (WHERE o.validator IS NOT NULL) AS offline_validator_epochs,
          round(100.0 * count(*) FILTER (WHERE o.validator IS NOT NULL AND s.validator IS NOT NULL)
                / count(*) FILTER (WHERE o.validator IS NOT NULL), 3) AS pct_offline_seen_in_gossip
        FROM assigned a
        LEFT JOIN off o USING (epoch, validator)
        LEFT JOIN seen s USING (epoch, validator)
        """
    ).df()
    print(ctrl.to_string(index=False))
    print(f"(gossip control over epochs {lo}-{hi}; sentry recall is the first "
          f"percentage and is the control for the second)")

    recall_pct = float(ctrl["pct_online_seen_in_gossip"].iloc[0])
    if recall_pct < 95.0:
        print(
            f"\n  !! SENTRY RECALL {recall_pct:.3f}% — THIS CONTROL FAILED.\n"
            "     Absence from gossip cannot be read as validator silence at this\n"
            "     coverage level, so the offline percentage above is NOT\n"
            "     interpretable and must not be quoted.\n"
            "     The flag breakdown earlier in this report is UNAFFECTED: it is\n"
            "     derived from canonical chain data, not from sentry observations."
        )


if __name__ == "__main__":
    main()
