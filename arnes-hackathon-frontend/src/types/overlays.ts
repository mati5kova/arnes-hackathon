export type OverlayKind = "fire" | "flood" | "air" | "landslide";

export interface OverlayCatalogItem {
    kind: OverlayKind;
    label: string;
    description: string;
}

export interface OverlayCatalogResponse {
    items: OverlayCatalogItem[];
}

export interface OverlayScaleStep {
    level: number;
    label: string;
    normalized: number;
}

export interface OverlayScale {
    direction: "low-to-high";
    leastLabel: string;
    mostLabel: string;
    steps: OverlayScaleStep[];
}

export interface OverlayCell {
    id: string;
    score: number;
    normalized: number;
    level: number;
    sampleCount: number;
    bounds: [number, number, number, number];
}

export interface OverlayArea {
    id: string;
    score: number;
    normalized: number;
    level: number;
    bounds: [number, number, number, number];
    ring: [number, number][];
}

export interface OverlayGridResponse {
    kind: OverlayKind;
    label: string;
    description: string;
    scale: OverlayScale;
    areas: OverlayArea[];
    cells: OverlayCell[];
    sampleCount: number;
    totalAvailableSamples: number;
    gridCellSizeDeg: number;
    generatedAt: number;
}
