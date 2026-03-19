import type { HeritageSiteSummary } from "@/types/heritage";
import { memo } from "react";
import { CircleMarker, Pane } from "react-leaflet";
import { getMarkerRadius, getMarkerStyle } from "./marker-utils";

interface MarkerLayerProps {
	markerSites: HeritageSiteSummary[];
	onMarkerClick: (site: HeritageSiteSummary) => void;
}

const MarkerLayer = ({ markerSites, onMarkerClick }: MarkerLayerProps) => {
	return (
		<Pane
			name="marker-layer"
			style={{
				opacity: 1,
				transition: "opacity 180ms ease",
			}}
		>
			{markerSites.map((site) => (
				<CircleMarker
					key={site.id}
					center={[site.lat, site.lng]}
					radius={getMarkerRadius(site)}
					pathOptions={getMarkerStyle(site)}
					eventHandlers={{
						click: () => onMarkerClick(site),
					}}
				/>
			))}
		</Pane>
	);
};

export default memo(MarkerLayer);
