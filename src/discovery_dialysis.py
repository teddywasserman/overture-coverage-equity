"""Best Bias Discovery: are life-sustaining dialysis clinics on the open map?

External public-domain sources (documented in REPORT.md):
  * CMS Provider Data Catalog, "Dialysis Facility - Listing by Facility" (dataset 23ew-n7w9,
    modified 2026-06-16), https://data.cms.gov/provider-data/dataset/23ew-n7w9  (US Gov work)
  * US Census Bureau Geocoder, batch endpoint, benchmark Public_AR_Current / vintage Current_Current
    https://geocoding.geo.census.gov/geocoder/  (US Gov service)
  * Fallback for addresses the Census geocoder cannot match: OpenStreetMap Nominatim (ODbL), 1 req/s.
    Results are cached in data/external/dfc_nominatim_cache.json (committed), so a re-run makes no
    network calls.
Challenge data: Overture places (2026-08-19.0), tract polygons and strata tables.

Steps: geocode each CMS facility -> keep those inside a scored tract -> match to Overture places by
(a) identical 10-digit phone anywhere in the region, or (b) a place within 250 m whose name or
category says dialysis/kidney/renal/nephrology or the operator brand. Outcome per facility:
  mapped_dialysis   matched place carries category dialysis_clinic
  mapped_other_cat  matched (phone/name) but filed under another category (invisible to a
                    category query such as "dialysis_clinic near me")
  missing           no match at all
Outputs: outputs/dialysis_facilities.csv, outputs/dialysis_summary.md, figures.
"""
from __future__ import annotations

import json
import re
import time
import urllib.parse
import urllib.request

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from scipy import stats

from common import FIG, OUT, RAW, ROOT, CORE_REGIONS as _CR, SCORED_REGIONS, connect, ref, strata, to5070

EXT = ROOT / "data" / "external"
# Full national file (src/get_external.py downloads it) or, if absent, the committed snapshot of the
# 1,857 rows in the six geocoded states (AZ, CA, NM, OK, TX, WA). Both give identical results.
CMS = EXT / "cms_dfc_facility_2026-06-16.csv"
if not CMS.exists():
    CMS = EXT / "cms_dfc_facility_2026-06-16_6states.csv"
GEO = EXT / "dfc_geocoded.csv"
NOMI_CACHE = EXT / "dfc_nominatim_cache.json"
DIAL_RE = re.compile(r"dialysis|kidney|renal|nephro|davita|fresenius|\bdci\b|satellite health|american renal|u\.?s\.? renal|innovative renal", re.I)


def phone10(x) -> str | None:
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return None
    d = re.sub(r"\D", "", str(x))
    return d[-10:] if len(d) >= 10 else None


def load_facilities() -> pd.DataFrame:
    cms = pd.read_csv(CMS, dtype=str)
    cms = cms.rename(columns={"CMS Certification Number (CCN)": "ccn"})
    g = pd.read_csv(GEO, header=None, dtype=str,
                    names=["ccn", "addr_in", "match", "match_type", "addr_out", "lonlat", "tiger_id", "side",
                           "st", "co", "tract", "block"])
    g[["lon", "lat"]] = g["lonlat"].str.split(",", expand=True).astype(float)
    g["GEOID_geocoder"] = g["st"] + g["co"] + g["tract"]
    df = cms.merge(g[["ccn", "match", "lon", "lat", "GEOID_geocoder"]], on="ccn", how="inner")  # 6 states geocoded
    df["geocoder"] = np.where(df["match"].eq("Match"), "census", None)

    # Nominatim fallback (cached) for Census no-matches
    cache = json.loads(NOMI_CACHE.read_text()) if NOMI_CACHE.exists() else {}
    todo = df[df["geocoder"].isna()]
    for _, r in todo.iterrows():
        if r["ccn"] in cache:
            continue
        q = {"street": r["Address Line 1"], "city": r["City/Town"], "state": r["State"],
             "postalcode": str(r["ZIP Code"])[:5], "country": "us", "format": "json", "limit": 1}
        url = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode(q)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "zindi-bias-bounty-research/1.0"})
            res = json.load(urllib.request.urlopen(req, timeout=15))
        except Exception as e:  # noqa: BLE001
            res = []
        cache[r["ccn"]] = res[0] if res else None
        NOMI_CACHE.write_text(json.dumps(cache))
        print("nominatim", len(cache), r["ccn"], bool(res), flush=True)
        time.sleep(1.1)
    NOMI_CACHE.write_text(json.dumps(cache))
    for i, r in df[df["geocoder"].isna()].iterrows():
        hit = cache.get(r["ccn"])
        if hit:
            df.loc[i, ["lon", "lat"]] = [float(hit["lon"]), float(hit["lat"])]
            df.loc[i, "geocoder"] = "nominatim"
    df["phone10"] = df["Telephone Number"].map(phone10)
    return df


def assign_tracts(df: pd.DataFrame, con) -> pd.DataFrame:
    pts = df.dropna(subset=["lon"])[["ccn", "lon", "lat"]]
    con.register("pts", pts)
    parts = []
    for r in SCORED_REGIONS:
        parts.append(con.sql(f"""
            SELECT p.ccn, t.GEOID, '{r}' AS region
            FROM pts p JOIN '{strata(r, 'census-tracts.parquet')}' t
              ON ST_Intersects(ST_Point(p.lon, p.lat), t.geometry)
            WHERE t.GEOID IN (SELECT GEOID FROM read_csv('{ref(r, 'sample-submission.csv')}', types={{'GEOID':'VARCHAR'}}))
        """).df())
    tr = pd.concat(parts).drop_duplicates("ccn")
    return df.merge(tr, on="ccn", how="inner")


def match_overture(fac: pd.DataFrame, con) -> pd.DataFrame:
    out = []
    for r in SCORED_REGIONS:
        f = fac[fac.region == r]
        if f.empty:
            continue
        pois = con.sql(f"""
            SELECT id, names."primary" AS name, categories."primary" AS cat,
                   coalesce(categories.alternate, []) AS alt,
                   list_filter([right(regexp_replace(x, '[^0-9]', '', 'g'), 10) for x in coalesce(phones, [])], y -> length(y) = 10) AS phone10s,
                   ST_X(geometry) lon, ST_Y(geometry) lat, confidence
            FROM '{ref(r, 'overture-pois.parquet')}'
        """).df()
        pois["is_dial_cat"] = pois["cat"].eq("dialysis_clinic") | pois["alt"].map(lambda a: "dialysis_clinic" in list(a))
        pois["is_dial_name"] = pois["name"].fillna("").str.contains(DIAL_RE)
        ph = pois.explode("phone10s").dropna(subset=["phone10s"])
        ph_idx = ph.groupby("phone10s").apply(lambda g: list(g.index)).to_dict()
        print("matching", r, len(f), "facilities vs", len(pois), "places", flush=True)
        # metric coords for distance (local equirectangular is fine at <1 km)
        lat0 = np.deg2rad(f["lat"].mean())
        px, py = np.deg2rad(pois["lon"].values) * 6371000 * np.cos(lat0), np.deg2rad(pois["lat"].values) * 6371000
        dial_mask = (pois["is_dial_cat"] | pois["is_dial_name"]).values
        for _, x in f.iterrows():
            fx, fy = np.deg2rad(x["lon"]) * 6371000 * np.cos(lat0), np.deg2rad(x["lat"]) * 6371000
            d = np.hypot(px - fx, py - fy)
            phone_hit = pd.Index(ph_idx.get(x["phone10"], [])) if x["phone10"] else pd.Index([])
            near_dial = np.where((d <= 250) & dial_mask)[0]
            cand_idx = list(dict.fromkeys(list(phone_hit) + list(pois.index[near_dial])))
            nearest_dial_cat_km = float(d[pois["is_dial_cat"].values].min() / 1000) if pois["is_dial_cat"].any() else np.nan
            rec = {"ccn": x["ccn"], "n_phone_matches": len(phone_hit), "n_near_dial": len(near_dial),
                   "nearest_dialysis_clinic_km": nearest_dial_cat_km}
            if cand_idx:
                c = pois.loc[cand_idx]
                rec["status"] = "mapped_dialysis" if c["is_dial_cat"].any() else "mapped_other_cat"
                rec["matched_cat"] = ";".join(sorted(set(c["cat"].fillna("None"))))
                rec["match_dist_m"] = float(d[[pois.index.get_loc(i) for i in cand_idx]].min())
                # distance to nearest *other* correctly-categorised clinic (what a category search returns)
                other = pois["is_dial_cat"].values.copy()
                other[[pois.index.get_loc(i) for i in cand_idx]] = False
                rec["next_mapped_dialysis_km"] = float(d[other].min() / 1000) if other.any() else np.nan
            else:
                rec["status"] = "missing"
                rec["matched_cat"] = None
                rec["match_dist_m"] = np.nan
                rec["next_mapped_dialysis_km"] = nearest_dial_cat_km
            out.append(rec)
    return fac.merge(pd.DataFrame(out), on="ccn")


def analyse(fac: pd.DataFrame) -> str:
    st = pd.read_parquet(RAW / "strata" / "national" / "national-strata-tract-table.parquet",
                         columns=["GEOID", "ruca_primary", "svi_overall", "svi_minority", "svi_socioeconomic",
                                  "tribal_any", "cvi_overall", "pop_total", "ur_class", "epht_heat_days_summer",
                                  "usfs_RPS_mean", "aiannh_name"])
    df = fac.merge(st, on="GEOID", how="left")
    df = df[~df["Facility Name"].str.lower().str.startswith("zz_closed")].copy()  # CMS marks closed units
    nm = df["Facility Name"].str.lower()
    df["pediatric"] = nm.str.contains(r"child|pediatric|driscoll|cook children").astype(int)
    df["hospital_based"] = nm.str.contains(r"hospital|medical center|health center|health system|university|valleywise|memorial|methodist|baptist|st[.]? |saint").astype(int)
    df["unseen"] = (df["status"] != "mapped_dialysis").astype(int)  # invisible to a category search
    df["missing"] = (df["status"] == "missing").astype(int)
    df["rural"] = (pd.to_numeric(df["ruca_primary"], errors="coerce") >= 4).astype(int)
    df["svi_q"] = pd.qcut(df["svi_overall"].rank(method="first"), 4, labels=["Q1 (least)", "Q2", "Q3", "Q4 (most)"])
    df["chain"] = df["Chain Owned"].eq("Yes").astype(int)
    df["nonprofit"] = df["Profit or Non-Profit"].eq("Non-profit").astype(int)
    df["stations"] = pd.to_numeric(df["# of Dialysis Stations"], errors="coerce")
    df["tribal"] = df["tribal_any"].fillna(False).astype(bool).astype(int)
    df.to_csv(OUT / "dialysis_facilities.csv", index=False)

    lines = ["# Dialysis-clinic visibility in Overture (scored tracts, 5 regions)\n"]
    lines.append(f"Facilities inside scored tracts: {len(df)}  (geocoder: {df.geocoder.value_counts().to_dict()})\n")
    lines.append("## Status overall\n" + df["status"].value_counts().to_frame().to_markdown() + "\n")
    for g in ["region", "rural", "svi_q", "tribal", "chain", "nonprofit", "hospital_based", "pediatric", "geocoder"]:
        t = df.groupby(g, observed=True).agg(n=("ccn", "size"), unseen_rate=("unseen", "mean"),
                                             missing_rate=("missing", "mean"), stations=("stations", "sum"))
        lines.append(f"## By {g}\n" + t.round(3).to_markdown() + "\n")
    # tests
    tests = []
    for g in ["rural", "tribal", "chain", "nonprofit", "hospital_based", "pediatric"]:
        ct = pd.crosstab(df[g], df["unseen"])
        if ct.shape == (2, 2):
            orr, p = stats.fisher_exact(ct.values)
            tests.append((g, "Fisher exact (unseen)", round(orr, 3), p))
    hi = df["svi_q"].astype(str).eq("Q4 (most)")
    lo = df["svi_q"].astype(str).eq("Q1 (least)")
    ct = pd.crosstab(df.loc[hi | lo, "svi_q"].astype(str), df.loc[hi | lo, "unseen"])
    if ct.shape == (2, 2):
        orr, p = stats.fisher_exact(ct.values)
        tests.append(("SVI Q1 vs Q4", "Fisher exact (unseen)", round(orr, 3), p))
    rho, p = stats.spearmanr(df["svi_overall"], df["unseen"], nan_policy="omit")
    tests.append(("svi_overall", "Spearman vs unseen", round(rho, 3), p))
    lines.append("## Tests\n" + pd.DataFrame(tests, columns=["contrast", "test", "stat (OR or rho)", "p"]).to_markdown(index=False) + "\n")
    # Robustness: Census-geocoded only (address-level location), and category-misfiling only
    cg = df[df.geocoder == "census"]
    t = cg.groupby("hospital_based").agg(n=("ccn", "size"), unseen=("unseen", "mean"), misfiled=("status", lambda x: (x == "mapped_other_cat").mean()))
    lines.append("## Robustness: Census-geocoded facilities only\n" + t.round(3).to_markdown() + "\n")
    t = df.groupby(["pediatric", "hospital_based"]).agg(n=("ccn", "size"), unseen=("unseen", "mean"),
            misfiled=("status", lambda x: (x == "mapped_other_cat").mean()), stations=("stations", "sum"))
    lines.append("## Pediatric x hospital-based\n" + t.round(3).to_markdown() + "\n")
    # For a family searching the open map for a PEDIATRIC dialysis unit: nearest pediatric unit that a
    # dialysis_clinic category query returns (great-circle km). Adult units generally do not dialyse small children.
    pd_all = df[df.pediatric == 1].copy()
    vis = pd_all[pd_all.status == "mapped_dialysis"]
    def hav(a_lat, a_lon, b_lat, b_lon):
        a_lat, a_lon, b_lat, b_lon = map(np.deg2rad, (a_lat, a_lon, b_lat, b_lon))
        h = np.sin((b_lat - a_lat) / 2) ** 2 + np.cos(a_lat) * np.cos(b_lat) * np.sin((b_lon - a_lon) / 2) ** 2
        return 2 * 6371 * np.arcsin(np.sqrt(h))
    pd_all["nearest_visible_pediatric_km"] = [
        float(hav(r.lat, r.lon, vis.lat.values, vis.lon.values)[vis.ccn.values != r.ccn].min()) if len(vis) else np.nan
        for r in pd_all.itertuples()]
    pd_all.to_csv(OUT / "dialysis_pediatric_units.csv", index=False)
    ped = pd_all[["Facility Name", "City/Town", "State", "region", "GEOID", "status", "matched_cat", "stations",
                  "next_mapped_dialysis_km", "nearest_visible_pediatric_km"]]
    lines.append("## Every pediatric dialysis unit in the scored tracts\n" + ped.to_markdown(index=False) + "\n")
    try:
        m = smf.logit("unseen ~ rural + svi_overall + tribal + chain + hospital_based + C(region)", data=df).fit(disp=0)
        lines.append("## Logit: unseen ~ rural + SVI + tribal + chain + region FE\n```\n" + m.summary2().tables[1].round(4).to_string() + "\n```\n")
    except Exception as e:  # noqa: BLE001
        lines.append(f"logit failed: {e}\n")
    unseen = df[df.unseen == 1]
    lines.append(f"## Consequence\nUnseen facilities: {len(unseen)}, stations {int(unseen.stations.sum())}. "
                 f"Median distance from an unseen clinic to the next clinic a category search returns: "
                 f"{unseen.next_mapped_dialysis_km.median():.1f} km (rural: {unseen[unseen.rural==1].next_mapped_dialysis_km.median():.1f} km).\n")
    txt = "\n".join(lines)
    (OUT / "dialysis_summary.md").write_text(txt, encoding="utf-8")
    return txt


def main():
    con = connect()
    fac = load_facilities()
    fac = assign_tracts(fac, con)
    fac = match_overture(fac, con)
    print(analyse(fac))


if __name__ == "__main__":
    main()
