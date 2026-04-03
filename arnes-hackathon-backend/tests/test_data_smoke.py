from __future__ import annotations

from pathlib import Path

import pytest

import rnpd_service
from overlays import service as overlay_service


@pytest.mark.slow
def test_real_rnpd_dataset_loads_from_local_source():
    dataset = rnpd_service.get_dataset(refresh=True)

    assert dataset["source_count"] > 0
    assert len(dataset["sites"]) > 0
    assert dataset["loading_phase"] == "ready"
    assert dataset["last_error"] is None


@pytest.mark.slow
def test_real_overlay_dataset_loads_all_core_hazard_layers():
    dataset = overlay_service.get_overlay_dataset(refresh=True)

    assert len(dataset["points_by_kind"]["air"]) > 0
    assert len(dataset["areas_by_kind"]["fire"]) > 0
    assert len(dataset["areas_by_kind"]["flood"]) > 0
    assert len(dataset["areas_by_kind"]["landslide"]) > 0
    river_source = dataset["line_source_by_kind"]["river"]
    assert isinstance(river_source, dict)
    if Path(overlay_service.OVERLAY_RIVER_LINE_SHP).is_file():
        assert len(river_source["records"]) > 0
    else:
        assert river_source["records"] == []
