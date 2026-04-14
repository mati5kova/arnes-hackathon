import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { buildExplainSitePrompt, EXPLAIN_SITE_EVENT } from "@/components/chat-events";
import { useLanguage } from "@/lib/i18n";
import type { HeritageSiteDetail, HeritageSiteSummary } from "@/types/heritage";

interface SiteDialogProps {
	site: HeritageSiteSummary | HeritageSiteDetail | null;
	open: boolean;
	loading?: boolean;
	onOpenChange: (open: boolean) => void;
}

function formatHazardScore(value?: number) {
	return typeof value === "number" ? value.toFixed(1) : "-";
}

const SiteDialog = ({ site, open, loading = false, onOpenChange }: SiteDialogProps) => {
	const { m } = useLanguage();
	if (!site) return null;

	const detailedSite = hasDetailedFields(site) ? site : null;
	const detailRows = detailedSite
		? [
				{ label: m.siteDialog.dating, value: detailedSite.dating },
				{ label: m.siteDialog.locationDescription, value: detailedSite.locationDescription },
				{ label: m.siteDialog.municipality, value: detailedSite.municipality },
				{ label: m.siteDialog.protection, value: detailedSite.protectionStatus },
			].filter((row) => Boolean(row.value))
		: [];
	const hazardRows = [
		{
			label: m.siteDialog.hazardFlood,
			original: detailedSite?.floodHazardOriginal,
			enriched: detailedSite?.floodHazard,
		},
		{
			label: m.siteDialog.hazardFire,
			original: detailedSite?.fireHazardOriginal,
			enriched: detailedSite?.fireHazard,
		},
		{
			label: m.siteDialog.hazardLandslide,
			original: detailedSite?.landslideHazardOriginal,
			enriched: detailedSite?.landslideHazard,
		},
		{
			label: m.siteDialog.hazardEarthquake,
			original: detailedSite?.earthquakeHazardOriginal,
			enriched: detailedSite?.earthquakeHazard,
		},
	];
	const hasHazardComparison = hazardRows.some((row) => typeof row.original === "number" || typeof row.enriched === "number");

	const handleExplainSite = () => {
		if (typeof window === "undefined" || site.isCluster) return;
		window.dispatchEvent(
			new CustomEvent(EXPLAIN_SITE_EVENT, {
				detail: { prompt: buildExplainSitePrompt(site) },
			}),
		);
	};

	return (
		<Dialog open={open} onOpenChange={onOpenChange}>
			<DialogContent className="max-w-2xl">
				<DialogHeader>
					<DialogTitle>{site.name}</DialogTitle>
					<DialogDescription className="text-muted-foreground">
						{m.siteDialog.description}
					</DialogDescription>
				</DialogHeader>

				<div className="space-y-4 text-sm">
					
					<dl className="grid grid-cols-1 gap-2 text-muted-foreground md:grid-cols-2">
						{site.registryId && (
							<div>
								<dt className="font-medium text-foreground">EID</dt>
								<dd>{site.registryId}</dd>
							</div>
						)}
						{site.type && (
							<div>
								<dt className="font-medium text-foreground">{m.siteDialog.type}</dt>
								<dd>{site.type}</dd>
							</div>
						)}
						{site.municipality && (
							<div>
								<dt className="font-medium text-foreground">{m.siteDialog.municipality}</dt>
								<dd>{site.municipality}</dd>
							</div>
						)}
						{site.protectionStatus && (
							<div>
								<dt className="font-medium text-foreground">{m.siteDialog.protection}</dt>
								<dd>{site.protectionStatus}</dd>
							</div>
						)}
						<div className="md:col-span-2">
							<dt className="font-medium text-foreground">{m.siteDialog.coordinates}</dt>
							<dd>
								{site.lat.toFixed(5)}, {site.lng.toFixed(5)}
							</dd>
						</div>
					</dl>

					{detailedSite?.description && <p className="leading-relaxed text-foreground">{detailedSite.description}</p>}

					{loading && (
						<div
							className="rounded-md border border-border bg-secondary/30 px-3 py-2 text-muted-foreground"
							role="status"
							aria-live="polite"
						>
							{m.siteDialog.loading}
						</div>
					)}

					{(detailRows.length > 0 || detailedSite?.photoUrl || hasHazardComparison) && (
						<div className="space-y-2">
							<dl className="max-h-72 space-y-2 overflow-y-auto rounded-md border border-border p-3">
								{detailRows.map((row) => (
									<div key={row.label}>
										<dt className="font-medium text-foreground">{row.label}</dt>
										<dd className="text-muted-foreground">{row.value}</dd>
									</div>
								))}
                                {/* vse slike ki nimajo slike se koncajo z kf_eid.jpg namesto nekim dejanskim url-jem */}
								{detailedSite?.photoUrl && !detailedSite?.photoUrl.endsWith("kf_eid.jpg") && (
									<div>
										<dt className="font-medium text-foreground">{m.siteDialog.photo}</dt>
										<dd className="text-muted-foreground">
											<a
												href={detailedSite.photoUrl}
												target="_blank"
												rel="noreferrer"
												className="break-all underline-offset-2 hover:underline"
											>
												{detailedSite.photoUrl}
											</a>
										</dd>
									</div>
								)}
								{hasHazardComparison && (
									<div className={detailRows.length > 0 || detailedSite?.photoUrl ? "border-t border-border pt-3" : undefined}>
										<dt className="font-medium text-foreground">{m.siteDialog.hazardComparisonTitle}</dt>
										<dd className="mt-2">
											<div className="grid grid-cols-3 gap-2 text-muted-foreground">
												<div className="font-medium text-foreground" />
												<div className="font-medium text-foreground">{m.siteDialog.hazardOriginal}</div>
												<div className="font-medium text-foreground">{m.siteDialog.hazardEnriched}</div>
												{hazardRows.map((row) => (
													<div key={row.label} className="contents">
														<div>{row.label}</div>
														<div>{formatHazardScore(row.original)}</div>
														<div>{formatHazardScore(row.enriched)}</div>
													</div>
												))}
											</div>
										</dd>
									</div>
								)}
							</dl>
						</div>
					)}
					{!site.isCluster && (
						<div className="flex justify-end">
							<button
								type="button"
								onClick={handleExplainSite}
								className="rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground transition-opacity hover:opacity-90"
							>
								{m.siteDialog.explainAction}
							</button>
						</div>
					)}
				</div>
			</DialogContent>
		</Dialog>
	);
};

export default SiteDialog;

function hasDetailedFields(site: HeritageSiteSummary | HeritageSiteDetail): site is HeritageSiteDetail {
	return (
		"description" in site ||
		"dating" in site ||
		"locationDescription" in site ||
		"photoUrl" in site ||
		"fireHazard" in site ||
		"floodHazard" in site
	);
}
