from __future__ import annotations

import json
import math
import os
from collections import OrderedDict
from pathlib import Path
from threading import Lock
from time import time
from typing import Any

from .spatial_sources import (
    build_area_spatial_index,
    compute_areas_bounds,
    load_fire_geojson_areas,
    load_flood_shapefile_areas,
    load_landslide_shapefile_areas,
    read_polyline_shapefile_index,
    select_bbox_candidates,
    select_visible_areas,
    select_visible_lines,
)

try:
    from rasterio.enums import MergeAlg
    from rasterio.features import rasterize
    from rasterio.transform import from_origin

    HAS_RASTERIO = True
except Exception:  # pragma: no cover - exercised only when optional deps are missing
    MergeAlg = None
    rasterize = None
    from_origin = None
    HAS_RASTERIO = False

BASE_DIR = Path(__file__).resolve().parents[1]
OVERLAY_HAZARD_FILE = os.getenv("OVERLAY_HAZARD_FILE", str(BASE_DIR / "AI" / "Data" / "kd_z_nevarnost.geojson"))
OVERLAY_AIR_FILE = os.getenv("OVERLAY_AIR_FILE", str(BASE_DIR / "AI" / "Data_Processing" / "zrak_postaje.geojson"))
OVERLAY_FIRE_AREA_FILE = os.getenv(
    "OVERLAY_FIRE_AREA_FILE",
    str(BASE_DIR / "AI" / "Data" / "pozarna_ogrozenost_majhen_100m_canonical.geojson"),
)
OVERLAY_FLOOD_FREQUENT_SHP = os.getenv(
    "OVERLAY_FLOOD_FREQUENT_SHP",
    str(BASE_DIR / "AI" / "Data_Processing" / "DRSV_OPKP_POGOSTE_POPL" / "DRSV_OPKP_POGOSTE_POPL.shp"),
)
OVERLAY_FLOOD_RARE_SHP = os.getenv(
    "OVERLAY_FLOOD_RARE_SHP",
    str(BASE_DIR / "AI" / "Data_Processing" / "DRSV_OPKP_REDKE_POPL" / "DRSV_OPKP_REDKE_POPL.shp"),
)
OVERLAY_FLOOD_VERY_RARE_SHP = os.getenv(
    "OVERLAY_FLOOD_VERY_RARE_SHP",
    str(BASE_DIR / "AI" / "Data_Processing" / "DRSV_OPKP_ZR_POPL" / "DRSV_OPKP_ZR_POPL.shp"),
)
OVERLAY_LANDSLIDE_SHP = os.getenv(
    "OVERLAY_LANDSLIDE_SHP",
    str(BASE_DIR / "AI" / "Data_Processing" / "DRSV_Opk_Plazovi_skupna" / "plazovi2.shp"),
)
OVERLAY_LANDSLIDE_DBF = os.getenv(
    "OVERLAY_LANDSLIDE_DBF",
    str(BASE_DIR / "AI" / "Data_Processing" / "DRSV_Opk_Plazovi_skupna" / "plazovi2.dbf"),
)
OVERLAY_RIVER_LINE_SHP = os.getenv(
    "OVERLAY_RIVER_LINE_SHP",
    str(BASE_DIR / "AI" / "Data_Processing" / "DRSV_HIDRO5_LIN_PV" / "HIDRO5_LIN_PV_TIPTV1_2.shp"),
)
OVERLAY_CACHE_TTL_MS = int(os.getenv("OVERLAY_CACHE_TTL_MS", str(1000 * 60 * 30)))
# Absolute backend safety cap. Runtime target is still zoom-adaptive and usually lower.
OVERLAY_MAX_GRID_CELLS = max(256, int(os.getenv("OVERLAY_MAX_GRID_CELLS", "7500")))
OVERLAY_MAX_AREA_ITEMS = max(1200, int(os.getenv("OVERLAY_MAX_AREA_ITEMS", "32000")))
OVERLAY_MAX_AREA_GRID_CELLS = max(320, int(os.getenv("OVERLAY_MAX_AREA_GRID_CELLS", "4200")))
OVERLAY_MAX_LINE_ITEMS = max(800, int(os.getenv("OVERLAY_MAX_LINE_ITEMS", "5000")))
OVERLAY_AREA_GRID_MIN_ZOOM = max(3, int(os.getenv("OVERLAY_AREA_GRID_MIN_ZOOM", "3")))
OVERLAY_AREA_GRID_MAX_ZOOM = min(18, max(OVERLAY_AREA_GRID_MIN_ZOOM, int(os.getenv("OVERLAY_AREA_GRID_MAX_ZOOM", "11"))))
OVERLAY_AREA_GRID_KINDS = frozenset(
    kind.strip()
    for kind in os.getenv("OVERLAY_AREA_GRID_KINDS", "flood,landslide").split(",")
    if kind.strip()
)
OVERLAY_VIEW_CACHE_SIZE = max(32, int(os.getenv("OVERLAY_VIEW_CACHE_SIZE", "320")))

OVERLAY_DEFINITIONS: dict[str, dict[str, Any]] = {
    "fire": {
        "label": "Fire danger",
        "description": "Fire danger polygons from the official hazard map.",
        "mode": "area",
        "scoreMin": 1.0,
        "scoreMax": 4.0,
    },
    "flood": {
        "label": "Flood danger",
        "description": "Flood-danger polygons for frequent, rare, and very rare flood scenarios.",
        "mode": "area",
        "scoreMin": 1.0,
        "scoreMax": 3.0,
    },
    "landslide": {
        "label": "Landslide danger",
        "description": "Landslide susceptibility polygons from national landslide inventory data.",
        "mode": "area",
        "scoreMin": 0.0,
        "scoreMax": 4.0,
    },
    "air": {
        "label": "Air pollution",
        "description": "Aggregated air-pollution danger score from monitoring stations.",
        "mode": "point_grid",
        "source": "air",
        "scoreMin": 1.0,
        "scoreMax": 4.0,
    },
    "river": {
        "label": "Rivers",
        "description": "Official DRSV hydrography line network for watercourses and major channels.",
        "mode": "line",
        "scoreMin": 0.0,
        "scoreMax": 0.0,
    },
}

_SCALE_STEPS = [
    {"level": 1, "label": "Low", "normalized": 0.0},
    {"level": 2, "label": "Moderate", "normalized": 0.33},
    {"level": 3, "label": "High", "normalized": 0.66},
    {"level": 4, "label": "Extreme", "normalized": 1.0},
]

overlay_cache_lock = Lock()
overlay_cache: dict[str, Any] = {
    "loaded_at": 0.0,
    "loading": False,
    "last_error": None,
    "points_by_kind": {kind: [] for kind in OVERLAY_DEFINITIONS},
    "areas_by_kind": {kind: [] for kind in OVERLAY_DEFINITIONS},
    "area_index_by_kind": {kind: None for kind in OVERLAY_DEFINITIONS},
    "line_source_by_kind": {kind: None for kind in OVERLAY_DEFINITIONS},
    "line_index_by_kind": {kind: None for kind in OVERLAY_DEFINITIONS},
    "source_meta": {
        "hazard_file": OVERLAY_HAZARD_FILE,
        "air_file": OVERLAY_AIR_FILE,
        "fire_area_file": OVERLAY_FIRE_AREA_FILE,
        "flood_frequent_shp": OVERLAY_FLOOD_FREQUENT_SHP,
        "flood_rare_shp": OVERLAY_FLOOD_RARE_SHP,
        "flood_very_rare_shp": OVERLAY_FLOOD_VERY_RARE_SHP,
        "landslide_shp": OVERLAY_LANDSLIDE_SHP,
        "landslide_dbf": OVERLAY_LANDSLIDE_DBF,
        "river_line_shp": OVERLAY_RIVER_LINE_SHP,
    },
}
overlay_view_cache: OrderedDict[tuple[Any, ...], dict[str, Any]] = OrderedDict()


def list_overlay_catalog() -> list[dict[str, str]]:
    return [
        {
            "kind": kind,
            "label": definition["label"],
            "description": definition["description"],
        }
        for kind, definition in OVERLAY_DEFINITIONS.items()
    ]


def list_overlay_grid(
    *,
    kind: str,
    bbox: list[float] | None = None,
    zoom: float | None = None,
    refresh: bool = False,
) -> dict[str, Any]:
    definition = OVERLAY_DEFINITIONS.get(kind)
    if not definition:
        raise ValueError(f"Unknown overlay kind '{kind}'.")

    dataset = get_overlay_dataset(refresh=refresh)
    overlay_mode = str(definition.get("mode") or "point_grid")
    zoom_int = clamp_int(int(round(zoom)) if isinstance(zoom, (int, float)) else 8, 3, 18)
    use_area_grid = overlay_mode == "area" and should_use_area_grid(kind=kind, zoom=zoom_int)
    view_mode = f"{overlay_mode}_grid" if use_area_grid else overlay_mode
    view_cache_key = build_view_cache_key(
        kind=kind,
        mode=view_mode,
        bbox=bbox,
        zoom=zoom_int,
        generated_at=float(dataset.get("loaded_at") or 0.0),
    )
    cached_payload = read_cached_overlay_view(view_cache_key)
    if cached_payload:
        return cached_payload

    if overlay_mode == "area":
        areas = dataset["areas_by_kind"].get(kind, [])
        area_index_by_kind = dataset.get("area_index_by_kind")
        area_index = area_index_by_kind.get(kind) if isinstance(area_index_by_kind, dict) else None
        if use_area_grid:
            aggregated = aggregate_areas_to_grid(
                areas=areas,
                bbox=bbox,
                zoom=zoom_int,
                score_min=float(definition["scoreMin"]),
                score_max=float(definition["scoreMax"]),
                area_index=area_index,
            )
            visible_areas = []
            sample_count = aggregated["sample_count"]
            total_available = len(areas)
            cells = aggregated["cells"]
            cell_size_deg = aggregated["cell_size_deg"]
        else:
            selection = select_visible_areas(
                areas=areas,
                bbox=bbox,
                zoom=zoom_int,
                max_items=get_target_max_area_items(zoom_int),
                area_index=area_index,
            )
            visible_areas = selection["areas"]
            sample_count = int(selection["in_view_count"])
            total_available = len(areas)
            cells = []
            cell_size_deg = 0.0
        visible_lines = []
    elif overlay_mode == "point_grid":
        points = dataset["points_by_kind"].get(kind, [])
        aggregated = aggregate_points_to_grid(
            points=points,
            bbox=bbox,
            zoom=zoom,
            score_min=float(definition["scoreMin"]),
            score_max=float(definition["scoreMax"]),
        )
        visible_areas = []
        sample_count = aggregated["sample_count"]
        total_available = len(points)
        cells = aggregated["cells"]
        cell_size_deg = aggregated["cell_size_deg"]
        visible_lines = []
    else:
        line_source_by_kind = dataset.get("line_source_by_kind")
        line_index_by_kind = dataset.get("line_index_by_kind")
        line_source = line_source_by_kind.get(kind) if isinstance(line_source_by_kind, dict) else None
        line_index = line_index_by_kind.get(kind) if isinstance(line_index_by_kind, dict) else None
        records = line_source.get("records") if isinstance(line_source, dict) else []
        line_path_value = line_source.get("path") if isinstance(line_source, dict) else None
        if not isinstance(records, list) or not line_path_value:
            visible_lines = []
            sample_count = 0
            total_available = 0
        else:
            selection = select_visible_lines(
                line_path=Path(str(line_path_value)),
                records=records,
                bbox=bbox,
                zoom=zoom_int,
                max_items=get_target_max_line_items(zoom_int),
                line_index=line_index,
            )
            visible_lines = selection["lines"]
            sample_count = int(selection["in_view_count"])
            total_available = len(records)
        visible_areas = []
        cells = []
        cell_size_deg = 0.0

    if overlay_mode != "line":
        visible_lines = []

    payload = {
        "kind": kind,
        "label": definition["label"],
        "description": definition["description"],
        "scale": {
            "direction": "low-to-high",
            "leastLabel": "Least endangered",
            "mostLabel": "Most endangered",
            "steps": _SCALE_STEPS,
        },
        "areas": visible_areas,
        "cells": cells,
        "lines": visible_lines,
        "sampleCount": sample_count,
        "totalAvailableSamples": total_available,
        "gridCellSizeDeg": cell_size_deg,
        "generatedAt": dataset["loaded_at"],
    }
    write_cached_overlay_view(view_cache_key, payload)
    return payload


def get_overlay_dataset(*, refresh: bool = False) -> dict[str, Any]:
    with overlay_cache_lock:
        loaded_ms = float(overlay_cache.get("loaded_at") or 0.0)
        is_fresh = (time() * 1000 - loaded_ms) < OVERLAY_CACHE_TTL_MS
        if not refresh and is_fresh and has_any_overlay_data(
            overlay_cache.get("points_by_kind"),
            overlay_cache.get("areas_by_kind"),
            overlay_cache.get("line_source_by_kind"),
        ):
            return overlay_cache
        if overlay_cache.get("loading"):
            if has_any_overlay_data(
                overlay_cache.get("points_by_kind"),
                overlay_cache.get("areas_by_kind"),
                overlay_cache.get("line_source_by_kind"),
            ):
                return overlay_cache
            raise RuntimeError("Overlay dataset loading in progress")
        overlay_cache["loading"] = True
        overlay_cache["last_error"] = None

    try:
        points_by_kind = load_overlay_points()
        areas_by_kind = load_overlay_areas()
        line_source_by_kind = load_overlay_lines()
        loaded_at_ms = time() * 1000
        snapshot = {
            "loaded_at": loaded_at_ms,
            "loading": False,
            "last_error": None,
            "points_by_kind": points_by_kind,
            "areas_by_kind": areas_by_kind,
            "area_index_by_kind": {kind: build_area_spatial_index(areas) for kind, areas in areas_by_kind.items()},
            "line_source_by_kind": line_source_by_kind,
            "line_index_by_kind": {
                kind: (
                    build_area_spatial_index(source["records"])
                    if isinstance(source, dict) and isinstance(source.get("records"), list) and source["records"]
                    else None
                )
                for kind, source in line_source_by_kind.items()
            },
            "source_meta": {
                "hazard_file": OVERLAY_HAZARD_FILE,
                "air_file": OVERLAY_AIR_FILE,
                "fire_area_file": OVERLAY_FIRE_AREA_FILE,
                "flood_frequent_shp": OVERLAY_FLOOD_FREQUENT_SHP,
                "flood_rare_shp": OVERLAY_FLOOD_RARE_SHP,
                "flood_very_rare_shp": OVERLAY_FLOOD_VERY_RARE_SHP,
                "landslide_shp": OVERLAY_LANDSLIDE_SHP,
                "landslide_dbf": OVERLAY_LANDSLIDE_DBF,
                "river_line_shp": OVERLAY_RIVER_LINE_SHP,
            },
        }
        with overlay_cache_lock:
            overlay_cache.update(snapshot)
            overlay_view_cache.clear()
            return dict(overlay_cache)
    except Exception as exc:
        with overlay_cache_lock:
            overlay_cache["loading"] = False
            overlay_cache["last_error"] = str(exc)
            if has_any_overlay_data(
                overlay_cache.get("points_by_kind"),
                overlay_cache.get("areas_by_kind"),
                overlay_cache.get("line_source_by_kind"),
            ):
                return dict(overlay_cache)
        raise RuntimeError(f"Unable to load overlay data: {exc}") from exc


def has_any_overlay_points(points_by_kind: Any) -> bool:
    if not isinstance(points_by_kind, dict):
        return False
    for points in points_by_kind.values():
        if isinstance(points, list) and points:
            return True
    return False


def has_any_overlay_areas(areas_by_kind: Any) -> bool:
    if not isinstance(areas_by_kind, dict):
        return False
    for areas in areas_by_kind.values():
        if isinstance(areas, list) and areas:
            return True
    return False


def has_any_overlay_lines(line_source_by_kind: Any) -> bool:
    if not isinstance(line_source_by_kind, dict):
        return False
    for source in line_source_by_kind.values():
        records = source.get("records") if isinstance(source, dict) else None
        if isinstance(records, list) and records:
            return True
    return False


def has_any_overlay_data(points_by_kind: Any, areas_by_kind: Any, line_source_by_kind: Any) -> bool:
    return (
        has_any_overlay_points(points_by_kind)
        or has_any_overlay_areas(areas_by_kind)
        or has_any_overlay_lines(line_source_by_kind)
    )


def load_overlay_points() -> dict[str, list[tuple[float, float, float]]]:
    points_by_kind: dict[str, list[tuple[float, float, float]]] = {kind: [] for kind in OVERLAY_DEFINITIONS}

    air_features = load_geojson_features(Path(OVERLAY_AIR_FILE))
    for feature in air_features:
        coordinates = read_feature_point_coordinates(feature)
        if not coordinates:
            continue
        lng, lat = coordinates
        props = feature.get("properties") if isinstance(feature, dict) else None
        if not isinstance(props, dict):
            continue

        score = compute_air_pollution_score(props)
        if score is None:
            continue
        points_by_kind["air"].append((lng, lat, score))

    return points_by_kind


def load_overlay_areas() -> dict[str, list[dict[str, Any]]]:
    areas_by_kind: dict[str, list[dict[str, Any]]] = {kind: [] for kind in OVERLAY_DEFINITIONS}

    fire_definition = OVERLAY_DEFINITIONS["fire"]
    areas_by_kind["fire"] = load_fire_geojson_areas(
        Path(OVERLAY_FIRE_AREA_FILE),
        score_min=float(fire_definition["scoreMin"]),
        score_max=float(fire_definition["scoreMax"]),
    )

    flood_definition = OVERLAY_DEFINITIONS["flood"]
    flood_areas: list[dict[str, Any]] = []
    flood_areas.extend(
        load_flood_shapefile_areas(
            shp_path=Path(OVERLAY_FLOOD_FREQUENT_SHP),
            level=3.0,
            score_min=float(flood_definition["scoreMin"]),
            score_max=float(flood_definition["scoreMax"]),
            id_prefix="flood:frequent",
        )
    )
    flood_areas.extend(
        load_flood_shapefile_areas(
            shp_path=Path(OVERLAY_FLOOD_RARE_SHP),
            level=2.0,
            score_min=float(flood_definition["scoreMin"]),
            score_max=float(flood_definition["scoreMax"]),
            id_prefix="flood:rare",
        )
    )
    flood_areas.extend(
        load_flood_shapefile_areas(
            shp_path=Path(OVERLAY_FLOOD_VERY_RARE_SHP),
            level=1.0,
            score_min=float(flood_definition["scoreMin"]),
            score_max=float(flood_definition["scoreMax"]),
            id_prefix="flood:very-rare",
        )
    )
    areas_by_kind["flood"] = flood_areas

    landslide_definition = OVERLAY_DEFINITIONS["landslide"]
    areas_by_kind["landslide"] = load_landslide_shapefile_areas(
        shp_path=Path(OVERLAY_LANDSLIDE_SHP),
        dbf_path=Path(OVERLAY_LANDSLIDE_DBF),
        score_min=float(landslide_definition["scoreMin"]),
        score_max=float(landslide_definition["scoreMax"]),
        id_prefix="landslide",
    )

    for kind, areas in areas_by_kind.items():
        areas.sort(key=lambda area: (int(area["level"]), str(area["id"])))

    return areas_by_kind


def load_overlay_lines() -> dict[str, dict[str, Any] | None]:
    line_source_by_kind: dict[str, dict[str, Any] | None] = {kind: None for kind in OVERLAY_DEFINITIONS}

    river_path = Path(OVERLAY_RIVER_LINE_SHP)
    river_records: list[dict[str, Any]] = []
    if river_path.is_file():
        river_records = read_polyline_shapefile_index(
            river_path,
            id_prefix="river",
        )
        river_records.sort(key=lambda record: str(record["id"]))
    line_source_by_kind["river"] = {
        "path": OVERLAY_RIVER_LINE_SHP,
        "records": river_records,
    }

    return line_source_by_kind


def build_view_cache_key(
    *,
    kind: str,
    mode: str,
    bbox: list[float] | None,
    zoom: int,
    generated_at: float,
) -> tuple[Any, ...]:
    normalized_bbox: tuple[float, float, float, float] | None = None
    if isinstance(bbox, list) and len(bbox) == 4:
        normalized_bbox = tuple(round(float(value), 5) for value in bbox)
    return (kind, mode, normalized_bbox, zoom, int(generated_at))


def read_cached_overlay_view(cache_key: tuple[Any, ...]) -> dict[str, Any] | None:
    with overlay_cache_lock:
        cached = overlay_view_cache.get(cache_key)
        if not isinstance(cached, dict):
            return None
        overlay_view_cache.move_to_end(cache_key)
        return cached


def write_cached_overlay_view(cache_key: tuple[Any, ...], payload: dict[str, Any]) -> None:
    with overlay_cache_lock:
        overlay_view_cache[cache_key] = payload
        overlay_view_cache.move_to_end(cache_key)
        while len(overlay_view_cache) > OVERLAY_VIEW_CACHE_SIZE:
            overlay_view_cache.popitem(last=False)


def load_geojson_features(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise RuntimeError(f"Overlay source file missing: {path}")

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise RuntimeError(f"Invalid GeoJSON payload in {path}: {exc}") from exc

    if not isinstance(payload, dict):
        return []

    features = payload.get("features")
    if isinstance(features, list):
        return [feature for feature in features if isinstance(feature, dict)]

    return []


def read_feature_point_coordinates(feature: dict[str, Any]) -> tuple[float, float] | None:
    geometry = feature.get("geometry")
    if not isinstance(geometry, dict):
        return None
    if geometry.get("type") != "Point":
        return None

    coordinates = geometry.get("coordinates")
    if not isinstance(coordinates, list) or len(coordinates) < 2:
        return None

    lng = to_number(coordinates[0])
    lat = to_number(coordinates[1])
    if lng is None or lat is None:
        return None
    if not (-180 <= lng <= 180 and -90 <= lat <= 90):
        return None

    return (lng, lat)


def compute_air_pollution_score(properties: dict[str, Any]) -> float | None:
    subscores: list[float] = []

    pm10 = to_number(properties.get("pm10_dnevna"))
    if pm10 is not None:
        subscores.append(score_by_thresholds(pm10, low=20.0, mid=35.0, high=50.0))

    pm25 = to_number(properties.get("pm2.5_dnevna"))
    if pm25 is not None:
        subscores.append(score_by_thresholds(pm25, low=10.0, mid=20.0, high=35.0))

    no2 = to_number(properties.get("no2_max_urna"))
    if no2 is not None:
        subscores.append(score_by_thresholds(no2, low=40.0, mid=90.0, high=120.0))

    o3 = to_number(properties.get("o3_max_8urna"))
    if o3 is not None:
        subscores.append(score_by_thresholds(o3, low=100.0, mid=130.0, high=180.0))

    if not subscores:
        return None

    # Use the highest pollutant pressure per station to keep danger representation conservative.
    return max(subscores)


def score_by_thresholds(value: float, *, low: float, mid: float, high: float) -> float:
    if not math.isfinite(value):
        return 1.0

    if value <= low:
        return 1.0 + max(0.0, value) / max(low, 1.0)
    if value <= mid:
        return 2.0 + (value - low) / max(mid - low, 1.0)
    if value <= high:
        return 3.0 + (value - mid) / max(high - mid, 1.0)
    return 4.0


def aggregate_points_to_grid(
    *,
    points: list[tuple[float, float, float]],
    bbox: list[float] | None,
    zoom: float | None,
    score_min: float,
    score_max: float,
) -> dict[str, Any]:
    if not points:
        return {
            "cells": [],
            "sample_count": 0,
            "cell_size_deg": get_grid_cell_size_degrees(8),
        }

    active_bbox = bbox if bbox else infer_bbox(points)
    if not active_bbox:
        return {
            "cells": [],
            "sample_count": 0,
            "cell_size_deg": get_grid_cell_size_degrees(8),
        }

    zoom_int = clamp_int(int(round(zoom)) if isinstance(zoom, (int, float)) else 8, 3, 18)
    base_cell_size = get_grid_cell_size_degrees(zoom_int)
    max_target_cells = get_target_max_grid_cells(zoom_int)

    aggregated_cells: list[dict[str, Any]] = []
    sample_count = 0
    chosen_cell_size = base_cell_size

    for attempt in range(12):
        cell_size = base_cell_size * (2**attempt)
        cells, sample_count = build_grid_cells(
            points=points,
            bbox=active_bbox,
            cell_size_deg=cell_size,
            score_min=score_min,
            score_max=score_max,
        )
        aggregated_cells = cells
        chosen_cell_size = cell_size
        if len(cells) <= max_target_cells:
            break

    aggregated_cells.sort(key=lambda cell: (cell["level"], cell["id"]))

    return {
        "cells": aggregated_cells,
        "sample_count": sample_count,
        "cell_size_deg": round(chosen_cell_size, 6),
    }


def should_use_area_grid(*, kind: str, zoom: int) -> bool:
    if not HAS_RASTERIO:
        return False
    if kind not in OVERLAY_AREA_GRID_KINDS:
        return False
    return OVERLAY_AREA_GRID_MIN_ZOOM <= zoom <= OVERLAY_AREA_GRID_MAX_ZOOM


def aggregate_areas_to_grid(
    *,
    areas: list[dict[str, Any]],
    bbox: list[float] | None,
    zoom: int,
    score_min: float,
    score_max: float,
    area_index: dict[str, Any] | None,
) -> dict[str, Any]:
    if not areas or not HAS_RASTERIO:
        return {"cells": [], "sample_count": 0, "cell_size_deg": 0.0}

    active_bbox = bbox if bbox else infer_area_bounds(areas=areas, area_index=area_index)
    if not active_bbox:
        return {"cells": [], "sample_count": 0, "cell_size_deg": 0.0}

    candidates = (
        select_bbox_candidates(areas=areas, bbox=active_bbox, area_index=area_index)
        if bbox
        else areas
    )
    if not candidates:
        return {"cells": [], "sample_count": 0, "cell_size_deg": 0.0}

    base_cell_size = get_grid_cell_size_degrees(zoom)
    max_target_cells = get_target_max_area_grid_cells(zoom)
    chosen_cell_size = base_cell_size
    aggregated_cells: list[dict[str, Any]] = []

    for attempt in range(8):
        cell_size = base_cell_size * (2**attempt)
        cells = build_area_grid_cells_with_rasterio(
            areas=candidates,
            bbox=active_bbox,
            cell_size_deg=cell_size,
            score_min=score_min,
            score_max=score_max,
        )
        aggregated_cells = cells
        chosen_cell_size = cell_size
        if len(cells) <= max_target_cells:
            break

    aggregated_cells.sort(key=lambda cell: (cell["level"], cell["id"]))
    return {
        "cells": aggregated_cells,
        "sample_count": len(candidates),
        "cell_size_deg": round(chosen_cell_size, 6),
    }


def build_area_grid_cells_with_rasterio(
    *,
    areas: list[dict[str, Any]],
    bbox: list[float],
    cell_size_deg: float,
    score_min: float,
    score_max: float,
) -> list[dict[str, Any]]:
    if not HAS_RASTERIO or rasterize is None or from_origin is None or MergeAlg is None:
        return []

    min_lng, min_lat, max_lng, max_lat = bbox
    if max_lng <= min_lng or max_lat <= min_lat:
        return []

    width = max(1, int(math.ceil((max_lng - min_lng) / cell_size_deg)))
    height = max(1, int(math.ceil((max_lat - min_lat) / cell_size_deg)))
    transform = from_origin(min_lng, max_lat, cell_size_deg, cell_size_deg)

    weighted_shapes: list[tuple[dict[str, Any], float]] = []
    count_shapes: list[tuple[dict[str, Any], int]] = []

    for area in sorted(areas, key=lambda candidate: float(candidate.get("normalized") or 0.0)):
        rings = area.get("rings")
        if not isinstance(rings, list) or not rings:
            ring = area.get("ring")
            rings = [ring] if isinstance(ring, list) else []
        if not rings:
            continue
        outer_ring = rings[0]
        if not isinstance(outer_ring, list) or len(outer_ring) < 4:
            continue
        geometry = {"type": "Polygon", "coordinates": rings}
        normalized = min(1.0, max(0.0, float(area.get("normalized") or 0.0)))
        weighted_shapes.append((geometry, normalized))
        count_shapes.append((geometry, 1))

    if not weighted_shapes:
        return []

    normalized_raster = rasterize(
        shapes=weighted_shapes,
        out_shape=(height, width),
        transform=transform,
        fill=0.0,
        dtype="float32",
        all_touched=True,
    )
    count_raster = rasterize(
        shapes=count_shapes,
        out_shape=(height, width),
        transform=transform,
        fill=0,
        dtype="uint16",
        all_touched=True,
        merge_alg=MergeAlg.add,
    )

    cells: list[dict[str, Any]] = []
    for grid_y in range(height):
        for grid_x in range(width):
            normalized = float(normalized_raster[grid_y, grid_x])
            if normalized <= 0.0:
                continue

            normalized_clamped = min(1.0, max(0.0, normalized))
            score = score_min + normalized_clamped * (score_max - score_min)
            level = normalized_to_level(normalized_clamped)

            cell_min_lng = min_lng + grid_x * cell_size_deg
            cell_max_lng = min(max_lng, cell_min_lng + cell_size_deg)
            cell_max_lat = max_lat - grid_y * cell_size_deg
            cell_min_lat = max(min_lat, cell_max_lat - cell_size_deg)

            cells.append(
                {
                    "id": f"cell:{grid_x}:{grid_y}",
                    "score": round(score, 3),
                    "normalized": round(normalized_clamped, 4),
                    "level": level,
                    "sampleCount": int(count_raster[grid_y, grid_x]) or 1,
                    "bounds": [
                        round(cell_min_lng, 6),
                        round(cell_min_lat, 6),
                        round(cell_max_lng, 6),
                        round(cell_max_lat, 6),
                    ],
                }
            )

    return cells


def build_grid_cells(
    *,
    points: list[tuple[float, float, float]],
    bbox: list[float],
    cell_size_deg: float,
    score_min: float,
    score_max: float,
) -> tuple[list[dict[str, Any]], int]:
    min_lng, min_lat, max_lng, max_lat = bbox
    range_lng = max(0.0, max_lng - min_lng)
    range_lat = max(0.0, max_lat - min_lat)
    max_grid_x = max(0, int(math.floor(max(range_lng - 1e-12, 0.0) / cell_size_deg)))
    max_grid_y = max(0, int(math.floor(max(range_lat - 1e-12, 0.0) / cell_size_deg)))
    buckets: dict[tuple[int, int], dict[str, float]] = {}
    sample_count = 0

    for lng, lat, score in points:
        if lng < min_lng or lng > max_lng or lat < min_lat or lat > max_lat:
            continue
        sample_count += 1

        grid_x = clamp_int(int(math.floor((lng - min_lng) / cell_size_deg)), 0, max_grid_x)
        grid_y = clamp_int(int(math.floor((lat - min_lat) / cell_size_deg)), 0, max_grid_y)
        key = (grid_x, grid_y)
        bucket = buckets.setdefault(
            key,
            {
                "sum": 0.0,
                "max": -math.inf,
                "count": 0.0,
            },
        )
        bucket["sum"] += score
        bucket["max"] = max(bucket["max"], score)
        bucket["count"] += 1.0

    cells: list[dict[str, Any]] = []
    for (grid_x, grid_y), bucket in buckets.items():
        count = int(bucket["count"])
        if count <= 0:
            continue

        mean_score = bucket["sum"] / count
        peak_score = bucket["max"]
        combined_score = peak_score * 0.65 + mean_score * 0.35
        normalized = normalize_score(combined_score, score_min=score_min, score_max=score_max)
        level = normalized_to_level(normalized)

        cell_min_lng = min_lng + grid_x * cell_size_deg
        cell_min_lat = min_lat + grid_y * cell_size_deg
        cell_max_lng = min(max_lng, cell_min_lng + cell_size_deg)
        cell_max_lat = min(max_lat, cell_min_lat + cell_size_deg)

        cells.append(
            {
                "id": f"cell:{grid_x}:{grid_y}",
                "score": round(combined_score, 3),
                "normalized": round(normalized, 4),
                "level": level,
                "sampleCount": count,
                "bounds": [
                    round(cell_min_lng, 6),
                    round(cell_min_lat, 6),
                    round(cell_max_lng, 6),
                    round(cell_max_lat, 6),
                ],
            }
        )

    return cells, sample_count


def infer_bbox(points: list[tuple[float, float, float]]) -> list[float] | None:
    if not points:
        return None

    lngs = [point[0] for point in points]
    lats = [point[1] for point in points]
    min_lng = min(lngs)
    max_lng = max(lngs)
    min_lat = min(lats)
    max_lat = max(lats)

    # Pad slightly so edge points are included after rounding.
    padding = 0.001
    return [min_lng - padding, min_lat - padding, max_lng + padding, max_lat + padding]


def normalize_score(score: float, *, score_min: float, score_max: float) -> float:
    if score_max <= score_min:
        return 0.0
    ratio = (score - score_min) / (score_max - score_min)
    return min(1.0, max(0.0, ratio))


def normalized_to_level(normalized: float) -> int:
    if normalized >= 1.0:
        return 4
    if normalized <= 0.0:
        return 1
    return clamp_int(int(math.floor(normalized * 4)) + 1, 1, 4)


def get_grid_cell_size_degrees(zoom: int) -> float:
    # Smaller screen-space cells preserve richer structure while zooming out.
    if zoom <= 5:
        pixel_span = 14
    elif zoom <= 8:
        pixel_span = 12
    elif zoom <= 11:
        pixel_span = 10
    elif zoom <= 14:
        pixel_span = 8
    elif zoom <= 16:
        pixel_span = 7
    else:
        pixel_span = 6
    return (pixel_span * 360.0) / (256.0 * (2**zoom))


def get_target_max_grid_cells(zoom: int) -> int:
    # Increase detail budget as user zooms in, still bounded by backend cap.
    zoom_adaptive_target = 1200 + max(0, zoom - 6) * 700
    return clamp_int(zoom_adaptive_target, 600, OVERLAY_MAX_GRID_CELLS)


def get_target_max_area_grid_cells(zoom: int) -> int:
    # Cell overlays keep low-zoom area rendering detailed but bounded.
    zoom_adaptive_target = 900 + max(0, zoom - 6) * 520
    return clamp_int(zoom_adaptive_target, 600, OVERLAY_MAX_AREA_GRID_CELLS)


def get_target_max_area_items(zoom: int) -> int:
    # Keep area overlays rich while reducing payload and render pressure at low zoom.
    zoom_adaptive_target = 4000 + max(0, zoom - 6) * 1700
    return clamp_int(zoom_adaptive_target, 2200, OVERLAY_MAX_AREA_ITEMS)


def get_target_max_line_items(zoom: int) -> int:
    # River lines stay readable at overview zooms while allowing denser detail when zoomed in.
    zoom_adaptive_target = 1800 + max(0, zoom - 6) * 420
    return clamp_int(zoom_adaptive_target, 1200, OVERLAY_MAX_LINE_ITEMS)


def infer_area_bounds(*, areas: list[dict[str, Any]], area_index: dict[str, Any] | None) -> list[float] | None:
    if isinstance(area_index, dict):
        bounds = area_index.get("bounds")
        if isinstance(bounds, list) and len(bounds) == 4:
            return [float(bounds[0]), float(bounds[1]), float(bounds[2]), float(bounds[3])]
    computed = compute_areas_bounds(areas)
    if not computed:
        return None
    return [float(computed[0]), float(computed[1]), float(computed[2]), float(computed[3])]


def to_number(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        number = float(value)
    elif isinstance(value, str):
        try:
            number = float(value.strip().replace(",", "."))
        except ValueError:
            return None
    else:
        return None

    if math.isfinite(number):
        return number
    return None


def clamp_int(value: int, minimum: int, maximum: int) -> int:
    return min(maximum, max(minimum, value))
