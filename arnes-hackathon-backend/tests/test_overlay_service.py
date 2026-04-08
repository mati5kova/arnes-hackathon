from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from overlays import service
from overlays import spatial_sources


def test_score_by_thresholds_monotonic_growth():
    low = service.score_by_thresholds(5.0, low=20.0, mid=35.0, high=50.0)
    medium = service.score_by_thresholds(28.0, low=20.0, mid=35.0, high=50.0)
    high = service.score_by_thresholds(44.0, low=20.0, mid=35.0, high=50.0)
    extreme = service.score_by_thresholds(90.0, low=20.0, mid=35.0, high=50.0)

    assert 1.0 <= low < medium < high <= extreme
    assert extreme == 4.0


def test_compute_air_pollution_score_uses_worst_available_signal():
    score = service.compute_air_pollution_score(
        {
            "pm10_dnevna": 22,
            "pm2.5_dnevna": 18,
            "no2_max_urna": 35,
            "o3_max_8urna": 150,
        }
    )

    assert score is not None
    # O3 value should dominate and push station into high/extreme range.
    assert score > 3.0


def test_build_grid_cells_generates_valid_bounds_and_levels():
    points = [
        (14.2, 46.1, 1.2),
        (14.21, 46.11, 2.4),
        (14.23, 46.09, 3.5),
        (14.3, 46.2, 3.9),
    ]
    cells, sample_count = service.build_grid_cells(
        points=points,
        bbox=[14.0, 46.0, 14.4, 46.3],
        cell_size_deg=0.1,
        score_min=1.0,
        score_max=4.0,
    )

    assert sample_count == len(points)
    assert len(cells) >= 2
    for cell in cells:
        assert len(cell["bounds"]) == 4
        assert 1 <= int(cell["level"]) <= 4
        assert 0.0 <= float(cell["normalized"]) <= 1.0


def test_aggregate_points_to_grid_respects_max_cell_limit(monkeypatch):
    monkeypatch.setattr(service, "OVERLAY_MAX_GRID_CELLS", 45)

    points = []
    for x in range(80):
        for y in range(80):
            points.append((13.2 + x * 0.004, 45.3 + y * 0.004, 1.0 + ((x + y) % 4)))

    result = service.aggregate_points_to_grid(
        points=points,
        bbox=[13.2, 45.3, 13.7, 45.8],
        zoom=16,
        score_min=1.0,
        score_max=4.0,
    )

    assert result["sample_count"] == len(points)
    assert len(result["cells"]) <= 45


def test_get_target_max_area_items_grows_with_zoom_and_respects_cap(monkeypatch):
    monkeypatch.setattr(service, "OVERLAY_MAX_AREA_ITEMS", 12000)

    overview = service.get_target_max_area_items(5)
    closeup = service.get_target_max_area_items(13)

    assert overview < closeup
    assert closeup <= 12000


def test_list_overlay_grid_area_mode_uses_hazard_areas_not_points(monkeypatch):
    area_inside = {
        "id": "fire:in",
        "score": 3.0,
        "normalized": 0.8,
        "level": 4,
        "bounds": [14.0, 46.0, 14.1, 46.1],
        "ring": [(14.0, 46.0), (14.1, 46.0), (14.1, 46.1), (14.0, 46.1), (14.0, 46.0)],
    }
    area_outside = {
        "id": "fire:out",
        "score": 2.0,
        "normalized": 0.4,
        "level": 2,
        "bounds": [15.0, 47.0, 15.1, 47.1],
        "ring": [(15.0, 47.0), (15.1, 47.0), (15.1, 47.1), (15.0, 47.1), (15.0, 47.0)],
    }

    dataset = {
        "loaded_at": 1762230400123.0,
        "points_by_kind": {kind: [] for kind in service.OVERLAY_DEFINITIONS},
        "areas_by_kind": {
            "fire": [area_inside, area_outside],
            "flood": [],
            "air": [],
            "landslide": [],
        },
    }

    monkeypatch.setattr(service, "get_overlay_dataset", lambda refresh=False: dataset)
    monkeypatch.setattr(service, "get_target_max_area_items", lambda zoom: 1000)

    payload = service.list_overlay_grid(kind="fire", bbox=[13.9, 45.9, 14.2, 46.2], zoom=8)

    assert payload["cells"] == []
    assert payload["sampleCount"] == 1
    assert payload["totalAvailableSamples"] == 2
    assert payload["areas"][0]["id"] == "fire:in"


def test_list_overlay_grid_reuses_view_cache_for_identical_request(monkeypatch):
    dataset = {
        "loaded_at": 1762230400456.0,
        "points_by_kind": {kind: [] for kind in service.OVERLAY_DEFINITIONS},
        "areas_by_kind": {
            "fire": [
                {
                    "id": "fire:in",
                    "score": 3.0,
                    "normalized": 0.8,
                    "level": 4,
                    "bounds": [14.0, 46.0, 14.1, 46.1],
                    "ring": [(14.0, 46.0), (14.1, 46.0), (14.1, 46.1), (14.0, 46.1), (14.0, 46.0)],
                }
            ],
            "flood": [],
            "air": [],
            "landslide": [],
        },
        "area_index_by_kind": {kind: None for kind in service.OVERLAY_DEFINITIONS},
    }

    call_counter = {"count": 0}

    def fake_select_visible_areas(*, areas, bbox, zoom, max_items, area_index=None):
        call_counter["count"] += 1
        return {"areas": list(areas), "in_view_count": len(areas)}

    service.overlay_view_cache.clear()
    monkeypatch.setattr(service, "get_overlay_dataset", lambda refresh=False: dataset)
    monkeypatch.setattr(service, "select_visible_areas", fake_select_visible_areas)

    payload_a = service.list_overlay_grid(kind="fire", bbox=[13.9, 45.9, 14.2, 46.2], zoom=8)
    payload_b = service.list_overlay_grid(kind="fire", bbox=[13.9, 45.9, 14.2, 46.2], zoom=8)

    assert call_counter["count"] == 1
    assert payload_a is payload_b


def test_select_visible_areas_reuses_per_zoom_render_cache(monkeypatch):
    area = {
        "id": "area:1",
        "score": 2.0,
        "normalized": 0.5,
        "level": 2,
        "bounds": [14.0, 46.0, 14.2, 46.2],
        "ring": [(14.0, 46.0), (14.2, 46.0), (14.2, 46.2), (14.0, 46.2), (14.0, 46.0)],
    }
    simplify_call_count = {"count": 0}
    original_simplify_ring = spatial_sources.simplify_ring

    def wrapped_simplify_ring(ring, *, tolerance):
        simplify_call_count["count"] += 1
        return original_simplify_ring(ring, tolerance=tolerance)

    monkeypatch.setattr(spatial_sources, "simplify_ring", wrapped_simplify_ring)

    first = spatial_sources.select_visible_areas(
        areas=[area],
        bbox=[13.9, 45.9, 14.3, 46.3],
        zoom=9,
        max_items=100,
    )
    second = spatial_sources.select_visible_areas(
        areas=[area],
        bbox=[13.9, 45.9, 14.3, 46.3],
        zoom=9,
        max_items=100,
    )

    assert simplify_call_count["count"] == 1
    assert first["areas"][0] is second["areas"][0]


def test_get_target_max_area_grid_cells_grows_with_zoom_and_respects_cap(monkeypatch):
    monkeypatch.setattr(service, "OVERLAY_MAX_AREA_GRID_CELLS", 2400)

    overview = service.get_target_max_area_grid_cells(5)
    closeup = service.get_target_max_area_grid_cells(10)

    assert overview < closeup
    assert closeup <= 2400


def test_list_overlay_grid_area_mode_uses_grid_cells_when_enabled(monkeypatch):
    dataset = {
        "loaded_at": 1762230400456.0,
        "points_by_kind": {kind: [] for kind in service.OVERLAY_DEFINITIONS},
        "areas_by_kind": {
            "fire": [],
            "flood": [
                {
                    "id": "flood:1",
                    "score": 3.0,
                    "normalized": 1.0,
                    "level": 4,
                    "bounds": [14.0, 46.0, 14.2, 46.2],
                    "ring": [(14.0, 46.0), (14.2, 46.0), (14.2, 46.2), (14.0, 46.2), (14.0, 46.0)],
                }
            ],
            "air": [],
            "landslide": [],
        },
        "area_index_by_kind": {kind: None for kind in service.OVERLAY_DEFINITIONS},
    }

    monkeypatch.setattr(service, "get_overlay_dataset", lambda refresh=False: dataset)
    monkeypatch.setattr(service, "should_use_area_grid", lambda *, kind, zoom: True)
    monkeypatch.setattr(
        service,
        "aggregate_areas_to_grid",
        lambda **kwargs: {
            "cells": [
                {
                    "id": "cell:0:0",
                    "score": 2.8,
                    "normalized": 0.9,
                    "level": 4,
                    "sampleCount": 1,
                    "bounds": [14.0, 46.0, 14.1, 46.1],
                }
            ],
            "sample_count": 1,
            "cell_size_deg": 0.1,
        },
    )

    payload = service.list_overlay_grid(kind="flood", bbox=[13.9, 45.9, 14.3, 46.3], zoom=8)

    assert payload["areas"] == []
    assert payload["cells"][0]["id"] == "cell:0:0"
    assert payload["sampleCount"] == 1
    assert payload["gridCellSizeDeg"] == 0.1


def test_list_overlay_grid_line_mode_uses_visible_lines(monkeypatch):
    dataset = {
        "loaded_at": 1762230400456.0,
        "points_by_kind": {kind: [] for kind in service.OVERLAY_DEFINITIONS},
        "areas_by_kind": {kind: [] for kind in service.OVERLAY_DEFINITIONS},
        "area_index_by_kind": {kind: None for kind in service.OVERLAY_DEFINITIONS},
        "line_source_by_kind": {
            kind: (
                {
                    "path": "/tmp/rivers.shp",
                    "records": [
                        {
                            "id": "river:1",
                            "bounds": [14.0, 46.0, 14.2, 46.2],
                            "contentOffset": 108,
                            "contentLength": 64,
                        }
                    ],
                }
                if kind == "river"
                else None
            )
            for kind in service.OVERLAY_DEFINITIONS
        },
        "line_index_by_kind": {kind: None for kind in service.OVERLAY_DEFINITIONS},
    }

    monkeypatch.setattr(service, "get_overlay_dataset", lambda refresh=False: dataset)
    monkeypatch.setattr(
        service,
        "select_visible_lines",
        lambda **kwargs: {
            "lines": [
                {
                    "id": "river:1",
                    "bounds": [14.0, 46.0, 14.2, 46.2],
                    "paths": [[[14.0, 46.0], [14.2, 46.2]]],
                }
            ],
            "in_view_count": 1,
        },
    )

    payload = service.list_overlay_grid(kind="river", bbox=[13.9, 45.9, 14.3, 46.3], zoom=8)

    assert payload["areas"] == []
    assert payload["cells"] == []
    assert payload["lines"][0]["id"] == "river:1"
    assert payload["sampleCount"] == 1


@pytest.mark.skipif(not service.HAS_RASTERIO, reason="rasterio is required for area-grid rasterization tests")
def test_build_area_grid_cells_with_rasterio_returns_non_empty_cells():
    cells = service.build_area_grid_cells_with_rasterio(
        areas=[
            {
                "id": "area:1",
                "normalized": 0.75,
                "ring": [(14.0, 46.0), (14.1, 46.0), (14.1, 46.1), (14.0, 46.1), (14.0, 46.0)],
            }
        ],
        bbox=[13.95, 45.95, 14.15, 46.15],
        cell_size_deg=0.02,
        score_min=1.0,
        score_max=4.0,
    )

    assert cells
    assert all("bounds" in cell for cell in cells)
    assert all(cell["normalized"] > 0 for cell in cells)


def test_overlay_source_paths_exist():
    required_source_paths = {
        "OVERLAY_HAZARD_FILE": service.OVERLAY_HAZARD_FILE,
        "OVERLAY_AIR_FILE": service.OVERLAY_AIR_FILE,
        "OVERLAY_FIRE_AREA_FILE": service.OVERLAY_FIRE_AREA_FILE,
        "OVERLAY_FLOOD_FREQUENT_SHP": service.OVERLAY_FLOOD_FREQUENT_SHP,
        "OVERLAY_FLOOD_RARE_SHP": service.OVERLAY_FLOOD_RARE_SHP,
        "OVERLAY_FLOOD_VERY_RARE_SHP": service.OVERLAY_FLOOD_VERY_RARE_SHP,
        "OVERLAY_LANDSLIDE_SHP": service.OVERLAY_LANDSLIDE_SHP,
        "OVERLAY_LANDSLIDE_DBF": service.OVERLAY_LANDSLIDE_DBF,
    }

    missing = [
        f"{name} -> {path}"
        for name, path in required_source_paths.items()
        if not Path(path).is_file()
    ]
    assert not missing, (
        "Overlay source files are missing. If paths moved, update overlays/service.py defaults or "
        "set the OVERLAY_* env vars.\n"
        + "\n".join(missing)
    )


def test_load_overlay_lines_returns_empty_river_records_when_local_dataset_is_missing(monkeypatch):
    monkeypatch.setattr(service, "OVERLAY_RIVER_LINE_SHP", "/tmp/does-not-exist-river.shp")

    result = service.load_overlay_lines()

    assert result["river"] == {
        "path": "/tmp/does-not-exist-river.shp",
        "records": [],
    }


def _empty_overlay_cache() -> dict:
    return {
        "loaded_at": 0.0,
        "loading": False,
        "last_error": None,
        "points_by_kind": {kind: [] for kind in service.OVERLAY_DEFINITIONS},
        "areas_by_kind": {kind: [] for kind in service.OVERLAY_DEFINITIONS},
        "area_index_by_kind": {kind: None for kind in service.OVERLAY_DEFINITIONS},
        "line_source_by_kind": {kind: None for kind in service.OVERLAY_DEFINITIONS},
        "line_index_by_kind": {kind: None for kind in service.OVERLAY_DEFINITIONS},
        "source_meta": {
            "hazard_file": service.OVERLAY_HAZARD_FILE,
            "air_file": service.OVERLAY_AIR_FILE,
            "fire_area_file": service.OVERLAY_FIRE_AREA_FILE,
            "flood_frequent_shp": service.OVERLAY_FLOOD_FREQUENT_SHP,
            "flood_rare_shp": service.OVERLAY_FLOOD_RARE_SHP,
            "flood_very_rare_shp": service.OVERLAY_FLOOD_VERY_RARE_SHP,
            "landslide_shp": service.OVERLAY_LANDSLIDE_SHP,
            "landslide_dbf": service.OVERLAY_LANDSLIDE_DBF,
            "river_line_shp": service.OVERLAY_RIVER_LINE_SHP,
        },
    }


@pytest.fixture
def restore_overlay_cache_state():
    original_cache = deepcopy(service.overlay_cache)
    original_view_cache = deepcopy(service.overlay_view_cache)
    try:
        yield
    finally:
        service.overlay_cache.clear()
        service.overlay_cache.update(original_cache)
        service.overlay_view_cache.clear()
        service.overlay_view_cache.update(original_view_cache)


def test_get_overlay_dataset_returns_stale_cache_when_refresh_load_fails(monkeypatch, restore_overlay_cache_state):
    stale_cache = _empty_overlay_cache()
    stale_cache["loaded_at"] = 123.0
    stale_cache["points_by_kind"]["air"] = [(14.5, 46.1, 2.3)]
    service.overlay_cache.clear()
    service.overlay_cache.update(stale_cache)

    def failing_load_points():
        raise RuntimeError("simulated overlay loader failure")

    monkeypatch.setattr(service, "load_overlay_points", failing_load_points)

    result = service.get_overlay_dataset(refresh=True)

    assert result["points_by_kind"]["air"] == [(14.5, 46.1, 2.3)]
    assert result["loading"] is False
    assert "simulated overlay loader failure" in str(result["last_error"])


def test_get_overlay_dataset_raises_when_refresh_load_fails_without_stale_data(monkeypatch, restore_overlay_cache_state):
    service.overlay_cache.clear()
    service.overlay_cache.update(_empty_overlay_cache())

    def failing_load_points():
        raise RuntimeError("simulated overlay loader failure")

    monkeypatch.setattr(service, "load_overlay_points", failing_load_points)

    with pytest.raises(RuntimeError, match="Unable to load overlay data"):
        service.get_overlay_dataset(refresh=True)
