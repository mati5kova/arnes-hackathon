import type { OverlayArea, OverlayCell } from "@/types/overlays";
import { memo, useMemo } from "react";
import { GeoJSON, Pane } from "react-leaflet";
import { getOverlayFillColor, getOverlayFillOpacity } from "./overlay-style";

interface OverlayLayerProps {
	layerKey: string;
	areas: OverlayArea[];
	cells: OverlayCell[];
}

const OverlayLayer = ({ layerKey, areas, cells }: OverlayLayerProps) => {
	const featureCollection = useMemo(() => {
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

	if (!featureCollection.features.length) return null;

	return (
		<Pane
			name="hazard-overlay-layer"
			style={{
				zIndex: 330,
				pointerEvents: "none",
			}}
		>
			<GeoJSON
				key={layerKey}
				data={featureCollection}
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
		</Pane>
	);
};

export default memo(OverlayLayer);
