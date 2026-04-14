from __future__ import annotations

import json
import math
import os
import re
import unicodedata
from pathlib import Path
from threading import Lock
from time import time
from typing import Any
from urllib.request import Request, urlopen

from observability import record_dataset_load

RNPD_SOURCE_URL = os.getenv(
    "RNPD_SOURCE_URL",
    "https://podatki.gov.si/dataset/6b5bf6d9-d3bd-4231-95ac-3863b6d70c56/resource/1b0d4a0b-45d4-484b-a760-d0ed14426230/download/rnpd.json",
)
CACHE_TTL_MS = int(os.getenv("RNPD_CACHE_TTL_MS", str(1000 * 60 * 60 * 6)))
BASE_DIR = Path(__file__).resolve().parent
RNPD_ALLOW_REMOTE = os.getenv("RNPD_ALLOW_REMOTE", "0").strip().lower() in {"1", "true", "yes", "y"}
RNPD_PREPROCESSED_CACHE_ENABLED = os.getenv("RNPD_PREPROCESSED_CACHE_ENABLED", "1").strip().lower() in {
    "1",
    "true",
    "yes",
    "y",
}
RNPD_PREPROCESSED_CACHE_FILE = os.getenv("RNPD_PREPROCESSED_CACHE_FILE", str(BASE_DIR / "rnpd.preprocessed.json"))
PREPROCESSED_SCHEMA_VERSION = 4
LOCAL_FALLBACK_CANDIDATES = [
    os.getenv("RNPD_LOCAL_FILE"),
    str(BASE_DIR / "AI" / "Data" / "kd_z_nevarnost_enriched_verified.geojson"),
    str(BASE_DIR / "rnpd.json"),
    str(BASE_DIR.parent / "arnes-hackathon-frontend" / "src" / "data" / "rnpd.json"),
]
SEARCH_FIELD_WEIGHTS = {"name": 100, "municipality": 35, "details": 12}
MAX_RESPONSE_ITEMS = max(1, int(os.getenv("RNPD_MAX_RESPONSE_ITEMS", "5000")))

cache_lock = Lock()
cache: dict[str, Any] = {
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


def list_heritage_sites(
    *,
    search: str = "",
    limit: int | None = None,
    bbox: list[float] | None = None,
    zoom: float | None = None,
    refresh: bool = False,
) -> dict[str, Any]:
    dataset = get_dataset(refresh=refresh)
    normalized_search = normalize_text_for_search(search.strip())

    if normalized_search:
        ranked_matches: list[tuple[int, int, str, str, dict[str, Any]]] = []
        for site in dataset["sites"]:
            if not is_inside_bbox(site, bbox):
                continue
            score = score_search_match(site, normalized_search)
            if score <= 0:
                continue
            tier = get_search_match_tier(site, normalized_search)
            ranked_matches.append((tier, score, string_value(site.get("name")), string_value(site.get("id")), site))
        ranked_matches.sort(key=lambda item: (item[0], -item[1], item[2], item[3]))
        filtered = [item[4] for item in ranked_matches]
    else:
        filtered = [site for site in dataset["sites"] if is_inside_bbox(site, bbox)]

    clustered = cluster_sites(filtered, bbox, zoom) if should_cluster_results(search=search, bbox=bbox, zoom=zoom) else filtered
    effective_limit = MAX_RESPONSE_ITEMS
    if isinstance(limit, int) and limit > 0:
        effective_limit = min(limit, MAX_RESPONSE_ITEMS)
    items = clustered[:effective_limit]

    return {
        "items": [to_summary(site) for site in items],
        "total": len(filtered),
        "sourceCount": dataset["source_count"],
    }


def get_heritage_site_details(site_id: str, *, refresh: bool = False) -> dict[str, Any] | None:
    if not site_id or site_id.startswith("cluster:"):
        return None

    dataset = get_dataset(refresh=refresh)
    site = dataset["site_by_id"].get(site_id)
    if not site:
        return None
    return to_detail(site)


def read_corrected_hazard(record: dict[str, Any], *keys: str) -> float | None:
    value = pick_first(record, list(keys))
    if value is None:
        return None
    parsed = to_number(value)
    return round(float(parsed), 3) if parsed is not None else None


def get_dataset(*, refresh: bool = False) -> dict[str, Any]:
    loading_started_at_ms = time() * 1000
    with cache_lock:
        loaded_ms = cache["loaded_at"]
        is_fresh = (time() * 1000 - loaded_ms) < CACHE_TTL_MS
        if not refresh and is_fresh and cache["sites"]:
            return cache
        if cache["loading"]:
            if cache["sites"]:
                return cache
            raise RuntimeError("Dataset loading in progress")
        cache["loading"] = True
        cache["loading_phase"] = "initializing"
        cache["loading_progress"] = 5
        cache["loading_started_at"] = loading_started_at_ms
        cache["last_error"] = None

    try:
        preprocessed_dataset = load_preprocessed_dataset(refresh=refresh)
        if preprocessed_dataset:
            _update_loading_state(progress=85, phase="preprocessed_loaded")
            loaded_at_ms = time() * 1000
            load_duration_ms = max(0.0, loaded_at_ms - loading_started_at_ms)
            with cache_lock:
                previous_load_count = int(cache.get("load_count") or 0)

            dataset = {
                "loaded_at": loaded_at_ms,
                "sites": preprocessed_dataset["sites"],
                "site_by_id": {site["id"]: site for site in preprocessed_dataset["sites"]},
                "source_count": int(preprocessed_dataset.get("source_count") or len(preprocessed_dataset["sites"])),
                "loading": False,
                "loading_phase": "ready",
                "loading_progress": 100,
                "loading_started_at": 0.0,
                "last_load_duration_ms": load_duration_ms,
                "load_count": previous_load_count + 1,
                "last_error": None,
            }
            with cache_lock:
                cache.update(dataset)
                record_dataset_load(
                    duration_ms=load_duration_ms,
                    source_count=dataset["source_count"],
                    site_count=len(preprocessed_dataset["sites"]),
                )
                return cache

        payload, source_signature = fetch_source_json_and_signature()
        _update_loading_state(progress=35, phase="source_loaded")
        records = extract_records(payload)
        _update_loading_state(progress=55, phase="records_extracted")
        sites = [site for idx, record in enumerate(records) if (site := normalize_record(record, idx)) is not None]
        _update_loading_state(progress=90, phase="records_normalized")

        loaded_at_ms = time() * 1000
        load_duration_ms = max(0.0, loaded_at_ms - loading_started_at_ms)
        with cache_lock:
            previous_load_count = int(cache.get("load_count") or 0)

        dataset = {
            "loaded_at": loaded_at_ms,
            "sites": sites,
            "site_by_id": {site["id"]: site for site in sites},
            "source_count": len(records),
            "loading": False,
            "loading_phase": "ready",
            "loading_progress": 100,
            "loading_started_at": 0.0,
            "last_load_duration_ms": load_duration_ms,
            "load_count": previous_load_count + 1,
            "last_error": None,
        }
        with cache_lock:
            cache.update(dataset)
            record_dataset_load(duration_ms=load_duration_ms, source_count=len(records), site_count=len(sites))
            snapshot = dict(cache)

        persist_preprocessed_dataset(sites=sites, source_count=len(records), source_signature=source_signature)
        return snapshot
    except Exception as exc:
        with cache_lock:
            cache["loading"] = False
            cache["loading_phase"] = "error"
            cache["loading_progress"] = 0
            cache["loading_started_at"] = 0.0
            cache["last_error"] = str(exc)
            # If we already have usable data, prefer stale data over request failure.
            if cache["sites"]:
                return cache
        raise


def get_dataset_status() -> dict[str, Any]:
    with cache_lock:
        return {
            "ready": bool(cache["sites"]),
            "loading": bool(cache["loading"]),
            "loading_phase": str(cache.get("loading_phase") or "idle"),
            "loading_progress": int(cache.get("loading_progress") or 0),
            "loading_started_at": float(cache.get("loading_started_at") or 0.0),
            "source_count": int(cache["source_count"]),
            "loaded_at": float(cache["loaded_at"]),
            "last_load_duration_ms": cache.get("last_load_duration_ms"),
            "load_count": int(cache.get("load_count") or 0),
            "last_error": cache["last_error"],
        }


def _update_loading_state(*, progress: int, phase: str) -> None:
    with cache_lock:
        if not cache.get("loading"):
            return
        cache["loading_progress"] = max(0, min(100, int(progress)))
        cache["loading_phase"] = phase


def load_preprocessed_dataset(*, refresh: bool = False) -> dict[str, Any] | None:
    if refresh or not RNPD_PREPROCESSED_CACHE_ENABLED:
        return None

    cache_path = Path(RNPD_PREPROCESSED_CACHE_FILE)
    if not cache_path.exists():
        return None

    try:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
    except Exception:
        return None

    if not isinstance(payload, dict):
        return None
    if payload.get("schemaVersion") != PREPROCESSED_SCHEMA_VERSION:
        return None

    sites = payload.get("sites")
    if not isinstance(sites, list):
        return None

    source_signature = payload.get("sourceSignature")
    current_signature = get_current_source_signature()
    if source_signature and current_signature and not source_signatures_match(source_signature, current_signature):
        return None

    source_count = payload.get("sourceCount")
    if not isinstance(source_count, int) or source_count < 0:
        source_count = len(sites)

    return {
        "sites": sites,
        "source_count": source_count,
    }


def persist_preprocessed_dataset(*, sites: list[dict[str, Any]], source_count: int, source_signature: dict[str, Any] | None) -> None:
    if not RNPD_PREPROCESSED_CACHE_ENABLED:
        return

    cache_path = Path(RNPD_PREPROCESSED_CACHE_FILE)
    tmp_path = cache_path.with_suffix(f"{cache_path.suffix}.tmp")
    payload = {
        "schemaVersion": PREPROCESSED_SCHEMA_VERSION,
        "generatedAtMs": int(time() * 1000),
        "sourceSignature": source_signature,
        "sourceCount": source_count,
        "sites": sites,
    }

    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        tmp_path.replace(cache_path)
    except Exception:
        try:
            if tmp_path.exists():
                tmp_path.unlink()
        except Exception:
            pass


def get_current_source_signature() -> dict[str, Any] | None:
    for candidate in LOCAL_FALLBACK_CANDIDATES:
        if not candidate:
            continue
        source_path = Path(candidate)
        try:
            if not source_path.is_file():
                continue
            stat = source_path.stat()
            return {
                "kind": "local",
                "path": str(source_path.resolve()),
                "size": int(stat.st_size),
                "mtimeNs": int(stat.st_mtime_ns),
            }
        except Exception:
            continue

    if RNPD_ALLOW_REMOTE:
        return {
            "kind": "remote",
            "url": RNPD_SOURCE_URL,
        }

    return None


def source_signatures_match(left: Any, right: Any) -> bool:
    if not isinstance(left, dict) or not isinstance(right, dict):
        return False
    if left.get("kind") != right.get("kind"):
        return False

    if left.get("kind") == "local":
        return (
            str(left.get("path") or "") == str(right.get("path") or "")
            and int(left.get("size") or -1) == int(right.get("size") or -1)
            and int(left.get("mtimeNs") or -1) == int(right.get("mtimeNs") or -1)
        )
    if left.get("kind") == "remote":
        return str(left.get("url") or "") == str(right.get("url") or "")

    return False


def fetch_source_json_and_signature() -> tuple[Any, dict[str, Any] | None]:
    for candidate in LOCAL_FALLBACK_CANDIDATES:
        if not candidate:
            continue
        source_path = Path(candidate)
        try:
            payload = json.loads(source_path.read_text(encoding="utf-8"))
            stat = source_path.stat()
            signature = {
                "kind": "local",
                "path": str(source_path.resolve()),
                "size": int(stat.st_size),
                "mtimeNs": int(stat.st_mtime_ns),
            }
            return payload, signature
        except Exception:
            continue

    if RNPD_ALLOW_REMOTE:
        request = Request(
            RNPD_SOURCE_URL,
            headers={
                "accept": "application/json",
                "user-agent": "heritage-map-backend/1.0",
            },
        )
        try:
            with urlopen(request, timeout=30) as response:
                return json.loads(response.read().decode("utf-8")), {"kind": "remote", "url": RNPD_SOURCE_URL}
        except Exception as exc:
            message = str(exc) if isinstance(exc, Exception) else "Unknown fetch error"
            raise RuntimeError(
                "Unable to load RNPD source. Local files were not found and remote fetch failed. " + message
            ) from exc

    raise RuntimeError(
        "Unable to load RNPD source from local files. "
        "Set RNPD_LOCAL_FILE to a valid JSON dataset path, or set RNPD_ALLOW_REMOTE=1 to enable remote fetch."
    )


def fetch_source_json() -> Any:
    payload, _ = fetch_source_json_and_signature()
    return payload


def extract_records(payload: Any) -> list[Any]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ["features", "data", "items", "records", "result", "results"]:
            value = payload.get(key)
            if isinstance(value, list):
                return value
        result = payload.get("result")
        if isinstance(result, dict) and isinstance(result.get("records"), list):
            return result["records"]
    return []


def normalize_record(record: Any, index: int) -> dict[str, Any] | None:
    feature = record if isinstance(record, dict) and record.get("type") == "Feature" else None
    base_record = dict(feature.get("properties", {})) if feature else to_object(record)
    flattened = flatten_object(base_record)
    source_with_geometry = {**flattened, **flatten_geometry(record.get("geometry") if isinstance(record, dict) else None)}

    coordinates = extract_coordinates(record, source_with_geometry)
    if not coordinates:
        return None

    registry_id = pick_first(
        source_with_geometry,
        ["eid", "esd", "e_s_d", "evidencna_stevilka", "evidencnastevilka", "sifra", "oznaka", "id"],
    )
    name = string_value(
        pick_first(source_with_geometry, ["ime", "naziv", "ime_enote", "naziv_enote", "imeobjekta", "title", "name"])
    ) or f"Heritage site {index + 1}"
    site_type = string_value(pick_first(source_with_geometry, ["zvrst", "vrsta", "tip", "tip_dediscine", "vrsta_dediscine", "type"]))
    protection_status = string_value(
        pick_first(
            source_with_geometry,
            ["status", "status_enote", "rezim", "varstveni_rezim", "protection_status", "protectionstatus", "pravni_status"],
        )
    )
    municipality = string_value(pick_first(source_with_geometry, ["obcina", "municipality", "upravna_enota", "naselje", "lokacija", "kraj"]))
    description = string_value(pick_first(source_with_geometry, ["opis", "kratki_opis", "description", "summary", "povzetek"]))
    dating = string_value(pick_first(source_with_geometry, ["datacija", "dating"]))
    location_description = string_value(pick_first(source_with_geometry, ["lokacijaopis", "lokacija_opis", "location_description"]))
    photo_url = string_value(pick_first(source_with_geometry, ["photourl", "photo_url"]))
    elevation_m = to_number(
        string_value(
            pick_first(
                source_with_geometry,
                ["z", "elevation", "elevation_m", "visina", "visina_m", "height", "height_m"],
            )
        )
    )
    fire_hazard = read_corrected_hazard(source_with_geometry, "pozar_ocena_popravljena", "fire_danger_revised")
    flood_hazard = read_corrected_hazard(source_with_geometry, "poplave_ocena_popravljena", "flood_danger_revised")
    landslide_hazard = read_corrected_hazard(source_with_geometry, "plazovi_ocena_popravljena", "landslide_danger_revised")
    earthquake_hazard = read_corrected_hazard(source_with_geometry, "potres_ocena_popravljena", "earthquake_danger_revised")
    fire_hazard_original = read_corrected_hazard(source_with_geometry, "pozar", "fire_danger")
    flood_hazard_original = read_corrected_hazard(source_with_geometry, "poplave", "flood_danger")
    landslide_hazard_original = read_corrected_hazard(source_with_geometry, "plazovi", "landslide_danger")
    earthquake_hazard_original = read_corrected_hazard(source_with_geometry, "potres", "earthquake_danger")
    combined_hazard = read_corrected_hazard(source_with_geometry, "skupaj_nevarnost", "combined_danger_score")
    site_id = string_value(registry_id) or f"{name}-{coordinates['lat']:.6f}-{coordinates['lng']:.6f}".lower()

    used_key_candidates = [
        "eid",
        "esd",
        "e_s_d",
        "evidencna_stevilka",
        "evidencnastevilka",
        "sifra",
        "oznaka",
        "id",
        "ime",
        "naziv",
        "ime_enote",
        "naziv_enote",
        "imeobjekta",
        "title",
        "name",
        "zvrst",
        "vrsta",
        "tip",
        "tip_dediscine",
        "vrsta_dediscine",
        "type",
        "status",
        "status_enote",
        "rezim",
        "varstveni_rezim",
        "protection_status",
        "protectionstatus",
        "pravni_status",
        "obcina",
        "municipality",
        "upravna_enota",
        "naselje",
        "lokacija",
        "kraj",
        "opis",
        "kratki_opis",
        "description",
        "summary",
        "povzetek",
        "lat",
        "latitude",
        "lng",
        "lon",
        "long",
        "longitude",
        "z",
        "elevation",
        "elevation_m",
        "visina",
        "visina_m",
        "height",
        "height_m",
        "tip_najblizje_reke",
        "rezim_toka_najblizje_reke",
        "vrsta_najblizje_reke",
        "visina_najblizje_reke_m",
        "relativna_visina_nad_najblizjo_reko_m",
        "lokalni_naklon_stopinje",
        "lega_terena",
        "dvignjena_terasa",
        "pas_razdalje_do_reke",
        "srednje_dalec",
        "pas_razdalje_do_poplavnega_obmocja",
        "ime_najblizje_reke",
        "zanesljivost_konteksta_terena",
        "metoda_konteksta_terena",
        "uradna_ocena_poplav",
        "ocena_blizine_poplav",
        "pas_poplavne_nevarnosti",
        "utemeljitev_poplav",
        "razlicica_modela_poplav",
        "utemeljitev_popravka_nevarnosti",
        "status_preveritve",
        "opombe_preveritve",
        "viri",
        "x",
        "y",
        "x_wgs84",
        "y_wgs84",
        "wgs84_x",
        "wgs84_y",
        "gmaps_x",
        "gmaps_y",
        "geometry",
        "geometry_type",
        "geometry_coordinates",
        "geom",
        "wkt",
        "pozar",
        "poplave",
        "plazovi",
        "potres",
        "pozar_ocena_popravljena",
        "poplave_ocena_popravljena",
        "plazovi_ocena_popravljena",
        "potres_ocena_popravljena",
        "fire_danger",
        "flood_danger",
        "landslide_danger",
        "earthquake_danger",
        "fire_danger_revised",
        "flood_danger_revised",
        "landslide_danger_revised",
        "earthquake_danger_revised",
        "skupaj_nevarnost",
        "combined_danger_score",
    ]
    used_keys = {normalize_key(value) for value in used_key_candidates if normalize_key(value)}

    detail_fields: list[dict[str, str]] = []
    for key, value in source_with_geometry.items():
        normalized_key = normalize_key(key)
        if normalized_key in used_keys or is_empty_value(value):
            continue
        stringified = stringify_value(value)
        if not stringified:
            continue
        detail_fields.append({"label": humanize_key(key), "value": stringified})
        if len(detail_fields) >= 30:
            break

    search_parts = [
        site_id,
        string_value(registry_id),
        name,
        site_type,
        protection_status,
        municipality,
        description,
        *[f"{field['label']} {field['value']}" for field in detail_fields],
    ]

    name_normalized = normalize_text_for_search(name)
    municipality_normalized = normalize_text_for_search(municipality or "")
    detail_search_parts = [
        site_id,
        string_value(registry_id),
        site_type,
        protection_status,
        description,
        *[f"{field['label']} {field['value']}" for field in detail_fields],
    ]
    details_normalized = normalize_text_for_search(" ".join(part for part in detail_search_parts if part))
    search_text = " ".join(part for part in search_parts if part).lower()
    search_text_normalized = normalize_text_for_search(search_text)

    return {
        "id": site_id,
        "registryId": string_value(registry_id) or None,
        "name": name,
        "lat": coordinates["lat"],
        "lng": coordinates["lng"],
        "type": site_type or None,
        "protectionStatus": protection_status or None,
        "municipality": municipality or None,
        "description": description or None,
        "dating": dating or None,
        "locationDescription": location_description or None,
        "photoUrl": photo_url or None,
        "elevationM": round(float(elevation_m), 2) if elevation_m is not None else None,
        "fireHazard": fire_hazard,
        "floodHazard": flood_hazard,
        "landslideHazard": landslide_hazard,
        "earthquakeHazard": earthquake_hazard,
        "fireHazardOriginal": fire_hazard_original,
        "floodHazardOriginal": flood_hazard_original,
        "landslideHazardOriginal": landslide_hazard_original,
        "earthquakeHazardOriginal": earthquake_hazard_original,
        "combinedHazard": combined_hazard,
        "detailFields": detail_fields,
        "searchNameNormalized": name_normalized,
        "searchMunicipalityNormalized": municipality_normalized,
        "searchDetailNormalized": details_normalized,
        "searchText": search_text,
        "searchTextNormalized": search_text_normalized,
        "sourceUrl": RNPD_SOURCE_URL,
    }


def to_summary(site: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": site.get("id"),
        "registryId": site.get("registryId"),
        "name": site.get("name"),
        "lat": site.get("lat"),
        "lng": site.get("lng"),
        "type": site.get("type"),
        "protectionStatus": site.get("protectionStatus"),
        "municipality": site.get("municipality"),
        "isCluster": site.get("isCluster"),
        "clusterCount": site.get("clusterCount"),
    }


def to_detail(site: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": site.get("id"),
        "registryId": site.get("registryId"),
        "name": site.get("name"),
        "lat": site.get("lat"),
        "lng": site.get("lng"),
        "type": site.get("type"),
        "protectionStatus": site.get("protectionStatus"),
        "municipality": site.get("municipality"),
        "isCluster": site.get("isCluster"),
        "description": site.get("description"),
        "dating": site.get("dating"),
        "locationDescription": site.get("locationDescription"),
        "photoUrl": site.get("photoUrl"),
        "fireHazard": site.get("fireHazard"),
        "floodHazard": site.get("floodHazard"),
        "landslideHazard": site.get("landslideHazard"),
        "earthquakeHazard": site.get("earthquakeHazard"),
        "fireHazardOriginal": site.get("fireHazardOriginal"),
        "floodHazardOriginal": site.get("floodHazardOriginal"),
        "landslideHazardOriginal": site.get("landslideHazardOriginal"),
        "earthquakeHazardOriginal": site.get("earthquakeHazardOriginal"),
    }


def should_cluster_results(*, search: str, bbox: list[float] | None, zoom: float | None) -> bool:
    if not bbox:
        return False
    if search.strip():
        return False
    if not isinstance(zoom, (int, float)):
        return True
    return float(zoom) < 15


def cluster_sites(sites: list[dict[str, Any]], bbox: list[float] | None, zoom: float | None) -> list[dict[str, Any]]:
    if not bbox or len(sites) < 1000:
        return sites

    normalized_zoom = clamp(int(round(float(zoom) if isinstance(zoom, (int, float)) else 8.0)), 3, 18)
    base_cell_size = get_cell_size_degrees(normalized_zoom)
    max_clusters = 1500
    clustered = sites

    for attempt in range(8):
        cell_multiplier = 2**attempt
        cell_lng = base_cell_size * cell_multiplier
        cell_lat = base_cell_size * cell_multiplier
        clustered = cluster_by_grid(sites, cell_lng, cell_lat, normalized_zoom, attempt)
        if len(clustered) <= max_clusters:
            break

    return clustered


def cluster_by_grid(
    sites: list[dict[str, Any]],
    cell_lng: float,
    cell_lat: float,
    zoom: int,
    salt: int,
) -> list[dict[str, Any]]:
    buckets: dict[str, list[dict[str, Any]]] = {}

    for site in sites:
        grid_x = math.floor(site["lng"] / cell_lng)
        grid_y = math.floor(site["lat"] / cell_lat)
        key = f"{grid_x}:{grid_y}"
        buckets.setdefault(key, []).append(site)

    result: list[dict[str, Any]] = []
    for key, bucket in buckets.items():
        if len(bucket) == 1:
            result.append(bucket[0])
            continue

        avg_lat = sum(site["lat"] for site in bucket) / len(bucket)
        avg_lng = sum(site["lng"] for site in bucket) / len(bucket)
        result.append(
            {
                "id": f"cluster:{zoom}:{salt}:{key}",
                "name": f"{len(bucket)} heritage sites",
                "lat": avg_lat,
                "lng": avg_lng,
                "type": "Cluster",
                "description": "Zoom in to view individual heritage sites.",
                "isCluster": True,
                "clusterCount": len(bucket),
                "sourceUrl": RNPD_SOURCE_URL,
                "detailFields": [],
                "searchText": "",
            }
        )
    return result


def get_cell_size_degrees(zoom: int) -> float:
    if zoom <= 7:
        cluster_radius_px = 80
    elif zoom <= 10:
        cluster_radius_px = 64
    elif zoom <= 13:
        cluster_radius_px = 48
    else:
        cluster_radius_px = 32
    return (cluster_radius_px * 360) / (256 * (2**zoom))


def clamp(value: int, minimum: int, maximum: int) -> int:
    return min(maximum, max(minimum, value))


def matches_search(site: dict[str, Any], search: str) -> bool:
    term = normalize_text_for_search(search.strip())
    if not term:
        return True
    return score_search_match(site, term) > 0


def score_search_match(site: dict[str, Any], normalized_search: str) -> int:
    if not normalized_search:
        return 0

    terms = [term for term in normalized_search.split(" ") if term]
    if not terms:
        return 0

    name_text = site.get("searchNameNormalized", "") or ""
    municipality_text = site.get("searchMunicipalityNormalized", "") or ""
    details_text = site.get("searchDetailNormalized", "") or ""
    full_text = site.get("searchTextNormalized", "") or ""

    name_score = score_search_field(name_text, normalized_search, terms)
    municipality_score = score_search_field(municipality_text, normalized_search, terms)
    details_score = score_search_field(details_text, normalized_search, terms)

    # For very short queries, suppress noisy detail-only matches.
    if len(normalized_search) <= 3 and name_score == 0 and municipality_score == 0:
        return 0

    if name_score == 0 and municipality_score == 0 and details_score == 0:
        return 0

    score = (
        name_score * SEARCH_FIELD_WEIGHTS["name"]
        + municipality_score * SEARCH_FIELD_WEIGHTS["municipality"]
        + details_score * SEARCH_FIELD_WEIGHTS["details"]
    )

    # Boost exact normalized phrase matches over looser field matches.
    if normalized_search in full_text:
        score += 120
    if normalized_search in name_text:
        score += 220
    if name_text.startswith(normalized_search):
        score += 180

    return score


def score_search_field(text: str, normalized_search: str, terms: list[str]) -> int:
    if not text:
        return 0

    score = 0
    matched_terms = 0

    if normalized_search in text:
        score += 70
    if text.startswith(normalized_search):
        score += 35

    for term in terms:
        if term in text:
            score += 20
            matched_terms += 1

    if matched_terms == len(terms):
        score += 24
    elif matched_terms == 0 and normalized_search not in text:
        return 0

    return score


def get_search_match_tier(site: dict[str, Any], normalized_search: str) -> int:
    terms = [term for term in normalized_search.split(" ") if term]
    name_text = site.get("searchNameNormalized", "") or ""
    municipality_text = site.get("searchMunicipalityNormalized", "") or ""
    details_text = site.get("searchDetailNormalized", "") or ""

    if field_has_search_hit(name_text, normalized_search, terms):
        return 0
    if field_has_search_hit(municipality_text, normalized_search, terms):
        return 1
    if field_has_search_hit(details_text, normalized_search, terms):
        return 2
    return 3


def field_has_search_hit(text: str, normalized_search: str, terms: list[str]) -> bool:
    if not text:
        return False
    if normalized_search in text:
        return True
    for term in terms:
        if term and term in text:
            return True
    return False


def is_inside_bbox(site: dict[str, Any], bbox: list[float] | None) -> bool:
    if not bbox:
        return True
    min_lng, min_lat, max_lng, max_lat = bbox
    return min_lng <= site["lng"] <= max_lng and min_lat <= site["lat"] <= max_lat


def read_bbox(raw_bbox: str | None, *, strict: bool = False) -> list[float] | None:
    if not raw_bbox:
        return None

    parts = [part.strip() for part in raw_bbox.split(",")]
    if len(parts) != 4:
        if strict:
            raise ValueError("Invalid bbox. Expected format: minLng,minLat,maxLng,maxLat")
        return None

    numbers = [to_number(value) for value in parts]
    if any(value is None for value in numbers):
        if strict:
            raise ValueError("Invalid bbox. Coordinates must be finite numbers.")
        return None

    min_lng = float(numbers[0])  # numbers are guaranteed non-None by the guard above.
    min_lat = float(numbers[1])
    max_lng = float(numbers[2])
    max_lat = float(numbers[3])

    if not (-180 <= min_lng <= 180 and -180 <= max_lng <= 180 and -90 <= min_lat <= 90 and -90 <= max_lat <= 90):
        if strict:
            raise ValueError("Invalid bbox. Longitude must be within [-180, 180] and latitude within [-90, 90].")
        return None

    if min_lng >= max_lng or min_lat >= max_lat:
        if strict:
            raise ValueError("Invalid bbox. Ensure minLng < maxLng and minLat < maxLat.")
        return None

    return [min_lng, min_lat, max_lng, max_lat]


def read_refresh_flag(refresh: str | None) -> bool:
    if refresh is None:
        return False
    normalized = refresh.strip().lower()
    return normalized in {"1", "true", "yes", "y"}


def extract_coordinates(record: Any, flattened: dict[str, Any]) -> dict[str, float] | None:
    direct_lat = parse_coordinate(pick_first(flattened, ["lat", "latitude", "y_wgs84", "wgs84_y", "y", "gmaps_y"]))
    direct_lng = parse_coordinate(
        pick_first(flattened, ["lng", "lon", "long", "longitude", "x_wgs84", "wgs84_x", "x", "gmaps_x"])
    )
    if is_valid_lat_lng(direct_lat, direct_lng):
        return {"lat": direct_lat, "lng": direct_lng}

    geometry = None
    if isinstance(record, dict):
        geometry = record.get("geometry") or record.get("geom") or record.get("geometry_wgs84") or record.get("wkt")

    from_geometry = extract_coordinates_from_geometry(geometry)
    if from_geometry:
        return from_geometry

    possible_geometry_strings = [pick_first(flattened, ["geometry", "geom", "geometry_wgs84", "wkt", "lokacija_wkt"])]
    for value in possible_geometry_strings:
        from_string = extract_coordinates_from_geometry(value)
        if from_string:
            return from_string

    return None


def extract_coordinates_from_geometry(geometry: Any) -> dict[str, float] | None:
    if geometry is None:
        return None

    if isinstance(geometry, str):
        point_match = re.search(r"POINT\s*\(\s*(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)\s*\)", geometry, re.IGNORECASE)
        if point_match:
            lng = float(point_match.group(1))
            lat = float(point_match.group(2))
            if is_valid_lat_lng(lat, lng):
                return {"lat": lat, "lng": lng}

        numeric_pairs = [(float(match.group(1)), float(match.group(2))) for match in re.finditer(r"(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)", geometry)]
        valid_pairs = [(lng, lat) for lng, lat in numeric_pairs if is_valid_lat_lng(lat, lng)]
        if valid_pairs:
            return extract_coordinates_from_geometry(valid_pairs)
        return None

    coordinate_pairs = collect_coordinate_pairs(geometry)
    if not coordinate_pairs:
        return None

    lngs = [pair[0] for pair in coordinate_pairs]
    lats = [pair[1] for pair in coordinate_pairs]
    center_lng = min(lngs) + (max(lngs) - min(lngs)) / 2
    center_lat = min(lats) + (max(lats) - min(lats)) / 2

    if not is_valid_lat_lng(center_lat, center_lng):
        return None
    return {"lat": center_lat, "lng": center_lng}


def collect_coordinate_pairs(value: Any) -> list[tuple[float, float]]:
    if value is None:
        return []

    if isinstance(value, (list, tuple)):
        sequence = list(value)
        if len(sequence) >= 2 and all(isinstance(item, (int, float)) for item in sequence):
            lng = float(sequence[0])
            lat = float(sequence[1])
            return [(lng, lat)] if is_valid_lat_lng(lat, lng) else []

        pairs: list[tuple[float, float]] = []
        for item in sequence:
            pairs.extend(collect_coordinate_pairs(item))
        return pairs

    if isinstance(value, dict):
        if isinstance(value.get("coordinates"), list):
            return collect_coordinate_pairs(value.get("coordinates"))
        pairs: list[tuple[float, float]] = []
        for item in value.values():
            pairs.extend(collect_coordinate_pairs(item))
        return pairs

    return []


def flatten_geometry(geometry: Any) -> dict[str, Any]:
    if geometry is None:
        return {}
    if isinstance(geometry, str):
        return {"geometry": geometry}
    if isinstance(geometry, dict):
        return flatten_object({"geometry": geometry})
    return {}


def flatten_object(value: Any, prefix: str = "") -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}

    output: dict[str, Any] = {}
    for raw_key, raw_value in value.items():
        key = f"{prefix}.{raw_key}" if prefix else str(raw_key)
        if isinstance(raw_value, list):
            output[key] = raw_value
            continue
        if isinstance(raw_value, dict):
            output.update(flatten_object(raw_value, key))
            continue
        output[key] = raw_value
    return output


def pick_first(record: dict[str, Any], candidates: list[str]) -> Any:
    entries = list(record.items())
    for candidate in candidates:
        target = normalize_key(candidate)
        for key, value in entries:
            normalized_key = normalize_key(key)
            if normalized_key == target or normalized_key.endswith(f"_{target}"):
                if not is_empty_value(value):
                    return value
    return None


def normalize_key(value: Any) -> str:
    text = str(value or "")
    normalized = unicodedata.normalize("NFD", text)
    without_diacritics = "".join(char for char in normalized if unicodedata.category(char) != "Mn")
    lowered = without_diacritics.lower()
    slug = re.sub(r"[^a-z0-9]+", "_", lowered).strip("_")
    return slug


def normalize_text_for_search(value: str) -> str:
    normalized = unicodedata.normalize("NFD", value or "")
    without_diacritics = "".join(char for char in normalized if unicodedata.category(char) != "Mn")
    lowered = without_diacritics.lower()
    return re.sub(r"\s+", " ", lowered).strip()


def humanize_key(key: Any) -> str:
    text = str(key)
    last_part = text.split(".")[-1] if "." in text else text
    return re.sub(r"\b\w", lambda match: match.group(0).upper(), last_part.replace("_", " "))


def to_object(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {"value": value}


def string_value(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float)):
        return str(value)
    return ""


def stringify_value(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, list):
        return ", ".join(part for part in [stringify_value(item) for item in value] if part)
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)
    return ""


def parse_coordinate(value: Any) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, str):
        return math.nan
    normalized = value.replace(" ", "").replace(",", ".")
    try:
        return float(normalized)
    except ValueError:
        return math.nan


def is_valid_lat_lng(lat: float, lng: float) -> bool:
    return math.isfinite(lat) and math.isfinite(lng) and -90 <= lat <= 90 and -180 <= lng <= 180


def is_empty_value(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return len(value.strip()) == 0
    if isinstance(value, list):
        return len(value) == 0
    return False


def to_number(value: str) -> float | None:
    try:
        number = float(value)
    except ValueError:
        return None
    if math.isfinite(number):
        return number
    return None
