#!/usr/bin/env bash
# Full historical backtest, from an empty data/ to results/ and figures/.
# ~5 GB of Parquet, ~10 min on a warm connection.
set -euo pipefail

PY=${PY:-.venv/bin/python}
EPOCH_LO=${EPOCH_LO:-411200}
EPOCH_HI=${EPOCH_HI:-411700}

echo "==> fetching the Xatu partitions the ingest needs"
$PY xatu_ingest.py --epoch-lo "$EPOCH_LO" --epoch-hi "$EPOCH_HI" \
    --data-dir data/xatu --out-dir data/derived

echo
echo "==> fetching the hourly partitions the ingest does not fetch itself"
# validator snapshots: effective balances across the range
# gossip: the p2p control and the attributed cut
# mev relay: the execution-layer share of normal income
$PY - <<'EOF'
import xatu_ingest as x, urllib.request, os
for d, h in [("2025-12-03", 1), ("2025-12-03", 2), ("2025-12-04", 2),
             ("2025-12-04", 5), ("2025-12-04", 7), ("2025-12-05", 6)]:
    x.ensure_validator_snapshot("data/xatu", d, h)

for h in range(2, 8):
    p = f"data/xatu/gossipatt_2025-12-4_h{h:02d}.parquet"
    if not os.path.exists(p):
        url = (f"{x.XATU_BASE}/beacon_api_eth_v1_events_attestation/2025/12/4/{h}.parquet")
        print("  downloading", url)
        x._fetch(url, p)

for m, days in ((11, range(20, 31)), (12, range(1, 11))):
    for d in days:
        p = f"data/xatu/mevpayload_2025-{m}-{d}.parquet"
        if not os.path.exists(p):
            x._fetch(f"{x.XATU_BASE}/mev_relay_proposer_payload_delivered/2025/{m}/{d}.parquet", p)
EOF

echo
echo "==> STEP 0: the gating question"
mkdir -p results
$PY step0_report.py | tee results/step0_report.txt

echo
echo "==> validating against the executable spec"
$PY spec_check.py

echo
echo "==> execution-layer share of normal income"
$PY el_bonus.py

echo
echo "==> attributed cut"
$PY attribution.py

echo
echo "==> mechanisms"
# pinned to the initial calibration so the committed results*/ record
# reproduces bit-for-bit; the adopted EIP constants are 765/256 (SEVERITY.md)
$PY eip7716_historical.py --penalty-slope 381 --max-penalty-factor 128 > /dev/null

echo
echo "==> sensitivity"
$PY sensitivity.py

echo
echo "==> tables and figures"
$PY results_table.py > /dev/null
$PY gen_figures_historical.py

echo
echo "done. results/RESULTS.md, results/summary.json, figures/h*.png"
