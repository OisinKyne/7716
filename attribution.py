#!/usr/bin/env python3
"""
Attributed cut of the offline cohort, with a visible `unknown` bucket.

There is no on-chain fingerprint for either consensus or execution clients, and
the ethPandaOps CBT tables that carry entity labels (`dim_node`,
`fct_attestation_liveness_by_entity`, `fct_block_proposer_entity`) are
Clickhouse-only -- not in the public Parquet mirror. So this does not claim a
client split.

What it does instead is a *behavioural* split that is measurable, using the
p2p gossip record (`beacon_api_eth_v1_events_attestation`, 93 sentries) against
the on-chain record. For every validator that the chain scored as offline:

  desynced      it gossiped an attestation whose SOURCE checkpoint did not match
                the canonical justified checkpoint. Such an attestation is
                structurally unincludable -- `process_attestation` asserts
                `is_matching_source`, so a block carrying it is invalid. The node
                was running and signing, from a stale view of the chain.

  wrong-target  correct source, non-canonical target. Alive, following, but on a
                different fork at the epoch boundary.

  uncollected   correct source AND correct target, seen on the network, never
                landed on chain. Genuinely alive; the chain simply never counted
                it. This is the bucket where the "offline" label is arguably
                wrong, and it is the honest error bar on the headline.

  silent        nothing observable on the network at all. Node down, or up but
                not producing -- attestation resource exhaustion looks exactly
                like this from the outside.

  chronic       already offline through the pre-Fusaka baseline window; not an
                event casualty at all.

The mapping from these buckets to named clients is an inference, not a
measurement, and is left to the write-up. `silent` is compatible with the Prysm
resource-exhaustion path and with any ordinary hard-down node; `desynced` is
compatible with the Nethermind -> Nimbus fake-invalid path. Neither is proof.

Sentry recall is measured, not assumed: the share of *on-chain-included*
validators that were also seen in gossip is reported per epoch, and is ~100%.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import duckdb

import events

# The behavioural split reads absence-from-gossip as evidence a validator was
# silent. That inference is only valid when sentry coverage is near-total, which
# is what the recall control measures. Below this floor the "silent" bucket is
# measuring sentry coverage rather than validator behaviour, so the
# classification is refused outright instead of being published with a caveat
# nobody reads. Observed: 99.996% (2025-12-04), 99.995% (2024-01-06),
# 7.953% (2024-01-21 -- refused).
MIN_SENTRY_RECALL_PCT = 95.0

# 'chronic' = already offline through this event's own baseline window,
# so it must be the event's window, not another era's.
CHRONIC_MIN_FRACTION = 0.5  # offline in >= half the baseline window


def _day_src(data_dir: str, kind: str, days: list[str]) -> str:
    from xatu_ingest import _local_name
    paths = [os.path.join(data_dir, _local_name(kind, d)) for d in days]
    paths = [p for p in paths if os.path.exists(p)]
    if not paths:
        raise SystemExit(f"no {kind} Parquet for {days} in {data_dir}")
    return "read_parquet([" + ", ".join(repr(p) for p in paths) + "])"


def gossip_files(data_dir: str, days: list[str]) -> list[str]:
    """
    Sentry partitions for THIS event's days only. An unfiltered glob would
    attribute one era's offline cohort using another era's p2p observations
    whenever more than one event is on disk -- silently, with no error.
    """
    # gossipatt_ files are named with un-zero-padded month/day
    prefixes = tuple(
        f"gossipatt_{d[:4]}-{int(d[5:7])}-{int(d[8:10])}_" for d in days
    )
    return sorted(
        os.path.join(data_dir, f)
        for f in os.listdir(data_dir)
        if f.startswith(prefixes) and f.endswith(".parquet")
    )


def build(con, data_dir, derived_dir, epoch_lo, epoch_hi, days,
          chronic_lo, chronic_hi, chronic_min_epochs):
    gfiles = gossip_files(data_dir, days)
    if not gfiles:
        raise SystemExit(
            f"no gossipatt_*.parquet for {days} in {data_dir}; "
            "download this event's sentry partitions first")
    glist = ", ".join(repr(p) for p in gfiles)
    G = f"read_parquet([{glist}])"
    A = _day_src(data_dir, "attestation", days)
    OFF = f"read_parquet('{os.path.join(derived_dir, 'offline_validators.parquet')}')"

    covered = con.sql(f"SELECT min(epoch), max(epoch) FROM {G}").fetchone()
    lo = max(epoch_lo, covered[0])
    hi = min(epoch_hi, covered[1])
    print(f"gossip covers epochs {covered[0]}-{covered[1]}; classifying {lo}-{hi}", file=sys.stderr)

    # canonical source / target for each epoch, from what actually landed on chain
    con.execute(
        f"""
        CREATE OR REPLACE TABLE canon AS
        SELECT epoch, any_value(source_root) AS src, mode(target_root) AS tgt
        FROM {A} WHERE epoch BETWEEN {lo} AND {hi} GROUP BY epoch
        """
    )
    # one row per (epoch, validator) seen gossiping, with what it voted
    con.execute(
        f"""
        CREATE OR REPLACE TABLE seen AS
        SELECT epoch, attesting_validator_index AS validator,
               bool_or(source_root = c.src) AS any_src_ok,
               bool_or(source_root = c.src AND target_root = c.tgt) AS any_full_ok,
               min(propagation_slot_start_diff) AS prop_ms
        FROM {G} g JOIN canon c USING (epoch)
        WHERE epoch BETWEEN {lo} AND {hi} AND attesting_validator_index IS NOT NULL
        GROUP BY epoch, attesting_validator_index
        """
    )
    con.execute(
        f"""
        CREATE OR REPLACE TABLE chronic AS
        SELECT validator FROM {OFF}
        WHERE epoch BETWEEN {chronic_lo} AND {chronic_hi}
        GROUP BY validator HAVING count(*) >= {chronic_min_epochs}
        """
    )
    con.execute(
        f"""
        CREATE OR REPLACE TABLE offline_classified AS
        SELECT o.epoch, o.validator, o.slot_index, o.effective_balance,
               CASE
                 WHEN c.validator IS NOT NULL THEN 'chronic'
                 WHEN s.validator IS NULL THEN 'silent'
                 WHEN NOT s.any_src_ok THEN 'desynced'
                 WHEN s.any_full_ok THEN 'uncollected'
                 ELSE 'wrong-target'
               END AS bucket
        FROM {OFF} o
        LEFT JOIN seen s ON s.epoch = o.epoch AND s.validator = o.validator
        LEFT JOIN chronic c ON c.validator = o.validator
        WHERE o.epoch BETWEEN {lo} AND {hi}
        """
    )
    return lo, hi


def recall(con, data_dir, lo, hi, days):
    """Share of on-chain-included validators also seen in gossip -- sentry recall."""
    C = _day_src(data_dir, "committee", days)
    OFF_TBL = "offline_classified"
    return con.sql(
        f"""
        WITH assigned AS (
            SELECT epoch, UNNEST(validators) AS validator FROM {C}
            WHERE epoch BETWEEN {lo} AND {hi}
        ),
        online AS (
            SELECT a.epoch, a.validator FROM assigned a
            LEFT JOIN {OFF_TBL} o USING (epoch, validator)
            WHERE o.validator IS NULL
        )
        SELECT count(*) AS online_validator_epochs,
               round(100.0 * count(*) FILTER (WHERE s.validator IS NOT NULL) / count(*), 3)
                 AS pct_seen_in_gossip
        FROM online LEFT JOIN seen s USING (epoch, validator)
        """
    ).df()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    events.add_event_arg(ap)
    ap.add_argument("--data-dir", default="data/xatu")
    ap.add_argument("--derived-dir", default=None)
    ap.add_argument("--out-dir", default=None)
    ap.add_argument("--epoch-lo", type=int, default=None)
    ap.add_argument("--epoch-hi", type=int, default=None)
    args = ap.parse_args()

    spec = events.get(args.event)
    args.derived_dir = args.derived_dir or spec.derived_dir
    args.out_dir = args.out_dir or spec.results_dir
    args.epoch_lo = args.epoch_lo if args.epoch_lo is not None else spec.event_lo
    args.epoch_hi = args.epoch_hi if args.epoch_hi is not None else spec.event_hi

    from xatu_ingest import days_covering
    # ISO throughout; gossip_files() and _local_name() each do their own
    # filename formatting, so converting here would double-convert.
    days = days_covering(args.epoch_lo, args.epoch_hi)
    chronic_lo, chronic_hi = spec.seed_lo, spec.seed_hi
    chronic_min_epochs = int((chronic_hi - chronic_lo + 1) * CHRONIC_MIN_FRACTION)

    os.makedirs(args.out_dir, exist_ok=True)
    con = duckdb.connect(config={"threads": 8, "memory_limit": "12GB"})
    lo, hi = build(con, args.data_dir, args.derived_dir, args.epoch_lo, args.epoch_hi,
                   days, chronic_lo, chronic_hi, chronic_min_epochs)

    rec = recall(con, args.data_dir, lo, hi, days)
    print("\n--- sentry recall control ---")
    print(rec.to_string(index=False))

    _recall_pct = float(rec["pct_seen_in_gossip"].iloc[0])
    if _recall_pct < MIN_SENTRY_RECALL_PCT:
        sys.exit(
            f"\nREFUSED: sentry recall {_recall_pct:.3f}% is below the "
            f"{MIN_SENTRY_RECALL_PCT}% floor.\n"
            "Absence from gossip cannot be read as validator silence at this "
            "coverage level -- the 'silent' bucket would be measuring the sentry\n"
            "fleet, not the validators. No classification written. Either fetch "
            "denser sentry partitions for this window, or report the recall\n"
            "failure itself as the finding and omit the behavioural split for "
            "this event."
        )

    by_bucket = con.sql(
        """
        SELECT bucket,
               count(*) AS validator_epochs,
               count(DISTINCT validator) AS validators,
               sum(effective_balance) / 1e9 AS eth_epochs,
               round(100.0 * sum(effective_balance) / sum(sum(effective_balance)) OVER (), 2)
                 AS pct_of_offline_stake
        FROM offline_classified GROUP BY bucket ORDER BY eth_epochs DESC
        """
    ).df()
    print("\n--- offline cohort, behavioural split ---")
    print(by_bucket.to_string(index=False))

    by_epoch = con.sql(
        """
        SELECT epoch, bucket, sum(effective_balance) / 1e9 AS eth
        FROM offline_classified GROUP BY 1, 2 ORDER BY 1, 2
        """
    ).df()

    # Validator-epochs and validators answer different questions. The split above
    # says what the offline stake was doing at a given moment; this says how many
    # distinct validators ever showed each signature. Nodes flapped between
    # states, so the two do not agree and both are reported.
    ever = con.sql(
        """
        SELECT count(DISTINCT validator) AS offline_validators,
               count(DISTINCT validator) FILTER (WHERE bucket = 'desynced') AS ever_desynced,
               count(DISTINCT validator) FILTER (WHERE bucket = 'silent') AS ever_silent,
               count(DISTINCT validator) FILTER (WHERE bucket = 'uncollected') AS ever_uncollected,
               count(DISTINCT validator) FILTER (WHERE bucket = 'wrong-target') AS ever_wrong_target,
               count(DISTINCT validator) FILTER (WHERE bucket = 'chronic') AS chronic
        FROM offline_classified
        """
    ).df()
    print("\n--- distinct validators that EVER showed each signature (buckets overlap) ---")
    print(ever.to_string(index=False))

    onset = con.sql(
        """
        SELECT epoch,
               round(sum(effective_balance) FILTER (WHERE bucket = 'desynced') / 1e9) AS desynced_eth,
               round(sum(effective_balance) FILTER (WHERE bucket = 'silent') / 1e9) AS silent_eth,
               round(sum(effective_balance) FILTER (WHERE bucket = 'uncollected') / 1e9) AS uncollected_eth
        FROM offline_classified GROUP BY epoch ORDER BY epoch
        """
    ).df()
    onset.to_csv(os.path.join(args.out_dir, "attribution_onset.csv"), index=False)

    con.execute(
        f"COPY offline_classified TO "
        f"'{os.path.join(args.out_dir, 'offline_classified.parquet')}' (FORMAT PARQUET)"
    )
    by_bucket.to_csv(os.path.join(args.out_dir, "attribution_buckets.csv"), index=False)
    by_epoch.to_csv(os.path.join(args.out_dir, "attribution_by_epoch.csv"), index=False)

    with open(os.path.join(args.out_dir, "attribution.json"), "w") as fh:
        json.dump(
            {
                "epochs_classified": [int(lo), int(hi)],
                "sentry_recall_pct": float(rec.pct_seen_in_gossip.iloc[0]),
                "buckets": by_bucket.to_dict("records"),
                "distinct_validators_ever": ever.to_dict("records")[0],
            },
            fh,
            indent=2,
            default=float,
        )
    print(f"\nwrote attribution outputs to {args.out_dir}")


if __name__ == "__main__":
    main()
