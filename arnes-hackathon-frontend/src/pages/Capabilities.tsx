import AppHeader from "@/components/AppHeader";
import { ArrowRight, Clock3, Lightbulb, ShieldCheck } from "lucide-react";

const currentCapabilities = [
	"Interactive map with viewport-based loading and clustering.",
	"Search heritage sites by name and metadata with keyboard navigation.",
	"Site detail dialog with registry metadata and coordinates.",
	"Shareable URL state for current map area, zoom, and search term.",
];

const comingSoon = [
	"Automated risk scoring and classification for each heritage site.",
	"Risk driver breakdowns with explainable score components.",
	"Historical trend views and scenario-based projections.",
	"Workflow-ready AI assistant connected to live risk analysis.",
];

const needsWorkingOn = [
	"Risk model calibration and validation against real events.",
	"Expanded test coverage for map interactions and query-state sync.",
	"Production deployment hardening and monitoring dashboards.",
	"Role-based collaboration and export/reporting workflows.",
];

const Capabilities = () => {
	return (
		<div className="min-h-screen bg-[radial-gradient(ellipse_at_top_left,_hsl(var(--secondary))_0%,_hsl(var(--background))_55%)]">
			<AppHeader />
			<main className="mx-auto max-w-6xl px-6 pb-16 pt-10">
				<section className="mb-10 rounded-2xl border border-border/80 bg-card/80 p-8 shadow-sm backdrop-blur-sm">
					<div className="mb-3 inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary/10 px-3 py-1 text-xs font-medium text-primary">
						<ShieldCheck className="h-3.5 w-3.5" aria-hidden="true" />
						Product Status
					</div>
					<h2 className="text-3xl font-semibold tracking-tight text-foreground">
						Current capabilities and near-term roadmap
					</h2>
					<p className="mt-3 max-w-3xl text-sm leading-6 text-muted-foreground">
						This page gives a transparent snapshot of what the app can do today, what is planned next, and
						which parts need focused engineering work before production rollout.
					</p>
				</section>

				<div className="grid gap-6 lg:grid-cols-3">
					<section className="rounded-xl border border-border bg-card/85 p-6 shadow-sm">
						<div className="mb-4 flex items-center gap-2 text-foreground">
							<ShieldCheck className="h-4 w-4 text-primary" aria-hidden="true" />
							<h3 className="text-lg font-semibold">Current capabilities</h3>
						</div>
						<ul className="space-y-3 text-sm text-muted-foreground">
							{currentCapabilities.map((item) => (
								<li key={item} className="flex items-start gap-2">
									<ArrowRight
										className="mt-0.5 h-3.5 w-3.5 shrink-0 text-primary/80"
										aria-hidden="true"
									/>
									<span>{item}</span>
								</li>
							))}
						</ul>
					</section>

					<section className="rounded-xl border border-border bg-card/85 p-6 shadow-sm">
						<div className="mb-4 flex items-center gap-2 text-foreground">
							<Clock3 className="h-4 w-4 text-primary" aria-hidden="true" />
							<h3 className="text-lg font-semibold">Coming soon</h3>
						</div>
						<ul className="space-y-3 text-sm text-muted-foreground">
							{comingSoon.map((item) => (
								<li key={item} className="flex items-start gap-2">
									<ArrowRight
										className="mt-0.5 h-3.5 w-3.5 shrink-0 text-primary/80"
										aria-hidden="true"
									/>
									<span>{item}</span>
								</li>
							))}
						</ul>
					</section>

					<section className="rounded-xl border border-border bg-card/85 p-6 shadow-sm">
						<div className="mb-4 flex items-center gap-2 text-foreground">
							<Lightbulb className="h-4 w-4 text-primary" aria-hidden="true" />
							<h3 className="text-lg font-semibold">Needs working on</h3>
						</div>
						<ul className="space-y-3 text-sm text-muted-foreground">
							{needsWorkingOn.map((item) => (
								<li key={item} className="flex items-start gap-2">
									<ArrowRight
										className="mt-0.5 h-3.5 w-3.5 shrink-0 text-primary/80"
										aria-hidden="true"
									/>
									<span>{item}</span>
								</li>
							))}
						</ul>
					</section>
				</div>
			</main>
		</div>
	);
};

export default Capabilities;
