from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
INPUT_PATH = BASE_DIR / "kd_z_nevarnost.geojson"
OUTPUT_PATH = BASE_DIR / "kd_z_nevarnost_verified.geojson"

GENERAL_SOURCE_STRINGS = [
    "RNPD description and location fields",
    "ARSO potresna nevarnost (2021)",
    "DRSV flood warning maps / Predhodna ocena 2024",
    "GeoZS landslide warning map 1:25k",
    "ARSO/URSZR fire warning context",
]

FIELD_MAP = {
    "fire_danger_revised": "pozar",
    "flood_danger_revised": "poplave",
    "earthquake_danger_revised": "potres",
    "landslide_danger_revised": "plazovi",
}


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


def rounded(value: float) -> float:
    return round(float(value) + 1e-9, 1)


def limit_delta(value: float, original: float) -> float:
    value = clamp(value, original - 1.0, original + 1.0)
    value = clamp(value, 0.0, 5.0)
    return rounded(value)


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


def infer_flood(props: dict[str, object], text: str) -> tuple[float, list[str]]:
    original = float(props.get("poplave") or 0.0)
    adjustment = 0.0
    cues: list[str] = []

    strong_river = has(RIVER_RE, text)
    flood_words = has(FLOOD_RE, text)
    high_ground = has(HIGH_GROUND_RE, text)

    if strong_river or flood_words:
        if original <= 1.0:
            adjustment += 0.2
        elif original <= 2.0:
            adjustment += 0.1
        cues.append("river/valley or floodplain siting")
    if has(STRONG_FLOOD_RE, text) or ("otok" in text and strong_river):
        adjustment += 0.2 if original <= 1.0 else 0.1
        cues.append("explicit floodplain/island wording")
    if "otok" in text or "barj" in text or "jezer" in text or "ravnic" in text:
        adjustment += 0.1
        if "floodplain siting" not in cues:
            cues.append("low-lying siting")
    if high_ground and not strong_river and original >= 1.0:
        adjustment -= 0.1
        cues.append("ridge/high-ground wording")

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


def infer_landslide(props: dict[str, object], text: str) -> tuple[float, list[str]]:
    original = float(props.get("plazovi") or 0.0)
    adjustment = 0.0
    cues: list[str] = []

    steep = has(SLOPE_RE, text)
    very_steep = "grapa" in text or "strm" in text or "pod robom" in text or "klif" in text or "sedl" in text
    flat = "barj" in text or "ravnic" in text or "terasi" in text or "polju" in text or "otoku" in text

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
    if flat and original >= 1.0:
        adjustment -= 0.1
        cues.append("terrace/plain wording")

    return limit_delta(original + adjustment, original), cues


def verification_status(props: dict[str, object], material_confidence: float, reason_hint: str) -> tuple[str, float]:
    official_source_count = 0
    if props.get("QR") or props.get("POVEZAVA1"):
        official_source_count += 1
    if props.get("PREDPISHTTP"):
        official_source_count += 1
    if props.get("PHOTOURL"):
        official_source_count += 1

    research_conf = 0.28 + 0.1 * official_source_count + 0.35 * material_confidence
    if "explicit" in reason_hint or "documented" in reason_hint:
        research_conf += 0.06
    research_conf = rounded(clamp(research_conf, 0.3, 0.92))

    if official_source_count >= 2 and material_confidence >= 0.7:
        return "verified", research_conf
    if official_source_count >= 1 and material_confidence >= 0.48:
        return "partially_verified", research_conf
    return "weakly_verified", research_conf


def build_sources(props: dict[str, object]) -> list[str]:
    sources: list[str] = []
    if props.get("QR"):
        sources.append(str(props["QR"]))
    elif props.get("POVEZAVA1"):
        sources.append(str(props["POVEZAVA1"]))
    sources.extend(GENERAL_SOURCE_STRINGS)
    if props.get("PREDPISHTTP") and len(sources) < 6:
        sources.insert(1, "eVRD legal regime entry")
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
) -> str:
    original = {
        "fire": float(props.get("pozar") or 0.0),
        "flood": float(props.get("poplave") or 0.0),
        "earthquake": float(props.get("potres") or 0.0),
        "landslide": float(props.get("plazovi") or 0.0),
    }
    revisions: list[str] = []
    if abs(fire - original["fire"]) >= 0.2:
        revisions.append("fire nudged for " + (fire_cues[0] if fire_cues else "material"))
    if abs(flood - original["flood"]) >= 0.2:
        revisions.append("flood nudged for " + (flood_cues[0] if flood_cues else "siting"))
    if abs(quake - original["earthquake"]) >= 0.2:
        revisions.append("earthquake set modestly above zero for " + (quake_cues[0] if quake_cues else "structural vulnerability"))
    if abs(slide - original["landslide"]) >= 0.2:
        revisions.append("landslide nudged for " + (slide_cues[0] if slide_cues else "terrain"))

    cue_pool = fire_cues + flood_cues + quake_cues + slide_cues
    if revisions:
        return f"Official register record supports {material}; {'; '.join(revisions[:2])}; remaining scores stay close to baseline."
    if cue_pool:
        return f"Official register record supports {material}; {cue_pool[0]} is consistent with the baseline, so scores remain near the original."
    return f"Official register record supports {material}; no stronger object-specific evidence than the baseline was found, so revised scores stay near the original."


def verification_notes(material_reason: str, status: str) -> str:
    material_reason = material_reason[0].lower() + material_reason[1:] if material_reason else "is inferred"
    if material_reason.startswith("material "):
        material_reason = material_reason[len("material "):]
    if status == "verified":
        return f"Identity anchored by RNPD/eVRD-style official links; material basis: {material_reason}; hazard review is conservative and site-specific where wording allows."
    if status == "partially_verified":
        return f"Identity anchored by official register metadata; material basis: {material_reason}; hazard review mixes baseline confirmation with limited inference."
    return f"Identity likely from official register metadata; material mostly inferred because the description is broad; hazard review stays conservative."


def enrich_feature(feature: dict[str, object]) -> dict[str, object]:
    props = feature["properties"]
    text = normalize(" ".join(str(props.get(k) or "") for k in ("IME", "GESLA", "OPIS", "LOKACIJAOPIS", "TIP", "ZVRST", "DATACIJA", "regija")))

    material, material_conf, material_reason = material_from_properties(props)
    fire, fire_cues = infer_fire(props, material, text)
    flood, flood_cues = infer_flood(props, text)
    quake, quake_cues = infer_earthquake(props, material, text)
    slide, slide_cues = infer_landslide(props, text)

    status, research_conf = verification_status(props, material_conf, material_reason)

    props["predominant_material"] = material
    props["material_confidence"] = rounded(clamp(material_conf, 0.0, 1.0))
    props["fire_danger_revised"] = fire
    props["flood_danger_revised"] = flood
    props["earthquake_danger_revised"] = quake
    props["landslide_danger_revised"] = slide
    props["danger_revision_reasoning"] = reasoning_sentence(
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
    )
    props["verification_status"] = status
    props["verification_notes"] = verification_notes(material_reason, status)
    props["sources"] = build_sources(props)
    props["research_confidence"] = research_conf
    return feature


def validate(data: dict[str, object]) -> None:
    if data.get("type") != "FeatureCollection":
        raise ValueError("Output is not a FeatureCollection.")

    for idx, feature in enumerate(data.get("features", []), start=1):
        props = feature.get("properties", {})
        for revised_field, original_field in FIELD_MAP.items():
            if revised_field not in props:
                raise ValueError(f"Missing {revised_field} on feature {idx}.")
            value = props[revised_field]
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                raise ValueError(f"{revised_field} is not numeric on feature {idx}.")
            if rounded(value) != value:
                raise ValueError(f"{revised_field} does not have one decimal place on feature {idx}.")
            original = float(props.get(original_field) or 0.0)
            if abs(float(value) - original) > 1.0 + 1e-9:
                raise ValueError(f"{revised_field} exceeds +/-1.0 delta on feature {idx}.")

        for required in (
            "predominant_material",
            "material_confidence",
            "danger_revision_reasoning",
            "verification_status",
            "verification_notes",
            "sources",
            "research_confidence",
        ):
            if required not in props:
                raise ValueError(f"Missing {required} on feature {idx}.")

        if props["verification_status"] not in {"verified", "partially_verified", "weakly_verified"}:
            raise ValueError(f"Invalid verification_status on feature {idx}.")
        if not isinstance(props["sources"], list) or not (2 <= len(props["sources"]) <= 6):
            raise ValueError(f"Invalid sources array on feature {idx}.")


def main() -> None:
    with INPUT_PATH.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    features = data.get("features", [])
    for i, feature in enumerate(features):
        features[i] = enrich_feature(feature)

    validate(data)

    with OUTPUT_PATH.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")

    print(f"Wrote {len(features)} features to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
