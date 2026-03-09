"""
Fetch Points of Interest in Warsaw
Config-driven downloader for any POI type from OpenStreetMap via Overpass API.

Usage:
    python 01_fetch_poi_osm.py <poi_id>           # with confirmation prompt
    python 01_fetch_poi_osm.py <poi_id> --force   # overwrite without prompting
"""
import sys
import requests
import geopandas as gpd
from shapely.geometry import Point
from datetime import datetime

from poi_config import (
    get_poi, poi_files, sanitize_col,
    WARSAW_BBOX, OVERPASS_URLS, POIS,
)


def build_overpass_query(osm_filters, bbox_str):
    """
    Build an Overpass QL union query from a list of tag-filter dicts.
    Tags within a dict are ANDed; multiple dicts produce separate node/way lines (OR).
    """
    lines = []
    for filter_dict in osm_filters:
        tag_str = "".join(f'["{k}"="{v}"]' for k, v in filter_dict.items())
        lines.append(f'  node{tag_str}({bbox_str});')
        lines.append(f'  way{tag_str}({bbox_str});')
    return f'[out:json][timeout:60];\n(\n' + '\n'.join(lines) + '\n);\nout center;\n'


def fetch_pois(poi_config, bbox):
    bbox_str = f"{bbox['south']},{bbox['west']},{bbox['north']},{bbox['east']}"
    query = build_overpass_query(poi_config["osm_filters"], bbox_str)
    label = poi_config["label"]

    print(f"Querying Overpass API for {label} in Warsaw...")
    print(f"Filters: {poi_config['osm_filters']}\n")

    headers = {
        'User-Agent': 'QGIS-Warsaw-Analysis/1.0',
        'Accept': 'application/json',
    }

    response = None
    for url in OVERPASS_URLS:
        try:
            print(f"  Trying {url}...")
            response = requests.post(url, data={'data': query}, headers=headers, timeout=90)
            if response.status_code == 200:
                break
            print(f"  HTTP {response.status_code}, trying next endpoint...")
        except requests.exceptions.Timeout:
            print(f"  Timeout, trying next endpoint...")
        except Exception as e:
            print(f"  Error: {e}, trying next endpoint...")

    if response is None or response.status_code != 200:
        print("All endpoints failed.")
        return None

    try:
        data = response.json()
    except ValueError as e:
        print(f"JSON parse error: {e}")
        print(f"Response text: {response.text[:200]}")
        return None

    elements = data.get('elements', [])
    print(f"Received {len(elements)} results from Overpass API\n")

    if not elements:
        print(f"No {label} found!")
        return None

    extra_keys = poi_config.get("extra_attributes", [])
    fetch_all_tags = poi_config.get("fetch_all_tags", False)
    records = []
    for element in elements:
        if element['type'] == 'node':
            lat, lon = element['lat'], element['lon']
        elif element['type'] == 'way' and 'center' in element:
            lat, lon = element['center']['lat'], element['center']['lon']
        else:
            continue

        tags = element.get('tags', {})
        record = {
            'osm_id':   element['id'],
            'osm_type': element['type'],
            'name':     tags.get('name'),
            'geometry': Point(lon, lat),
        }

        if fetch_all_tags:
            # Store ALL tags from OSM data for analysis
            for key, value in tags.items():
                col_name = sanitize_col(key)
                if col_name not in record:  # Don't overwrite core columns
                    record[col_name] = value
        else:
            # Only fetch specified extra attributes
            for key in extra_keys:
                record[sanitize_col(key)] = tags.get(key)

        records.append(record)

    return records


def main():
    if len(sys.argv) < 2:
        print("Usage: python 01_fetch_poi_osm.py <poi_id> [--force]")
        print("\nAvailable POIs:")
        for p in POIS:
            status = "enabled" if p["enabled"] else "disabled"
            print(f"  {p['id']:<20} {p['label']} ({status})")
        sys.exit(1)

    poi_id = sys.argv[1]
    force  = "--force" in sys.argv
    poi    = get_poi(poi_id)
    files  = poi_files(poi)
    output_file = files["stores"]

    print("=" * 60)
    print(f"{poi['label']} Fetcher for Warsaw")
    print("=" * 60)
    print(f"Output: {output_file}\n")

    if output_file.exists() and not force:
        resp = input("Output file already exists. Delete and re-fetch? (y/n): ")
        if resp.lower() != 'y':
            print("Keeping existing data.")
            return

    start_time = datetime.now()
    records = fetch_pois(poi, WARSAW_BBOX)

    if not records:
        print("No POIs fetched!")
        return

    print(f"Creating GeoDataFrame...", end=' ', flush=True)
    gdf = gpd.GeoDataFrame(records, crs="EPSG:4326")

    # Filter out library return lockers for parcel_locker POI type
    if poi_id == "parcel_locker":
        before_count = len(gdf)
        if 'operator' in gdf.columns:
            # Exclude any parcel lockers with 'Biblio' in operator field
            gdf = gdf[~gdf['operator'].fillna('').str.contains('Biblio', case=False, na=False)]
            filtered_count = before_count - len(gdf)
            if filtered_count > 0:
                print(f"\n  Filtered out {filtered_count} library return lockers (Biblio)", end=' ')

    # Filter for elementary schools only (schools with "podstaw" in name)
    if poi_id == "elementary_school":
        before_count = len(gdf)
        if 'name' in gdf.columns:
            # Keep only schools with 'podstaw' in name (case-insensitive)
            gdf = gdf[gdf['name'].fillna('').str.contains('podstaw', case=False, na=False)]
            filtered_count = before_count - len(gdf)
            if filtered_count > 0:
                print(f"\n  Kept only elementary schools (podstaw): {len(gdf)}/{before_count}", end=' ')

    # Merge nearby churches (within 50m) to deduplicate building + symbol
    if poi_id == "church" and len(gdf) > 0:
        before_count = len(gdf)
        # Convert to metric CRS for accurate distance calculation
        gdf_metric = gdf.to_crs("EPSG:2180")

        # Sort by osm_id for reproducibility
        gdf_metric = gdf_metric.sort_values('osm_id').reset_index(drop=True)

        # Track which churches to keep
        keep_indices = []
        for idx in range(len(gdf_metric)):
            # Check if this church is too close to any already-kept church
            too_close = False
            current_point = gdf_metric.iloc[idx].geometry

            for keep_idx in keep_indices:
                kept_point = gdf_metric.iloc[keep_idx].geometry
                if current_point.distance(kept_point) <= 50:  # 50 meters
                    too_close = True
                    break

            if not too_close:
                keep_indices.append(idx)

        # Keep only the selected churches
        gdf = gdf.iloc[keep_indices].reset_index(drop=True)
        merged_count = before_count - len(gdf)
        if merged_count > 0:
            print(f"\n  Merged {merged_count} duplicate churches (within 50m)", end=' ')

    gdf['poi_id'] = range(1, len(gdf) + 1)
    print(f"{len(gdf)} POIs")

    # Ordered columns: poi_id, name, osm_id, osm_type, extra attrs, geometry
    # Exclude any extra_attribute that duplicates a core column (e.g. "name")
    core_cols  = ['poi_id', 'name', 'osm_id', 'osm_type']

    if poi.get("fetch_all_tags", False):
        # Keep all columns when fetching all tags
        all_cols = [c for c in gdf.columns if c not in ['geometry']]
        # Reorder to put core columns first, then alphabetically sort the rest
        other_cols = sorted([c for c in all_cols if c not in core_cols])
        ordered = [c for c in core_cols if c in gdf.columns] + other_cols
    else:
        # Only keep specified extra attributes
        extra_cols = [sanitize_col(k) for k in poi.get("extra_attributes", [])
                      if sanitize_col(k) not in core_cols]
        ordered = [c for c in core_cols + extra_cols if c in gdf.columns]

    gdf = gdf[ordered + ['geometry']]

    print(f"Saving to {output_file.name}...", end=' ', flush=True)
    gdf.to_file(output_file, driver="GPKG", layer=f"{poi_id}_stores")
    elapsed = (datetime.now() - start_time).total_seconds()
    print("Done")

    print()
    print("=" * 60)
    print(f"{len(gdf)} {poi['label']} locations saved")
    print("=" * 60)
    print(f"Time:   {elapsed:.1f}s")
    print(f"Output: {output_file}")
    print()

    print("Sample records:")
    for _, row in gdf.head(5).iterrows():
        print(f"  {row['poi_id']}. {row.get('name') or '(no name)'}")
    if len(gdf) > 5:
        print(f"  ... and {len(gdf) - 5} more")
    print()


if __name__ == "__main__":
    main()
