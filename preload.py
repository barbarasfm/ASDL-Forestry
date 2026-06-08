"""
preload.py  ─  Run ONCE before launching dashboard.py
=======================================================
Builds two cache files that let the dashboard start instantly
without any geocoding or OSRM calls at runtime:

    cache/county_coords.csv     lat/lon centroid for every GA county that
                                appears in ANY of the three biomass datasets.
                                Geocoded via Nominatim (OSM), ~1 req/s.

    cache/mill_distances.csv    Wide table.  One row per county; one column
                                per operating GA mill (road miles, one-way).
                                Also stores residue supply for each source:
                                  forest_kdry_metric  k metric dry t/yr
                                  mill_kdry_metric    k metric dry t/yr
                                  pulpwood_kdry_metric k metric dry t/yr   (converted from short dry tons)
                                  pulpwood_kdry_metric converted to metric

RUN:
    python preload.py

RESTART-SAFE:
    county_coords.csv: if file exists, geocoding is skipped entirely.
    mill_distances.csv: new mills are appended incrementally; already-
    computed mill columns are skipped.  Safe to Ctrl-C and re-run.

DATA SOURCES (expected in same directory as this script):
    Forest_Residues.csv      County, State, Thousand Dry Tonnes/Yr
    Mill_Residues.csv        County, State, Thousand Dry Tonnes/Yr
    Pulpwood_Residues.xlsx   County Name, Total MCF Vol,
                             Total Mass (dry tons x 1000)
    GA_Mills.xlsx            Mill site, Company name, Status, State,
                             X Coord. (lon), Y Coord. (lat)
"""

import argparse
import math
import os
import time

import pandas as pd
import requests
from geopy.geocoders import Nominatim

# ─── Constants ───────────────────────────────────────────────────────────────
METERS_PER_MILE   = 1_609.34
OSRM_BASE         = "http://router.project-osrm.org"

# Georgia bounding box for filtering mills with bad coordinates
GA_LAT_RANGE = (30.3, 35.1)
GA_LON_RANGE = (-85.7, -80.8)

# Unit conversion: 1 US short dry ton = 0.907185 metric dry tonne
SHORT_TON_TO_METRIC = 0.907185


# ─────────────────────────────────────────────────────────────────────────────
# STEP 1: Collect unique GA county names from all three biomass datasets
# ─────────────────────────────────────────────────────────────────────────────

def collect_ga_counties(forest_path, mill_path, pulpwood_path):
    """
    Return sorted list of unique Georgia county names that appear in any
    of the three biomass data files with non-zero supply.
    Union ensures every county on any map gets a geocoded coordinate.
    """
    names = set()

    # Forest residues: filter State==Georgia and non-zero supply
    fr = pd.read_csv(forest_path)
    fr.columns = fr.columns.str.strip()
    ga_fr = fr[(fr["State"] == "Georgia") & (fr["Thousand Dry Tonnes/Yr"] > 0)]
    names.update(ga_fr["County"].str.strip())
    print(f"  Forest   : {len(ga_fr)} GA counties with non-zero residue")

    # Mill residues: same column structure as forest
    mr = pd.read_csv(mill_path)
    mr.columns = mr.columns.str.strip()
    ga_mr = mr[(mr["State"] == "Georgia") & (mr["Thousand Dry Tonnes/Yr"] > 0)]
    names.update(ga_mr["County"].str.strip())
    print(f"  Mill     : {len(ga_mr)} GA counties with non-zero residue")

    # Pulpwood: already Georgia-only; column is "County Name" not "County"
    pw = pd.read_excel(pulpwood_path)
    pw.columns = [c.strip() for c in pw.columns]
    ga_pw = pw[pw["Total Mass (dry tons x 1000)"] > 0]
    names.update(ga_pw["County Name"].str.strip())
    print(f"  Pulpwood : {len(ga_pw)} GA counties with non-zero supply")

    result = sorted(names)
    print(f"\n  -> {len(result)} unique GA counties to geocode")
    return result


# ─────────────────────────────────────────────────────────────────────────────
# STEP 2: Geocode county centroids via Nominatim
# ─────────────────────────────────────────────────────────────────────────────

def geocode_counties(counties, cache_dir):
    """
    Geocode county names to lat/lon via Nominatim (OSM).
    Saves cache/county_coords.csv.  Skips if file already exists.
    Sleeps 1.1s between requests to respect Nominatim rate limit.
    """
    out_path = os.path.join(cache_dir, "county_coords.csv")

    if os.path.exists(out_path):
        print(f"  county_coords.csv already exists -- skipping (delete to refresh)")
        return pd.read_csv(out_path)

    print(f"\n  Geocoding {len(counties)} counties (~{len(counties)*1.1/60:.0f} min)...")
    geo  = Nominatim(user_agent="ga_biomass_dashboard_v4_preload")
    rows = []

    for i, county in enumerate(counties):
        try:
            loc = geo.geocode(f"{county} County, Georgia, USA", timeout=10)
            if loc:
                rows.append({
                    "county": county,
                    "lat":    round(loc.latitude,  6),
                    "lon":    round(loc.longitude, 6),
                    "status": "ok",
                })
                print(f"  [{i+1:3d}/{len(counties)}]  OK   {county}")
            else:
                rows.append({"county": county, "lat": None, "lon": None,
                             "status": "not_found"})
                print(f"  [{i+1:3d}/{len(counties)}]  MISS {county}")
        except Exception as e:
            rows.append({"county": county, "lat": None, "lon": None,
                         "status": f"error: {e}"})

        time.sleep(1.1)   # Nominatim rate limit: 1 req/s

    df = pd.DataFrame(rows)
    df.to_csv(out_path, index=False)
    ok = (df["status"] == "ok").sum()
    print(f"\n  Geocoded {ok}/{len(df)} counties.  Saved -> {out_path}")
    return df


# ─────────────────────────────────────────────────────────────────────────────
# STEP 3: Compute road distances via OSRM Table API (one HTTP call per mill)
# ─────────────────────────────────────────────────────────────────────────────

def haversine_miles(lat1, lon1, lat2, lon2):
    """Straight-line distance in miles; multiplied by 1.3 as road proxy."""
    R  = 3_958.8
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a  = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2 * R * math.asin(math.sqrt(a))


def compute_mill_distances(mills_path, coords_df, cache_dir):
    """
    For each operating GA mill, compute road distances (miles, one-way)
    to every geocoded county using OSRM Table API.
    Saves incrementally after each mill so Ctrl-C is safe.
    Falls back to haversine*1.3 if OSRM is unavailable.
    """
    out_path = os.path.join(cache_dir, "mill_distances.csv")

    # Load mills, filter operating GA mills with valid coordinates
    mills = pd.read_excel(mills_path)
    mills.columns = [c.replace("\n", " ").strip() for c in mills.columns]
    mills = mills[(mills["Status"] == "Operating") & (mills["State"] == "GA")].copy()
    mills = mills.rename(columns={"X Coord.": "longitude", "Y Coord.": "latitude"})
    mills["mill_label"] = (mills["Mill site"].str.strip()
                           + " -- " + mills["Company name"].str.strip())
    valid = (mills["latitude"].between(*GA_LAT_RANGE)
             & mills["longitude"].between(*GA_LON_RANGE))
    mills = mills[valid].reset_index(drop=True)
    print(f"\n  {len(mills)} operating GA mills with valid coordinates")

    # Only geocoded-OK counties get distance rows
    ok_coords = coords_df[coords_df["status"] == "ok"].copy().reset_index(drop=True)

    # Column names that are NOT mill distance columns
    non_mill = {"county", "lat", "lon", "forest_kdry_metric", "mill_kdry_metric",
                "pulpwood_kdry_metric", "status"}

    # Load existing partial cache for incremental mode
    if os.path.exists(out_path):
        base_df    = pd.read_csv(out_path)
        done_mills = [c for c in base_df.columns if c not in non_mill]
        remaining  = mills[~mills["mill_label"].isin(done_mills)]
        print(f"  {len(done_mills)} mills cached; computing {len(remaining)} remaining")
    else:
        base_df   = ok_coords[["county", "lat", "lon", "status"]].copy()
        remaining = mills

    if remaining.empty:
        print(f"  All mills already cached -> {out_path}")
        return base_df

    for _, mrow in remaining.iterrows():
        label    = mrow["mill_label"]
        mill_lat = float(mrow["latitude"])
        mill_lon = float(mrow["longitude"])
        print(f"  Mill: {label}")

        # OSRM Table: mill at index 0 (source), counties at indices 1..N
        # OSRM expects lon,lat order
        coord_pairs  = f"{mill_lon},{mill_lat}"
        for _, row in ok_coords.iterrows():
            coord_pairs += f";{row['lon']},{row['lat']}"
        dest_idx = ";".join(str(i+1) for i in range(len(ok_coords)))
        url = (f"{OSRM_BASE}/table/v1/driving/{coord_pairs}"
               f"?sources=0&destinations={dest_idx}&annotations=distance")

        try:
            resp = requests.get(url, timeout=60).json()
            if resp.get("code") == "Ok":
                # distances[0] = metres from mill to each county
                dist_miles = [
                    round(d / METERS_PER_MILE, 2) if d is not None else None
                    for d in resp["distances"][0]
                ]
            else:
                raise ValueError(resp.get("message", "OSRM error"))
        except Exception as e:
            print(f"    OSRM failed ({e}) -- haversine*1.3 fallback")
            dist_miles = [
                round(haversine_miles(mill_lat, mill_lon,
                                      float(r["lat"]), float(r["lon"])) * 1.3, 2)
                for _, r in ok_coords.iterrows()
            ]

        # Add this mill as a column and save
        ok_coords[label] = dist_miles
        base_df = base_df.merge(ok_coords[["county", label]], on="county", how="left")
        base_df.to_csv(out_path, index=False)
        print(f"    Saved -> {out_path}")
        time.sleep(0.5)

    return base_df


# ─────────────────────────────────────────────────────────────────────────────
# STEP 4: Merge residue supply columns into the distance cache
# ─────────────────────────────────────────────────────────────────────────────

def merge_residue_columns(forest_path, mill_path, pulpwood_path, dist_df, cache_dir):
    """
    Joins forest, mill, and pulpwood supply onto the distance table.
    Counties missing data for a source get 0.0 (not NaN).
    Also stores pulpwood_kdry_metric (= short * 0.907185) for unit consistency.
    """
    out_path = os.path.join(cache_dir, "mill_distances.csv")

    # Forest residues (already k metric dry t/yr)
    fr = pd.read_csv(forest_path)
    fr.columns = fr.columns.str.strip()
    ga_fr = (fr[(fr["State"] == "Georgia") & (fr["Thousand Dry Tonnes/Yr"] > 0)]
             .rename(columns={"County": "county",
                               "Thousand Dry Tonnes/Yr": "forest_kdry_metric"})
             [["county", "forest_kdry_metric"]]
             .assign(county=lambda d: d["county"].str.strip()))

    # Mill residues (already k metric dry t/yr)
    mr = pd.read_csv(mill_path)
    mr.columns = mr.columns.str.strip()
    ga_mr = (mr[(mr["State"] == "Georgia") & (mr["Thousand Dry Tonnes/Yr"] > 0)]
             .rename(columns={"County": "county",
                               "Thousand Dry Tonnes/Yr": "mill_kdry_metric"})
             [["county", "mill_kdry_metric"]]
             .assign(county=lambda d: d["county"].str.strip()))

    # Pulpwood: source unit is "Total Mass (dry tons x 1000)" = k US short dry tons.
    # Convert directly to k metric dry tonnes (x 0.907185).
    # pulpwood_kdry_short is NOT stored in the cache — only the metric value is
    # needed for all weighted-average distance and supply calculations.
    pw = pd.read_excel(pulpwood_path)
    pw.columns = [c.strip() for c in pw.columns]
    pw = pw[pw["Total Mass (dry tons x 1000)"] > 0].copy()
    pw["county"]               = pw["County Name"].str.strip()
    pw["pulpwood_kdry_metric"] = pw["Total Mass (dry tons x 1000)"] * SHORT_TON_TO_METRIC
    pw = pw[["county", "pulpwood_kdry_metric"]]

    # Drop existing residue columns to avoid duplicates on re-run.
    # Also drop pulpwood_kdry_short if it exists from an old cache run.
    merged = dist_df.copy()
    for col in ["forest_kdry_metric", "mill_kdry_metric",
                "pulpwood_kdry_metric", "pulpwood_kdry_short"]:
        if col in merged.columns:
            merged = merged.drop(columns=[col])

    # Left-join: every geocoded county kept; counties with no supply get 0.0
    merged = merged.merge(ga_fr, on="county", how="left")
    merged = merged.merge(ga_mr, on="county", how="left")
    merged = merged.merge(pw,    on="county", how="left")
    for col in ["forest_kdry_metric", "mill_kdry_metric", "pulpwood_kdry_metric"]:
        merged[col] = merged[col].fillna(0.0)

    # Reorder columns: metadata | three residue cols | one col per mill
    res_cols  = ["forest_kdry_metric", "mill_kdry_metric", "pulpwood_kdry_metric"]
    non_mill  = {"county", "lat", "lon", "status"} | set(res_cols)
    mill_cols = [c for c in merged.columns if c not in non_mill]
    merged    = merged[["county", "lat", "lon"] + res_cols + mill_cols]
    merged.to_csv(out_path, index=False)

    print(f"\n  Residue totals in cache:")
    print(f"    Forest   : {merged['forest_kdry_metric'].sum():>10,.1f} k metric dry t/yr")
    print(f"    Mill     : {merged['mill_kdry_metric'].sum():>10,.1f} k metric dry t/yr")
    print(f"    Pulpwood : {merged['pulpwood_kdry_metric'].sum():>10,.1f} k metric dry t/yr")
    print(f"  Saved -> {out_path}")
    return merged


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Pre-compute geocodes and OSRM road distances for GA biomass dashboard."
    )
    parser.add_argument("--forest",   default="Locations/Forest_Residues.csv")
    parser.add_argument("--mill",     default="Locations/Mill_Residues.csv")
    parser.add_argument("--pulpwood", default="Locations/Pulpwood_Residues.xlsx")
    parser.add_argument("--ga_mills", default="Locations/GA_Mills.xlsx")
    parser.add_argument("--cache",    default="cache")
    args = parser.parse_args()

    os.makedirs(args.cache, exist_ok=True)

    print("=" * 65)
    print("  Georgia Biomass Dashboard -- Pre-computation (v4)")
    print("=" * 65)

    print("\n[1/4] Collecting county names...")
    counties = collect_ga_counties(args.forest, args.mill, args.pulpwood)

    print("\n[2/4] Geocoding counties...")
    coords_df = geocode_counties(counties, args.cache)

    print("\n[3/4] Computing road distances via OSRM...")
    dist_df = compute_mill_distances(args.ga_mills, coords_df, args.cache)

    print("\n[4/4] Merging residue data into cache...")
    merge_residue_columns(args.forest, args.mill, args.pulpwood, dist_df, args.cache)

    print("\n" + "=" * 65)
    print("  Done!  Now run:  streamlit run dashboard.py")
    print("=" * 65)