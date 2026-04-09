from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any
import chromadb
from openai import AzureOpenAI, OpenAI

from dotenv import load_dotenv
from system_prompt import SYSTEM_PROMPT


BASE_DIR = Path(__file__).resolve().parent
load_dotenv()

DEFAULT_RISK_DATA_FILE = BASE_DIR / "AI" / "Data" / "kd_z_nevarnost_enriched_verified.geojson"
CHAT_RISK_DATA_FILE = Path(os.getenv("CHAT_RISK_DATA_FILE", str(DEFAULT_RISK_DATA_FILE)))
CHAT_MAX_TOOL_ROUNDS = max(1, int(os.getenv("CHAT_MAX_TOOL_ROUNDS", "8")))
CHAT_MAX_OUTPUT_TOKENS = max(256, int(os.getenv("CHAT_MAX_OUTPUT_TOKENS", "4096")))
CHAT_INCOMPLETE_RESPONSE_RETRIES = max(0, int(os.getenv("CHAT_INCOMPLETE_RESPONSE_RETRIES", "1")))
CHAT_USAGE_SUMMARY_FILE = Path(
    os.getenv("CHAT_USAGE_SUMMARY_FILE", str(BASE_DIR / "logs" / "chat-usage-summary.json"))
)
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2025-03-01-preview")
ACTIVE_MODEL_ENV_PREFIX = os.getenv("CHAT_ACTIVE_MODEL_ENV_PREFIX", "CHAT_MODEL_MDML_GPT4O_MINI_001")

@dataclass(frozen=True)
class ModelSpec:
    id: str
    label: str
    env_prefix: str

MODEL_SPECS = (
    ModelSpec("mdml-gpt4-1-mini-001", "MDML-GPT4.1-Mini-001", "CHAT_MODEL_MDML_GPT4_1_MINI_001"),
    ModelSpec("mdml-gpt4o-mini-001", "MDML-GPT4o-Mini-001", "CHAT_MODEL_MDML_GPT4O_MINI_001"),
    ModelSpec("mdml-gpt4o-001", "MDML-GPT4o-001", "CHAT_MODEL_MDML_GPT4O_001"),
    ModelSpec("mdml-gpt5-mini-001", "MDML-GPT5-Mini-001", "CHAT_MODEL_MDML_GPT5_MINI_001"),
    ModelSpec("mdml-gpt5-001", "MDML-GPT5-001", "CHAT_MODEL_MDML_GPT5_001"),
    ModelSpec("mdml-gpt5-1-001", "MDML-GPT5.1-001", "CHAT_MODEL_MDML_GPT5_1_001"),
    ModelSpec("mdml-gpt5-2-001", "MDML-GPT5.2-001", "CHAT_MODEL_MDML_GPT5_2_001"),
    ModelSpec("mdml-gpt5-nano-001", "MDML-GPT5-Nano-001", "CHAT_MODEL_MDML_GPT5_NANO_001"),
    ModelSpec("gams-3-12b", "GaMS-3-12B-Instruct", "CHAT_MODEL_GAMS_3_12B"), #GaMS
)

EMBED_MODEL=os.getenv("MDML-TextEmbedding-003_DEPLOYMENT")
EMBED_API_KEY = os.getenv("MDML-TextEmbedding-003_API_KEY")
EMBED_BASE_URL = os.getenv("MDML-TextEmbedding-003_BASE_URL")
chroma_client = chromadb.PersistentClient(path="AI/Data/chroma_db")
collection = chroma_client.get_or_create_collection(name="kulturna_dediscina")

embed_client = (
    AzureOpenAI(
        api_key=EMBED_API_KEY,
        azure_endpoint=EMBED_BASE_URL,
        api_version="2024-02-01",
    )
    if EMBED_MODEL and EMBED_API_KEY and EMBED_BASE_URL
    else None
)

DATA_LOCK = Lock()
USAGE_SUMMARY_LOCK = Lock()
GDF_CACHE: dict[str, Any] = {"loaded": False, "path": None, "gdf": None}


class ChatServiceError(RuntimeError):           #interni error handler, codex naredil, pravi, da je bolje tako -\_o_/-
    def __init__(self, message: str, *, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def list_chat_models() -> list[dict[str, Any]]:         #izpise modele na voljo, v trenutni obliki vedno samo enkrat, koda ce bi zeleli uporabniku dati vec izbire (kot v testiranju)
    default_model_id = get_default_chat_model_id()
    return [_serialize_model(spec, default_model_id=default_model_id) for spec in MODEL_SPECS]


def get_default_chat_model_id() -> str:
    preferred_spec = _find_model_spec_by_env_prefix(ACTIVE_MODEL_ENV_PREFIX)
    if preferred_spec is not None and _resolve_model_config(preferred_spec)["available"]:
        return preferred_spec.id

    for spec in MODEL_SPECS:
        if _resolve_model_config(spec)["available"]:
            return spec.id

    return preferred_spec.id if preferred_spec is not None else MODEL_SPECS[0].id


def get_chat_usage_summary() -> dict[str, Any]:         # za /logs
    return _read_usage_summary()


def generate_chat_reply(*, messages: list[dict[str, str]], model_id: str | None = None, use_web_search: bool) -> dict[str, Any]:
    requested_model = (model_id or get_default_chat_model_id()).strip()
    selected_spec = _find_model_spec_by_id(requested_model)
    if selected_spec is None:
        raise ChatServiceError(f"Unknown chat model '{requested_model}'.", status_code=404)

    config = _resolve_model_config(selected_spec)
    if not config["available"]:
        raise ChatServiceError(
            f"Model '{config['label']}' is not fully configured. Missing: {', '.join(config['missingEnv'])}",
            status_code=503,
        )

    conversation_history = _sanitize_messages(messages)
    if not conversation_history:
        raise ChatServiceError("At least one chat message is required.", status_code=400)

    conversation: list[dict[str, Any]] = [{"role": "system", "content": SYSTEM_PROMPT}, *conversation_history]

    if _is_gams_model(requested_model):
        result = _generate_gams_reply(
            conversation=conversation,
            model_id=requested_model,
            config=config,
        )
        # samo tko za info, dejansko nepotrebno
        _record_usage_summary(
            model_id=config["id"],
            model_label=config["label"],
            deployment=config["deployment"],
            usage=result["usage"],
            web_search_used=False,
        )
        return result
    # nadaljuj normalno preko azurja ce ni GaMS

    client = _create_azure_client(
        api_key=config["apiKey"],
        azure_endpoint=config["azureEndpoint"],
    )

    tools = _build_tools(use_web_search=use_web_search)
    aggregated_usage = _empty_usage_totals()
    web_search_used = False
    incomplete_response_retries = 0

    
    response: Any = None
    for _ in range(CHAT_MAX_TOOL_ROUNDS + 1):
        response = client.responses.create(
            model=config["deployment"],
            input=conversation,
            tools=tools,
            max_output_tokens=CHAT_MAX_OUTPUT_TOKENS,
        )
        _merge_usage(aggregated_usage, _extract_usage_from_response(response))

        response_items = _response_output_items(response)
        tool_calls = [item for item in response_items if getattr(item, "type", "") == "function_call"]
        web_search_used = web_search_used or any(
            getattr(item, "type", "") == "web_search_call" for item in response_items
        )

        if not tool_calls:
            text, citations, response_status = _extract_text_and_citations_from_response(response)
            if response_status == "incomplete":
                if incomplete_response_retries < CHAT_INCOMPLETE_RESPONSE_RETRIES:
                    incomplete_response_retries += 1
                    continue
                raise ChatServiceError("The selected model returned an incomplete response.", status_code=502)
            if not text:
                raise ChatServiceError("The selected model returned an empty response.", status_code=502)

            _record_usage_summary(
                model_id=config["id"],
                model_label=config["label"],
                deployment=config["deployment"],
                usage=aggregated_usage,
                web_search_used=web_search_used
            )

            return {
                "model": {
                    "id": config["id"],
                    "label": config["label"],
                    "deployment": config["deployment"],
                },
                "content": text,
                "citations": citations,
                "webSearchUsed": web_search_used,
                "responseId": getattr(response, "id", None),
                "usage": aggregated_usage,
            }

        conversation.extend(_response_items_to_conversation_messages(response_items))
        for call in tool_calls:
            args = _parse_tool_arguments(getattr(call, "arguments", None) or "{}")
            try:
                result = dispatch_tool(call.name, args)
                output = json.dumps(result, ensure_ascii=False, default=str)
            except Exception as exc:
                output = json.dumps({"error": str(exc)}, ensure_ascii=False)

            conversation.append(
                {
                    "type": "function_call_output",
                    "call_id": call.call_id,
                    "output": output,
                }
            )
            print(conversation)


    raise ChatServiceError("Tool loop limit reached before the model finished.", status_code=502)


def run(
    user_message: str,
    *,
    messages: list[dict[str, Any]] | None = None,
    model: str | None = None,
    use_web_search: bool = False,
) -> dict[str, Any]:
    history = list(messages or [])
    history.append({"role": "user", "content": user_message})
    return generate_chat_reply(
        messages=history,
        model_id=model or get_default_chat_model_id(),
        use_web_search=use_web_search,
    )


def dispatch_tool(name: str, args: dict[str, Any]) -> Any:
    if name == "top_k_endangered_in_region":
        return top_k_endangered_in_region(**args)
    if name == "top_k_endangered_in_municipality":
        return top_k_endangered_in_municipality(**args)
    if name == "get_info_by_eids":
        return get_info_by_eids(**args)
    if name == "search_heritage_records":
        return search_heritage_records(**args)
    if name == "top_k_endangered_in_country":
        return top_k_endangered_in_country(**args)
    raise ValueError(f"Unknown tool: {  name}")


def top_k_endangered_in_region(regija: str, endangerment: str, k: int = -1) -> list[str]:
    if endangerment not in {'pozar_ocena_popravljena', 'poplave_ocena_popravljena', 'potres_ocena_popravljena', 'plazovi_ocena_popravljena', 'skupaj_nevarnost'}:
        raise ValueError("Unsupported endangerment.")

    gdf = _load_gdf()
    subset = gdf[gdf['regija'] == regija]
    if subset.empty:
        return []

    scores = subset[endangerment].fillna(0)
    if k == -1:
        max_score = scores.max()
        ranked = subset[scores == max_score]
    else:
        ranked = subset.nlargest(max(1, int(k)), endangerment)

    return ranked["EID"].astype(str).tolist()

def top_k_endangered_in_municipality(obcina: str, endangerment: str, k: int = -1) -> list[str]:
    if endangerment not in {'pozar_ocena_popravljena', 'poplave_ocena_popravljena','potres_ocena_popravljena', 'plazovi_ocena_popravljena', 'skupaj_nevarnost'}:
        raise ValueError("Unsupported endangerment.")

    gdf = _load_gdf()
    subset = gdf[gdf['OBCINA'] == obcina]
    if subset.empty:
        return []

    scores = subset[endangerment].fillna(0)
    if k == -1:
        max_score = scores.max()
        ranked = subset[scores == max_score]
    else:
        ranked = subset.nlargest(max(1, int(k)), endangerment)

    return ranked["EID"].astype(str).tolist()

def top_k_endangered_in_country(endangerment: str, k: int = -1):
    if endangerment not in {'pozar_ocena_popravljena', 'poplave_ocena_popravljena','potres_ocena_popravljena', 'plazovi_ocena_popravljena', 'skupaj_nevarnost'}:
        raise ValueError("Unsupported endangerment.")

    gdf = _load_gdf()
    
    scores = gdf[endangerment].fillna(0)
    if k == -1:
        max_score = scores.max()
        ranked = gdf[scores == max_score]
    else:
        ranked = gdf.nlargest(max(1, int(k)), endangerment)

    return ranked["EID"].astype(str).tolist()

def get_info_by_eids(eids: list[str], columns: list[str] | None = None) -> list[dict]:
    gdf = _load_gdf()
    subset = gdf.drop(columns="geometry", errors="ignore")
    subset = gdf[gdf["EID"].isin(eids)]

    if subset.empty:
        raise ValueError(f"No site was found for EIDs {eids}.")

    if columns:
        missing = [column for column in columns if column not in gdf.columns]
        if missing:
            raise ValueError(f"Unknown columns: {', '.join(missing)}")
        subset = subset[columns]

    return subset.to_dict(orient="records")

def search_heritage_records(query: str, k: int = 5):
    if embed_client is None or not EMBED_MODEL:
        raise ChatServiceError(
            "Semantic search is not configured. Missing embedding model credentials.",
            status_code=503,
        )

    query_emb = embed_client.embeddings.create(
        model=EMBED_MODEL,
        input=[query]
    ).data[0].embedding

    where = {}
    #lahko dodamo filter po npr obcini, ce to zelimo ze na tem nivoju

    query_args = {
        "query_embeddings": [query_emb],
        "n_results": k,
        "include":["documents", "metadatas"]
        }
    
    if where:
        query_args["where"] = where
    
    result = collection.query(**query_args)
    #results->dict z moznimi: "ids", "metadatas", "documents"(text ki je bil embeddan)
    print(result)
    return result


def _build_tools(*, use_web_search: bool) -> list[dict[str, Any]]:
    _ = use_web_search
    tools = [
        {
            "type":"function",
            "name":"search_heritage_records",
            "description":"""Searches the heritage-record vector database using semantic similarity. Use this tool when the user is asking about monuments, heritage objects,
                        materials, descriptions, categories, or related attributes that may exist in the indexed dataset. Returns the most relevant matching records,
                        including their EID, stored metadata, and embedded source text. If the results are weak or irrelevant, say that clearly instead of treating them as authoritative""",
            "parameters":{
                "type":"object",
                "properties":{
                    "query":{
                        "type":"string",
                        "description":"users querry to do semantic search on. Usually something that is semantically similar to what you are looking for like the users prompt itself"
                    },
                    "k":{
                        "type":"integer",
                        "description":"how many results from the database you want, default is 5"
                    }
                },
                "required":['query'],
                "additionalProperties":False
            }
        },
        {
            "type": "function",
            "name": "top_k_endangered_in_country",
            "description": "Returns a list of the top endangered objects in the whole country for one endangerment type. You can also use the endangerment for a combined danger. Use this when the user asks about dangers for the whole country",
            "parameters": {
                    "type": "object",
                    "properties": {
                        "endangerment": {
                            "type": "string",
                            "enum": ['pozar_ocena_popravljena', 'poplave_ocena_popravljena','potres_ocena_popravljena', 'plazovi_ocena_popravljena', 'skupaj_nevarnost'],
                        },
                        "k": {
                            "type": "integer",
                            "description": "How many results to return. If omitted, returns all with max score.",
                        },
                    },
                    "required": ["endangerment"],
                    "additionalProperties": False,
                },
        },
        {
            "type": "function",
            "name": "top_k_endangered_in_region",
            "description": "Returns a list of the top endangered objects in a region for one endangerment type. You can also use the endangerment for a combined danger. You can also use this to get all heritage sites in a region by entering a large k",
            "parameters": {
                    "type": "object",
                    "properties": {
                        "regija": {
                            "type": "string",
                            "description": "Region name, regions are like 'Posavska'",
                            "enum" : ['Osrednjeslovenska', 'Savinjska', 'Gorenjska', 'Podravska', 'Jugovzhodna Slovenija', 'Goriška', 'Obalno-kraška', 
                                      'Pomurska', 'Posavska', 'Primorsko-notranjska', 'Koroška', 'Zasavska']
                        },
                        "endangerment": {
                            "type": "string",
                            "enum": ['pozar_ocena_popravljena', 'poplave_ocena_popravljena','potres_ocena_popravljena', 'plazovi_ocena_popravljena', 'skupaj_nevarnost'],
                        },
                        "k": {
                            "type": "integer",
                            "description": "How many results to return. If omitted, returns all with max score.",
                        },
                    },
                    "required": ["regija", "endangerment"],
                    "additionalProperties": False,
                },
        },
        {
            "type": "function",
            "name": "top_k_endangered_in_municipality",
            "description": "Returns a list of the top endangered objects in a municipality for one endangerment type. You can also use the endangerment for a combined danger. You can also use this to get all heritage sites in a municipality by entering k=-1 and any endangerment type",
            "parameters": {
                    "type": "object",
                    "properties": {
                        "obcina": {
                            "type": "string",
                            "description": "Slovenian manuicipality name, municipalities are all caps such as 'LJUBLJANA'",
                        },
                        "endangerment": {
                            "type": "string",
                            "enum": ['pozar_ocena_popravljena', 'poplave_ocena_popravljena','potres_ocena_popravljena', 'plazovi_ocena_popravljena', 'skupaj_nevarnost'],
                        },
                        "k": {
                            "type": "integer",
                            "description": "How many results to return. If omitted, returns all with max score.",
                        },
                    },
                    "required": ["obcina", "endangerment"],
                    "additionalProperties": False,
                },
        },
        {
            "type": "function",
            "name": "get_info_by_eids",
            "description": "Returns information about multiple or one specific cultural heritage objects by their EID. Use this when you recieve EIDs from another tool.",
            "parameters": {
                    "type": "object",
                    "properties": {
                        "eids": {
                            "type": "array",
                            "items": {"type" : "string"}
                            },
                        "columns": {
                            "type": "array",
                            "items": {
                                "type": "string",
                                "enum": ["ESD", "EID", "IME", "SINONIMI", "OPIS", "ZVRST", "TIP", "GESLA", "DATACIJA", "LOKACIJAOPIS", "OBCINA", "ZAVOD", "SPOMENIK", "poplave", "pozar", "plazovi", "regija", "UE_UIME", "potres", "prevladujoci_material",
                                          'pozar_ocena_popravljena', 'poplave_ocena_popravljena', 'potres_ocena_popravljena', 'plazovi_ocena_popravljena', "danger_revision_reasoning", "skupaj_nevarnost"]
                                },
                            "description": "Columns to show"
                        },
                    },
                    "required": ["eids"],
                    "additionalProperties": False,
                },
        },
        {
            "type": "web_search",
            "user_location": {
                "type": "approximate",
                "country": "SI"
            }
        }
    ]

    

    return tools


def _load_gdf() -> Any:
    with DATA_LOCK:
        if GDF_CACHE["loaded"] and GDF_CACHE["path"] == str(CHAT_RISK_DATA_FILE):
            return GDF_CACHE["gdf"]

        if not CHAT_RISK_DATA_FILE.exists():
            raise FileNotFoundError(f"Risk dataset not found at {CHAT_RISK_DATA_FILE}")

        try:
            import geopandas as gpd
        except ModuleNotFoundError as exc:
            raise ChatServiceError(
                "geopandas is not installed. Install backend requirements first.",
                status_code=503,
            ) from exc

        gdf = gpd.read_file(CHAT_RISK_DATA_FILE)
        GDF_CACHE.update(
            {
                "loaded": True,
                "path": str(CHAT_RISK_DATA_FILE),
                "gdf": gdf,
            }
        )
        return gdf


def _sanitize_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Makes sure that all messages in history are in one of the following formats:
    {"role": "user", "content": "..."}
    {"role": "assistant", "content": "..."}
    {
        "role": "tool",
        "tool_call_id": "...",
        "content": "..."
    }
    """

    sanitized: list[dict[str, Any]] = []
    for message in messages:
        if not isinstance(message, dict):
            continue
        role = message.get("role")
        if role in {"user", "assistant"} and "content" in message:
            sanitized.append({"role": role, "content": message["content"]})
        elif message.get("type") == "function_call_output" and "call_id" in message and "output" in message:
            sanitized.append(
                {
                    "type": "function_call_output",
                    "call_id": message["call_id"],
                    "output": message["output"],
                }
            )
        elif role == "tool" and "tool_call_id" in message and "content" in message:
            sanitized.append(
                {
                    "type": "function_call_output",
                    "call_id": message["tool_call_id"],
                    "output": message["content"],
                }
            )
    return sanitized


def _parse_tool_arguments(raw: str) -> dict[str, Any]:
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON arguments: {exc}") from exc
    if not isinstance(parsed, dict):
        raise ValueError("Tool arguments must be a JSON object.")
    return parsed


def _response_output_items(response: Any) -> list[Any]:
    output = getattr(response, "output", None)
    if output is None:
        return []
    if isinstance(output, list):
        return output
    return list(output)


def _response_items_to_conversation_messages(items: list[Any]) -> list[dict[str, Any]]:
    conversation_messages: list[dict[str, Any]] = []
    for item in items:
        item_type = getattr(item, "type", "")
        if item_type == "message":
            conversation_messages.append(item.model_dump(exclude_unset=True))
        elif item_type == "function_call":
            conversation_messages.append(
                {
                    "type": "function_call",
                    "call_id": item.call_id,
                    "name": item.name,
                    "arguments": item.arguments,
                }
            )
    return conversation_messages


def _extract_text_and_citations_from_message(message: Any) -> tuple[str, list[dict[str, Any]]]:
    text_parts: list[str] = []
    citations: list[dict[str, Any]] = []

    for content_item in getattr(message, "content", []) or []:
        if getattr(content_item, "type", "") != "output_text":
            continue
        text_part = str(getattr(content_item, "text", "") or "")
        if text_part:
            text_parts.append(text_part)

        annotations = getattr(content_item, "annotations", []) or []
        for annotation in annotations:
            url = getattr(annotation, "url", None) or getattr(annotation, "source", None)
            if not url:
                continue
            citations.append(
                {
                    "title": getattr(annotation, "title", None),
                    "url": url,
                }
            )

    unique_citations: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    for citation in citations:
        url = str(citation.get("url") or "").strip()
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        unique_citations.append(citation)

    return "".join(text_parts).strip(), unique_citations


def _extract_text_and_citations_from_response(response: Any) -> tuple[str, list[dict[str, Any]], str]:
    assistant_messages = [
        item
        for item in _response_output_items(response)
        if getattr(item, "type", "") == "message" and str(getattr(item, "role", "assistant") or "assistant") == "assistant"
    ]

    for message in reversed(assistant_messages):
        status = str(getattr(message, "status", "") or "")
        text, citations = _extract_text_and_citations_from_message(message)
        if status == "incomplete":
            return text, citations, "incomplete"
        if text:
            return text, citations, status or "completed"

    text = str(getattr(response, "output_text", "") or "").strip()
    return text, [], "completed" if text else ""


def _serialize_model(spec: ModelSpec, *, default_model_id: str) -> dict[str, Any]:
    config = _resolve_model_config(spec)
    return {
        "id": config["id"],
        "label": config["label"],
        "deployment": config["deployment"],
        "available": config["available"],
        "missingEnv": config["missingEnv"],
        "supportsWebSearch": not _is_gams_model(spec.id),
        "isDefault": config["id"] == default_model_id,
    }


def _find_model_spec_by_id(model_id: str) -> ModelSpec | None:
    return next((spec for spec in MODEL_SPECS if spec.id == model_id), None)


def _find_model_spec_by_env_prefix(env_prefix: str) -> ModelSpec | None:
    return next((spec for spec in MODEL_SPECS if spec.env_prefix == env_prefix), None)


def _resolve_model_config(spec: ModelSpec) -> dict[str, Any]:
    # GaMS — lokalni vLLM, ne potrebuje Azure konfiga
    if spec.id.startswith("gams-"):
        base_url = os.getenv("GAMS_BASE_URL", "http://localhost:65535/v1")
        return {
            "id": spec.id,
            "label": spec.label,
            "deployment": os.getenv("GAMS_MODEL_NAME", "GaMS3-12B-Instruct"),
            "apiKey": "EMPTY",
            "azureEndpoint": base_url,
            "available": True,   # privzeto dostopen, napaka se pojavi pri klicu
            "missingEnv": [],
        }

    deployment = _read_env(f"{spec.env_prefix}_DEPLOYMENT")
    api_key = (
        _read_env(f"{spec.env_prefix}_API_KEY")
        or _read_env(f"{spec.env_prefix}_TOKEN")
        or _read_env("AZURE_OPENAI_API_KEY")
        or _read_env("AZURE_OPENAI_TOKEN")
    )
    azure_endpoint = _resolve_azure_endpoint(spec.env_prefix)

    missing_env: list[str] = []
    if not deployment:
        missing_env.append(f"{spec.env_prefix}_DEPLOYMENT")
    if not api_key:
        missing_env.append(f"{spec.env_prefix}_API_KEY or AZURE_OPENAI_API_KEY")
    if not azure_endpoint:
        missing_env.append(f"{spec.env_prefix}_BASE_URL or AZURE_OPENAI_BASE_URL")

    return {
        "id": spec.id,
        "label": deployment or spec.label,
        "deployment": deployment,
        "apiKey": api_key,
        "azureEndpoint": azure_endpoint,
        "available": not missing_env,
        "missingEnv": missing_env,
    }


def _resolve_azure_endpoint(env_prefix: str) -> str | None:
    raw = (
        _read_env(f"{env_prefix}_BASE_URL")
        or _read_env(f"{env_prefix}_ENDPOINT")
        or _read_env("AZURE_OPENAI_BASE_URL")
        or _read_env("AZURE_OPENAI_ENDPOINT")
    )
    if not raw:
        return None

    endpoint = raw.rstrip("/")
    for suffix in ("/openai/v1", "/openai"):
        if endpoint.endswith(suffix):
            endpoint = endpoint[: -len(suffix)]

    #374-477 lahko tudi odstranimo, mal popravi, ce je api url narobe formatiran. Ce je pravilno(za kar poskrbimo mi pac), bi lahko vrnili tudi raw
    return endpoint


def _read_env(name: str) -> str | None:
    value = os.getenv(name)
    if value is None:
        return None
    stripped = value.strip()
    #odstrani whitespace, vrez problema bi lahko bil os.getnenv() povsod
    return stripped or None


def _create_azure_client(*, api_key: str, azure_endpoint: str) -> Any:
    try:
        from openai import AzureOpenAI
    except ModuleNotFoundError as exc:
        raise ChatServiceError(
            "The openai package is not installed. Install backend requirements first.",
            status_code=503,
        ) from exc

    return AzureOpenAI(
        api_key=api_key,
        azure_endpoint=azure_endpoint,
        api_version=AZURE_OPENAI_API_VERSION,
    )


def _extract_usage_from_response(response: Any) -> dict[str, int]:
    usage = getattr(response, "usage", None)
    if usage is None:
        return _empty_usage_totals()

    input_tokens = int(getattr(usage, "input_tokens", getattr(usage, "prompt_tokens", 0)) or 0)
    output_tokens = int(getattr(usage, "output_tokens", getattr(usage, "completion_tokens", 0)) or 0)
    total_tokens = int(getattr(usage, "total_tokens", input_tokens + output_tokens) or 0)
    output_tokens_details = getattr(usage, "output_tokens_details", getattr(usage, "completion_tokens_details", None))
    reasoning_tokens = int(getattr(output_tokens_details, "reasoning_tokens", 0) or 0)

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
        models: dict[str, Any] = {}
        for model_id, item in raw_models.items():
            if not isinstance(item, dict):
                continue
            models[str(model_id)] = {
                "modelId": str(item.get("modelId") or model_id),
                "label": str(item.get("label") or model_id),
                "deployment": str(item.get("deployment") or item.get("label") or model_id),
                "requestsTotal": int(item.get("requestsTotal", 0) or 0),
                "webSearchRequestsTotal": int(item.get("webSearchRequestsTotal", 0) or 0),
                "usageTotals": _coerce_usage_dict(item.get("usageTotals")),
                "lastUsedAt": item.get("lastUsedAt"),
            }
        summary["models"] = models

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


def _json_safe(value: Any) -> Any:
    try:
        import pandas as pd
    except ModuleNotFoundError:
        pd = None

    if pd is not None and pd.isna(value):
        return None
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if hasattr(value, "item") and callable(value.item):
        try:
            return _json_safe(value.item())
        except Exception:
            return str(value)
    return value

#
# GAMS
#
def _is_gams_model(model_id: str) -> bool:
    return model_id.startswith("gams-")

def _create_gams_client() -> OpenAI:
    base_url = os.getenv("GAMS_BASE_URL", "http://localhost:65535/v1")
    return OpenAI(
        base_url=base_url,
        api_key="EMPTY",  # vLLM ne potrebuje pravega ključa
    )

def _generate_gams_reply(
    *,
    conversation: list[dict],
    model_id: str,
    config: dict,
) -> dict:
    """Koda pot za GaMS prek vLLM — brez tool callinga."""
    client = _create_gams_client()
    vllm_model_name = os.getenv("GAMS_MODEL_NAME", "GaMS3-12B-Instruct")

    messages: list[dict[str, Any]] = []
    for msg in conversation:
        role = msg.get("role") or ""
        content = msg.get("content") or ""
        if role in ("user", "assistant", "system") and content:
            messages.append({"role": role, "content": content})

    try:
        response = client.chat.completions.create(
            model=vllm_model_name,
            messages=messages,
            temperature=0.6,
            top_p=0.95,
            max_tokens=CHAT_MAX_OUTPUT_TOKENS,
        )
        print(response)
    except Exception as exc:
        raise ChatServiceError(
            f"GaMS strežnik ni dosegljiv: {exc}. "
            "Preverite da teče vLLM na HPC in da je SSH tunel odprt.",
            status_code=503,
        ) from exc

    text = response.choices[0].message.content or ""
    if not text:
        raise ChatServiceError("GaMS je vrnil prazen odgovor.", status_code=502)

    usage = response.usage
    aggregated_usage = {
        "inputTokens": getattr(usage, "prompt_tokens", 0),
        "outputTokens": getattr(usage, "completion_tokens", 0),
        "totalTokens": getattr(usage, "total_tokens", 0),
        "reasoningTokens": 0,
    }

    return {
        "model": {
            "id": model_id,
            "label": config["label"],
            "deployment": vllm_model_name,
        },
        "content": text,
        "citations": [],
        "webSearchUsed": False,
        "responseId": response.id,
        "usage": aggregated_usage,
    }

if __name__ == "__main__":
    result = run(
        "Kateri spomeniki v Komendi so najbolj ogrozeni zaradi poplav?",
        use_web_search=True,
    )
    print(result["content"])
