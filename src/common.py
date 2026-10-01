"""Shared paths and helpers for the Bias Bounty Mapping Equity pipeline.

Only PERMITTED challenge files are read (Overture extracts, ACS housing, strata, boundaries).
The reference layers removed on 2026-09-25 (TIGER roads, Microsoft footprints, HIFLD/USGS
facilities, CBP) and any *-coverage-gap.* file are never read: see `assert_permitted`.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
INTERIM = ROOT / "data" / "interim"
FEAT = ROOT / "data" / "features"
OUT = ROOT / "outputs"
FIG = OUT / "figures"
SUB = OUT / "submissions"
ZINDI = ROOT / "data"  # Zindi downloads (SampleSubmission.csv etc.) land here

# Official Zindi SampleSubmission.csv (9,794 rows) also contains eastern-wa (added 2026-09-08).
CORE_REGIONS = ["eastern-ok", "maricopa-az", "northern-ca", "south-central-tx"]
SCORED_REGIONS = CORE_REGIONS + ["eastern-wa"]
ALL_REGIONS = SCORED_REGIONS
EXPECTED_ROWS = {"eastern-ok": 1192, "maricopa-az": 1593, "northern-ca": 591, "south-central-tx": 6003, "eastern-wa": 415}

NAMED_CLASSES = ("motorway", "trunk", "primary", "secondary")
SCHOOL_CATS = ("elementary_school", "middle_school", "high_school", "school", "private_school", "public_school")

# Files/patterns that must never be read (removed reference layers / published targets).
_FORBIDDEN = re.compile(r"(coverage-gap|tiger|microsoft|msft|hifld|usgs-structures|cbp|county-business)", re.I)


def assert_permitted(path: str | os.PathLike) -> str:
    p = str(path)
    if _FORBIDDEN.search(Path(p).name):
        raise PermissionError(f"Refusing to read non-permitted/target-like file: {p}")
    return p


def ref(region: str, layer: str) -> str:
    return assert_permitted(RAW / "reference" / region / f"{region}-{layer}")


def strata(region: str, table: str) -> str:
    return assert_permitted(RAW / "strata" / region / f"{region}-{table}")


def connect(threads: int | None = None) -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    con.sql("INSTALL spatial; LOAD spatial;")  # INSTALL is a no-op once installed
    if threads:
        con.sql(f"SET threads={threads};")
    con.sql(f"SET temp_directory='{(INTERIM / 'duck_tmp').as_posix()}';")
    return con


# Lon/lat (OGC:CRS84) -> CONUS Albers equal-area metres. always_xy is REQUIRED (see data README).
def to5070(col: str = "geometry") -> str:
    return f"ST_Transform({col}, 'EPSG:4326', 'EPSG:5070', always_xy := true)"


for d in (INTERIM, FEAT, FIG, SUB, INTERIM / "duck_tmp"):
    d.mkdir(parents=True, exist_ok=True)
