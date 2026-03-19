import type { HeritageSiteSummary } from "@/types/heritage";
import { Suspense, lazy, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AttributionControl, MapContainer, TileLayer, ZoomControl } from "react-leaflet";
import { useSearchParams } from "react-router-dom";
import MapLegend from "./heritage-map/MapLegend";
import MapSearchBox from "./heritage-map/MapSearchBox";
import MapStatusOverlays from "./heritage-map/MapStatusOverlays";
import MarkerLayer from "./heritage-map/MarkerLayer";
import {
	CLUSTER_FLY_HOLD_MS,
	FLY_TO_DIALOG_DELAY_MS,
	MAP_INSTRUCTIONS_ID,
	MAX_RECENT_SEARCHES,
} from "./heritage-map/constants";
import { FlyToSite, InitialViewport, MapResizeInvalidator, ViewportListener } from "./heritage-map/map-behavior";
import {
	getMarkerRecoveryDetails,
	getMarkerRecoveryMessage,
	mergeRecentSearchesForChips,
	persistRecentSearches,
	readPersistedRecentSearches,
} from "./heritage-map/map-ui-state";
import {
	formatZoomForUrl,
	markMapUrlStateMountHandled,
	parseMapUrlState,
	shouldIgnoreMapUrlStateOnMount,
} from "./heritage-map/url-state";
import { useHeritageMapData } from "./heritage-map/use-heritage-map-data";

const SiteDialog = lazy(() => import("./SiteDialog"));

const HeritageMap = () => {
	const [searchParams, setSearchParams] = useSearchParams();
	const ignoreMapUrlStateRef = useRef(shouldIgnoreMapUrlStateOnMount());
	const initialUrlStateRef = useRef(
		parseMapUrlState(ignoreMapUrlStateRef.current ? new URLSearchParams() : searchParams),
	);
	const initialUrlState = initialUrlStateRef.current;
	const [selectedSiteId, setSelectedSiteId] = useState<string | null>(null);
	const [selectedSitePreview, setSelectedSitePreview] = useState<HeritageSiteSummary | null>(null);
	const [dialogOpen, setDialogOpen] = useState(false);
	const [searchQuery, setSearchQuery] = useState(initialUrlState.search);
	const [recentSearches, setRecentSearches] = useState<string[]>([]);
	const [flyTarget, setFlyTarget] = useState<HeritageSiteSummary | null>(null);
	const [flyZoom, setFlyZoom] = useState<number | undefined>(undefined);
	const [bbox, setBbox] = useState<string | null>(initialUrlState.bbox);
	const [zoom, setZoom] = useState<number>(initialUrlState.zoom);

	const {
		markersQuery,
		searchResultsQuery,
		siteDetailQuery,
		healthQuery,
		markerSites,
		searchResults,
		selectedSite,
		healthStatus,
		shouldShowSearch,
		totalInView,
		displayPointCount,
		showMarkerOverlay,
	} = useHeritageMapData({
		bbox,
		zoom,
		searchQuery,
		selectedSiteId,
		selectedSitePreview,
		dialogOpen,
	});

	useEffect(() => {
		setRecentSearches(readPersistedRecentSearches());
	}, []);

	useEffect(() => {
		markMapUrlStateMountHandled();
	}, []);

	const recentAndChipSearches = useMemo(() => mergeRecentSearchesForChips(recentSearches), [recentSearches]);

	useEffect(() => {
		if (!ignoreMapUrlStateRef.current) return;
		setSearchParams(
			(currentParams) => {
				const nextParams = new URLSearchParams(currentParams);
				nextParams.delete("bbox");
				nextParams.delete("zoom");
				nextParams.delete("search");
				return nextParams.toString() === currentParams.toString() ? currentParams : nextParams;
			},
			{ replace: true },
		);
	}, [setSearchParams]);

	useEffect(() => {
		setSearchParams(
			(currentParams) => {
				const nextParams = new URLSearchParams(currentParams);
				const normalizedSearch = searchQuery.trim();

				if (bbox) {
					nextParams.set("bbox", bbox);
				} else {
					nextParams.delete("bbox");
				}

				if (Number.isFinite(zoom)) {
					nextParams.set("zoom", formatZoomForUrl(zoom));
				} else {
					nextParams.delete("zoom");
				}

				if (normalizedSearch) {
					nextParams.set("search", normalizedSearch);
				} else {
					nextParams.delete("search");
				}

				return nextParams.toString() === currentParams.toString() ? currentParams : nextParams;
			},
			{ replace: true },
		);
	}, [bbox, searchQuery, setSearchParams, zoom]);

	const handleMarkerClick = useCallback(
		(site: HeritageSiteSummary) => {
			if (site.isCluster) {
				setFlyTarget(site);
				setFlyZoom(Math.min(17, zoom + 2));
				window.setTimeout(() => {
					setFlyTarget(null);
					setFlyZoom(undefined);
				}, CLUSTER_FLY_HOLD_MS);
				return;
			}

			setSelectedSiteId(site.id);
			setSelectedSitePreview(site);
			setDialogOpen(true);
		},
		[zoom],
	);

	const persistRecentSearch = (rawTerm: string) => {
		const term = rawTerm.trim().toLowerCase();
		if (!term) return;
		setRecentSearches((prev) => {
			const next = [term, ...prev.filter((item) => item !== term)].slice(0, MAX_RECENT_SEARCHES);
			persistRecentSearches(next);
			return next;
		});
	};

	const handleSearchSelect = (site: HeritageSiteSummary) => {
		persistRecentSearch(searchQuery);
		setSearchQuery("");
		setDialogOpen(false);

		requestAnimationFrame(() => {
			requestAnimationFrame(() => {
				setFlyTarget(site);
				setFlyZoom(15);
			});
		});

		window.setTimeout(() => {
			setSelectedSiteId(site.id);
			setSelectedSitePreview(site);
			setDialogOpen(true);
		}, FLY_TO_DIALOG_DELAY_MS);

		window.setTimeout(() => {
			setFlyTarget(null);
			setFlyZoom(undefined);
		}, FLY_TO_DIALOG_DELAY_MS + 550);
	};

	const markerError = markersQuery.error;
	const healthError = healthQuery.error;
	const datasetLoading = Boolean(healthStatus?.datasetLoading);
	const datasetNotReady = Boolean(healthStatus) && !healthStatus.datasetReady;
	const noMarkerDataLoaded = markerSites.length === 0;
	const hasTransientMarkerFailures = markersQuery.failureCount > 0;
	const isRecoveringFromError =
		(Boolean(markerError) || Boolean(healthError)) && (datasetLoading || markersQuery.isFetching);
	const isWaitingForDataset = (datasetLoading || datasetNotReady) && noMarkerDataLoaded;
	// Keep recovery banner visible during retry-delay gaps to avoid a brief hard-error flash before success.
	const isRetryingBackendStartup = noMarkerDataLoaded && (hasTransientMarkerFailures || Boolean(healthError));
	const showRecoveryBanner = isRecoveringFromError || isWaitingForDataset || isRetryingBackendStartup;
	const markerRecoveryMessage = getMarkerRecoveryMessage(markerError ?? healthError, healthStatus);
	const markerRecoveryDetails = getMarkerRecoveryDetails(healthStatus);
	const isRetryNowDisabled = markersQuery.isFetching && healthQuery.isFetching;

	const handleRetryNow = () => {
		void healthQuery.refetch();
		void markersQuery.refetch();
	};

	return (
		<div className="relative h-full flex-1" role="region" aria-label="Heritage map and search">
			<MapSearchBox
				searchQuery={searchQuery}
				onSearchQueryChange={setSearchQuery}
				searchResults={searchResults}
				searchLoading={searchResultsQuery.isFetching}
				shouldShowSearch={shouldShowSearch}
				recentAndChipSearches={recentAndChipSearches}
				onSearchSelect={handleSearchSelect}
			/>

			<p id={MAP_INSTRUCTIONS_ID} className="sr-only">
				Interactive map showing heritage sites and clusters. Use search results to navigate to a site and open
				details.
			</p>

			<MapContainer
				center={[46.15, 14.99]}
				zoom={initialUrlState.zoom}
				className="z-0 h-full w-full"
				attributionControl={false}
				zoomControl={false}
				preferCanvas={true}
				zoomAnimationThreshold={20}
				aria-label="Interactive heritage map"
				aria-describedby={MAP_INSTRUCTIONS_ID}
			>
				<TileLayer
					attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
					url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
				/>
				<AttributionControl position="bottomright" prefix={false} />
				<ZoomControl position="topleft" />
				<InitialViewport bbox={initialUrlState.bbox} zoom={initialUrlState.zoom} />
				<MapResizeInvalidator />
				<ViewportListener
					onViewportChange={(nextBbox, nextZoom) => {
						setBbox(nextBbox);
						setZoom(nextZoom);
					}}
				/>
				<MarkerLayer markerSites={markerSites} onMarkerClick={handleMarkerClick} />
				<FlyToSite
					site={flyTarget}
					zoom={flyZoom}
					onNoMovement={() => {
						setFlyTarget(null);
						setFlyZoom(undefined);
					}}
				/>
			</MapContainer>

			<MapStatusOverlays
				showMarkerOverlay={showMarkerOverlay}
				hasMarkerError={Boolean(markerError ?? healthError) && !showRecoveryBanner}
				isRecovering={showRecoveryBanner}
				recoveryMessage={markerRecoveryMessage}
				recoveryDetails={markerRecoveryDetails}
				onRetryNow={handleRetryNow}
				retryDisabled={isRetryNowDisabled}
			/>
			<MapLegend displayPointCount={displayPointCount} totalInView={totalInView} />

			<Suspense fallback={null}>
				<SiteDialog
					site={selectedSite}
					open={dialogOpen}
					loading={siteDetailQuery.isLoading}
					onOpenChange={setDialogOpen}
				/>
			</Suspense>
		</div>
	);
};

export default HeritageMap;
