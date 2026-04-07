from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

FIRE_SCORE_MIN = 1.0
FIRE_SCORE_MAX = 4.0
FIRE_SCALE_METADATA_KEY = "fire_scale"
FIRE_SCALE_VERSION = "low_to_high_v1"
CANONICAL_FIRE_SCALE_METADATA = {
    "version": FIRE_SCALE_VERSION,
    "direction": "low_to_high",
    "meaning": "1 means low fire hazard and 4 means high fire hazard",
}

CANONICAL_FIRE_LABELS = {
    1: "MAJHNA OGROZENOST",
    2: "SREDNJA OGROZENOST",
    3: "VELIKA OGROZENOST",
    4: "ZELO VELIKA OGROZENOST",
}


def read_json_file(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"{path} is not a JSON object.")
    return payload


def write_json_file(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def is_canonical_fire_scale(payload: dict[str, Any]) -> bool:
    metadata = payload.get(FIRE_SCALE_METADATA_KEY)
    if not isinstance(metadata, dict):
        return False
    return (
        metadata.get("version") == FIRE_SCALE_VERSION
        and metadata.get("direction") == "low_to_high"
    )


def ensure_canonical_fire_scale(
    payload: dict[str, Any],
    *,
    fields: tuple[str, ...],
    source_note: str,
) -> dict[str, Any]:
    if payload.get("type") != "FeatureCollection":
        raise ValueError("Expected a GeoJSON FeatureCollection.")

    if is_canonical_fire_scale(payload):
        return payload

    features = payload.get("features")
    if not isinstance(features, list):
        raise ValueError("FeatureCollection has no features array.")

    for feature in features:
        if not isinstance(feature, dict):
            continue
        properties = feature.get("properties")
        if not isinstance(properties, dict):
            continue
        for field in fields:
            if field not in properties:
                continue
            properties[field] = standardize_legacy_fire_score(properties[field])

    metadata = dict(CANONICAL_FIRE_SCALE_METADATA)
    metadata["source"] = source_note
    payload[FIRE_SCALE_METADATA_KEY] = metadata
    return payload


def build_canonical_fire_overlay(payload: dict[str, Any], *, source_note: str) -> dict[str, Any]:
    canonical = ensure_canonical_fire_scale(
        copy.deepcopy(payload),
        fields=("pozar",),
        source_note=source_note,
    )
    canonical["name"] = "pozarna_ogrozenost_majhen_100m_canonical"

    features = canonical.get("features")
    if not isinstance(features, list):
        return canonical

    for feature in features:
        if not isinstance(feature, dict):
            continue
        properties = feature.get("properties")
        if not isinstance(properties, dict):
            continue
        score = to_number(properties.get("pozar"))
        if score is None:
            continue
        label = CANONICAL_FIRE_LABELS.get(int(round(score)))
        if label:
            properties["pozar_nazi"] = label

    return canonical


def standardize_legacy_fire_score(value: Any) -> Any:
    number = to_number(value)
    if number is None:
        return value

    standardized = rounded_fire_score(FIRE_SCORE_MIN + FIRE_SCORE_MAX - number)
    if isinstance(value, str):
        if standardized.is_integer():
            return str(int(standardized))
        return f"{standardized:.1f}"
    return standardized


def rounded_fire_score(value: float) -> float:
    return round(float(value) + 1e-9, 1)


def to_number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        number = float(value)
    elif isinstance(value, str):
        try:
            number = float(value.strip().replace(",", "."))
        except ValueError:
            return None
    else:
        return None

    if number != number or number in {float("inf"), float("-inf")}:
        return None
    return number
