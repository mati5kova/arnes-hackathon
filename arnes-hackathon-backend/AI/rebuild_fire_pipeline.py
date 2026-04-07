from __future__ import annotations

from pathlib import Path

try:
    from AI.standardize_fire_outputs import main as standardize_fire_outputs_main
    from AI.sync_chroma_metadata import sync_chroma_metadata
    from AI.verify_enrich_geojson import main as verify_enrich_geojson_main
except ModuleNotFoundError:
    from standardize_fire_outputs import main as standardize_fire_outputs_main
    from sync_chroma_metadata import sync_chroma_metadata
    from verify_enrich_geojson import main as verify_enrich_geojson_main

BASE_DIR = Path(__file__).resolve().parent
CHROMA_PATH = BASE_DIR / "Data" / "chroma_db"


def main() -> None:
    standardize_fire_outputs_main()
    verify_enrich_geojson_main()
    if CHROMA_PATH.exists():
        sync_chroma_metadata()
    else:
        print(f"Skipping Chroma sync because {CHROMA_PATH} does not exist.")


if __name__ == "__main__":
    main()
