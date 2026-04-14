from __future__ import annotations

import json
import math
import re
import unicodedata
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import geopandas as gpd
import numpy as np
from shapely.geometry import Point
from shapely.strtree import STRtree

BASE_DIR = Path(__file__).resolve().parent
INPUT_PATH = BASE_DIR / "Data" / "kd_visine.geojson"
OUTPUT_PATH = BASE_DIR / "Data" / "kd_z_nevarnost_enriched_verified.geojson"
FLOOD_FREQUENT_PATH = BASE_DIR / "Data_Processing" / "DRSV_OPKP_POGOSTE_POPL" / "DRSV_OPKP_POGOSTE_POPL.shp"
FLOOD_RARE_PATH = BASE_DIR / "Data_Processing" / "DRSV_OPKP_REDKE_POPL" / "DRSV_OPKP_REDKE_POPL.shp"
FLOOD_VERY_RARE_PATH = BASE_DIR / "Data_Processing" / "DRSV_OPKP_ZR_POPL" / "DRSV_OPKP_ZR_POPL.shp"
RIVER_PATH = BASE_DIR / "Data_Processing" / "DRSV_HIDRO5_LIN_PV" / "HIDRO5_LIN_PV_TIPTV1_2.shp"
METRIC_CRS = "EPSG:3794"
FLOOD_MODEL_VERSION = "drsv-flood-river-terrain-v2"

GENERAL_SOURCE_STRINGS = [
    "Metapodatki registra RNPD in opisna polja",
    "Uradne opozorilne karte poplav DRSV (pogoste, redke, zelo redke)",
    "Uradno hidrografsko omrezje DRSV HIDRO5_LIN_PV",
    "Visina lokacije iz kd_visine.geojson",
    "Kontekst terena ocenjen iz Z najblizjega vodotoka in uradnih poplavnih poligonov (DEM raster ni v repozitoriju)",
    "ARSO potresna nevarnost (2021), GeoZS karta plazov 1:25k, ARSO/URSZR kontekst pozarne nevarnosti",
]

FIELD_MAP = {
    "pozar_ocena_popravljena": "pozar",
    "poplave_ocena_popravljena": "poplave",
    "potres_ocena_popravljena": "potres",
    "plazovi_ocena_popravljena": "plazovi",
}

SITE_LEVEL_FEATURES = (
    "znotraj_obmocja_pogostih_poplav",
    "znotraj_obmocja_redkih_poplav",
    "znotraj_obmocja_zelo_redkih_poplav",
    "razdalja_do_reke_m",
    "razdalja_do_poplavnega_obmocja_m",
    "visina_m",
    "visina_najblizje_reke_m",
    "relativna_visina_nad_najblizjo_reko_m",
    "lokalni_naklon_stopinje",
    "lega_terena",
)

OUTPUT_FIELD_NAMES = {
    "predominant_material": "prevladujoci_material",
    "material_confidence": "zanesljivost_materiala",
    "fire_danger_revised": "pozar_ocena_popravljena",
    "flood_danger_revised": "poplave_ocena_popravljena",
    "earthquake_danger_revised": "potres_ocena_popravljena",
    "landslide_danger_revised": "plazovi_ocena_popravljena",
    "elevation_m": "visina_m",
    "inside_frequent_flood_zone": "znotraj_obmocja_pogostih_poplav",
    "inside_rare_flood_zone": "znotraj_obmocja_redkih_poplav",
    "inside_very_rare_flood_zone": "znotraj_obmocja_zelo_redkih_poplav",
    "distance_to_river_m": "razdalja_do_reke_m",
    "distance_to_flood_zone_m": "razdalja_do_poplavnega_obmocja_m",
    "nearest_river_name": "ime_najblizje_reke",
    "nearest_river_type": "tip_najblizje_reke",
    "nearest_river_flow_regime": "rezim_toka_najblizje_reke",
    "nearest_river_kind": "vrsta_najblizje_reke",
    "nearest_river_elevation_m": "visina_najblizje_reke_m",
    "relative_height_above_nearest_river_m": "relativna_visina_nad_najblizjo_reko_m",
    "local_slope_deg": "lokalni_naklon_stopinje",
    "terrain_position": "lega_terena",
    "river_distance_band": "pas_razdalje_do_reke",
    "flood_zone_distance_band": "pas_razdalje_do_poplavnega_obmocja",
    "terrain_context_confidence": "zanesljivost_konteksta_terena",
    "terrain_context_method": "metoda_konteksta_terena",
    "flood_official_score": "uradna_ocena_poplav",
    "flood_proximity_score": "ocena_blizine_poplav",
    "flood_hazard_band": "pas_poplavne_nevarnosti",
    "flood_reasoning": "utemeljitev_poplav",
    "flood_model_version": "razlicica_modela_poplav",
    "danger_revision_reasoning": "utemeljitev_popravka_nevarnosti",
    "verification_status": "status_preveritve",
    "verification_notes": "opombe_preveritve",
    "sources": "viri",
    "research_confidence": "zanesljivost_raziskave",
}

MATERIAL_LABELS = {
    "stone/marble": "kamen/marmor",
    "metal and concrete": "kovina in beton",
    "reinforced concrete": "armirani beton",
    "stone and concrete infrastructure": "kamnita in betonska infrastruktura",
    "earthworks and stone": "zemeljski nasipi in kamen",
    "mixed masonry and wood": "mesana zidana in lesena gradnja",
    "wood": "les",
    "brick masonry": "opecno zidovje",
    "stone masonry": "kamnito zidovje",
    "wood and mixed rural fabric": "les in mesano podezelsko tkivo",
    "vegetation and masonry features": "vegetacija in zidani elementi",
    "mixed heritage fabric": "mesano dediscinsko tkivo",
    "mixed masonry": "mesano zidovje",
}

MATERIAL_REASON_LABELS = {
    "material explicit in memorial marker wording": "material je izrecno naveden v poimenovanju spominskega obelezja",
    "explicit metal and concrete wording": "izrecno omenjena kovina in beton",
    "infrastructure wording with metal cues": "opis infrastrukture vsebuje namige za kovino",
    "explicit concrete or postwar construction wording": "izrecno omenjen beton ali povojna gradnja",
    "infrastructure wording dominates": "opis infrastrukture prevladuje",
    "archaeological earthworks and masonry remains": "arheoloski zemeljski nasipi in zidani ostanki",
    "explicit timber and masonry cues": "izrecno omenjena lesena in zidana gradnja",
    "explicit timber wording": "izrecno omenjen les",
    "explicit brick/masonry wording": "izrecno omenjena opeka oziroma zidovje",
    "explicit stone or marble wording": "izrecno omenjen kamen ali marmor",
    "building type usually masonry and description supports it": "tip objekta je obicajno zidan, opis pa to podpira",
    "explicit masonry wording": "izrecno omenjeno zidovje",
    "highland rural ensemble with wooden structures": "visokogorski podezelski sklop z lesenimi objekti",
    "park/garden ensemble with limited structural specificity": "parkovni oziroma vrtni sklop z omejeno konstrukcijsko dolocnostjo",
    "ensemble or settlement description is broader than one structure": "opis sklopa ali naselja je sirsi od posamezne strukture",
    "building record but material only weakly implied": "evidenca stavbe, vendar je material le sibko nakazan",
    "material largely inferred from broad type": "material je v veliki meri sklepan iz splosne vrste",
}

CUE_LABELS = {
    "timber construction": "lesena konstrukcija",
    "mixed timber elements": "mesani leseni elementi",
    "non-combustible remains/marker": "negorljivi ostanki oziroma oznaka",
    "mostly open-air archaeological fabric": "pretežno odprta arheoloska struktura",
    "documented fire history": "dokumentirana zgodovina pozarov",
    "Primorska wildfire exposure": "izpostavljenost pozarom v Primorski",
    "highly combustible farm/outbuilding type": "zelo gorljiv gospodarski oziroma pomocni objekt",
    "light timber structures": "lahke lesene konstrukcije",
    "mixed traditional fabric": "mesana tradicionalna struktura",
    "older unreinforced masonry likely": "verjetno starejse nearmirano zidovje",
    "stone fabric": "kamnita struktura",
    "heavier built fabric": "tezja grajena struktura",
    "engineered structure": "inzenirska konstrukcija",
    "rigid infrastructure fabric": "toga infrastrukturna struktura",
    "open-air remains": "ostanki na prostem",
    "ensemble with vulnerable traditional structures": "sklop z ranljivimi tradicionalnimi strukturami",
    "tower/heavy masonry elements": "stolpni oziroma tezki zidani elementi",
    "documented earthquake damage/history": "dokumentirana potresna skoda oziroma zgodovina",
    "explicit landslide/rockfall wording": "izrecno omenjen plaz oziroma podor",
    "slope-edge siting": "lega na robu pobocja",
    "steep terrain wording": "opis strmega terena",
    "river-side terrain appears steep": "teren ob reki deluje strm",
    "river plain/terrace context": "kontekst recne ravnice oziroma terase",
    "site intersects the frequent official flood polygon": "lokacija seka uradni poligon pogostih poplav",
    "site intersects the rare official flood polygon": "lokacija seka uradni poligon redkih poplav",
    "site intersects the very-rare official flood polygon": "lokacija seka uradni poligon zelo redkih poplav",
    "outside official polygons, flood score derived conservatively from river distance, flood-zone distance, and relative height above the nearest river": "zunaj uradnih poligonov, ocena poplav je previdno izpeljana iz razdalje do reke, razdalje do poplavnega obmocja in relativne visine nad najblizjo reko",
    "register wording independently mentions floodplain or island context": "besedilo registra samostojno omenja poplavno ravnico ali otoski kontekst",
    "register wording confirms elevated terrain": "besedilo registra potrjuje dvignjen teren",
}

DISTANCE_BAND_LABELS = {
    "adjacent": "tik_ob",
    "near": "blizu",
    "close": "blizje",
    "intermediate": "srednje_dalec",
    "far": "dalec",
    "remote": "zelo_dalec",
    "inside": "znotraj",
    "touching": "v_stiku",
    "very_near": "zelo_blizu",
    "moderate": "zmerno_dalec",
    "unknown": "neznano",
}

TERRAIN_POSITION_LABELS = {
    "active_floodplain": "aktivna_poplavna_ravnica",
    "floodplain": "poplavna_ravnica",
    "valley_floor": "dolinsko_dno",
    "low_terrace": "nizka_terasa",
    "elevated_terrace": "dvignjena_terasa",
    "ridge_or_high_ground": "greben_ali_visji_teren",
    "valley_side": "dolinsko_pobocje",
    "upland": "visji_svet",
    "gentle_hillside": "polozno_pobocje",
}

FLOOD_HAZARD_BAND_LABELS = {
    "very_high": "zelo_visoka",
    "high": "visoka",
    "moderate": "zmerna",
    "low": "nizka",
    "very_low": "zelo_nizka",
}

VERIFICATION_STATUS_LABELS = {
    "verified": "preverjeno",
    "partially_verified": "delno_preverjeno",
    "weakly_verified": "sibko_preverjeno",
}


@dataclass(slots=True)
class FloodContext:
    inside_frequent_flood_zone: bool
    inside_rare_flood_zone: bool
    inside_very_rare_flood_zone: bool
    distance_to_river_m: float | None
    distance_to_flood_zone_m: float | None
    elevation_m: float | None
    nearest_river_elevation_m: float | None
    relative_height_above_nearest_river_m: float | None
    local_slope_deg: float | None
    terrain_position: str
    nearest_river_name: str | None
    nearest_river_type: str | None
    nearest_river_flow_regime: str | None
    nearest_river_kind: str | None
    river_distance_band: str
    flood_zone_distance_band: str
    terrain_context_confidence: float
    terrain_context_method: str
    flood_official_score: float
    flood_proximity_score: float
    flood_hazard_band: str
    flood_reasoning: str


def localized_field(name: str) -> str:
    return OUTPUT_FIELD_NAMES.get(name, name)


def localized_material(value: str) -> str:
    return MATERIAL_LABELS.get(value, value)


def localized_material_reason(value: str) -> str:
    return MATERIAL_REASON_LABELS.get(value, value)


def localized_cue(value: str) -> str:
    return CUE_LABELS.get(value, value)


def localized_distance_band(value: str) -> str:
    return DISTANCE_BAND_LABELS.get(value, value)


def localized_terrain_position(value: str) -> str:
    return TERRAIN_POSITION_LABELS.get(value, value)


def localized_flood_band(value: str) -> str:
    return FLOOD_HAZARD_BAND_LABELS.get(value, value)


def localized_verification_status(value: str) -> str:
    return VERIFICATION_STATUS_LABELS.get(value, value)


def normalize(value: object) -> str:
    text = str(value or "").lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", text).strip()


def compile_any(*parts: str) -> re.Pattern[str]:
    return re.compile("|".join(parts))


WOOD_RE = compile_any(
    r"\blesen\w*",
    r"\bles\b",
    r"\bbrun\w*",
    r"\bhlod\w*",
    r"\bdeske?\b",
    r"\bskodl\w*",
    r"\bkozolec\w*",
    r"\btoplar\w*",
    r"\bbarak\w*",
    r"\bbajt\w*",
    r"\bskedenj\w*",
    r"\bkoca\b",
    r"\bkoc\w*",
    r"\bkolib\w*",
)
MASONRY_RE = compile_any(
    r"\bzidan\w*",
    r"\bkamnit\w*",
    r"\bkamen\w*",
    r"\bkamn\w*",
    r"\bobzid\w*",
    r"\bportal\w*",
    r"\bobokan\w*",
    r"\btuf\w*",
    r"\bapnen\w*",
    r"\bmalta\b",
)
BRICK_RE = compile_any(r"\bopek\w*", r"\bbrick\b")
STONE_MARBLE_RE = compile_any(r"\bmarmor\w*", r"\bgranit\w*", r"\bkamnosek\w*")
CONCRETE_RE = compile_any(r"\bbeton\w*", r"\barmiranobeton\w*", r"\bmontaz\w*", r"\bhitrogradnj\w*")
METAL_RE = compile_any(r"\bjekl\w*", r"\bzelezn\w*", r"\bkovin\w*", r"\blitozelezn\w*")
INFRA_RE = compile_any(r"\bcesta\b", r"\bmost\b", r"\bviadukt\w*", r"\bpredor\w*", r"\bobelisk\w*")
ARCH_RE = compile_any(r"\barheolosk\w*", r"\bgradi\w*", r"\bnekropol\w*", r"\bgrobisc\w*", r"\bgomil\w*", r"\brefugij\w*")
LANDSCAPE_RE = compile_any(r"\bkulturna krajina\b", r"\bplanina\b", r"\bpark\b", r"\bvrt\b", r"\bnaselje\b", r"\bvas\b", r"\bmestno jedro\b")
CHURCH_RE = compile_any(r"\bcerk\w*", r"\bkapel\w*", r"\bsamostan\w*", r"\bkartuzij\w*", r"\bzvonik\w*")
TOWER_RE = compile_any(r"\bstolp\w*", r"\bzvonik\w*", r"\bbergfrid\w*")
HEAVY_BUILDING_RE = compile_any(r"\bgrad\b", r"\bdvorec\w*", r"\bvila\b")
PLAQUE_RE = compile_any(r"\bspominska plosc\w*", r"\bplosc\w*", r"\bspomenik\w*", r"\bznamenje\b", r"\brazpelo\b")
RUIN_RE = compile_any(r"\brusevin\w*", r"\blokacija\b", r"\bostaline\b", r"\btemelj\w*")

FIRE_HISTORY_RE = compile_any(r"\bpozar\w*", r"\bpogorel\w*", r"\bzgorel\w*", r"\bunicen\w* v pozar")
FLOOD_RE = compile_any(r"\bpoplav\w*")
RIVER_RE = compile_any(
    r"\brek\w*",
    r"\bpotok\w*",
    r"\bbreg\w*",
    r"\bsotocj\w*",
    r"\bjezer\w*",
    r"\bbarj\w*",
    r"\bpolj\w*",
    r"\botok\b",
    r"\bdolin\w*",
    r"\bgrap\w*",
    r"\bravnic\w*",
    r"\bsava\b",
    r"\bdrava\b",
    r"\bmura\b",
    r"\bkrka\b",
    r"\bsoca\b",
    r"\bsora\b",
    r"\bsotla\b",
    r"\bsavinj\w*",
)
HIGH_GROUND_RE = compile_any(
    r"\bna vrhu\b",
    r"\bvrh\b",
    r"\bslemen\w*",
    r"\bgreben\w*",
    r"\bplanot\w*",
    r"\bvisokogorsk\w*",
    r"\bsedl\w*",
)
STRONG_FLOOD_RE = compile_any(
    r"\bpoplavna ravnic\w*",
    r"\bna otoku\b",
    r"\brobu barja\b",
    r"\brobu .* jezera\b",
    r"\bob reki\b",
    r"\bob sotocj\w*",
)
SLOPE_RE = compile_any(
    r"\bpoboc\w*",
    r"\bstrm\w*",
    r"\bgri\w*",
    r"\bvzpetin\w*",
    r"\bgrap\w*",
    r"\bklif\w*",
    r"\bpod robom\b",
    r"\bhrib\w*",
    r"\brob\w*",
)
LANDSLIDE_RE = compile_any(r"\bplaz\w*", r"\bpodor\w*")
QUAKE_RE = compile_any(r"\bpotres\w*")
WILDFIRE_CONTEXT_RE = compile_any(r"\bgozd\w*", r"\bvinograd\w*", r"\bkras\w*", r"\bplanina\b")


def has(pattern: re.Pattern[str], text: str) -> bool:
    return bool(pattern.search(text))


def clamp(value: float, lower: float, upper: float) -> float:
    return min(max(value, lower), upper)


def rounded_score(value: float) -> float:
    return round(float(value) + 1e-9, 1)


def rounded_metric(value: float | None) -> float | None:
    if value is None or not math.isfinite(value):
        return None
    return round(float(value) + 1e-9, 1)


def rounded_confidence(value: float) -> float:
    return round(float(value) + 1e-9, 2)


def limit_delta(value: float, original: float) -> float:
    value = clamp(value, original - 1.0, original + 1.0)
    value = clamp(value, 0.0, 4.0)
    return rounded_score(value)


def clamp_score(value: float) -> float:
    return rounded_score(clamp(value, 0.0, 4.0))


def safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return None
    if math.isfinite(number):
        return number
    return None


def percentile_band(value: float | None, thresholds: list[tuple[float, str]], default: str) -> str:
    if value is None:
        return default
    for upper, label in thresholds:
        if value <= upper:
            return label
    return thresholds[-1][1] if thresholds else default


def piecewise_linear(value: float | None, points: list[tuple[float, float]], *, default: float = 0.0) -> float:
    if value is None or not points:
        return default
    if value <= points[0][0]:
        return points[0][1]
    for left, right in zip(points, points[1:]):
        x1, y1 = left
        x2, y2 = right
        if value <= x2:
            if x2 == x1:
                return y2
            ratio = (value - x1) / (x2 - x1)
            return y1 + ratio * (y2 - y1)
    return points[-1][1]


def material_from_properties(props: dict[str, object]) -> tuple[str, float, str]:
    core_text = normalize(" ".join(str(props.get(k) or "") for k in ("IME", "GESLA", "OPIS", "TIP", "ZVRST")))
    location_text = normalize(props.get("LOKACIJAOPIS"))
    text = " ".join(part for part in (core_text, location_text) if part)
    zvrst = normalize(props.get("ZVRST"))
    tip = normalize(props.get("TIP"))

    wood = has(WOOD_RE, text)
    masonry = has(MASONRY_RE, text)
    brick = has(BRICK_RE, text)
    stone_marble = has(STONE_MARBLE_RE, text)
    concrete = has(CONCRETE_RE, text)
    metal = has(METAL_RE, text)
    infra = has(INFRA_RE, core_text) or zvrst == "drugi objekti in naprave"
    arch = has(ARCH_RE, core_text) or "arheoloska" in zvrst or "arheoloska" in tip
    landscape = zvrst in {"kulturna krajina", "parki in vrtovi", "naselja in njihovi deli", "stavbe s parki ali z vrtovi"} or has(LANDSCAPE_RE, core_text)
    plaque = has(PLAQUE_RE, core_text)
    church = has(CHURCH_RE, core_text) or "sakralna" in tip

    if plaque and (stone_marble or masonry or "plosca" in text or "znamenje" in text or "razpelo" in text):
        return "stone/marble", 0.88 if stone_marble or "marmor" in text else 0.8, "material explicit in memorial marker wording"
    if metal and concrete:
        return "metal and concrete", 0.8, "explicit metal and concrete wording"
    if metal and infra:
        return "metal and concrete", 0.76, "infrastructure wording with metal cues"
    if concrete:
        return "reinforced concrete", 0.78, "explicit concrete or postwar construction wording"
    if infra:
        if metal:
            return "metal and concrete", 0.76, "infrastructure wording with metal cues"
        return "stone and concrete infrastructure", 0.7, "infrastructure wording dominates"
    if arch:
        return "earthworks and stone", 0.76 if masonry or "obzid" in text or "nasip" in text else 0.64, "archaeological earthworks and masonry remains"
    if wood and (masonry or brick or church):
        return "mixed masonry and wood", 0.84 if masonry else 0.76, "explicit timber and masonry cues"
    if wood:
        return "wood", 0.9 if "lesen" in text or "lesena" in text or "leseni" in text else 0.82, "explicit timber wording"
    if brick and masonry:
        return "brick masonry", 0.82, "explicit brick/masonry wording"
    if stone_marble:
        return "stone/marble", 0.86, "explicit stone or marble wording"
    if church or has(TOWER_RE, text) or "grad" in text or "dvorec" in text or "vila" in text:
        return "stone masonry", 0.74 if masonry else 0.66, "building type usually masonry and description supports it"
    if masonry:
        return "stone masonry", 0.76, "explicit masonry wording"
    if landscape:
        if wood and "planina" in text:
            return "wood and mixed rural fabric", 0.7, "highland rural ensemble with wooden structures"
        if zvrst == "parki in vrtovi":
            return "vegetation and masonry features", 0.58, "park/garden ensemble with limited structural specificity"
        return "mixed heritage fabric", 0.56, "ensemble or settlement description is broader than one structure"
    if "stavbe" in zvrst or "stavbna" in tip:
        return "mixed masonry", 0.55, "building record but material only weakly implied"
    return "mixed heritage fabric", 0.45, "material largely inferred from broad type"


def infer_fire(props: dict[str, object], material: str, text: str) -> tuple[float, list[str]]:
    original = float(props.get("pozar") or 0.0)
    adjustment = 0.0
    cues: list[str] = []

    if material == "wood":
        adjustment += 0.3
        cues.append("timber construction")
    elif material == "mixed masonry and wood":
        adjustment += 0.2
        cues.append("mixed timber elements")
    elif material in {"stone/marble", "stone masonry", "brick masonry"} and (has(PLAQUE_RE, text) or has(RUIN_RE, text)):
        adjustment -= 0.2
        cues.append("non-combustible remains/marker")
    elif material == "earthworks and stone":
        adjustment -= 0.2
        cues.append("mostly open-air archaeological fabric")

    if has(FIRE_HISTORY_RE, text):
        adjustment += 0.2
        cues.append("documented fire history")
    if has(WILDFIRE_CONTEXT_RE, text) and normalize(props.get("regija")) in {"goriska", "obalno-kraska"}:
        adjustment += 0.1
        cues.append("Primorska wildfire exposure")
    if "kozolec" in text or "toplar" in text or "baraka" in text or "bajt" in text or "skedenj" in text:
        adjustment += 0.2
        cues.append("highly combustible farm/outbuilding type")

    return limit_delta(original + adjustment, original), cues


def infer_earthquake(props: dict[str, object], material: str, text: str) -> tuple[float, list[str]]:
    original = float(props.get("potres") or 0.0)
    score = 0.2
    cues: list[str] = []

    if material == "wood":
        score = 0.4
        cues.append("light timber structures")
    elif material == "mixed masonry and wood":
        score = 0.6
        cues.append("mixed traditional fabric")
    elif material in {"stone masonry", "brick masonry", "mixed masonry"}:
        score = 0.7
        cues.append("older unreinforced masonry likely")
    elif material == "stone/marble":
        score = 0.3 if has(PLAQUE_RE, text) else 0.7
        cues.append("stone fabric")
    elif material == "reinforced concrete":
        score = 0.5
        cues.append("heavier built fabric")
    elif material == "metal and concrete":
        score = 0.4
        cues.append("engineered structure")
    elif material == "stone and concrete infrastructure":
        score = 0.3
        cues.append("rigid infrastructure fabric")
    elif material == "earthworks and stone":
        score = 0.3 if has(RUIN_RE, text) else 0.2
        cues.append("open-air remains")
    elif material in {"mixed heritage fabric", "wood and mixed rural fabric", "vegetation and masonry features"}:
        score = 0.5
        cues.append("ensemble with vulnerable traditional structures")

    if has(TOWER_RE, text) or has(HEAVY_BUILDING_RE, text) or has(CHURCH_RE, text):
        score += 0.1
        cues.append("tower/heavy masonry elements")
    if has(QUAKE_RE, text):
        score += 0.2
        cues.append("documented earthquake damage/history")

    return limit_delta(score, original), cues


def infer_landslide(props: dict[str, object], text: str, flood_context: FloodContext) -> tuple[float, list[str]]:
    original = float(props.get("plazovi") or 0.0)
    adjustment = 0.0
    cues: list[str] = []

    steep = has(SLOPE_RE, text)
    very_steep = "grapa" in text or "strm" in text or "pod robom" in text or "klif" in text or "sedl" in text
    flat_terrain = flood_context.terrain_position in {"active_floodplain", "floodplain", "valley_floor", "low_terrace"}

    if has(LANDSLIDE_RE, text):
        adjustment += 0.4 if original <= 2.0 else 0.2
        cues.append("explicit landslide/rockfall wording")
    elif steep:
        adjustment += 0.2 if original <= 2.0 else 0.1
        cues.append("slope-edge siting")
    if very_steep:
        adjustment += 0.1
        if "slope-edge siting" not in cues:
            cues.append("steep terrain wording")
    if flood_context.local_slope_deg is not None and flood_context.local_slope_deg >= 12.0:
        adjustment += 0.1
        cues.append("river-side terrain appears steep")
    if flat_terrain and original >= 1.0:
        adjustment -= 0.1
        cues.append("river plain/terrace context")

    return limit_delta(original + adjustment, original), cues


def classify_distance_band(distance_m: float | None, *, river: bool) -> str:
    if river:
        return percentile_band(
            distance_m,
            [
                (25.0, "adjacent"),
                (100.0, "near"),
                (250.0, "close"),
                (500.0, "intermediate"),
                (1000.0, "far"),
                (2500.0, "remote"),
            ],
            "unknown",
        )
    return percentile_band(
        distance_m,
        [
            (0.0, "inside"),
            (25.0, "touching"),
            (100.0, "very_near"),
            (250.0, "near"),
            (500.0, "moderate"),
            (1000.0, "far"),
        ],
        "unknown",
    )


def classify_terrain_position(
    *,
    inside_frequent: bool,
    inside_rare: bool,
    inside_very_rare: bool,
    distance_to_river_m: float | None,
    relative_height_above_river_m: float | None,
    local_slope_deg: float | None,
    text: str,
) -> str:
    if inside_frequent:
        return "active_floodplain"
    if inside_rare or inside_very_rare:
        return "floodplain"

    dist = distance_to_river_m if distance_to_river_m is not None else 999999.0
    rel = relative_height_above_river_m if relative_height_above_river_m is not None else 999999.0
    slope = local_slope_deg if local_slope_deg is not None else 0.0

    if dist <= 150.0 and rel <= 3.0:
        return "valley_floor"
    if dist <= 300.0 and rel <= 10.0:
        return "low_terrace"
    if dist <= 600.0 and rel <= 25.0:
        return "elevated_terrace"
    if rel >= 60.0 or (rel >= 35.0 and slope >= 8.0) or (has(HIGH_GROUND_RE, text) and rel >= 20.0):
        return "ridge_or_high_ground"
    if dist <= 1200.0 and rel >= 20.0 and slope >= 4.0:
        return "valley_side"
    if dist > 1200.0 and rel >= 20.0:
        return "upland"
    return "gentle_hillside"


def terrain_confidence(
    *,
    elevation_m: float | None,
    nearest_river_elevation_m: float | None,
    nearest_river_name: str | None,
    nearest_river_kind: str | None,
) -> float:
    confidence = 0.55
    if elevation_m is not None:
        confidence += 0.1
    if nearest_river_elevation_m is not None:
        confidence += 0.15
    if nearest_river_kind == "vodotok":
        confidence += 0.05
    if nearest_river_name:
        confidence += 0.02
    return rounded_confidence(clamp(confidence, 0.45, 0.9))


def official_flood_score(*, inside_frequent: bool, inside_rare: bool, inside_very_rare: bool) -> float:
    if inside_frequent:
        return 4.0
    if inside_rare:
        return 3.2
    if inside_very_rare:
        return 2.4
    return 0.0


def flood_proximity_score(
    *,
    distance_to_river_m: float | None,
    relative_height_above_river_m: float | None,
    local_slope_deg: float | None,
    distance_to_flood_zone_m: float | None,
    nearest_river_kind: str | None,
) -> float:
    distance_factor = piecewise_linear(
        distance_to_river_m,
        [
            (0.0, 1.0),
            (25.0, 0.98),
            (50.0, 0.95),
            (100.0, 0.85),
            (200.0, 0.7),
            (350.0, 0.55),
            (500.0, 0.42),
            (750.0, 0.28),
            (1000.0, 0.18),
            (1500.0, 0.1),
            (2500.0, 0.0),
        ],
    )
    relative_height_factor = piecewise_linear(
        relative_height_above_river_m,
        [
            (-10.0, 1.25),
            (0.0, 1.18),
            (2.0, 1.08),
            (5.0, 1.0),
            (10.0, 0.82),
            (20.0, 0.55),
            (35.0, 0.3),
            (50.0, 0.15),
            (75.0, 0.06),
            (100.0, 0.03),
        ],
    )
    flood_zone_bonus = piecewise_linear(
        distance_to_flood_zone_m,
        [
            (0.0, 1.0),
            (25.0, 0.8),
            (50.0, 0.65),
            (100.0, 0.45),
            (200.0, 0.25),
            (400.0, 0.1),
            (800.0, 0.0),
        ],
    )

    slope_bonus = 0.0
    if local_slope_deg is not None:
        if local_slope_deg < 1.5:
            slope_bonus = 0.35
        elif local_slope_deg < 3.0:
            slope_bonus = 0.25
        elif local_slope_deg < 6.0:
            slope_bonus = 0.1
        elif local_slope_deg >= 15.0:
            slope_bonus = -0.3
        elif local_slope_deg >= 10.0:
            slope_bonus = -0.15

    base = 2.6 * distance_factor * relative_height_factor
    score = base + flood_zone_bonus + slope_bonus
    if nearest_river_kind == "razbremenilni kanal":
        score *= 0.95
    return clamp(score, 0.0, 3.4)


def outside_polygon_flood_score(flood_context: FloodContext) -> float:
    score = flood_context.flood_proximity_score
    river_distance = flood_context.distance_to_river_m
    flood_distance = flood_context.distance_to_flood_zone_m
    relative_height = flood_context.relative_height_above_nearest_river_m
    local_slope = flood_context.local_slope_deg
    terrain = flood_context.terrain_position

    dist = river_distance if river_distance is not None else 999999.0
    flood_dist = flood_distance if flood_distance is not None else 999999.0
    rel = relative_height if relative_height is not None else 999999.0
    slope = local_slope if local_slope is not None else 0.0

    # Elevated terrain should only retain meaningful flood risk when it is also very near an official flood-zone edge.
    if terrain in {"ridge_or_high_ground", "upland"} or rel >= 30.0:
        score = min(score, 1.2 if flood_dist <= 100.0 else 0.8)
    elif terrain == "valley_side" or rel >= 20.0 or slope >= 8.0:
        score = min(score, 1.7 if flood_dist <= 50.0 else 1.1)
    elif terrain == "elevated_terrace" or rel >= 10.0:
        score = min(score, 2.1 if flood_dist <= 25.0 else 1.5)

    if flood_dist <= 10.0 and rel <= 5.0:
        score = max(score, 2.8 if dist <= 300.0 else 2.5)
    elif flood_dist <= 25.0 and rel <= 5.0:
        score = max(score, 2.5 if dist <= 500.0 else 2.3)
    elif flood_dist <= 100.0 and rel <= 10.0:
        score = max(score, 1.9 if terrain in {"valley_floor", "low_terrace", "floodplain"} else 1.6)
    elif dist <= 50.0 and rel <= 2.0 and slope < 3.0:
        score = max(score, 2.3)
    elif dist <= 100.0 and rel <= 5.0 and slope < 5.0:
        score = max(score, 1.9)
    elif dist <= 200.0 and rel <= 10.0 and terrain in {"valley_floor", "low_terrace"}:
        score = max(score, 1.5)
    else:
        if terrain in {"ridge_or_high_ground", "upland"}:
            score = min(score, 0.8)
        elif dist > 500.0 and flood_dist > 100.0:
            score = min(score, 0.8)
        elif dist > 200.0 and rel > 10.0:
            score = min(score, 1.2)

    return clamp(score, 0.0, 3.0)


def classify_flood_hazard_band(score: float) -> str:
    if score >= 3.5:
        return "very_high"
    if score >= 2.5:
        return "high"
    if score >= 1.5:
        return "moderate"
    if score >= 0.75:
        return "low"
    return "very_low"


def infer_flood(props: dict[str, object], text: str, flood_context: FloodContext) -> tuple[float, list[str], str]:
    official = flood_context.flood_official_score
    proximity = flood_context.flood_proximity_score

    if flood_context.inside_frequent_flood_zone:
        score = 4.0
        cues = ["site intersects the frequent official flood polygon"]
    elif flood_context.inside_rare_flood_zone:
        score = max(3.2, min(3.8, 2.9 + 0.25 * proximity))
        cues = ["site intersects the rare official flood polygon"]
    elif flood_context.inside_very_rare_flood_zone:
        score = max(2.4, min(3.4, 1.9 + 0.4 * proximity))
        cues = ["site intersects the very-rare official flood polygon"]
    else:
        score = outside_polygon_flood_score(flood_context)
        cues = ["outside official polygons, flood score derived conservatively from river distance, flood-zone distance, and relative height above the nearest river"]

    if has(STRONG_FLOOD_RE, text) and flood_context.distance_to_river_m is not None and flood_context.distance_to_river_m <= 500.0:
        score += 0.1
        cues.append("register wording independently mentions floodplain or island context")
    if has(HIGH_GROUND_RE, text) and (flood_context.relative_height_above_nearest_river_m or 0.0) >= 20.0:
        score -= 0.1
        cues.append("register wording confirms elevated terrain")

    score = clamp_score(score)
    band = classify_flood_hazard_band(score)
    reasoning = build_flood_reasoning(flood_context=flood_context, score=score, band=band)
    return score, cues, reasoning


def build_flood_reasoning(*, flood_context: FloodContext, score: float, band: str) -> str:
    river_name = flood_context.nearest_river_name or "najblizji evidentirani vodotok"
    river_distance = "neznano" if flood_context.distance_to_river_m is None else f"{flood_context.distance_to_river_m:.1f} m"
    flood_distance = "neznano" if flood_context.distance_to_flood_zone_m is None else f"{flood_context.distance_to_flood_zone_m:.1f} m"
    rel_height = (
        "neznano"
        if flood_context.relative_height_above_nearest_river_m is None
        else f"{flood_context.relative_height_above_nearest_river_m:.1f} m"
    )
    localized_band = localized_flood_band(band)
    localized_terrain = localized_terrain_position(flood_context.terrain_position)

    if flood_context.inside_frequent_flood_zone:
        return (
            f"Lokacija lezi znotraj uradnega poligona pogostih poplav; najblizji recni kontekst je {river_name} na razdalji {river_distance}, "
            f"pri cemer je lokacija {rel_height} nad vzorceno gladino reke. Koncni pas poplavne nevarnosti: {localized_band}."
        )
    if flood_context.inside_rare_flood_zone:
        return (
            f"Lokacija lezi znotraj uradnega poligona redkih poplav; najblizji recni kontekst je {river_name} na razdalji {river_distance}, "
            f"lokacija pa stoji {rel_height} nad vzorceno gladino reke. Koncni pas poplavne nevarnosti: {localized_band}."
        )
    if flood_context.inside_very_rare_flood_zone:
        return (
            f"Lokacija lezi znotraj uradnega poligona zelo redkih poplav; najblizji recni kontekst je {river_name} na razdalji {river_distance}, "
            f"lokacija pa stoji {rel_height} nad vzorceno gladino reke. Koncni pas poplavne nevarnosti: {localized_band}."
        )
    return (
        f"Lokacija lezi zunaj uradnih poplavnih poligonov; najblizji recni kontekst je {river_name} na razdalji {river_distance}, "
        f"najblizje evidentirano poplavno obmocje je oddaljeno {flood_distance}, lokacija pa stoji {rel_height} nad vzorceno gladino reke, "
        f"teren pa je razvrscen kot {localized_terrain}. Koncni pas poplavne nevarnosti: {localized_band}."
    )


def verification_status(
    props: dict[str, object],
    material_confidence: float,
    reason_hint: str,
    flood_context: FloodContext,
) -> tuple[str, float]:
    official_source_count = 0
    if props.get("QR") or props.get("POVEZAVA1"):
        official_source_count += 1
    if props.get("PREDPISHTTP"):
        official_source_count += 1
    if props.get("PHOTOURL"):
        official_source_count += 1

    research_conf = 0.34 + 0.08 * official_source_count + 0.22 * material_confidence + 0.28 * flood_context.terrain_context_confidence
    if flood_context.inside_frequent_flood_zone or flood_context.inside_rare_flood_zone or flood_context.inside_very_rare_flood_zone:
        research_conf += 0.05
    if "explicit" in reason_hint or "documented" in reason_hint:
        research_conf += 0.03
    research_conf = rounded_confidence(clamp(research_conf, 0.4, 0.96))

    if official_source_count >= 2 and material_confidence >= 0.7 and flood_context.terrain_context_confidence >= 0.72:
        return "verified", research_conf
    if official_source_count >= 1 and flood_context.terrain_context_confidence >= 0.62:
        return "partially_verified", research_conf
    return "weakly_verified", research_conf


def build_sources(props: dict[str, object]) -> list[str]:
    sources: list[str] = []
    if props.get("QR"):
        sources.append(str(props["QR"]))
    elif props.get("POVEZAVA1"):
        sources.append(str(props["POVEZAVA1"]))
    sources.extend(GENERAL_SOURCE_STRINGS)
    return sources[:6]


def reasoning_sentence(
    material: str,
    fire: float,
    flood: float,
    quake: float,
    slide: float,
    props: dict[str, object],
    fire_cues: list[str],
    flood_cues: list[str],
    quake_cues: list[str],
    slide_cues: list[str],
    flood_context: FloodContext,
) -> str:
    localized_material_label = localized_material(material)
    original = {
        "fire": float(props.get("pozar") or 0.0),
        "flood": float(props.get("poplave") or 0.0),
        "earthquake": float(props.get("potres") or 0.0),
        "landslide": float(props.get("plazovi") or 0.0),
    }
    revisions: list[str] = []
    if abs(fire - original["fire"]) >= 0.2:
        revisions.append("pozarna ocena je prilagojena zaradi " + localized_cue(fire_cues[0] if fire_cues else "timber construction"))
    if abs(flood - original["flood"]) >= 0.2:
        revisions.append("poplavna ocena je ponovno modelirana iz uradnih poligonov, razdalje do reke in relativne lege terena")
    if abs(quake - original["earthquake"]) >= 0.2:
        revisions.append(
            "potresna ocena je zmerno povisana zaradi "
            + localized_cue(quake_cues[0] if quake_cues else "ensemble with vulnerable traditional structures")
        )
    if abs(slide - original["landslide"]) >= 0.2:
        revisions.append("ocena plazov je prilagojena zaradi " + localized_cue(slide_cues[0] if slide_cues else "steep terrain wording"))

    flood_fragment = (
        f"razdalje do najblizje reke {flood_context.distance_to_river_m:.1f} m in relativne visine {flood_context.relative_height_above_nearest_river_m:.1f} m"
        if flood_context.distance_to_river_m is not None and flood_context.relative_height_above_nearest_river_m is not None
        else "relativnega terena glede na reko, ocenjenega iz uradne hidrografije"
    )

    if revisions:
        return f"Uradni registrski zapis podpira material {localized_material_label}; {'; '.join(revisions[:3])}; poplavni kontekst uporablja {flood_fragment}."
    return f"Uradni registrski zapis podpira material {localized_material_label}; popravljene ocene ostajajo blizu izhodisca, poplavni kontekst pa uporablja {flood_fragment}."


def verification_notes(material_reason: str, status: str, flood_context: FloodContext) -> str:
    material_reason = localized_material_reason(material_reason) if material_reason else "je sklepan"
    terrain_note = (
        f"lega terena {localized_terrain_position(flood_context.terrain_position)}, "
        f"zanesljivost {flood_context.terrain_context_confidence:.2f}"
    )
    if status == "verified":
        return f"Identiteta je zasidrana v uradnih registrskih povezavah; osnova za material: {material_reason}; poplavni kontekst uporablja uradne poligone in hidrografijo z opombo: {terrain_note}."
    if status == "partially_verified":
        return f"Identiteta je zasidrana v uradnih registrskih metapodatkih; osnova za material: {material_reason}; poplavni kontekst uporablja uradne poligone in hidrografijo z opombo: {terrain_note}."
    return f"Identiteta verjetno izhaja iz uradnih registrskih metapodatkov; material je vecinoma sklepan, ker je opis sirok; poplavni kontekst se vedno uporablja uradne poligone in hidrografijo z opombo: {terrain_note}."


def build_boolean_flags(points: np.ndarray, polygons: np.ndarray) -> np.ndarray:
    flags = np.zeros(len(points), dtype=bool)
    if len(points) == 0 or len(polygons) == 0:
        return flags
    tree = STRtree(polygons)
    pairs = tree.query(points, predicate="intersects")
    if len(pairs) == 0:
        return flags
    flags[np.unique(pairs[0])] = True
    return flags


def nearest_indexes_and_distances(points: np.ndarray, geometries: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    indexes = np.full(len(points), -1, dtype=int)
    distances = np.full(len(points), np.nan, dtype=float)
    if len(points) == 0 or len(geometries) == 0:
        return indexes, distances
    tree = STRtree(geometries)
    pairs, dists = tree.query_nearest(points, all_matches=False, return_distance=True)
    if len(pairs) == 0:
        return indexes, distances
    indexes[pairs[0]] = pairs[1]
    distances[pairs[0]] = dists
    return indexes, distances


def load_flood_polygons(path: Path) -> gpd.GeoDataFrame:
    gdf = gpd.read_file(path, columns=[])
    gdf = gdf.to_crs(METRIC_CRS)
    gdf = gdf.loc[gdf.geometry.notna() & ~gdf.geometry.is_empty, ["geometry"]].reset_index(drop=True)
    return gdf


def load_rivers() -> gpd.GeoDataFrame:
    rivers = gpd.read_file(
        RIVER_PATH,
        columns=["IME", "VRSTA_IME", "TIPTV_IM", "STALN_IM", "OS_IME", "POTEK_IM"],
    )
    rivers = rivers.to_crs(METRIC_CRS)
    rivers = rivers.loc[rivers.geometry.notna() & ~rivers.geometry.is_empty].copy()
    rivers = rivers.loc[
        (rivers["VRSTA_IME"] == "tekoča voda")
        & (rivers["POTEK_IM"] == "da - potek je znan")
        & (rivers["OS_IME"] == "dejanska")
    ].reset_index(drop=True)
    return rivers[["IME", "VRSTA_IME", "TIPTV_IM", "STALN_IM", "geometry"]]


def clean_river_name(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text or text.startswith("0000 "):
        return None
    if text.startswith("0000 ("):
        return None
    return text


def nearest_river_elevation(point: Point, geometry: Any) -> float | None:
    try:
        nearest_point = geometry.interpolate(geometry.project(point))
    except Exception:
        return None
    if not getattr(nearest_point, "has_z", False):
        return None
    z_value = getattr(nearest_point, "z", None)
    return float(z_value) if z_value is not None and math.isfinite(float(z_value)) else None


def compute_geospatial_contexts(features: list[dict[str, Any]]) -> list[FloodContext]:
    sites_wgs84 = gpd.GeoDataFrame.from_features(features, crs="EPSG:4326")
    sites_metric = sites_wgs84.to_crs(METRIC_CRS)
    site_points = np.asarray(sites_metric.geometry.values, dtype=object)

    frequent = load_flood_polygons(FLOOD_FREQUENT_PATH)
    rare = load_flood_polygons(FLOOD_RARE_PATH)
    very_rare = load_flood_polygons(FLOOD_VERY_RARE_PATH)
    all_flood = gpd.GeoDataFrame(
        geometry=gpd.GeoSeries(
            pd_concat_geometries([frequent.geometry, rare.geometry, very_rare.geometry]),
            crs=METRIC_CRS,
        )
    )

    frequent_flags = build_boolean_flags(site_points, np.asarray(frequent.geometry.values, dtype=object))
    rare_flags = build_boolean_flags(site_points, np.asarray(rare.geometry.values, dtype=object))
    very_rare_flags = build_boolean_flags(site_points, np.asarray(very_rare.geometry.values, dtype=object))

    _, flood_distances = nearest_indexes_and_distances(site_points, np.asarray(all_flood.geometry.values, dtype=object))

    rivers = load_rivers()
    river_geometries = np.asarray(rivers.geometry.values, dtype=object)
    river_indexes, river_distances = nearest_indexes_and_distances(site_points, river_geometries)

    contexts: list[FloodContext] = []
    for idx, feature in enumerate(features):
        props = feature.get("properties", {})
        text = normalize(" ".join(str(props.get(k) or "") for k in ("LOKACIJAOPIS", "OPIS", "IME", "GESLA")))
        point = sites_metric.geometry.iloc[idx]
        elevation_m = safe_float(props.get("z"))

        nearest_idx = int(river_indexes[idx])
        river_distance_m = float(river_distances[idx]) if math.isfinite(float(river_distances[idx])) else None
        nearest_river_name = None
        nearest_river_type = None
        nearest_river_flow_regime = None
        nearest_river_kind = None
        river_elevation_m = None

        if nearest_idx >= 0:
            nearest_row = rivers.iloc[nearest_idx]
            nearest_river_name = clean_river_name(nearest_row.get("IME"))
            nearest_river_type = str(nearest_row.get("VRSTA_IME") or "").strip() or None
            nearest_river_kind = str(nearest_row.get("TIPTV_IM") or "").strip() or None
            nearest_river_flow_regime = str(nearest_row.get("STALN_IM") or "").strip() or None
            river_elevation_m = nearest_river_elevation(point, nearest_row.geometry)

        relative_height_m = None
        if elevation_m is not None and river_elevation_m is not None:
            relative_height_m = elevation_m - river_elevation_m

        local_slope_deg = None
        if relative_height_m is not None and river_distance_m is not None:
            local_slope_deg = math.degrees(math.atan(abs(relative_height_m) / max(river_distance_m, 5.0)))

        inside_frequent = bool(frequent_flags[idx])
        inside_rare = bool(rare_flags[idx])
        inside_very_rare = bool(very_rare_flags[idx])
        distance_to_flood_zone_m = float(flood_distances[idx]) if math.isfinite(float(flood_distances[idx])) else None

        terrain_position = classify_terrain_position(
            inside_frequent=inside_frequent,
            inside_rare=inside_rare,
            inside_very_rare=inside_very_rare,
            distance_to_river_m=river_distance_m,
            relative_height_above_river_m=relative_height_m,
            local_slope_deg=local_slope_deg,
            text=text,
        )
        terrain_context_conf = terrain_confidence(
            elevation_m=elevation_m,
            nearest_river_elevation_m=river_elevation_m,
            nearest_river_name=nearest_river_name,
            nearest_river_kind=nearest_river_kind,
        )
        official_score = official_flood_score(
            inside_frequent=inside_frequent,
            inside_rare=inside_rare,
            inside_very_rare=inside_very_rare,
        )
        proximity_score = flood_proximity_score(
            distance_to_river_m=river_distance_m,
            relative_height_above_river_m=relative_height_m,
            local_slope_deg=local_slope_deg,
            distance_to_flood_zone_m=distance_to_flood_zone_m,
            nearest_river_kind=nearest_river_kind,
        )

        placeholder_context = FloodContext(
            inside_frequent_flood_zone=inside_frequent,
            inside_rare_flood_zone=inside_rare,
            inside_very_rare_flood_zone=inside_very_rare,
            distance_to_river_m=rounded_metric(river_distance_m),
            distance_to_flood_zone_m=rounded_metric(distance_to_flood_zone_m),
            elevation_m=rounded_metric(elevation_m),
            nearest_river_elevation_m=rounded_metric(river_elevation_m),
            relative_height_above_nearest_river_m=rounded_metric(relative_height_m),
            local_slope_deg=rounded_metric(local_slope_deg),
            terrain_position=terrain_position,
            nearest_river_name=nearest_river_name,
            nearest_river_type=nearest_river_type,
            nearest_river_flow_regime=nearest_river_flow_regime,
            nearest_river_kind=nearest_river_kind,
            river_distance_band=classify_distance_band(river_distance_m, river=True),
            flood_zone_distance_band=classify_distance_band(distance_to_flood_zone_m, river=False),
            terrain_context_confidence=terrain_context_conf,
            terrain_context_method="ocenjeno iz uradnih poplavnih poligonov, geometrije najblizje reke, Z-vrednosti reke in visine lokacije; DEM raster ni na voljo",
            flood_official_score=official_score,
            flood_proximity_score=rounded_score(proximity_score),
            flood_hazard_band="unknown",
            flood_reasoning="",
        )
        contexts.append(placeholder_context)

    return contexts


def pd_concat_geometries(geometry_sets: list[Any]) -> list[Any]:
    merged: list[Any] = []
    for geometry_set in geometry_sets:
        merged.extend(list(geometry_set))
    return merged


def enrich_feature(feature: dict[str, Any], flood_context: FloodContext) -> dict[str, Any]:
    props = feature["properties"]
    text = normalize(
        " ".join(str(props.get(k) or "") for k in ("IME", "GESLA", "OPIS", "LOKACIJAOPIS", "TIP", "ZVRST", "DATACIJA", "regija"))
    )

    material, material_conf, material_reason = material_from_properties(props)
    fire, fire_cues = infer_fire(props, material, text)
    flood, flood_cues, flood_reasoning = infer_flood(props, text, flood_context)
    quake, quake_cues = infer_earthquake(props, material, text)
    slide, slide_cues = infer_landslide(props, text, flood_context)

    updated_flood_context = replace(
        flood_context,
        flood_hazard_band=classify_flood_hazard_band(flood),
        flood_reasoning=flood_reasoning,
    )

    status, research_conf = verification_status(props, material_conf, material_reason, updated_flood_context)

    props[localized_field("predominant_material")] = localized_material(material)
    props[localized_field("material_confidence")] = rounded_confidence(clamp(material_conf, 0.0, 1.0))
    props[localized_field("fire_danger_revised")] = fire
    props[localized_field("flood_danger_revised")] = flood
    props[localized_field("earthquake_danger_revised")] = quake
    props[localized_field("landslide_danger_revised")] = slide
    props[localized_field("elevation_m")] = updated_flood_context.elevation_m
    props[localized_field("inside_frequent_flood_zone")] = updated_flood_context.inside_frequent_flood_zone
    props[localized_field("inside_rare_flood_zone")] = updated_flood_context.inside_rare_flood_zone
    props[localized_field("inside_very_rare_flood_zone")] = updated_flood_context.inside_very_rare_flood_zone
    props[localized_field("distance_to_river_m")] = updated_flood_context.distance_to_river_m
    props[localized_field("distance_to_flood_zone_m")] = updated_flood_context.distance_to_flood_zone_m
    props[localized_field("nearest_river_name")] = updated_flood_context.nearest_river_name
    props[localized_field("nearest_river_type")] = updated_flood_context.nearest_river_type
    props[localized_field("nearest_river_flow_regime")] = updated_flood_context.nearest_river_flow_regime
    props[localized_field("nearest_river_kind")] = updated_flood_context.nearest_river_kind
    props[localized_field("nearest_river_elevation_m")] = updated_flood_context.nearest_river_elevation_m
    props[localized_field("relative_height_above_nearest_river_m")] = updated_flood_context.relative_height_above_nearest_river_m
    props[localized_field("local_slope_deg")] = updated_flood_context.local_slope_deg
    props[localized_field("terrain_position")] = localized_terrain_position(updated_flood_context.terrain_position)
    props[localized_field("river_distance_band")] = localized_distance_band(updated_flood_context.river_distance_band)
    props[localized_field("flood_zone_distance_band")] = localized_distance_band(updated_flood_context.flood_zone_distance_band)
    props[localized_field("terrain_context_confidence")] = updated_flood_context.terrain_context_confidence
    props[localized_field("terrain_context_method")] = updated_flood_context.terrain_context_method
    props[localized_field("flood_official_score")] = rounded_score(updated_flood_context.flood_official_score)
    props[localized_field("flood_proximity_score")] = rounded_score(updated_flood_context.flood_proximity_score)
    props[localized_field("flood_hazard_band")] = localized_flood_band(updated_flood_context.flood_hazard_band)
    props[localized_field("flood_reasoning")] = updated_flood_context.flood_reasoning
    props[localized_field("flood_model_version")] = FLOOD_MODEL_VERSION
    props[localized_field("danger_revision_reasoning")] = reasoning_sentence(
        material,
        fire,
        flood,
        quake,
        slide,
        props,
        fire_cues,
        flood_cues,
        quake_cues,
        slide_cues,
        updated_flood_context,
    )
    props[localized_field("verification_status")] = localized_verification_status(status)
    props[localized_field("verification_notes")] = verification_notes(material_reason, status, updated_flood_context)
    props[localized_field("sources")] = build_sources(props)
    props[localized_field("research_confidence")] = research_conf
    return feature


def validate(data: dict[str, object]) -> None:
    if data.get("type") != "FeatureCollection":
        raise ValueError("Output is not a FeatureCollection.")

    for idx, feature in enumerate(data.get("features", []), start=1):
        props = feature.get("properties", {})
        for revised_field in FIELD_MAP:
            if revised_field not in props:
                raise ValueError(f"Missing {revised_field} on feature {idx}.")
            value = props[revised_field]
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                raise ValueError(f"{revised_field} is not numeric on feature {idx}.")
            if rounded_score(float(value)) != float(value):
                raise ValueError(f"{revised_field} does not have one decimal place on feature {idx}.")
            if not (0.0 <= float(value) <= 4.0):
                raise ValueError(f"{revised_field} falls outside the 0..4 range on feature {idx}.")

        for required in (
            localized_field("predominant_material"),
            localized_field("material_confidence"),
            localized_field("danger_revision_reasoning"),
            localized_field("verification_status"),
            localized_field("verification_notes"),
            localized_field("sources"),
            localized_field("research_confidence"),
            localized_field("flood_reasoning"),
            localized_field("flood_model_version"),
            localized_field("terrain_context_method"),
            localized_field("terrain_context_confidence"),
            localized_field("flood_official_score"),
            localized_field("flood_proximity_score"),
            localized_field("flood_hazard_band"),
        ) + SITE_LEVEL_FEATURES:
            if required not in props:
                raise ValueError(f"Missing {required} on feature {idx}.")

        if props[localized_field("verification_status")] not in set(VERIFICATION_STATUS_LABELS.values()):
            raise ValueError(f"Invalid {localized_field('verification_status')} on feature {idx}.")
        if props[localized_field("flood_hazard_band")] not in set(FLOOD_HAZARD_BAND_LABELS.values()):
            raise ValueError(f"Invalid {localized_field('flood_hazard_band')} on feature {idx}.")
        if props[localized_field("terrain_position")] not in {
            "aktivna_poplavna_ravnica",
            "poplavna_ravnica",
            "dolinsko_dno",
            "nizka_terasa",
            "dvignjena_terasa",
            "polozno_pobocje",
            "dolinsko_pobocje",
            "greben_ali_visji_teren",
            "visji_svet",
        }:
            raise ValueError(f"Invalid {localized_field('terrain_position')} on feature {idx}.")
        if not isinstance(props[localized_field("sources")], list) or not (2 <= len(props[localized_field("sources")]) <= 6):
            raise ValueError(f"Invalid {localized_field('sources')} array on feature {idx}.")


def main() -> None:
    with INPUT_PATH.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    features = data.get("features", [])
    print(f"Loaded {len(features)} features from {INPUT_PATH}")
    print("Racunam uradne poplavne, recne in terenske kontekste...")
    flood_contexts = compute_geospatial_contexts(features)

    print("Bogatim lastnosti objektov...")
    for idx, feature in enumerate(features):
        features[idx] = enrich_feature(feature, flood_contexts[idx])

    validate(data)

    with OUTPUT_PATH.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")

     # skupna_ocena
    gdf = gpd.read_file("./Data/kd_z_nevarnost_enriched_verified.geojson")
    gdf['pozar_ocena_popravljena'] = 4 - gdf['pozar_ocena_popravljena']
    gdf['pozar'] = 4 - gdf['pozar'] # predlagam da tudi originalno oceno invertamo ker je 1="zelo ogrozeno" pac cudasko in naredimo 0...4 scale
    gdf['potres_ocena_popravljena'] = 2 * gdf['potres_ocena_popravljena']
    gdf['skupaj_nevarnost'] = gdf['pozar_ocena_popravljena'] + gdf['poplave_ocena_popravljena'] + gdf['plazovi_ocena_popravljena'] + gdf['potres_ocena_popravljena']
    gdf.to_file("./Data/kd_z_nevarnost_enriched_verified.geojson", driver="GeoJSON")

    print(f"Wrote {len(features)} features to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
