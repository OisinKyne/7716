#!/usr/bin/env python3
"""
Measure execution-layer proposer income around the event, as a fraction of
consensus-layer issuance.

`days-to-recoup` divides by *normal total* staking income, so the EL share is a
denominator input. It is the one number in the model that cannot be read off the
beacon chain, so it is measured rather than assumed: relay bid values from
`mev_relay_proposer_payload_delivered` are the amount actually paid to the
proposer for every MEV-Boost block.

Two bounds are reported, because locally-built blocks (~9% of slots) have no
relay record:

  lower  relay payments spread over every slot, i.e. locally-built blocks earned
         nothing
  upper  locally-built blocks earned the same per block as relayed ones

The `value` column is a 32-byte little-endian uint256 of wei.
"""

from __future__ import annotations

import argparse
import glob
import math
import os

import duckdb

SLOTS_PER_EPOCH = 32
EPOCHS_PER_DAY = 225
GENESIS_TIME = 1_606_824_023


def measure(data_dir="data/xatu", total_active_balance_gwei=35_632_266_500_000_000,
            block_production_rate=0.993):
    files = sorted(glob.glob(os.path.join(data_dir, "mevpayload_*.parquet")))
    if not files:
        raise SystemExit("no mevpayload_*.parquet in data dir; see README for the fetch")
    con = duckdb.connect(config={"threads": 6})
    lst = ", ".join(repr(f) for f in files)
    df = con.sql(f"SELECT slot, epoch, value FROM read_parquet([{lst}])").df()
    df["wei"] = [int.from_bytes(bytes(v), "little") for v in df.value]
    # one slot can be reported by several relays; the proposer was paid once
    g = df.groupby("slot").wei.max()
    eth = g / 1e18
    span_slots = int(df.slot.max() - df.slot.min() + 1)

    bri = (10**9 * 64) // math.isqrt(total_active_balance_gwei)
    cl_per_epoch_eth = (total_active_balance_gwei // 10**9) * bri / 1e9

    el_lower = float(eth.sum()) / span_slots * SLOTS_PER_EPOCH
    el_upper = float(eth.mean()) * SLOTS_PER_EPOCH * block_production_rate
    staked_eth = total_active_balance_gwei / 1e9
    to_apr = EPOCHS_PER_DAY * 365.25 / staked_eth

    return {
        "n_files": len(files),
        "span_slots": span_slots,
        "span_days": round(span_slots * 12 / 86400, 1),
        "mevboost_blocks": int(len(g)),
        "mevboost_share_of_slots": round(len(g) / span_slots, 4),
        "mean_eth_per_relayed_block": float(eth.mean()),
        "median_eth_per_relayed_block": float(eth.median()),
        "base_reward_per_increment_gwei": bri,
        "cl_issuance_eth_per_epoch": cl_per_epoch_eth,
        "el_eth_per_epoch_lower": el_lower,
        "el_eth_per_epoch_upper": el_upper,
        "el_over_cl_lower": el_lower / cl_per_epoch_eth,
        "el_over_cl_upper": el_upper / cl_per_epoch_eth,
        "el_over_cl_central": (el_lower + el_upper) / 2 / cl_per_epoch_eth,
        "cl_apr": cl_per_epoch_eth * to_apr,
        "total_apr_lower": (cl_per_epoch_eth + el_lower) * to_apr,
        "total_apr_upper": (cl_per_epoch_eth + el_upper) * to_apr,
    }


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data-dir", default="data/xatu")
    args = ap.parse_args()
    out = measure(args.data_dir)
    w = max(len(k) for k in out)
    for k, v in out.items():
        print(f"{k:<{w}}  {v:.6g}" if isinstance(v, float) else f"{k:<{w}}  {v}")
