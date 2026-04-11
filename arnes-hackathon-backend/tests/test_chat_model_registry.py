from __future__ import annotations

from types import SimpleNamespace

import chat_service
import pytest
from system_prompt import SYSTEM_PROMPT


def test_list_chat_models_returns_multiple_configured_models(monkeypatch):
    monkeypatch.setattr(chat_service, "ACTIVE_MODEL_ENV_PREFIX", "CHAT_MODEL_MDML_GPT5_001")
    monkeypatch.delenv("CHAT_MODEL_MDML_GPT4O_MINI_001_API_KEY", raising=False)
    monkeypatch.delenv("CHAT_MODEL_MDML_GPT4O_MINI_001_TOKEN", raising=False)
    monkeypatch.delenv("CHAT_MODEL_MDML_GPT4O_MINI_001_BASE_URL", raising=False)
    monkeypatch.delenv("CHAT_MODEL_MDML_GPT4O_MINI_001_ENDPOINT", raising=False)
    monkeypatch.delenv("CHAT_MODEL_MDML_GPT5_001_API_KEY", raising=False)
    monkeypatch.delenv("CHAT_MODEL_MDML_GPT5_001_TOKEN", raising=False)
    monkeypatch.delenv("CHAT_MODEL_MDML_GPT5_001_BASE_URL", raising=False)
    monkeypatch.delenv("CHAT_MODEL_MDML_GPT5_001_ENDPOINT", raising=False)
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "shared-key")
    monkeypatch.setenv("AZURE_OPENAI_BASE_URL", "https://shared-resource.openai.azure.com/openai/v1/")
    monkeypatch.setenv("CHAT_MODEL_MDML_GPT4O_MINI_001_DEPLOYMENT", "MDML-GPT4o-Mini-001")
    monkeypatch.setenv("CHAT_MODEL_MDML_GPT5_001_DEPLOYMENT", "MDML-GPT5-001")

    models = chat_service.list_chat_models()
    models_by_id = {item["id"]: item for item in models}

    assert models_by_id["mdml-gpt4o-mini-001"]["available"] is True
    assert models_by_id["mdml-gpt5-001"]["available"] is True
    assert models_by_id["mdml-gpt5-001"]["isDefault"] is True
    assert chat_service.get_default_chat_model_id() == "mdml-gpt5-001"

    spec = chat_service._find_model_spec_by_id("mdml-gpt4o-mini-001")
    assert spec is not None
    config = chat_service._resolve_model_config(spec)
    assert config["azureEndpoint"] == "https://shared-resource.openai.azure.com"


def test_system_prompt_allows_general_disaster_queries_in_slovenia():
    assert "Če uporabnik sprašuje o preteklih ali nedavnih naravnih nesrečah v Sloveniji" in SYSTEM_PROMPT


def test_generate_chat_reply_uses_selected_model_configuration(monkeypatch):
    monkeypatch.setattr(chat_service, "ACTIVE_MODEL_ENV_PREFIX", "CHAT_MODEL_MDML_GPT5_001")
    monkeypatch.setenv("CHAT_MODEL_MDML_GPT4O_MINI_001_DEPLOYMENT", "MDML-GPT4o-Mini-001")
    monkeypatch.setenv("CHAT_MODEL_MDML_GPT4O_MINI_001_API_KEY", "mini-key")
    monkeypatch.setenv("CHAT_MODEL_MDML_GPT4O_MINI_001_BASE_URL", "https://mini-resource.openai.azure.com/openai/v1/")
    monkeypatch.setenv("CHAT_MODEL_MDML_GPT5_001_DEPLOYMENT", "MDML-GPT5-001")
    monkeypatch.setenv("CHAT_MODEL_MDML_GPT5_001_API_KEY", "gpt5-key")
    monkeypatch.setenv("CHAT_MODEL_MDML_GPT5_001_BASE_URL", "https://gpt5-resource.openai.azure.com/openai/v1/")

    captured: dict[str, str] = {}

    class FakeResponse:
        id = "resp_selected_model"
        output = []
        output_text = '<div class="kulturko-response"><p>Selected model reply.</p></div>'
        usage = SimpleNamespace(
            input_tokens=12,
            output_tokens=8,
            total_tokens=20,
            output_tokens_details=SimpleNamespace(reasoning_tokens=3),
        )

    class FakeResponses:
        def create(self, *, model, input, tools, max_output_tokens):
            captured["deployment"] = model
            return FakeResponse()

    class FakeClient:
        responses = FakeResponses()

    def fake_create_azure_client(*, api_key: str, azure_endpoint: str):
        captured["api_key"] = api_key
        captured["azure_endpoint"] = azure_endpoint
        return FakeClient()

    monkeypatch.setattr(chat_service, "_create_azure_client", fake_create_azure_client)
    monkeypatch.setattr(chat_service, "_record_usage_summary", lambda **kwargs: None)

    result = chat_service.generate_chat_reply(
        messages=[{"role": "user", "content": "Pozdravljen"}],
        model_id="mdml-gpt4o-mini-001",
        use_web_search=False,
    )

    assert captured["api_key"] == "mini-key"
    assert captured["azure_endpoint"] == "https://mini-resource.openai.azure.com"
    assert captured["deployment"] == "MDML-GPT4o-Mini-001"
    assert result["model"]["id"] == "mdml-gpt4o-mini-001"
    assert "Selected model reply." in result["content"]


def test_generate_chat_reply_generates_local_response_id_when_provider_id_missing(monkeypatch):
    monkeypatch.setenv("CHAT_MODEL_MDML_GPT4O_MINI_001_DEPLOYMENT", "MDML-GPT4o-Mini-001")
    monkeypatch.setenv("CHAT_MODEL_MDML_GPT4O_MINI_001_API_KEY", "mini-key")
    monkeypatch.setenv("CHAT_MODEL_MDML_GPT4O_MINI_001_BASE_URL", "https://mini-resource.openai.azure.com/openai/v1/")

    class FakeResponse:
        id = None
        output = []
        output_text = '<div class="kulturko-response"><p>Fallback id reply.</p></div>'
        usage = SimpleNamespace(
            input_tokens=5,
            output_tokens=4,
            total_tokens=9,
            output_tokens_details=SimpleNamespace(reasoning_tokens=0),
        )

    class FakeResponses:
        def create(self, *, model, input, tools, max_output_tokens):
            return FakeResponse()

    class FakeClient:
        responses = FakeResponses()

    monkeypatch.setattr(chat_service, "_create_azure_client", lambda **kwargs: FakeClient())
    monkeypatch.setattr(chat_service, "_record_usage_summary", lambda **kwargs: None)

    result = chat_service.generate_chat_reply(
        messages=[{"role": "user", "content": "Pozdravljen"}],
        model_id="mdml-gpt4o-mini-001",
        use_web_search=False,
    )

    assert isinstance(result["responseId"], str)
    assert result["responseId"].startswith("local-")
    assert len(result["responseId"]) > len("local-")


def test_generate_chat_reply_uses_last_completed_assistant_message(monkeypatch):
    monkeypatch.setenv("CHAT_MODEL_MDML_GPT4O_MINI_001_DEPLOYMENT", "MDML-GPT4o-Mini-001")
    monkeypatch.setenv("CHAT_MODEL_MDML_GPT4O_MINI_001_API_KEY", "mini-key")
    monkeypatch.setenv("CHAT_MODEL_MDML_GPT4O_MINI_001_BASE_URL", "https://mini-resource.openai.azure.com/openai/v1/")

    class FakeAnnotation(SimpleNamespace):
        pass

    class FakeMessage(SimpleNamespace):
        pass

    class FakeResponse:
        id = "resp_last_message"
        output_text = "stara zavrnitev in nov odgovor skupaj"
        usage = SimpleNamespace(
            input_tokens=12,
            output_tokens=8,
            total_tokens=20,
            output_tokens_details=SimpleNamespace(reasoning_tokens=0),
        )
        output = [
            FakeMessage(
                type="message",
                role="assistant",
                status="completed",
                content=[
                    SimpleNamespace(
                        type="output_text",
                        text='<div class="kulturko-response"><p>To ni pravi odgovor.</p></div>',
                        annotations=[],
                    )
                ],
            ),
            FakeMessage(
                type="message",
                role="assistant",
                status="completed",
                content=[
                    SimpleNamespace(
                        type="output_text",
                        text='<div class="kulturko-response"><p>To je koncni odgovor.</p></div>',
                        annotations=[
                            FakeAnnotation(title="Vir", url="https://example.com/vir"),
                        ],
                    )
                ],
            ),
        ]

    class FakeResponses:
        def create(self, *, model, input, tools, max_output_tokens):
            return FakeResponse()

    class FakeClient:
        responses = FakeResponses()

    monkeypatch.setattr(chat_service, "_create_azure_client", lambda **kwargs: FakeClient())
    monkeypatch.setattr(chat_service, "_record_usage_summary", lambda **kwargs: None)

    result = chat_service.generate_chat_reply(
        messages=[{"role": "user", "content": "Kaj se je zgodilo v Kranju?"}],
        model_id="mdml-gpt4o-mini-001",
        use_web_search=True,
    )

    assert result["content"] == '<div class="kulturko-response"><p>To je koncni odgovor.</p></div>'
    assert result["citations"] == [{"title": "Vir", "url": "https://example.com/vir"}]


def test_generate_chat_reply_retries_once_after_incomplete_response(monkeypatch):
    monkeypatch.setenv("CHAT_MODEL_MDML_GPT4O_MINI_001_DEPLOYMENT", "MDML-GPT4o-Mini-001")
    monkeypatch.setenv("CHAT_MODEL_MDML_GPT4O_MINI_001_API_KEY", "mini-key")
    monkeypatch.setenv("CHAT_MODEL_MDML_GPT4O_MINI_001_BASE_URL", "https://mini-resource.openai.azure.com/openai/v1/")
    monkeypatch.setattr(chat_service, "CHAT_INCOMPLETE_RESPONSE_RETRIES", 1)

    class FakeMessage(SimpleNamespace):
        pass

    first_response = SimpleNamespace(
        id="resp_incomplete",
        output=[],
        output_text="",
        usage=SimpleNamespace(
            input_tokens=12,
            output_tokens=8,
            total_tokens=20,
            output_tokens_details=SimpleNamespace(reasoning_tokens=0),
        ),
    )
    first_response.output = [
        FakeMessage(
            type="message",
            role="assistant",
            status="incomplete",
            content=[
                SimpleNamespace(
                    type="output_text",
                    text='<div class="kulturko-response"><p>Odrezan odgovor',
                    annotations=[],
                )
            ],
        )
    ]

    second_response = SimpleNamespace(
        id="resp_complete",
        output=[],
        output_text="",
        usage=SimpleNamespace(
            input_tokens=12,
            output_tokens=8,
            total_tokens=20,
            output_tokens_details=SimpleNamespace(reasoning_tokens=0),
        ),
    )
    second_response.output = [
        FakeMessage(
            type="message",
            role="assistant",
            status="completed",
            content=[
                SimpleNamespace(
                    type="output_text",
                    text='<div class="kulturko-response"><p>Cel odgovor.</p></div>',
                    annotations=[],
                )
            ],
        )
    ]

    responses = [first_response, second_response]
    create_calls: list[list[dict[str, str]]] = []

    class FakeResponses:
        def create(self, *, model, input, tools, max_output_tokens):
            create_calls.append(list(input))
            return responses.pop(0)

    class FakeClient:
        responses = FakeResponses()

    monkeypatch.setattr(chat_service, "_create_azure_client", lambda **kwargs: FakeClient())
    monkeypatch.setattr(chat_service, "_record_usage_summary", lambda **kwargs: None)

    result = chat_service.generate_chat_reply(
        messages=[{"role": "user", "content": "Kaj se je zgodilo v Kranju?"}],
        model_id="mdml-gpt4o-mini-001",
        use_web_search=True,
    )

    assert result["content"] == '<div class="kulturko-response"><p>Cel odgovor.</p></div>'
    assert len(create_calls) == 2
    assert create_calls[0] == create_calls[1]


def test_generate_chat_reply_returns_502_after_repeated_incomplete_response(monkeypatch):
    monkeypatch.setenv("CHAT_MODEL_MDML_GPT4O_MINI_001_DEPLOYMENT", "MDML-GPT4o-Mini-001")
    monkeypatch.setenv("CHAT_MODEL_MDML_GPT4O_MINI_001_API_KEY", "mini-key")
    monkeypatch.setenv("CHAT_MODEL_MDML_GPT4O_MINI_001_BASE_URL", "https://mini-resource.openai.azure.com/openai/v1/")
    monkeypatch.setattr(chat_service, "CHAT_INCOMPLETE_RESPONSE_RETRIES", 1)

    class FakeMessage(SimpleNamespace):
        pass

    incomplete_response = SimpleNamespace(
        id="resp_incomplete",
        output=[],
        output_text="",
        usage=SimpleNamespace(
            input_tokens=12,
            output_tokens=8,
            total_tokens=20,
            output_tokens_details=SimpleNamespace(reasoning_tokens=0),
        ),
    )
    incomplete_response.output = [
        FakeMessage(
            type="message",
            role="assistant",
            status="incomplete",
            content=[
                SimpleNamespace(
                    type="output_text",
                    text='<div class="kulturko-response"><p>Odrezan odgovor',
                    annotations=[],
                )
            ],
        )
    ]

    class FakeResponses:
        def create(self, *, model, input, tools, max_output_tokens):
            return incomplete_response

    class FakeClient:
        responses = FakeResponses()

    monkeypatch.setattr(chat_service, "_create_azure_client", lambda **kwargs: FakeClient())
    monkeypatch.setattr(chat_service, "_record_usage_summary", lambda **kwargs: None)

    with pytest.raises(chat_service.ChatServiceError) as exc_info:
        chat_service.generate_chat_reply(
            messages=[{"role": "user", "content": "Kaj se je zgodilo v Kranju?"}],
            model_id="mdml-gpt4o-mini-001",
            use_web_search=True,
        )

    assert exc_info.value.status_code == 502
    assert "incomplete response" in str(exc_info.value)
