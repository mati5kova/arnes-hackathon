import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import type { HeritageSiteDetail, HeritageSiteSummary } from "@/types/heritage";

interface SiteDialogProps {
	site: HeritageSiteSummary | HeritageSiteDetail | null;
	open: boolean;
	loading?: boolean;
	onOpenChange: (open: boolean) => void;
}

const SiteDialog = ({ site, open, loading = false, onOpenChange }: SiteDialogProps) => {
	if (!site) return null;

	const detailFields = "detailFields" in site ? site.detailFields : [];

	return (
		<Dialog open={open} onOpenChange={onOpenChange}>
			<DialogContent className="max-w-2xl">
				<DialogHeader>
					<DialogTitle>{site.name}</DialogTitle>
					<DialogDescription className="text-muted-foreground">
						Details for this cultural heritage site, including location and metadata from the registry.
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
								<dt className="font-medium text-foreground">Type</dt>
								<dd>{site.type}</dd>
							</div>
						)}
						{site.municipality && (
							<div>
								<dt className="font-medium text-foreground">Municipality</dt>
								<dd>{site.municipality}</dd>
							</div>
						)}
						{site.protectionStatus && (
							<div>
								<dt className="font-medium text-foreground">Protection</dt>
								<dd>{site.protectionStatus}</dd>
							</div>
						)}
						<div className="md:col-span-2">
							<dt className="font-medium text-foreground">Coordinates</dt>
							<dd>
								{site.lat.toFixed(5)}, {site.lng.toFixed(5)}
							</dd>
						</div>
					</dl>

					{site.description && <p className="leading-relaxed text-foreground">{site.description}</p>}

					{loading && (
						<div
							className="rounded-md border border-border bg-secondary/30 px-3 py-2 text-muted-foreground"
							role="status"
							aria-live="polite"
						>
							Loading full site details...
						</div>
					)}

					{detailFields.length > 0 && (
						<div className="space-y-2">
							<div className="font-medium text-foreground">Additional data</div>
							<dl className="max-h-72 space-y-2 overflow-y-auto rounded-md border border-border p-3">
								{detailFields.map((field) => (
									<div key={`${field.label}-${field.value}`}>
										<dt className="font-medium text-foreground">{field.label}</dt>
										<dd className="text-muted-foreground">{field.value}</dd>
									</div>
								))}
							</dl>
						</div>
					)}
				</div>
			</DialogContent>
		</Dialog>
	);
};

export default SiteDialog;
