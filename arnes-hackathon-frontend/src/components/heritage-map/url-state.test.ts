import { afterEach, describe, expect, it, vi } from "vitest";

describe("url-state reload behavior", () => {
	afterEach(() => {
		vi.restoreAllMocks();
		vi.resetModules();
		window.sessionStorage.clear();
	});

	it("resets map URL state once on browser reload", async () => {
		vi.spyOn(window.performance, "getEntriesByType").mockReturnValue([
			{ entryType: "navigation", type: "reload" } as PerformanceNavigationTiming,
		]);

		const module = await import("./url-state");
		expect(module.shouldIgnoreMapUrlStateOnMount()).toBe(true);

		module.markMapUrlStateMountHandled();
		expect(module.shouldIgnoreMapUrlStateOnMount()).toBe(false);
	});

	it("keeps map URL state on in-app navigation", async () => {
		vi.spyOn(window.performance, "getEntriesByType").mockReturnValue([
			{ entryType: "navigation", type: "navigate" } as PerformanceNavigationTiming,
		]);

		const module = await import("./url-state");
		expect(module.shouldIgnoreMapUrlStateOnMount()).toBe(false);
	});

	it("parses valid overlay from URL state", async () => {
		const module = await import("./url-state");
		const parsed = module.parseMapUrlState(new URLSearchParams("overlay=flood"));
		expect(parsed.overlay).toBe("flood");
	});

	it("parses river overlay from URL state", async () => {
		const module = await import("./url-state");
		const parsed = module.parseMapUrlState(new URLSearchParams("overlay=river"));
		expect(parsed.overlay).toBe("river");
	});

	it("ignores invalid overlay in URL state", async () => {
		const module = await import("./url-state");
		const parsed = module.parseMapUrlState(new URLSearchParams("overlay=unknown"));
		expect(parsed.overlay).toBeNull();
	});
});
