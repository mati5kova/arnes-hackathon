const COLOR_STOPS = [
	{ at: 0.0, color: "#2b8a3e" },
	{ at: 0.45, color: "#0c8599" },
	{ at: 0.75, color: "#1d4ed8" },
	{ at: 1.0, color: "#c92a2a" },
] as const;

export const OVERLAY_SCALE_GRADIENT =
	"linear-gradient(90deg, #2b8a3e 0%, #0c8599 45%, #1d4ed8 75%, #c92a2a 100%)";

export function getOverlayFillColor(normalized: number) {
	const clamped = clamp(normalized, 0, 1);

	for (let index = 0; index < COLOR_STOPS.length - 1; index += 1) {
		const left = COLOR_STOPS[index];
		const right = COLOR_STOPS[index + 1];
		if (clamped > right.at) continue;

		const segmentSpan = Math.max(0.0001, right.at - left.at);
		const segmentRatio = clamp((clamped - left.at) / segmentSpan, 0, 1);
		return mixHexColors(left.color, right.color, segmentRatio);
	}

	return COLOR_STOPS[COLOR_STOPS.length - 1].color;
}

export function getOverlayFillOpacity(normalized: number) {
	const clamped = clamp(normalized, 0, 1);
	return 0.12 + clamped * 0.22;
}

function mixHexColors(leftHex: string, rightHex: string, ratio: number) {
	const left = hexToRgb(leftHex);
	const right = hexToRgb(rightHex);
	const mixed = {
		r: Math.round(left.r + (right.r - left.r) * ratio),
		g: Math.round(left.g + (right.g - left.g) * ratio),
		b: Math.round(left.b + (right.b - left.b) * ratio),
	};
	return `rgb(${mixed.r}, ${mixed.g}, ${mixed.b})`;
}

function hexToRgb(hex: string) {
	const normalized = hex.replace("#", "");
	if (normalized.length !== 6) {
		return { r: 0, g: 0, b: 0 };
	}
	return {
		r: parseInt(normalized.slice(0, 2), 16),
		g: parseInt(normalized.slice(2, 4), 16),
		b: parseInt(normalized.slice(4, 6), 16),
	};
}

function clamp(value: number, min: number, max: number) {
	return Math.min(max, Math.max(min, value));
}
