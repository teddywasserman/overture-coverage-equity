"""Figures for the dialysis discovery.

Reads outputs of discovery_dialysis.py and, if present, audit_pediatric_matches.py.
  outputs/figures/dialysis_unseen_rates.png      share not returned by a dialysis_clinic query, with 95% CIs
  outputs/figures/dialysis_pediatric_texas.png   pediatric units in the South-Central Texas region
"""
import geopandas as gpd
import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from common import FIG, OUT, RAW  # noqa: E402

INK, INK2, GRID = "#0b0b0b", "#52514e", "#e4e3df"
FOCUS, REF = "#e34948", "#9a9993"
BLUE, YELLOW, RED = "#2a78d6", "#eda100", "#e34948"
plt.rcParams.update({"font.size": 9, "axes.edgecolor": INK2, "axes.labelcolor": INK, "xtick.color": INK2,
                     "ytick.color": INK, "figure.facecolor": "white"})


def wilson(k, n, z=1.96):
    if n == 0:
        return np.nan, np.nan
    p = k / n
    c = (p + z * z / (2 * n)) / (1 + z * z / n)
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return c - h, c + h


d = pd.read_csv(OUT / "dialysis_facilities.csv", dtype={"GEOID": str})
d = d[~d["Facility Name"].str.lower().str.startswith("zz_closed")]

# --- Figure 1: unseen rate by contrast pair ------------------------------------------------------
pairs = [
    ("Patient age", ("Pediatric units", d.pediatric == 1), ("Adult units", d.pediatric == 0)),
    ("Ownership", ("Independent", d.chain == 0), ("Chain-owned", d.chain == 1)),
    ("Rurality", ("Rural tracts", d.rural == 1), ("Urban tracts", d.rural == 0)),
    ("Social vulnerability", ("SVI top quartile", d.svi_q == "Q4 (most)"), ("SVI bottom quartile", d.svi_q == "Q1 (least)")),
]
labels, vals, los, his, cols = [], [], [], [], []
for _, (la, ma), (lb, mb) in pairs:
    for lab, m, col in [(la, ma, FOCUS), (lb, mb, REF)]:
        k, n = int(d.loc[m, "unseen"].sum()), int(m.sum())
        lo, hi = wilson(k, n)
        labels.append(f"{lab}  ({k}/{n})"); vals.append(k / n); los.append(k / n - lo); his.append(hi - k / n); cols.append(col)
fig, ax = plt.subplots(figsize=(8, 4.6))
y = np.arange(len(labels))[::-1] + np.repeat(np.arange(len(pairs))[::-1] * 0.6, 2)
ax.barh(y, vals, color=cols, height=0.8, edgecolor="white", linewidth=2)
ax.errorbar(vals, y, xerr=[los, his], fmt="none", ecolor=INK2, elinewidth=1, capsize=2)
for yi, v, h in zip(y, vals, his):
    ax.text(v + h + 0.015, yi, f"{v:.0%}", va="center", color=INK)
ax.set_yticks(y, labels)
ax.set_xlim(0, 1)
ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
ax.grid(axis="x", color=GRID, linewidth=0.8); ax.set_axisbelow(True)
for s in ("top", "right", "left"):
    ax.spines[s].set_visible(False)
ax.tick_params(axis="y", length=0)
ax.set_xlabel("CMS-certified dialysis facilities NOT returned by an Overture 'dialysis_clinic' query\n"
              "(missing, or present under another category). Whiskers: Wilson 95% CI.", color=INK2)
fig.suptitle("Who the open map hides: pediatric and independent units, not rural or high-SVI places",
             x=0.01, ha="left", color=INK, fontsize=10.5)
fig.text(0.01, 0.01, "863 facilities in the 9,794 scored tracts. CMS Dialysis Facility listing (2026-06-16) vs Overture places 2026-08-19.0.",
         color=INK2, fontsize=7.5)
fig.tight_layout(rect=(0, 0.03, 1, 1))
fig.savefig(FIG / "dialysis_unseen_rates.png", dpi=150)
plt.close(fig)

# --- Figure 2: Texas map of pediatric units ------------------------------------------------------
p = pd.read_csv(OUT / "dialysis_pediatric_units.csv", dtype={"GEOID": str, "ccn": str})
audit_path = OUT / "pediatric_match_audit.csv"
if audit_path.exists():
    a = pd.read_csv(audit_path, dtype={"ccn": str})[["ccn", "findable_strict"]]
    p = p.merge(a, on="ccn", how="left")
else:
    p["findable_strict"] = p["status"].eq("mapped_dialysis")
p["state3"] = np.where(p.findable_strict, "ped",
                       np.where(p.status.eq("mapped_dialysis"), "adult_only", "hidden"))
tx = p[p.State == "TX"].copy()
tracts = gpd.read_parquet(RAW / "strata" / "south-central-tx" / "south-central-tx-census-tracts.parquet")
fig, ax = plt.subplots(figsize=(7.5, 8))
tracts.plot(ax=ax, color="#f0efec", edgecolor="#e2e1dc", linewidth=0.1)
adult = d[(d.region == "south-central-tx") & (d.pediatric == 0)]
ax.scatter(adult.lon, adult.lat, s=5, color="#b5b4ae", label="adult dialysis unit (CMS)", zorder=2)
style = {
    "ped": dict(marker="o", s=110, color=BLUE, label="pediatric unit, findable as a dialysis_clinic"),
    "adult_only": dict(marker="^", s=120, color=YELLOW, label="pediatric unit; query finds only an ADULT clinic within 250 m"),
    "hidden": dict(marker="X", s=140, color=RED, label="pediatric unit, not returned by the query"),
}
for k, st in style.items():
    g = tx[tx.state3 == k]
    ax.scatter(g.lon, g.lat, edgecolor=INK, linewidth=0.8, zorder=4, **st)
offsets = {"houston": (-12, -28), "dallas": (10, 6), "fort worth": (-10, 14), "austin": (12, 10),
           "san antonio": (-12, -18), "corpus christi": (10, 0), "mcallen": (10, 4)}
for city, g in tx.groupby(tx["City/Town"].str.lower()):
    hid = g[g.state3 != "ped"]
    txt = f"{city.title().replace('Mcallen', 'McAllen')}: {len(g)} unit{'s' if len(g) > 1 else ''}, {int(g.stations.sum())} stations"
    if len(hid):
        txt += f"\n{int(hid.stations.sum())} stations not findable as pediatric"
    dx, dy = offsets.get(city, (8, 6))
    ax.annotate(txt, (g.lon.mean(), g.lat.mean()), xytext=(dx, dy), textcoords="offset points", fontsize=7,
                color=INK, ha="right" if dx < 0 else "left",
                bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="none", alpha=0.85), zorder=5)
ax.legend(loc="lower left", fontsize=7, frameon=True, framealpha=0.95)
ax.set_title(f"South-Central Texas: {len(tx)} pediatric dialysis units, {int((tx.state3 == 'ped').sum())} findable as pediatric", loc="left",
             fontsize=10.5, color=INK)
fig.text(0.02, 0.015, "Overture places 2026-08-19.0 vs CMS Dialysis Facility listing (2026-06-16). "
         "Houston and Dallas-Fort Worth: nearest findable\npediatric unit is in Austin, 232 km and 273-290 km away. "
         "Strict test: src/audit_pediatric_matches.py.", fontsize=7, color=INK2)
ax.set_axis_off()
fig.tight_layout(rect=(0, 0.04, 1, 1))
fig.savefig(FIG / "dialysis_pediatric_texas.png", dpi=150)
plt.close(fig)
print("ok")
