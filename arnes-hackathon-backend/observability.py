from __future__ import annotations

import json
from datetime import datetime, timezone
from threading import Lock
from typing import Any

metrics_lock = Lock()
metrics: dict[str, Any] = {
    "started_at": datetime.now(timezone.utc).isoformat(),
    "requests_total": 0,
    "requests_5xx_total": 0,
    "request_latency_ms_total": 0.0,
    "request_latency_ms_max": 0.0,
    "requests_by_path": {},
    "search_requests_total": 0,
    "search_latency_ms_total": 0.0,
    "search_latency_ms_max": 0.0,
    "dataset_loads_total": 0,
    "dataset_last_load_duration_ms": None,
    "dataset_last_source_count": 0,
    "dataset_last_site_count": 0,
}


def log_event(event: str, **fields: Any) -> None:
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": event,
        **fields,
    }
    print(json.dumps(payload, ensure_ascii=False), flush=True)


def record_request(*, path: str, method: str, status_code: int, latency_ms: float) -> None:
    path_key = f"{method} {path}"

    with metrics_lock:
        metrics["requests_total"] += 1
        metrics["request_latency_ms_total"] += latency_ms
        metrics["request_latency_ms_max"] = max(metrics["request_latency_ms_max"], latency_ms)

        if status_code >= 500:
            metrics["requests_5xx_total"] += 1

        path_bucket = metrics["requests_by_path"].setdefault(
            path_key,
            {
                "count": 0,
                "errors_5xx": 0,
                "latency_ms_total": 0.0,
                "latency_ms_max": 0.0,
            },
        )
        path_bucket["count"] += 1
        path_bucket["latency_ms_total"] += latency_ms
        path_bucket["latency_ms_max"] = max(path_bucket["latency_ms_max"], latency_ms)
        if status_code >= 500:
            path_bucket["errors_5xx"] += 1


def record_search_latency(*, latency_ms: float) -> None:
    with metrics_lock:
        metrics["search_requests_total"] += 1
        metrics["search_latency_ms_total"] += latency_ms
        metrics["search_latency_ms_max"] = max(metrics["search_latency_ms_max"], latency_ms)


def record_dataset_load(*, duration_ms: float, source_count: int, site_count: int) -> None:
    with metrics_lock:
        metrics["dataset_loads_total"] += 1
        metrics["dataset_last_load_duration_ms"] = duration_ms
        metrics["dataset_last_source_count"] = source_count
        metrics["dataset_last_site_count"] = site_count


def get_metrics_snapshot() -> dict[str, Any]:
    with metrics_lock:
        requests_total = int(metrics["requests_total"])
        search_requests_total = int(metrics["search_requests_total"])

        by_path: dict[str, Any] = {}
        for path_key, bucket in metrics["requests_by_path"].items():
            count = int(bucket["count"])
            avg_latency = bucket["latency_ms_total"] / count if count else 0.0
            by_path[path_key] = {
                "count": count,
                "errors5xx": int(bucket["errors_5xx"]),
                "avgLatencyMs": round(avg_latency, 2),
                "maxLatencyMs": round(float(bucket["latency_ms_max"]), 2),
            }

        avg_request_latency = metrics["request_latency_ms_total"] / requests_total if requests_total else 0.0
        avg_search_latency = metrics["search_latency_ms_total"] / search_requests_total if search_requests_total else 0.0

        return {
            "startedAt": metrics["started_at"],
            "requestsTotal": requests_total,
            "requests5xxTotal": int(metrics["requests_5xx_total"]),
            "avgRequestLatencyMs": round(avg_request_latency, 2),
            "maxRequestLatencyMs": round(float(metrics["request_latency_ms_max"]), 2),
            "requestsByPath": by_path,
            "searchRequestsTotal": search_requests_total,
            "avgSearchLatencyMs": round(avg_search_latency, 2),
            "maxSearchLatencyMs": round(float(metrics["search_latency_ms_max"]), 2),
            "datasetLoadsTotal": int(metrics["dataset_loads_total"]),
            "datasetLastLoadDurationMs": metrics["dataset_last_load_duration_ms"],
            "datasetLastSourceCount": int(metrics["dataset_last_source_count"]),
            "datasetLastSiteCount": int(metrics["dataset_last_site_count"]),
        }
