"""Per-tract feature table from PERMITTED layers only.

For every tract in each region's sample submission we compute:
  roads      km by Overture class, km of the scored "named highway" classes, km carrying a signed
             Interstate / US / State route (from Overture's own `routes` attribute), the signed
             length Overture files under a NON-named class, and source freshness.
  buildings  counts by upstream dataset (OSM / Microsoft ML / Esri / Google), footprint area.
  places     total, high-confidence, per facility category used by the official POI gap, by source.
  infra      transit/airport features.
  context    ACS housing units, population, land area, strata columns used later.

Usage: python src/features.py [region ...]     -> data/features/<region>-features.parquet
"""
from __future__ import annotations

import sys
import time

import pandas as pd

from common import (ALL_REGIONS, FEAT, NAMED_CLASSES, RAW, SCHOOL_CATS, connect, ref, strata, to5070)

NAMED = ", ".join(f"'{c}'" for c in NAMED_CLASSES)
SCHOOLS = ", ".join(f"'{c}'" for c in SCHOOL_CATS)
# Interstate, US highway, State route networks in Overture `routes.network` (OSM route relations).
SIGNED_SQL = r"""regexp_matches(r.network, '^US:(I|US|[A-Z]{2})$')"""


def build(region: str) -> pd.DataFrame:
    t0 = time.time()
    con = connect()
    ss = pd.read_csv(ref(region, "sample-submission.csv"), dtype={"GEOID": str})
    con.register("ss", ss[["GEOID"]])

    # Tract polygons (whole tracts; region boundary is the dissolve of its tracts).
    con.sql(f"""
        CREATE TABLE tracts AS
        SELECT t.GEOID, t.COUNTYFP, t.ALAND, t.pop_total, t.ur_class,
               {to5070('t.geometry')} AS g,
               t.geometry AS g4326
        FROM '{strata(region, 'census-tracts.parquet')}' t JOIN ss USING (GEOID)
    """)
    n_tracts = con.sql("select count(*) from tracts").fetchone()[0]
    assert n_tracts == len(ss), (region, n_tracts, len(ss))

    # ---------------- roads ----------------
    con.sql(f"""
        CREATE TABLE seg AS
        SELECT id, class,
               {to5070()} AS g,
               list_bool_or([{SIGNED_SQL} for r in coalesce(routes, [])]) AS signed,
               list_bool_or([r.network = 'US:I' for r in coalesce(routes, [])]) AS interstate,
               list_bool_or([r.network = 'US:US' for r in coalesce(routes, [])]) AS us_route,
               list_bool_or([regexp_matches(r.network, '^US:[A-Z]{{2}}$') for r in coalesce(routes, [])]) AS state_route,
               list_bool_or([regexp_matches(r.network, '^US:[A-Z]{{2}}:') AND NOT regexp_matches(r.network, 'Scenic|Business|Historic|Bypass|Truck|Loop|Spur') for r in coalesce(routes, [])]) AS county_route,
               names."primary" IS NOT NULL AS has_name,
               list_max([try_cast(left(s.update_time, 4) AS INT) for s in coalesce(sources, [])]) AS upd_year
        FROM '{ref(region, 'overture-roads.parquet')}'
    """)
    con.sql("""
        CREATE TABLE road_parts AS
        SELECT t.GEOID, s.class, coalesce(s.signed,false) signed, coalesce(s.interstate,false) interstate,
               coalesce(s.us_route,false) us_route, coalesce(s.state_route,false) state_route, coalesce(s.county_route,false) county_route, s.has_name, s.upd_year,
               CASE WHEN ST_Within(s.g, t.g) THEN ST_Length(s.g)
                    ELSE ST_Length(ST_Intersection(s.g, t.g)) END / 1000.0 AS km
        FROM seg s JOIN tracts t ON ST_Intersects(s.g, t.g)
    """)
    roads = con.sql(f"""
        SELECT GEOID,
          sum(km) road_km_all,
          sum(km) FILTER (WHERE class IN ({NAMED})) road_km_named,
          sum(km) FILTER (WHERE class='motorway') road_km_motorway,
          sum(km) FILTER (WHERE class='trunk') road_km_trunk,
          sum(km) FILTER (WHERE class='primary') road_km_primary,
          sum(km) FILTER (WHERE class='secondary') road_km_secondary,
          sum(km) FILTER (WHERE class='tertiary') road_km_tertiary,
          sum(km) FILTER (WHERE class='residential') road_km_residential,
          sum(km) FILTER (WHERE class='unclassified') road_km_unclassified,
          sum(km) FILTER (WHERE signed) road_km_signed,
          sum(km) FILTER (WHERE interstate) road_km_interstate,
          sum(km) FILTER (WHERE us_route) road_km_us,
          sum(km) FILTER (WHERE state_route) road_km_state,
          sum(km) FILTER (WHERE signed AND class NOT IN ({NAMED})) road_km_signed_lowclass,
          sum(km) FILTER (WHERE (NOT signed) AND class IN ({NAMED})) road_km_named_unsigned,
          sum(km) FILTER (WHERE county_route AND NOT signed) road_km_county_route,
          sum(km) FILTER (WHERE county_route AND NOT signed AND class NOT IN ({NAMED})) road_km_county_lowclass,
          sum(km) FILTER (WHERE class IN ({NAMED}) AND NOT has_name) road_km_named_noname,
          sum(km) FILTER (WHERE has_name) / nullif(sum(km),0) road_frac_named_streets,
          median(upd_year) FILTER (WHERE class IN ({NAMED})) road_named_upd_year_med,
          sum(km) FILTER (WHERE upd_year < 2015) / nullif(sum(km),0) road_frac_stale_pre2015
        FROM road_parts GROUP BY GEOID
    """).df()

    # ---------------- buildings (centroid-in-tract) ----------------
    con.sql(f"""
        CREATE TABLE bpts AS
        SELECT ST_Centroid(geometry) AS c,
               ST_Area({to5070()}) AS area_m2,
               coalesce(sources[1].dataset, 'unknown') AS ds,
               height IS NOT NULL OR num_floors IS NOT NULL AS has_height
        FROM '{ref(region, 'overture-buildings.parquet')}'
    """)
    bld = con.sql("""
        SELECT t.GEOID,
          count(*) bld_n,
          count(*) FILTER (WHERE ds='OpenStreetMap') bld_n_osm,
          count(*) FILTER (WHERE ds='Microsoft ML Buildings') bld_n_ms,
          count(*) FILTER (WHERE ds='Esri Community Maps') bld_n_esri,
          count(*) FILTER (WHERE ds ILIKE '%google%') bld_n_google,
          sum(area_m2) bld_area_m2,
          median(area_m2) bld_area_med_m2,
          count(*) FILTER (WHERE area_m2 < 40) bld_n_small,
          count(*) FILTER (WHERE area_m2 > 1000) bld_n_large,
          avg(has_height::INT) bld_frac_height
        FROM bpts b JOIN tracts t ON ST_Intersects(b.c, t.g4326)
        GROUP BY t.GEOID
    """).df()

    # ---------------- places ----------------
    con.sql(f"""
        CREATE TABLE poi AS
        SELECT geometry AS p, categories."primary" AS cat, confidence, names."primary" AS nm,
               coalesce(sources[1].dataset,'unknown') ds,
               len(coalesce(sources, [])) n_src,
               len(coalesce(addresses, [])) > 0 has_addr,
               len(coalesce(phones, [])) > 0 OR len(coalesce(websites, [])) > 0 has_contact,
               operating_status
        FROM '{ref(region, 'overture-pois.parquet')}'
    """)
    poi = con.sql(f"""
        SELECT t.GEOID,
          count(*) poi_n,
          count(*) FILTER (WHERE confidence >= 0.5) poi_n_conf50,
          count(*) FILTER (WHERE confidence >= 0.8) poi_n_conf80,
          avg(confidence) poi_conf_mean,
          count(*) FILTER (WHERE cat='fire_department') poi_fire,
          count(*) FILTER (WHERE cat='fire_protection_service') poi_fire_protection,
          count(*) FILTER (WHERE cat='ambulance_and_ems_services') poi_ems,
          count(*) FILTER (WHERE cat IN ({SCHOOLS})) poi_schools,
          count(*) FILTER (WHERE cat='hospital') poi_hospital,
          count(*) FILTER (WHERE cat IN ('police_department')) poi_police,
          count(*) FILTER (WHERE cat IS DISTINCT FROM 'fire_department' AND regexp_matches(lower(coalesce(nm,'')), '(fire (station|dep|dept|district|rescue|company|hall)|volunteer fire|\\bvfd\\b|fire & rescue|fire and rescue)')) poi_fire_name_other_cat,
          count(*) FILTER (WHERE cat IS DISTINCT FROM 'ambulance_and_ems_services' AND regexp_matches(lower(coalesce(nm,'')), '(\\bems\\b|ambulance|emergency medical)')) poi_ems_name_other_cat,
          count(*) FILTER (WHERE cat NOT IN ({SCHOOLS}) AND regexp_matches(lower(coalesce(nm,'')), '(elementary|middle school|high school|junior high|primary school|academy|intermediate school)')) poi_school_name_other_cat,
          count(*) FILTER (WHERE cat IN ('dialysis_clinic')) poi_dialysis,
          count(*) FILTER (WHERE cat IN ('library','community_center','senior_citizen_services')) poi_cooling_type,
          count(*) FILTER (WHERE ds='meta') poi_n_meta,
          count(*) FILTER (WHERE ds='Microsoft') poi_n_msft,
          count(*) FILTER (WHERE ds IN ('Overture','Overture-signals')) poi_n_overture,
          count(*) FILTER (WHERE ds='Foursquare') poi_n_fsq,
          count(*) FILTER (WHERE ds='BrightQuery') poi_n_bq,
          count(*) FILTER (WHERE n_src > 1) poi_n_multisrc,
          avg(has_addr::INT) poi_frac_addr,
          avg(has_contact::INT) poi_frac_contact,
          count(*) FILTER (WHERE operating_status IS NOT NULL AND operating_status <> 'open') poi_n_not_open
        FROM poi JOIN tracts t ON ST_Intersects(poi.p, t.g4326)
        GROUP BY t.GEOID
    """).df()

    infra = con.sql(f"""
        SELECT t.GEOID, count(*) infra_n
        FROM '{ref(region, 'overture-infrastructure.parquet')}' i JOIN tracts t
          ON ST_Intersects(ST_Centroid(i.geometry), t.g4326)
        GROUP BY t.GEOID
    """).df()

    acs = con.sql(f"SELECT GEOID, housing_units AS acs_housing_units FROM '{ref(region, 'census-acs-housing.parquet')}'").df()
    base = con.sql("SELECT GEOID, COUNTYFP, ALAND, pop_total, ur_class, ST_Area(g) AS area_m2 FROM tracts").df()

    df = base
    for part in (acs, roads, bld, poi, infra):
        df = df.merge(part, on="GEOID", how="left")
    cnt_cols = [c for c in df.columns if c.startswith(("road_km", "bld_n", "poi_", "infra_n", "bld_area_m2"))
                and not c.startswith(("poi_conf_mean", "poi_frac"))]
    df[cnt_cols] = df[cnt_cols].fillna(0)
    df.insert(1, "region", region)
    df["county_fips"] = df["GEOID"].str[:5]
    out = FEAT / f"{region}-features.parquet"
    df.to_parquet(out, index=False)
    print(f"{region}: {len(df)} tracts, {df.shape[1]} cols, {time.time()-t0:.0f}s -> {out.name}", flush=True)
    return df


if __name__ == "__main__":
    regions = sys.argv[1:] or ALL_REGIONS
    for r in regions:
        if not (RAW / "reference" / r).exists():
            print("skip (not downloaded):", r)
            continue
        build(r)
