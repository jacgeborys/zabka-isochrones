"""
Generate Walking Isochrones for Points of Interest - Local Version
Uses OSMnx to build walking network and calculate isochrones locally.
No API limits, full control, more accurate for Warsaw's street network.

Usage:
    python 03_generate_isochrones_local.py <poi_id>
"""
import sys
import geopandas as gpd
import pandas as pd
import osmnx as ox
import networkx as nx
from pathlib import Path
from datetime import datetime
from shapely.geometry import Point, Polygon, MultiPolygon
from shapely.ops import unary_union
import numpy as np

from poi_config import get_poi, poi_files, sanitize_col, NETWORK_DIR, WALKING_SPEED

NETWORK_FILE  = NETWORK_DIR / "warsaw_walking_network.graphml"
NETWORK_CACHE = NETWORK_DIR / "warsaw_walking_network.pkl"


def load_network():
    """Load pre-downloaded walking network. Try pickle first, fall back to GraphML."""
    import pickle

    if NETWORK_CACHE.exists():
        print(f"Loading network from cache...", end=' ', flush=True)
        try:
            with open(NETWORK_CACHE, 'rb') as f:
                G = pickle.load(f)
            print(f"{len(G.nodes):,} nodes, {len(G.edges):,} edges")
            return G
        except Exception as e:
            print(f"Cache failed: {e}")

    if NETWORK_FILE.exists():
        print(f"Loading network from GraphML...", end=' ', flush=True)
        try:
            G = ox.load_graphml(NETWORK_FILE)
            print(f"{len(G.nodes):,} nodes, {len(G.edges):,} edges")
            return G
        except Exception as e:
            print(f"{e}")
            return None

    print(f"Network not found!")
    print(f"\nPlease run 02_fetch_walking_network.py first to download the network.")
    return None


def create_isochrone(G, poi_point, distance_m, poi_name):
    """
    Create isochrone polygon from a POI point.

    Args:
        G: NetworkX graph
        poi_point: Shapely Point (WGS84)
        distance_m: Maximum walking distance in meters
        poi_name: For logging

    Returns:
        Shapely polygon or None
    """
    try:
        nearest_node = ox.distance.nearest_nodes(G, poi_point.x, poi_point.y)

        # Skip if nearest node is too far away (POI outside network area).
        # Project both points to EPSG:2180 for an exact metric distance.
        node_data    = G.nodes[nearest_node]
        node_pt      = Point(node_data['x'], node_data['y'])
        poi_metric   = gpd.GeoSeries([poi_point], crs="EPSG:4326").to_crs("EPSG:2180").iloc[0]
        node_metric  = gpd.GeoSeries([node_pt],   crs="EPSG:4326").to_crs("EPSG:2180").iloc[0]
        node_dist    = poi_metric.distance(node_metric)
        if node_dist > 500:
            print(f"\n    Skipping {poi_name}: nearest node is {node_dist:.0f} m away")
            return None

        subgraph = nx.ego_graph(G, nearest_node, radius=distance_m, distance='length')

        if len(subgraph.nodes) == 0:
            print(f"\n    Skipping {poi_name}: no reachable nodes")
            return None

        node_points = [Point(G.nodes[n]['x'], G.nodes[n]['y']) for n in subgraph.nodes()]

        if len(node_points) < 3:
            print(f"\n    Skipping {poi_name}: only {len(node_points)} reachable nodes")
            return None

        # Buffer nodes (intersections)
        nodes_gdf    = gpd.GeoSeries(node_points, crs="EPSG:4326")
        nodes_metric = nodes_gdf.to_crs("EPSG:2180")
        buffered_nodes = nodes_metric.buffer(50)  # 50 m buffer per node

        # Also buffer edges (street segments) to fill gaps on long straight roads
        from shapely.geometry import LineString
        edge_lines = []
        for u, v in subgraph.edges():
            u_pt = Point(G.nodes[u]['x'], G.nodes[u]['y'])
            v_pt = Point(G.nodes[v]['x'], G.nodes[v]['y'])
            edge_lines.append(LineString([u_pt, v_pt]))

        if edge_lines:
            edges_gdf = gpd.GeoSeries(edge_lines, crs="EPSG:4326")
            edges_metric = edges_gdf.to_crs("EPSG:2180")
            buffered_edges = edges_metric.buffer(50)  # 50 m buffer per street segment
            # Combine node buffers and edge buffers
            all_buffers = list(buffered_nodes) + list(buffered_edges)
            isochrone_metric = unary_union(all_buffers)
        else:
            # Fallback if no edges (shouldn't happen but just in case)
            isochrone_metric = unary_union(buffered_nodes.tolist())

        # Keep MultiPolygon as-is; discarding parts would silently drop areas
        # separated by rivers, railways, etc.
        isochrone_wgs84 = (
            gpd.GeoSeries([isochrone_metric], crs="EPSG:2180")
            .to_crs("EPSG:4326")
            .iloc[0]
        )
        return isochrone_wgs84

    except Exception as e:
        print(f"\n    Error for {poi_name}: {e}")
        return None


def main():
    if len(sys.argv) < 2:
        print("Usage: python 03_generate_isochrones_local.py <poi_id>")
        sys.exit(1)

    poi_id = sys.argv[1]
    poi    = get_poi(poi_id)
    files  = poi_files(poi)

    stores_file = files["stores"]
    output_file = files["isochrones"]
    time_limit  = poi["walking_minutes"]
    distance_m  = time_limit * (WALKING_SPEED * 1000 / 60)

    print("=" * 60)
    print(f"{poi['label']} Isochrone Generator (Local - OSMnx)")
    print("=" * 60)
    print(f"Stores: {stores_file}")
    print(f"Output: {output_file}")
    print(f"Time limit:    {time_limit} min  ({distance_m:.0f} m)")
    print(f"Walking speed: {WALKING_SPEED} km/h\n")

    if not stores_file.exists():
        print(f"Stores file not found: {stores_file}")
        print(f"\nPlease run: python 01_fetch_poi_osm.py {poi_id}")
        return

    print(f"Loading {poi['label']} stores...", end=' ', flush=True)
    stores = gpd.read_file(stores_file)
    if stores.crs != "EPSG:4326":
        stores = stores.to_crs("EPSG:4326")
    print(f"{len(stores)} POIs loaded")

    # Columns to carry through to the isochrone layer
    extra_cols = [sanitize_col(k) for k in poi.get("extra_attributes", [])]
    extra_cols = [c for c in extra_cols if c in stores.columns]

    G = load_network()
    if G is None:
        print("\nFailed to load network. Run: python 02_fetch_walking_network.py")
        return

    print(f"\nGenerating isochrones for {len(stores)} {poi['label']} POIs...\n")

    start_time     = datetime.now()
    all_isochrones = []
    failed_pois    = []

    for seq, (idx, store) in enumerate(stores.iterrows()):
        poi_name  = store.get('name') or f"{poi['label']} {store.get('poi_id', idx)}"
        poi_seq_id = store.get('poi_id', idx)

        if seq % 50 == 0 and seq > 0:
            elapsed   = (datetime.now() - start_time).total_seconds()
            rate      = elapsed / seq
            remaining = rate * (len(stores) - seq)
            print(f"  [{seq}/{len(stores)}] {elapsed:.0f}s elapsed, ~{remaining:.0f}s remaining")

        polygon = create_isochrone(G, store.geometry, distance_m, poi_name)

        if polygon is not None and not polygon.is_empty:
            record = {
                'poi_id':       poi_seq_id,
                'poi_name':     poi_name,
                'time_minutes': time_limit,
                'distance_m':   distance_m,
                'geometry':     polygon,
            }
            for col in extra_cols:
                record[col] = store.get(col)
            all_isochrones.append(record)
        else:
            failed_pois.append((poi_seq_id, poi_name))

    generated_ids = set(r['poi_id'] for r in all_isochrones)
    print(f"\n{'='*60}")
    print(f"Results: {len(generated_ids)}/{len(stores)} {poi['label']} POIs got isochrones")
    if failed_pois:
        print(f"\nFailed ({len(failed_pois)}):")
        for sid, sname in sorted(failed_pois):
            print(f"  poi_id={sid}  {sname}")
    else:
        print("All POIs generated successfully.")
    print(f"{'='*60}\n")

    if not all_isochrones:
        print("No isochrones generated!")
        return

    print(f"Creating GeoDataFrame...", end=' ', flush=True)
    gdf = gpd.GeoDataFrame(all_isochrones, crs="EPSG:4326")

    gdf_metric   = gdf.to_crs("EPSG:2180")
    gdf['area_ha'] = gdf_metric.geometry.area / 10000

    gdf.to_file(output_file, driver="GPKG")
    elapsed = (datetime.now() - start_time).total_seconds()
    print("Done")

    print()
    print("=" * 60)
    print(f"Done! {len(gdf)} isochrones in {elapsed/60:.1f} min")
    print("=" * 60)
    print(f"\nSummary:")
    print(f"  POIs:        {len(stores)}")
    print(f"  Isochrones:  {len(gdf)}")
    print(f"  Time limit:  {time_limit} min")
    print(f"  Output:      {output_file}")

    print(f"\nIsochrone areas (hectares):")
    avg_area = gdf['area_ha'].mean()
    min_area = gdf['area_ha'].min()
    max_area = gdf['area_ha'].max()
    print(f"  {time_limit} min: {avg_area:.1f} ha avg (range: {min_area:.1f}-{max_area:.1f})")
    print()


if __name__ == "__main__":
    main()
