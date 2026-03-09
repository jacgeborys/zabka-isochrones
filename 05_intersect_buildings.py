"""
Intersect Buildings with POI Coverage Map
Finds all buildings that fall within the coverage area.
Uses BDOT10k building data for accurate classification.

Usage:
    python 05_intersect_buildings.py <poi_id>
"""
import sys
import geopandas as gpd
from pathlib import Path
from datetime import datetime

from poi_config import get_poi, poi_files, DATA_DIR

# Use BDOT buildings for proper classification (not OSM buildings)
BUILDINGS_FILE = DATA_DIR / "bdot" / "bdot_buildings_warsaw.gpkg"


def main():
    if len(sys.argv) < 2:
        print("Usage: python 05_intersect_buildings.py <poi_id>")
        sys.exit(1)

    poi_id = sys.argv[1]
    poi    = get_poi(poi_id)
    files  = poi_files(poi)

    COVERAGE_FILE = files["coverage"]
    OUTPUT_FILE   = files["buildings"]

    print("=" * 60)
    print(f"Buildings Near {poi['label']} Coverage Intersector")
    print("=" * 60)
    print(f"Buildings:    {BUILDINGS_FILE}")
    print(f"Coverage map: {COVERAGE_FILE}")
    print(f"Output:       {OUTPUT_FILE}\n")

    # Check if input files exist
    if not BUILDINGS_FILE.exists():
        print(f"Buildings file not found: {BUILDINGS_FILE}")
        return

    if not COVERAGE_FILE.exists():
        print(f"Coverage map file not found: {COVERAGE_FILE}")
        print(f"\nPlease run: python 04_create_coverage_map.py {poi_id}")
        return

    start_time = datetime.now()

    # Load coverage map
    print("Loading coverage map...", end=' ', flush=True)
    coverage = gpd.read_file(COVERAGE_FILE)
    print(f"✓ {len(coverage)} polygons loaded")

    # Load buildings
    print("Loading buildings...", end=' ', flush=True)
    buildings = gpd.read_file(BUILDINGS_FILE)
    print(f"✓ {len(buildings):,} buildings loaded")

    # Ensure same CRS
    print("\nEnsuring same coordinate system...", end=' ', flush=True)
    if buildings.crs != coverage.crs:
        coverage = coverage.to_crs(buildings.crs)
        print(f"✓ (converted to {buildings.crs})")
    else:
        print("✓")

    # Spatial join to find buildings within coverage and get attributes
    print("\nFinding buildings within coverage area and joining attributes...", end=' ', flush=True)
    buildings_with_coverage = gpd.sjoin(
        buildings,
        coverage[['num_points', 'area_ha', 'geometry']],
        how='inner',  # Only keep buildings that intersect coverage
        predicate='intersects'
    )
    print(f"✓ {len(buildings_with_coverage):,} intersections found")

    if len(buildings_with_coverage) == 0:
        print("\n⚠ No buildings found in coverage area!")
        return

    # If a building intersects multiple coverage polygons, keep the one with highest num_points
    print("Selecting best coverage for each building...", end=' ', flush=True)
    buildings_with_coverage = buildings_with_coverage.sort_values('num_points', ascending=False)

    # Get unique buildings (before deduplication count)
    total_intersections = len(buildings_with_coverage)

    # Drop duplicates - keep first (highest num_points due to sort)
    buildings_with_coverage = buildings_with_coverage.drop_duplicates(subset='geometry', keep='first')
    unique_buildings = len(buildings_with_coverage)
    print(f"✓ ({unique_buildings:,} unique buildings)")

    # Clean up columns
    if 'index_right' in buildings_with_coverage.columns:
        buildings_with_coverage = buildings_with_coverage.drop(columns=['index_right'])

    # Save result
    print(f"\nSaving to {OUTPUT_FILE.name}...", end=' ', flush=True)
    buildings_with_coverage.to_file(OUTPUT_FILE, driver="GPKG")
    print("✓")

    elapsed = (datetime.now() - start_time).total_seconds()

    # Show results
    print()
    print("=" * 60)
    print(f"Done! Completed in {elapsed:.1f} seconds")
    print("=" * 60)

    print(f"\nResults:")
    print(f"  • Total buildings in dataset: {len(buildings):,}")
    print(f"  • Buildings in coverage area: {unique_buildings:,}")
    print(f"  • Percentage covered: {unique_buildings/len(buildings)*100:.1f}%")
    print(f"  • Total intersections (before dedup): {total_intersections:,}")

    if 'num_points' in buildings_with_coverage.columns:
        print(f"\nBuildings by {poi['label']} accessibility:")
        for num_poi in sorted(buildings_with_coverage['num_points'].dropna().unique(), reverse=True):
            count = len(buildings_with_coverage[buildings_with_coverage['num_points'] == num_poi])
            pct = count / unique_buildings * 100
            print(f"  • Reachable from {int(num_poi)} {poi['label']}(s): {count:,} buildings ({pct:.1f}%)")

    print(f"\nOutput saved to: {OUTPUT_FILE}")
    print()


if __name__ == "__main__":
    main()
