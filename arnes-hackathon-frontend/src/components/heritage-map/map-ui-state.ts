import { ApiError, type ApiHealthStatus } from "@/lib/heritage-api";
import { MAX_RECENT_SEARCHES, RECENT_SEARCHES_KEY } from "./constants";

const MAX_RECENT_SEARCH_CHIPS = 10;
type RecoveryMessages = (typeof import("@/lib/i18n").messages)["en"]["map"]["recovery"];

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

export function getMarkerRecoveryMessage(
	error: unknown,
	healthStatus?: ApiHealthStatus,
	i18n?: RecoveryMessages,
) {
	const text = i18n;
	if (healthStatus?.datasetLoading) {
		const progress = formatProgress(healthStatus.datasetProgressPct);
		return progress
			? `${text?.serverWakingWithProgress ?? "Server waking up. Loading heritage dataset"} (${progress}).`
			: (text?.serverWaking ?? "Server waking up. Loading heritage dataset...");
	}

	if (healthStatus && !healthStatus.datasetReady) {
		return text?.serverStartingRetrying ?? "Server is starting and dataset is not ready yet. Retrying automatically...";
	}

	if (error instanceof ApiError && error.status >= 500) {
		return text?.coldStartRetrying ?? "Server cold start in progress. Loading heritage data and retrying...";
	}

	if (error instanceof TypeError) {
		return text?.waitingBackendConnection ?? "Waiting for backend connection. Retrying automatically...";
	}

	if (error instanceof Error) {
		const message = error.message.toLowerCase();
		if (message.includes("network") || message.includes("failed to fetch")) {
			return text?.backendNotReady ?? "Backend not ready yet. Retrying automatically...";
		}
	}

	return text?.temporaryIssue ?? "Temporary server issue. Retrying automatically...";
}

export function getMarkerRecoveryDetails(healthStatus?: ApiHealthStatus, i18n?: RecoveryMessages) {
	if (!healthStatus) return [];

	const details: string[] = [];
	const progress = formatProgress(healthStatus.datasetProgressPct);
	if (progress) {
		details.push(`${i18n?.startupProgress ?? "Startup progress"}: ${progress}`);
	}

	const lastUpdate = formatHealthTimestamp(healthStatus.datasetLoadedAt || healthStatus.timestamp);
	if (lastUpdate) {
		details.push(`${i18n?.lastUpdate ?? "Last update"}: ${lastUpdate}`);
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
