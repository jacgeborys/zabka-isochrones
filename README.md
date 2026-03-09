# Warsaw Walking Accessibility Analysis

Isochrone-based walking accessibility analysis for Warsaw, Poland. Generates coverage maps for multiple services and publication-ready analytical charts.

**155,000 buildings analyzed. Floor-area weighted. Built with OpenStreetMap, BDOT10k, Python and QGIS.**

## Maps

| | |
|---|---|
| ![Żabka](output/maps/zabka.png) | ![Parcel lockers](output/maps/paczkomaty.png) |
| ![Schools](output/maps/szkoly.png) | ![Churches](output/maps/koscioly.png) |

## Charts

### Walking accessibility heatmap
![Walking accessibility heatmap](output/charts/walking_accessibility_heatmap.png)

### Service coverage pyramid
![Service coverage pyramid](output/charts/service_coverage_pyramid.png)

### Effective market per Żabka
![Effective market map](output/charts/zabka_effective_market_map.png)

## Services analyzed

| Service | Walk time | Color |
|---------|-----------|-------|
| Żabka (convenience stores) | 10 min | Green |
| Parcel lockers (InPost, DHL, etc.) | 10 min | Blue |
| Elementary schools | 15 min | Orange |
| Churches (Roman Catholic) | 10 min | Pink |

## Pipeline

Run scripts in order. Each step reads the output of the previous one.

```
01_fetch_poi_osm.py              Fetch POI locations from OpenStreetMap
02_fetch_walking_network.py      Download walking network for Warsaw (one-time)
03_generate_isochrones_local.py  Generate 10/15-min walking isochrones per POI
04_create_coverage_map.py        Merge isochrones into coverage heatmap
05_intersect_buildings.py        Spatial join: buildings x coverage
06_classify_buildings.py         Classify all Warsaw buildings using BDOT10k
07_generate_charts.py            Generate the 3 publication charts
```

### Quick start

```bash
# 1. Download walking network (one-time, ~10 min)
python 02_fetch_walking_network.py

# 2. Run pipeline for all enabled services
python run_pipeline.py

# 3. Classify buildings across all services
python 06_classify_buildings.py

# 4. Generate charts
python 07_generate_charts.py
```

### Run a single service

```bash
python run_pipeline.py zabka
python run_pipeline.py church
```

## Project structure

```
01-05_*.py                   Pipeline scripts (run in order, per service)
06_classify_buildings.py     Cross-service building classification
07_generate_charts.py        Final publication charts

poi_config.py                Service definitions and configuration
building_categories.py       BDOT10k building type mappings
run_pipeline.py              Batch runner for 01-05 across all services
generate_qgis_styles.py      Generate QGIS layer styles from data

styles/                      QGIS QML style files
output/
  charts/                    Final publication charts (3 PNGs, tracked)
  maps/                      QGIS-exported map images (tracked)
  gpkg/                      Generated geodata (gitignored, ~2 GB)
network/                     Cached walking network (gitignored, ~470 MB)
```

## How it works

### Isochrone generation
- Walking network from OSMnx
- Walking speed: 4.5 km/h
- Node + edge buffering (50m) for gap-free coverage
- CRS: EPSG:2180 (Poland CS92)

### Coverage map
- Planar subdivision: merge all isochrone boundaries, polygonize, count overlaps
- Each polygon gets a `num_points` attribute = number of reachable POIs

### Building classification
- BDOT10k building footprints for Warsaw (~155k buildings)
- Floor area estimated from footprint area x number of floors
- Spatial join with coverage maps for all 4 services

### Effective market metric (chart 3)
- For each Żabka, find all buildings within its 10-min isochrone
- Count how many other Żabkas also reach each building
- Split each building's floor area equally among competing stores
- Sum to get each store's "effective market area"

## Data sources

- **POI locations**: OpenStreetMap via Overpass API
- **Walking network**: OpenStreetMap via OSMnx
- **Building footprints**: BDOT10k (Polish national topographic database)
- **District boundaries**: OpenStreetMap admin boundaries

## Dependencies

```
geopandas
osmnx
networkx
shapely
pandas
numpy
matplotlib
scipy
requests
```

## License

Map data © OpenStreetMap contributors. Building data © GUGiK (BDOT10k).
