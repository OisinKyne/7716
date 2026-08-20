#!/usr/bin/env python3
"""Smoke test for window_sweep.py on a small synthetic derived dir.

Builds 300 epochs of schema-identical parquet (baseline 0.3% offline, a 10%
spike at epoch 1200 with an exponential cohort recovery over ~8 hours and a
straggler tail out to 48h), runs the full sweep, and prints the headline
numbers. Purpose: catch schema/SQL/logic crashes before the real ingest lands,
and sanity-check directionality (fast-rise variants should show lower
straggler ratios and worse re-arm).
"""

import os
import shutil

import duckdb
import numpy as np

import events as events_mod
from events import EventSpec
import window_sweep

rng = np.random.default_rng(7716)

OUT = "data/derived_smoke"
E0, E1 = 1000, 1599
EVENT_LO, EVENT_HI = 1200, 1215
SEED_LO, SEED_HI = 1000, 1191
TAIL_HI = 1560
TAB = 35_000_000 * 10**9  # 35M ETH in gwei
N_VALS = 4000             # synthetic cohort, 32 ETH each
EB = 32 * 10**9

shutil.rmtree(OUT, ignore_errors=True)
os.makedirs(OUT, exist_ok=True)

# cohort recovery: half-life 3h for 90%, plus 10% straggling to ~36h
onset_epoch = EVENT_LO
def offline_share(epoch):
    base = 0.003
    if epoch < onset_epoch:
        return base
    h = (epoch - onset_epoch) * 32 * 12 / 3600
    fast = 0.09 * 0.5 ** (h / 3.0)
    slow = 0.01 * 0.5 ** (h / 18.0)
    return base + fast + slow

slots_rows = []
epochs_rows = []
off_rows = []
# assign each synthetic validator a recovery hour: 90% fast, 10% straggler
rec_h = np.where(rng.random(N_VALS) < 0.9,
                 rng.exponential(3.0 / np.log(2), N_VALS),
                 rng.exponential(18.0 / np.log(2), N_VALS))
val_slot = rng.integers(0, 32, N_VALS)  # fixed committee slot per epoch (simplification)

for ep in range(E0, E1 + 1):
    share = offline_share(ep)
    asg_slot = TAB // 32
    ep_off_bal = 0
    for si in range(32):
        noise = 1.0 + rng.normal(0, 0.05)
        ob = int(asg_slot * share * max(0.0, noise))
        ep_off_bal += ob
        slots_rows.append((ep, ep * 32 + si, si, ob, asg_slot, TAB, TAB // 32, True))
    part = 1 - ep_off_bal / TAB
    epochs_rows.append((ep, TAB, ep_off_bal,
                        int(TAB * 0.001), int(TAB * 0.001),
                        int(TAB * part * 0.998), int(TAB * part * 0.95), TAB))
    # per-validator offline rows during/after the event, plus baseline chronic
    if ep >= onset_epoch:
        h = (ep - onset_epoch) * 32 * 12 / 3600
        down = np.nonzero(rec_h > h)[0]
        for v in down:
            off_rows.append((ep, int(val_slot[v]), int(v), EB))
    # 20 chronic validators offline the whole range
    for v in range(N_VALS, N_VALS + 20):
        off_rows.append((ep, int(v % 32), int(v), EB))

con = duckdb.connect()
con.execute("CREATE TABLE slots (epoch UINTEGER, slot UINTEGER, slot_index UTINYINT, "
            "offline_bal HUGEINT, assigned_bal HUGEINT, total_active_balance HUGEINT, "
            "slot_reference_balance HUGEINT, has_block BOOLEAN)")
con.executemany("INSERT INTO slots VALUES (?,?,?,?,?,?,?,?)", slots_rows)
con.execute("CREATE TABLE epochs (epoch UINTEGER, assigned_bal HUGEINT, offline_bal HUGEINT, "
            "source_only_bal HUGEINT, target_only_bal HUGEINT, both_bal HUGEINT, "
            "head_bal HUGEINT, total_active_balance HUGEINT)")
con.executemany("INSERT INTO epochs VALUES (?,?,?,?,?,?,?,?)", epochs_rows)
con.execute("CREATE TABLE offline_validators (epoch UINTEGER, slot_index UTINYINT, "
            "validator UINTEGER, effective_balance UBIGINT)")
con.executemany("INSERT INTO offline_validators VALUES (?,?,?,?)", off_rows)
for t in ("slots", "epochs", "offline_validators"):
    con.execute(f"COPY {t} TO '{OUT}/{t}.parquet' (FORMAT PARQUET)")

events_mod.EVENTS["smoke"] = EventSpec(
    key="smoke", title="synthetic smoke test", subtitle="n/a",
    event_lo=EVENT_LO, event_hi=EVENT_HI, seed_lo=SEED_LO, seed_hi=SEED_HI,
    tail_hi=TAIL_HI, pull_lo=E0, pull_hi=E1,
    derived_dir=OUT, results_dir="results_smoke", fig_prefix="smoke",
    el_bonus=0.08, eth_price=3000.0, total_active_balance_gwei=TAB,
    mev_date_prefixes=(),
)

out = window_sweep.run("smoke", "results_smoke")

print("\n--- headline ---")
for name, r in out["variants"].items():
    ts = r['tail_share_of_scaled_penalties']
    print(f"{name:22s} peak {r['peak_factor']:4d}  dtr {r['mean_days_to_recoup']:.2f}d "
          f"({r['vs_status_quo']:.1f}x)  tail-share {ts if ts is None else round(ts,2)}  "
          f"sustained7d {r['synthetic_sustained_10pct_7d_dtr']:.1f}d  "
          f"rearm+7d {r['rearm']['+7d']['vs_original_onset']:.2f}")
sc = out["straggler_curve"]
print("\n--- straggler mean dtr by recovery bucket (status quo / sym_2^17 / rise_2^12) ---")
for b in ("2-4h", "6-8h", "12-18h", "24-36h", "36-48h"):
    row = []
    for k in ("status_quo", "sym_2^17", "rise_2^12_fall_2^17"):
        v = sc[k].get(b)
        row.append(f"{v['mean_dtr']:.3f}d(n={v['n']})" if v else "--")
    print(f"{b:8s} " + "  ".join(row))
