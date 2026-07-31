#!/usr/bin/env python3
"""
Historical ingestion path: real mainnet chain data -> per-slot offline balances.

The repo's other modules run *synthetic* scenarios parameterised by outage size
and duration. This module produces the same per-slot quantity the mechanism
consumes (`get_slot_offline_balance`) from actual chain data, so the existing
factor computation can be driven by a real event.

Data source
-----------
ethPandaOps Xatu public Parquet, `data.ethpandaops.io`. No key, no account.
Three tables are used, all daily-partitioned on the *attested/assigned* slot:

  canonical_beacon_committee               (slot, committee_index, validators[])
  canonical_beacon_elaborated_attestation  (slot, block_slot, target_root, validators[])
  canonical_beacon_block                   (slot, block_root)      -- canonical chain
  canonical_beacon_validators              (epoch, index, effective_balance, slashed)

Flag derivation
---------------
No public dataset stores participation flags. They are derived here exactly as
`get_attestation_participation_flag_indices` does, post-EIP-7045 (Deneb):

  is_matching_source  -- guaranteed. `process_attestation` asserts it, so every
                         attestation that made it into a canonical block matched
                         the justified checkpoint. (Confirmed empirically: one
                         distinct source_root per epoch across the pull range.)
  TIMELY_SOURCE       <- inclusion_delay <= integer_squareroot(SLOTS_PER_EPOCH) = 5
  TIMELY_TARGET       <- target_root == get_block_root(state, epoch)
                         (EIP-7045 removed the inclusion-delay bound on target)
  TIMELY_HEAD         <- matching target AND beacon_block_root == canonical root
                         at the attested slot AND inclusion_delay == 1

  get_block_root(state, epoch) is the root of the most recent canonical block at
  or before `epoch * SLOTS_PER_EPOCH` -- the skipped-slot fill-back that
  `state.block_roots` performs.

`is_offline_in_previous_epoch` == not slashed and not TIMELY_SOURCE and not
TIMELY_TARGET. A validator with a timely source but a late/wrong target
demonstrated liveness and is *not* offline.

Outputs (written to --out-dir as Parquet + CSV)
----------------------------------------------
  slots.parquet   one row per slot: offline_balance_gwei, assigned_balance_gwei,
                  the four-way flag breakdown, total_active_balance_gwei
  epochs.parquet  per-epoch rollup, incl. participation rates for cross-checks
  offline.parquet one row per (epoch, validator) that was offline, with the slot
                  its committee sat in -- drives the per-validator cost model
"""

from __future__ import annotations

import argparse
import os
import sys
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import duckdb

# ------------------------------------------------------------------ chain constants
GENESIS_TIME = 1_606_824_023  # mainnet
SLOTS_PER_EPOCH = 32
SECONDS_PER_SLOT = 12
# integer_squareroot(SLOTS_PER_EPOCH); the timely-source inclusion bound
TIMELY_SOURCE_MAX_DELAY = 5

XATU_BASE = "https://data.ethpandaops.io/xatu/mainnet/databases/default"
# the CDN 403s the default urllib agent
USER_AGENT = "eip7716-model/1.0 (+https://github.com/OisinKyne/7716)"


def _fetch(url: str, path: str) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req) as resp, open(path, "wb") as fh:
        while chunk := resp.read(1 << 20):
            fh.write(chunk)

TABLES_DAILY = {
    "committee": "canonical_beacon_committee",
    "attestation": "canonical_beacon_elaborated_attestation",
    "block": "canonical_beacon_block",
}


def epoch_start_time(epoch: int) -> int:
    return GENESIS_TIME + epoch * SLOTS_PER_EPOCH * SECONDS_PER_SLOT


def epoch_utc(epoch: int) -> datetime:
    return datetime.fromtimestamp(epoch_start_time(epoch), timezone.utc)


def days_covering(epoch_lo: int, epoch_hi: int) -> list[str]:
    """UTC dates whose daily partitions cover [epoch_lo, epoch_hi] inclusive.

    Partitions key on the *assigned/attested* slot, so the dates spanned by the
    epoch range's wall-clock extent are exactly the partitions needed. (Late
    inclusion does not widen this: a row lives in the partition of the slot it
    attests to, not the block that carried it.)
    """
    d0 = epoch_utc(epoch_lo).date()
    d1 = epoch_utc(epoch_hi + 1).date()
    out, d = [], d0
    while d <= d1:
        out.append(d.isoformat())
        d += timedelta(days=1)
    return out


# ------------------------------------------------------------------ download
def _local_name(kind: str, date: str) -> str:
    return f"{kind}_{date[:4]}-{int(date[5:7])}-{int(date[8:10])}.parquet"


def _remote_url(kind: str, date: str) -> str:
    y, m, d = int(date[:4]), int(date[5:7]), int(date[8:10])
    return f"{XATU_BASE}/{TABLES_DAILY[kind]}/{y}/{m}/{d}.parquet"


def ensure_daily(data_dir: str, kind: str, date: str, verbose=True) -> str | None:
    path = os.path.join(data_dir, _local_name(kind, date))
    if os.path.exists(path) and os.path.getsize(path) > 0:
        return path
    url = _remote_url(kind, date)
    try:
        if verbose:
            print(f"  downloading {url}", file=sys.stderr)
        _fetch(url, path + ".part")
        os.replace(path + ".part", path)
        return path
    except Exception as exc:  # noqa: BLE001 - partition may simply not exist
        if verbose:
            print(f"  !! {url}: {exc}", file=sys.stderr)
        if os.path.exists(path + ".part"):
            os.remove(path + ".part")
        return None


def validator_snapshot_url(date: str, hour: int) -> str:
    y, m, d = int(date[:4]), int(date[5:7]), int(date[8:10])
    return f"{XATU_BASE}/canonical_beacon_validators/{y}/{m}/{d}/{hour}.parquet"


def ensure_validator_snapshot(data_dir: str, date: str, hour: int, verbose=True) -> str | None:
    path = os.path.join(
        data_dir, f"validators_{date[:4]}-{int(date[5:7])}-{int(date[8:10])}_h{hour:02d}.parquet"
    )
    if os.path.exists(path) and os.path.getsize(path) > 0:
        return path
    url = validator_snapshot_url(date, hour)
    try:
        if verbose:
            print(f"  downloading {url}", file=sys.stderr)
        _fetch(url, path + ".part")
        os.replace(path + ".part", path)
        return path
    except Exception as exc:  # noqa: BLE001
        if verbose:
            print(f"  !! {url}: {exc}", file=sys.stderr)
        if os.path.exists(path + ".part"):
            os.remove(path + ".part")
        return None


# ------------------------------------------------------------------ ingestion
@dataclass
class Ingest:
    data_dir: str
    epoch_lo: int
    epoch_hi: int
    threads: int = 8
    memory_limit: str = "12GB"

    def __post_init__(self):
        self.con = duckdb.connect(
            config={"threads": self.threads, "memory_limit": self.memory_limit}
        )
        self.dates = days_covering(self.epoch_lo, self.epoch_hi)
        self.files: dict[str, list[str]] = {}
        for kind in TABLES_DAILY:
            paths = [p for d in self.dates if (p := ensure_daily(self.data_dir, kind, d))]
            if not paths:
                raise SystemExit(f"no {kind} partitions available for {self.dates}")
            self.files[kind] = paths
        self.validator_files = sorted(
            os.path.join(self.data_dir, f)
            for f in os.listdir(self.data_dir)
            if f.startswith("validators_") and f.endswith(".parquet")
        )
        if not self.validator_files:
            raise SystemExit("no canonical_beacon_validators snapshots in data dir")

    def _src(self, kind: str) -> str:
        lst = ", ".join(repr(p) for p in self.files[kind])
        return f"read_parquet([{lst}])"

    # -------------------------------------------------------------- canonical chain
    def build_canonical_roots(self) -> None:
        """slot -> canonical block root, plus the fill-back used by state.block_roots."""
        lo = (self.epoch_lo - 2) * SLOTS_PER_EPOCH
        hi = (self.epoch_hi + 2) * SLOTS_PER_EPOCH
        self.con.execute(
            f"""
            CREATE OR REPLACE TABLE blocks AS
            SELECT slot, any_value(block_root) AS block_root
            FROM {self._src('block')}
            WHERE slot BETWEEN {lo} AND {hi}
            GROUP BY slot
            """
        )
        # get_block_root_at_slot: for a skipped slot, the most recent prior root.
        self.con.execute(
            f"""
            CREATE OR REPLACE TABLE slot_roots AS
            WITH all_slots AS (SELECT UNNEST(range({lo}, {hi + 1})) AS slot),
                 j AS (SELECT a.slot, b.block_root FROM all_slots a LEFT JOIN blocks b USING (slot))
            SELECT slot,
                   block_root AS block_root_here,
                   last_value(block_root IGNORE NULLS) OVER (
                       ORDER BY slot ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
                   ) AS filled_root
            FROM j
            """
        )
        # get_block_root(state, epoch) == get_block_root_at_slot(epoch * 32)
        self.con.execute(
            f"""
            CREATE OR REPLACE TABLE epoch_target_roots AS
            SELECT slot // {SLOTS_PER_EPOCH} AS epoch, filled_root AS target_root
            FROM slot_roots
            WHERE slot % {SLOTS_PER_EPOCH} = 0
            """
        )
        n_missing = self.con.sql(
            "SELECT count(*) FROM epoch_target_roots WHERE target_root IS NULL"
        ).fetchone()[0]
        if n_missing:
            raise SystemExit(f"{n_missing} epochs have no resolvable target root")

    # -------------------------------------------------------------- balances
    def build_balances(self) -> None:
        """Per-validator effective balance from the nearest available snapshot epoch.

        Effective balance moves only at epoch boundaries and only through the
        Electra hysteresis band, so a snapshot within a few hundred epochs is a
        sub-basis-point approximation. Every snapshot epoch is retained and each
        analysis epoch binds to the nearest one, so validators activated during
        the window are still covered.
        """
        lst = ", ".join(repr(p) for p in self.validator_files)
        self.con.execute(
            f"""
            CREATE OR REPLACE TABLE validator_snapshots AS
            SELECT epoch AS snap_epoch, index AS validator, effective_balance, slashed,
                   status::VARCHAR AS status
            FROM read_parquet([{lst}])
            WHERE status::VARCHAR IN ('active_ongoing', 'active_exiting', 'active_slashed')
            """
        )
        self.con.execute(
            """
            CREATE OR REPLACE TABLE snapshot_epochs AS
            SELECT DISTINCT snap_epoch FROM validator_snapshots ORDER BY snap_epoch
            """
        )
        self.snap_epochs = [r[0] for r in self.con.sql("SELECT * FROM snapshot_epochs").fetchall()]
        # total_active_balance per snapshot epoch -> slot_reference_balance
        self.con.execute(
            """
            CREATE OR REPLACE TABLE snapshot_totals AS
            SELECT snap_epoch,
                   sum(effective_balance)::HUGEINT AS total_active_balance,
                   count(*) AS n_active
            FROM validator_snapshots GROUP BY snap_epoch
            """
        )

    def _nearest_snapshot(self, epoch: int) -> int:
        return min(self.snap_epochs, key=lambda s: abs(s - epoch))

    # -------------------------------------------------------------- flags
    def run(self, chunk: int = 20, verbose: bool = True):
        self.build_canonical_roots()
        self.build_balances()

        self.con.execute("DROP TABLE IF EXISTS slot_stats")
        self.con.execute(
            """
            CREATE TABLE slot_stats (
                epoch UINTEGER, slot UINTEGER, slot_index UTINYINT,
                assigned_n BIGINT, assigned_bal HUGEINT,
                offline_n BIGINT, offline_bal HUGEINT,
                no_att_n BIGINT, no_att_bal HUGEINT,
                late_and_wrong_n BIGINT, late_and_wrong_bal HUGEINT,
                target_only_n BIGINT, target_only_bal HUGEINT,
                source_only_n BIGINT, source_only_bal HUGEINT,
                both_n BIGINT, both_bal HUGEINT,
                head_n BIGINT, head_bal HUGEINT,
                slashed_n BIGINT, slashed_bal HUGEINT
            )
            """
        )
        self.con.execute("DROP TABLE IF EXISTS offline_validators")
        self.con.execute(
            "CREATE TABLE offline_validators ("
            "epoch UINTEGER, slot_index UTINYINT, validator UINTEGER, effective_balance UBIGINT)"
        )
        self.con.execute("DROP TABLE IF EXISTS epoch_snapshot")
        self.con.execute("CREATE TABLE epoch_snapshot (epoch UINTEGER, snap_epoch UINTEGER)")

        self.unmatched = 0
        for lo in range(self.epoch_lo, self.epoch_hi + 1, chunk):
            hi = min(lo + chunk - 1, self.epoch_hi)
            snap = self._nearest_snapshot((lo + hi) // 2)
            if verbose:
                print(
                    f"  epochs {lo}-{hi}  (balances @ snapshot epoch {snap})",
                    file=sys.stderr,
                )
            self.con.execute(
                f"INSERT INTO epoch_snapshot "
                f"SELECT UNNEST(range({lo}, {hi + 1})), {snap}"
            )
            self._chunk(lo, hi, snap)

        if self.unmatched:
            print(
                f"  note: {self.unmatched} (epoch, validator) assignments had no effective "
                f"balance in the nearest snapshot; defaulted to 32 ETH",
                file=sys.stderr,
            )
        return self.con

    def _chunk(self, lo: int, hi: int, snap: int) -> None:
        slot_lo, slot_hi = lo * SLOTS_PER_EPOCH, hi * SLOTS_PER_EPOCH + SLOTS_PER_EPOCH - 1
        con = self.con

        con.execute(
            f"""
            CREATE OR REPLACE TEMP TABLE eb AS
            SELECT validator, effective_balance, slashed
            FROM validator_snapshots WHERE snap_epoch = {snap}
            """
        )

        # Per-validator participation flags for each epoch in the chunk.
        # A validator has exactly one attestation duty per epoch; multiple rows
        # are the same attestation re-included in several blocks/aggregates, so
        # max() over the rows reproduces "the flag was set at some inclusion".
        con.execute(
            f"""
            CREATE OR REPLACE TEMP TABLE flags AS
            WITH att AS (
                SELECT a.epoch,
                       UNNEST(a.validators) AS validator,
                       a.block_slot - a.slot AS delay,
                       a.target_root = t.target_root AS target_ok,
                       a.beacon_block_root = r.filled_root AS head_ok
                FROM {self._src('attestation')} a
                JOIN epoch_target_roots t ON t.epoch = a.epoch
                JOIN slot_roots r ON r.slot = a.slot
                WHERE a.epoch BETWEEN {lo} AND {hi}
                  AND a.slot BETWEEN {slot_lo} AND {slot_hi}
            )
            SELECT epoch, validator,
                   bool_or(delay <= {TIMELY_SOURCE_MAX_DELAY}) AS timely_source,
                   bool_or(target_ok) AS timely_target,
                   bool_or(target_ok AND head_ok AND delay = 1) AS timely_head,
                   min(delay) AS min_delay
            FROM att GROUP BY epoch, validator
            """
        )

        con.execute(
            f"""
            CREATE OR REPLACE TEMP TABLE assign AS
            SELECT c.epoch, c.slot, (c.slot % {SLOTS_PER_EPOCH})::UTINYINT AS slot_index,
                   UNNEST(c.validators) AS validator
            FROM {self._src('committee')} c
            WHERE c.epoch BETWEEN {lo} AND {hi}
              AND c.slot BETWEEN {slot_lo} AND {slot_hi}
            """
        )

        con.execute(
            f"""
            CREATE OR REPLACE TEMP TABLE joined AS
            SELECT a.epoch, a.slot, a.slot_index, a.validator,
                   COALESCE(e.effective_balance, 32000000000)::UBIGINT AS eb,
                   e.validator IS NOT NULL AS eb_known,
                   COALESCE(e.slashed, FALSE) AS slashed,
                   COALESCE(f.timely_source, FALSE) AS ts,
                   COALESCE(f.timely_target, FALSE) AS tt,
                   COALESCE(f.timely_head, FALSE) AS th,
                   f.validator IS NOT NULL AS attested_at_all
            FROM assign a
            LEFT JOIN eb e USING (validator)
            LEFT JOIN flags f ON f.epoch = a.epoch AND f.validator = a.validator
            """
        )

        self.unmatched += con.sql(
            "SELECT count(*) FROM joined WHERE NOT eb_known"
        ).fetchone()[0]

        con.execute(
            """
            INSERT INTO slot_stats
            SELECT epoch, slot, slot_index,
                   count(*), sum(eb),
                   count(*) FILTER (WHERE NOT ts AND NOT tt AND NOT slashed),
                   COALESCE(sum(eb) FILTER (WHERE NOT ts AND NOT tt AND NOT slashed), 0),
                   count(*) FILTER (WHERE NOT attested_at_all),
                   COALESCE(sum(eb) FILTER (WHERE NOT attested_at_all), 0),
                   count(*) FILTER (WHERE attested_at_all AND NOT ts AND NOT tt),
                   COALESCE(sum(eb) FILTER (WHERE attested_at_all AND NOT ts AND NOT tt), 0),
                   count(*) FILTER (WHERE NOT ts AND tt),
                   COALESCE(sum(eb) FILTER (WHERE NOT ts AND tt), 0),
                   count(*) FILTER (WHERE ts AND NOT tt),
                   COALESCE(sum(eb) FILTER (WHERE ts AND NOT tt), 0),
                   count(*) FILTER (WHERE ts AND tt),
                   COALESCE(sum(eb) FILTER (WHERE ts AND tt), 0),
                   count(*) FILTER (WHERE th),
                   COALESCE(sum(eb) FILTER (WHERE th), 0),
                   count(*) FILTER (WHERE slashed),
                   COALESCE(sum(eb) FILTER (WHERE slashed), 0)
            FROM joined GROUP BY epoch, slot, slot_index
            """
        )

        con.execute(
            """
            INSERT INTO offline_validators
            SELECT epoch, slot_index, validator, eb
            FROM joined WHERE NOT ts AND NOT tt AND NOT slashed
            """
        )

    # -------------------------------------------------------------- outputs
    def write(self, out_dir: str) -> None:
        os.makedirs(out_dir, exist_ok=True)
        con = self.con
        con.execute(
            f"""
            CREATE OR REPLACE TABLE slots AS
            SELECT s.*,
                   t.total_active_balance,
                   t.total_active_balance // {SLOTS_PER_EPOCH} AS slot_reference_balance,
                   {GENESIS_TIME} + s.slot * {SECONDS_PER_SLOT} AS slot_time,
                   b.slot IS NOT NULL AS has_block
            FROM slot_stats s
            JOIN epoch_snapshot es USING (epoch)
            JOIN snapshot_totals t ON t.snap_epoch = es.snap_epoch
            LEFT JOIN blocks b ON b.slot = s.slot
            ORDER BY s.slot
            """
        )
        con.execute(
            """
            CREATE OR REPLACE TABLE epochs AS
            SELECT epoch,
                   sum(assigned_n) AS assigned_n, sum(assigned_bal) AS assigned_bal,
                   sum(offline_n) AS offline_n, sum(offline_bal) AS offline_bal,
                   sum(no_att_n) AS no_att_n, sum(no_att_bal) AS no_att_bal,
                   sum(late_and_wrong_n) AS late_and_wrong_n,
                   sum(late_and_wrong_bal) AS late_and_wrong_bal,
                   sum(target_only_n) AS target_only_n, sum(target_only_bal) AS target_only_bal,
                   sum(source_only_n) AS source_only_n, sum(source_only_bal) AS source_only_bal,
                   sum(both_n) AS both_n, sum(both_bal) AS both_bal,
                   sum(head_n) AS head_n, sum(head_bal) AS head_bal,
                   sum(slashed_n) AS slashed_n,
                   count(*) FILTER (WHERE has_block) AS blocks,
                   any_value(total_active_balance) AS total_active_balance,
                   sum(offline_bal) / sum(assigned_bal) AS offline_share,
                   (sum(target_only_bal) + sum(both_bal)) / sum(assigned_bal) AS target_participation,
                   (sum(source_only_bal) + sum(both_bal)) / sum(assigned_bal) AS source_participation
            FROM slots GROUP BY epoch ORDER BY epoch
            """
        )
        for tbl in ("slots", "epochs", "offline_validators", "epoch_snapshot"):
            con.execute(
                f"COPY {tbl} TO '{os.path.join(out_dir, tbl + '.parquet')}' (FORMAT PARQUET)"
            )
        con.execute(f"COPY epochs TO '{os.path.join(out_dir, 'epochs.csv')}' (HEADER, DELIMITER ',')")
        con.execute(
            f"COPY (SELECT epoch, slot, slot_index, assigned_bal, offline_bal, "
            f"slot_reference_balance FROM slots ORDER BY slot) "
            f"TO '{os.path.join(out_dir, 'slots.csv')}' (HEADER, DELIMITER ',')"
        )
        print(f"wrote slots/epochs/offline_validators to {out_dir}", file=sys.stderr)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data-dir", default="data/xatu")
    ap.add_argument("--out-dir", default="data/derived")
    ap.add_argument("--epoch-lo", type=int, default=411200)
    ap.add_argument("--epoch-hi", type=int, default=411700)
    ap.add_argument("--chunk", type=int, default=20)
    ap.add_argument("--threads", type=int, default=8)
    ap.add_argument("--memory-limit", default="12GB")
    args = ap.parse_args()

    os.makedirs(args.data_dir, exist_ok=True)
    ing = Ingest(
        args.data_dir, args.epoch_lo, args.epoch_hi,
        threads=args.threads, memory_limit=args.memory_limit,
    )
    print(
        f"epochs {args.epoch_lo}-{args.epoch_hi}  "
        f"({epoch_utc(args.epoch_lo):%Y-%m-%d %H:%M}Z -> {epoch_utc(args.epoch_hi + 1):%Y-%m-%d %H:%M}Z)",
        file=sys.stderr,
    )
    ing.run(chunk=args.chunk)
    ing.write(args.out_dir)


if __name__ == "__main__":
    main()
