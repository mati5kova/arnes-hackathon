import type { HeritageSiteSummary } from "@/types/heritage";
import L from "leaflet";
import { useEffect, useRef } from "react";
import { useMap, useMapEvents } from "react-leaflet";

interface FlyToSiteProps {
	site: HeritageSiteSummary | null;
	zoom?: number;
	onNoMovement?: () => void;
}

export const FlyToSite = ({ site, zoom, onNoMovement }: FlyToSiteProps) => {
	const map = useMap();

	useEffect(() => {
		if (!site) return;
		const targetZoom = zoom ?? map.getZoom();
		const targetCenter = L.latLng(site.lat, site.lng);
		const currentCenter = map.getCenter();
		const sameCenter = currentCenter.distanceTo(targetCenter) < 2;
		const sameZoom = Math.abs(map.getZoom() - targetZoom) < 0.01;
		if (sameCenter && sameZoom) {
			onNoMovement?.();
			return;
		}

		map.flyTo([site.lat, site.lng], targetZoom, {
			duration: 1.2,
			easeLinearity: 0.12,
		});
	}, [map, onNoMovement, site, zoom]);

	return null;
};

interface ViewportListenerProps {
	onViewportChange: (bbox: string, zoom: number) => void;
}

export const ViewportListener = ({ onViewportChange }: ViewportListenerProps) => {
	const lastViewportKeyRef = useRef<string>("");
	const map = useMapEvents({
		// Emit only when map movement settles to avoid duplicate backend requests per gesture.
		moveend: () => emitViewportChange(),
	});

	const emitViewportChange = () => {
		const nextBbox = getBoundsString(map);
		const nextZoom = map.getZoom();
		const viewportKey = `${nextBbox}|${nextZoom.toFixed(2)}`;
		if (viewportKey === lastViewportKeyRef.current) return;
		lastViewportKeyRef.current = viewportKey;
		onViewportChange(nextBbox, nextZoom);
	};

	useEffect(() => {
		emitViewportChange();
		// eslint-disable-next-line react-hooks/exhaustive-deps
	}, []);

	return null;
};

export const MapResizeInvalidator = () => {
	const map = useMap();

	useEffect(() => {
		const container = map.getContainer();
		let rafId: number | null = null;

		const observer = new ResizeObserver(() => {
			if (rafId !== null) {
				window.cancelAnimationFrame(rafId);
			}
			rafId = window.requestAnimationFrame(() => {
				map.invalidateSize({ pan: false, animate: false });
			});
		});

		observer.observe(container);

		return () => {
			if (rafId !== null) {
				window.cancelAnimationFrame(rafId);
			}
			observer.disconnect();
		};
	}, [map]);

	return null;
};

interface InitialViewportProps {
	bbox: string | null;
	zoom: number;
}

export const InitialViewport = ({ bbox, zoom }: InitialViewportProps) => {
	const map = useMap();
	const appliedRef = useRef(false);

	useEffect(() => {
		if (appliedRef.current) return;
		appliedRef.current = true;

		if (bbox) {
			const bounds = parseBoundsString(bbox);
			if (bounds) {
				map.fitBounds(bounds, { animate: false });
			}
		}

		if (Number.isFinite(zoom) && Math.abs(map.getZoom() - zoom) > 0.01) {
			map.setZoom(zoom, { animate: false });
		}
	}, [bbox, map, zoom]);

	return null;
};

function getBoundsString(map: L.Map) {
	const bounds = map.getBounds();
	const southWest = bounds.getSouthWest();
	const northEast = bounds.getNorthEast();
	return [southWest.lng, southWest.lat, northEast.lng, northEast.lat].map((value) => value.toFixed(4)).join(",");
}

function parseBoundsString(bbox: string): L.LatLngBoundsExpression | null {
	const parts = bbox.split(",").map((part) => Number(part.trim()));
	if (parts.length !== 4 || parts.some((value) => !Number.isFinite(value))) {
		return null;
	}

	const [minLng, minLat, maxLng, maxLat] = parts;
	if (minLng >= maxLng || minLat >= maxLat) {
		return null;
	}

	return [
		[minLat, minLng],
		[maxLat, maxLng],
	];
}
