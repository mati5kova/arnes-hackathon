import { useLanguage } from "@/lib/i18n";
import type { OverlayKind, OverlayScale } from "@/types/overlays";
import { Layers } from "lucide-react";
import { OVERLAY_SCALE_GRADIENT } from "./overlay-style";

const OVERLAY_OPTIONS: OverlayKind[] = ["fire", "flood", "air", "landslide", "river"];

interface MapOverlayControlsProps {
	activeOverlay: OverlayKind | null;
	activeOverlayLabel?: string;
	activeScale?: OverlayScale;
	renderedItemCount?: number;
	renderedItemUnit?: "areas" | "cells" | "lines";
	sampleCount?: number;
	loading: boolean;
	hasError: boolean;
	onToggleOverlay: (kind: OverlayKind) => void;
}

const MapOverlayControls = ({
	activeOverlay,
	activeOverlayLabel,
	activeScale,
	renderedItemCount = 0,
	renderedItemUnit = "cells",
	sampleCount = 0,
	loading,
	hasError,
	onToggleOverlay,
}: MapOverlayControlsProps) => {
	const { m } = useLanguage();
	const leastLabel = activeScale?.leastLabel || m.map.overlay.leastLabel;
	const mostLabel = activeScale?.mostLabel || m.map.overlay.mostLabel;
	const showScale = activeOverlay !== "river";

	return (
		<div className="absolute right-4 top-3 z-[10] w-[16.5rem] rounded-lg border border-border bg-card/95 p-3 shadow-lg backdrop-blur-sm">
			<div className="flex items-center gap-2 text-sm font-semibold text-foreground">
				<Layers className="h-4 w-4 text-primary" aria-hidden="true" />
				<span>{m.map.overlay.title}</span>
			</div>

			<div className="mt-2 grid grid-cols-2 gap-1.5" role="group" aria-label={m.map.overlay.groupAria}>
				{OVERLAY_OPTIONS.map((kind) => {
					const isActive = activeOverlay === kind;
					const optionLabel = m.map.overlay.options[kind];
					return (
						<button
							key={kind}
							type="button"
							onClick={() => onToggleOverlay(kind)}
							aria-pressed={isActive}
							aria-label={`${optionLabel} ${m.map.overlay.overlayAriaSuffix}`}
							className={`rounded-md border px-2 py-1.5 text-xs font-medium transition-colors [transition-duration:120ms] ${
								isActive
									? "border-primary/60 bg-primary/10 text-foreground"
									: "border-border bg-background/80 text-muted-foreground hover:bg-secondary hover:text-foreground"
							}`}
						>
							{optionLabel}
						</button>
					);
				})}
			</div>

			<div className="mt-3 rounded-md border border-border/70 bg-background/85 px-2 py-2">
				<div className="mb-1 text-[11px] font-medium text-foreground" role="status" aria-live="polite">
					{activeOverlay
						? showScale
							? `${activeOverlayLabel || m.map.overlay.options[activeOverlay]} ${m.map.overlay.scaleSuffix}`
							: activeOverlayLabel || m.map.overlay.options[activeOverlay]
						: m.map.overlay.noneActive}
				</div>
				{showScale ? (
					<>
						<div className="flex items-center justify-between text-[10px] uppercase tracking-wide text-muted-foreground">
							<span>{leastLabel}</span>
							<span>{mostLabel}</span>
						</div>
						<div
							className="mt-1 h-1.5 rounded-full"
							style={{
								backgroundImage: OVERLAY_SCALE_GRADIENT,
								opacity: activeOverlay ? 1 : 0.35,
							}}
						/>
					</>
				) : (
					<div className="text-[11px] text-muted-foreground">{m.map.overlay.riverNote}</div>
				)}
			</div>

			{loading && <div className="mt-2 text-xs text-muted-foreground">{m.map.overlay.loading}</div>}
			{activeOverlay && !loading && !hasError && renderedItemCount > 0 && (
				<div className="mt-2 text-xs text-muted-foreground" role="status" aria-live="polite">
					{sampleCount > renderedItemCount
						? `${formatCompact(renderedItemCount)} ${m.map.overlay.units[renderedItemUnit]} ${m.map.overlay.viewRenderedSuffix} • ${formatCompact(sampleCount)} ${m.map.overlay.sourceItemsInView}`
						: `${formatCompact(renderedItemCount)} ${m.map.overlay.units[renderedItemUnit]} ${m.map.overlay.inViewSuffix}`}
				</div>
			)}
			{hasError && (
				<div className="mt-2 text-xs text-destructive" role="status" aria-live="polite">
					{m.map.overlay.error}
				</div>
			)}
		</div>
	);
};

export default MapOverlayControls;

function formatCompact(value: number) {
	return new Intl.NumberFormat(undefined, { notation: "compact", maximumFractionDigits: 1 }).format(value);
}
