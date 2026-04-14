import type { HeritageSiteDetail, HeritageSiteSummary } from "@/types/heritage";

export const EXPLAIN_SITE_EVENT = "heritage:explain-site";

export interface ExplainSiteEventDetail {
    prompt: string;
}

function formatHazard(label: string, value?: number) {
    return typeof value === "number" ? `${label}: ${value.toFixed(1)}` : null;
}

export function buildExplainSitePrompt(site: HeritageSiteSummary | HeritageSiteDetail) {
    const hazardParts = [
        formatHazard("poplava", "floodHazard" in site ? site.floodHazard : undefined),
        formatHazard("pozar", "fireHazard" in site ? site.fireHazard : undefined),
        formatHazard("plaz", "landslideHazard" in site ? site.landslideHazard : undefined),
        formatHazard("potres", "earthquakeHazard" in site ? site.earthquakeHazard : undefined),
    ].filter(Boolean);

    const contextParts = [
        `Povej mi več o enoti kulturne dediščine z imenom: "${site.name}".`,
        site.registryId ? `EID: ${site.registryId}.` : null,
        site.municipality ? `Obcina: ${site.municipality}.` : null,
        hazardParts.length > 0 ? `Prikazane ocene nevarnosti: ${hazardParts.join(", ")}.` : null,
        "Povej, katera tveganja najbolj izstopajo, kaj pomenijo prikazane ocene v tej aplikaciji in kako naj uporabnik razume te podatke. ",
    ];

    return contextParts.filter(Boolean).join(" ");
}
