#!/usr/bin/env bash
# Reproduce everything. Usage:
#   bash run_all.sh discovery    # Best Bias Discovery only: ~340 MB download, ~2 min
#   bash run_all.sh submission   # leaderboard file from the committed features (seconds; needs data/SampleSubmission.csv)
#   bash run_all.sh all          # full pipeline from raw data: ~3 GB download, ~10 min
# Set PYTHON=/path/to/python to use a specific interpreter (default: python).
set -euo pipefail
cd "$(dirname "$0")"
PY=${PYTHON:-python}
export PYTHONIOENCODING=utf-8
STEP=${1:-all}

need_sample() {
  if [ ! -f data/SampleSubmission.csv ]; then
    echo "Put Zindi's SampleSubmission.csv (Data tab, 9,794 rows) at data/SampleSubmission.csv first." >&2
    exit 1
  fi
}

case "$STEP" in
  discovery)
    [ -f data/raw/.complete-dialysis ] || [ -f data/raw/.complete-full ] || MODE=dialysis bash src/download.sh
    $PY src/discovery_dialysis.py
    $PY src/audit_pediatric_matches.py
    $PY src/fig_dialysis.py
    ;;
  submission)
    need_sample
    $PY src/estimate.py --name structural_v1
    ;;
  all)
    need_sample
    [ -f data/raw/.complete-full ] || bash src/download.sh
    $PY src/features.py
    $PY src/estimate.py --name structural_v1
    $PY src/estimate.py --name v2_gamma08 --gamma 0.8
    $PY src/estimate.py --name v3_shrink05 --shrink 0.5
    $PY src/estimate.py --name v4_no_name_evidence --use_name_evidence false
    $PY src/estimate.py --name v5_transport_only --components t
    $PY src/train.py
    $PY src/bias.py
    $PY src/discovery_dialysis.py
    $PY src/audit_pediatric_matches.py
    $PY src/fig_dialysis.py
    ;;
  *) echo "unknown step: $STEP (discovery | submission | all)" >&2; exit 2 ;;
esac
echo "done: $STEP"
