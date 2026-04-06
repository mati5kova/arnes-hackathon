from __future__ import annotations

import json

import chat_service


def test_usage_summary_is_persisted_per_model(tmp_path, monkeypatch):
    summary_path = tmp_path / "chat-usage-summary.json"
    monkeypatch.setattr(chat_service, "CHAT_USAGE_SUMMARY_FILE", summary_path)

    chat_service._record_usage_summary(
        model_id="mdml-gpt5-001",
        model_label="MDML-GPT5-001",
        deployment="MDML-GPT5-001",
        usage={
            "inputTokens": 100,
            "outputTokens": 50,
            "totalTokens": 150,
            "reasoningTokens": 10,
        },
        web_search_used=True,
    )
    chat_service._record_usage_summary(
        model_id="mdml-gpt5-001",
        model_label="MDML-GPT5-001",
        deployment="MDML-GPT5-001",
        usage={
            "inputTokens": 20,
            "outputTokens": 10,
            "totalTokens": 30,
            "reasoningTokens": 2,
        },
        web_search_used=False,
    )

    payload = chat_service.get_chat_usage_summary()
    assert payload["requestsTotal"] == 2
    assert payload["webSearchRequestsTotal"] == 1
    assert payload["usageTotals"]["inputTokens"] == 120
    assert payload["usageTotals"]["totalTokens"] == 180
    assert payload["models"]["mdml-gpt5-001"]["requestsTotal"] == 2
    assert payload["models"]["mdml-gpt5-001"]["webSearchRequestsTotal"] == 1
    assert payload["models"]["mdml-gpt5-001"]["usageTotals"]["outputTokens"] == 60

    on_disk = json.loads(summary_path.read_text(encoding="utf-8"))
    assert on_disk["models"]["mdml-gpt5-001"]["usageTotals"]["reasoningTokens"] == 12
