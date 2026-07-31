#!/usr/bin/env python3
"""
Validate the historical pipeline against the executable spec.

Rather than trusting a hand-rolled transcription, this pulls the Python code
blocks straight out of the spec markdown and executes them:

  specs/_features/eip7716/beacon-chain.md   (consensus-specs PR #5452)
      is_offline_in_previous_epoch
      get_slot_offline_balance
      get_slot_reference_balance
      get_updated_smoothed_offline_balance
      get_slot_penalty_factors
      process_smoothed_offline_balance

  specs/deneb/beacon-chain.md               (upstream, EIP-7045 form)
      get_attestation_participation_flag_indices

They run against a minimal state shim backed by the real committee membership,
effective balances and derived participation flags for a handful of epochs, and
their outputs are compared with:

  * `offline_bal` from `xatu_ingest.py`      -> validates the flag derivation
  * `revised_factors` from `eip7716_historical.py` -> validates the recursion

Exit status is non-zero if anything disagrees.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import urllib.request

import duckdb
import numpy as np

from eip7716_historical import (
    MAX_PENALTY_FACTOR,
    OFFLINE_BALANCE_SMOOTHING_FACTOR,
    PENALTY_SLOPE,
    revised_factors,
)
from xatu_ingest import SLOTS_PER_EPOCH, TIMELY_SOURCE_MAX_DELAY, USER_AGENT

SPEC_7716 = (
    "https://raw.githubusercontent.com/OisinKyne/consensus-specs/"
    "eip7716-anti-correlation-penalties/specs/_features/eip7716/beacon-chain.md"
)
SPEC_DENEB = (
    "https://raw.githubusercontent.com/OisinKyne/consensus-specs/"
    "eip7716-anti-correlation-penalties/specs/deneb/beacon-chain.md"
)

TIMELY_SOURCE_FLAG_INDEX = 0
TIMELY_TARGET_FLAG_INDEX = 1
TIMELY_HEAD_FLAG_INDEX = 2


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req) as resp:
        return resp.read().decode()


def extract(md: str, name: str) -> str:
    """Pull the ```python block that defines `name` out of a spec markdown file."""
    for block in re.findall(r"```python\n(.*?)```", md, re.S):
        if re.match(rf"\s*def {re.escape(name)}\b", block):
            return block
    raise SystemExit(f"could not find `def {name}` in spec")


# ---------------------------------------------------------------- shim
class Validator:
    __slots__ = ("effective_balance", "slashed")

    def __init__(self, effective_balance, slashed):
        self.effective_balance = effective_balance
        self.slashed = slashed


class Checkpoint:
    __slots__ = ("epoch", "root")

    def __init__(self, epoch, root):
        self.epoch, self.root = epoch, root

    def __eq__(self, other):
        return self.epoch == other.epoch and self.root == other.root


class AttestationData:
    __slots__ = ("slot", "index", "beacon_block_root", "source", "target")

    def __init__(self, slot, beacon_block_root, source, target):
        self.slot = slot
        self.beacon_block_root = beacon_block_root
        self.source = source
        self.target = target


class State:
    """Just enough BeaconState for the spec functions under test."""

    def __init__(self, epoch, committees, validators, participation, total_active,
                 smoothed_offline_balance, block_roots=None,
                 current_justified=None, previous_justified=None):
        self._epoch = epoch                    # the *current* epoch; duties are previous
        self.committees = committees           # {slot: {committee_index: [validator]}}
        self.validators = validators           # {index: Validator}
        self.previous_epoch_participation = participation  # {index: flag bitfield}
        self._total_active = total_active
        self.smoothed_offline_balance = smoothed_offline_balance
        self.block_roots = block_roots or {}
        self.current_justified_checkpoint = current_justified
        self.previous_justified_checkpoint = previous_justified


def build_namespace(state_cls):
    """Globals the extracted spec functions close over."""
    ns = {
        "Gwei": int,
        "Uint64": int,
        "Slot": int,
        "Epoch": int,
        "Root": bytes,
        "ValidatorIndex": int,
        "CommitteeIndex": int,
        "BeaconState": state_cls,
        "AttestationData": AttestationData,
        "Sequence": list,
        "Tuple": tuple,
        "SLOTS_PER_EPOCH": SLOTS_PER_EPOCH,
        "MAX_PENALTY_FACTOR": MAX_PENALTY_FACTOR,
        "PENALTY_SLOPE": PENALTY_SLOPE,
        "OFFLINE_BALANCE_SMOOTHING_FACTOR": OFFLINE_BALANCE_SMOOTHING_FACTOR,
        "TIMELY_SOURCE_FLAG_INDEX": TIMELY_SOURCE_FLAG_INDEX,
        "TIMELY_TARGET_FLAG_INDEX": TIMELY_TARGET_FLAG_INDEX,
        "TIMELY_HEAD_FLAG_INDEX": TIMELY_HEAD_FLAG_INDEX,
        "MIN_ATTESTATION_INCLUSION_DELAY": 1,
        "has_flag": lambda flags, idx: bool(flags & (1 << idx)),
        "integer_squareroot": lambda n: int(np.isqrt(n)) if hasattr(np, "isqrt") else int(n**0.5),
        "compute_epoch_at_slot": lambda slot: slot // SLOTS_PER_EPOCH,
        "compute_start_slot_at_epoch": lambda epoch: epoch * SLOTS_PER_EPOCH,
        "get_previous_epoch": lambda state: state._epoch - 1,
        "get_current_epoch": lambda state: state._epoch,
        "get_total_active_balance": lambda state: state._total_active,
        "get_committee_count_per_slot": lambda state, epoch: len(
            next(iter(state.committees.values()))
        ),
        "get_beacon_committee": lambda state, slot, ci: state.committees[slot][ci],
        "get_block_root": lambda state, epoch: state.block_roots[epoch * SLOTS_PER_EPOCH],
        "get_block_root_at_slot": lambda state, slot: state.block_roots[slot],
    }
    ns["integer_squareroot"] = lambda n: int(n**0.5)
    return ns


def load_spec_functions(verbose=True):
    md7716 = fetch(SPEC_7716)
    mddeneb = fetch(SPEC_DENEB)
    names_7716 = [
        "is_offline_in_previous_epoch",
        "get_slot_offline_balance",
        "get_slot_reference_balance",
        "get_updated_smoothed_offline_balance",
        "get_slot_penalty_factors",
        "process_smoothed_offline_balance",
    ]
    ns = build_namespace(State)
    for name in names_7716:
        src = extract(md7716, name)
        exec(compile(src, f"<spec:{name}>", "exec"), ns)
        if verbose:
            print(f"  loaded {name} from eip7716/beacon-chain.md", file=sys.stderr)
    src = extract(mddeneb, "get_attestation_participation_flag_indices")
    exec(compile(src, "<spec:flags>", "exec"), ns)
    ns["_flag_src"] = src
    if verbose:
        print("  loaded get_attestation_participation_flag_indices from deneb/beacon-chain.md",
              file=sys.stderr)
    return ns


# ---------------------------------------------------------------- fixtures
def build_epoch_state(con, epoch, data_dir, derived_dir, smoothed, snap_epoch, snap_file):
    """Real committees + effective balances + derived flags for one epoch."""
    day = "2025-12-4"
    committee_src = f"read_parquet('{data_dir}/committee_{day}.parquet')"
    att_src = f"read_parquet('{data_dir}/attestation_{day}.parquet')"
    block_src = f"read_parquet('{data_dir}/block_{day}.parquet')"
    val_src = f"read_parquet('{snap_file}')"

    lo, hi = epoch * SLOTS_PER_EPOCH, epoch * SLOTS_PER_EPOCH + SLOTS_PER_EPOCH - 1
    target_root = con.sql(
        f"SELECT block_root FROM {block_src} WHERE slot <= {lo} ORDER BY slot DESC LIMIT 1"
    ).fetchone()[0]

    comm = con.sql(
        f"SELECT slot, committee_index::VARCHAR AS ci, validators FROM {committee_src} "
        f"WHERE epoch = {epoch}"
    ).df()
    committees: dict[int, dict[int, list[int]]] = {}
    for row in comm.itertuples():
        committees.setdefault(int(row.slot), {})[int(row.ci)] = list(row.validators)

    flags_df = con.sql(
        f"""
        WITH att AS (
            SELECT UNNEST(validators) AS v, block_slot - slot AS delay,
                   target_root = ? AS target_ok
            FROM {att_src} WHERE epoch = {epoch} AND slot BETWEEN {lo} AND {hi}
        )
        SELECT v, bool_or(delay <= {TIMELY_SOURCE_MAX_DELAY}) AS ts, bool_or(target_ok) AS tt
        FROM att GROUP BY v
        """,
        params=[target_root],
    ).df()

    participation: dict[int, int] = {}
    for v, ts, tt in zip(flags_df.v.to_numpy(), flags_df.ts.to_numpy(), flags_df.tt.to_numpy()):
        participation[int(v)] = (int(bool(ts)) << TIMELY_SOURCE_FLAG_INDEX) | (
            int(bool(tt)) << TIMELY_TARGET_FLAG_INDEX
        )

    assigned = sorted({v for cs in committees.values() for c in cs.values() for v in c})
    snap = con.sql(
        f"SELECT index, effective_balance, slashed FROM {val_src} WHERE epoch = {snap_epoch}"
    ).df()
    ebs = dict(zip(snap["index"].to_numpy().tolist(), snap.effective_balance.to_numpy().tolist()))
    sl = dict(zip(snap["index"].to_numpy().tolist(), snap.slashed.to_numpy().tolist()))
    validators = {
        v: Validator(int(ebs.get(v, 32_000_000_000)), bool(sl.get(v, False))) for v in assigned
    }
    for v in assigned:
        participation.setdefault(v, 0)

    total_active = con.sql(
        f"""SELECT sum(effective_balance) FROM {val_src} WHERE epoch = {snap_epoch}
            AND status::VARCHAR IN ('active_ongoing','active_exiting','active_slashed')"""
    ).fetchone()[0]

    return State(
        epoch=epoch + 1,  # duties under test are the *previous* epoch
        committees=committees,
        validators=validators,
        participation=participation,
        total_active=int(total_active),
        smoothed_offline_balance=int(smoothed),
    )


# ---------------------------------------------------------------- checks
def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data-dir", default="data/xatu")
    ap.add_argument("--derived-dir", default="data/derived")
    ap.add_argument("--epochs", type=int, nargs="+", default=[411441, 411450, 411465, 411480])
    args = ap.parse_args()

    print("loading spec functions from consensus-specs...", file=sys.stderr)
    ns = load_spec_functions()

    con = duckdb.connect(config={"threads": 8, "memory_limit": "8GB"})
    slots = con.sql(
        f"SELECT slot, epoch, slot_index, offline_bal, total_active_balance, "
        f"slot_reference_balance FROM read_parquet('{args.derived_dir}/slots.parquet') ORDER BY slot"
    ).df()

    # bind each epoch to the same validator snapshot the pipeline used, so the
    # comparison isolates logic rather than effective-balance vintage
    snap_map = dict(
        con.sql(
            f"SELECT epoch, snap_epoch FROM read_parquet('{args.derived_dir}/epoch_snapshot.parquet')"
        ).fetchall()
    )
    snap_files = {}
    for f in sorted(os.listdir(args.data_dir)):
        if f.startswith("validators_") and f.endswith(".parquet"):
            path = os.path.join(args.data_dir, f)
            for (e,) in con.sql(f"SELECT DISTINCT epoch FROM read_parquet('{path}')").fetchall():
                snap_files[int(e)] = path

    ok = True
    print("\n=== 1. get_slot_offline_balance vs the SQL flag derivation ===")
    print(f"{'epoch':>8} {'slots':>6} {'max abs diff (gwei)':>22} {'match':>7}")
    states = {}
    for epoch in args.epochs:
        ours = slots[slots.epoch == epoch].sort_values("slot")
        snap = int(snap_map[epoch])
        st = build_epoch_state(con, epoch, args.data_dir, args.derived_dir, 0,
                               snap, snap_files[snap])
        states[epoch] = st
        spec_vals = [
            ns["get_slot_offline_balance"](st, int(s)) for s in ours.slot.to_numpy()
        ]
        diff = np.abs(np.array(spec_vals, dtype=np.int64) - ours.offline_bal.to_numpy(dtype=np.int64))
        good = bool(diff.max() == 0)
        ok &= good
        print(f"{epoch:>8} {len(ours):>6} {int(diff.max()):>22} {'OK' if good else 'MISMATCH':>7}")

    print("\n=== 2. get_slot_penalty_factors vs revised_factors() ===")
    print(f"{'epoch':>8} {'seed EMA (gwei)':>18} {'max abs diff':>14} {'match':>7}")
    for epoch in args.epochs:
        ours = slots[slots.epoch == epoch].sort_values("slot")
        # seed both with the same moving average: the mean baseline offline balance
        seed = int(slots[slots.epoch.between(411200, 411391)].offline_bal.mean())
        st = states[epoch]
        st.smoothed_offline_balance = seed
        spec_factors = ns["get_slot_penalty_factors"](st)
        # the spec normalises by get_total_active_balance from the same state, so
        # align the reference balance explicitly
        ref = ns["get_slot_reference_balance"](st)
        mine_ref, _ = revised_factors(
            ours.offline_bal.to_numpy(dtype=np.int64),
            np.full(len(ours), ref, dtype=np.int64),
            seed,
        )
        diff = np.abs(np.array(spec_factors, dtype=np.int64) - mine_ref)
        good = bool(diff.max() == 0)
        ok &= good
        print(f"{epoch:>8} {seed:>18} {int(diff.max()):>14} {'OK' if good else 'MISMATCH':>7}")

    print("\n=== 3. process_smoothed_offline_balance vs the EMA carried by revised_factors() ===")
    for epoch in args.epochs[:1]:
        ours = slots[slots.epoch == epoch].sort_values("slot")
        seed = int(slots[slots.epoch.between(411200, 411391)].offline_bal.mean())
        st = states[epoch]
        st.smoothed_offline_balance = seed
        ns["process_smoothed_offline_balance"](st)
        _, emas = revised_factors(
            ours.offline_bal.to_numpy(dtype=np.int64),
            ours.slot_reference_balance.to_numpy(dtype=np.int64),
            seed,
        )
        # revised_factors records the EMA *before* each slot's update; replay the
        # final update to land on the persisted value
        ob = int(ours.offline_bal.to_numpy()[-1])
        e = int(emas[-1])
        e = (e + (ob - e) // OFFLINE_BALANCE_SMOOTHING_FACTOR) if ob > e else (
            e - (e - ob) // OFFLINE_BALANCE_SMOOTHING_FACTOR
        )
        good = st.smoothed_offline_balance == e
        ok &= good
        print(f"epoch {epoch}: spec {st.smoothed_offline_balance} vs ours {e} "
              f"-> {'OK' if good else 'MISMATCH'}")

    print("\n=== 4. get_attestation_participation_flag_indices vs the SQL flag rules ===")
    ok &= check_flag_rules(ns)

    print("\nRESULT:", "all checks passed" if ok else "FAILURES PRESENT")
    return 0 if ok else 1


def check_flag_rules(ns):
    """Drive the Deneb spec function over the flag-relevant case grid."""
    justified = Checkpoint(10, b"J")
    canonical_target = b"T"
    canonical_head = b"H"

    class FlagState:
        _epoch = 11
        current_justified_checkpoint = justified
        previous_justified_checkpoint = justified
        block_roots = {11 * SLOTS_PER_EPOCH: canonical_target, 11 * SLOTS_PER_EPOCH + 3: canonical_head}

    ns2 = dict(ns)
    ns2["get_block_root"] = lambda state, epoch: canonical_target
    ns2["get_block_root_at_slot"] = lambda state, slot: canonical_head
    ns2["get_current_epoch"] = lambda state: 11
    ns2["get_previous_epoch"] = lambda state: 10
    fn_src = ns["_flag_src"]
    exec(compile(fn_src, "<spec:flags2>", "exec"), ns2)
    fn = ns2["get_attestation_participation_flag_indices"]

    slot = 11 * SLOTS_PER_EPOCH + 3
    cases = []
    for delay in (1, 2, 5, 6, 12, 33, 63):
        for target_ok in (True, False):
            for head_ok in (True, False):
                data = AttestationData(
                    slot=slot,
                    beacon_block_root=canonical_head if head_ok else b"X",
                    source=justified,
                    target=Checkpoint(11, canonical_target if target_ok else b"Z"),
                )
                got = set(fn(FlagState(), data, delay))
                # what xatu_ingest.py's SQL asserts
                want = set()
                if delay <= TIMELY_SOURCE_MAX_DELAY:
                    want.add(TIMELY_SOURCE_FLAG_INDEX)
                if target_ok:
                    want.add(TIMELY_TARGET_FLAG_INDEX)
                if target_ok and head_ok and delay == 1:
                    want.add(TIMELY_HEAD_FLAG_INDEX)
                cases.append((delay, target_ok, head_ok, got, want))

    bad = [c for c in cases if c[3] != c[4]]
    print(f"  {len(cases)} (delay x target x head) cases, {len(bad)} mismatches")
    for delay, t, h, got, want in bad[:8]:
        print(f"    delay={delay} target_ok={t} head_ok={h}: spec {sorted(got)} vs ours {sorted(want)}")
    return not bad


if __name__ == "__main__":
    sys.exit(main())
