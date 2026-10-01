"""Label-free structural estimator of the coverage gap score (permitted data only).

Since 2026-09-25 the reference layers (TIGER roads, Microsoft footprints, USGS/HIFLD facilities,
CBP) are gone and may not be re-obtained ("prohibited target reconstruction"). No training labels
are published. This module therefore mirrors the OFFICIAL formula component by component, replacing
each missing reference count with an estimate built only from Overture's own attributes:

  transport  TIGER S1100+S1200 length  ~  km carrying a signed Interstate/US/State route
             (Overture `routes`) + gamma * km of county-route-numbered roads + beta * km of
             unsigned named-class roads.  gap = 1 - min(1, Overture named-class km / estimate);
             defined when the estimate > MIN_KM.
  building   Microsoft count is not observable; Overture already ingests Microsoft ML footprints,
             so the published mean gap is ~0.005. gap = building_floor (default 0); defined if any
             building is present.
  poi        per facility type k (fire / EMS / schools): reference count ~ Overture places in the
             official category + places whose NAME says they are that facility but are filed
             under another category (e.g. "Volunteer Fire Department" as fire_protection_service).
             gap_k = 1 - min(1, in_category / estimate), defined when estimate > 0.
             CBP half: gap = cbp_floor (default 0; Overture places outnumber establishments).
             poi = mean(facility half, CBP half).
  composite  mean of the defined components (official rule).

Every parameter is in PARAMS so alternative submissions are one CLI flag away.
Usage: python src/estimate.py [--name NAME] [--gamma 0.5] [--beta 0] [--shrink 1.0] ...
"""
from __future__ import annotations

import argparse
import json

import numpy as np
import pandas as pd

from common import FEAT, SCORED_REGIONS, SUB, ZINDI

PARAMS = dict(gamma=0.5, beta=0.0, min_km=0.1, building_floor=0.0, cbp_floor=0.0,
              use_name_evidence=True, shrink=1.0, components="tpb")

COLS = ["GEOID", "coverage_gap_score", "region", "transport_gap", "transport_defined", "building_gap",
        "building_defined", "poi_gap", "poi_defined", "poi_gap_fire", "poi_defined_fire", "poi_gap_ems",
        "poi_defined_ems", "poi_gap_schools", "poi_defined_schools", "poi_gap_cbp", "poi_defined_cbp"]


def load_features(regions=SCORED_REGIONS) -> pd.DataFrame:
    return pd.concat([pd.read_parquet(FEAT / f"{r}-features.parquet") for r in regions], ignore_index=True)


def ratio_gap(have, ref):
    have, ref = np.asarray(have, float), np.asarray(ref, float)
    with np.errstate(divide="ignore", invalid="ignore"):
        g = 1 - np.minimum(1.0, np.where(ref > 0, have / ref, 1.0))
    return np.clip(np.nan_to_num(g), 0, 1)


def estimate(f: pd.DataFrame, p: dict | None = None) -> pd.DataFrame:
    p = {**PARAMS, **(p or {})}
    o = pd.DataFrame({"GEOID": f["GEOID"], "region": f["region"]})

    tiger = f["road_km_signed"] + p["gamma"] * f["road_km_county_route"] + p["beta"] * f["road_km_named_unsigned"]
    o["transport_defined"] = (tiger > p["min_km"]).values
    o["transport_gap"] = np.where(o["transport_defined"], ratio_gap(f["road_km_named"], tiger), 0.0)

    o["building_defined"] = (f["bld_n"] > 0).values
    o["building_gap"] = np.where(o["building_defined"], p["building_floor"], 0.0)

    ne = 1.0 if p["use_name_evidence"] else 0.0
    halves = []
    for k, cat, nm in [("fire", "poi_fire", "poi_fire_name_other_cat"), ("ems", "poi_ems", "poi_ems_name_other_cat"),
                       ("schools", "poi_schools", "poi_school_name_other_cat")]:
        ref_est = f[cat] + ne * f[nm]
        o[f"poi_defined_{k}"] = (ref_est > 0).values
        o[f"poi_gap_{k}"] = np.where(o[f"poi_defined_{k}"], ratio_gap(f[cat], ref_est), 0.0)
        halves.append(k)
    dmat = o[[f"poi_defined_{k}" for k in halves]].values
    gmat = o[[f"poi_gap_{k}" for k in halves]].values
    fac_def = dmat.any(1)
    fac_gap = np.where(fac_def, (gmat * dmat).sum(1) / np.maximum(dmat.sum(1), 1), 0.0)
    o["poi_defined_cbp"] = (f["poi_n"] >= 0).values  # CBP establishments exist in (almost) every tract
    o["poi_gap_cbp"] = p["cbp_floor"]
    o["poi_defined"] = fac_def | o["poi_defined_cbp"].values
    o["poi_gap"] = np.where(fac_def, (fac_gap + o["poi_gap_cbp"]) / 2, o["poi_gap_cbp"])

    use = {"t": "transport", "p": "poi", "b": "building"}
    num = np.zeros(len(o)); den = np.zeros(len(o))
    for c in p["components"]:
        n = use[c]
        num += np.where(o[f"{n}_defined"], o[f"{n}_gap"], 0)
        den += o[f"{n}_defined"].astype(int)
    o["coverage_gap_score"] = np.clip(p["shrink"] * np.where(den > 0, num / np.maximum(den, 1), 0.0), 0, 1)
    return o


def write_submission(o: pd.DataFrame, name: str, params: dict) -> str:
    ss = pd.read_csv(ZINDI / "SampleSubmission.csv", dtype={"GEOID": str})
    sub = ss[["GEOID"]].merge(o, on="GEOID", how="left")
    missing = sub["coverage_gap_score"].isna().sum()
    assert missing == 0, f"{missing} tracts in SampleSubmission without a prediction"
    sub = sub[COLS]
    assert len(sub) == len(ss) and sub.notna().all().all()
    path = SUB / f"{name}.csv"
    sub.to_csv(path, index=False, float_format="%.6f")
    (SUB / f"{name}.params.json").write_text(json.dumps(params, indent=1))
    return str(path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", default="structural_v1")
    for k, v in PARAMS.items():
        ap.add_argument(f"--{k}", type=type(v) if not isinstance(v, bool) else (lambda s: s.lower() in ("1", "true", "yes")), default=v)
    a = vars(ap.parse_args())
    name = a.pop("name")
    f = load_features()
    o = estimate(f, a)
    path = write_submission(o, name, a)
    s = o.groupby("region").agg(n=("GEOID", "size"), score_mean=("coverage_gap_score", "mean"),
                                score_median=("coverage_gap_score", "median"),
                                t_def=("transport_defined", "mean"), t_mean=("transport_gap", "mean"),
                                poi_mean=("poi_gap", "mean"), fire_def=("poi_defined_fire", "mean"))
    print(s.round(4).to_string())
    print("overall mean", round(o.coverage_gap_score.mean(), 5), "->", path)


if __name__ == "__main__":
    main()
