from __future__ import annotations

from types import SimpleNamespace

import chat_service


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
