"""Re-create the external inputs of the Bias Discovery analysis from their public sources.

You do NOT need to run this to reproduce the results: the derived files are committed in
data/external/ (geocoder output, Nominatim cache, and a 6-state snapshot of the CMS file).
Run it only to audit how those files were made, or to refresh them against a newer CMS release.

  python src/get_external.py cms        # download the full CMS facility listing (7 MB, public domain)
  python src/get_external.py geoin      # rebuild dfc_geocode_in.csv from the CMS file
  python src/get_external.py geocode    # send dfc_geocode_in.csv to the Census batch geocoder

Sources
  CMS Provider Data Catalog, "Dialysis Facility - Listing by Facility", dataset 23ew-n7w9,
    modified 2026-06-16 (released 2026-07-15). https://data.cms.gov/provider-data/dataset/23ew-n7w9
    US Government work, public domain. The analysis used the 2026-06-16 release. CMS announces
    the next update for 2026-10-28; after that `cms` fetches a newer file. The committed snapshot
    keeps results exact.
  US Census Bureau Geocoder, batch endpoint geographies/addressbatch, benchmark Public_AR_Current,
    vintage Current_Current. https://geocoding.geo.census.gov/geocoder/  Public domain.
    Census matches change slowly as the address file is updated, so a fresh run can differ by a
    handful of facilities.
  Facilities the Census geocoder cannot match are geocoded by discovery_dialysis.py with
    OpenStreetMap Nominatim (ODbL 1.0, 1 request/s, usage policy:
    https://operations.osmfoundation.org/policies/nominatim/). Its results are cached in
    data/external/dfc_nominatim_cache.json.
"""
from __future__ import annotations

import json
import sys
import urllib.request
import uuid
from pathlib import Path

import pandas as pd

EXT = Path(__file__).resolve().parents[1] / "data" / "external"
CMS_META = "https://data.cms.gov/provider-data/api/1/metastore/schemas/dataset/items/23ew-n7w9?show-reference-ids=false"
CMS_OUT = EXT / "cms_dfc_facility_2026-06-16.csv"
STATES = ["AZ", "CA", "NM", "OK", "TX", "WA"]  # states that intersect the five challenge regions
GEO_URL = "https://geocoding.geo.census.gov/geocoder/geographies/addressbatch"


def cms() -> None:
    meta = json.load(urllib.request.urlopen(CMS_META, timeout=60))
    url = meta["distribution"][0]["data"]["downloadURL"]
    print("CMS release modified", meta.get("modified"), "->", url)
    if meta.get("modified") != "2026-06-16":
        print("WARNING: newer CMS release than the one analysed; results may differ slightly.")
    EXT.mkdir(parents=True, exist_ok=True)
    urllib.request.urlretrieve(url, CMS_OUT)
    print("wrote", CMS_OUT)


def geoin() -> None:
    src = CMS_OUT if CMS_OUT.exists() else EXT / "cms_dfc_facility_2026-06-16_6states.csv"
    c = pd.read_csv(src, dtype=str)
    s = c[c["State"].isin(STATES)]
    out = pd.DataFrame({"id": s["CMS Certification Number (CCN)"], "street": s["Address Line 1"],
                        "city": s["City/Town"], "state": s["State"], "zip": s["ZIP Code"].str[:5]})
    out.to_csv(EXT / "dfc_geocode_in.csv", index=False, header=False)
    print("wrote", len(out), "addresses to dfc_geocode_in.csv")


def geocode() -> None:
    body_file = (EXT / "dfc_geocode_in.csv").read_bytes()
    b = uuid.uuid4().hex
    parts = []
    for k, v in {"benchmark": "Public_AR_Current", "vintage": "Current_Current"}.items():
        parts.append(f'--{b}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode())
    parts.append(f'--{b}\r\nContent-Disposition: form-data; name="addressFile"; filename="in.csv"\r\n'
                 f"Content-Type: text/csv\r\n\r\n".encode() + body_file + b"\r\n")
    parts.append(f"--{b}--\r\n".encode())
    req = urllib.request.Request(GEO_URL, data=b"".join(parts), method="POST",
                                 headers={"Content-Type": f"multipart/form-data; boundary={b}"})
    res = urllib.request.urlopen(req, timeout=600).read()
    (EXT / "dfc_geocoded.csv").write_bytes(res)
    print("wrote dfc_geocoded.csv,", res.count(b"\n"), "rows")


if __name__ == "__main__":
    steps = sys.argv[1:] or ["cms", "geoin", "geocode"]
    for st in steps:
        {"cms": cms, "geoin": geoin, "geocode": geocode}[st]()
