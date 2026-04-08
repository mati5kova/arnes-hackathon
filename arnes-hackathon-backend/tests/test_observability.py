from __future__ import annotations

from datetime import datetime, timezone

import pytest

import observability


def _reset_metrics() -> None:
    with observability.metrics_lock:
        observability.metrics.clear()
        observability.metrics.update(
            {
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
        )


@pytest.fixture(autouse=True)
def reset_observability_state():
    _reset_metrics()
    yield
    _reset_metrics()


def test_record_request_updates_totals_path_buckets_and_latency_stats():
    observability.record_request(path="/api/health", method="GET", status_code=200, latency_ms=10.0)
    observability.record_request(path="/api/health", method="GET", status_code=503, latency_ms=40.0)
    observability.record_request(path="/api/overlays/fire", method="GET", status_code=200, latency_ms=15.0)

    snapshot = observability.get_metrics_snapshot()

    assert snapshot["requestsTotal"] == 3
    assert snapshot["requests5xxTotal"] == 1
    assert snapshot["avgRequestLatencyMs"] == 21.67
    assert snapshot["maxRequestLatencyMs"] == 40.0

    health_bucket = snapshot["requestsByPath"]["GET /api/health"]
    assert health_bucket["count"] == 2
    assert health_bucket["errors5xx"] == 1
    assert health_bucket["avgLatencyMs"] == 25.0
    assert health_bucket["maxLatencyMs"] == 40.0

    overlays_bucket = snapshot["requestsByPath"]["GET /api/overlays/fire"]
    assert overlays_bucket["count"] == 1
    assert overlays_bucket["errors5xx"] == 0
    assert overlays_bucket["avgLatencyMs"] == 15.0


def test_record_search_and_dataset_load_metrics_are_reflected_in_snapshot():
    observability.record_search_latency(latency_ms=12.0)
    observability.record_search_latency(latency_ms=30.0)
    observability.record_dataset_load(duration_ms=1850.25, source_count=31000, site_count=28000)

    snapshot = observability.get_metrics_snapshot()

    assert snapshot["searchRequestsTotal"] == 2
    assert snapshot["avgSearchLatencyMs"] == 21.0
    assert snapshot["maxSearchLatencyMs"] == 30.0
    assert snapshot["datasetLoadsTotal"] == 1
    assert snapshot["datasetLastLoadDurationMs"] == 1850.25
    assert snapshot["datasetLastSourceCount"] == 31000
    assert snapshot["datasetLastSiteCount"] == 28000
