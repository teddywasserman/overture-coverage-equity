"""Strict audit of the 12 pediatric dialysis units (run after discovery_dialysis.py).

discovery_dialysis.py calls a facility "mapped_dialysis" when ANY place with a dialysis-like name or
category lies within 250 m, or shares its phone number. That rule is fair for adult patients, since
any adult clinic next door is a substitute. It is lenient for children: an adult DaVita 87 m from a
pediatric unit makes the pediatric unit look "findable" when it is not.

This script lists every Overture place the rule matched to each pediatric unit and applies a
stricter, still fully automatic, test:
  pediatric_listing   a matched place whose NAME marks it as pediatric
                      (child / pediatric / kids / Cook Children's / Driscoll / Dell Children's)
  findable_strict     such a pediatric listing carries dialysis_clinic as primary or alternate category
Output: outputs/pediatric_match_audit.csv and a printed table.
"""
from __future__ import annotations

import re

import numpy as np
import pandas as pd

from common import OUT, connect, ref
from discovery_dialysis import DIAL_RE, phone10

PED_RE = re.compile(r"child|pediatric|\bkids?\b|cook children|driscoll|dell children", re.I)


def main():
    d = pd.read_csv(OUT / "dialysis_pediatric_units.csv", dtype={"GEOID": str, "ccn": str})
    con = connect()
    rows = []
    for r in d.region.unique():
        pois = con.sql(f"""
            SELECT names."primary" AS name, categories."primary" AS cat,
                   coalesce(categories.alternate, []) AS alt, coalesce(phones, []) AS phones,
                   ST_X(geometry) AS lon, ST_Y(geometry) AS lat
            FROM '{ref(r, 'overture-pois.parquet')}'""").df()
        pois["is_dial_cat"] = pois["cat"].eq("dialysis_clinic") | pois["alt"].map(lambda a: "dialysis_clinic" in list(a))
        pois["dial"] = pois["is_dial_cat"] | pois["name"].fillna("").str.contains(DIAL_RE)
        pois["p10"] = pois["phones"].map(lambda L: {phone10(x) for x in L} - {None})
        for _, x in d[d.region == r].iterrows():
            lat0 = np.deg2rad(x.lat)
            dist = np.hypot((np.deg2rad(pois.lon.values) - np.deg2rad(x.lon)) * 6371000 * np.cos(lat0),
                            (np.deg2rad(pois.lat.values) - np.deg2rad(x.lat)) * 6371000)
            p10 = phone10(x["Telephone Number"])
            m = ((dist <= 250) & pois["dial"].values) | pois["p10"].map(lambda s: p10 in s).values
            hit = pois[m].assign(dist_m=dist[m].round()).sort_values("dist_m")
            ped = hit[hit["name"].fillna("").str.contains(PED_RE)]
            rows.append({
                "ccn": x.ccn, "facility": x["Facility Name"], "city": x["City/Town"], "status_auto": x.status,
                "matched_places": " | ".join(f"{n} [{c}] {int(dm)} m" for n, c, dm in zip(hit["name"], hit["cat"], hit["dist_m"])),
                "pediatric_listing": len(ped) > 0,
                "findable_strict": bool(ped["is_dial_cat"].any()),
            })
    out = pd.DataFrame(rows)
    out.to_csv(OUT / "pediatric_match_audit.csv", index=False)
    print(out[["facility", "status_auto", "pediatric_listing", "findable_strict"]].to_markdown(index=False))
    print(f"\nfindable under the automated rule: {(out.status_auto == 'mapped_dialysis').sum()}/{len(out)}; "
          f"findable as a PEDIATRIC dialysis_clinic (strict): {out.findable_strict.sum()}/{len(out)}")


if __name__ == "__main__":
    main()
