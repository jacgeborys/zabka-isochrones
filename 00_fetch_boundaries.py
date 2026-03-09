"""
Fetch Warsaw administrative boundaries from OpenStreetMap.

Downloads admin_level 7 (city boundary) and 9 (borough/district boundaries)
via the Overpass API, saving them as GeoPackage files in data/osm/.

Usage:
    python 00_fetch_boundaries.py
"""
import requests
import geopandas as gpd
from shapely.geometry import Polygon, MultiPolygon
from pathlib import Path
import time

PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR.parent / "data" / "osm"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.openstreetmap.ru/api/interpreter",
]

WARSAW_BBOX = "52.0977,20.8519,52.3690,21.2711"

LAYERS = {
    "admin_level_7": {
        "query": f"""
[out:json][timeout:120];
relation["boundary"="administrative"]["admin_level"="7"]({WARSAW_BBOX});
out geom;
""",
        "description": "Warsaw city boundary",
    },
    "admin_level_9": {
        "query": f"""
[out:json][timeout:120];
relation["boundary"="administrative"]["admin_level"="9"]({WARSAW_BBOX});
out geom;
""",
        "description": "Warsaw borough/district boundaries (18 districts)",
    },
}


def join_ways(ways):
    """Join multiple way segments into closed rings."""
    if not ways:
        return []
    if len(ways) == 1:
        coords = ways[0]
        if coords[0] != coords[-1]:
            coords = list(coords) + [coords[0]]
        return [coords]

    segments = [c for c in ways if len(c) >= 2]
    if not segments:
        return []

    rings = []
    used = set()

    for start_idx in range(len(segments)):
        if start_idx in used:
            continue
        ring = list(segments[start_idx])
        used.add(start_idx)

        for _ in range(len(segments) * 2):
            dist = ((ring[0][0] - ring[-1][0])**2 + (ring[0][1] - ring[-1][1])**2)**0.5
            if dist < 0.00001:
                if ring[0] != ring[-1]:
                    ring.append(ring[0])
                rings.append(ring)
                break

            best_idx, best_dist, reverse = None, float('inf'), False
            for idx in range(len(segments)):
                if idx in used:
                    continue
                seg = segments[idx]
                d_start = ((seg[0][0] - ring[-1][0])**2 + (seg[0][1] - ring[-1][1])**2)**0.5
                d_end = ((seg[-1][0] - ring[-1][0])**2 + (seg[-1][1] - ring[-1][1])**2)**0.5
                if d_start < best_dist:
                    best_idx, best_dist, reverse = idx, d_start, False
                if d_end < best_dist:
                    best_idx, best_dist, reverse = idx, d_end, True

            if best_idx is not None:
                seg = segments[best_idx]
                if reverse:
                    seg = list(reversed(seg))
                ring.extend(seg[1:] if best_dist < 0.00001 else seg)
                used.add(best_idx)
            else:
                if ring[0] != ring[-1]:
                    ring.append(ring[0])
                rings.append(ring)
                break
        else:
            if ring[0] != ring[-1]:
                ring.append(ring[0])
            if len(ring) >= 4:
                rings.append(ring)

    return rings


def parse_geometry(element):
    """Convert an OSM relation element to a Shapely polygon geometry."""
    if element['type'] != 'relation' or 'members' not in element:
        return None

    outer_ways, inner_ways = [], []
    for member in element['members']:
        if member.get('type') != 'way' or 'geometry' not in member:
            continue
        coords = [(n['lon'], n['lat']) for n in member['geometry']]
        if len(coords) < 2:
            continue
        if member.get('role') == 'outer':
            outer_ways.append(coords)
        elif member.get('role') == 'inner':
            inner_ways.append(coords)

    if not outer_ways:
        return None

    try:
        outer_rings = join_ways(outer_ways)
        inner_rings = join_ways(inner_ways) if inner_ways else []
        if not outer_rings:
            return None

        if len(outer_rings) == 1:
            return Polygon(outer_rings[0], inner_rings) if inner_rings else Polygon(outer_rings[0])

        polygons = []
        for outer_ring in outer_rings:
            try:
                outer_poly = Polygon(outer_ring)
                holes = [ir for ir in inner_rings if outer_poly.contains(Polygon(ir))] if inner_rings else []
                polygons.append(Polygon(outer_ring, holes) if holes else Polygon(outer_ring))
            except Exception:
                continue

        if len(polygons) == 1:
            return polygons[0]
        return MultiPolygon(polygons) if polygons else None
    except Exception:
        return None


def fetch_layer(name, query, description):
    """Fetch a single layer from Overpass API."""
    output_file = OUTPUT_DIR / f"{name}.gpkg"
    if output_file.exists():
        print(f"  {name}: already exists, skipping ({description})")
        return True

    print(f"  {name}: fetching ({description})...", end=" ", flush=True)

    for url in OVERPASS_URLS:
        try:
            resp = requests.post(url, data={"data": query}, timeout=180)
            if resp.status_code != 200:
                continue
            data = resp.json()
            break
        except Exception:
            time.sleep(5)
            continue
    else:
        print("FAILED (all servers)")
        return False

    geometries, properties = [], []
    for el in data.get("elements", []):
        geom = parse_geometry(el)
        if geom is None:
            continue
        tags = el.get("tags", {})
        props = {k: v for k, v in tags.items()}
        geometries.append(geom)
        properties.append(props)

    if not geometries:
        print("no data returned")
        return False

    gdf = gpd.GeoDataFrame(properties, geometry=geometries, crs="EPSG:4326")
    gdf = gdf.reset_index(drop=True)
    gdf.to_file(output_file, driver="GPKG")
    print(f"{len(gdf)} features -> {output_file.name}")
    return True


def main():
    print("Fetching Warsaw administrative boundaries from OpenStreetMap\n")
    for name, cfg in LAYERS.items():
        fetch_layer(name, cfg["query"], cfg["description"])
    print("\nDone!")


if __name__ == "__main__":
    main()
