"""
Complete Warsaw Żabka Analysis
Analyzes ALL buildings in Warsaw (including those with NO access)
Creates comprehensive charts showing the full picture
"""

import geopandas as gpd
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.gridspec import GridSpec
import seaborn as sns
from pathlib import Path
from datetime import datetime
import numpy as np
import sys

# Configuration
PROJECT_DIR = Path(__file__).resolve().parent
DATA_DIR = PROJECT_DIR.parent / "data"
GPKG_DIR = PROJECT_DIR / "output" / "gpkg"
GPKG_DIR.mkdir(parents=True, exist_ok=True)

# Input files
BUILDINGS_ALL = DATA_DIR / "bdot" / "bdot_buildings_warsaw.gpkg"
ZABKA_COVERAGE = GPKG_DIR / "zabka" / "zabka_coverage_map.gpkg"
WARSAW_ADMIN = DATA_DIR / "osm" / "admin_level_7.gpkg"
BOROUGHS = DATA_DIR / "osm" / "admin_level_9.gpkg"

# Output files
BUILDINGS_CLASSIFIED = GPKG_DIR / "warsaw_all_buildings_classified.gpkg"
STATS_CSV = GPKG_DIR / "warsaw_complete_statistics.csv"
SUMMARY_TXT = GPKG_DIR / "warsaw_complete_summary.txt"

# Charts (viral-focused for LinkedIn/social media)
CHART_STRATIFICATION = GPKG_DIR / "01_zabka_stratyfikacja.png"
CHART_HEIGHT_PRIVILEGE = GPKG_DIR / "02_zabka_przywilej_wysokosci.png"
CHART_SUBURBAN_DIVIDE = GPKG_DIR / "03_zabka_przedmiescia_vs_centrum.png"
CHART_BOROUGHS = GPKG_DIR / "04_zabka_dzielnice.png"
CHART_OPPORTUNITY_MATRIX = GPKG_DIR / "05_zabka_matryca_potencjalu.png"

# Import building categories
sys.path.insert(0, str(PROJECT_DIR))
from building_categories import BUILDING_CATEGORIES, adjust_color


def classify_building_type(row):
    """Classify BDOT building"""
    from building_categories import get_building_category
    if 'FSBUD' in row.index and pd.notna(row['FSBUD']):
        return get_building_category(row['FSBUD'])
    elif 'FOBUD' in row.index and pd.notna(row['FOBUD']):
        fobud = str(row['FOBUD']).strip()
        if fobud in BUILDING_CATEGORIES:
            return fobud
    return 'pozostałe budynki niemieszkalne'


def estimate_floors(row):
    """Get number of floors"""
    if 'LICZ_KONDY' in row.index and pd.notna(row['LICZ_KONDY']):
        try:
            floors = int(row['LICZ_KONDY'])
            if 0 < floors <= 100:
                return floors
        except:
            pass
    try:
        area = row.geometry.area
        if area < 100: return 1
        elif area < 300: return 2
        elif area < 600: return 3
        else: return 4
    except:
        return 2


def load_and_classify_buildings():
    """Load ALL Warsaw buildings and classify them"""
    print("\n" + "="*80)
    print("LOADING AND CLASSIFYING ALL WARSAW BUILDINGS")
    print("="*80)

    # Load Warsaw boundary
    print("\n1. Loading Warsaw boundary...", end=' ', flush=True)
    if not WARSAW_ADMIN.exists():
        print(f"\n   ✗ Not found: {WARSAW_ADMIN}")
        print(f"   Run: python 00_fetch_boundaries.py")
        return None

    warsaw = gpd.read_file(WARSAW_ADMIN)
    warsaw = warsaw[warsaw['name'].str.contains('Warszawa', na=False)]
    if len(warsaw) == 0:
        print("✗ No Warszawa boundary found")
        return None

    warsaw_boundary = warsaw.iloc[0].geometry
    print(f"✓")

    # Load ALL buildings
    print("2. Loading ALL BDOT buildings...", end=' ', flush=True)
    buildings = gpd.read_file(BUILDINGS_ALL)
    print(f"✓ {len(buildings):,}")

    # Clip to Warsaw
    print("3. Clipping to Warsaw boundary...", end=' ', flush=True)
    if buildings.crs != warsaw.crs:
        buildings = buildings.to_crs(warsaw.crs)
    buildings = buildings[buildings.intersects(warsaw_boundary)]
    print(f"✓ {len(buildings):,}")

    # Convert to metric
    print("4. Converting to EPSG:2180...", end=' ', flush=True)
    if buildings.crs != "EPSG:2180":
        buildings = buildings.to_crs("EPSG:2180")
    print("✓")

    # Classify
    print("5. Classifying buildings...")
    print("   • Footprints...", end=' ', flush=True)
    buildings['footprint_m2'] = buildings.geometry.area
    print("✓")

    print("   • Types...", end=' ', flush=True)
    buildings['building_type'] = buildings.apply(classify_building_type, axis=1)
    print("✓")

    print("   • Floors...", end=' ', flush=True)
    buildings['estimated_floors'] = buildings.apply(estimate_floors, axis=1)
    print("✓")

    print("   • Floor areas...", end=' ', flush=True)
    buildings['floor_area_m2'] = buildings['footprint_m2'] * buildings['estimated_floors']
    print("✓")

    # Height categories
    buildings['height_category'] = pd.cut(
        buildings['estimated_floors'],
        bins=[0, 3, 10, 100],
        labels=['<3 kond.', '3-10 kond.', '>10 kond.']
    )

    return buildings


def add_zabka_access(buildings):
    """Add Żabka access information to ALL buildings"""
    print("\n6. Determining Żabka access...")

    if not ZABKA_COVERAGE.exists():
        print(f"   ✗ Coverage not found: {ZABKA_COVERAGE}")
        print(f"   Run: python 04_create_coverage_map.py zabka")
        return None

    print("   • Loading coverage...", end=' ', flush=True)
    coverage = gpd.read_file(ZABKA_COVERAGE)
    if coverage.crs != buildings.crs:
        coverage = coverage.to_crs(buildings.crs)
    print(f"✓ {len(coverage)} polygons")

    print("   • Spatial join...", end=' ', flush=True)
    buildings_joined = gpd.sjoin(
        buildings,
        coverage[['num_points', 'geometry']],
        how='left',
        predicate='intersects'
    )
    print("✓")

    print("   • Resolving overlaps...", end=' ', flush=True)
    buildings_joined['num_points'] = buildings_joined['num_points'].fillna(0)
    buildings_joined = buildings_joined.sort_values('num_points', ascending=False)
    buildings_joined = buildings_joined.drop_duplicates(subset=['geometry'], keep='first')
    if 'index_right' in buildings_joined.columns:
        buildings_joined = buildings_joined.drop(columns=['index_right'])
    print("✓")

    # Add access flags
    buildings_joined['has_access'] = buildings_joined['num_points'] > 0
    buildings_joined['zabka_tier'] = pd.cut(
        buildings_joined['num_points'],
        bins=[-1, 0, 2, 4, 7, 10, 15, 20, 100],
        labels=['Brak', '1-2 Ż', '3-4 Ż', '5-7 Ż', '8-10 Ż', '11-15 Ż', '16-20 Ż', '20+ Ż']
    )

    with_access = buildings_joined['has_access'].sum()
    print(f"\n   ✓ {with_access:,} buildings WITH access ({with_access/len(buildings_joined)*100:.1f}%)")
    print(f"   ✓ {len(buildings_joined)-with_access:,} buildings WITHOUT access ({(len(buildings_joined)-with_access)/len(buildings_joined)*100:.1f}%)")

    return buildings_joined


def save_buildings(buildings):
    """Save classified buildings"""
    print("\n7. Saving classified buildings...", end=' ', flush=True)

    buildings_save = buildings.copy()
    # Convert categorical to string for GPKG
    if 'height_category' in buildings_save.columns:
        buildings_save['height_category'] = buildings_save['height_category'].astype(str)
    if 'zabka_tier' in buildings_save.columns:
        buildings_save['zabka_tier'] = buildings_save['zabka_tier'].astype(str)

    buildings_save.to_file(BUILDINGS_CLASSIFIED, driver="GPKG")
    print("✓")


def calculate_statistics(buildings):
    """Calculate comprehensive statistics"""
    print("\n8. Calculating statistics...")

    stats = []

    # Overall
    total = len(buildings)
    with_acc = buildings['has_access'].sum()
    without_acc = total - with_acc

    print(f"\n   OVERALL:")
    print(f"   • Total: {total:,}")
    print(f"   • With access: {with_acc:,} ({with_acc/total*100:.1f}%)")
    print(f"   • WITHOUT access: {without_acc:,} ({without_acc/total*100:.1f}%)")

    # By type
    print(f"\n   BY TYPE:")
    for btype in buildings['building_type'].unique():
        subset = buildings[buildings['building_type'] == btype]
        t = len(subset)
        w = subset['has_access'].sum()
        wo = t - w

        if t > 100:
            label = BUILDING_CATEGORIES.get(btype, {'description': btype})['description']
            print(f"   • {label:30s} {w:6,}/{t:6,} ({w/t*100:5.1f}%)")

            stats.append({
                'category': 'type',
                'label': label,
                'type': btype,
                'height': 'all',
                'total': t,
                'with_access': w,
                'without_access': wo,
                'pct_with': w/t*100 if t>0 else 0,
                'pct_without': wo/t*100 if t>0 else 0
            })

    # By height
    print(f"\n   BY HEIGHT:")
    for height in ['<3 kond.', '3-10 kond.', '>10 kond.']:
        subset = buildings[buildings['height_category'].astype(str) == height]
        t = len(subset)
        w = subset['has_access'].sum()
        wo = t - w

        if t > 0:
            print(f"   • {height:10s} {w:6,}/{t:6,} ({w/t*100:5.1f}%)")

            stats.append({
                'category': 'height',
                'label': height,
                'type': 'all',
                'height': height,
                'total': t,
                'with_access': w,
                'without_access': wo,
                'pct_with': w/t*100,
                'pct_without': wo/t*100
            })

    # By type AND height
    print(f"\n   BY TYPE AND HEIGHT:")
    key_types = ['budynki mieszkalne', 'budynki handlowo-usługowe', 'budynki biurowe']

    for btype in key_types:
        label_type = BUILDING_CATEGORIES[btype]['description']
        print(f"   {label_type}:")

        for height in ['<3 kond.', '3-10 kond.', '>10 kond.']:
            subset = buildings[
                (buildings['building_type'] == btype) &
                (buildings['height_category'].astype(str) == height)
            ]
            t = len(subset)
            w = subset['has_access'].sum()
            wo = t - w

            if t > 0:
                print(f"     • {height:10s} {w:6,}/{t:6,} ({w/t*100:5.1f}%) WITH, {wo/t*100:5.1f}% WITHOUT")

                stats.append({
                    'category': 'type_height',
                    'label': f"{label_type} {height}",
                    'type': btype,
                    'height': height,
                    'total': t,
                    'with_access': w,
                    'without_access': wo,
                    'pct_with': w/t*100,
                    'pct_without': wo/t*100
                })

    # Save stats
    df_stats = pd.DataFrame(stats)
    df_stats.to_csv(STATS_CSV, index=False)
    print(f"\n   ✓ Saved: {STATS_CSV.name}")

    # Text report
    with open(SUMMARY_TXT, 'w', encoding='utf-8') as f:
        f.write("=" * 80 + "\n")
        f.write("COMPLETE WARSAW ŻABKA ANALYSIS\n")
        f.write("=" * 80 + "\n\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Total buildings: {total:,}\n\n")

        f.write("OVERALL:\n")
        f.write(f"  With access:    {with_acc:8,} ({with_acc/total*100:5.1f}%)\n")
        f.write(f"  WITHOUT access: {without_acc:8,} ({without_acc/total*100:5.1f}%)\n\n")

        for _, row in df_stats.iterrows():
            if row['total'] > 100:
                f.write(f"{row['label']:40s}\n")
                f.write(f"  Total: {row['total']:,}\n")
                f.write(f"  With: {row['with_access']:,} ({row['pct_with']:.1f}%)\n")
                f.write(f"  WITHOUT: {row['without_access']:,} ({row['pct_without']:.1f}%)\n\n")

    print(f"   ✓ Saved: {SUMMARY_TXT.name}")

    return df_stats


def analyze_boroughs(buildings):
    """Analyze by borough (admin_level_9)"""
    if not BOROUGHS.exists():
        print("\n⚠ Boroughs not found, skipping borough analysis")
        return None

    print("\n   • Boroughs...")
    print("     Loading boundaries...", end=' ', flush=True)
    boroughs = gpd.read_file(BOROUGHS)
    boroughs = boroughs[boroughs['name'].notna() & (boroughs['name'].str.len() > 0)]
    print(f"✓ {len(boroughs)}")

    if buildings.crs != boroughs.crs:
        buildings = buildings.to_crs(boroughs.crs)

    print("     Spatial join...", end=' ', flush=True)
    buildings_with_borough = gpd.sjoin(
        buildings,
        boroughs[['name', 'geometry']],
        how='left',
        predicate='within'
    )
    buildings_with_borough = buildings_with_borough.drop_duplicates(subset=['geometry'], keep='first')
    buildings_with_borough = buildings_with_borough.rename(columns={'name': 'borough'})
    if 'index_right' in buildings_with_borough.columns:
        buildings_with_borough = buildings_with_borough.drop(columns=['index_right'])
    print("✓")

    print("     Calculating stats...", end=' ', flush=True)
    stats = []
    for borough_name in buildings_with_borough['borough'].dropna().unique():
        borough_buildings = buildings_with_borough[buildings_with_borough['borough'] == borough_name]
        if len(borough_buildings) < 100:  # Skip tiny boroughs
            continue

        total = len(borough_buildings)
        with_access = borough_buildings['has_access'].sum()
        residential = len(borough_buildings[borough_buildings['building_type'] == 'budynki mieszkalne'])
        low_rise = len(borough_buildings[borough_buildings['height_category'] == '<3 kond.'])

        stats.append({
            'borough': borough_name,
            'total_buildings': total,
            'with_access': with_access,
            'without_access': total - with_access,
            'pct_with_access': with_access / total * 100,
            'pct_without_access': (total - with_access) / total * 100,
            'pct_residential': residential / total * 100,
            'pct_low_rise': low_rise / total * 100,
            'avg_zabkas': borough_buildings['num_points'].mean()
        })

    df_borough = pd.DataFrame(stats)
    print(f"✓ {len(df_borough)} boroughs")
    return df_borough


def create_charts(buildings, df_stats):
    """Create viral-worthy charts for LinkedIn/social media"""
    print("\n" + "="*80)
    print("CREATING VIRAL CHARTS")
    print("="*80)

    # Analyze boroughs
    df_boroughs = analyze_boroughs(buildings)

    # Chart 1: Stratification
    create_stratification_chart(buildings)

    # Chart 2: Height privilege
    create_height_scatter_chart(buildings)

    # Chart 3: Suburban divide
    create_suburban_divide_chart(buildings, df_stats)

    # Chart 4: Boroughs (if available)
    if df_boroughs is not None:
        create_boroughs_chart(df_boroughs)

        # Chart 5: Market opportunity matrix
        create_opportunity_matrix_chart(df_boroughs)


def create_stratification_chart(buildings):
    """Stratification chart INCLUDING buildings with NO access"""
    print("\n1. Stratification chart (with 'Brak')...", end=' ', flush=True)

    # Categories with density
    categories = {
        'budynki mieszkalne': {'label': 'Mieszkalne', 'density': True},
        'budynki handlowo-usługowe': {'label': 'Handlowo-usług.', 'density': True},
        'budynki biurowe': {'label': 'Biurowe', 'density': True},
        'budynki przemysłowe i magazynowe': {'label': 'Przemysłowe', 'density': False},
        'budynki oświaty i nauki': {'label': 'Edukacja', 'density': False},
    }

    # All tiers INCLUDING "Brak"
    tiers = ['Brak', '1-2 Ż', '3-4 Ż', '5-7 Ż', '8-10 Ż', '11-15 Ż', '16-20 Ż', '20+ Ż']

    chart_data = {}
    order = 0

    for cat_name, cat_info in categories.items():
        if cat_info['density']:
            for density_level, density_label, floor_range in [
                ('high', '>10 kond.', (10, 100)),
                ('medium', '3-10 kond.', (3, 10)),
                ('low', '<3 kond.', (0, 3))
            ]:
                areas = []
                for tier in tiers:
                    subset = buildings[
                        (buildings['building_type'] == cat_name) &
                        (buildings['zabka_tier'].astype(str) == tier) &
                        (buildings['estimated_floors'] > floor_range[0]) &
                        (buildings['estimated_floors'] <= floor_range[1])
                    ]
                    areas.append(subset['floor_area_m2'].sum() / 1e6)

                if sum(areas) > 0:
                    chart_data[f"{cat_info['label']} {density_label}"] = {
                        'values': areas,
                        'color': adjust_color(BUILDING_CATEGORIES[cat_name]['base_color'], density_level),
                        'order': order
                    }
                    order += 1
        else:
            areas = []
            for tier in tiers:
                subset = buildings[
                    (buildings['building_type'] == cat_name) &
                    (buildings['zabka_tier'].astype(str) == tier)
                ]
                areas.append(subset['floor_area_m2'].sum() / 1e6)

            if sum(areas) > 0:
                chart_data[cat_info['label']] = {
                    'values': areas,
                    'color': BUILDING_CATEGORIES[cat_name]['base_color'],
                    'order': order
                }
                order += 1

    # Other
    other_types = [t for t in buildings['building_type'].unique()
                   if t not in categories.keys()]
    other_areas = []
    for tier in tiers:
        subset = buildings[
            buildings['building_type'].isin(other_types) &
            (buildings['zabka_tier'].astype(str) == tier)
        ]
        other_areas.append(subset['floor_area_m2'].sum() / 1e6)

    if sum(other_areas) > 0:
        chart_data['Pozostałe'] = {
            'values': other_areas,
            'color': '#4D4D4D',
            'order': 999
        }

    # Plot
    sorted_items = sorted(chart_data.items(), key=lambda x: x[1]['order'])

    fig, ax = plt.subplots(figsize=(20, 9))
    fig.patch.set_facecolor('#1a1a1a')
    ax.set_facecolor('#1a1a1a')

    x_pos = range(len(tiers))
    bottom = [0] * len(tiers)

    for label, data in sorted_items:
        ax.bar(x_pos, data['values'], bottom=bottom, color=data['color'],
               label=label, width=0.75, edgecolor='#2a2a2a', linewidth=0.5)
        bottom = [b + v for b, v in zip(bottom, data['values'])]

    # Format x-labels
    tier_labels = []
    for tier in tiers:
        if tier == 'Brak':
            tier_labels.append('Brak\ndostępu')
        else:
            tier_labels.append(tier)

    ax.set_xticks(x_pos)
    ax.set_xticklabels(tier_labels, color='white', fontsize=11)
    ax.set_ylabel('Powierzchnia użytkowa (miliony m²)', color='white', fontsize=12)
    ax.tick_params(colors='white')

    ax.grid(axis='y', alpha=0.2, color='white', linestyle='-', linewidth=0.5)
    ax.set_axisbelow(True)

    for spine in ax.spines.values():
        spine.set_color('#3a3a3a')

    ax.legend(loc='upper left', frameon=True, facecolor='#2a2a2a',
             edgecolor='#3a3a3a', labelcolor='white', fontsize=9, ncol=2)

    ax.text(0.5, 1.06, 'Penetracja Rynku według Typu i Wysokości Zabudowy',
            transform=ax.transAxes, ha='center', color='white',
            fontsize=16, weight='bold')

    ax.text(0.02, 1.02, '"Brak" = niezagospodarowany segment rynku',
            transform=ax.transAxes, ha='left', color='#888888', fontsize=9)

    ax.text(0.98, 1.02, f'{len(buildings):,} budynków',
            transform=ax.transAxes, ha='right', color='#888888', fontsize=9)

    plt.tight_layout()
    plt.savefig(CHART_STRATIFICATION, dpi=150, facecolor='#1a1a1a', bbox_inches='tight')
    plt.close()
    print("✓")


def create_height_scatter_chart(buildings):
    """Scatter: floors vs Żabkas (including 0)"""
    print("3. Height privilege scatter...", end=' ', flush=True)

    key_types = ['budynki mieszkalne', 'budynki handlowo-usługowe', 'budynki biurowe']
    subset = buildings[buildings['building_type'].isin(key_types)].copy()

    # Add jitter
    subset['floors_jitter'] = subset['estimated_floors'] + np.random.uniform(-0.3, 0.3, len(subset))
    subset['zabka_jitter'] = subset['num_points'] + np.random.uniform(-0.3, 0.3, len(subset))

    fig, ax = plt.subplots(figsize=(14, 8))
    fig.patch.set_facecolor('#1a1a1a')
    ax.set_facecolor('#1a1a1a')

    for btype in key_types:
        data = subset[subset['building_type'] == btype]
        color = BUILDING_CATEGORIES[btype]['base_color']
        label = BUILDING_CATEGORIES[btype]['description']

        ax.scatter(data['floors_jitter'], data['zabka_jitter'],
                  c=color, label=label, alpha=0.4, s=20, edgecolors='none')

        # Trend line
        if len(data) > 10:
            z = np.polyfit(data['estimated_floors'], data['num_points'], 1)
            p = np.poly1d(z)
            x_trend = np.linspace(data['estimated_floors'].min(), data['estimated_floors'].max(), 100)
            ax.plot(x_trend, p(x_trend), color=color, linewidth=2, alpha=0.8, linestyle='--')

    ax.set_xlabel('Liczba kondygnacji', color='white', fontsize=12)
    ax.set_ylabel('Liczba Żabek w zasięgu (włącznie z 0!)', color='white', fontsize=12)
    ax.tick_params(colors='white')

    ax.grid(True, alpha=0.2, color='white')
    ax.set_axisbelow(True)

    for spine in ax.spines.values():
        spine.set_color('#3a3a3a')

    ax.legend(loc='upper left', frameon=True, facecolor='#2a2a2a',
             edgecolor='#3a3a3a', labelcolor='white', fontsize=11)

    ax.text(0.5, 1.05, 'Korelacja: Im wyższa zabudowa, tym większa penetracja',
            transform=ax.transAxes, ha='center', color='white',
            fontsize=15, weight='bold')

    ax.text(0.02, 1.01, 'Wnioski: Gęsta zabudowa = wysoka konkurencja. Niska zabudowa = niezaspokojony popyt.',
            transform=ax.transAxes, ha='left', color='#888888', fontsize=9)

    plt.tight_layout()
    plt.savefig(CHART_HEIGHT_PRIVILEGE, dpi=150, facecolor='#1a1a1a', bbox_inches='tight')
    plt.close()
    print("✓")


def create_suburban_divide_chart(buildings, df_stats):
    """Viral chart: suburbs vs city center"""
    print("\n3. Suburban divide chart...", end=' ', flush=True)

    # Compare low-rise residential vs high-rise
    categories = [
        ('Domy\njednorodzinne\n(<3 kond.)', 'budynki mieszkalne', '<3 kond.'),
        ('Kamienice\n(3-10 kond.)', 'budynki mieszkalne', '3-10 kond.'),
        ('Wieżowce\nmieszkalne\n(>10 kond.)', 'budynki mieszkalne', '>10 kond.'),
        ('Biurowce\n(>10 kond.)', 'budynki biurowe', '>10 kond.'),
    ]

    fig, ax = plt.subplots(figsize=(14, 9))
    fig.patch.set_facecolor('#1a1a1a')
    ax.set_facecolor('#1a1a1a')

    data_with = []
    data_without = []
    labels = []
    colors_with = []
    colors_without = []

    for label, btype, height in categories:
        subset = buildings[
            (buildings['building_type'] == btype) &
            (buildings['height_category'] == height)
        ]

        if len(subset) > 0:
            pct_with = subset['has_access'].sum() / len(subset) * 100
            pct_without = 100 - pct_with

            data_with.append(pct_with)
            data_without.append(pct_without)
            labels.append(label)

            # Colors
            if pct_without > 60:
                colors_without.append('#FF3333')  # Bad - red
                colors_with.append('#FF9999')
            else:
                colors_without.append('#FFAA00')  # OK - orange
                colors_with.append('#00FF00')  # Good - green

    x = range(len(labels))
    width = 0.7

    # Stacked bars
    ax.bar(x, data_with, width, label='Z dostępem', color='#00AA00', edgecolor='#2a2a2a', linewidth=1)
    ax.bar(x, data_without, width, bottom=data_with, label='BEZ dostępu', color='#CC0000', edgecolor='#2a2a2a', linewidth=1)

    # Add percentage labels
    for i, (w, wo) in enumerate(zip(data_with, data_without)):
        # With access label
        if w > 10:
            ax.text(i, w/2, f'{w:.0f}%', ha='center', va='center',
                   color='white', fontsize=16, weight='bold')
        # Without access label
        if wo > 10:
            ax.text(i, w + wo/2, f'{wo:.0f}%', ha='center', va='center',
                   color='white', fontsize=16, weight='bold')

    ax.set_xticks(x)
    ax.set_xticklabels(labels, color='white', fontsize=13, weight='bold')
    ax.set_ylabel('Procent budynków', color='white', fontsize=14)
    ax.set_ylim(0, 100)
    ax.tick_params(colors='white')

    ax.grid(axis='y', alpha=0.2, color='white')
    ax.set_axisbelow(True)

    for spine in ax.spines.values():
        spine.set_color('#3a3a3a')

    ax.legend(loc='upper right', frameon=True, facecolor='#2a2a2a',
             edgecolor='#3a3a3a', labelcolor='white', fontsize=12)

    ax.text(0.5, 1.08, 'Analiza Rynku: Saturacja vs Potencjał Wzrostu',
            transform=ax.transAxes, ha='center', color='white',
            fontsize=18, weight='bold')

    ax.text(0.02, 1.03, 'Przedmieścia = największy potencjał ekspansji',
            transform=ax.transAxes, ha='left', color='#888888', fontsize=11)

    plt.tight_layout()
    plt.savefig(CHART_SUBURBAN_DIVIDE, dpi=150, facecolor='#1a1a1a', bbox_inches='tight')
    plt.close()
    print("✓")


def create_boroughs_chart(df_boroughs):
    """Borough penetration rates"""
    print("\n4. Borough penetration chart...", end=' ', flush=True)

    # Sort by penetration rate (ascending - lowest first)
    df_sorted = df_boroughs.sort_values('pct_with_access', ascending=True)

    fig, ax = plt.subplots(figsize=(14, 10))
    fig.patch.set_facecolor('#1a1a1a')
    ax.set_facecolor('#1a1a1a')

    y_pos = range(len(df_sorted))

    # Color gradient: red for low penetration, green for high
    colors = []
    for pct in df_sorted['pct_with_access']:
        if pct < 40:
            colors.append('#FF3333')  # Red - low penetration
        elif pct < 60:
            colors.append('#FF9933')  # Orange - medium-low
        elif pct < 75:
            colors.append('#FFCC00')  # Yellow - medium
        else:
            colors.append('#00CC00')  # Green - high penetration

    bars = ax.barh(y_pos, df_sorted['pct_with_access'], color=colors,
                   edgecolor='#2a2a2a', linewidth=1)

    # Add percentage labels on bars
    for i, (idx, row) in enumerate(df_sorted.iterrows()):
        ax.text(row['pct_with_access'] + 1, i, f"{row['pct_with_access']:.0f}%",
                va='center', color='white', fontsize=9, weight='bold')

    ax.set_yticks(y_pos)
    ax.set_yticklabels(df_sorted['borough'], color='white', fontsize=11)
    ax.set_xlabel('Penetracja rynku (%)', color='white', fontsize=13, weight='bold')
    ax.set_xlim(0, 110)  # Extra space for labels
    ax.set_title('Penetracja Rynku według Dzielnicy',
                 color='white', fontsize=18, weight='bold', pad=20)

    ax.text(0.02, 1.02, 'Czerwony = potencjał ekspansji  |  Zielony = rynek nasycony',
            transform=ax.transAxes, ha='left', color='#888888', fontsize=10)

    ax.tick_params(colors='white', labelsize=10)
    ax.grid(axis='x', alpha=0.2, color='white', linewidth=0.5)

    for spine in ax.spines.values():
        spine.set_color('#3a3a3a')

    plt.tight_layout()
    plt.savefig(CHART_BOROUGHS, dpi=150, facecolor='#1a1a1a', bbox_inches='tight')
    plt.close()
    print("✓")


def create_opportunity_matrix_chart(df_boroughs):
    """Market opportunity matrix: size vs penetration"""
    print("\n5. Market opportunity matrix...", end=' ', flush=True)

    fig, ax = plt.subplots(figsize=(14, 10))
    fig.patch.set_facecolor('#1a1a1a')
    ax.set_facecolor('#1a1a1a')

    # Bubble chart
    x = df_boroughs['total_buildings']
    y = df_boroughs['pct_with_access']
    sizes = df_boroughs['without_access']

    # Normalize bubble sizes (scale to reasonable range)
    size_scale = (sizes - sizes.min()) / (sizes.max() - sizes.min()) * 2000 + 200

    # Color based on quadrant strategy
    colors = []
    for _, row in df_boroughs.iterrows():
        market_size = row['total_buildings']
        penetration = row['pct_with_access']

        median_size = df_boroughs['total_buildings'].median()
        median_pen = df_boroughs['pct_with_access'].median()

        if market_size >= median_size and penetration < median_pen:
            colors.append('#FF3333')  # Large market + low penetration = PRIORITY
        elif market_size >= median_size and penetration >= median_pen:
            colors.append('#00CC00')  # Large market + high penetration = MAINTAIN
        elif market_size < median_size and penetration < median_pen:
            colors.append('#FF9933')  # Small market + low penetration = EVALUATE
        else:
            colors.append('#66FF66')  # Small market + high penetration = SATURATED NICHE

    scatter = ax.scatter(x, y, s=size_scale, c=colors, alpha=0.7,
                        edgecolors='white', linewidth=1.5)

    # Add borough labels
    for _, row in df_boroughs.iterrows():
        ax.annotate(row['borough'],
                   (row['total_buildings'], row['pct_with_access']),
                   fontsize=9, color='white', weight='bold',
                   ha='center', va='center')

    # Draw quadrant lines
    median_size = df_boroughs['total_buildings'].median()
    median_pen = df_boroughs['pct_with_access'].median()

    ax.axhline(median_pen, color='#666666', linestyle='--', linewidth=1, alpha=0.5)
    ax.axvline(median_size, color='#666666', linestyle='--', linewidth=1, alpha=0.5)

    # Quadrant labels
    max_x = x.max()
    max_y = y.max()

    ax.text(median_size * 1.5, median_pen * 0.5,
           '🎯 PRIORYTET EKSPANSJI\n(duży rynek, niska penetracja)',
           ha='center', va='center', color='#FF6666', fontsize=11,
           style='italic', weight='bold', alpha=0.7)

    ax.text(median_size * 1.5, median_pen * 1.3,
           '🏆 UTRZYMAĆ DOMINACJĘ\n(duży rynek, wysoka penetracja)',
           ha='center', va='center', color='#66FF66', fontsize=11,
           style='italic', weight='bold', alpha=0.7)

    ax.text(median_size * 0.4, median_pen * 0.5,
           '🤔 OCENIĆ POTENCJAŁ\n(mały rynek, niska penetracja)',
           ha='center', va='center', color='#FFAA66', fontsize=11,
           style='italic', weight='bold', alpha=0.7)

    ax.text(median_size * 0.4, median_pen * 1.3,
           '✅ NISZA NASYCONA\n(mały rynek, wysoka penetracja)',
           ha='center', va='center', color='#99FF99', fontsize=11,
           style='italic', weight='bold', alpha=0.7)

    # Labels and styling
    ax.set_xlabel('Wielkość rynku (liczba budynków)', color='white',
                 fontsize=13, weight='bold')
    ax.set_ylabel('Penetracja rynku (%)', color='white',
                 fontsize=13, weight='bold')
    ax.set_title('Matryca Możliwości Rynkowych według Dzielnicy',
                color='white', fontsize=18, weight='bold', pad=20)

    ax.text(0.02, 1.02, 'Wielkość bąbelka = liczba budynków bez dostępu (potencjał)',
           transform=ax.transAxes, ha='left', color='#888888', fontsize=10)

    ax.tick_params(colors='white', labelsize=10)
    ax.grid(alpha=0.15, color='white', linewidth=0.5)

    for spine in ax.spines.values():
        spine.set_color('#3a3a3a')

    plt.tight_layout()
    plt.savefig(CHART_OPPORTUNITY_MATRIX, dpi=150, facecolor='#1a1a1a', bbox_inches='tight')
    plt.close()
    print("✓")


def main():
    start_time = datetime.now()

    print("="*80)
    print("COMPLETE WARSAW ŻABKA ANALYSIS")
    print("All buildings (including those with NO access)")
    print("="*80)

    # Load and classify ALL buildings
    buildings = load_and_classify_buildings()
    if buildings is None:
        return

    # Add Żabka access info
    buildings = add_zabka_access(buildings)
    if buildings is None:
        return

    # Save
    save_buildings(buildings)

    # Calculate stats
    df_stats = calculate_statistics(buildings)

    # Create charts
    create_charts(buildings, df_stats)

    elapsed = (datetime.now() - start_time).total_seconds()

    print("\n" + "="*80)
    print(f"🎉 COMPLETE! ({elapsed/60:.1f} minutes)")
    print("="*80)

    print(f"\nFiles created in output/:")
    print(f"\n  📊 VIRAL CHARTS (for LinkedIn/social media):")
    print(f"    • {CHART_STRATIFICATION.name}")
    print(f"    • {CHART_HEIGHT_PRIVILEGE.name}")
    print(f"    • {CHART_SUBURBAN_DIVIDE.name}")
    print(f"    • {CHART_BOROUGHS.name}")
    print(f"    • {CHART_OPPORTUNITY_MATRIX.name}")
    print(f"\n  📁 Data files:")
    print(f"    • {BUILDINGS_CLASSIFIED.name}")
    print(f"    • {STATS_CSV.name}")

    with_acc = buildings['has_access'].sum()
    pct_without = (len(buildings)-with_acc)/len(buildings)*100
    print(f"\n💥 VIRAL HEADLINE:")
    print(f"  '{pct_without:.0f}% budynków Warszawy NIE MA dostępu do Żabki!'")
    print(f"\n🎯 Post to LinkedIn with chart 00_zabka_glowny_wykres.png!")


if __name__ == "__main__":
    main()
