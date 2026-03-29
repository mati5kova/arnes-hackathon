import AppHeader from "@/components/AppHeader";
import { useLanguage } from "@/lib/i18n";
import { ArrowRight, Clock3, Lightbulb, ShieldCheck } from "lucide-react";

const Capabilities = () => {
	const { m } = useLanguage();

	return (
		<div className="min-h-screen bg-[radial-gradient(ellipse_at_top_left,_hsl(var(--secondary))_0%,_hsl(var(--background))_55%)]">
			<AppHeader />
			<main className="mx-auto max-w-6xl px-6 pb-16 pt-10">
				<section className="mb-10 rounded-2xl border border-border/80 bg-card/80 p-8 shadow-sm backdrop-blur-sm">
					<div className="mb-3 inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary/10 px-3 py-1 text-xs font-medium text-primary">
						<ShieldCheck className="h-3.5 w-3.5" aria-hidden="true" />
						{m.capabilities.status}
					</div>
					<h2 className="text-3xl font-semibold tracking-tight text-foreground">
						{m.capabilities.title}
					</h2>
					<p className="mt-3 max-w-3xl text-sm leading-6 text-muted-foreground">
						{m.capabilities.description}
					</p>
				</section>

				<div className="grid gap-6 lg:grid-cols-3">
					<section className="rounded-xl border border-border bg-card/85 p-6 shadow-sm">
						<div className="mb-4 flex items-center gap-2 text-foreground">
							<ShieldCheck className="h-4 w-4 text-primary" aria-hidden="true" />
							<h3 className="text-lg font-semibold">{m.capabilities.currentTitle}</h3>
						</div>
						<ul className="space-y-3 text-sm text-muted-foreground">
							{m.capabilities.current.map((item) => (
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
							<h3 className="text-lg font-semibold">{m.capabilities.comingSoonTitle}</h3>
						</div>
						<ul className="space-y-3 text-sm text-muted-foreground">
							{m.capabilities.comingSoon.map((item) => (
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
							<h3 className="text-lg font-semibold">{m.capabilities.needsWorkTitle}</h3>
						</div>
						<ul className="space-y-3 text-sm text-muted-foreground">
							{m.capabilities.needsWork.map((item) => (
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
