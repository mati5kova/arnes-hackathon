import { useLanguage } from "@/lib/i18n";

interface MapStatusOverlaysProps {
	showMarkerOverlay: boolean;
	hasMarkerError: boolean;
	isRecovering?: boolean;
	recoveryMessage?: string;
	recoveryDetails?: string[];
	onRetryNow?: () => void;
	retryDisabled?: boolean;
}

const MapStatusOverlays = ({
	showMarkerOverlay,
	hasMarkerError,
	isRecovering = false,
	recoveryMessage,
	recoveryDetails = [],
	onRetryNow,
	retryDisabled = false,
}: MapStatusOverlaysProps) => {
	const { m } = useLanguage();
	const effectiveRecoveryMessage = recoveryMessage || m.map.recovery.retrying;

	return (
		<>
			{showMarkerOverlay && (
				<div className="pointer-events-none absolute inset-0 z-[9]" aria-hidden="true">
					<div className="absolute inset-0 bg-gradient-to-b from-transparent via-background/10 to-transparent" />
				</div>
			)}

			{isRecovering && (
				<div
					className="absolute right-4 top-36 z-[10] max-w-sm rounded-md border border-amber-500/35 bg-card/95 px-3 py-2 text-sm text-amber-700 shadow-md backdrop-blur-sm"
					role="status"
					aria-live="polite"
				>
					<div>{effectiveRecoveryMessage}</div>
					{recoveryDetails.length > 0 && (
						<div className="mt-1 text-xs text-amber-800/85">{recoveryDetails.join(" • ")}</div>
					)}
					<button
						type="button"
						onClick={onRetryNow}
						disabled={retryDisabled}
						className="mt-2 rounded border border-amber-600/40 px-2 py-1 text-xs text-amber-800 transition-colors [transition-duration:120ms] hover:bg-amber-100/60 disabled:cursor-not-allowed disabled:opacity-50"
					>
						{m.map.status.retryNow}
					</button>
				</div>
			)}

			{hasMarkerError && (
				<div
					className="absolute right-4 top-36 z-[10] max-w-sm rounded-md border border-destructive/30 bg-card/95 px-3 py-2 text-sm text-destructive shadow-md backdrop-blur-sm"
					role="alert"
					aria-live="assertive"
				>
					<div>{m.map.status.unableLoadData}</div>
					<button
						type="button"
						onClick={onRetryNow}
						disabled={retryDisabled}
						className="mt-2 rounded border border-destructive/35 px-2 py-1 text-xs text-destructive transition-colors [transition-duration:120ms] hover:bg-destructive/10 disabled:cursor-not-allowed disabled:opacity-50"
					>
						{m.map.status.retryNow}
					</button>
				</div>
			)}
		</>
	);
};

export default MapStatusOverlays;
