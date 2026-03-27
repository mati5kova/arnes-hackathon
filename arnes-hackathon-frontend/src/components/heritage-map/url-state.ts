import type { OverlayKind } from "@/types/overlays";

const DEFAULT_ZOOM = 8;
const MIN_ZOOM = 3;
const MAX_ZOOM = 18;
const MAP_RELOAD_RESET_HANDLED_KEY = "heritage-map-reload-reset-handled";
const PAGE_LOAD_TOKEN = getPageLoadToken();
const SHOULD_RESET_ON_INITIAL_MAP_MOUNT = shouldResetMapStateOnReload();
let hasMountedMapInCurrentPage = false;

export interface ParsedMapUrlState {
	bbox: string | null;
	zoom: number;
	search: string;
	overlay: OverlayKind | null;
}

export function parseMapUrlState(searchParams: URLSearchParams): ParsedMapUrlState {
	return {
		bbox: normalizeBbox(searchParams.get("bbox")),
		zoom: parseZoom(searchParams.get("zoom")),
		search: (searchParams.get("search") || "").trim(),
		overlay: parseOverlayKind(searchParams.get("overlay")),
	};
}

export function shouldIgnoreMapUrlStateOnMount(): boolean {
	return SHOULD_RESET_ON_INITIAL_MAP_MOUNT && !hasMountedMapInCurrentPage;
}

export function markMapUrlStateMountHandled() {
	if (hasMountedMapInCurrentPage) return;
	hasMountedMapInCurrentPage = true;

	if (!SHOULD_RESET_ON_INITIAL_MAP_MOUNT) return;
	if (typeof window === "undefined") return;

	try {
		window.sessionStorage.setItem(MAP_RELOAD_RESET_HANDLED_KEY, PAGE_LOAD_TOKEN);
	} catch {
		// Ignore storage write failures in restricted browser contexts.
	}
}

export function formatZoomForUrl(zoom: number): string {
	return (Math.round(zoom * 100) / 100).toFixed(2);
}

function parseZoom(rawZoom: string | null): number {
	if (!rawZoom) return DEFAULT_ZOOM;
	const numericZoom = Number(rawZoom);
	if (!Number.isFinite(numericZoom)) return DEFAULT_ZOOM;
	return clamp(numericZoom, MIN_ZOOM, MAX_ZOOM);
}

function normalizeBbox(rawBbox: string | null): string | null {
	if (!rawBbox) return null;
	const parts = rawBbox.split(",").map((part) => part.trim());
	if (parts.length !== 4) return null;
	const numbers = parts.map(Number);
	if (numbers.some((value) => !Number.isFinite(value))) return null;
	const [minLng, minLat, maxLng, maxLat] = numbers;
	if (minLng >= maxLng || minLat >= maxLat) return null;
	return numbers.map((value) => value.toFixed(4)).join(",");
}

function parseOverlayKind(rawOverlay: string | null): OverlayKind | null {
	if (!rawOverlay) return null;
	const normalized = rawOverlay.trim().toLowerCase();
	if (normalized === "fire" || normalized === "flood" || normalized === "air" || normalized === "landslide") {
		return normalized;
	}
	return null;
}

function clamp(value: number, min: number, max: number) {
	return Math.min(max, Math.max(min, value));
}

function shouldResetMapStateOnReload() {
	if (typeof window === "undefined") return false;

	const navigationEntry = window.performance
		.getEntriesByType("navigation")
		.find((entry): entry is PerformanceNavigationTiming => entry.entryType === "navigation");
	const isReloadNavigation = navigationEntry?.type === "reload";
	if (!isReloadNavigation) return false;

	try {
		const handledToken = window.sessionStorage.getItem(MAP_RELOAD_RESET_HANDLED_KEY);
		return handledToken !== PAGE_LOAD_TOKEN;
	} catch {
		// If storage is unavailable, still prefer reload reset behavior.
		return true;
	}
}

function getPageLoadToken() {
	if (typeof window === "undefined") return "server";
	const timeOrigin = window.performance?.timeOrigin;
	return Number.isFinite(timeOrigin) ? String(timeOrigin) : String(Date.now());
}
