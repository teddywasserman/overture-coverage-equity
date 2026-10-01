# overture-coverage-equity

Code and small derived data for an entry to the Zindi **Bias Bounty Mapping Equity Challenge**
(Humane Intelligence, 2026). The repository does two things:

1. **Leaderboard estimate.** A label-free estimate of the tract-level `coverage_gap_score` for all
   9,794 scored census tracts, built only from the challenge's own Overture, ACS and strata files.
2. **Bias Discovery: "Children on dialysis are invisible on the open map".** We compared every
   CMS-certified dialysis facility in the scored tracts with Overture places. Pediatric units are
   missing from a `dialysis_clinic` category query far more often than adult units: 8 of 12
   versus 127 of 851, odds ratio 11.4, Fisher p = 8.4e-5. Under a stricter test, only 1 of the 12
   is findable as a pediatric clinic. Houston and Dallas-Fort Worth have no pediatric unit that the
   query returns. The nearest one it returns is in Austin, 232 km from Houston and 273-290 km from
   Dallas-Fort Worth.

Write-ups: see the Zindi discussion threads "Best Bias Discovery: …" and "Best Documentation: …".

## Compliance statement

* **The scored submission** (`outputs/submissions/structural_v1.csv`) uses only challenge files that
  remained published after 2026-09-25: Overture extracts, ACS housing, strata tables and tract
  boundaries. It never reads TIGER/Line roads, Microsoft Building Footprints, HIFLD/USGS
  facilities, County Business Patterns, any `*-coverage-gap*` file, or other copies of them.
  `src/common.py::assert_permitted` refuses those file names, and `src/download.sh` never fetches
  them. The estimator uses Overture's own attributes, mainly road `routes` and place names and
  categories. We have asked the organisers to confirm this is in scope.
* **The Bias Discovery analysis** uses only Overture's own attributes (place names, categories,
  phone numbers) from the challenge files, plus openly licensed external data, which the rules
  allow for this prize: the CMS dialysis facility listing, the US Census Bureau geocoder, and
  OpenStreetMap Nominatim as a fallback geocoder. **It uses none of the withdrawn reference
  layers.** It does not estimate or calibrate any score.
* No supervised training on labels. No labels were ever published. A fixed seed (`SEED` in `src/train.py`)
  makes `train.py` deterministic.

## Reproduce

Tested on Windows 11 with Python 3.13 on CPU. The commands work in any bash, including Git Bash.

```bash
python -m venv .venv
source .venv/bin/activate          # Windows Git Bash: source .venv/Scripts/activate
pip install -r requirements.txt    # pinned versions; see note below
```

| goal | command | download | time |
|---|---|---|---|
| Bias Discovery tables and figures | `bash run_all.sh discovery` | ~340 MB | ~2 min |
| Leaderboard file from committed features | `bash run_all.sh submission` | none (needs `data/SampleSubmission.csv`) | seconds |
| Everything from raw data | `bash run_all.sh all` | ~3 GB | ~10 min |

`data/SampleSubmission.csv` comes from the competition's Zindi Data tab. It is not redistributed here.

**Discovery step by step** (what `run_all.sh discovery` runs):

```bash
MODE=dialysis bash src/download.sh       # Overture places, tract polygons, sample IDs, national strata
python src/discovery_dialysis.py         # -> outputs/dialysis_summary.md, dialysis_facilities.csv, dialysis_pediatric_units.csv
python src/audit_pediatric_matches.py    # -> outputs/pediatric_match_audit.csv (strict pediatric test)
python src/fig_dialysis.py               # -> outputs/figures/dialysis_unseen_rates.png, dialysis_pediatric_texas.png
```

The external inputs are committed in `data/external/`, so the discovery step makes **no calls**
to CMS, Census or Nominatim. `src/get_external.py` documents and re-runs how they were made:
it downloads CMS, rebuilds the geocoder input, and calls the Census batch geocoder.

A clean run on these committed files reproduced the committed outputs byte-for-byte:
`structural_v1.csv`, `dialysis_facilities.csv` and `dialysis_pediatric_units.csv`.

*Note:* pins such as duckdb 1.4.1, pandas 2.3.3 and pyarrow 21.0.0 are deliberate.
Newer wheels were blocked by Windows Smart App Control on the development machine.
DuckDB installs its `spatial` extension on first use, which needs internet access once.

## Layout

```
run_all.sh                       one-command reproduction (discovery | submission | all)
src/common.py                    paths, permitted-file guard, CRS helper
src/download.sh                  public challenge data from Source Cooperative (resumable)
src/features.py                  per-tract features from Overture roads/buildings/places/infra + ACS
src/estimate.py                  label-free estimator + submission writer (exact Zindi columns)
src/train.py                     spatial GroupKFold CV pipeline (proxy target; real labels if ever published)
src/bias.py                      coverage indicators by stratum, regressions, maps
src/discovery_dialysis.py        Bias Discovery: CMS dialysis facilities vs Overture places
src/audit_pediatric_matches.py   strict check of the 12 pediatric matches
src/fig_dialysis.py              discovery figures
src/get_external.py              how data/external/ was produced (CMS download, Census geocoder)
data/external/                   CMS snapshot (6 states), geocoder output, Nominatim cache
data/features/                   per-tract features (2.4 MB), so the estimator runs without the 3 GB download
outputs/                         results committed for inspection (regenerated by run_all.sh)
```

## Data sources and licences

| source | used for | licence | URL | retrieved |
|---|---|---|---|---|
| Challenge bundle (Overture 2026-08-19.0 extracts, ACS housing, strata, tracts) | everything | CC BY-SA 4.0 (challenge), with the upstream licences below | https://source.coop/humane-intelligence/bias-bounty-mapping-equity-challenge | 2026-10-02 |
| Overture Maps places | estimator, discovery | CDLA-Permissive-2.0 | https://overturemaps.org | via bundle |
| Overture Maps transportation, buildings | estimator | ODbL 1.0 | https://overturemaps.org | via bundle |
| CMS *Dialysis Facility – Listing by Facility* (dataset 23ew-n7w9, modified 2026-06-16) | discovery | US Government work, public domain | https://data.cms.gov/provider-data/dataset/23ew-n7w9 | 2026-10-02 |
| US Census Bureau Geocoder, batch `geographies/addressbatch`, Public_AR_Current / Current_Current | discovery (795 of 863 facilities) | public domain | https://geocoding.geo.census.gov/geocoder/ | 2026-10-02 |
| OpenStreetMap Nominatim (fallback geocoder) | discovery (68 of 863 facilities, none pediatric) | ODbL 1.0, © OpenStreetMap contributors | https://nominatim.openstreetmap.org | 2026-10-02 |

`data/external/cms_dfc_facility_2026-06-16_6states.csv` is an unmodified row subset of the CMS
file, covering AZ, CA, NM, OK, TX and WA. It is kept because CMS refreshes the listing; the next
update is announced for 2026-10-28.

## Licence

Code: MIT (see `LICENSE`). Derived data keeps the licence of its source. Files derived from
Overture and the challenge bundle are under ODbL / CDLA-Permissive-2.0 / CC BY-SA 4.0. Files
derived from Nominatim coordinates are under ODbL. Files derived only from CMS or Census data are
public domain.
