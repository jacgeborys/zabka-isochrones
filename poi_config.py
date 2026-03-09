"""
POI Configuration
Define all points of interest to analyse. Set enabled=False to skip a POI
without deleting its entry. Add new POIs by appending to POIS.
"""
from pathlib import Path

BASE_DIR    = Path(__file__).resolve().parent
DATA_DIR    = BASE_DIR.parent / "data"
NETWORK_DIR = BASE_DIR / "network"
OUTPUT_DIR  = BASE_DIR / "output"

WARSAW_BBOX = {
    'south': 52.0977,
    'west':  20.8519,
    'north': 52.3690,
    'east':  21.2711,
}

OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.openstreetmap.ru/api/interpreter",
]

WALKING_SPEED = 4.5  # km/h

# ---------------------------------------------------------------------------
# POI definitions
#
# osm_filters  – list of tag dicts; tags within a dict are ANDed together,
#                multiple dicts are ORed (each becomes its own node+way query)
# extra_attributes – OSM tag keys to extract from each feature; missing tags
#                    become NULL. Colons are replaced by underscores in
#                    the output column name (addr:street → addr_street).
# ---------------------------------------------------------------------------
POIS = [
    {
        "id": "zabka",
        "enabled": True,
        "label": "Żabka",
        "osm_filters": [
            {"brand": "Żabka"},
            {"name": "Żabka"},
        ],
        "extra_attributes": ["opening_hours", "addr:street", "addr:housenumber", "addr:city"],
        "walking_minutes": 10,
    },
    {
        "id": "church",
        "enabled": True,
        "label": "Church",
        "osm_filters": [
            {"building": "church", "denomination": "roman_catholic"},
        ],
        "extra_attributes": ["denomination", "building", "religion", "name"],
        "walking_minutes": 10,
    },
    {
        "id": "pharmacy",
        "enabled": True,
        "label": "Pharmacy",
        "osm_filters": [
            {"amenity": "pharmacy"},
        ],
        "extra_attributes": ["name", "opening_hours", "building"],
        "walking_minutes": 10,
    },
    {
        "id": "parcel_locker",
        "enabled": True,
        "label": "Parcel Locker",
        "osm_filters": [
            {"amenity": "parcel_locker"},
        ],
        "extra_attributes": ["brand", "operator", "building"],
        "fetch_all_tags": True,  # Fetch ALL OSM tags for analysis
        "walking_minutes": 10,
    },
    {
        "id": "elementary_school",
        "enabled": True,
        "label": "Elementary School",
        "osm_filters": [
            {"amenity": "school"},
        ],
        "extra_attributes": ["name", "operator", "addr:street", "addr:housenumber"],
        "walking_minutes": 15,  # Kids might walk a bit further
    },
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_poi(poi_id):
    for p in POIS:
        if p["id"] == poi_id:
            return p
    available = [p["id"] for p in POIS]
    raise ValueError(f"Unknown POI id: {poi_id!r}. Available: {available}")


def get_enabled_pois():
    return [p for p in POIS if p["enabled"]]


def poi_files(poi):
    """Return canonical file paths for every pipeline stage of a POI."""
    pid = poi["id"]
    gpkg_dir = OUTPUT_DIR / "gpkg" / pid
    gpkg_dir.mkdir(parents=True, exist_ok=True)
    return {
        "stores":     gpkg_dir / f"{pid}_stores.gpkg",
        "isochrones": gpkg_dir / f"{pid}_isochrones.gpkg",
        "coverage":   gpkg_dir / f"{pid}_coverage_map.gpkg",
        "buildings":  gpkg_dir / f"buildings_near_{pid}.gpkg",
    }


def sanitize_col(name):
    """Make an OSM tag key safe as a column name (addr:street → addr_street)."""
    return name.replace(":", "_")
