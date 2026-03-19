from __future__ import annotations

import math

import pytest

from rnpd_service import (
    cluster_sites,
    extract_coordinates_from_geometry,
    get_search_match_tier,
    read_bbox,
    score_search_match,
    should_cluster_results,
)


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
