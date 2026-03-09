"""
Final publication charts — Warsaw walkability analysis.

Generates 3 charts:
  1. DNA heatmap — walking accessibility of 4 services by district
  2. Accessibility pyramid — how many services each building can reach
  3. Store map — effective market area per Żabka, colored by catchment type

Usage:
    python 08_final_charts.py           # all 3 charts  
    python 08_final_charts.py 1 3       # specific charts
    python 08_final_charts.py --force   # recompute cached data
"""
import sys
import gc
import geopandas as gpd
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from pathlib import Path
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

# ---------------------------------------------------------------------------
# Font
# ---------------------------------------------------------------------------
plt.rcParams['font.family'] = 'Segoe UI'

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_DIR = Path(__file__).resolve().parent
DATA_DIR    = PROJECT_DIR.parent / "data"
GPKG_DIR    = PROJECT_DIR / "output" / "gpkg"
CHARTS_DIR  = PROJECT_DIR / "output" / "charts"
CHARTS_DIR.mkdir(parents=True, exist_ok=True)

BUILDINGS_CLASSIFIED = GPKG_DIR / "warsaw_all_buildings_classified.gpkg"
UNIFIED_CACHE        = GPKG_DIR / "warsaw_unified_4services.gpkg"
BOROUGHS_FILE        = DATA_DIR / "osm" / "admin_level_9.gpkg"
ISO_PATH             = GPKG_DIR / "zabka" / "zabka_isochrones.gpkg"
STORES_PATH          = GPKG_DIR / "zabka" / "zabka_stores.gpkg"
STORE_CACHE          = GPKG_DIR / "zabka_effective_market_cache.parquet"

sys.path.insert(0, str(PROJECT_DIR))
from building_categories import BUILDING_CATEGORIES

SERVICES = {
    'zabka':             {'label': 'Żabka',          'color': '#00CC00', 'minutes': 10},
    'parcel_locker':     {'label': 'Parcel lockers', 'color': '#057ffa', 'minutes': 10},
    'elementary_school': {'label': 'Schools',        'color': '#f56b26', 'minutes': 15},
    'church':            {'label': 'Churches',       'color': '#ff039e', 'minutes': 10},
}
SERVICE_ORDER = ['zabka', 'parcel_locker', 'elementary_school', 'church']

CHARTS = {
    1: CHARTS_DIR / "walking_accessibility_heatmap.png",
    2: CHARTS_DIR / "service_coverage_pyramid.png",
    3: CHARTS_DIR / "zabka_effective_market_map.png",
}

# Relevant building categories for floor-area metrics
CAT_RESIDENTIAL = 'budynki mieszkalne'
CAT_COMMERCIAL  = 'budynki handlowo-usługowe'
CAT_OFFICE      = 'budynki biurowe'
RELEVANT_CATS   = [CAT_RESIDENTIAL, CAT_COMMERCIAL, CAT_OFFICE]

# Warsaw's 18 official districts
WARSAW_BOROUGHS = {
    'Bemowo', 'Białołęka', 'Bielany', 'Mokotów', 'Ochota',
    'Praga-Południe', 'Praga-Północ', 'Rembertów', 'Śródmieście',
    'Targówek', 'Ursus', 'Ursynów', 'Wawer', 'Wesoła',
    'Wilanów', 'Wola', 'Włochy', 'Żoliborz',
}

# ---------------------------------------------------------------------------
# Dark theme
# ---------------------------------------------------------------------------
BG     = '#1a1a1a'
BG2    = '#2a2a2a'
GRID_C = '#3a3a3a'
TXT    = 'white'
SUBTLE = '#888888'

CLR_RES = '#00CC00'
CLR_COM = '#057ffa'
CLR_TOT = '#FFD700'


def dark(fig, ax):
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(BG)
    ax.tick_params(colors=TXT, labelsize=11)
    for s in ax.spines.values():
        s.set_color(GRID_C)
    ax.grid(alpha=0.2, color=TXT, linewidth=0.5)
    ax.set_axisbelow(True)


def save(fig, path, dpi=150, top=None):
    if top:
        fig.tight_layout(rect=[0, 0, 1, top])
    else:
        fig.tight_layout()
    fig.savefig(path, dpi=dpi, facecolor=BG, bbox_inches='tight')
    plt.close(fig)
    print(f"    -> {path.name}")


# ---------------------------------------------------------------------------
# Data loading — unified buildings (charts 1 & 2)
# ---------------------------------------------------------------------------
def prepare_unified_data(force=False):
    """Load or build unified dataset: all buildings x 4 services x borough."""

    if UNIFIED_CACHE.exists() and not force:
        print("Loading cached unified data...", end=' ', flush=True)
        bld = gpd.read_file(UNIFIED_CACHE)
        for s in SERVICE_ORDER:
            bld[f"has_{s}"] = bld[f"{s}_count"] > 0
        bld['service_count'] = sum(bld[f"has_{s}"].astype(int) for s in SERVICE_ORDER)
        print(f"{len(bld):,} buildings")
        return bld

    print("Building unified dataset (first run — a few minutes)...\n")

    print("  [1/4] Loading classified buildings...", end=' ', flush=True)
    bld = gpd.read_file(BUILDINGS_CLASSIFIED)
    bld['bld_id'] = range(len(bld))
    if bld.crs and str(bld.crs) != "EPSG:2180":
        bld = bld.to_crs("EPSG:2180")
    print(f"{len(bld):,}")

    if 'num_points' in bld.columns:
        bld = bld.rename(columns={'num_points': 'zabka_count'})
    bld['zabka_count'] = bld['zabka_count'].fillna(0).astype(int)

    print("  [2/4] Adding service coverages...")
    for svc in ['parcel_locker', 'elementary_school', 'church']:
        col = f"{svc}_count"
        cov_path = GPKG_DIR / svc / f"{svc}_coverage_map.gpkg"
        print(f"         {SERVICES[svc]['label']:16s} ", end='', flush=True)

        if not cov_path.exists():
            print("NOT FOUND")
            bld[col] = 0
            continue

        cov = gpd.read_file(cov_path)
        if cov.crs != bld.crs:
            cov = cov.to_crs(bld.crs)

        joined = gpd.sjoin(
            bld[['bld_id', 'geometry']],
            cov[['num_points', 'geometry']],
            how='left', predicate='intersects'
        )
        best = joined.groupby('bld_id')['num_points'].max().fillna(0).astype(int)
        bld[col] = bld['bld_id'].map(best).fillna(0).astype(int)
        n = (bld[col] > 0).sum()
        print(f"{n:,} with access")

    for s in SERVICE_ORDER:
        bld[f"has_{s}"] = bld[f"{s}_count"] > 0
    bld['service_count'] = sum(bld[f"has_{s}"].astype(int) for s in SERVICE_ORDER)

    print("  [3/4] Adding boroughs...", end=' ', flush=True)
    if BOROUGHS_FILE.exists():
        bor = gpd.read_file(BOROUGHS_FILE)
        bor = bor[bor['name'].notna() & (bor['name'].str.len() > 0)]
        if bor.crs != bld.crs:
            bor = bor.to_crs(bld.crs)
        cents = bld[['bld_id']].copy()
        cents['geometry'] = bld.geometry.centroid
        cents = gpd.GeoDataFrame(cents, crs=bld.crs)
        j = gpd.sjoin(cents, bor[['name', 'geometry']], how='left', predicate='within')
        j = j.drop_duplicates(subset='bld_id', keep='first')
        bld['borough'] = bld['bld_id'].map(j.set_index('bld_id')['name'])
        print(f"{bld['borough'].notna().sum():,} assigned")
    else:
        bld['borough'] = None
        print("NOT FOUND")

    print("  [4/4] Saving cache...", end=' ', flush=True)
    sv = bld.copy()
    for s in SERVICE_ORDER:
        sv[f"has_{s}"] = sv[f"has_{s}"].astype(int)
    sv['service_count'] = sv['service_count'].astype(int)
    sv.to_file(UNIFIED_CACHE, driver="GPKG")
    print("OK\n")

    return bld


def borough_filter(bld, min_buildings=200):
    b = bld[bld['borough'].notna()].copy()
    counts = b['borough'].value_counts()
    valid = counts[counts >= min_buildings].index
    return b[b['borough'].isin(valid)]


# ---------------------------------------------------------------------------
# Data loading — store effective market (chart 3)
# ---------------------------------------------------------------------------
def load_store_metrics(force=False):
    """Load or compute per-store effective market data + borough geometries."""

    # Boroughs
    bor = gpd.read_file(BOROUGHS_FILE)
    bor = bor[bor['name'].notna() & (bor['name'].str.len() > 0)]
    if str(bor.crs) != "EPSG:2180":
        bor = bor.to_crs("EPSG:2180")

    # Try cache first
    if STORE_CACHE.exists() and not force:
        print("Loading cached store metrics...", end=' ', flush=True)
        per_store = pd.read_parquet(STORE_CACHE)
        print(f"{len(per_store)} stores")
        return per_store, bor

    print("Computing effective market areas (first run — may take a few minutes)...")

    # Load inputs
    bld_all = gpd.read_file(BUILDINGS_CLASSIFIED)
    if str(bld_all.crs) != "EPSG:2180":
        bld_all = bld_all.to_crs("EPSG:2180")

    bld = bld_all[bld_all['building_type'].isin(RELEVANT_CATS)].copy()
    bld['bld_id'] = range(len(bld))
    if 'floor_area_m2' not in bld.columns:
        bld['floor_area_m2'] = bld['footprint_m2'] * bld['estimated_floors']
    bld['fa_res'] = np.where(bld['building_type'] == CAT_RESIDENTIAL, bld['floor_area_m2'], 0)
    bld['fa_com'] = np.where(bld['building_type'].isin([CAT_COMMERCIAL, CAT_OFFICE]), bld['floor_area_m2'], 0)
    bld['fa_total'] = bld['floor_area_m2']
    del bld_all
    gc.collect()

    stores = gpd.read_file(STORES_PATH)
    iso = gpd.read_file(ISO_PATH)
    if str(iso.crs) != "EPSG:2180":
        iso = iso.to_crs("EPSG:2180")
    if str(stores.crs) != "EPSG:2180":
        stores = stores.to_crs("EPSG:2180")

    # Spatial join
    bld_cols = ['bld_id', 'fa_res', 'fa_com', 'fa_total', 'geometry']
    print(f"  Joining {len(bld):,} buildings x {len(iso)} isochrones...", end=' ', flush=True)
    joined = gpd.sjoin(bld[bld_cols], iso[['poi_id', 'geometry']],
                       how='inner', predicate='intersects')
    print(f"{len(joined):,} pairs")

    n_stores_per_bld = joined.groupby('bld_id')['poi_id'].nunique()
    joined['n_zabkas'] = joined['bld_id'].map(n_stores_per_bld)

    joined['share_res']   = joined['fa_res']   / joined['n_zabkas']
    joined['share_com']   = joined['fa_com']   / joined['n_zabkas']
    joined['share_total'] = joined['fa_total'] / joined['n_zabkas']

    per_store = joined.groupby('poi_id').agg(
        eff_res=('share_res', 'sum'),
        eff_com=('share_com', 'sum'),
        eff_total=('share_total', 'sum'),
        n_buildings=('bld_id', 'nunique'),
        mean_overlap=('n_zabkas', 'mean'),
    ).reset_index()

    # Borough assignment
    bor_cols = bor[['name', 'geometry']].rename(columns={'name': 'borough_name'})
    sj = gpd.sjoin(stores, bor_cols, how='left', predicate='within')
    sj = sj.drop_duplicates(subset='poi_id', keep='first')
    store_bor = sj.set_index('poi_id')['borough_name'].to_dict()
    per_store['borough'] = per_store['poi_id'].map(store_bor)

    # Store coordinates
    store_pts = stores[['poi_id', 'geometry']].copy()
    per_store = per_store.merge(
        store_pts.drop(columns='geometry').assign(
            x=store_pts.geometry.x, y=store_pts.geometry.y),
        on='poi_id', how='left')

    per_store.to_parquet(STORE_CACHE)
    print(f"  Cached to {STORE_CACHE.name}")

    del joined
    gc.collect()

    return per_store, bor


# ===================================================================
# Chart 1 — DNA heatmap
# ===================================================================
def chart_01_heatmap(bld):
    print("  Chart 1: DNA heatmap...")

    b = borough_filter(bld)
    b = b[b['building_type'].isin(RELEVANT_CATS)].copy()

    rows = []
    for name in b['borough'].unique():
        sub = b[b['borough'] == name]
        total_fa = sub['floor_area_m2'].sum()
        if total_fa == 0:
            continue
        row = {'borough': name}
        for s in SERVICE_ORDER:
            covered_fa = sub.loc[sub[f"has_{s}"], 'floor_area_m2'].sum()
            row[s] = covered_fa / total_fa * 100
        row['mean'] = np.mean([row[s] for s in SERVICE_ORDER])
        rows.append(row)

    df = pd.DataFrame(rows).sort_values('mean', ascending=True)
    cols = SERVICE_ORDER + ['mean']
    col_labels = [SERVICES[s]['label'] for s in SERVICE_ORDER] + ['Average']
    matrix = df[cols].values

    fig, ax = plt.subplots(figsize=(12, 10))
    dark(fig, ax)
    ax.grid(False)

    cmap = LinearSegmentedColormap.from_list(
        'ryg', ['#CC0000', '#FF6600', '#FFCC00', '#88CC00', '#00AA00'])
    im = ax.imshow(matrix, cmap=cmap, aspect='auto', vmin=20, vmax=95)

    for i in range(matrix.shape[0]):
        for j in range(matrix.shape[1]):
            v = matrix[i, j]
            tc = 'white' if v < 35 or v > 85 else 'black'
            w = 'bold' if j == len(SERVICE_ORDER) else 'normal'
            ax.text(j, i, f"{v:.0f}%", ha='center', va='center',
                    color=tc, fontsize=10, weight=w)

    ax.axvline(len(SERVICE_ORDER) - 0.5, color=TXT, linewidth=2, alpha=0.4)
    ax.set_xticks(range(len(col_labels)))
    ax.set_xticklabels(col_labels, color=TXT, fontsize=12, weight='bold')
    ax.set_yticks(range(len(df)))
    ax.set_yticklabels(df['borough'].values, color=TXT, fontsize=11)
    ax.tick_params(left=True, bottom=False, top=True, labeltop=True, labelbottom=False)

    cbar = fig.colorbar(im, ax=ax, shrink=0.8, pad=0.02)
    cbar.set_label('% floor area with access', color=TXT, fontsize=11)
    cbar.ax.tick_params(colors=TXT)

    fig.suptitle('Walking accessibility of services in Warsaw',
                 color=TXT, fontsize=17, weight='bold', x=0.04, ha='left', y=0.98)
    fig.text(0.04, 0.935,
             '% floor area (residential + office + commercial) within walking distance',
             color='#aaaaaa', fontsize=13, ha='left')

    save(fig, CHARTS[1], top=0.97)


# ===================================================================
# Chart 2 — Accessibility pyramid
# ===================================================================
def chart_02_pyramid(bld):
    print("  Chart 2: Accessibility pyramid...")

    b = borough_filter(bld)
    b = b[b['building_type'].isin(RELEVANT_CATS)].copy()

    rows = []
    for name in b['borough'].unique():
        sub = b[b['borough'] == name]
        total_fa = sub['floor_area_m2'].sum()
        if total_fa == 0:
            continue
        row = {'borough': name}
        for i in range(5):
            row[str(i)] = sub.loc[sub['service_count'] == i, 'floor_area_m2'].sum() / total_fa * 100
        row['pct4'] = row['4']
        rows.append(row)

    df = pd.DataFrame(rows).sort_values('pct4', ascending=True)

    fig, ax = plt.subplots(figsize=(16, 10))
    dark(fig, ax)

    y = range(len(df))
    svc_colors = ['#CC0000', '#FF6600', '#FFCC00', '#88CC00', '#00AA00']
    svc_labels = ['0 services', '1 service', '2 services', '3 services', '4 services']
    left = np.zeros(len(df))

    for i in range(5):
        vals = df[str(i)].values
        ax.barh(y, vals, left=left, color=svc_colors[i], label=svc_labels[i],
                edgecolor=BG2, linewidth=0.5, height=0.75)
        for j, v in enumerate(vals):
            if v > 7:
                ax.text(left[j] + v / 2, j, f"{v:.0f}%",
                        ha='center', va='center', color='white',
                        fontsize=9, weight='bold')
        left += vals

    ax.set_yticks(y)
    ax.set_yticklabels(df['borough'].values, color=TXT, fontsize=11)
    ax.set_xlim(0, 100)
    ax.set_xlabel('% floor area (residential + office + commercial)', color=TXT, fontsize=13)
    ax.legend(loc='upper right', frameon=True, facecolor=BG2,
              edgecolor=GRID_C, labelcolor=TXT, fontsize=11)
    ax.set_ylim(-0.5, len(df) - 0.5)

    fig.suptitle('Żabka, parcel locker, school, church — what\'s within walking distance?',
                 color=TXT, fontsize=17, weight='bold', x=0.04, ha='left', y=0.98)
    fig.text(0.04, 0.935,
             '4/4 = all 4 services within a 10–15 min walk',
             color='#aaaaaa', fontsize=13, ha='left')

    save(fig, CHARTS[2], top=0.97)


# ===================================================================
# Chart 3 — Store map (effective market area per Żabka)
# ===================================================================
def chart_03_store_map(per_store, boroughs):
    from shapely.geometry import box as shapely_box

    print("  Chart 3: Store map...")

    valid = per_store[per_store['x'].notna() & per_store['y'].notna()].copy()
    if len(valid) == 0:
        print("    SKIP — no coordinates")
        return

    waw = boroughs[boroughs['name'].isin(WARSAW_BOROUGHS)].copy()

    # Catchment type classification
    valid['pct_res'] = valid['eff_res'] / valid['eff_total'].clip(lower=1)
    valid['dom_type'] = np.where(
        valid['pct_res'] > 0.7, 'residential',
        np.where(valid['pct_res'] < 0.3, 'commercial', 'mixed')
    )

    dom_colors = {
        'residential': CLR_RES,
        'commercial': CLR_COM,
        'mixed': CLR_TOT,
    }
    dom_labels = {
        'residential': 'Residential-dominated',
        'mixed':       'Mixed',
        'commercial':  'Commercial/office-dominated',
    }

    # Size normalization
    size_min, size_max = 8, 100
    emin = valid['eff_total'].quantile(0.02)
    emax = valid['eff_total'].quantile(0.98)
    valid['sz'] = ((valid['eff_total'].clip(emin, emax) - emin)
                   / (emax - emin) * (size_max - size_min) + size_min)

    # View extent from store cloud
    pad_frac = 0.05
    xmin, xmax = valid['x'].min(), valid['x'].max()
    ymin, ymax = valid['y'].min(), valid['y'].max()
    dx = (xmax - xmin) * pad_frac
    dy = (ymax - ymin) * pad_frac
    x0, x1, y0, y1 = xmin - dx, xmax + dx, ymin - dy, ymax + dy
    clip_box = shapely_box(x0, y0, x1, y1)

    # Clip borough geometries to view
    waw_clipped = waw.copy()
    waw_clipped['geometry'] = waw_clipped.geometry.intersection(clip_box)
    waw_clipped = waw_clipped[~waw_clipped.is_empty]

    # Figure
    fig, ax = plt.subplots(figsize=(14, 14))
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(BG)
    ax.grid(False)
    ax.set_aspect('equal')
    ax.set_xticks([])
    ax.set_yticks([])
    for s in ax.spines.values():
        s.set_visible(False)

    waw_clipped.boundary.plot(ax=ax, color='#505050', linewidth=1.0, alpha=0.8)

    ax.set_xlim(x0, x1)
    ax.set_ylim(y0, y1)

    # Plot stores (largest first so small dots sit on top)
    valid_sorted = valid.sort_values('eff_total', ascending=False)

    for dt in ['residential', 'mixed', 'commercial']:
        sub = valid_sorted[valid_sorted['dom_type'] == dt]
        ax.scatter(sub['x'], sub['y'], s=sub['sz'],
                   c=dom_colors[dt], alpha=0.6,
                   edgecolors=TXT, linewidth=0.2,
                   label=dom_labels[dt], zorder=3)

    ax.legend(loc='lower left', frameon=True, facecolor=BG2,
              edgecolor=GRID_C, labelcolor=TXT, fontsize=11,
              markerscale=1.3, handletextpad=0.8,
              borderpad=0.8, labelspacing=0.7)

    fig.suptitle('Which Żabkas serve the largest effective market?',
                 color=TXT, fontsize=17, weight='bold', x=0.04, ha='left', y=0.98)
    fig.text(0.04, 0.95,
             'Dot size = effective market area.'
             ' If a building is within range of multiple Żabkas, its area is split between them.',
             color='#aaaaaa', fontsize=13, ha='left')

    ax.set_xlim(x0, x1)
    ax.set_ylim(y0, y1)

    save(fig, CHARTS[3], dpi=200)


# ===================================================================
# Main
# ===================================================================
CHART_FUNCS = {
    1: ('DNA heatmap',           'unified'),
    2: ('Accessibility pyramid', 'unified'),
    3: ('Store map',             'stores'),
}


def main():
    start = datetime.now()
    force = '--force' in sys.argv
    requested = [int(a) for a in sys.argv[1:] if a.isdigit()]
    charts_to_run = requested if requested else [1, 2, 3]

    print("=" * 60)
    print("Warsaw Walkability — Final Charts")
    print("=" * 60)

    need_unified = any(c in charts_to_run for c in [1, 2])
    need_stores  = 3 in charts_to_run

    bld = None
    per_store = None
    boroughs = None

    if need_unified:
        bld = prepare_unified_data(force=force)

    if need_stores:
        per_store, boroughs = load_store_metrics(force=force)

    print(f"\nGenerating charts: {charts_to_run}\n")

    for num in charts_to_run:
        try:
            if num == 1:
                chart_01_heatmap(bld)
            elif num == 2:
                chart_02_pyramid(bld)
            elif num == 3:
                chart_03_store_map(per_store, boroughs)
        except Exception as e:
            print(f"    FAILED (chart {num}): {e}")
            import traceback
            traceback.print_exc()

    elapsed = (datetime.now() - start).total_seconds()
    print(f"\nDone! {len(charts_to_run)} charts in {elapsed:.0f}s")
    print(f"Output: {CHARTS_DIR}")


if __name__ == "__main__":
    main()
