import type { HeritageSiteDetail, HeritageSiteListResponse, HeritageSiteSummary } from "@/types/heritage";
import type { OverlayGridResponse, OverlayKind } from "@/types/overlays";

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");

export class ApiError extends Error {
	status: number;
	path: string;
	detail?: string;

	constructor(status: number, path: string, detail?: string) {
		super(`Request failed with status ${status}`);
		this.name = "ApiError";
		this.status = status;
		this.path = path;
		this.detail = detail;
	}
}

interface ListOptions {
	bbox?: string | null;
	search?: string;
	limit?: number;
	zoom?: number;
	signal?: AbortSignal;
}

export interface ApiHealthStatus {
	status: string;
	service: string;
	timestamp: string;
	datasetReady: boolean;
	datasetLoading: boolean;
	datasetLastError?: string | null;
	datasetPhase?: string;
	datasetProgressPct?: number;
	datasetLoadedAt?: string | null;
	datasetLastLoadDurationMs?: number | null;
	datasetSourceCount?: number;
}

export interface ChatModelDescriptor {
	id: string;
	label: string;
	deployment: string;
	available: boolean;
	supportsWebSearch: boolean;
	isDefault: boolean;
	missingEnv: string[];
}

export interface ChatModelsResponse {
	items: ChatModelDescriptor[];
	defaultModelId: string;
}

export interface ChatMessage {
	role: "user" | "assistant";
	content: string;
}

export interface ChatCitation {
	title: string;
	url: string;
}

export interface ChatResponse {
	model: ChatModelDescriptor;
	message: ChatMessage;
	citations: ChatCitation[];
	webSearchUsed: boolean;
	responseId: string;
}

export async function fetchHeritageSites(options: ListOptions = {}): Promise<HeritageSiteListResponse> {
	const searchParams = new URLSearchParams();

	if (options.bbox) {
		searchParams.set("bbox", options.bbox);
	}
	if (options.search?.trim()) {
		searchParams.set("search", options.search.trim());
	}
	if (typeof options.limit === "number") {
		searchParams.set("limit", String(options.limit));
	}
	if (typeof options.zoom === "number" && Number.isFinite(options.zoom)) {
		searchParams.set("zoom", String(options.zoom));
	}

	const queryString = searchParams.toString();
	return fetchJson<HeritageSiteListResponse>(
		`/api/heritage-sites${queryString ? `?${queryString}` : ""}`,
		options.signal,
	);
}

export async function fetchHeritageSite(siteId: string, signal?: AbortSignal): Promise<HeritageSiteDetail> {
	return fetchJson<HeritageSiteDetail>(`/api/heritage-sites/${encodeURIComponent(siteId)}`, signal);
}

export async function fetchApiHealth(signal?: AbortSignal): Promise<ApiHealthStatus> {
	return fetchJson<ApiHealthStatus>("/api/health", signal);
}

export async function fetchChatModels(signal?: AbortSignal): Promise<ChatModelsResponse> {
	return fetchJson<ChatModelsResponse>("/api/chat/models", signal);
}

export async function sendChatMessage(
	payload: {
		messages: ChatMessage[];
		modelId: string;
	},
	signal?: AbortSignal,
): Promise<ChatResponse> {
	const response = await fetch(`${API_BASE_URL}/api/chat`, {
		method: "POST",
		headers: {
			"Content-Type": "application/json",
		},
		body: JSON.stringify(payload),
		signal,
	});

	if (!response.ok) {
		let detail: string | undefined;
		try {
			const errorPayload = await response.json();
			if (
				errorPayload &&
				typeof errorPayload === "object" &&
				"detail" in errorPayload &&
				typeof errorPayload.detail === "string"
			) {
				detail = errorPayload.detail;
			}
		} catch {
			// Best effort only.
		}
		throw new ApiError(response.status, "/api/chat", detail);
	}

	return (await response.json()) as ChatResponse;
}

interface OverlayOptions {
	bbox?: string | null;
	zoom?: number;
	signal?: AbortSignal;
}

export async function fetchOverlayGrid(kind: OverlayKind, options: OverlayOptions = {}): Promise<OverlayGridResponse> {
	const searchParams = new URLSearchParams();

	if (options.bbox) {
		searchParams.set("bbox", options.bbox);
	}
	if (typeof options.zoom === "number" && Number.isFinite(options.zoom)) {
		searchParams.set("zoom", String(options.zoom));
	}

	const queryString = searchParams.toString();
	return fetchJson<OverlayGridResponse>(
		`/api/overlays/${encodeURIComponent(kind)}${queryString ? `?${queryString}` : ""}`,
		options.signal,
	);
}

async function fetchJson<T>(path: string, signal?: AbortSignal): Promise<T> {
	const response = await fetch(`${API_BASE_URL}${path}`, { signal });
	if (!response.ok) {
		let detail: string | undefined;
		try {
			const payload = await response.json();
			if (payload && typeof payload === "object" && "detail" in payload && typeof payload.detail === "string") {
				detail = payload.detail;
			}
		} catch {
			// Best effort only; not all responses are JSON.
		}
		throw new ApiError(response.status, path, detail);
	}
	return (await response.json()) as T;
}

export function getSearchSubtitle(site: HeritageSiteSummary): string {
	return [site.type, site.protectionStatus, site.municipality].filter(Boolean).join(" • ");
}
