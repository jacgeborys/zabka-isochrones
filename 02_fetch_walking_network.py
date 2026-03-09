"""
Fetch Walking Network for Warsaw
Downloads and caches the full OSM walking network for the Warsaw bounding box.
"""

import osmnx as ox
from pathlib import Path
from datetime import datetime
import pickle
from shapely.geometry import box

from poi_config import NETWORK_DIR, WARSAW_BBOX

NETWORK_DIR.mkdir(parents=True, exist_ok=True)

NETWORK_FILE  = NETWORK_DIR / "warsaw_walking_network.graphml"
NETWORK_CACHE = NETWORK_DIR / "warsaw_walking_network.pkl"

# Each Overpass sub-query covers up to this many m².
# Default is 2,500,000 (2.5 km²) which fragments Warsaw into thousands of requests.
# 50 km² keeps each request manageable while cutting sub-queries to ~10 for Warsaw.
MAX_QUERY_AREA = 50_000_000  # 50 km²


def main():
    print("=" * 60)
    print("Walking Network Fetcher for Warsaw (full bbox)")
    print("=" * 60)
    print(f"Bbox:   {WARSAW_BBOX}")
    print(f"Output: {NETWORK_FILE}\n")

    if NETWORK_FILE.exists():
        response = input("Network file already exists. Delete and re-download? (y/n): ")
        if response.lower() != 'y':
            print("Keeping existing network.")
            return

    print("Downloading walking network from OpenStreetMap...\n")

    ox.settings.log_console = True
    ox.settings.max_query_area_size = MAX_QUERY_AREA
    ox.settings.requests_pause = 2  # seconds between sub-queries to avoid 429s

    # Build polygon from bbox — avoids graph_from_bbox parameter order issues
    bbox_polygon = box(
        WARSAW_BBOX['west'],
        WARSAW_BBOX['south'],
        WARSAW_BBOX['east'],
        WARSAW_BBOX['north'],
    )

    start_time = datetime.now()

    try:
        G = ox.graph_from_polygon(
            bbox_polygon,
            network_type='walk',
            simplify=True,
            retain_all=False,
        )

        elapsed = (datetime.now() - start_time).total_seconds()
        print(f"\nNetwork downloaded in {elapsed:.1f}s")
        print(f"  Nodes (intersections):  {len(G.nodes):,}")
        print(f"  Edges (street segments): {len(G.edges):,}")

        print(f"\nSaving GraphML...", end=' ', flush=True)
        ox.save_graphml(G, NETWORK_FILE)
        print(f"Done ({NETWORK_FILE.stat().st_size / 1024 / 1024:.1f} MB)")

        print(f"Saving pickle (faster loading)...", end=' ', flush=True)
        with open(NETWORK_CACHE, 'wb') as f:
            pickle.dump(G, f, protocol=pickle.HIGHEST_PROTOCOL)
        print(f"Done ({NETWORK_CACHE.stat().st_size / 1024 / 1024:.1f} MB)")

        print()
        print("=" * 60)
        print("Done! Network covers the full Warsaw bbox.")
        print("=" * 60)
        print(f"\nNext step: run the pipeline for your POIs")
        print(f"  python run_pipeline.py")
        print()

    except Exception as e:
        print(f"\nError downloading network: {e}")
        print(f"\nTroubleshooting:")
        print(f"  Check internet connection")
        print(f"  Verify OSMnx is up to date: pip install --upgrade osmnx")


if __name__ == "__main__":
    main()
