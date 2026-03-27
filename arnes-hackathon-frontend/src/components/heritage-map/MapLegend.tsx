import { useLanguage } from "@/lib/i18n";

interface MapLegendProps {
	displayPointCount: number;
	totalInView: number;
}

const MapLegend = ({ displayPointCount, totalInView }: MapLegendProps) => {
	const { m } = useLanguage();

	return (
		<div
			className="absolute bottom-4 left-4 z-[10] w-72 rounded-lg border border-border bg-card/90 p-3 text-xs backdrop-blur-sm"
			role="note"
			aria-label={m.map.legend.containerAria}
		>
			<div className="mb-2 text-sm font-semibold text-foreground">{m.map.legend.title}</div>
			<div className="flex items-center gap-2 text-muted-foreground">
				<span className="inline-block h-3 w-3 rounded-full bg-primary" />
				<span>{m.map.legend.singleSite}</span>
			</div>
			<div className="mt-1 flex items-center gap-2 text-muted-foreground">
				<span className="inline-block h-3 w-3 rounded-full bg-amber-500" />
				<span>{m.map.legend.cluster}</span>
			</div>
			<div className="mt-2 border-t border-border pt-2 text-muted-foreground" role="status" aria-live="polite">
				<span>{`${displayPointCount} ${m.map.legend.pointSummary} ${totalInView} ${m.map.legend.siteSummary}`}</span>
			</div>
		</div>
	);
};

export default MapLegend;
