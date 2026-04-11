import os
from hashlib import sha1
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from threading import Thread
from time import perf_counter
from typing import Any, Dict, List, Literal, Optional

from fastapi.concurrency import run_in_threadpool
from fastapi import FastAPI, HTTPException, Path, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from chat_service import (
    ChatServiceError,
    generate_chat_reply,
    get_chat_usage_summary,
    get_default_chat_model_id,
    list_chat_models,
)
from observability import get_metrics_snapshot, log_event, record_request, record_search_latency
from overlays import list_overlay_catalog, list_overlay_grid
from overlays.service import get_overlay_dataset
from rnpd_service import (
    get_dataset,
    get_dataset_status,
    get_heritage_site_details,
    list_heritage_sites,
    read_bbox,
    read_refresh_flag,
)

PORT = int(os.getenv("PORT", "8787"))
CORS_ORIGIN = os.getenv("CORS_ORIGIN", "*")
UNBOUNDED_LIST_LIMIT = int(os.getenv("API_UNBOUNDED_LIST_LIMIT", "2500"))
CACHE_CONTROL_DEFAULT = os.getenv("API_CACHE_CONTROL_DEFAULT", "no-store")
CACHE_CONTROL_HEALTH = os.getenv("API_CACHE_CONTROL_HEALTH", "no-store")
CACHE_CONTROL_METRICS = os.getenv("API_CACHE_CONTROL_METRICS", "no-store")
CACHE_CONTROL_SITES = os.getenv("API_CACHE_CONTROL_SITES", "public, max-age=60")
CACHE_CONTROL_SITE_DETAIL = os.getenv("API_CACHE_CONTROL_SITE_DETAIL", "public, max-age=300")
CACHE_CONTROL_OVERLAYS = os.getenv("API_CACHE_CONTROL_OVERLAYS", "public, max-age=30")
if UNBOUNDED_LIST_LIMIT < 1:
    UNBOUNDED_LIST_LIMIT = 2500

EXAMPLE_BBOX_MEDVODE = "14.37,46.12,14.50,46.17"
EXAMPLE_SITE_ID_SPODNJE_PIRNICE = "1-02508"


class HealthResponse(BaseModel):
    status: str = Field(description="Service status string.", examples=["ok"])
    service: str = Field(description="Internal service identifier.", examples=["heritage-map-backend"])
    timestamp: str = Field(
        description="Server timestamp in UTC (ISO-8601).",
        examples=["2026-03-07T13:20:15.314000+00:00"],
    )
    datasetReady: bool = Field(
        description="True when dataset is loaded and ready for heritage queries.",
        examples=[True, False],
    )
    datasetLoading: bool = Field(
        description="True while server is actively loading dataset source data.",
        examples=[False, True],
    )
    datasetLastError: Optional[str] = Field(
        default=None,
        description="Last dataset load error, if any.",
        examples=[None, "Unable to load RNPD source from local files."],
    )
    datasetPhase: str = Field(
        description="Current dataset lifecycle phase.",
        examples=["initializing", "source_loaded", "records_extracted", "records_normalized", "ready", "error"],
    )
    datasetProgressPct: int = Field(description="Estimated startup progress percentage.", examples=[0, 35, 100])
    datasetLoadedAt: Optional[str] = Field(
        default=None,
        description="UTC timestamp when dataset was last successfully loaded.",
        examples=["2026-03-07T13:19:58.314000+00:00"],
    )
    datasetLastLoadDurationMs: Optional[float] = Field(
        default=None,
        description="Duration of the last successful dataset load in milliseconds.",
        examples=[1842.33],
    )
    datasetSourceCount: int = Field(
        description="Number of source records in the currently loaded dataset.",
        examples=[31083],
    )


class HeritageSiteSummary(BaseModel):
    id: str = Field(description="Stable site ID (typically EID from RNPD).", examples=["1-02508"])
    registryId: Optional[str] = Field(
        default=None,
        description="RNPD registry identifier, if available.",
        examples=["1-02508"],
    )
    name: str = Field(
        description="Site display name.",
        examples=["Spodnje Pirnice - Cerkev Marijinega vnebovzetja"],
    )
    lat: float = Field(description="Latitude in WGS84.", examples=[46.14211])
    lng: float = Field(description="Longitude in WGS84.", examples=[14.43172])
    type: Optional[str] = Field(
        default=None,
        description="Heritage type/category as available in the source dataset.",
        examples=["sakralna stavbna dediščina"],
    )
    protectionStatus: Optional[str] = Field(
        default=None,
        description="Legal/protection status in source metadata.",
        examples=["spomenik lokalnega pomena"],
    )
    municipality: Optional[str] = Field(
        default=None,
        description="Municipality or nearest locality field from source data.",
        examples=["MEDVODE"],
    )
    description: Optional[str] = Field(
        default=None,
        description="Short textual description if available.",
        examples=["Baročna cerkev v jedru Spodnjih Pirnic."],
    )
    elevationM: Optional[float] = Field(
        default=None,
        description="Site elevation in meters when available from enriched spatial data.",
        examples=[337.41],
    )
    isCluster: Optional[bool] = Field(
        default=None,
        description="True when this item is a synthetic cluster marker (not a single site).",
        examples=[False, True],
    )
    clusterCount: Optional[int] = Field(
        default=None,
        description="Number of sites represented by cluster marker.",
        examples=[18],
    )


class HeritageSiteField(BaseModel):
    label: str = Field(description="Humanized source field name.", examples=["Datacija"])
    value: str = Field(description="Stringified source value.", examples=["17. stol."])


class HeritageSiteDetail(HeritageSiteSummary):
    detailFields: List[HeritageSiteField] = Field(
        description="Additional metadata fields extracted from source, excluding primary summary fields."
    )
    sourceUrl: str = Field(
        description="Configured source URL reference (informational).",
        examples=[
            "https://podatki.gov.si/dataset/6b5bf6d9-d3bd-4231-95ac-3863b6d70c56/resource/1b0d4a0b-45d4-484b-a760-d0ed14426230/download/rnpd.json"
        ],
    )


class HeritageSiteListResponse(BaseModel):
    items: List[HeritageSiteSummary] = Field(
        description="List of markers/sites for requested map/search context (may include cluster points)."
    )
    total: int = Field(description="Number of matching real sites before limit/clustering.", examples=[236])
    sourceCount: int = Field(description="Total number of raw records loaded from source dataset.", examples=[31083])
    sourceUrl: str = Field(description="Configured source URL reference.", examples=["https://podatki.gov.si/.../rnpd.json"])


class ErrorResponse(BaseModel):
    detail: str = Field(description="Human-readable error detail.", examples=["Site not found"])


class ChatCitation(BaseModel):
    title: str = Field(description="Human-readable source title.", examples=["Recent flood report"])
    url: str = Field(description="Source URL.", examples=["https://example.com/report"])


class ChatModelDescriptor(BaseModel):
    id: str = Field(description="Stable frontend-facing model identifier.", examples=["mdml-gpt5-001"])
    label: str = Field(description="Display label for the configured model.", examples=["MDML-GPT5-001"])
    deployment: str = Field(description="Azure OpenAI deployment name.", examples=["MDML-GPT5-001"])
    available: bool = Field(description="True when this model is fully configured from environment variables.")
    supportsWebSearch: bool = Field(description="True when the frontend may offer the web-search toggle.")
    isDefault: bool = Field(description="True for the backend-selected default model.")
    missingEnv: List[str] = Field(description="Missing environment variable names when model configuration is incomplete.")


class ChatModelsResponse(BaseModel):
    items: List[ChatModelDescriptor] = Field(description="Selectable chat models exposed to the frontend.")
    defaultModelId: str = Field(description="Preferred default model identifier.", examples=["mdml-gpt5-001"])


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"] = Field(description="Chat message role.", examples=["user", "assistant"])
    content: str = Field(description="Plain text message content.", examples=["Summarize fire risks near Ptuj."])


class ChatRequest(BaseModel):
    messages: List[ChatMessage] = Field(description="Conversation history in chronological order.")
    modelId: str = Field(description="Selected frontend model identifier.", examples=["mdml-gpt5-001"])
    useWebSearch: bool = Field(
        default=False,
        description="Enable Azure web-search tool (`web_search_preview`) for this request.",
    )


class ChatResponse(BaseModel):
    model: ChatModelDescriptor = Field(description="Metadata for the model that produced this response.")
    message: ChatMessage = Field(description="Assistant reply.")
    citations: List[ChatCitation] = Field(description="URL citations returned by the model.")
    webSearchUsed: bool = Field(description="True when the model invoked the Azure web-search tool.")
    responseId: str = Field(description="Provider response identifier.", examples=["resp_123"])


class ChatUsageTotals(BaseModel):
    inputTokens: int = Field(description="Accumulated input tokens.")
    outputTokens: int = Field(description="Accumulated output tokens.")
    totalTokens: int = Field(description="Accumulated total tokens.")
    reasoningTokens: int = Field(description="Accumulated reasoning tokens when available.")


class ChatUsageModelSummary(BaseModel):
    modelId: str = Field(description="Stable frontend-facing model identifier.")
    label: str = Field(description="Human-readable model label.")
    deployment: str = Field(description="Azure deployment name.")
    requestsTotal: int = Field(description="Total completed chat requests for this model.")
    webSearchRequestsTotal: int = Field(description="Number of requests where web search was enabled and used.")
    usageTotals: ChatUsageTotals = Field(description="Token totals accumulated for this model.")
    lastUsedAt: Optional[str] = Field(default=None, description="Last successful use timestamp in UTC ISO-8601 format.")


class ChatUsageSummaryResponse(BaseModel):
    updatedAt: Optional[str] = Field(default=None, description="Last summary update timestamp in UTC ISO-8601 format.")
    requestsTotal: int = Field(description="Total completed chat requests across all models.")
    webSearchRequestsTotal: int = Field(description="Total completed requests that used web search.")
    usageTotals: ChatUsageTotals = Field(description="Global token totals across all models.")
    models: List[ChatUsageModelSummary] = Field(description="Per-model usage totals currently stored on disk.")


class OverlayCatalogItem(BaseModel):
    kind: str = Field(description="Overlay key identifier.", examples=["fire", "flood", "air", "landslide"])
    label: str = Field(description="Display label for overlay toggle.", examples=["Fire danger"])
    description: str = Field(
        description="Short human-readable explanation of the overlay data source.",
        examples=["Fire danger polygons from the official hazard map."],
    )


class OverlayCatalogResponse(BaseModel):
    items: List[OverlayCatalogItem] = Field(description="Available overlay options.")


class OverlayScaleStep(BaseModel):
    level: int = Field(description="Discrete display level from 1 (least) to 4 (most).", examples=[1, 4])
    label: str = Field(description="Label for this level.", examples=["Low", "Extreme"])
    normalized: float = Field(description="Normalized position in [0,1].", examples=[0.0, 1.0])


class OverlayScale(BaseModel):
    direction: str = Field(description="Scale direction for UI rendering.", examples=["low-to-high"])
    leastLabel: str = Field(description="Label shown at low end of scale.", examples=["Least endangered"])
    mostLabel: str = Field(description="Label shown at high end of scale.", examples=["Most endangered"])
    steps: List[OverlayScaleStep] = Field(description="Scale stops used by UI.")


class OverlayCell(BaseModel):
    id: str = Field(description="Stable grid cell identifier for current viewport.", examples=["cell:14:27"])
    score: float = Field(description="Aggregated raw score for this cell.", examples=[2.74])
    normalized: float = Field(description="Score normalized to [0,1] for consistent coloring.", examples=[0.58])
    level: int = Field(description="Discrete danger level from 1..4.", examples=[3])
    sampleCount: int = Field(description="Number of source samples merged into this cell.", examples=[23])
    bounds: List[float] = Field(
        description="Cell bounds in format [minLng,minLat,maxLng,maxLat].",
        min_length=4,
        max_length=4,
        examples=[[14.1225, 46.0125, 14.1450, 46.0350]],
    )


class OverlayArea(BaseModel):
    id: str = Field(description="Stable area identifier.", examples=["fire:1028:0"])
    score: float = Field(description="Raw hazard score for this area.", examples=[3.0])
    normalized: float = Field(description="Score normalized to [0,1] for consistent coloring.", examples=[0.66])
    level: int = Field(description="Discrete danger level from 1..4.", examples=[3])
    bounds: List[float] = Field(
        description="Area bounds in format [minLng,minLat,maxLng,maxLat].",
        min_length=4,
        max_length=4,
        examples=[[14.1225, 46.0125, 14.1450, 46.0350]],
    )
    ring: List[List[float]] = Field(
        description="Polygon outer ring in [lng,lat] coordinate pairs.",
        examples=[[[14.12, 46.01], [14.14, 46.01], [14.14, 46.03], [14.12, 46.03], [14.12, 46.01]]],
    )


class OverlayLine(BaseModel):
    id: str = Field(description="Stable line identifier.", examples=["river:1028"])
    bounds: List[float] = Field(
        description="Line bounds in format [minLng,minLat,maxLng,maxLat].",
        min_length=4,
        max_length=4,
        examples=[[14.1225, 46.0125, 14.245, 46.088]],
    )
    paths: List[List[List[float]]] = Field(
        description="One or more line paths in [lng,lat] coordinate pairs.",
        examples=[[[[14.12, 46.01], [14.14, 46.02], [14.16, 46.03]]]],
    )


class OverlayGridResponse(BaseModel):
    kind: str = Field(description="Overlay key identifier.", examples=["fire"])
    label: str = Field(description="Display label for active overlay.", examples=["Fire danger"])
    description: str = Field(description="Overlay description.")
    scale: OverlayScale = Field(description="Legend/scale metadata.")
    areas: List[OverlayArea] = Field(description="Viewport-optimized hazard polygons for area overlays.")
    cells: List[OverlayCell] = Field(description="Viewport-optimized grid cells for point-based overlays.")
    lines: List[OverlayLine] = Field(description="Viewport-optimized polyline features for line-based overlays.")
    sampleCount: int = Field(description="Number of rendered source items represented in current viewport.", examples=[1420])
    totalAvailableSamples: int = Field(description="Total source items available for this overlay.", examples=[31086])
    gridCellSizeDeg: float = Field(description="Final aggregation cell size in degrees (0 for area overlays).", examples=[0.0214, 0.0])
    generatedAt: float = Field(description="UTC timestamp (ms since epoch) of overlay cache load.", examples=[1762230400123.0])


@asynccontextmanager
async def lifespan(_: FastAPI):
    def warm_overlay_dataset() -> None:
        try:
            get_overlay_dataset(refresh=False)
        except Exception as exc:
            # Keep API process alive; first overlay request will report any load issue.
            print(f"[startup] overlay warmup failed: {exc}")

    try:
        get_dataset(refresh=False)
    except Exception as exc:
        # Keep API process alive; request handlers will still surface loading errors.
        print(f"[startup] dataset warmup failed: {exc}")
    Thread(target=warm_overlay_dataset, daemon=True).start()
    yield


app = FastAPI(
    lifespan=lifespan,
    title="Heritage Map Backend API",
    summary="RNPD-powered API for map markers, clustering, search, and site details.",
    description=(
        "This API powers the Slovenian cultural heritage map.\n\n"
        "## What this API does\n"
        "- Loads RNPD source data (local-first, optional remote fallback)\n"
        "- Normalizes heterogeneous records to a stable response shape\n"
        "- Supports viewport filtering (`bbox`), full-text search (`search`), and marker clustering (`zoom`)\n"
        "- Provides per-site detail endpoint with additional metadata fields\n\n"
        "## Notes\n"
        "- `bbox` format: `minLng,minLat,maxLng,maxLat`\n"
        "- `zoom` helps backend decide when to return clusters vs single-site markers\n"
        "- `refresh=1` bypasses in-memory cache and reloads source data\n"
    ),
    version="1.0.0",
    contact={"name": "Arnes Hackathon Team"},
    license_info={"name": "Internal / Hackathon Use"},
)

if CORS_ORIGIN.strip() == "*":
    allowed_origins = ["*"]
else:
    allowed_origins = [origin.strip() for origin in CORS_ORIGIN.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins or ["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)


@app.middleware("http")
async def observability_middleware(request: Request, call_next):  # type: ignore[override]
    started_at = perf_counter()
    response_status = 500
    error_detail: Optional[str] = None

    try:
        response = await call_next(request)
        response_status = response.status_code
        if CACHE_CONTROL_DEFAULT and "cache-control" not in response.headers:
            response.headers["cache-control"] = CACHE_CONTROL_DEFAULT
        return response
    except Exception as exc:
        error_detail = str(exc)
        raise
    finally:
        latency_ms = (perf_counter() - started_at) * 1000
        record_request(
            path=request.url.path,
            method=request.method,
            status_code=response_status,
            latency_ms=latency_ms,
        )
        log_event(
            "http_request",
            method=request.method,
            path=request.url.path,
            query=request.url.query or None,
            statusCode=response_status,
            latencyMs=round(latency_ms, 2),
            clientIp=request.client.host if request.client else None,
            error=error_detail,
        )


@app.get(
    "/api/health",
    tags=["Health"],
    summary="Health Check",
    description="Returns service status and UTC timestamp. Useful for local smoke tests and readiness checks.",
    response_model=HealthResponse,
    responses={
        200: {
            "description": "Backend is available.",
            "content": {
                "application/json": {
                    "examples": {
                        "ok": {
                            "summary": "Healthy response",
                            "value": {
                                "status": "ok",
                                "service": "heritage-map-backend",
                                "timestamp": "2026-03-07T13:20:15.314000+00:00",
                                "datasetReady": True,
                                "datasetLoading": False,
                                "datasetLastError": None,
                            },
                        }
                    }
                }
            },
        }
    },
)
async def health(response: Response) -> Dict[str, Any]:
    response.headers["cache-control"] = CACHE_CONTROL_HEALTH
    dataset_status = get_dataset_status()
    return {
        "status": "ok",
        "service": "heritage-map-backend",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "datasetReady": dataset_status["ready"],
        "datasetLoading": dataset_status["loading"],
        "datasetLastError": dataset_status["last_error"],
        "datasetPhase": dataset_status["loading_phase"],
        "datasetProgressPct": dataset_status["loading_progress"],
        "datasetLoadedAt": _utc_iso_from_ms(dataset_status["loaded_at"]),
        "datasetLastLoadDurationMs": dataset_status["last_load_duration_ms"],
        "datasetSourceCount": dataset_status["source_count"],
    }


@app.get(
    "/api/metrics",
    tags=["Observability"],
    summary="Service Metrics",
    description=(
        "Returns in-memory request and startup metrics intended for local observability and debugging."
    ),
)
async def metrics(response: Response) -> Dict[str, Any]:
    response.headers["cache-control"] = CACHE_CONTROL_METRICS
    dataset_status = get_dataset_status()
    return {
        **get_metrics_snapshot(),
        "datasetStatus": {
            "ready": dataset_status["ready"],
            "loading": dataset_status["loading"],
            "phase": dataset_status["loading_phase"],
            "progressPct": dataset_status["loading_progress"],
            "sourceCount": dataset_status["source_count"],
            "loadedAt": _utc_iso_from_ms(dataset_status["loaded_at"]),
            "lastLoadDurationMs": dataset_status["last_load_duration_ms"],
            "loadCount": dataset_status["load_count"],
            "lastError": dataset_status["last_error"],
        },
    }


@app.get(
    "/api/chat/models",
    tags=["Chat"],
    summary="List Configured Chat Models",
    description="Returns model options for the chat sidebar, including env-configuration status and default selection.",
    response_model=ChatModelsResponse,
)
async def chat_models(response: Response) -> Dict[str, Any]:
    response.headers["cache-control"] = CACHE_CONTROL_DEFAULT
    return {
        "items": list_chat_models(),
        "defaultModelId": get_default_chat_model_id(),
    }


@app.get(
    "/api/chat/usage",
    tags=["Chat"],
    summary="Get Persisted Chat Usage Totals",
    description="Returns request and token totals per chat model from the on-disk usage summary file.",
    response_model=ChatUsageSummaryResponse,
)
async def chat_usage(response: Response) -> Dict[str, Any]:
    summary = await run_in_threadpool(get_chat_usage_summary)
    models = list(summary.get("models", {}).values()) if isinstance(summary.get("models"), dict) else []
    models.sort(key=lambda item: str(item.get("label") or item.get("modelId") or ""))

    response.headers["cache-control"] = CACHE_CONTROL_DEFAULT
    return {
        "updatedAt": summary.get("updatedAt"),
        "requestsTotal": summary.get("requestsTotal", 0),
        "webSearchRequestsTotal": summary.get("webSearchRequestsTotal", 0),
        "usageTotals": summary.get("usageTotals", {}),
        "models": models,
    }


@app.post(
    "/api/chat",
    tags=["Chat"],
    summary="Generate a Chat Reply",
    description=(
        "Runs the selected Azure OpenAI model against the provided conversation history. "
        "When enabled, the Azure web-search tool is exposed as `web_search_preview`."
    ),
    response_model=ChatResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid request."},
        404: {"model": ErrorResponse, "description": "Unknown model ID."},
        502: {"model": ErrorResponse, "description": "Model returned an unusable response."},
        503: {"model": ErrorResponse, "description": "Model configuration is incomplete."},
    },
)
async def chat(payload: ChatRequest, response: Response) -> Dict[str, Any]:
    # web_serach tool je na voljo pri vseh GPT5+ modelih ne pa pri GaMS-u
    use_web_search = payload.modelId != "gams-3-12b"
    try:
        result = await run_in_threadpool(
            generate_chat_reply,
            messages=[message.model_dump() for message in payload.messages],
            model_id=payload.modelId,
            use_web_search=use_web_search,
        )
    except ChatServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    response.headers["cache-control"] = CACHE_CONTROL_DEFAULT
    return {
        "model": {
            **next(
                (item for item in list_chat_models() if item["id"] == result["model"]["id"]),
                {
                    "id": result["model"]["id"],
                    "label": result["model"]["label"],
                    "deployment": result["model"]["deployment"],
                    "available": True,
                    "supportsWebSearch": True,
                    "isDefault": False,
                    "missingEnv": [],
                },
            ),
            "deployment": result["model"]["deployment"],
            "available": True,
            "missingEnv": [],
        },
        "message": {
            "role": "assistant",
            "content": result["content"],
        },
        "citations": result["citations"],
        "webSearchUsed": result["webSearchUsed"],
        "responseId": result["responseId"],
    }


@app.get(
    "/api/overlays",
    tags=["Overlays"],
    summary="List Available Overlays",
    description="Returns available map overlays and their display metadata.",
    response_model=OverlayCatalogResponse,
)
async def overlays_catalog(response: Response) -> Dict[str, Any]:
    response.headers["cache-control"] = CACHE_CONTROL_OVERLAYS
    return {"items": list_overlay_catalog()}


@app.get(
    "/api/overlays/{overlay_kind}",
    tags=["Overlays"],
    summary="Get Overlay Data for Current Viewport",
    description=(
        "Returns overlay data for the current map viewport.\n\n"
        "This endpoint is optimized for map rendering performance:\n"
        "- Area overlays return hazard polygons at high zoom and detailed grid cells at low zoom\n"
        "- Point overlays return aggregated grid cells (for station-based datasets)\n"
        "- Density is bounded server-side to prevent frontend overload\n"
        "- Scores are normalized to a shared low-to-high scale (least to most endangered)\n"
    ),
    response_model=OverlayGridResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Unknown overlay key."},
        503: {"model": ErrorResponse, "description": "Overlay data unavailable."},
    },
)
async def overlay_grid(
    response: Response,
    overlay_kind: str = Path(
        description="Overlay key (`fire`, `flood`, `air`, `landslide`).",
        examples=["fire"],
    ),
    bbox: Optional[str] = Query(
        default=None,
        description="Viewport bounding box in format: `minLng,minLat,maxLng,maxLat`.",
        examples={"slovenia": {"summary": "Approximate Slovenia viewport", "value": "13.30,45.30,16.70,46.90"}},
    ),
    zoom: Optional[float] = Query(
        default=None,
        ge=0,
        le=22,
        description="Client map zoom used to decide aggregation cell size.",
        examples={"overview": {"summary": "Overview map", "value": 8}, "street": {"summary": "Street-level map", "value": 15}},
    ),
    refresh: Optional[str] = Query(
        default=None,
        description="Set to `1`, `true`, `yes`, or `y` to reload overlay source data.",
        examples={"force_reload": {"summary": "Bypass cache", "value": "1"}},
    ),
) -> Dict[str, Any]:
    try:
        parsed_bbox = read_bbox(bbox, strict=True)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        payload = await run_in_threadpool(
            list_overlay_grid,
            kind=overlay_kind,
            bbox=parsed_bbox,
            zoom=zoom,
            refresh=read_refresh_flag(refresh),
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=f"Overlay dataset unavailable: {exc}") from exc

    response.headers["cache-control"] = CACHE_CONTROL_OVERLAYS
    return payload


@app.get(
    "/api/heritage-sites",
    tags=["Heritage Sites"],
    summary="List Heritage Sites / Marker Points",
    description=(
        "Returns map points for the current context.\n\n"
        "Behavior depends on parameters:\n"
        "- `bbox` only: returns markers for current map viewport\n"
        "- `bbox + zoom`: may return clusters for lower zoom levels\n"
        "- `search`: returns matching real sites (clusters are disabled for search)\n"
        "- `limit`: caps number of returned items (applied after clustering/search filtering)\n"
    ),
    response_model=HeritageSiteListResponse,
    responses={
        200: {
            "description": "List of sites or cluster markers.",
            "content": {
                "application/json": {
                    "examples": {
                        "medvode_viewport_clusters": {
                            "summary": "Medvode/Spodnje Pirnice viewport at map zoom 8",
                            "value": {
                                "items": [
                                    {
                                        "id": "cluster:8:0:10:28",
                                        "registryId": None,
                                        "name": "18 heritage sites",
                                        "lat": 46.1433,
                                        "lng": 14.4312,
                                        "type": "Cluster",
                                        "protectionStatus": None,
                                        "municipality": None,
                                        "description": "Zoom in to view individual heritage sites.",
                                        "isCluster": True,
                                        "clusterCount": 18,
                                    }
                                ],
                                "total": 236,
                                "sourceCount": 31083,
                                "sourceUrl": "https://podatki.gov.si/.../rnpd.json",
                            },
                        },
                        "search_spodnje_pirnice": {
                            "summary": "Search by place name",
                            "value": {
                                "items": [
                                    {
                                        "id": "1-02508",
                                        "registryId": "1-02508",
                                        "name": "Spodnje Pirnice - Cerkev Marijinega vnebovzetja",
                                        "lat": 46.14211,
                                        "lng": 14.43172,
                                        "type": "sakralna stavbna dediščina",
                                        "protectionStatus": "spomenik lokalnega pomena",
                                        "municipality": "MEDVODE",
                                        "description": "Baročna cerkev v jedru Spodnjih Pirnic.",
                                        "isCluster": False,
                                        "clusterCount": None,
                                    }
                                ],
                                "total": 3,
                                "sourceCount": 31083,
                                "sourceUrl": "https://podatki.gov.si/.../rnpd.json",
                            },
                        },
                    }
                }
            },
        }
    },
)
async def heritage_sites(
    request: Request,
    response: Response,
    bbox: Optional[str] = Query(
        default=None,
        description="Viewport bounding box in format: `minLng,minLat,maxLng,maxLat`.",
        examples={
            "medvode_spodnje_pirnice": {
                "summary": "Medvode / Spodnje Pirnice area",
                "value": EXAMPLE_BBOX_MEDVODE,
            },
            "whole_slovenia": {
                "summary": "Approximate Slovenia-wide viewport",
                "value": "13.30,45.30,16.70,46.90",
            },
        },
    ),
    search: str = Query(
        default="",
        description=(
            "Case-insensitive and diacritic-insensitive search with weighted ranking. "
            "Name matches rank highest, then municipality, then detail fields. "
            "Matches are based on normalized exact token/phrase containment."
        ),
        examples={
            "by_place": {"summary": "Place query", "value": "spodnje pirnice"},
            "by_municipality": {"summary": "Municipality query", "value": "medvode"},
            "by_registry": {"summary": "Registry ID query", "value": "1-02508"},
        },
    ),
    limit: Optional[int] = Query(
        default=None,
        ge=1,
        le=5000,
        description="Maximum number of returned items.",
        examples={"small_list": {"summary": "Autocomplete/search size", "value": 20}},
    ),
    zoom: Optional[float] = Query(
        default=None,
        ge=0,
        le=22,
        description=(
            "Client map zoom level used for backend clustering heuristics. "
            "At lower zoom levels, endpoint may return orange cluster points."
        ),
        examples={
            "overview": {"summary": "Overview map", "value": 8},
            "street": {"summary": "Street-level map", "value": 15},
        },
    ),
    refresh: Optional[str] = Query(
        default=None,
        description="Set to `1`, `true`, `yes`, or `y` to bypass cache and reload source data.",
        examples={"force_reload": {"summary": "Bypass cache", "value": "1"}},
    ),
):
    query_started_at = perf_counter()
    has_search_query = bool(search.strip())
    try:
        parsed_bbox = read_bbox(bbox, strict=True)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    effective_limit = limit if isinstance(limit, int) else None
    if effective_limit is None and not has_search_query and parsed_bbox is None:
        effective_limit = UNBOUNDED_LIST_LIMIT
        log_event(
            "response_guardrail_applied",
            path="/api/heritage-sites",
            reason="unbounded_request_without_bbox_or_search",
            appliedLimit=effective_limit,
        )

    try:
        payload = await run_in_threadpool(
            list_heritage_sites,
            search=search,
            limit=effective_limit,
            bbox=parsed_bbox,
            zoom=zoom,
            refresh=read_refresh_flag(refresh),
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=f"Dataset unavailable: {exc}") from exc

    dataset_status = get_dataset_status()
    etag = _build_etag(
        "sites",
        dataset_status.get("loaded_at"),
        parsed_bbox,
        search.strip(),
        effective_limit,
        zoom,
    )
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers={"etag": etag, "cache-control": CACHE_CONTROL_SITES})
    response.headers["etag"] = etag
    response.headers["cache-control"] = CACHE_CONTROL_SITES

    if has_search_query:
        search_latency_ms = (perf_counter() - query_started_at) * 1000
        record_search_latency(latency_ms=search_latency_ms)
        log_event(
            "search_request",
            queryLength=len(search.strip()),
            resultCount=payload.get("total", 0),
            latencyMs=round(search_latency_ms, 2),
        )
    return payload


@app.get(
    "/api/heritage-sites/{site_id}",
    tags=["Heritage Sites"],
    summary="Get Heritage Site Details",
    description=(
        "Returns a single site with expanded `detailFields` metadata.\n\n"
        "Use an `id` returned by `/api/heritage-sites` list/search responses."
    ),
    response_model=HeritageSiteDetail,
    responses={
        200: {
            "description": "Detailed site payload.",
            "content": {
                "application/json": {
                    "examples": {
                        "spodnje_pirnice_detail": {
                            "summary": "Detail response for Spodnje Pirnice site",
                            "value": {
                                "id": "1-02508",
                                "registryId": "1-02508",
                                "name": "Spodnje Pirnice - Cerkev Marijinega vnebovzetja",
                                "lat": 46.14211,
                                "lng": 14.43172,
                                "type": "sakralna stavbna dediščina",
                                "protectionStatus": "spomenik lokalnega pomena",
                                "municipality": "MEDVODE",
                                "description": "Baročna cerkev v jedru Spodnjih Pirnic.",
                                "isCluster": False,
                                "clusterCount": None,
                                "detailFields": [
                                    {"label": "Datacija", "value": "17. stol."},
                                    {"label": "Zavod", "value": "ZVKD Ljubljana"},
                                ],
                                "sourceUrl": "https://podatki.gov.si/.../rnpd.json",
                            },
                        }
                    }
                }
            },
        },
        404: {
            "model": ErrorResponse,
            "description": "No site exists for provided ID.",
            "content": {
                "application/json": {
                    "examples": {
                        "not_found": {"summary": "Unknown ID", "value": {"detail": "Site not found"}}
                    }
                }
            },
        },
    },
)
async def heritage_site_details(
    request: Request,
    response: Response,
    site_id: str = Path(
        description="Site ID from list/search endpoint (for example RNPD EID).",
        examples=[EXAMPLE_SITE_ID_SPODNJE_PIRNICE],
    ),
    refresh: Optional[str] = Query(
        default=None,
        description="Set to `1`, `true`, `yes`, or `y` to bypass cache and reload source data.",
        examples={"force_reload": {"summary": "Bypass cache", "value": "1"}},
    ),
):
    try:
        site = get_heritage_site_details(site_id, refresh=read_refresh_flag(refresh))
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=f"Dataset unavailable: {exc}") from exc
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")

    dataset_status = get_dataset_status()
    etag = _build_etag("site-detail", dataset_status.get("loaded_at"), site_id)
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers={"etag": etag, "cache-control": CACHE_CONTROL_SITE_DETAIL})

    response.headers["etag"] = etag
    response.headers["cache-control"] = CACHE_CONTROL_SITE_DETAIL
    return site


@app.options("/{path:path}", include_in_schema=False)
async def options_handler(path: str) -> Response:
    return Response(status_code=204)


def _build_etag(prefix: str, *parts: Any) -> str:
    raw = "|".join(str(part) for part in parts)
    digest = sha1(raw.encode("utf-8")).hexdigest()[:20]
    return f'W/"{prefix}-{digest}"'


def _utc_iso_from_ms(value_ms: Optional[float]) -> Optional[str]:
    if not isinstance(value_ms, (int, float)) or value_ms <= 0:
        return None
    return datetime.fromtimestamp(value_ms / 1000, tz=timezone.utc).isoformat()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=PORT, reload=False)
