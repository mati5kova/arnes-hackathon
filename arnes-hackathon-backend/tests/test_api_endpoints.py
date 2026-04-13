from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

import main as api_main


def _dataset_status() -> dict[str, Any]:
    return {
        "ready": True,
        "loading": False,
        "loading_phase": "ready",
        "loading_progress": 100,
        "loading_started_at": 0.0,
        "source_count": 1,
        "loaded_at": 1_777_777_777_000.0,
        "last_load_duration_ms": 15.2,
        "load_count": 2,
        "last_error": None,
    }


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(api_main, "get_dataset", lambda refresh=False: {"sites": [], "site_by_id": {}, "source_count": 0})
    monkeypatch.setattr(api_main, "get_overlay_dataset", lambda refresh=False: {"loaded_at": 1_777_777_777_000.0})
    monkeypatch.setattr(api_main, "get_dataset_status", lambda: _dataset_status())
    monkeypatch.setattr(api_main, "log_event", lambda *args, **kwargs: None)

    with TestClient(api_main.app) as test_client:
        yield test_client


def test_health_endpoint_returns_expected_shape_and_headers(client: TestClient):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.headers.get("cache-control") == api_main.CACHE_CONTROL_HEALTH

    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["service"] == "heritage-map-backend"
    assert payload["datasetReady"] is True
    assert payload["datasetLoading"] is False
    assert payload["datasetPhase"] == "ready"
    assert payload["datasetProgressPct"] == 100
    assert payload["datasetSourceCount"] == 1


def test_metrics_endpoint_returns_dataset_status_and_headers(client: TestClient):
    response = client.get("/api/metrics")
    assert response.status_code == 200
    assert response.headers.get("cache-control") == api_main.CACHE_CONTROL_METRICS

    payload = response.json()
    assert "datasetStatus" in payload
    assert payload["datasetStatus"]["ready"] is True
    assert payload["datasetStatus"]["phase"] == "ready"


def test_chat_models_endpoint_returns_backend_model_config(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        api_main,
        "list_chat_models",
        lambda: [
            {
                "id": "mdml-gpt5-001",
                "label": "MDML-GPT5-001",
                "deployment": "MDML-GPT5-001",
                "available": True,
                "supportsWebSearch": True,
                "isDefault": True,
                "missingEnv": [],
            }
        ],
    )
    monkeypatch.setattr(api_main, "get_default_chat_model_id", lambda: "mdml-gpt5-001")

    response = client.get("/api/chat/models")
    assert response.status_code == 200

    payload = response.json()
    assert payload["defaultModelId"] == "mdml-gpt5-001"
    assert payload["items"][0]["label"] == "MDML-GPT5-001"
    assert payload["items"][0]["supportsWebSearch"] is True


def test_chat_usage_endpoint_returns_persisted_totals(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        api_main,
        "get_chat_usage_summary",
        lambda: {
            "updatedAt": "2026-04-02T12:00:00+00:00",
            "requestsTotal": 3,
            "webSearchRequestsTotal": 2,
            "usageTotals": {
                "inputTokens": 120,
                "outputTokens": 45,
                "totalTokens": 165,
                "reasoningTokens": 7,
            },
            "models": {
                "mdml-gpt5-001": {
                    "modelId": "mdml-gpt5-001",
                    "label": "MDML-GPT5-001",
                    "deployment": "MDML-GPT5-001",
                    "requestsTotal": 2,
                    "webSearchRequestsTotal": 1,
                    "usageTotals": {
                        "inputTokens": 80,
                        "outputTokens": 30,
                        "totalTokens": 110,
                        "reasoningTokens": 4,
                    },
                    "lastUsedAt": "2026-04-02T12:00:00+00:00",
                }
            },
        },
    )

    response = client.get("/api/chat/usage")
    assert response.status_code == 200

    payload = response.json()
    assert payload["requestsTotal"] == 3
    assert payload["webSearchRequestsTotal"] == 2
    assert payload["usageTotals"]["totalTokens"] == 165
    assert payload["models"][0]["modelId"] == "mdml-gpt5-001"
    assert payload["models"][0]["usageTotals"]["inputTokens"] == 80


def test_chat_endpoint_returns_assistant_reply_and_citations(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        api_main,
        "list_chat_models",
        lambda: [
            {
                "id": "mdml-gpt5-001",
                "label": "MDML-GPT5-001",
                "deployment": "MDML-GPT5-001",
                "available": True,
                "supportsWebSearch": True,
                "isDefault": True,
                "missingEnv": [],
            }
        ],
    )
    monkeypatch.setattr(
        api_main,
        "generate_chat_reply",
        lambda **kwargs: {
            "model": {
                "id": "mdml-gpt5-001",
                "label": "MDML-GPT5-001",
                "deployment": "MDML-GPT5-001",
            },
            "content": "Recent flooding was reported near the selected municipality.",
            "citations": [{"title": "Flood report", "url": "https://example.com/flood"}],
            "webSearchUsed": True,
            "responseId": "resp_test_123",
        },
    )

    response = client.post(
        "/api/chat",
        json={
            "messages": [{"role": "user", "content": "Any recent flooding near Ptuj?"}],
            "modelId": "mdml-gpt5-001",
        },
    )
    assert response.status_code == 200

    payload = response.json()
    assert payload["message"]["role"] == "assistant"
    assert payload["message"]["content"].startswith("Recent flooding")
    assert payload["citations"][0]["url"] == "https://example.com/flood"
    assert payload["webSearchUsed"] is True
    assert payload["responseId"] == "resp_test_123"


def test_heritage_sites_invalid_bbox_returns_400(client: TestClient):
    response = client.get("/api/heritage-sites", params={"bbox": "invalid-bbox"})
    assert response.status_code == 400
    assert "Invalid bbox" in response.json()["detail"]


def test_unknown_overlay_kind_returns_404(client: TestClient):
    response = client.get("/api/overlays/not-a-kind", params={"bbox": "13.3,45.3,16.7,46.9"})
    assert response.status_code == 404
    assert "Unknown overlay kind" in response.json()["detail"]


def test_heritage_sites_supports_etag_and_304(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    payload = {
        "items": [
            {
                "id": "EID-1",
                "registryId": "EID-1",
                "name": "Sample Site",
                "lat": 46.1,
                "lng": 14.5,
                "type": "site",
                "protectionStatus": None,
                "municipality": "TEST",
                "description": None,
                "elevationM": 337.41,
                "fireHazard": 0.2,
                "floodHazard": 0.8,
                "landslideHazard": 0.0,
                "earthquakeHazard": 4.0,
                "combinedHazard": 5.0,
                "isCluster": False,
                "clusterCount": None,
            }
        ],
        "total": 1,
        "sourceCount": 1,
        "sourceUrl": "local",
    }
    monkeypatch.setattr(api_main, "list_heritage_sites", lambda **kwargs: payload)
    monkeypatch.setattr(api_main, "get_dataset_status", lambda: _dataset_status())

    query = {"bbox": "13.3,45.3,16.7,46.9", "zoom": "8"}
    first_response = client.get("/api/heritage-sites", params=query)
    assert first_response.status_code == 200
    assert first_response.headers.get("cache-control") == api_main.CACHE_CONTROL_SITES
    assert first_response.json()["items"][0]["combinedHazard"] == 5.0

    etag = first_response.headers.get("etag")
    assert etag

    second_response = client.get("/api/heritage-sites", params=query, headers={"if-none-match": etag})
    assert second_response.status_code == 304
    assert second_response.headers.get("etag") == etag


def test_heritage_site_detail_supports_etag_and_304(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    site_payload = {
        "id": "EID-42",
        "registryId": "EID-42",
        "name": "Detail Site",
        "lat": 46.1,
        "lng": 14.5,
        "type": "site",
        "protectionStatus": "protected",
        "municipality": "TEST",
        "description": "Detailed description",
        "elevationM": 337.41,
        "fireHazard": 0.2,
        "floodHazard": 0.8,
        "landslideHazard": 0.0,
        "earthquakeHazard": 4.0,
        "combinedHazard": 5.0,
        "isCluster": False,
        "clusterCount": None,
        "detailFields": [{"label": "Datacija", "value": "19. stol."}],
        "sourceUrl": "local",
    }

    monkeypatch.setattr(
        api_main,
        "get_heritage_site_details",
        lambda site_id, refresh=False: site_payload if site_id == "EID-42" else None,
    )
    monkeypatch.setattr(api_main, "get_dataset_status", lambda: _dataset_status())

    first_response = client.get("/api/heritage-sites/EID-42")
    assert first_response.status_code == 200
    assert first_response.headers.get("cache-control") == api_main.CACHE_CONTROL_SITE_DETAIL
    assert first_response.json()["fireHazard"] == 0.2

    etag = first_response.headers.get("etag")
    assert etag

    second_response = client.get("/api/heritage-sites/EID-42", headers={"if-none-match": etag})
    assert second_response.status_code == 304
    assert second_response.headers.get("etag") == etag
