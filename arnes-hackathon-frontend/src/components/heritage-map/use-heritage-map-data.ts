import { useDebouncedValue } from "@/hooks/use-debounced-value";
import { ApiError, fetchApiHealth, fetchHeritageSite, fetchHeritageSites, fetchOverlayGrid } from "@/lib/heritage-api";
import type { HeritageSiteDetail, HeritageSiteSummary } from "@/types/heritage";
import type { OverlayKind } from "@/types/overlays";
import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";

const STARTUP_RETRY_POLICY = {
	maxRetries: 120,
	baseDelayMs: 500,
	maxDelayMs: 5_000,
} as const;

const ERROR_RECOVERY_POLL_MS = 3_000;

const QUERY_CACHE_POLICY = {
	markers: {
		// Dataset is effectively static during session: keep query perpetually fresh.
		staleTime: Infinity,
		gcTime: 10 * 60_000,
		refetchOnWindowFocus: false,
		// Keep mount refetch off for successful cached data, while retry policy handles startup errors.
		refetchOnMount: false,
		refetchOnReconnect: false,
	},
	search: {
		// Search results derive from static source data.
		staleTime: Infinity,
		gcTime: 5 * 60_000,
		refetchOnWindowFocus: false,
		refetchOnMount: false,
		refetchOnReconnect: false,
	},
	detail: {
		// Detail records are static metadata.
		staleTime: Infinity,
		gcTime: 30 * 60_000,
		refetchOnWindowFocus: false,
		refetchOnMount: false,
		refetchOnReconnect: false,
	},
} as const;

const RETRY_POLICY = {
	retry: shouldRetryQuery,
	retryDelay: getRetryDelay,
} as const;

interface UseHeritageMapDataOptions {
	bbox: string | null;
	zoom: number;
	activeOverlay: OverlayKind | null;
	searchQuery: string;
	selectedSiteId: string | null;
	selectedSitePreview: HeritageSiteSummary | null;
	dialogOpen: boolean;
}

export function useHeritageMapData({
	bbox,
	zoom,
	activeOverlay,
	searchQuery,
	selectedSiteId,
	selectedSitePreview,
	dialogOpen,
}: UseHeritageMapDataOptions) {
	const normalizedZoom = useMemo(() => (Number.isFinite(zoom) ? Math.round(zoom * 100) / 100 : NaN), [zoom]);
	const debouncedSearch = useDebouncedValue(searchQuery, 250);
	const markerCachePolicy = QUERY_CACHE_POLICY.markers;
	const searchCachePolicy = QUERY_CACHE_POLICY.search;
	const detailCachePolicy = QUERY_CACHE_POLICY.detail;

	const markersQuery = useQuery({
		queryKey: ["heritage-sites", "markers", bbox, normalizedZoom],
		queryFn: ({ signal }) => fetchHeritageSites({ bbox, zoom: normalizedZoom, signal }),
		enabled: Boolean(bbox),
		...markerCachePolicy,
		...RETRY_POLICY,
		// Keep probing backend readiness after cold-start failures.
		refetchInterval: (query) => (query.state.error ? ERROR_RECOVERY_POLL_MS : false),
		refetchIntervalInBackground: true,
		placeholderData: (previousData) => previousData,
	});

	const overlayQuery = useQuery({
		queryKey: ["overlay-grid", activeOverlay, bbox, normalizedZoom],
		queryFn: ({ signal }) => fetchOverlayGrid(activeOverlay as OverlayKind, { bbox, zoom: normalizedZoom, signal }),
		enabled: Boolean(activeOverlay) && Boolean(bbox),
		staleTime: 45_000,
		gcTime: 10 * 60_000,
		refetchOnWindowFocus: false,
		refetchOnMount: false,
		refetchOnReconnect: false,
		...RETRY_POLICY,
	});

	const searchResultsQuery = useQuery({
		queryKey: ["heritage-sites", "search", debouncedSearch],
		queryFn: ({ signal }) => fetchHeritageSites({ search: debouncedSearch, limit: 20, signal }),
		enabled: debouncedSearch.trim().length > 1,
		...searchCachePolicy,
		...RETRY_POLICY,
	});

	const siteDetailQuery = useQuery({
		queryKey: ["heritage-site", selectedSiteId],
		queryFn: ({ signal }) => fetchHeritageSite(selectedSiteId as string, signal),
		enabled: dialogOpen && Boolean(selectedSiteId),
		...detailCachePolicy,
		...RETRY_POLICY,
	});

	const healthQuery = useQuery({
		queryKey: ["api-health"],
		queryFn: ({ signal }) => fetchApiHealth(signal),
		enabled: Boolean(bbox),
		staleTime: 0,
		gcTime: 60_000,
		retry: false,
		refetchInterval: (query) => {
			const status = query.state.data;
			if (!status) return 2_000;
			if (status.datasetLoading || !status.datasetReady) return 2_000;
			if (markersQuery.isFetching || markersQuery.isError) return 2_000;
			return false;
		},
		refetchIntervalInBackground: true,
	});

	const markerSites = markersQuery.data?.items ?? [];
	const shouldShowSearch = searchQuery.trim().length > 1;
	const searchResults = shouldShowSearch ? (searchResultsQuery.data?.items ?? []) : [];
	const selectedSite: HeritageSiteSummary | HeritageSiteDetail | null = siteDetailQuery.data ?? selectedSitePreview;

	return {
		markersQuery,
		overlayQuery,
		searchResultsQuery,
		siteDetailQuery,
		healthQuery,
		markerSites,
		overlayGrid: overlayQuery.data,
		searchResults,
		selectedSite,
		healthStatus: healthQuery.data,
		shouldShowSearch,
		totalInView: markersQuery.data?.total ?? markerSites.length,
		displayPointCount: markerSites.length,
		showMarkerOverlay: markersQuery.isFetching,
	};
}

function shouldRetryQuery(failureCount: number, error: unknown) {
	if (failureCount >= STARTUP_RETRY_POLICY.maxRetries) return false;

	if (error instanceof Error && error.name === "AbortError") {
		return false;
	}

	if (error instanceof ApiError) {
		return error.status >= 500;
	}

	if (error instanceof TypeError) {
		// Covers network-level startup errors (e.g., backend just coming online).
		return true;
	}

	if (error instanceof Error) {
		const message = error.message.toLowerCase();
		return message.includes("failed to fetch") || message.includes("network");
	}

	return false;
}

function getRetryDelay(attemptIndex: number) {
	return Math.min(STARTUP_RETRY_POLICY.baseDelayMs * 2 ** attemptIndex, STARTUP_RETRY_POLICY.maxDelayMs);
}
