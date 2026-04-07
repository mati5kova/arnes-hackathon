from __future__ import annotations

from pathlib import Path

try:
    from AI.fire_pipeline import (
        build_canonical_fire_overlay,
        ensure_canonical_fire_scale,
        read_json_file,
        write_json_file,
    )
except ModuleNotFoundError:
    from fire_pipeline import (
        build_canonical_fire_overlay,
        ensure_canonical_fire_scale,
        read_json_file,
        write_json_file,
    )

BASE_DIR = Path(__file__).resolve().parent
SITE_DATA_FILES = (
    BASE_DIR / "Data" / "brez_filanja_lukenj.geojson",
    BASE_DIR / "Data" / "kd_z_nevarnost.geojson",
    BASE_DIR / "Data" / "kd_visine.geojson",
)
RAW_FIRE_OVERLAY_PATH = BASE_DIR / "Data_Processing" / "pozarna_ogrozenost_majhen_100m.geojson"
CANONICAL_FIRE_OVERLAY_PATH = BASE_DIR / "Data" / "pozarna_ogrozenost_majhen_100m_canonical.geojson"


def standardize_site_files() -> None:
    for path in SITE_DATA_FILES:
        payload = read_json_file(path)
        ensure_canonical_fire_scale(
            payload,
            fields=("pozar",),
            source_note=f"standardized from legacy fire semantics in {path.name}",
        )
        write_json_file(path, payload)
        print(f"Standardized fire scale in {path}")


def build_overlay_file() -> None:
    raw_overlay = read_json_file(RAW_FIRE_OVERLAY_PATH)
    canonical_overlay = build_canonical_fire_overlay(
        raw_overlay,
        source_note=f"derived from {RAW_FIRE_OVERLAY_PATH.name} without altering source geometry",
    )
    write_json_file(CANONICAL_FIRE_OVERLAY_PATH, canonical_overlay)
    print(f"Wrote canonical fire overlay to {CANONICAL_FIRE_OVERLAY_PATH}")


def main() -> None:
    standardize_site_files()
    build_overlay_file()


if __name__ == "__main__":
    main()
