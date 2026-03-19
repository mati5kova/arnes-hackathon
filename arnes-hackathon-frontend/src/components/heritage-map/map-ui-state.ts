import { ApiError, type ApiHealthStatus } from "@/lib/heritage-api";
import { MAX_RECENT_SEARCHES, RECENT_SEARCHES_KEY } from "./constants";

const MAX_RECENT_SEARCH_CHIPS = 10;

export function readPersistedRecentSearches() {
	if (typeof window === "undefined") return [];

	try {
		const raw = window.localStorage.getItem(RECENT_SEARCHES_KEY);
		if (!raw) return [];

		const parsed = JSON.parse(raw) as unknown;
		if (!Array.isArray(parsed)) return [];

		return parsed
			.filter((value): value is string => typeof value === "string")
			.map((value) => value.trim())
			.filter(Boolean)
			.slice(0, MAX_RECENT_SEARCHES);
	} catch {
		return [];
	}
}

export function persistRecentSearches(value: string[]) {
	try {
		window.localStorage.setItem(RECENT_SEARCHES_KEY, JSON.stringify(value));
	} catch {
		// Ignore write failures in restricted browser contexts.
	}
}

export function mergeRecentSearchesForChips(recentSearches: string[]) {
	return Array.from(new Set(recentSearches.map((item) => item.toLowerCase()))).slice(0, MAX_RECENT_SEARCH_CHIPS);
}

export function getMarkerRecoveryMessage(error: unknown, healthStatus?: ApiHealthStatus) {
	if (healthStatus?.datasetLoading) {
		const progress = formatProgress(healthStatus.datasetProgressPct);
		return progress
			? `Server waking up. Loading heritage dataset (${progress}).`
			: "Server waking up. Loading heritage dataset...";
	}

	if (healthStatus && !healthStatus.datasetReady) {
		return "Server is starting and dataset is not ready yet. Retrying automatically...";
	}

	if (error instanceof ApiError && error.status >= 500) {
		return "Server cold start in progress. Loading heritage data and retrying...";
	}

	if (error instanceof TypeError) {
		return "Waiting for backend connection. Retrying automatically...";
	}

	if (error instanceof Error) {
		const message = error.message.toLowerCase();
		if (message.includes("network") || message.includes("failed to fetch")) {
			return "Backend not ready yet. Retrying automatically...";
		}
	}

	return "Temporary server issue. Retrying automatically...";
}

export function getMarkerRecoveryDetails(healthStatus?: ApiHealthStatus) {
	if (!healthStatus) return [];

	const details: string[] = [];
	const progress = formatProgress(healthStatus.datasetProgressPct);
	if (progress) {
		details.push(`Startup progress: ${progress}`);
	}

	const lastUpdate = formatHealthTimestamp(healthStatus.datasetLoadedAt || healthStatus.timestamp);
	if (lastUpdate) {
		details.push(`Last update: ${lastUpdate}`);
	}

	return details;
}

function formatProgress(value: number | undefined) {
	if (typeof value !== "number" || !Number.isFinite(value)) return null;
	const clamped = Math.max(0, Math.min(100, Math.round(value)));
	return `${clamped}%`;
}

function formatHealthTimestamp(value: string | undefined | null) {
	if (!value) return null;
	const date = new Date(value);
	if (!Number.isFinite(date.getTime())) return null;
	return new Intl.DateTimeFormat(undefined, {
		hour: "2-digit",
		minute: "2-digit",
		second: "2-digit",
	}).format(date);
}
