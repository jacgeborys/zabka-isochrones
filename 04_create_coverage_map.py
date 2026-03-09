"""
Create Coverage Map from Overlapping Isochrones
Planar subdivision approach:
- Collects all isochrone boundaries
- Polygonizes them into minimal pieces
- Counts overlaps per piece via spatial join
- Dissolves adjacent pieces with the same count
- No tiling, no seams, correct counts everywhere

Usage:
    python 04_create_coverage_map.py <poi_id>
"""
import sys
import geopandas as gpd
import numpy as np
from pathlib import Path
from datetime import datetime
from shapely.ops import unary_union
from shapely.geometry import MultiPolygon, Polygon
import warnings
warnings.filterwarnings('ignore')
import time

# Import make_valid with fallback for older shapely versions
try:
    from shapely.validation import make_valid
except ImportError:
    # Fallback for shapely < 1.8
    def make_valid(geom):
        return geom.buffer(0)

from poi_config import get_poi, poi_files


def fix_geometry_aggressive(geom):
    """Aggressively fix a geometry using multiple techniques"""
    if geom is None or geom.is_empty:
        return None

    try:
        # Step 1: Make valid
        geom = make_valid(geom)

        # Step 2: Buffer(0) to fix self-intersections
        geom = geom.buffer(0)

        # Step 3: Small buffer/unbuffer to fix micro-topology issues
        # Use 0.1m buffer (we're in EPSG:2180 which is in meters)
        geom = geom.buffer(0.1).buffer(-0.1)

        # Step 4: Make valid again
        geom = make_valid(geom)

        # Step 5: Remove tiny holes (< 100 m²)
        if hasattr(geom, 'interiors'):
            # Single polygon
            if len(geom.interiors) > 0:
                exterior = geom.exterior
                holes = [interior for interior in geom.interiors
                        if Polygon(interior).area >= 100]
                geom = Polygon(exterior, holes)
        elif geom.geom_type == 'MultiPolygon':
            # Multiple polygons - also clean holes
            polys = []
            for poly in geom.geoms:
                if poly.area < 100:  # Skip tiny polygons
                    continue
                if hasattr(poly, 'interiors') and len(poly.interiors) > 0:
                    exterior = poly.exterior
                    holes = [interior for interior in poly.interiors
                            if Polygon(interior).area >= 100]
                    polys.append(Polygon(exterior, holes))
                else:
                    polys.append(poly)
            if polys:
                geom = MultiPolygon(polys) if len(polys) > 1 else polys[0]
            else:
                return None

        # Step 6: Final validation
        if not geom.is_valid:
            geom = geom.buffer(0)

        # Check if geometry is reasonable
        if geom.is_empty or geom.area < 10:  # Less than 10 m²
            return None

        return geom

    except Exception as e:
        print(f"      Warning: Could not fix geometry: {e}")
        return None


def create_coverage_map_efficient(isochrones_gdf):
    """
    Planar subdivision approach:
    1. Fix all geometries
    2. Union all boundaries into a planar graph
    3. Polygonize into minimal pieces
    4. Count overlaps per piece via spatial join
    5. Dissolve adjacent pieces with the same count
    """
    from shapely.ops import polygonize

    print("\nCreating coverage map (planar subdivision)...")
    print(f"Processing {len(isochrones_gdf)} isochrones...\n")

    original_crs = isochrones_gdf.crs
    gdf = isochrones_gdf.to_crs("EPSG:2180").copy()

    # Step 1: Fix geometries
    print("Step 1: Fixing geometries...")
    fixed_geoms = []
    failed_count = 0

    for idx, geom in enumerate(gdf.geometry):
        if (idx + 1) % 100 == 0:
            print(f"    Progress: {idx + 1}/{len(gdf)} geometries fixed...")
        fixed = fix_geometry_aggressive(geom)
        if fixed is not None:
            fixed_geoms.append(fixed)
        else:
            failed_count += 1

    if failed_count > 0:
        print(f"  Warning: could not fix {failed_count} geometries")

    if len(fixed_geoms) == 0:
        print("ERROR: All geometries failed validation!")
        return None

    gdf = gpd.GeoDataFrame({'geometry': fixed_geoms}, crs="EPSG:2180")
    print(f"  {len(gdf)} geometries validated\n")

    # Step 2: Build planar graph from all boundary rings
    print("Step 2: Building planar graph from all boundaries...")
    all_rings = []
    for geom in gdf.geometry:
        if geom.geom_type == 'Polygon':
            all_rings.append(geom.exterior)
            all_rings.extend(geom.interiors)
        elif geom.geom_type == 'MultiPolygon':
            for poly in geom.geoms:
                all_rings.append(poly.exterior)
                all_rings.extend(poly.interiors)

    print(f"  Collected {len(all_rings)} boundary rings")
    print(f"  Merging boundaries...")
    planar_graph = unary_union(all_rings)

    # Step 3: Polygonize into minimal pieces
    print("Step 3: Polygonizing into minimal pieces...")
    pieces = list(polygonize(planar_graph))
    print(f"  Created {len(pieces)} minimal polygons\n")

    if len(pieces) == 0:
        print("ERROR: No polygons created from boundaries")
        return None

    # Step 4: Count overlaps via spatial join on representative points
    print("Step 4: Counting overlaps per piece...")
    pieces_gdf = gpd.GeoDataFrame(geometry=pieces, crs="EPSG:2180")

    rep_points = pieces_gdf.geometry.representative_point()
    rep_gdf = gpd.GeoDataFrame(geometry=rep_points, crs="EPSG:2180")

    joined = gpd.sjoin(rep_gdf, gdf[['geometry']], how='left', predicate='within')
    joined = joined.dropna(subset=['index_right'])
    pieces_gdf['num_points'] = pieces_gdf.index.map(
        joined.groupby(joined.index).size()
    ).fillna(0).astype(int)

    pieces_gdf = pieces_gdf[pieces_gdf['num_points'] > 0].copy()
    print(f"  {len(pieces_gdf)} pieces with coverage\n")

    # Step 5: Dissolve adjacent pieces with the same count
    print("Step 5: Merging adjacent pieces with same count...")
    dissolved = pieces_gdf.dissolve(by='num_points').reset_index()
    dissolved = dissolved.explode(index_parts=False).reset_index(drop=True)
    print(f"  {len(dissolved)} polygons after merging\n")

    # Step 6: Final cleanup
    print("Step 6: Final cleanup...")

    dissolved['geometry'] = dissolved.geometry.apply(
        lambda g: make_valid(g.buffer(0)) if g is not None and not g.is_empty else None
    )
    dissolved = dissolved[dissolved.geometry.notna()]
    dissolved = dissolved[~dissolved.geometry.is_empty]
    dissolved = dissolved[dissolved.geometry.is_valid]
    dissolved = dissolved[dissolved.geometry.area > 10]
    dissolved = dissolved[dissolved.geometry.area <= 5_000_000]  # remove gap-filled phantoms (500 ha)

    dissolved['area_ha'] = dissolved.geometry.area / 10000
    dissolved = dissolved[['num_points', 'area_ha', 'geometry']].copy()

    dissolved = dissolved.to_crs(original_crs)
    dissolved = dissolved.sort_values('num_points', ascending=False).reset_index(drop=True)

    print(f"  Final result: {len(dissolved)} polygons\n")
    return dissolved


def main():
    if len(sys.argv) < 2:
        print("Usage: python 04_create_coverage_map.py <poi_id>")
        sys.exit(1)

    poi_id = sys.argv[1]
    poi    = get_poi(poi_id)
    files  = poi_files(poi)

    ISOCHRONES_FILE = files["isochrones"]
    OUTPUT_FILE     = files["coverage"]

    print("=" * 60)
    print(f"{poi['label']} Coverage Map Generator")
    print("Planar Subdivision Method")
    print("=" * 60)
    print(f"Input:  {ISOCHRONES_FILE}")
    print(f"Output: {OUTPUT_FILE}\n")

    # Check if input exists
    if not ISOCHRONES_FILE.exists():
        print(f"Isochrones file not found: {ISOCHRONES_FILE}")
        print(f"\nPlease run: python 03_generate_isochrones_local.py {poi_id}")
        return

    # Load isochrones
    print("Loading isochrones...", end=' ', flush=True)
    isochrones = gpd.read_file(ISOCHRONES_FILE)
    print(f"✓ {len(isochrones)} isochrones loaded")

    # Show initial statistics
    print(f"\nInput statistics:")
    print(f"  • Total isochrones: {len(isochrones)}")
    if 'time_minutes' in isochrones.columns:
        for time_val in sorted(isochrones['time_minutes'].unique()):
            count = len(isochrones[isochrones['time_minutes'] == time_val])
            print(f"  • {time_val} min isochrones: {count}")

    print(f"\nUsing planar subdivision approach (no tiling)")
    print(f"Features:")
    print(f"  • All isochrone boundaries merged into planar graph")
    print(f"  • Polygonized into minimal pieces")
    print(f"  • Overlaps counted via spatial join")
    print(f"  • No tile seams, correct counts everywhere")

    # Start processing
    start_time = datetime.now()

    # Create coverage map
    coverage_gdf = create_coverage_map_efficient(isochrones)

    if coverage_gdf is None or len(coverage_gdf) == 0:
        print("\n✗ Failed to create coverage map")
        return

    # Save result
    print("\nSaving coverage map...", end=' ', flush=True)
    coverage_gdf.to_file(OUTPUT_FILE, driver="GPKG")
    print("✓")

    elapsed = (datetime.now() - start_time).total_seconds()

    # Show results
    print()
    print("=" * 60)
    print(f"Done! Created coverage map in {elapsed/60:.1f} minutes")
    print("=" * 60)

    print(f"\nCoverage statistics:")
    print(f"  • Total polygons: {len(coverage_gdf):,}")
    print(f"  • Max stores reachable: {coverage_gdf['num_points'].max()}")
    print(f"  • Min stores reachable: {coverage_gdf['num_points'].min()}")
    print(f"  • Mean stores reachable: {coverage_gdf['num_points'].mean():.2f}")
    print(f"  • Median stores reachable: {coverage_gdf['num_points'].median():.0f}")

    print(f"\nBreakdown by accessibility level:")
    for num_stores in sorted(coverage_gdf['num_points'].unique(), reverse=True):
        count = len(coverage_gdf[coverage_gdf['num_points'] == num_stores])
        total_area = coverage_gdf[coverage_gdf['num_points'] == num_stores]['area_ha'].sum()
        pct = (count / len(coverage_gdf)) * 100
        print(f"  • {num_stores} store{'s' if num_stores != 1 else ''}: {count:,} polygons ({pct:.1f}%) - {total_area:.1f} ha")

    # Show some statistics about polygon sizes
    print(f"\nPolygon size statistics:")
    print(f"  • Mean area: {coverage_gdf['area_ha'].mean():.4f} ha")
    print(f"  • Median area: {coverage_gdf['area_ha'].median():.4f} ha")
    print(f"  • Total coverage: {coverage_gdf['area_ha'].sum():.1f} ha")

    print(f"\nOutput saved to: {OUTPUT_FILE}")
    print(f"\nVisualization tips for QGIS:")
    print(f"1. Load {OUTPUT_FILE.name}")
    print(f"2. Style → Graduated → Column: num_points")
    print(f"3. Use color ramp: Yellow-Orange-Red")
    print(f"4. Add 40% transparency")
    print()


if __name__ == "__main__":
    main()
