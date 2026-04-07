from __future__ import annotations

import pytest

from AI.embedding_pipeline import (
    build_embedding_records,
    load_canonical_embedding_payload,
)


def test_build_embedding_records_uses_canonical_properties_for_text_and_metadata():
    payload = {
        "type": "FeatureCollection",
        "fire_scale": {
            "version": "low_to_high_v1",
            "direction": "low_to_high",
        },
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "EID": "1-00001",
                    "IME": "Testna enota",
                    "SINONIMI": ["Sinonim A", "Sinonim B"],
                    "OPIS": "Kratek opis",
                    "prevladujoci_material": "kamen",
                    "UE_UIME": "Koper",
                    "OBCINA": "Koper",
                    "STATUS": "registrirana dediščina",
                    "SPOMENIK": "spomenik",
                    "pozar_ocena_popravljena": 3.9,
                    "poplave_ocena_popravljena": 0.0,
                    "potres_ocena_popravljena": 1.0,
                    "plazovi_ocena_popravljena": 0.0,
                },
            }
        ],
    }

    records = build_embedding_records(payload)

    assert records == [
        {
            "eid": "1-00001",
            "text": (
                "ime: Testna enota | sinonimi: Sinonim A Sinonim B | opis: Kratek opis | "
                "material: kamen | okraj: Koper | obcina: Koper"
            ),
            "meta_data": {
                "EID": "1-00001",
                "OBCINA": "Koper",
                "STATUS": "registrirana dediščina",
                "SPOMENIK": "spomenik",
                "UE_UIME": "Koper",
                "prevladujoci_material": "kamen",
                "pozar_ocena_popravljena": 3.9,
                "poplave_ocena_popravljena": 0.0,
                "potres_ocena_popravljena": 1.0,
                "plazovi_ocena_popravljena": 0.0,
            },
        }
    ]


def test_load_canonical_embedding_payload_requires_fire_scale_metadata(tmp_path):
    path = tmp_path / "missing-fire-scale.geojson"
    path.write_text('{"type":"FeatureCollection","features":[]}', encoding="utf-8")

    with pytest.raises(ValueError, match="canonical fire-scale metadata"):
        load_canonical_embedding_payload(path)
