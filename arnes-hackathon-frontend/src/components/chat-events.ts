import type { HeritageSiteSummary } from "@/types/heritage";

export const EXPLAIN_SITE_EVENT = "heritage:explain-site";

export interface ExplainSiteEventDetail {
    prompt: string;
}

function formatHazard(label: string, value?: number) {
    return typeof value === "number" ? `${label}: ${value.toFixed(1)}` : null;
}

export function buildExplainSitePrompt(site: HeritageSiteSummary) {
    const hazardParts = [
        formatHazard("poplava", site.floodHazard),
        formatHazard("pozar", site.fireHazard),
        formatHazard("plaz", site.landslideHazard),
        formatHazard("potres", site.earthquakeHazard),
        formatHazard("skupaj", site.combinedHazard),
    ].filter(Boolean);

    const contextParts = [
        `Povej mi več o enoti kulturne dediščine z imenom: "${site.name}".`,
        site.registryId ? `EID: ${site.registryId}.` : null,
        site.municipality ? `Obcina: ${site.municipality}.` : null,
        "Povej, katera tveganja najbolj izstopajo, kaj pomenijo prikazane ocene v tej aplikaciji in kako naj uporabnik razume te podatke. ",
    ];

    return contextParts.filter(Boolean).join(" ");
}
