from __future__ import annotations

import json
import math
from copy import deepcopy
from pathlib import Path

import pytest

import rnpd_service
from rnpd_service import (
    cluster_sites,
    extract_records,
    extract_coordinates_from_geometry,
    fetch_source_json_and_signature,
    get_dataset,
    get_search_match_tier,
    normalize_record,
    read_bbox,
    score_search_match,
    should_cluster_results,
)


def _empty_dataset_cache() -> dict:
    return {
        "loaded_at": 0.0,
        "sites": [],
        "site_by_id": {},
        "source_count": 0,
        "loading": False,
        "loading_phase": "idle",
        "loading_progress": 0,
        "loading_started_at": 0.0,
        "last_load_duration_ms": None,
        "load_count": 0,
        "last_error": None,
    }


@pytest.fixture(autouse=True)
def reset_rnpd_runtime_cache():
    original_cache = deepcopy(rnpd_service.cache)
    rnpd_service.cache.clear()
    rnpd_service.cache.update(_empty_dataset_cache())
    try:
        yield
    finally:
        rnpd_service.cache.clear()
        rnpd_service.cache.update(original_cache)


def _site(*, lat: float, lng: float) -> dict:
    return {
        "id": f"{lat:.4f}-{lng:.4f}",
        "name": "Site",
        "lat": lat,
        "lng": lng,
        "type": None,
        "protectionStatus": None,
        "municipality": None,
        "description": None,
        "detailFields": [],
        "searchNameNormalized": "",
        "searchMunicipalityNormalized": "",
        "searchDetailNormalized": "",
        "searchTextNormalized": "",
    }


def test_read_bbox_valid_strict():
    assert read_bbox("14.37,46.12,14.50,46.17", strict=True) == [14.37, 46.12, 14.5, 46.17]


def test_read_bbox_invalid_format_raises_in_strict_mode():
    with pytest.raises(ValueError, match="Invalid bbox"):
        read_bbox("14.37,46.12,14.50", strict=True)


def test_read_bbox_invalid_range_returns_none_in_non_strict_mode():
    assert read_bbox("14.50,46.17,14.37,46.12") is None


def test_should_cluster_results_thresholds():
    bbox = [13.3, 45.3, 16.7, 46.9]
    assert should_cluster_results(search="", bbox=bbox, zoom=14.99) is True
    assert should_cluster_results(search="", bbox=bbox, zoom=15) is False
    assert should_cluster_results(search="ljubljana", bbox=bbox, zoom=8) is False


def test_cluster_sites_reduces_dense_marker_set():
    # Build a dense map window with >1000 points to exercise clustering branch.
    sites = [_site(lat=45.6 + (idx % 40) * 0.002, lng=13.6 + (idx // 40) * 0.002) for idx in range(1200)]
    clustered = cluster_sites(sites, bbox=[13.3, 45.3, 16.7, 46.9], zoom=8)

    assert len(clustered) < len(sites)
    assert any(item.get("isCluster") for item in clustered)


def test_extract_coordinates_from_wkt_polygon_returns_center():
    geometry = "POLYGON((14.0 46.0,14.2 46.0,14.2 46.2,14.0 46.2,14.0 46.0))"
    coordinates = extract_coordinates_from_geometry(geometry)
    assert coordinates is not None
    assert math.isclose(coordinates["lat"], 46.1, abs_tol=1e-6)
    assert math.isclose(coordinates["lng"], 14.1, abs_tol=1e-6)


def test_search_ranking_prefers_name_hits_over_detail_only_hits():
    normalized_search = "ljubljana"
    name_hit = {
        "searchNameNormalized": "ljubljana grad",
        "searchMunicipalityNormalized": "",
        "searchDetailNormalized": "",
        "searchTextNormalized": "ljubljana grad",
    }
    detail_hit = {
        "searchNameNormalized": "neznano mesto",
        "searchMunicipalityNormalized": "",
        "searchDetailNormalized": "lokacija ljubljana grad",
        "searchTextNormalized": "lokacija ljubljana grad",
    }

    assert get_search_match_tier(name_hit, normalized_search) == 0
    assert get_search_match_tier(detail_hit, normalized_search) == 2
    assert score_search_match(name_hit, normalized_search) > score_search_match(detail_hit, normalized_search)


def test_extract_records_supports_multiple_payload_shapes():
    assert extract_records([{"id": 1}]) == [{"id": 1}]
    assert extract_records({"features": [{"id": 2}]}) == [{"id": 2}]
    assert extract_records({"records": [{"id": 3}]}) == [{"id": 3}]
    assert extract_records({"result": {"records": [{"id": 4}]}}) == [{"id": 4}]


def test_normalize_record_caps_detail_fields_to_30():
    record = {
        "id": "EID-1",
        "name": "Test Site",
        "lat": 46.1234,
        "lng": 14.5678,
        **{f"extra_field_{index}": f"value-{index}" for index in range(60)},
    }

    normalized = normalize_record(record, 0)
    assert normalized is not None
    assert len(normalized["detailFields"]) == 30


def test_normalize_record_extracts_explicit_elevation():
    record = {
        "id": "EID-2",
        "name": "Elevated Site",
        "lat": 46.1234,
        "lng": 14.5678,
        "z": "412.58",
    }

    normalized = normalize_record(record, 0)
    assert normalized is not None
    assert normalized["elevationM"] == 412.58


def test_score_search_match_suppresses_short_detail_only_queries():
    site = {
        "searchNameNormalized": "",
        "searchMunicipalityNormalized": "",
        "searchDetailNormalized": "abc matching details only",
        "searchTextNormalized": "abc matching details only",
    }
    assert score_search_match(site, "abc") == 0


def test_fetch_source_json_prefers_first_local_candidate(monkeypatch, tmp_path: Path):
    preferred = tmp_path / "preferred.json"
    fallback = tmp_path / "fallback.json"
    preferred.write_text(json.dumps({"records": [{"source": "preferred"}]}), encoding="utf-8")
    fallback.write_text(json.dumps({"records": [{"source": "fallback"}]}), encoding="utf-8")

    monkeypatch.setattr(rnpd_service, "LOCAL_FALLBACK_CANDIDATES", [str(preferred), str(fallback)])
    monkeypatch.setattr(rnpd_service, "RNPD_ALLOW_REMOTE", False)

    payload, signature = fetch_source_json_and_signature()

    assert payload["records"][0]["source"] == "preferred"
    assert signature is not None
    assert signature["kind"] == "local"
    assert signature["path"] == str(preferred.resolve())


def test_fetch_source_json_falls_back_to_next_local_candidate(monkeypatch, tmp_path: Path):
    missing = tmp_path / "missing.json"
    fallback = tmp_path / "fallback.json"
    fallback.write_text(json.dumps({"records": [{"source": "fallback"}]}), encoding="utf-8")

    monkeypatch.setattr(rnpd_service, "LOCAL_FALLBACK_CANDIDATES", [str(missing), str(fallback)])
    monkeypatch.setattr(rnpd_service, "RNPD_ALLOW_REMOTE", False)

    payload, signature = fetch_source_json_and_signature()

    assert payload["records"][0]["source"] == "fallback"
    assert signature is not None
    assert signature["path"] == str(fallback.resolve())


def test_fetch_source_json_raises_when_local_missing_and_remote_disabled(monkeypatch, tmp_path: Path):
    missing_a = tmp_path / "missing-a.json"
    missing_b = tmp_path / "missing-b.json"
    monkeypatch.setattr(rnpd_service, "LOCAL_FALLBACK_CANDIDATES", [str(missing_a), str(missing_b)])
    monkeypatch.setattr(rnpd_service, "RNPD_ALLOW_REMOTE", False)

    with pytest.raises(RuntimeError, match="Unable to load RNPD source from local files"):
        fetch_source_json_and_signature()


def test_preprocessed_cache_signature_mismatch_triggers_source_reload(monkeypatch, tmp_path: Path):
    source_file = tmp_path / "rnpd-source.json"
    source_payload = [
        {
            "id": "EID-RELOAD",
            "name": "Reloaded site",
            "lat": 46.05,
            "lng": 14.5,
            "type": "site",
        }
    ]
    source_file.write_text(json.dumps(source_payload), encoding="utf-8")

    preprocessed_path = tmp_path / "rnpd.preprocessed.json"
    preprocessed_payload = {
        "schemaVersion": rnpd_service.PREPROCESSED_SCHEMA_VERSION,
        "generatedAtMs": 1,
        "sourceSignature": {
            "kind": "local",
            "path": str((tmp_path / "different-source.json").resolve()),
            "size": 10,
            "mtimeNs": 10,
        },
        "sourceCount": 1,
        "sites": [
            {
                "id": "FROM-CACHE",
                "name": "Stale cached site",
                "lat": 46.0,
                "lng": 14.0,
            }
        ],
    }
    preprocessed_path.write_text(json.dumps(preprocessed_payload), encoding="utf-8")

    fetch_calls = {"count": 0}

    def fake_fetch_source_json_and_signature():
        fetch_calls["count"] += 1
        stat = source_file.stat()
        return source_payload, {
            "kind": "local",
            "path": str(source_file.resolve()),
            "size": int(stat.st_size),
            "mtimeNs": int(stat.st_mtime_ns),
        }

    monkeypatch.setattr(rnpd_service, "LOCAL_FALLBACK_CANDIDATES", [str(source_file)])
    monkeypatch.setattr(rnpd_service, "RNPD_ALLOW_REMOTE", False)
    monkeypatch.setattr(rnpd_service, "RNPD_PREPROCESSED_CACHE_ENABLED", True)
    monkeypatch.setattr(rnpd_service, "RNPD_PREPROCESSED_CACHE_FILE", str(preprocessed_path))
    monkeypatch.setattr(rnpd_service, "fetch_source_json_and_signature", fake_fetch_source_json_and_signature)

    dataset = get_dataset(refresh=False)

    assert fetch_calls["count"] == 1
    assert "EID-RELOAD" in dataset["site_by_id"]
    assert "FROM-CACHE" not in dataset["site_by_id"]
