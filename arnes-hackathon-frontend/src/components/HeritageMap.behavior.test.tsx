import type { HeritageSiteSummary } from "@/types/heritage";
import { act, fireEvent, render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

interface MockQueryState {
	error: unknown;
	isFetching: boolean;
	failureCount?: number;
	refetch: () => void;
}

interface MockDataState {
	markersQuery: MockQueryState;
	searchResultsQuery: { isFetching: boolean };
	siteDetailQuery: { isLoading: boolean };
	healthQuery: MockQueryState;
	markerSites: HeritageSiteSummary[];
	searchResults: HeritageSiteSummary[];
	selectedSite: HeritageSiteSummary | null;
	healthStatus:
		| {
				status: string;
				service: string;
				timestamp: string;
				datasetReady: boolean;
				datasetLoading: boolean;
				datasetProgressPct?: number;
		  }
		| undefined;
	shouldShowSearch: boolean;
	totalInView: number;
	displayPointCount: number;
	showMarkerOverlay: boolean;
}

type MockUseDataImpl = (options: unknown) => MockDataState;

const mockFns = vi.hoisted((): { useDataImpl: MockUseDataImpl } => ({
	useDataImpl: (_options: unknown) => {
		throw new Error("useDataImpl not configured");
	},
}));

vi.mock("react-leaflet", () => ({
	MapContainer: ({ children }: { children: ReactNode }) => <div data-testid="map-container">{children}</div>,
	TileLayer: () => null,
	ZoomControl: () => null,
	Pane: ({ children }: { children: ReactNode }) => <>{children}</>,
	CircleMarker: () => null,
}));

vi.mock("./heritage-map/map-behavior", () => ({
	FlyToSite: () => null,
	InitialViewport: () => null,
	MapResizeInvalidator: () => null,
	ViewportListener: () => null,
}));

vi.mock("./SiteDialog", () => ({
	default: ({ site, open }: { site: HeritageSiteSummary | null; open: boolean }) =>
		open && site ? <div>Dialog: {site.name}</div> : null,
}));

vi.mock("./heritage-map/use-heritage-map-data", () => ({
	useHeritageMapData: (options: unknown) => mockFns.useDataImpl(options),
}));

import HeritageMap from "./HeritageMap";
import { FLY_TO_DIALOG_DELAY_MS } from "./heritage-map/constants";

describe("HeritageMap core behavior", () => {
	beforeEach(() => {
		mockFns.useDataImpl = () => ({
			markersQuery: { error: null, isFetching: false, failureCount: 0, refetch: vi.fn() },
			searchResultsQuery: { isFetching: false },
			siteDetailQuery: { isLoading: false },
			healthQuery: { error: null, isFetching: false, refetch: vi.fn() },
			markerSites: [],
			searchResults: [],
			selectedSite: null,
			healthStatus: undefined,
			shouldShowSearch: false,
			totalInView: 0,
			displayPointCount: 0,
			showMarkerOverlay: false,
		});
	});

	afterEach(() => {
		vi.useRealTimers();
	});

	it("opens site dialog after selecting a search result", async () => {
		const site: HeritageSiteSummary = {
			id: "1-02508",
			name: "Spodnje Pirnice - Cerkev Marijinega vnebovzetja",
			lat: 46.14211,
			lng: 14.43172,
			type: "sakralna stavbna dediščina",
			municipality: "MEDVODE",
		};

		mockFns.useDataImpl = (options: unknown) => {
			const typedOptions = options as { searchQuery: string; selectedSitePreview: HeritageSiteSummary | null };
			const shouldShow = typedOptions.searchQuery.trim().length > 1;
			return {
				markersQuery: { error: null, isFetching: false, failureCount: 0, refetch: vi.fn() },
				searchResultsQuery: { isFetching: false },
				siteDetailQuery: { isLoading: false },
				healthQuery: { error: null, isFetching: false, refetch: vi.fn() },
				markerSites: [],
				searchResults: shouldShow ? [site] : [],
				selectedSite: typedOptions.selectedSitePreview,
				healthStatus: undefined,
				shouldShowSearch: shouldShow,
				totalInView: 0,
				displayPointCount: 0,
				showMarkerOverlay: false,
			};
		};

		render(
			<MemoryRouter
				initialEntries={["/"]}
				future={{
					v7_startTransition: true,
					v7_relativeSplatPath: true,
				}}
			>
				<HeritageMap />
			</MemoryRouter>,
		);

		fireEvent.change(screen.getByRole("combobox", { name: /search heritage sites/i }), {
			target: { value: "spodnje" },
		});
		fireEvent.click(await screen.findByRole("option", { name: /select spodnje pirnice/i }));

		await act(async () => {
			await new Promise((resolve) => window.setTimeout(resolve, FLY_TO_DIALOG_DELAY_MS + 50));
		});

		expect(await screen.findByText(/Dialog: Spodnje Pirnice - Cerkev Marijinega vnebovzetja/i)).toBeInTheDocument();
	});

	it("shows cold-start recovery banner with progress and retry action", async () => {
		const refetchMarkers = vi.fn();
		const refetchHealth = vi.fn();

		mockFns.useDataImpl = () => ({
			markersQuery: {
				error: new TypeError("Failed to fetch"),
				isFetching: false,
				failureCount: 2,
				refetch: refetchMarkers,
			},
			searchResultsQuery: { isFetching: false },
			siteDetailQuery: { isLoading: false },
			healthQuery: { error: null, isFetching: false, refetch: refetchHealth },
			markerSites: [],
			searchResults: [],
			selectedSite: null,
			healthStatus: {
				status: "ok",
				service: "heritage-map-backend",
				timestamp: "2026-03-10T18:00:00.000Z",
				datasetReady: false,
				datasetLoading: true,
				datasetProgressPct: 42,
			},
			shouldShowSearch: false,
			totalInView: 0,
			displayPointCount: 0,
			showMarkerOverlay: false,
		});

		render(
			<MemoryRouter
				initialEntries={["/"]}
				future={{
					v7_startTransition: true,
					v7_relativeSplatPath: true,
				}}
			>
				<HeritageMap />
			</MemoryRouter>,
		);

		expect(screen.getByText(/server waking up/i)).toBeInTheDocument();
		expect(screen.getByText(/startup progress: 42%/i)).toBeInTheDocument();
		expect(screen.getByText(/last update:/i)).toBeInTheDocument();
		expect(screen.queryByText(/unable to load heritage data/i)).not.toBeInTheDocument();

		fireEvent.click(screen.getByRole("button", { name: /retry now/i }));
		expect(refetchMarkers).toHaveBeenCalledTimes(1);
		expect(refetchHealth).toHaveBeenCalledTimes(1);
	});
});
