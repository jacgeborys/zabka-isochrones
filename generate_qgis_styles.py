"""
Generate Dynamic QGIS Styles Based on Actual Data
Creates optimized color bins based on the actual max num_points in your coverage map.

Usage:
    python generate_dynamic_style.py <poi_id>
    python generate_dynamic_style.py church
"""
import sys
import geopandas as gpd
from pathlib import Path
from poi_config import get_poi, poi_files

# Color palettes (light to very dark)
COLOR_PALETTES = {
    "zabka": {
        "name": "Żabka",
        "colors": [
            (150, 255, 145),  # Light bright green (clearly visible)
            (100, 255, 95),   # Lighter neon green
            (50, 255, 45),    # Bright neon green
            (18, 255, 1),     # Żabka signature green #12ff01
            (15, 220, 1),     # Slightly darker neon
            (12, 180, 1),     # Medium neon green
            (10, 140, 1),     # Darker green
            (8, 100, 1),      # Deep green
            (5, 60, 1),       # Very dark green
            (3, 30, 1),       # Almost black-green
        ],
    },
    "pharmacy": {
        "name": "Pharmacy",
        "colors": [
            (239, 154, 154),  # Medium light pink (clearly visible)
            (229, 115, 115),
            (239, 83, 80),
            (244, 67, 54),
            (229, 57, 53),
            (211, 47, 47),
            (198, 40, 40),
            (183, 28, 28),
            (136, 14, 14),
            (60, 6, 6),       # Almost black-red
        ],
    },
    "church": {
        "name": "Church",
        "colors": [
            (206, 147, 216),  # Medium light purple (clearly visible)
            (186, 104, 200),
            (171, 71, 188),
            (156, 39, 176),
            (142, 36, 170),
            (123, 31, 162),
            (106, 27, 154),
            (74, 20, 134),
            (49, 12, 66),
            (20, 5, 30),      # Almost black-purple
        ],
    },
    "parcel_locker": {
        "name": "Paczkomat",
        "colors": [
            (245, 210, 90),   # Rich light yellow (slightly darker min)
            (255, 205, 50),   # Bright yellow
            (255, 203, 5),    # InPost signature yellow #ffcb05
            (255, 190, 0),    # Golden yellow
            (255, 170, 0),    # Yellow-orange (orange starts here)
            (250, 145, 0),    # Orange-yellow
            (240, 120, 0),    # Orange
            (220, 90, 0),     # Deep orange
            (170, 60, 0),     # Brown-orange
            (80, 25, 0),      # Very dark brown-orange (almost black)
        ],
    },
    "elementary_school": {
        "name": "School",
        "colors": [
            (179, 229, 252),  # Very light blue (bright, visible)
            (144, 202, 249),  # Light blue
            (100, 181, 246),  # Sky blue
            (66, 165, 245),   # Bright blue
            (42, 150, 243),   # Medium blue
            (33, 150, 243),   # Vivid blue
            (25, 118, 210),   # Deep blue
            (21, 101, 192),   # Darker blue
            (13, 71, 161),    # Very dark blue
            (10, 50, 120),    # Almost black-blue
        ],
    },
}


def generate_bins(max_value, num_bins=8):
    """Generate smart bins based on max value."""
    if max_value <= 1:
        return [(1, 1)]

    if max_value <= 10:
        # For small datasets, use simple bins
        bins = []
        bins.append((1, 1))
        if max_value >= 3:
            bins.append((2, 3))
        if max_value >= 5:
            bins.append((4, min(5, max_value)))
        if max_value >= 7:
            bins.append((6, min(7, max_value)))
        if max_value >= 9:
            bins.append((8, max_value))
        return bins

    # For larger datasets, create logarithmic-ish bins
    bins = [(1, 1)]

    thresholds = [3, 6, 10, 15, 20, 30, int(max_value * 0.7)]
    prev = 1

    for threshold in thresholds:
        if threshold < max_value:
            bins.append((prev + 1, threshold))
            prev = threshold
        else:
            break

    # Add final bin for the maximum
    bins.append((prev + 1, max_value))

    return bins


def format_label(poi_name, lower, upper):
    """Format bin label with proper Polish grammar."""
    if lower == upper:
        return f"{lower} {poi_name}"
    elif upper >= 999999:
        return f"{lower}+ {poi_name}"
    else:
        return f"{lower}-{upper} {poi_name}"


def generate_qml(poi_id, coverage_file, output_file):
    """Generate dynamic QML style file."""
    print(f"Reading coverage map: {coverage_file}")
    gdf = gpd.read_file(coverage_file)

    if 'num_points' not in gdf.columns:
        print("ERROR: Coverage map doesn't have 'num_points' column!")
        return False

    max_points = int(gdf['num_points'].max())
    min_points = int(gdf['num_points'].min())

    print(f"  Range: {min_points} to {max_points} POIs")

    # Get color palette
    palette = COLOR_PALETTES.get(poi_id, COLOR_PALETTES["zabka"])
    colors = palette["colors"]
    poi_name = palette["name"]

    # Generate bins
    bins = generate_bins(max_points)
    print(f"  Generated {len(bins)} bins")

    # Build QML XML
    qml_lines = [
        '<!DOCTYPE qgis PUBLIC \'http://mrcc.com/qgis.dtd\' \'SYSTEM\'>',
        '<qgis version="3.28.0" styleCategories="Symbology">',
        '  <renderer-v2 type="graduatedSymbol" attr="num_points" enableorderby="0" forceraster="0" symbollevels="0">',
        '    <ranges>',
    ]

    # Add range definitions
    for i, (lower, upper) in enumerate(bins):
        label = format_label(poi_name, lower, upper)
        upper_val = 999999 if i == len(bins) - 1 else upper
        qml_lines.append(
            f'      <range render="true" label="{label}" '
            f'lower="{lower}.000000" upper="{upper_val}.000000" symbol="{i}"/>'
        )

    qml_lines.append('    </ranges>')
    qml_lines.append('    <symbols>')

    # Add symbol definitions with progressive opacity
    for i, (lower, upper) in enumerate(bins):
        # Progressive opacity: 0.65 to 0.95
        opacity = 0.65 + (i / (len(bins) - 1)) * 0.3

        # Select color from palette (map bin index to color index)
        color_idx = min(int(i / len(bins) * len(colors)), len(colors) - 1)
        r, g, b = colors[color_idx]

        qml_lines.extend([
            f'      <symbol type="fill" name="{i}" alpha="{opacity:.2f}" clip_to_extent="1" force_rhr="0">',
            f'        <data_defined_properties>',
            f'          <Option type="Map">',
            f'            <Option type="QString" name="name" value=""/>',
            f'            <Option name="properties"/>',
            f'            <Option type="QString" name="type" value="collection"/>',
            f'          </Option>',
            f'        </data_defined_properties>',
            f'        <layer class="SimpleFill" locked="0" pass="0" enabled="1">',
            f'          <effect type="effectStack" enabled="1">',
            f'            <effect type="blur">',
            f'              <Option type="Map">',
            f'                <Option type="QString" name="blend_mode" value="0"/>',
            f'                <Option type="QString" name="blur_level" value="0.5"/>',
            f'                <Option type="QString" name="blur_method" value="0"/>',
            f'                <Option type="QString" name="draw_mode" value="2"/>',
            f'                <Option type="QString" name="enabled" value="1"/>',
            f'                <Option type="QString" name="opacity" value="1"/>',
            f'              </Option>',
            f'            </effect>',
            f'          </effect>',
            f'          <prop k="color" v="{r},{g},{b},255"/>',
            f'          <prop k="outline_color" v="35,35,35,0"/>',
            f'          <prop k="outline_style" v="solid"/>',
            f'          <prop k="outline_width" v="0"/>',
            f'          <prop k="style" v="solid"/>',
            f'        </layer>',
            f'      </symbol>',
        ])

    qml_lines.extend([
        '    </symbols>',
        '  </renderer-v2>',
        '  <blendMode>0</blendMode>',
        '  <featureBlendMode>0</featureBlendMode>',
        '  <layerOpacity>1</layerOpacity>',
        '</qgis>',
    ])

    # Write QML file
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(qml_lines))

    print(f"\n✓ Generated: {output_file}")
    print(f"  Bins: {bins}")
    print(f"  Opacity range: 65% → 95%")
    print(f"  Colors: Medium {poi_name.lower()} → Almost black")

    return True


def main():
    if len(sys.argv) < 2:
        print("Usage: python generate_dynamic_style.py <poi_id>")
        print("\nExample:")
        print("  python generate_dynamic_style.py church")
        print("  python generate_dynamic_style.py parcel_locker")
        sys.exit(1)

    poi_id = sys.argv[1]

    try:
        poi = get_poi(poi_id)
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)

    files = poi_files(poi)
    coverage_file = files["coverage"]

    if not coverage_file.exists():
        print(f"ERROR: Coverage map not found: {coverage_file}")
        print(f"\nPlease run the pipeline first:")
        print(f"  python run_pipeline.py {poi_id}")
        sys.exit(1)

    # Generate style file
    styles_dir = Path(__file__).parent / "styles"
    styles_dir.mkdir(exist_ok=True)

    output_file = styles_dir / f"{poi_id}_coverage_style.qml"

    print("=" * 60)
    print(f"{poi['label']} Dynamic Style Generator")
    print("=" * 60)

    success = generate_qml(poi_id, coverage_file, output_file)

    if success:
        print("\n" + "=" * 60)
        print("Done! Load this style in QGIS:")
        print("=" * 60)
        print(f"1. Right-click layer → Styles → Load Style")
        print(f"2. Select: {output_file.name}")
        print()


if __name__ == "__main__":
    main()
