"""Validated supervised pipeline (spatial CV by county) + error analysis by demographic group.

Two modes:
  --labels PATH   a CSV with GEOID + target column(s) that is LEGITIMATELY available
                  (e.g. if the organisers publish a labelled training region). Trains on it.
  --proxy         (default) no labels exist under the current rules, so the target is the
                  label-free structural estimate from estimate.py. Two models are fitted:
                    A  all permitted features  -> plumbing check (should be near-perfect)
                    B  strata/demographics ONLY (no map features) -> "how much of the coverage
                       gap can be predicted from WHO lives there?" (bias analysis input)

Outputs: outputs/cv_report.md, outputs/feature_importance_*.csv, outputs/oof_*.parquet
"""
from __future__ import annotations

import argparse

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.linear_model import RidgeCV
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from common import OUT, RAW
from estimate import estimate, load_features

SEED = 42
STRATA_COLS = ["svi_overall", "svi_socioeconomic", "svi_household", "svi_minority", "svi_housing_transport",
               "cvi_overall", "ruca_primary", "rucc_2023", "nchs_2013", "tribal_any", "tribal_pct",
               "pct_urban", "usfs_RPS_mean", "usfs_WHP_mean", "epht_heat_days_summer", "usdm_summer_dsci",
               "mtbs_wildfire_ever", "ghcn_any_nearest_km"]


def load_strata() -> pd.DataFrame:
    s = pd.read_parquet(RAW / "strata" / "national" / "national-strata-tract-table.parquet",
                        columns=["GEOID"] + STRATA_COLS)
    for c in STRATA_COLS:
        s[c] = pd.to_numeric(s[c].astype("float64") if s[c].dtype == bool else s[c], errors="coerce")
    return s


def design(f: pd.DataFrame, s: pd.DataFrame):
    d = f.merge(s, on="GEOID", how="left")
    d["log_pop"] = np.log1p(d["pop_total"])
    d["log_density"] = np.log1p(d["pop_total"] / (d["ALAND"].clip(lower=1) / 1e6))
    d["log_hu"] = np.log1p(d["acs_housing_units"])
    map_cols = [c for c in f.columns if c.startswith(("road_", "bld_", "poi_", "infra_"))]
    demo_cols = STRATA_COLS + ["log_pop", "log_density", "log_hu"]
    return d, map_cols, demo_cols


def cv_eval(d: pd.DataFrame, y: np.ndarray, cols: list[str], groups: np.ndarray, tag: str, n_splits=5):
    X = d[cols].astype(float)
    gkf = GroupKFold(n_splits=n_splits)
    oof = {k: np.zeros(len(d)) for k in ["zero", "median", "ridge", "lgbm"]}
    grid = [dict(num_leaves=15, learning_rate=0.03, min_child_samples=40, n_estimators=600),
            dict(num_leaves=31, learning_rate=0.03, min_child_samples=20, n_estimators=800),
            dict(num_leaves=63, learning_rate=0.05, min_child_samples=20, n_estimators=600)]
    # pick hyper-parameters by inner spatial CV on the first outer training fold (cheap, no leakage)
    tr0, _ = next(gkf.split(X, y, groups))
    best, best_s = None, 1e9
    for g in grid:
        inner = GroupKFold(3)
        errs = []
        for a, b in inner.split(X.iloc[tr0], y[tr0], groups[tr0]):
            m = lgb.LGBMRegressor(**g, subsample=0.8, subsample_freq=1, colsample_bytree=0.8, random_state=SEED, verbose=-1)
            m.fit(X.iloc[tr0].iloc[a], y[tr0][a])
            errs.append(np.sqrt(np.mean((m.predict(X.iloc[tr0].iloc[b]) - y[tr0][b]) ** 2)))
        if np.mean(errs) < best_s:
            best, best_s = g, np.mean(errs)
    imps = []
    for tr, te in gkf.split(X, y, groups):
        oof["median"][te] = np.median(y[tr])
        r = make_pipeline(StandardScaler(), RidgeCV(alphas=np.logspace(-3, 3, 13)))
        r.fit(X.iloc[tr].fillna(X.iloc[tr].median()), y[tr])
        oof["ridge"][te] = np.clip(r.predict(X.iloc[te].fillna(X.iloc[tr].median())), 0, 1)
        m = lgb.LGBMRegressor(**best, subsample=0.8, subsample_freq=1, colsample_bytree=0.8, random_state=SEED, verbose=-1)
        m.fit(X.iloc[tr], y[tr])
        oof["lgbm"][te] = np.clip(m.predict(X.iloc[te]), 0, 1)
        imps.append(pd.Series(m.booster_.feature_importance("gain"), index=cols))
    res = {k: dict(rmse=float(np.sqrt(np.mean((v - y) ** 2))), mae=float(np.mean(np.abs(v - y)))) for k, v in oof.items()}
    imp = pd.concat(imps, axis=1).mean(1).sort_values(ascending=False)
    imp.to_csv(OUT / f"feature_importance_{tag}.csv", header=["gain"])
    return res, oof, imp, best


def error_by_group(d, y, pred, tag) -> pd.DataFrame:
    e = pd.DataFrame({"y": y, "pred": pred, "region": d["region"],
                      "rural": np.where(d["ruca_primary"] >= 4, "rural", "urban"),
                      "tribal": np.where(d["tribal_any"] > 0, "tribal", "non-tribal"),
                      "svi_q": pd.qcut(d["svi_overall"], 4, labels=["Q1", "Q2", "Q3", "Q4"])})
    e["err"] = e["pred"] - e["y"]
    rows = []
    for g in ["region", "rural", "tribal", "svi_q"]:
        t = e.groupby(g, observed=True).agg(n=("y", "size"), y_mean=("y", "mean"), pred_mean=("pred", "mean"),
                                           bias=("err", "mean"), rmse=("err", lambda x: np.sqrt(np.mean(x ** 2))))
        t.index = [f"{g}={i}" for i in t.index]
        rows.append(t)
    out = pd.concat(rows)
    out.to_csv(OUT / f"error_by_group_{tag}.csv")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--labels", default=None, help="CSV with GEOID + target (only if legitimately available)")
    ap.add_argument("--target", default="coverage_gap_score")
    a = ap.parse_args()
    f = load_features()
    s = load_strata()
    d, map_cols, demo_cols = design(f, s)
    if a.labels:
        lab = pd.read_csv(a.labels, dtype={"GEOID": str})[["GEOID", a.target]]
        d = d.merge(lab, on="GEOID", how="inner")
        y = d[a.target].values.astype(float)
        src = f"labels file {a.labels}"
    else:
        y = estimate(d)["coverage_gap_score"].values
        src = "PROXY = label-free structural estimate (estimate.py defaults)"
    groups = d["county_fips"].values
    lines = [f"# Spatial-CV report\nTarget: {src}. n={len(d)}, groups = counties ({len(set(groups))}), GroupKFold(5).\n"]
    for tag, cols in [("all_features", map_cols + demo_cols), ("demographics_only", demo_cols)]:
        res, oof, imp, best = cv_eval(d, y, cols, groups, tag)
        lines.append(f"## Model set: {tag} ({len(cols)} features), LightGBM params {best}\n")
        lines.append(pd.DataFrame(res).T.round(5).to_markdown() + "\n")
        lines.append("Top features (gain): " + ", ".join(imp.index[:12]) + "\n")
        eg = error_by_group(d, y, oof["lgbm"], tag)
        lines.append("Error by group (LightGBM OOF):\n" + eg.round(4).to_markdown() + "\n")
        pd.DataFrame({"GEOID": d["GEOID"], "y": y, **{f"oof_{k}": v for k, v in oof.items()}}).to_parquet(OUT / f"oof_{tag}.parquet")
    txt = "\n".join(lines)
    (OUT / "cv_report.md").write_text(txt, encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()
