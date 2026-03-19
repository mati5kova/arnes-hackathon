import type { HeritageSiteSummary } from "@/types/heritage";

const CLUSTER_MARKER_STYLE = {
	color: "#d97706",
	weight: 1,
	fillColor: "#f59e0b",
	fillOpacity: 0.75,
} as const;

const SITE_MARKER_STYLE = {
	color: "#1d4ed8",
	weight: 1,
	fillColor: "#2563eb",
	fillOpacity: 0.8,
} as const;

export function getMarkerStyle(site: HeritageSiteSummary) {
	return site.isCluster ? CLUSTER_MARKER_STYLE : SITE_MARKER_STYLE;
}

export function getMarkerRadius(site: HeritageSiteSummary) {
	if (!site.isCluster) return 5;
	const count = Math.max(2, site.clusterCount || 2);
	return Math.min(18, 6 + Math.log2(count) * 1.8);
}
