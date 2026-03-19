import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import AppHeader from "./AppHeader";

const LAST_MAP_SEARCH_KEY = "heritage-last-map-search";

describe("AppHeader map-link preservation", () => {
	it("uses persisted map URL state when opening map from capabilities page", async () => {
		window.sessionStorage.setItem(
			LAST_MAP_SEARCH_KEY,
			"?bbox=13.0000,45.0000,16.0000,47.0000&zoom=8.00&search=ptuj",
		);

		render(
			<MemoryRouter
				initialEntries={["/capabilities"]}
				future={{
					v7_startTransition: true,
					v7_relativeSplatPath: true,
				}}
			>
				<AppHeader />
			</MemoryRouter>,
		);

		const mapLink = await screen.findByRole("link", { name: /open interactive map/i });
		expect(mapLink).toHaveAttribute("href", "/?bbox=13.0000,45.0000,16.0000,47.0000&zoom=8.00&search=ptuj");
	});

	it("persists current map URL state while on map page", async () => {
		render(
			<MemoryRouter
				initialEntries={["/?bbox=14.3700,46.1200,14.5000,46.1700&zoom=8.00&search=medvode"]}
				future={{
					v7_startTransition: true,
					v7_relativeSplatPath: true,
				}}
			>
				<AppHeader />
			</MemoryRouter>,
		);

		await waitFor(() => {
			expect(window.sessionStorage.getItem(LAST_MAP_SEARCH_KEY)).toBe(
				"?bbox=14.3700,46.1200,14.5000,46.1700&zoom=8.00&search=medvode",
			);
		});
	});
});
