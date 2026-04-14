import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { HeritageSiteDetail } from "@/types/heritage";
import SiteDialog from "./SiteDialog";

function buildSite(overrides: Partial<HeritageSiteDetail> = {}): HeritageSiteDetail {
	return {
		id: "EID-42",
		registryId: "EID-42",
		name: "Detail Site",
		lat: 46.12345,
		lng: 14.98765,
		type: "site",
		protectionStatus: "protected",
		municipality: "Test Municipality",
		description: "Sample description",
		dating: "19. stol.",
		locationDescription: "Near the old bridge.",
		photoUrl: "https://example.com/photo.jpg",
		...overrides,
	};
}

describe("SiteDialog", () => {
	it("renders explicit detail fields above the hazard comparison grid", () => {
		render(
			<SiteDialog
				open
				site={buildSite({
					fireHazardOriginal: 0.0,
					floodHazardOriginal: 1.0,
					landslideHazardOriginal: 1.0,
					earthquakeHazardOriginal: 3.0,
					fireHazard: 0.0,
					floodHazard: 1.5,
					landslideHazard: 1.2,
					earthquakeHazard: 4.0,
				})}
				onOpenChange={vi.fn()}
			/>,
		);

		expect(screen.getByText("Dating")).toBeInTheDocument();
		expect(screen.getByText("19. stol.")).toBeInTheDocument();
		expect(screen.getByText("Location description")).toBeInTheDocument();
		expect(screen.getByText("Near the old bridge.")).toBeInTheDocument();
		expect(screen.getByRole("link", { name: "https://example.com/photo.jpg" })).toHaveAttribute(
			"href",
			"https://example.com/photo.jpg",
		);
		expect(screen.getByText("Hazard assessment")).toBeInTheDocument();
		expect(screen.getByText("Original")).toBeInTheDocument();
		expect(screen.getByText("Enriched")).toBeInTheDocument();
		expect(screen.getByText("Flood")).toBeInTheDocument();
		expect(screen.getByText("Fire")).toBeInTheDocument();
		expect(screen.getByText("Landslide")).toBeInTheDocument();
		expect(screen.getByText("Earthquake")).toBeInTheDocument();
		expect(screen.getAllByText("1.0").length).toBeGreaterThanOrEqual(2);
		expect(screen.getByText("1.5")).toBeInTheDocument();
		expect(screen.getByText("1.2")).toBeInTheDocument();
		expect(screen.getByText("4.0")).toBeInTheDocument();
	});

	it("does not render the removed additional data section", () => {
		render(
			<SiteDialog
				open
				site={buildSite({
					fireHazardOriginal: 0.0,
					fireHazard: 0.2,
				})}
				onOpenChange={vi.fn()}
			/>,
		);

		expect(screen.queryByText("Additional data")).not.toBeInTheDocument();
		expect(screen.getByText("Hazard assessment")).toBeInTheDocument();
	});
});
