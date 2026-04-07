from __future__ import annotations

from AI.fire_pipeline import (
    CANONICAL_FIRE_LABELS,
    FIRE_SCALE_METADATA_KEY,
    build_canonical_fire_overlay,
    ensure_canonical_fire_scale,
)


def test_ensure_canonical_fire_scale_flips_legacy_site_scores_once():
    payload = {
        "type": "FeatureCollection",
        "features": [
            {"type": "Feature", "properties": {"pozar": 1.0}, "geometry": None},
            {"type": "Feature", "properties": {"pozar": 4.0}, "geometry": None},
        ],
    }

    ensure_canonical_fire_scale(
        payload,
        fields=("pozar",),
        source_note="test fixture",
    )
    first_pass_scores = [feature["properties"]["pozar"] for feature in payload["features"]]

    ensure_canonical_fire_scale(
        payload,
        fields=("pozar",),
        source_note="test fixture",
    )
    second_pass_scores = [feature["properties"]["pozar"] for feature in payload["features"]]

    assert first_pass_scores == [4.0, 1.0]
    assert second_pass_scores == first_pass_scores
    assert payload[FIRE_SCALE_METADATA_KEY]["direction"] == "low_to_high"


def test_build_canonical_fire_overlay_updates_scores_and_labels():
    payload = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "pozar": "1",
                    "pozar_nazi": "ZELO VELIKA OGROZENOST",
                },
                "geometry": {"type": "Polygon", "coordinates": []},
            }
        ],
    }

    canonical = build_canonical_fire_overlay(payload, source_note="test fixture")

    properties = canonical["features"][0]["properties"]
    assert properties["pozar"] == "4"
    assert properties["pozar_nazi"] == CANONICAL_FIRE_LABELS[4]
    assert canonical[FIRE_SCALE_METADATA_KEY]["version"] == "low_to_high_v1"
