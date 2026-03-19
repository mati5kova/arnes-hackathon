interface MapLegendProps {
	displayPointCount: number;
	totalInView: number;
}

const MapLegend = ({ displayPointCount, totalInView }: MapLegendProps) => {
	return (
		<div
			className="absolute bottom-4 left-4 z-[10] w-72 rounded-lg border border-border bg-card/90 p-3 text-xs backdrop-blur-sm"
			role="note"
			aria-label="Map legend"
		>
			<div className="mb-2 text-sm font-semibold text-foreground">Map legend</div>
			<div className="flex items-center gap-2 text-muted-foreground">
				<span className="inline-block h-3 w-3 rounded-full bg-primary" />
				<span>Single heritage site</span>
			</div>
			<div className="mt-1 flex items-center gap-2 text-muted-foreground">
				<span className="inline-block h-3 w-3 rounded-full bg-amber-500" />
				<span>Cluster (click to zoom in)</span>
			</div>
			<div className="mt-2 border-t border-border pt-2 text-muted-foreground" role="status" aria-live="polite">
				<span>{`${displayPointCount} map points representing ${totalInView} heritage sites`}</span>
			</div>
		</div>
	);
};

export default MapLegend;
