#!/usr/bin/env bash
# Download the permitted challenge files (public, no login) from Source Cooperative.
# Resumable (curl -C -).
#
#   bash src/download.sh                    # everything the full pipeline needs, ~3 GB
#   bash src/download.sh eastern-ok ...     # only some regions
#   MODE=dialysis bash src/download.sh      # only what the Bias Discovery analysis needs, ~340 MB
#                                           # (places, tract polygons, sample IDs, national strata)
#
# Never downloads the reference layers withdrawn on 2026-09-25 (TIGER, Microsoft footprints,
# HIFLD/USGS, CBP) or any *-coverage-gap* file.
set -u
B=https://data.source.coop/humane-intelligence/bias-bounty-mapping-equity-challenge
D="$(cd "$(dirname "$0")/.." && pwd)/data/raw"
REGIONS=${@:-"northern-ca eastern-ok maricopa-az south-central-tx eastern-wa"}
MODE=${MODE:-full}
get() { mkdir -p "$(dirname "$D/$1")"; for i in 1 2 3 4 5; do curl -s -f -L -C - --retry 5 -o "$D/$1" "$B/$1" && return 0; sleep 3; done; echo "FAILED $1"; }
get README.md
get boundaries/all-aois.geojson
get strata/national/national-strata-tract-table.parquet
for r in $REGIONS; do
  if [ "$MODE" = "dialysis" ]; then
    for f in sample-submission.csv overture-pois.parquet; do get reference/$r/$r-$f; done
    get strata/$r/$r-census-tracts.parquet
    continue
  fi
  get boundaries/$r-tract-geoids.csv
  for f in sample-submission.csv census-acs-housing.parquet overture-pois.parquet overture-infrastructure.parquet overture-roads.parquet overture-buildings.parquet; do get reference/$r/$r-$f; done
  for f in strata-tract-table.parquet census-tracts.parquet tribal-tract-table.parquet usfs-wildfire-tract-table.parquet census-aiannh.parquet; do get strata/$r/$r-$f; done
done
touch "$D/.complete-$MODE"
echo DONE
