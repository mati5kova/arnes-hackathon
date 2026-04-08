import type { OverlayArea, OverlayCell, OverlayLine } from "@/types/overlays";
import { memo, useMemo } from "react";
import { GeoJSON, Pane } from "react-leaflet";
import { getOverlayFillColor, getOverlayFillOpacity } from "./overlay-style";

interface OverlayLayerProps {
	layerKey: string;
	areas: OverlayArea[];
	cells: OverlayCell[];
	lines: OverlayLine[];
}

const OverlayLayer = ({ layerKey, areas, cells, lines }: OverlayLayerProps) => {
	const areaFeatureCollection = useMemo(() => {
		const features: Array<{
			type: "Feature";
			id: string;
			properties: { normalized: number };
			geometry: {
				type: "Polygon";
				coordinates: number[][][];
			};
		}> = [];

		for (const area of areas) {
			if (area.ring.length < 4) continue;
			features.push({
				type: "Feature",
				id: area.id,
				properties: { normalized: area.normalized },
				geometry: {
					type: "Polygon",
					coordinates: [area.ring.map(([lng, lat]) => [lng, lat])],
				},
			});
		}

		for (const cell of cells) {
			const [minLng, minLat, maxLng, maxLat] = cell.bounds;
			features.push({
				type: "Feature",
				id: cell.id,
				properties: { normalized: cell.normalized },
				geometry: {
					type: "Polygon",
					coordinates: [[[minLng, minLat], [maxLng, minLat], [maxLng, maxLat], [minLng, maxLat], [minLng, minLat]]],
				},
			});
		}

		features.sort((left, right) => left.properties.normalized - right.properties.normalized);

		return {
			type: "FeatureCollection" as const,
			features,
		};
	}, [areas, cells]);

	const lineFeatureCollection = useMemo(() => {
		const features: Array<{
			type: "Feature";
			id: string;
			properties: Record<string, never>;
			geometry:
				| {
						type: "LineString";
						coordinates: number[][];
				  }
				| {
						type: "MultiLineString";
						coordinates: number[][][];
				  };
		}> = [];

		for (const line of lines) {
			if (!line.paths.length) continue;
			const filteredPaths = line.paths.filter((path) => path.length >= 2).map((path) => path.map(([lng, lat]) => [lng, lat]));
			if (!filteredPaths.length) continue;
			features.push({
				type: "Feature",
				id: line.id,
				properties: {},
				geometry:
					filteredPaths.length === 1
						? { type: "LineString", coordinates: filteredPaths[0] }
						: { type: "MultiLineString", coordinates: filteredPaths },
			});
		}

		return {
			type: "FeatureCollection" as const,
			features,
		};
	}, [lines]);

	if (!areaFeatureCollection.features.length && !lineFeatureCollection.features.length) return null;

	return (
		<Pane
			name="hazard-overlay-layer"
			style={{
				zIndex: 330,
				pointerEvents: "none",
			}}
		>
			{areaFeatureCollection.features.length > 0 && (
				<GeoJSON
					key={`${layerKey}:areas`}
					data={areaFeatureCollection}
					interactive={false}
					style={(feature) => {
						const normalized = typeof feature?.properties?.normalized === "number" ? feature.properties.normalized : 0;
						return {
							stroke: false,
							fill: true,
							fillColor: getOverlayFillColor(normalized),
							fillOpacity: getOverlayFillOpacity(normalized),
						};
					}}
				/>
			)}
			{lineFeatureCollection.features.length > 0 && (
				<GeoJSON
					key={`${layerKey}:lines`}
					data={lineFeatureCollection}
					interactive={false}
					style={() => ({
						stroke: true,
						color: "#2563eb",
						weight: 2,
						opacity: 0.65,
					})}
				/>
			)}
		</Pane>
	);
};

export default memo(OverlayLayer);
