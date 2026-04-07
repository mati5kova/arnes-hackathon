from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    from AI.fire_pipeline import is_canonical_fire_scale, read_json_file
except ModuleNotFoundError:
    from fire_pipeline import is_canonical_fire_scale, read_json_file

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_EMBEDDING_DATA_PATH = BASE_DIR / "Data" / "kd_z_nevarnost_enriched_verified.geojson"

EMBED_TEXT_FIELDS = (
    "IME",
    "SINONIMI",
    "OPIS",
    "ZVRST",
    "TIP",
    "GESLA",
    "DATACIJA",
    "LOKACIJAOPIS",
    "prevladujoci_material",
    "UE_UIME",
    "OBCINA",
)

EMBED_METADATA_FIELDS = (
    "EID",
    "OBCINA",
    "STATUS",
    "SPOMENIK",
    "UE_UIME",
    "prevladujoci_material",
    "pozar_ocena_popravljena",
    "poplave_ocena_popravljena",
    "potres_ocena_popravljena",
    "plazovi_ocena_popravljena",
)


def load_canonical_embedding_payload(path: Path = DEFAULT_EMBEDDING_DATA_PATH) -> dict[str, Any]:
    payload = read_json_file(path)
    if not is_canonical_fire_scale(payload):
        raise ValueError(
            f"{path} is missing canonical fire-scale metadata. Run the fire-data pipeline first."
        )
    return payload


def build_embedding_records(payload: dict[str, Any]) -> list[dict[str, Any]]:
    if payload.get("type") != "FeatureCollection":
        raise ValueError("Expected a GeoJSON FeatureCollection.")

    features = payload.get("features")
    if not isinstance(features, list):
        raise ValueError("FeatureCollection has no features array.")

    records: list[dict[str, Any]] = []
    for feature in features:
        if not isinstance(feature, dict):
            continue
        properties = feature.get("properties")
        if not isinstance(properties, dict):
            continue

        eid = properties.get("EID")
        if eid is None:
            continue

        records.append(
            {
                "eid": str(eid),
                "text": feature_to_embed_text(properties),
                "meta_data": build_metadata(properties),
            }
        )

    return records


def feature_to_embed_text(properties: dict[str, Any]) -> str:
    parts: list[str] = []

    for field in EMBED_TEXT_FIELDS:
        if field not in properties:
            continue
        value = properties.get(field)
        if is_empty_value(value):
            continue

        rendered = render_text_value(value)
        if not rendered:
            continue

        if field == "prevladujoci_material":
            parts.append(f"material: {rendered}")
        elif field == "UE_UIME":
            parts.append(f"okraj: {rendered}")
        else:
            parts.append(f"{field.lower()}: {rendered}")

    return " | ".join(parts)


def build_metadata(properties: dict[str, Any]) -> dict[str, Any]:
    metadata: dict[str, Any] = {}

    for field in EMBED_METADATA_FIELDS:
        value = properties.get(field)
        if is_empty_value(value):
            metadata[field] = ""
            continue

        if isinstance(value, (list, tuple)):
            items = [str(item) for item in value if not is_empty_value(item)]
            metadata[field] = ", ".join(items) if items else ""
            continue

        metadata[field] = value

    return metadata


def render_text_value(value: Any) -> str:
    if isinstance(value, (list, tuple)):
        items = [str(item).strip() for item in value if not is_empty_value(item)]
        return " ".join(item for item in items if item).strip()
    return str(value).strip()


def is_empty_value(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, tuple)):
        return not any(not is_empty_value(item) for item in value)
    return False
