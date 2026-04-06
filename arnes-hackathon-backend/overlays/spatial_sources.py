from __future__ import annotations

import json
import math
import struct
from pathlib import Path
from typing import Any


def load_fire_geojson_areas(path: Path, *, score_min: float, score_max: float) -> list[dict[str, Any]]:
    if not path.is_file():
        raise RuntimeError(f"Overlay source file missing: {path}")

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise RuntimeError(f"Invalid GeoJSON payload in {path}: {exc}") from exc

    if not isinstance(payload, dict):
        return []

    features = payload.get("features")
    if not isinstance(features, list):
        return []

    areas: list[dict[str, Any]] = []
    for feature_index, feature in enumerate(features):
        if not isinstance(feature, dict):
            continue

        geometry = feature.get("geometry")
        properties = feature.get("properties")
        if not isinstance(geometry, dict) or not isinstance(properties, dict):
            continue

        raw_score = to_number(properties.get("pozar"))
        if raw_score is None:
            continue

        normalized = normalize_score(raw_score, score_min=score_min, score_max=score_max)
        level = normalized_to_level(normalized)
        rings = extract_geojson_outer_rings(geometry)

        for ring_index, ring in enumerate(rings):
            bounds = compute_ring_bounds(ring)
            if not bounds:
                continue
            areas.append(
                {
                    "id": f"fire:{feature_index}:{ring_index}",
                    "score": raw_score,
                    "normalized": normalized,
                    "level": level,
                    "bounds": bounds,
                    "ring": ring,
                }
            )

    return areas


def load_flood_shapefile_areas(
    *,
    shp_path: Path,
    level: float,
    score_min: float,
    score_max: float,
    id_prefix: str,
) -> list[dict[str, Any]]:
    records = read_polygon_shapefile_records(shp_path)
    normalized = normalize_score(level, score_min=score_min, score_max=score_max)
    display_level = normalized_to_level(normalized)

    areas: list[dict[str, Any]] = []
    for record_index, record in enumerate(records):
        for ring_index, ring_xy in enumerate(record["rings"]):
            ring = [maybe_transform_d96_to_wgs84(point[0], point[1]) for point in ring_xy]
            bounds = compute_ring_bounds(ring)
            if not bounds:
                continue
            areas.append(
                {
                    "id": f"{id_prefix}:{record_index}:{ring_index}",
                    "score": level,
                    "normalized": normalized,
                    "level": display_level,
                    "bounds": bounds,
                    "ring": ring,
                }
            )

    return areas


def load_landslide_shapefile_areas(
    *,
    shp_path: Path,
    dbf_path: Path,
    score_min: float,
    score_max: float,
    id_prefix: str,
) -> list[dict[str, Any]]:
    records = read_polygon_shapefile_records(shp_path)
    attributes = read_dbf_records(dbf_path)

    areas: list[dict[str, Any]] = []
    for record_index, record in enumerate(records):
        attrs = attributes[record_index] if record_index < len(attributes) else {}
        raw_score = to_number(attrs.get("DN"))
        if raw_score is None:
            continue
        normalized = normalize_score(raw_score, score_min=score_min, score_max=score_max)
        display_level = normalized_to_level(normalized)

        for ring_index, ring_xy in enumerate(record["rings"]):
            ring = [maybe_transform_d96_to_wgs84(point[0], point[1]) for point in ring_xy]
            bounds = compute_ring_bounds(ring)
            if not bounds:
                continue
            areas.append(
                {
                    "id": f"{id_prefix}:{record_index}:{ring_index}",
                    "score": raw_score,
                    "normalized": normalized,
                    "level": display_level,
                    "bounds": bounds,
                    "ring": ring,
                }
            )

    return areas


def select_visible_areas(
    *,
    areas: list[dict[str, Any]],
    bbox: list[float] | None,
    zoom: int,
    max_items: int,
    area_index: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not areas:
        return {"areas": [], "in_view_count": 0}

    if bbox:
        candidates = select_bbox_candidates(areas=areas, bbox=bbox, area_index=area_index)
    else:
        candidates = list(areas)

    if not candidates:
        return {"areas": [], "in_view_count": 0}

    in_view_count = len(candidates)

    if len(candidates) > max_items:
        candidates = spatially_sample_candidates(candidates, max_items=max_items, bbox=bbox)

    tolerance = get_zoom_tolerance_deg(zoom)
    cache_key = zoom
    visible: list[dict[str, Any]] = []

    for area in candidates:
        render_cache = area.setdefault("_render_cache", {})
        cached_area = render_cache.get(cache_key)
        if isinstance(cached_area, dict):
            visible.append(cached_area)
            continue

        simplified = simplify_ring(area["ring"], tolerance=tolerance)
        bounds = compute_ring_bounds(simplified)
        if not bounds:
            continue

        cached_area = {
            "id": area["id"],
            "score": round(float(area["score"]), 3),
            "normalized": round(float(area["normalized"]), 4),
            "level": int(area["level"]),
            "bounds": [round(value, 5) for value in bounds],
            "ring": [[round(point[0], 5), round(point[1], 5)] for point in simplified],
        }
        render_cache[cache_key] = cached_area
        visible.append(cached_area)

    return {"areas": visible, "in_view_count": in_view_count}


def select_bbox_candidates(
    *,
    areas: list[dict[str, Any]],
    bbox: list[float],
    area_index: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    if not area_index:
        return [area for area in areas if bounds_intersect(area["bounds"], bbox)]

    candidate_indexes = query_area_spatial_index(area_index, bbox)
    if candidate_indexes is None:
        return [area for area in areas if bounds_intersect(area["bounds"], bbox)]

    candidates: list[dict[str, Any]] = []
    for area_index_value in candidate_indexes:
        if area_index_value < 0 or area_index_value >= len(areas):
            continue
        area = areas[area_index_value]
        if bounds_intersect(area["bounds"], bbox):
            candidates.append(area)
    return candidates


def build_area_spatial_index(areas: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not areas:
        return None

    overall_bounds = compute_areas_bounds(areas)
    if not overall_bounds:
        return None

    min_lng, min_lat, max_lng, max_lat = overall_bounds
    span_lng = max(max_lng - min_lng, 1e-9)
    span_lat = max(max_lat - min_lat, 1e-9)

    grid_side = clamp_int(int(math.sqrt(max(1, len(areas) // 3))), 24, 120)
    buckets: dict[tuple[int, int], list[int]] = {}

    for area_index, area in enumerate(areas):
        bounds = area.get("bounds")
        if not isinstance(bounds, list) or len(bounds) != 4:
            continue
        area_min_lng = float(bounds[0])
        area_min_lat = float(bounds[1])
        area_max_lng = float(bounds[2])
        area_max_lat = float(bounds[3])

        start_x = clamp_int(int((area_min_lng - min_lng) / span_lng * grid_side), 0, grid_side - 1)
        end_x = clamp_int(int((area_max_lng - min_lng) / span_lng * grid_side), 0, grid_side - 1)
        start_y = clamp_int(int((area_min_lat - min_lat) / span_lat * grid_side), 0, grid_side - 1)
        end_y = clamp_int(int((area_max_lat - min_lat) / span_lat * grid_side), 0, grid_side - 1)

        for grid_x in range(start_x, end_x + 1):
            for grid_y in range(start_y, end_y + 1):
                bucket = buckets.setdefault((grid_x, grid_y), [])
                bucket.append(area_index)

    return {
        "bounds": overall_bounds,
        "grid_side": grid_side,
        "buckets": buckets,
    }


def query_area_spatial_index(area_index: dict[str, Any], bbox: list[float]) -> list[int] | None:
    bounds = area_index.get("bounds")
    buckets = area_index.get("buckets")
    grid_side = area_index.get("grid_side")
    if (
        not isinstance(bounds, list)
        or len(bounds) != 4
        or not isinstance(buckets, dict)
        or not isinstance(grid_side, int)
        or grid_side <= 0
    ):
        return None

    min_lng, min_lat, max_lng, max_lat = bounds
    span_lng = max(max_lng - min_lng, 1e-9)
    span_lat = max(max_lat - min_lat, 1e-9)

    bbox_min_lng, bbox_min_lat, bbox_max_lng, bbox_max_lat = bbox
    start_x = clamp_int(int((bbox_min_lng - min_lng) / span_lng * grid_side), 0, grid_side - 1)
    end_x = clamp_int(int((bbox_max_lng - min_lng) / span_lng * grid_side), 0, grid_side - 1)
    start_y = clamp_int(int((bbox_min_lat - min_lat) / span_lat * grid_side), 0, grid_side - 1)
    end_y = clamp_int(int((bbox_max_lat - min_lat) / span_lat * grid_side), 0, grid_side - 1)

    indexes: set[int] = set()
    for grid_x in range(start_x, end_x + 1):
        for grid_y in range(start_y, end_y + 1):
            bucket = buckets.get((grid_x, grid_y))
            if not isinstance(bucket, list):
                continue
            indexes.update(index for index in bucket if isinstance(index, int))

    return sorted(indexes)


def spatially_sample_candidates(
    candidates: list[dict[str, Any]],
    *,
    max_items: int,
    bbox: list[float] | None,
) -> list[dict[str, Any]]:
    if len(candidates) <= max_items:
        return candidates
    if max_items <= 0:
        return []

    view_bounds = bbox if bbox else compute_areas_bounds(candidates)
    if not view_bounds:
        ranked = sorted(candidates, key=area_importance_score, reverse=True)
        return ranked[:max_items]

    min_lng, min_lat, max_lng, max_lat = view_bounds
    span_lng = max(max_lng - min_lng, 1e-9)
    span_lat = max(max_lat - min_lat, 1e-9)

    grid_side = clamp_int(int(math.sqrt(max_items * 0.65)), 10, 280)
    buckets: dict[tuple[int, int], list[dict[str, Any]]] = {}

    for area in candidates:
        bounds = area.get("bounds")
        if not isinstance(bounds, list) or len(bounds) != 4:
            continue
        center_lng = (float(bounds[0]) + float(bounds[2])) / 2.0
        center_lat = (float(bounds[1]) + float(bounds[3])) / 2.0
        grid_x = clamp_int(int((center_lng - min_lng) / span_lng * grid_side), 0, grid_side - 1)
        grid_y = clamp_int(int((center_lat - min_lat) / span_lat * grid_side), 0, grid_side - 1)
        bucket = buckets.setdefault((grid_x, grid_y), [])
        bucket.append(area)

    if not buckets:
        ranked = sorted(candidates, key=area_importance_score, reverse=True)
        return ranked[:max_items]

    for bucket in buckets.values():
        bucket.sort(key=area_importance_score, reverse=True)

    ordered_keys = sorted(buckets.keys(), key=lambda key: (key[1], key[0] if key[1] % 2 == 0 else -key[0]))
    selected: list[dict[str, Any]] = []
    depth = 0

    while len(selected) < max_items:
        appended = 0
        for key in ordered_keys:
            bucket = buckets[key]
            if depth >= len(bucket):
                continue
            selected.append(bucket[depth])
            appended += 1
            if len(selected) >= max_items:
                break
        if appended == 0:
            break
        depth += 1

    if len(selected) < max_items:
        selected_ids = {str(item.get("id")) for item in selected}
        leftovers = [item for item in candidates if str(item.get("id")) not in selected_ids]
        leftovers.sort(key=area_importance_score, reverse=True)
        selected.extend(leftovers[: max_items - len(selected)])

    return selected[:max_items]


def compute_areas_bounds(areas: list[dict[str, Any]]) -> list[float] | None:
    if not areas:
        return None

    min_lng = math.inf
    min_lat = math.inf
    max_lng = -math.inf
    max_lat = -math.inf

    for area in areas:
        bounds = area.get("bounds")
        if not isinstance(bounds, list) or len(bounds) != 4:
            continue
        min_lng = min(min_lng, float(bounds[0]))
        min_lat = min(min_lat, float(bounds[1]))
        max_lng = max(max_lng, float(bounds[2]))
        max_lat = max(max_lat, float(bounds[3]))

    if not (math.isfinite(min_lng) and math.isfinite(min_lat) and math.isfinite(max_lng) and math.isfinite(max_lat)):
        return None
    return [min_lng, min_lat, max_lng, max_lat]


def area_importance_score(area: dict[str, Any]) -> float:
    bounds = area.get("bounds") or [0.0, 0.0, 0.0, 0.0]
    width = max(0.0, float(bounds[2]) - float(bounds[0]))
    height = max(0.0, float(bounds[3]) - float(bounds[1]))
    bbox_area = width * height
    normalized = float(area.get("normalized") or 0.0)
    return bbox_area * (0.7 + normalized * 0.8)


def get_zoom_tolerance_deg(zoom: int) -> float:
    if zoom <= 5:
        return 0.008
    if zoom <= 7:
        return 0.004
    if zoom <= 9:
        return 0.002
    if zoom <= 11:
        return 0.001
    if zoom <= 13:
        return 0.0005
    if zoom <= 15:
        return 0.00025
    return 0.00012


def extract_geojson_outer_rings(geometry: dict[str, Any]) -> list[list[tuple[float, float]]]:
    geometry_type = geometry.get("type")
    coordinates = geometry.get("coordinates")
    if not isinstance(coordinates, list):
        return []

    rings: list[list[tuple[float, float]]] = []
    if geometry_type == "Polygon":
        if coordinates:
            ring = to_ring(coordinates[0])
            if ring:
                rings.append(ring)
        return rings

    if geometry_type == "MultiPolygon":
        for polygon in coordinates:
            if not isinstance(polygon, list) or not polygon:
                continue
            ring = to_ring(polygon[0])
            if ring:
                rings.append(ring)
        return rings

    return []


def to_ring(value: Any) -> list[tuple[float, float]]:
    if not isinstance(value, list):
        return []

    ring: list[tuple[float, float]] = []
    for pair in value:
        if not isinstance(pair, list) or len(pair) < 2:
            continue
        lng = to_number(pair[0])
        lat = to_number(pair[1])
        if lng is None or lat is None:
            continue
        ring.append((lng, lat))

    return ensure_ring_closed(ring)


def ensure_ring_closed(ring: list[tuple[float, float]]) -> list[tuple[float, float]]:
    if len(ring) < 3:
        return []
    if ring[0] != ring[-1]:
        ring = [*ring, ring[0]]
    return ring


def compute_ring_bounds(ring: list[tuple[float, float]]) -> list[float] | None:
    if len(ring) < 4:
        return None

    lngs = [point[0] for point in ring]
    lats = [point[1] for point in ring]
    min_lng = min(lngs)
    max_lng = max(lngs)
    min_lat = min(lats)
    max_lat = max(lats)

    if not (-180 <= min_lng <= 180 and -180 <= max_lng <= 180 and -90 <= min_lat <= 90 and -90 <= max_lat <= 90):
        return None

    return [min_lng, min_lat, max_lng, max_lat]


def compute_path_bounds(path: list[tuple[float, float]]) -> list[float] | None:
    if len(path) < 2:
        return None

    lngs = [point[0] for point in path]
    lats = [point[1] for point in path]
    min_lng = min(lngs)
    max_lng = max(lngs)
    min_lat = min(lats)
    max_lat = max(lats)

    if not (-180 <= min_lng <= 180 and -180 <= max_lng <= 180 and -90 <= min_lat <= 90 and -90 <= max_lat <= 90):
        return None

    return [min_lng, min_lat, max_lng, max_lat]


def bounds_intersect(left: list[float], right: list[float]) -> bool:
    left_min_lng, left_min_lat, left_max_lng, left_max_lat = left
    right_min_lng, right_min_lat, right_max_lng, right_max_lat = right

    if left_max_lng < right_min_lng or right_max_lng < left_min_lng:
        return False
    if left_max_lat < right_min_lat or right_max_lat < left_min_lat:
        return False
    return True


def simplify_ring(ring: list[tuple[float, float]], *, tolerance: float) -> list[tuple[float, float]]:
    if len(ring) < 6 or tolerance <= 0:
        return ring

    closed = ring[0] == ring[-1]
    path = ring[:-1] if closed else ring
    simplified = rdp(path, tolerance)

    if closed and simplified and simplified[0] != simplified[-1]:
        simplified = [*simplified, simplified[0]]

    if len(simplified) < 4:
        return ring

    return simplified


def simplify_path(path: list[tuple[float, float]], *, tolerance: float) -> list[tuple[float, float]]:
    if len(path) < 3 or tolerance <= 0:
        return path

    simplified = rdp(path, tolerance)
    if len(simplified) < 2:
        return path

    return simplified


def rdp(points: list[tuple[float, float]], tolerance: float) -> list[tuple[float, float]]:
    if len(points) < 3:
        return points

    start = points[0]
    end = points[-1]
    max_distance = -1.0
    split_index = -1

    for index in range(1, len(points) - 1):
        distance = perpendicular_distance(points[index], start, end)
        if distance > max_distance:
            max_distance = distance
            split_index = index

    if max_distance <= tolerance or split_index < 0:
        return [start, end]

    left = rdp(points[: split_index + 1], tolerance)
    right = rdp(points[split_index:], tolerance)
    return left[:-1] + right


def perpendicular_distance(
    point: tuple[float, float],
    start: tuple[float, float],
    end: tuple[float, float],
) -> float:
    x, y = point
    x1, y1 = start
    x2, y2 = end

    dx = x2 - x1
    dy = y2 - y1
    if dx == 0 and dy == 0:
        return math.hypot(x - x1, y - y1)

    t = ((x - x1) * dx + (y - y1) * dy) / (dx * dx + dy * dy)
    t = min(1.0, max(0.0, t))
    proj_x = x1 + t * dx
    proj_y = y1 + t * dy
    return math.hypot(x - proj_x, y - proj_y)


def read_polygon_shapefile_records(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise RuntimeError(f"Shapefile missing: {path}")

    data = path.read_bytes()
    if len(data) < 100:
        return []

    shape_type = struct.unpack("<i", data[32:36])[0]
    if shape_type not in {5, 15, 25}:
        raise RuntimeError(f"Unsupported shape type {shape_type} in {path}")

    records: list[dict[str, Any]] = []
    offset = 100

    while offset + 8 <= len(data):
        # Record header uses big-endian numbers.
        _, content_length_words = struct.unpack(">2i", data[offset : offset + 8])
        offset += 8
        content_length = content_length_words * 2
        content = data[offset : offset + content_length]
        offset += content_length

        if len(content) < 44:
            continue

        record_shape_type = struct.unpack("<i", content[:4])[0]
        if record_shape_type == 0:
            continue
        if record_shape_type not in {5, 15, 25}:
            continue

        xmin, ymin, xmax, ymax = struct.unpack("<4d", content[4:36])
        num_parts, num_points = struct.unpack("<2i", content[36:44])

        parts_offset = 44
        points_offset = parts_offset + 4 * num_parts
        if len(content) < points_offset + 16 * num_points:
            continue

        part_indices = list(struct.unpack(f"<{num_parts}i", content[parts_offset:points_offset]))

        points_xy: list[tuple[float, float]] = []
        for point_index in range(num_points):
            point_offset = points_offset + point_index * 16
            x, y = struct.unpack("<2d", content[point_offset : point_offset + 16])
            points_xy.append((x, y))

        rings: list[list[tuple[float, float]]] = []
        for part_index, start in enumerate(part_indices):
            end = part_indices[part_index + 1] if part_index + 1 < len(part_indices) else len(points_xy)
            ring = ensure_ring_closed(points_xy[start:end])
            if ring:
                rings.append(ring)

        if not rings:
            continue

        records.append(
            {
                "bbox": [xmin, ymin, xmax, ymax],
                "rings": rings,
            }
        )

    return records


def read_polyline_shapefile_index(path: Path, *, id_prefix: str) -> list[dict[str, Any]]:
    if not path.is_file():
        raise RuntimeError(f"Shapefile missing: {path}")

    with path.open("rb") as handle:
        header = handle.read(100)
        if len(header) < 100:
            return []

        shape_type = struct.unpack("<i", header[32:36])[0]
        if shape_type not in {3, 13, 23}:
            raise RuntimeError(f"Unsupported shape type {shape_type} in {path}")

        records: list[dict[str, Any]] = []

        while True:
            record_header_offset = handle.tell()
            record_header = handle.read(8)
            if not record_header:
                break
            if len(record_header) < 8:
                break

            _, content_length_words = struct.unpack(">2i", record_header)
            content_length = content_length_words * 2
            content_offset = record_header_offset + 8
            content_head = handle.read(min(content_length, 44))

            if len(content_head) >= 44:
                record_shape_type = struct.unpack("<i", content_head[:4])[0]
                if record_shape_type in {3, 13, 23}:
                    xmin, ymin, xmax, ymax = struct.unpack("<4d", content_head[4:36])
                    corners = [
                        maybe_transform_d96_to_wgs84(xmin, ymin),
                        maybe_transform_d96_to_wgs84(xmax, ymax),
                    ]
                    lngs = [point[0] for point in corners]
                    lats = [point[1] for point in corners]
                    records.append(
                        {
                            "id": f"{id_prefix}:{len(records)}",
                            "bounds": [min(lngs), min(lats), max(lngs), max(lats)],
                            "contentOffset": content_offset,
                            "contentLength": content_length,
                        }
                    )

            remaining = content_length - len(content_head)
            if remaining > 0:
                handle.seek(remaining, 1)

    return records


def read_polyline_record_from_handle(
    handle: Any,
    *,
    content_offset: int,
    content_length: int,
) -> list[list[tuple[float, float]]]:
    handle.seek(content_offset)
    content = handle.read(content_length)
    if len(content) < 44:
        return []

    record_shape_type = struct.unpack("<i", content[:4])[0]
    if record_shape_type == 0:
        return []
    if record_shape_type not in {3, 13, 23}:
        return []

    num_parts, num_points = struct.unpack("<2i", content[36:44])
    parts_offset = 44
    points_offset = parts_offset + 4 * num_parts
    if len(content) < points_offset + 16 * num_points:
        return []

    part_indices = list(struct.unpack(f"<{num_parts}i", content[parts_offset:points_offset]))

    points_xy: list[tuple[float, float]] = []
    for point_index in range(num_points):
        point_offset = points_offset + point_index * 16
        x, y = struct.unpack("<2d", content[point_offset : point_offset + 16])
        points_xy.append(maybe_transform_d96_to_wgs84(x, y))

    paths: list[list[tuple[float, float]]] = []
    for part_index, start in enumerate(part_indices):
        end = part_indices[part_index + 1] if part_index + 1 < len(part_indices) else len(points_xy)
        path = points_xy[start:end]
        if len(path) >= 2:
            paths.append(path)

    return paths


def select_visible_lines(
    *,
    line_path: Path,
    records: list[dict[str, Any]],
    bbox: list[float] | None,
    zoom: int,
    max_items: int,
    line_index: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not records:
        return {"lines": [], "in_view_count": 0}

    if bbox:
        candidates = select_bbox_candidates(areas=records, bbox=bbox, area_index=line_index)
    else:
        candidates = list(records)

    if not candidates:
        return {"lines": [], "in_view_count": 0}

    in_view_count = len(candidates)
    if len(candidates) > max_items:
        candidates = spatially_sample_line_candidates(candidates, max_items=max_items, bbox=bbox)

    tolerance = get_zoom_tolerance_deg(zoom)
    cache_key = zoom
    visible: list[dict[str, Any]] = []

    with line_path.open("rb") as handle:
        for record in candidates:
            render_cache = record.setdefault("_render_cache", {})
            cached_line = render_cache.get(cache_key)
            if isinstance(cached_line, dict):
                visible.append(cached_line)
                continue

            content_offset = int(record.get("contentOffset") or 0)
            content_length = int(record.get("contentLength") or 0)
            if content_offset <= 0 or content_length <= 0:
                continue

            raw_paths = read_polyline_record_from_handle(
                handle,
                content_offset=content_offset,
                content_length=content_length,
            )
            simplified_paths: list[list[list[float]]] = []
            line_bounds: list[float] | None = None

            for raw_path in raw_paths:
                simplified = simplify_path(raw_path, tolerance=tolerance)
                bounds = compute_path_bounds(simplified)
                if not bounds:
                    continue
                if bbox and not bounds_intersect(bounds, bbox):
                    continue
                simplified_paths.append([[round(point[0], 5), round(point[1], 5)] for point in simplified])
                if line_bounds is None:
                    line_bounds = bounds
                else:
                    line_bounds = [
                        min(line_bounds[0], bounds[0]),
                        min(line_bounds[1], bounds[1]),
                        max(line_bounds[2], bounds[2]),
                        max(line_bounds[3], bounds[3]),
                    ]

            if not simplified_paths or line_bounds is None:
                continue

            cached_line = {
                "id": str(record.get("id") or f"line:{len(visible)}"),
                "bounds": [round(value, 5) for value in line_bounds],
                "paths": simplified_paths,
            }
            render_cache[cache_key] = cached_line
            visible.append(cached_line)

    return {"lines": visible, "in_view_count": in_view_count}


def spatially_sample_line_candidates(
    candidates: list[dict[str, Any]],
    *,
    max_items: int,
    bbox: list[float] | None,
) -> list[dict[str, Any]]:
    if len(candidates) <= max_items:
        return candidates
    if max_items <= 0:
        return []

    view_bounds = bbox if bbox else compute_areas_bounds(candidates)
    if not view_bounds:
        ranked = sorted(candidates, key=line_importance_score, reverse=True)
        return ranked[:max_items]

    min_lng, min_lat, max_lng, max_lat = view_bounds
    span_lng = max(max_lng - min_lng, 1e-9)
    span_lat = max(max_lat - min_lat, 1e-9)

    grid_side = clamp_int(int(math.sqrt(max_items * 0.8)), 10, 240)
    buckets: dict[tuple[int, int], list[dict[str, Any]]] = {}

    for candidate in candidates:
        bounds = candidate.get("bounds")
        if not isinstance(bounds, list) or len(bounds) != 4:
            continue
        center_lng = (float(bounds[0]) + float(bounds[2])) / 2.0
        center_lat = (float(bounds[1]) + float(bounds[3])) / 2.0
        grid_x = clamp_int(int((center_lng - min_lng) / span_lng * grid_side), 0, grid_side - 1)
        grid_y = clamp_int(int((center_lat - min_lat) / span_lat * grid_side), 0, grid_side - 1)
        buckets.setdefault((grid_x, grid_y), []).append(candidate)

    if not buckets:
        ranked = sorted(candidates, key=line_importance_score, reverse=True)
        return ranked[:max_items]

    for bucket in buckets.values():
        bucket.sort(key=line_importance_score, reverse=True)

    ordered_keys = sorted(buckets.keys(), key=lambda key: (key[1], key[0] if key[1] % 2 == 0 else -key[0]))
    selected: list[dict[str, Any]] = []
    depth = 0

    while len(selected) < max_items:
        appended = 0
        for key in ordered_keys:
            bucket = buckets[key]
            if depth >= len(bucket):
                continue
            selected.append(bucket[depth])
            appended += 1
            if len(selected) >= max_items:
                break
        if appended == 0:
            break
        depth += 1

    return selected[:max_items]


def line_importance_score(candidate: dict[str, Any]) -> float:
    bounds = candidate.get("bounds") or [0.0, 0.0, 0.0, 0.0]
    width = max(0.0, float(bounds[2]) - float(bounds[0]))
    height = max(0.0, float(bounds[3]) - float(bounds[1]))
    bbox_diagonal = math.hypot(width, height)
    content_length = float(candidate.get("contentLength") or 0.0)
    return bbox_diagonal * 1000.0 + content_length


def read_dbf_records(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise RuntimeError(f"DBF file missing: {path}")

    data = path.read_bytes()
    if len(data) < 32:
        return []

    record_count = struct.unpack("<I", data[4:8])[0]
    header_length = struct.unpack("<H", data[8:10])[0]
    record_length = struct.unpack("<H", data[10:12])[0]

    fields: list[dict[str, Any]] = []
    offset = 32
    while offset + 32 <= header_length:
        if data[offset] == 0x0D:
            break
        raw_name = data[offset : offset + 11].split(b"\x00", 1)[0]
        field_name = raw_name.decode("latin1", errors="ignore").strip()
        field_type = chr(data[offset + 11])
        field_length = int(data[offset + 16])
        decimal_count = int(data[offset + 17])
        fields.append(
            {
                "name": field_name,
                "type": field_type,
                "length": field_length,
                "decimals": decimal_count,
            }
        )
        offset += 32

    records: list[dict[str, Any]] = []
    start = header_length

    for index in range(record_count):
        row = data[start + index * record_length : start + (index + 1) * record_length]
        if len(row) < record_length:
            continue
        if row[:1] == b"*":
            continue

        cursor = 1
        parsed: dict[str, Any] = {}
        for field in fields:
            length = field["length"]
            raw = row[cursor : cursor + length]
            cursor += length

            raw_text = raw.decode("latin1", errors="ignore").strip()
            parsed[field["name"]] = parse_dbf_value(raw_text, field_type=field["type"], decimals=field["decimals"])

        records.append(parsed)

    return records


def parse_dbf_value(raw_value: str, *, field_type: str, decimals: int) -> Any:
    if not raw_value:
        return None

    if field_type in {"N", "F"}:
        try:
            numeric = float(raw_value)
        except ValueError:
            return None
        if decimals <= 0 and numeric.is_integer():
            return int(numeric)
        return numeric

    if field_type == "L":
        return raw_value.upper() in {"Y", "T", "1"}

    return raw_value


def maybe_transform_d96_to_wgs84(x: float, y: float) -> tuple[float, float]:
    if -180 <= x <= 180 and -90 <= y <= 90:
        return (x, y)
    lat, lng = d96_to_wgs84(y_coord=y, x_coord=x)
    return (lng, lat)


def d96_to_wgs84(*, y_coord: float, x_coord: float) -> tuple[float, float]:
    # EPSG:3794 (D96/TM) -> WGS84, Transverse Mercator inverse on GRS80 ellipsoid.
    a = 6378137.0
    inv_f = 298.257222101
    f = 1.0 / inv_f
    e2 = 2 * f - f * f
    e_prime_sq = e2 / (1 - e2)

    k0 = 0.9999
    lon0 = math.radians(15.0)
    false_easting = 500000.0
    false_northing = -5000000.0

    x = (x_coord - false_easting) / k0
    y = (y_coord - false_northing) / k0

    m = y
    mu = m / (a * (1 - e2 / 4 - 3 * e2 * e2 / 64 - 5 * e2**3 / 256))

    e1 = (1 - math.sqrt(1 - e2)) / (1 + math.sqrt(1 - e2))
    j1 = 3 * e1 / 2 - 27 * e1**3 / 32
    j2 = 21 * e1**2 / 16 - 55 * e1**4 / 32
    j3 = 151 * e1**3 / 96
    j4 = 1097 * e1**4 / 512

    fp = mu + j1 * math.sin(2 * mu) + j2 * math.sin(4 * mu) + j3 * math.sin(6 * mu) + j4 * math.sin(8 * mu)

    sin_fp = math.sin(fp)
    cos_fp = math.cos(fp)
    tan_fp = math.tan(fp)

    c1 = e_prime_sq * cos_fp * cos_fp
    t1 = tan_fp * tan_fp
    n1 = a / math.sqrt(1 - e2 * sin_fp * sin_fp)
    r1 = n1 * (1 - e2) / (1 - e2 * sin_fp * sin_fp)
    d = x / n1

    lat = fp - (n1 * tan_fp / r1) * (
        d * d / 2
        - (5 + 3 * t1 + 10 * c1 - 4 * c1 * c1 - 9 * e_prime_sq) * d**4 / 24
        + (61 + 90 * t1 + 298 * c1 + 45 * t1 * t1 - 252 * e_prime_sq - 3 * c1 * c1) * d**6 / 720
    )

    lon = lon0 + (
        d
        - (1 + 2 * t1 + c1) * d**3 / 6
        + (5 - 2 * c1 + 28 * t1 - 3 * c1 * c1 + 8 * e_prime_sq + 24 * t1 * t1) * d**5 / 120
    ) / cos_fp

    return (math.degrees(lat), math.degrees(lon))


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
    return int(math.floor(normalized * 4)) + 1


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
