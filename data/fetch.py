#!/usr/bin/env python3
"""Fetch NYC completed solar projects from NYSERDA (data.ny.gov 3x8r-34rs).

Output: solar.json  -> compact array of installs for the animated map.
Each record: [lng, lat, year, kw, sector, dac, boro]
  lng, lat : rounded to 5 decimals (~1m)
  year     : application-received year (int)
  kw       : nameplate kW DC (1 decimal)
  sector   : 0 = Residential, 1 = Non-Residential
  dac      : 1 = inside a NYS Disadvantaged Community, else 0
  boro     : 0 Manhattan, 1 Bronx, 2 Brooklyn, 3 Queens, 4 Staten Island
Also writes summary.json with per-borough / per-year aggregates.
"""
import json, urllib.parse, urllib.request, sys, collections

BASE = "https://data.ny.gov/resource/3x8r-34rs.json"
COUNTIES = ("Bronx", "Kings", "New York", "Queens", "Richmond")
BOROUGH = {"Bronx": "Bronx", "Kings": "Brooklyn", "New York": "Manhattan",
           "Queens": "Queens", "Richmond": "Staten Island"}
BORO_IDX = {"New York": 0, "Bronx": 1, "Kings": 2, "Queens": 3, "Richmond": 4}
WHERE = ("county in('Bronx','Kings','New York','Queens','Richmond') "
         "AND project_status='Complete' AND latitude IS NOT NULL "
         "AND date_application_received IS NOT NULL")
SELECT = ("latitude,longitude,date_application_received,totalnameplatekwdc,"
          "sector,nys_disadvantaged_community_status,county")

def fetch_all():
    rows, offset, page = [], 0, 50000
    while True:
        qs = urllib.parse.urlencode({
            "$select": SELECT, "$where": WHERE,
            "$order": "date_application_received",
            "$limit": page, "$offset": offset})
        with urllib.request.urlopen(f"{BASE}?{qs}", timeout=120) as r:
            chunk = json.load(r)
        rows.extend(chunk)
        print(f"  fetched {len(rows)}", file=sys.stderr)
        if len(chunk) < page:
            break
        offset += page
    return rows

def main():
    rows = fetch_all()
    out = []
    by_boro = collections.defaultdict(lambda: {"n": 0, "kw": 0.0})
    by_year = collections.defaultdict(lambda: {"n": 0, "kw": 0.0})
    dac_n = 0
    for r in rows:
        try:
            lat = round(float(r["latitude"]), 5)
            lng = round(float(r["longitude"]), 5)
        except (KeyError, ValueError, TypeError):
            continue
        # NYC bounding box sanity check
        if not (40.45 <= lat <= 40.95 and -74.30 <= lng <= -73.65):
            continue
        year = int(r["date_application_received"][:4])
        try:
            kw = round(float(r.get("totalnameplatekwdc") or 0), 1)
        except ValueError:
            kw = 0.0
        sector = 0 if (r.get("sector") or "").startswith("Res") else 1
        dac = 1 if (r.get("nys_disadvantaged_community_status") or "") == "Inside a NYS DAC" else 0
        boro_i = BORO_IDX.get(r.get("county"), 0)
        out.append([lng, lat, year, kw, sector, dac, boro_i])
        boro = BOROUGH.get(r.get("county"), r.get("county"))
        by_boro[boro]["n"] += 1
        by_boro[boro]["kw"] += kw
        by_year[year]["n"] += 1
        by_year[year]["kw"] += kw
        dac_n += dac

    out.sort(key=lambda x: x[2])  # by year for clean cumulative animation
    with open("solar.json", "w") as f:
        json.dump(out, f, separators=(",", ":"))

    summary = {
        "total": len(out),
        "total_mw": round(sum(x[3] for x in out) / 1000, 1),
        "dac_share": round(100 * dac_n / len(out), 1),
        "by_borough": {k: {"n": v["n"], "mw": round(v["kw"] / 1000, 1)}
                       for k, v in by_boro.items()},
        "by_year": {str(k): {"n": v["n"], "mw": round(v["kw"] / 1000, 1)}
                    for k, v in sorted(by_year.items())},
        "years": sorted(by_year),
    }
    with open("summary.json", "w") as f:
        json.dump(summary, f, indent=2)
    print(f"wrote solar.json ({len(out)} pts), summary.json", file=sys.stderr)
    print(json.dumps(summary["by_borough"], indent=2))
    print("total MW:", summary["total_mw"], "| DAC share %:", summary["dac_share"])

if __name__ == "__main__":
    main()
