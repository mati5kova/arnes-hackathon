from __future__ import annotations

import json
import os
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent
load_dotenv()

DEFAULT_RISK_DATA_FILE = BASE_DIR / "AI" / "Data" / "kd_z_nevarnost.geojson"
CHAT_RISK_DATA_FILE = Path(os.getenv("CHAT_RISK_DATA_FILE", str(DEFAULT_RISK_DATA_FILE)))
CHAT_MAX_TOOL_ROUNDS = max(1, int(os.getenv("CHAT_MAX_TOOL_ROUNDS", "8")))
CHAT_MAX_TOOL_RESULTS = max(1, min(25, int(os.getenv("CHAT_MAX_TOOL_RESULTS", "8"))))
CHAT_MAX_OUTPUT_TOKENS = max(256, int(os.getenv("CHAT_MAX_OUTPUT_TOKENS", "1200")))
CHAT_USAGE_SUMMARY_FILE = Path(
    os.getenv("CHAT_USAGE_SUMMARY_FILE", str(BASE_DIR / "logs" / "chat-usage-summary.json"))
)

# Azure OpenAI API version — update if needed
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview")


class ChatServiceError(RuntimeError):
    def __init__(self, message: str, *, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class ModelSpec:
    id: str
    label: str
    env_prefix: str


MODEL_SPECS = (
    ModelSpec("mdml-gpt4-1-mini-001", "MDML-GPT4.1-Mini-001", "CHAT_MODEL_MDML_GPT4_1_MINI_001"),
    ModelSpec("mdml-gpt4o-mini-001", "MDML-GPT4o-Mini-001", "CHAT_MODEL_MDML_GPT4O_MINI_001"),
    ModelSpec("mdml-gpt4o-002", "MDML-GPT4o-002", "CHAT_MODEL_MDML_GPT4O_002"),
    ModelSpec("mdml-gpt4o-001", "MDML-GPT4o-001", "CHAT_MODEL_MDML_GPT4O_001"),
    ModelSpec("mdml-gpt5-mini-001", "MDML-GPT5-Mini-001", "CHAT_MODEL_MDML_GPT5_MINI_001"),
    ModelSpec("mdml-gpt5-001", "MDML-GPT5-001", "CHAT_MODEL_MDML_GPT5_001"),
    ModelSpec("mdml-gpt5-1-001", "MDML-GPT5.1-001", "CHAT_MODEL_MDML_GPT5_1_001"),
    ModelSpec("mdml-gpt5-2-001", "MDML-GPT5.2-001", "CHAT_MODEL_MDML_GPT5_2_001"),
    ModelSpec("mdml-gpt5-nano-001", "MDML-GPT5-Nano-001", "CHAT_MODEL_MDML_GPT5_NANO_001"),
)

SYSTEM_PROMPT = """
You are KULTURKO, the cultural-heritage risk assistant for this project.

Your job is to help users understand Slovenian cultural heritage sites, risk factors, and the purpose of the app:
- the map shows Slovenian heritage sites
- overlay layers show environmental hazards such as fire, flood, air, and landslide exposure
- the assistant can use local heritage-risk tools for dataset-backed answers
- when web search is enabled, you may use web search for recent or external context

Response style:
- be concise, practical, and transparent
- prefer local dataset tools for exact site and risk facts
- use web search for current events, recent incidents, or missing external context
- if web search is disabled, say you are relying on the local heritage dataset when that matters
- never invent facts, EIDs, or sources
""".strip()

RISK_DATA_CACHE: dict[str, Any] = {
    "loaded": False,
    "records": [],
    "by_eid": {},
    "path": None,
}
RISK_DATA_LOCK = Lock()
USAGE_SUMMARY_LOCK = Lock()


def list_chat_models() -> list[dict[str, Any]]:
    return [_serialize_model(spec) for spec in MODEL_SPECS]


def get_default_chat_model_id() -> str:
    models = list_chat_models()
    for model in models:
        if model["available"]:
            return str(model["id"])
    return str(models[0]["id"])


def get_chat_usage_summary() -> dict[str, Any]:
    return _read_usage_summary()


def generate_chat_reply(
    *,
    messages: list[dict[str, str]],
    model_id: str,
    use_web_search: bool,
) -> dict[str, Any]:
    selected_spec = next((spec for spec in MODEL_SPECS if spec.id == model_id), None)
    if selected_spec is None:
        raise ChatServiceError(f"Unknown chat model '{model_id}'.", status_code=404)

    model_config = _resolve_model_config(selected_spec)
    if not model_config["available"]:
        raise ChatServiceError(
            f"Model '{selected_spec.label}' is not fully configured. Missing: {', '.join(model_config['missingEnv'])}",
            status_code=503,
        )

    sanitized_messages = _sanitize_messages(messages)
    if not sanitized_messages:
        raise ChatServiceError("At least one chat message is required.", status_code=400)

    client = _create_azure_client(
        api_key=model_config["apiKey"],
        azure_endpoint=model_config["azureEndpoint"],
    )

    aggregated_usage = _empty_usage_totals()
    web_search_used = False
    tools = _build_tools(use_web_search=use_web_search)

    # Build the full message list with the system prompt prepended
    conversation: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        *sanitized_messages,
    ]

    for _ in range(CHAT_MAX_TOOL_ROUNDS + 1):
        response = client.chat.completions.create(
            model=model_config["deployment"],
            messages=conversation,
            tools=tools if tools else None,
            max_tokens=CHAT_MAX_OUTPUT_TOKENS,
        )
        _merge_usage(aggregated_usage, _extract_usage_from_completion(response))

        choice = response.choices[0]
        assistant_message = choice.message

        # Append the assistant turn to maintain history
        conversation.append(assistant_message.model_dump(exclude_unset=True))

        # Check finish reason — done if no tool calls
        if choice.finish_reason != "tool_calls" or not assistant_message.tool_calls:
            break

        # Execute each tool call and append results
        for tool_call in assistant_message.tool_calls:
            try:
                parsed_arguments = json.loads(tool_call.function.arguments or "{}")
            except json.JSONDecodeError as exc:
                parsed_arguments = {"_error": f"Invalid JSON arguments: {exc}"}

            try:
                output = _dispatch_tool_call(tool_call.function.name, parsed_arguments)
            except Exception as exc:
                output = {"error": str(exc)}

            conversation.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(output, ensure_ascii=False, default=str),
                }
            )

    text = (assistant_message.content or "").strip()
    if not text:
        raise ChatServiceError("The selected model returned an empty response.", status_code=502)

    _record_usage_summary(
        model_id=model_config["id"],
        model_label=model_config["label"],
        deployment=model_config["deployment"],
        usage=aggregated_usage,
        web_search_used=web_search_used,
    )

    return {
        "model": {
            "id": model_config["id"],
            "label": model_config["label"],
            "deployment": model_config["deployment"],
        },
        "content": text,
        "citations": [],  # Azure chat completions don't return URL annotations
        "webSearchUsed": web_search_used,
        "responseId": response.id,
        "usage": aggregated_usage,
    }


def _sanitize_messages(messages: list[dict[str, str]]) -> list[dict[str, str]]:
    sanitized: list[dict[str, str]] = []
    for message in messages:
        role = str(message.get("role") or "").strip()
        content = str(message.get("content") or "").strip()
        if role not in {"user", "assistant"} or not content:
            continue
        sanitized.append({"role": role, "content": content})
    return sanitized


def _serialize_model(spec: ModelSpec) -> dict[str, Any]:
    resolved = _resolve_model_config(spec)
    return {
        "id": resolved["id"],
        "label": resolved["label"],
        "deployment": resolved["deployment"],
        "available": resolved["available"],
        "missingEnv": resolved["missingEnv"],
        "supportsWebSearch": True,
        "isDefault": resolved["id"] == get_first_available_model_id(),
    }


def get_first_available_model_id() -> str:
    for spec in MODEL_SPECS:
        if _resolve_model_config(spec)["available"]:
            return spec.id
    return MODEL_SPECS[0].id


def _resolve_model_config(spec: ModelSpec) -> dict[str, Any]:
    deployment = _read_env(f"{spec.env_prefix}_DEPLOYMENT") or spec.label
    api_key = (
        _read_env(f"{spec.env_prefix}_API_KEY")
        or _read_env(f"{spec.env_prefix}_TOKEN")
        or _read_env("AZURE_OPENAI_API_KEY")
        or _read_env("AZURE_OPENAI_TOKEN")
    )
    azure_endpoint = _resolve_azure_endpoint(spec.env_prefix)

    missing_env: list[str] = []
    if not api_key:
        missing_env.append(f"{spec.env_prefix}_API_KEY")
    if not azure_endpoint:
        missing_env.append(f"{spec.env_prefix}_BASE_URL or {spec.env_prefix}_ENDPOINT")

    return {
        "id": spec.id,
        "label": spec.label,
        "deployment": deployment,
        "apiKey": api_key,
        "azureEndpoint": azure_endpoint,
        "available": not missing_env,
        "missingEnv": missing_env,
    }


def _resolve_azure_endpoint(env_prefix: str) -> str | None:
    """
    Returns a clean Azure endpoint (e.g. https://my-resource.openai.azure.com).
    Accepts BASE_URL or ENDPOINT env vars — strips any /openai/v1 suffix so the
    AzureOpenAI client can build the correct path itself.
    """
    raw = (
        _read_env(f"{env_prefix}_BASE_URL")
        or _read_env(f"{env_prefix}_ENDPOINT")
        or _read_env("AZURE_OPENAI_BASE_URL")
        or _read_env("AZURE_OPENAI_ENDPOINT")
    )
    if not raw:
        return None
    # Strip any trailing path the old code added so we get the bare endpoint
    endpoint = raw.rstrip("/")
    for suffix in ("/openai/v1", "/openai"):
        if endpoint.endswith(suffix):
            endpoint = endpoint[: -len(suffix)]
    return endpoint


def _read_env(name: str) -> str | None:
    value = os.getenv(name)
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _create_azure_client(*, api_key: str, azure_endpoint: str) -> Any:
    try:
        from openai import AzureOpenAI
    except ModuleNotFoundError as exc:
        raise ChatServiceError(
            "Chat dependencies are not installed. Install backend requirements first.",
            status_code=503,
        ) from exc

    return AzureOpenAI(
        api_key=api_key,
        azure_endpoint=azure_endpoint,
        api_version=AZURE_OPENAI_API_VERSION,
    )


def _build_tools(*, use_web_search: bool) -> list[dict[str, Any]]:
    """
    Build the tools list for chat.completions.create().
    web_search_preview is an OpenAI-platform-only tool and is intentionally
    omitted here — Azure deployments don't support it.
    """
    tools: list[dict[str, Any]] = [
        {
            "type": "function",
            "function": {
                "name": "find_heritage_sites",
                "description": "Find heritage sites in the local Slovenian heritage-risk dataset by name, EID, municipality, or region.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search string such as a site name, EID, municipality, or region.",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of results to return.",
                            "minimum": 1,
                            "maximum": CHAT_MAX_TOOL_RESULTS,
                        },
                    },
                    "required": ["query"],
                    "additionalProperties": False,
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_site_risk_profile",
                "description": "Return local risk and heritage metadata for a specific site by EID.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "eid": {
                            "type": "string",
                            "description": "The heritage site EID, for example 1-02508.",
                        }
                    },
                    "required": ["eid"],
                    "additionalProperties": False,
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_top_risk_sites",
                "description": "Return the highest-risk sites for a selected hazard within a municipality, region, or administrative unit.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "area_type": {
                            "type": "string",
                            "enum": ["municipality", "region", "administrative_unit"],
                            "description": "Which area field to filter by.",
                        },
                        "area_name": {
                            "type": "string",
                            "description": "The municipality, region, or administrative-unit name.",
                        },
                        "hazard": {
                            "type": "string",
                            "enum": ["poplave", "pozar", "plazovi", "potres"],
                            "description": "The hazard column to rank by.",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of results to return.",
                            "minimum": 1,
                            "maximum": CHAT_MAX_TOOL_RESULTS,
                        },
                    },
                    "required": ["area_type", "area_name", "hazard"],
                    "additionalProperties": False,
                },
            },
        },
    ]

    # NOTE: web_search_preview is not available on Azure OpenAI.
    # If use_web_search is requested, we silently ignore it here.
    # You could integrate Bing Search or another Azure-native solution if needed.
    _ = use_web_search

    return tools


def _dispatch_tool_call(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    if name == "find_heritage_sites":
        return {
            "items": _find_heritage_sites(
                query=str(arguments.get("query") or ""),
                limit=int(arguments.get("limit") or CHAT_MAX_TOOL_RESULTS),
            )
        }
    if name == "get_site_risk_profile":
        return _get_site_risk_profile(eid=str(arguments.get("eid") or ""))
    if name == "get_top_risk_sites":
        return {
            "items": _get_top_risk_sites(
                area_type=str(arguments.get("area_type") or ""),
                area_name=str(arguments.get("area_name") or ""),
                hazard=str(arguments.get("hazard") or ""),
                limit=int(arguments.get("limit") or CHAT_MAX_TOOL_RESULTS),
            )
        }
    raise ValueError(f"Unknown tool '{name}'.")


def _load_risk_dataset() -> dict[str, Any]:
    with RISK_DATA_LOCK:
        if RISK_DATA_CACHE["loaded"] and RISK_DATA_CACHE["path"] == str(CHAT_RISK_DATA_FILE):
            return RISK_DATA_CACHE

        if not CHAT_RISK_DATA_FILE.exists():
            raise FileNotFoundError(f"Risk dataset not found at {CHAT_RISK_DATA_FILE}")

        payload = json.loads(CHAT_RISK_DATA_FILE.read_text(encoding="utf-8"))
        features = payload.get("features") if isinstance(payload, dict) else None
        if not isinstance(features, list):
            raise ValueError("Risk dataset is missing a valid GeoJSON feature list.")

        records: list[dict[str, Any]] = []
        by_eid: dict[str, dict[str, Any]] = {}
        for feature in features:
            if not isinstance(feature, dict):
                continue
            properties = feature.get("properties")
            if not isinstance(properties, dict):
                continue

            eid = str(properties.get("EID") or "").strip()
            if not eid:
                continue

            record = {
                "eid": eid,
                "name": _string_value(properties.get("IME")),
                "municipality": _string_value(properties.get("OBCINA")),
                "region": _string_value(properties.get("regija")),
                "administrativeUnit": _string_value(properties.get("UE_UIME")),
                "type": _string_value(properties.get("TIP") or properties.get("ZVRST")),
                "status": _string_value(properties.get("STATUS")),
                "description": _string_value(properties.get("OPIS")),
                "datacija": _string_value(properties.get("DATACIJA")),
                "locationDescription": _string_value(properties.get("LOKACIJAOPIS")),
                "sourceUrl": _string_value(properties.get("POVEZAVA1")),
                "qrUrl": _string_value(properties.get("QR")),
                "photoUrl": _string_value(properties.get("PHOTOURL")),
                "hazards": {
                    "poplave": _float_value(properties.get("poplave")),
                    "pozar": _float_value(properties.get("pozar")),
                    "plazovi": _float_value(properties.get("plazovi")),
                    "potres": _float_value(properties.get("potres")),
                },
            }
            record["searchText"] = _normalize_search_text(
                " ".join(
                    value
                    for value in [
                        record["eid"],
                        record["name"],
                        record["municipality"],
                        record["region"],
                        record["administrativeUnit"],
                        record["type"],
                    ]
                    if value
                )
            )
            records.append(record)
            by_eid[eid] = record

        RISK_DATA_CACHE.update(
            {
                "loaded": True,
                "records": records,
                "by_eid": by_eid,
                "path": str(CHAT_RISK_DATA_FILE),
            }
        )
        return RISK_DATA_CACHE


def _find_heritage_sites(*, query: str, limit: int) -> list[dict[str, Any]]:
    normalized_query = _normalize_search_text(query)
    if not normalized_query:
        raise ValueError("The query must not be empty.")

    dataset = _load_risk_dataset()
    clamped_limit = max(1, min(limit, CHAT_MAX_TOOL_RESULTS))

    matches = [record for record in dataset["records"] if normalized_query in record["searchText"]]
    matches.sort(key=lambda record: (record["name"] or "", record["eid"]))
    return [_summarize_risk_record(record) for record in matches[:clamped_limit]]


def _get_site_risk_profile(*, eid: str) -> dict[str, Any]:
    normalized_eid = eid.strip()
    if not normalized_eid:
        raise ValueError("The EID must not be empty.")

    dataset = _load_risk_dataset()
    record = dataset["by_eid"].get(normalized_eid)
    if not record:
        raise ValueError(f"No site was found for EID '{normalized_eid}'.")
    return record


def _get_top_risk_sites(*, area_type: str, area_name: str, hazard: str, limit: int) -> list[dict[str, Any]]:
    field_name = {
        "municipality": "municipality",
        "region": "region",
        "administrative_unit": "administrativeUnit",
    }.get(area_type)
    if field_name is None:
        raise ValueError("Unsupported area_type.")

    if hazard not in {"poplave", "pozar", "plazovi", "potres"}:
        raise ValueError("Unsupported hazard.")

    normalized_area_name = _normalize_search_text(area_name)
    if not normalized_area_name:
        raise ValueError("The area_name must not be empty.")

    dataset = _load_risk_dataset()
    clamped_limit = max(1, min(limit, CHAT_MAX_TOOL_RESULTS))

    filtered = [
        record
        for record in dataset["records"]
        if _normalize_search_text(str(record.get(field_name) or "")) == normalized_area_name
    ]
    filtered.sort(
        key=lambda record: (
            -float(record["hazards"].get(hazard) or 0),
            record["name"] or "",
            record["eid"],
        )
    )

    return [
        {
            **_summarize_risk_record(record),
            "selectedHazard": hazard,
            "selectedHazardScore": record["hazards"].get(hazard),
        }
        for record in filtered[:clamped_limit]
    ]


def _summarize_risk_record(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "eid": record["eid"],
        "name": record["name"],
        "municipality": record["municipality"],
        "region": record["region"],
        "administrativeUnit": record["administrativeUnit"],
        "type": record["type"],
        "status": record["status"],
        "hazards": record["hazards"],
        "sourceUrl": record["sourceUrl"],
        "qrUrl": record["qrUrl"],
    }


def _extract_usage_from_completion(response: Any) -> dict[str, int]:
    usage = getattr(response, "usage", None)
    if usage is None:
        return _empty_usage_totals()

    input_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
    output_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
    total_tokens = int(getattr(usage, "total_tokens", input_tokens + output_tokens) or 0)

    completion_tokens_details = getattr(usage, "completion_tokens_details", None)
    reasoning_tokens = int(getattr(completion_tokens_details, "reasoning_tokens", 0) or 0)

    return {
        "inputTokens": input_tokens,
        "outputTokens": output_tokens,
        "totalTokens": total_tokens,
        "reasoningTokens": reasoning_tokens,
    }


def _empty_usage_totals() -> dict[str, int]:
    return {
        "inputTokens": 0,
        "outputTokens": 0,
        "totalTokens": 0,
        "reasoningTokens": 0,
    }


def _merge_usage(target: dict[str, int], source: dict[str, int]) -> None:
    for key in ("inputTokens", "outputTokens", "totalTokens", "reasoningTokens"):
        target[key] = int(target.get(key, 0)) + int(source.get(key, 0))


def _record_usage_summary(
    *,
    model_id: str,
    model_label: str,
    deployment: str,
    usage: dict[str, int],
    web_search_used: bool,
) -> None:
    with USAGE_SUMMARY_LOCK:
        summary = _read_usage_summary()
        now = datetime.now(timezone.utc).isoformat()

        summary["updatedAt"] = now
        summary["requestsTotal"] = int(summary.get("requestsTotal", 0)) + 1
        summary["webSearchRequestsTotal"] = int(summary.get("webSearchRequestsTotal", 0)) + (1 if web_search_used else 0)
        _merge_usage(summary["usageTotals"], usage)

        per_model = summary["models"].setdefault(
            model_id,
            {
                "modelId": model_id,
                "label": model_label,
                "deployment": deployment,
                "requestsTotal": 0,
                "webSearchRequestsTotal": 0,
                "usageTotals": _empty_usage_totals(),
                "lastUsedAt": now,
            },
        )
        per_model["label"] = model_label
        per_model["deployment"] = deployment
        per_model["requestsTotal"] = int(per_model.get("requestsTotal", 0)) + 1
        per_model["webSearchRequestsTotal"] = int(per_model.get("webSearchRequestsTotal", 0)) + (
            1 if web_search_used else 0
        )
        per_model["lastUsedAt"] = now
        _merge_usage(per_model["usageTotals"], usage)

        _write_usage_summary(summary)


def _read_usage_summary() -> dict[str, Any]:
    if not CHAT_USAGE_SUMMARY_FILE.exists():
        return _default_usage_summary()

    try:
        payload = json.loads(CHAT_USAGE_SUMMARY_FILE.read_text(encoding="utf-8"))
    except Exception:
        return _default_usage_summary()

    if not isinstance(payload, dict):
        return _default_usage_summary()

    summary = _default_usage_summary()
    summary["updatedAt"] = payload.get("updatedAt")
    summary["requestsTotal"] = int(payload.get("requestsTotal", 0) or 0)
    summary["webSearchRequestsTotal"] = int(payload.get("webSearchRequestsTotal", 0) or 0)
    summary["usageTotals"] = _coerce_usage_dict(payload.get("usageTotals"))

    raw_models = payload.get("models")
    if isinstance(raw_models, dict):
        coerced_models: dict[str, Any] = {}
        for model_id, raw_item in raw_models.items():
            if not isinstance(raw_item, dict):
                continue
            coerced_models[str(model_id)] = {
                "modelId": str(raw_item.get("modelId") or model_id),
                "label": str(raw_item.get("label") or model_id),
                "deployment": str(raw_item.get("deployment") or raw_item.get("label") or model_id),
                "requestsTotal": int(raw_item.get("requestsTotal", 0) or 0),
                "webSearchRequestsTotal": int(raw_item.get("webSearchRequestsTotal", 0) or 0),
                "usageTotals": _coerce_usage_dict(raw_item.get("usageTotals")),
                "lastUsedAt": raw_item.get("lastUsedAt"),
            }
        summary["models"] = coerced_models

    return summary


def _write_usage_summary(summary: dict[str, Any]) -> None:
    CHAT_USAGE_SUMMARY_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = CHAT_USAGE_SUMMARY_FILE.with_suffix(f"{CHAT_USAGE_SUMMARY_FILE.suffix}.tmp")
    tmp_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(CHAT_USAGE_SUMMARY_FILE)


def _default_usage_summary() -> dict[str, Any]:
    return {
        "updatedAt": None,
        "requestsTotal": 0,
        "webSearchRequestsTotal": 0,
        "usageTotals": _empty_usage_totals(),
        "models": {},
    }


def _coerce_usage_dict(value: Any) -> dict[str, int]:
    if not isinstance(value, dict):
        return _empty_usage_totals()
    return {
        "inputTokens": int(value.get("inputTokens", 0) or 0),
        "outputTokens": int(value.get("outputTokens", 0) or 0),
        "totalTokens": int(value.get("totalTokens", 0) or 0),
        "reasoningTokens": int(value.get("reasoningTokens", 0) or 0),
    }


def _normalize_search_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_only = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return " ".join(ascii_only.lower().split())


def _string_value(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _float_value(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None