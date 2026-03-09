"""
Pipeline Runner
Runs the full analysis pipeline for all enabled POIs in poi_config.py.y
Steps where the output file already exists are skipped automatically.

Usage:
    python run_pipeline.py              # skip existing outputs
    python run_pipeline.py --force      # re-run all steps, overwrite existing
    python run_pipeline.py church       # run only a specific POI
"""
import sys
import subprocess
from pathlib import Path
from datetime import datetime

from poi_config import get_enabled_pois, get_poi, poi_files

SCRIPTS_DIR = Path(__file__).parent

# Pipeline steps: (script, output_key, extra_flags_when_forced)
STEPS = [
    ("01_fetch_poi_osm.py",             "stores",     ["--force"]),
    ("03_generate_isochrones_local.py", "isochrones", []),
    ("04_create_coverage_map.py",       "coverage",   []),
    ("05_intersect_buildings.py",       "buildings",  []),
]


def run_step(script, poi_id, extra_args=()):
    cmd = [sys.executable, str(SCRIPTS_DIR / script), poi_id] + list(extra_args)
    result = subprocess.run(cmd, cwd=SCRIPTS_DIR)
    return result.returncode == 0


def print_plan(pois, force):
    print("\nPipeline plan:")
    for poi in pois:
        files = poi_files(poi)
        print(f"\n  {poi['label']} ({poi['id']})")
        for script, key, _ in STEPS:
            path   = files[key]
            exists = path.exists()
            if force or not exists:
                status = "RUN"
            else:
                status = f"SKIP (exists: {path.name})"
            print(f"    {script:<40} {status}")


def main():
    force      = "--force" in sys.argv
    explicit   = [a for a in sys.argv[1:] if not a.startswith("--")]

    if explicit:
        try:
            pois = [get_poi(pid) for pid in explicit]
        except ValueError as e:
            print(e)
            sys.exit(1)
    else:
        pois = get_enabled_pois()

    if not pois:
        print("No enabled POIs found in poi_config.py")
        sys.exit(0)

    print("=" * 60)
    print("Warsaw POI Pipeline Runner")
    print("=" * 60)
    print(f"POIs to process: {[p['id'] for p in pois]}")
    print(f"Force re-run:    {force}")

    print_plan(pois, force)

    print()
    confirm = input("Proceed? (y/n): ")
    if confirm.lower() != 'y':
        print("Aborted.")
        sys.exit(0)

    overall_start = datetime.now()
    results = {}

    for poi in pois:
        poi_id = poi["id"]
        files  = poi_files(poi)

        print(f"\n{'#' * 60}")
        print(f"# {poi['label']} ({poi_id})")
        print(f"{'#' * 60}")

        poi_start = datetime.now()
        poi_ok    = True

        for script, key, force_flags in STEPS:
            output_path = files[key]

            if not force and output_path.exists():
                print(f"  Skipping {script} (output exists)")
                continue

            print(f"\n  --- {script} ---")
            extra = force_flags if force else []
            ok    = run_step(script, poi_id, extra)

            if not ok:
                print(f"\n  Pipeline failed at {script} for {poi_id}. Stopping this POI.")
                poi_ok = False
                break

        elapsed = (datetime.now() - poi_start).total_seconds()
        results[poi_id] = {"ok": poi_ok, "elapsed": elapsed}

    # Final summary
    total = (datetime.now() - overall_start).total_seconds()
    print(f"\n{'=' * 60}")
    print(f"Pipeline complete  ({total/60:.1f} min total)")
    print(f"{'=' * 60}")
    for poi_id, r in results.items():
        status = "OK" if r["ok"] else "FAILED"
        print(f"  {poi_id:<20} {status}  ({r['elapsed']/60:.1f} min)")
    print()


if __name__ == "__main__":
    main()