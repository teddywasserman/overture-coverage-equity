"""Where, and for whom, is the open map thinnest?  (permitted challenge data only)

Indicators per tract (all from Overture + ACS + strata):
  est_gap            label-free coverage gap estimate (estimate.py)
  hwy_downgrade      share of signed Interstate/US/State + county-route km that Overture files
                     under a non-named class (what a highway-class filter / router deprioritises)
  ai_only_bld        share of buildings whose only source is Microsoft ML (no OSM/Esri survey)
  places_per_1k_hu   Overture places per 1,000 ACS housing units
  fire_misfiled      tract has a fire station only under a non-fire category (invisible to the
                     official fire_department query)
  school_misfiled    ditto for schools
Stratifiers: RUCA rural/urban, SVI quartile, tribal overlap, CVI quartile, wildfire risk (USFS RPS
quartile), summer heat days quartile. Tests: Mann-Whitney / Kruskal-Wallis, and OLS/logit with
region fixed effects and county-clustered SEs so differences are not regional composition.
Outputs: outputs/bias_tables.md, outputs/figures/*.png
"""
from __future__ import annotations

import geopandas as gpd
import matplotlib
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from scipy import stats

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from common import FIG, OUT, RAW, SCORED_REGIONS, strata  # noqa: E402
from estimate import estimate, load_features  # noqa: E402

COLS = ["GEOID", "ruca_primary", "svi_overall", "svi_minority", "tribal_any", "cvi_overall", "usfs_RPS_mean",
        "epht_heat_days_summer", "pop_total", "aiannh_name", "mtbs_wildfire_ever"]


def indicators() -> pd.DataFrame:
    f = load_features()
    e = estimate(f)
    s = pd.read_parquet(RAW / "strata" / "national" / "national-strata-tract-table.parquet", columns=COLS)
    d = f.merge(e[["GEOID", "coverage_gap_score", "transport_gap", "transport_defined", "poi_gap"]], on="GEOID") \
         .merge(s.drop(columns=["pop_total"]), on="GEOID", how="left")
    d = d.rename(columns={"coverage_gap_score": "est_gap"})
    hw = d["road_km_signed"] + d["road_km_county_route"]
    d["hwy_downgrade"] = np.where(hw > 0.1, (d["road_km_signed_lowclass"] + d["road_km_county_lowclass"]) / hw.clip(lower=1e-9), np.nan)
    d["ai_only_bld"] = np.where(d["bld_n"] > 0, d["bld_n_ms"] / d["bld_n"].clip(lower=1), np.nan)
    d["places_per_1k_hu"] = d["poi_n"] / (d["acs_housing_units"].clip(lower=1) / 1000)
    d["fire_misfiled"] = ((d["poi_fire"] == 0) & (d["poi_fire_name_other_cat"] > 0)).astype(int)
    d["school_misfiled"] = ((d["poi_schools"] == 0) & (d["poi_school_name_other_cat"] > 0)).astype(int)
    d["no_fire_any"] = ((d["poi_fire"] == 0) & (d["poi_fire_name_other_cat"] == 0)).astype(int)
    d["rural"] = np.where(pd.to_numeric(d["ruca_primary"], errors="coerce") >= 4, "rural", "urban")
    d["tribal"] = np.where(d["tribal_any"].fillna(False).astype(bool), "tribal", "non-tribal")
    q = lambda c: pd.qcut(d[c].rank(method="first"), 4, labels=["Q1", "Q2", "Q3", "Q4"])
    d["svi_q"], d["cvi_q"], d["fire_q"], d["heat_q"] = q("svi_overall"), q("cvi_overall"), q("usfs_RPS_mean"), q("epht_heat_days_summer")
    d.to_parquet(OUT / "tract_indicators.parquet", index=False)
    return d


INDS = ["est_gap", "transport_gap", "poi_gap", "hwy_downgrade", "ai_only_bld", "places_per_1k_hu", "fire_misfiled", "school_misfiled"]


def tables(d: pd.DataFrame) -> str:
    out = ["# Coverage indicators by stratum (all 5 regions, n=%d tracts)\n" % len(d)]
    for g in ["region", "rural", "tribal", "svi_q", "cvi_q", "fire_q", "heat_q"]:
        t = d.groupby(g, observed=True)[INDS].mean()
        t.insert(0, "n", d.groupby(g, observed=True).size())
        out.append(f"## {g}\n" + t.round(3).to_markdown() + "\n")
    rows = []
    for ind in INDS:
        for g, a, b in [("rural", "rural", "urban"), ("tribal", "tribal", "non-tribal"), ("svi_q", "Q4", "Q1")]:
            x, y = d.loc[d[g] == a, ind].dropna(), d.loc[d[g] == b, ind].dropna()
            if len(x) > 5 and len(y) > 5:
                u, p = stats.mannwhitneyu(x, y)
                rows.append((ind, f"{g}: {a} vs {b}", round(x.mean(), 4), round(y.mean(), 4),
                             round(x.mean() / y.mean(), 2) if y.mean() else np.nan, p))
    out.append("## Mann-Whitney tests\n" + pd.DataFrame(rows, columns=["indicator", "contrast", "mean A", "mean B", "ratio", "p"]).to_markdown(index=False) + "\n")
    # adjusted models: region FE, county-clustered SE
    dd = d.dropna(subset=["svi_overall"]).copy()
    dd["rural_i"] = (dd["rural"] == "rural").astype(int)
    dd["tribal_i"] = (dd["tribal"] == "tribal").astype(int)
    for ind in ["est_gap", "hwy_downgrade", "ai_only_bld", "fire_misfiled"]:
        sub = dd.dropna(subset=[ind])
        m = smf.ols(f"{ind} ~ rural_i + tribal_i + svi_overall + C(region)", data=sub).fit(
            cov_type="cluster", cov_kwds={"groups": sub["county_fips"]})
        out.append(f"## OLS {ind} ~ rural + tribal + SVI + region FE (county-clustered SE)\n```\n"
                   + m.summary2().tables[1].loc[["rural_i", "tribal_i", "svi_overall"]].round(4).to_string() + "\n```\n")
    txt = "\n".join(out)
    (OUT / "bias_tables.md").write_text(txt, encoding="utf-8")
    return txt


def maps(d: pd.DataFrame):
    for col, title, cmap in [("est_gap", "Estimated coverage gap (label-free)", "magma_r"),
                             ("hwy_downgrade", "Signed highway km filed under a minor class", "viridis_r"),
                             ("ai_only_bld", "Share of buildings from AI footprints only", "cividis_r")]:
        fig, axes = plt.subplots(1, len(SCORED_REGIONS), figsize=(22, 5))
        for ax, r in zip(axes, SCORED_REGIONS):
            g = gpd.read_parquet(strata(r, "census-tracts.parquet"))[["GEOID", "geometry"]]
            g = g.merge(d[["GEOID", col]], on="GEOID", how="inner")
            g.plot(column=col, ax=ax, cmap=cmap, vmin=0, vmax=max(0.05, float(d[col].quantile(0.98))),
                   legend=True, legend_kwds={"shrink": 0.6}, missing_kwds={"color": "#dddddd"}, linewidth=0)
            ax.set_title(r); ax.set_axis_off()
        fig.suptitle(title)
        fig.tight_layout()
        fig.savefig(FIG / f"map_{col}.png", dpi=110)
        plt.close(fig)
    # strata bar chart
    fig, axes = plt.subplots(1, 3, figsize=(15, 4))
    for ax, ind in zip(axes, ["hwy_downgrade", "ai_only_bld", "fire_misfiled"]):
        t = pd.concat([d.groupby("rural")[ind].mean(), d.groupby("tribal")[ind].mean(), d.groupby("svi_q", observed=True)[ind].mean()])
        t.plot.bar(ax=ax, color="#4c72b0")
        ax.set_title(ind); ax.tick_params(axis="x", rotation=45)
    fig.tight_layout(); fig.savefig(FIG / "indicators_by_stratum.png", dpi=110); plt.close(fig)


if __name__ == "__main__":
    d = indicators()
    print(tables(d))
    maps(d)
