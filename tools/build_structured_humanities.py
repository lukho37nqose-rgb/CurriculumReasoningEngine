#!/usr/bin/env python3
"""Add every 2026 Humanities undergraduate qualification route.

The generated catalogue keeps handbook facts separate from computed student
outcomes.  Conditions that depend on auditions, placement, professional
suitability, departmental selection, live offerings, or Senate discretion are
represented explicitly as manual/discretionary rules rather than inferred.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "uct_humanities"
REQ_PATH = DATA / "degree_requirements.json"
COURSE_PATH = DATA / "courses.json"
MUSIC_PATH = DATA / "music_pathways_2026.json"

HANDBOOK = "2026 Humanities Undergraduate Handbook"
GENERAL = "2026 General Rules and Policies Handbook"


def src(page: int | str, section: str, rule: str = "") -> dict[str, Any]:
    out: dict[str, Any] = {"document": HANDBOOK, "page": page, "section": section}
    if rule:
        out["rule"] = rule
    return out


def rule_course(rule_id: str, label: str, codes: list[str], *, required: int = 1,
                status: str = "verified", page: int | str = "") -> dict[str, Any]:
    return {
        "id": rule_id, "type": "course", "label": label,
        "course_codes": codes, "required": required,
        "verification_status": status,
        "source": src(page, label) if page else {},
    }


def all_courses(rule_id: str, label: str, codes: list[str], *, status: str = "verified",
                page: int | str = "") -> dict[str, Any]:
    return {
        "id": rule_id, "type": "all_courses", "label": label,
        "course_codes": codes, "verification_status": status,
        "source": src(page, label) if page else {},
    }


def choose(rule_id: str, label: str, codes: list[str], required: int = 1, *,
           status: str = "verified", page: int | str = "") -> dict[str, Any]:
    return {
        "id": rule_id, "type": "choose_n", "label": label,
        "course_codes": codes, "required": required,
        "verification_status": status,
        "source": src(page, label) if page else {},
    }


def count(rule_id: str, label: str, required: int, *, codes: list[str] | None = None,
          filters: dict[str, Any] | None = None, status: str = "verified",
          page: int | str = "") -> dict[str, Any]:
    actual_filters = dict(filters or {})
    if codes:
        actual_filters["course_codes"] = codes
    return {
        "id": rule_id, "type": "course_count", "label": label,
        "required": required, "filters": actual_filters,
        "verification_status": status,
        "source": src(page, label) if page else {},
    }


def minimum_mark(rule_id: str, label: str, codes: list[str], threshold: int, *,
                 status: str = "verified", page: int | str = "") -> dict[str, Any]:
    return {
        "id": rule_id, "type": "minimum_mark", "label": label,
        "course_codes": codes, "minimum_mark": threshold,
        "verification_status": status,
        "source": src(page, label) if page else {},
    }


def manual(rule_id: str, label: str, note: str, *, status: str = "discretionary",
           blocking: bool = True, page: int | str = "") -> dict[str, Any]:
    return {
        "id": rule_id, "type": "manual", "label": label,
        "note": note, "status": status, "blocking": blocking,
        "assumed_complete": True,
        "source": src(page, label) if page else {},
    }


def path(name: str, rules: list[dict[str, Any]], *, required: list[str] | None = None,
         support: list[str] | None = None, status: str = "verified",
         availability: str = "open", availability_note: str = "",
         page: int | str = "") -> dict[str, Any]:
    return {
        "name": name,
        "curriculum_rules": rules,
        "required_courses": required or [],
        "support_course_codes": support or [],
        "verification_status": status,
        "availability": availability,
        "availability_note": availability_note,
        "source": src(page, name) if page else {},
    }


def programme(name: str, code: str, *, min_credits: int, level7: int = 0,
              level_requirements: dict[int, int] | None = None,
              min_years: int = 1, max_years: int | None = None,
              route_type: str = "structured", category: str = "structured",
              rules: list[dict[str, Any]] | None = None,
              pathways: dict[str, Any] | None = None,
              pathway_required: bool = False,
              support: list[str] | None = None,
              availability: str = "open", availability_note: str = "",
              admission: list[str] | None = None,
              progression: list[str] | None = None,
              award: list[str] | None = None,
              thresholds: list[dict[str, int]] | None = None,
              page: int | str = "") -> dict[str, Any]:
    return {
        "name": name,
        "qualification_codes": [code],
        "minimum_nqf_credits": min_credits,
        "minimum_nqf_level_7_credits": level7,
        "level_credit_requirements": {str(k): v for k, v in (level_requirements or {}).items()},
        "minimum_semester_courses": 0,
        "minimum_senior_semester_courses": 0,
        "minimum_humanities_semester_courses": 0,
        "minimum_majors": 0,
        "minimum_humanities_majors": 0,
        "minimum_duration_years": min_years,
        "maximum_registration_years": max_years,
        "route_type": route_type,
        "degree_category": category,
        "programme_type": "structured",
        "required_courses": [],
        "major_keys": [],
        "elective_course_codes": [],
        "elective_departments": [],
        "support_course_codes": support or [],
        "curriculum_rules": rules or [],
        "pathways": pathways or {},
        "pathway_required": pathway_required,
        "default_pathway_key": "",
        "scope_verified": True,
        "availability": availability,
        "availability_note": availability_note,
        "admission_notes": admission or [],
        "progression_notes": progression or [],
        "award_notes": award or [],
        "readmission_thresholds": thresholds or [],
        "source": src(page, name),
    }


def codes_from_rules(rules: list[dict[str, Any]]) -> set[str]:
    result: set[str] = set()
    for r in rules:
        result.update(str(c).upper() for c in r.get("course_codes", []))
        result.update(str(c).upper() for c in r.get("filters", {}).get("course_codes", []))
        result.update(codes_from_rules(r.get("children", [])))
    return result


req = json.loads(REQ_PATH.read_text())
courses = json.loads(COURSE_PATH.read_text())
music = json.loads(MUSIC_PATH.read_text())
programmes = req["programmes"]

# Preserve and identify the four flexible general-degree routes.
for key in ("ba_regular", "bsocsc_regular", "ba_extended", "bsocsc_extended"):
    programmes[key]["programme_type"] = "general_degree"
    programmes[key]["scope_verified"] = True

# ---------------------------------------------------------------------------
# Education certificates and advanced diplomas
# ---------------------------------------------------------------------------
programmes["higher_certificate_acet"] = programme(
    "Higher Certificate in Adult and Community Education and Training", "HU052",
    min_credits=120, level_requirements={5: 120}, min_years=1,
    rules=[all_courses("hc_acet_core", "All Higher Certificate ACET modules", [
        "EDN1031FS", "EDN1030FS", "EDN1032FS"], page=21)],
    progression=["EDN1031FS and EDN1030FS must be passed before EDN1032FS."],
    award=["Every prescribed course must be passed for the certificate to be awarded."],
    page=20,
)

foundation = ["EDN2521W", "EDN2522W", "EDN2523W", "EDN2524W", "EDN2525W",
              "EDN2526W", "EDN2527W", "EDN2528W", "EDN2529W"]
programmes["advanced_certificate_foundation_phase"] = programme(
    "Advanced Certificate in Foundation Phase Teaching", "HU048",
    min_credits=120, level_requirements={6: 120}, min_years=1,
    rules=[all_courses("acfpt_core", "All Foundation Phase core modules", foundation, page=24),
           manual("acfpt_ict", "ICT competence condition",
                  "EDN1536W is an additional level-5 course only for entrants without the required ICT competence.",
                  blocking=False, page=24)],
    support=["EDN1536W"], page=24,
)

intermediate = ["EDN2522W", "EDN2528W", "EDN2530W", "EDN2531W", "EDN2532W",
                "EDN2533W", "EDN2534W", "EDN2535W"]
programmes["advanced_certificate_intermediate_phase"] = programme(
    "Advanced Certificate in Intermediate Phase Teaching: English FAL and Mathematics", "HU045",
    min_credits=120, level_requirements={6: 120}, min_years=1,
    rules=[all_courses("acipt_core", "All Intermediate Phase core modules", intermediate, page=24),
           manual("acipt_ict", "ICT competence condition",
                  "EDN1536W is an additional level-5 course only for entrants without the required ICT competence.",
                  blocking=False, page=24)],
    support=["EDN1536W"], page=24,
)

senior_paths = {
    "english_fal": ("English First Additional Language", [f"EDN25{i:02d}W" for i in range(0, 7)], "EDN31"),
    "mathematics": ("Mathematics", [f"EDN25{i:02d}W" for i in range(7, 14)], "EDN32"),
    "natural_sciences": ("Natural Sciences", [f"EDN25{i:02d}W" for i in range(14, 21)], "EDN33"),
}
programmes["advanced_certificate_senior_phase"] = programme(
    "Advanced Certificate in Senior Phase Teaching", "HU043",
    min_credits=120, level_requirements={6: 120}, min_years=1,
    pathways={k: path(f"{name} [{stream}]", [all_courses(f"acspt_{k}", f"All {name} modules", cs, page=25)], page=25)
              for k, (name, cs, stream) in senior_paths.items()},
    pathway_required=True, page=25,
)

programmes["advanced_diploma_acet"] = programme(
    "Advanced Diploma in Adult and Community Education and Training", "HU051",
    min_credits=120, level7=120, level_requirements={7: 120}, min_years=2,
    rules=[all_courses("ad_acet_core", "All Advanced Diploma ACET modules",
                       ["EDN3700FS", "EDN3702FS", "EDN3701FS", "EDN3703FS"], page=27)],
    admission=["Admission depends on an approved prior education qualification and at least two years of relevant experience."],
    page=26,
)

slm_first = ["EDN3704W", "EDN3705W", "EDN3706W", "EDN3707W", "EDN3711W",
             "EDN3712W", "EDN3708W", "EDN3709W", "EDN3710W"]
slm_second = ["EDN3704W", "EDN3705W", "EDN3711W", "EDN3713W", "EDN3706W",
              "EDN3707W", "EDN3708W", "EDN3709W", "EDN3710W"]
programmes["advanced_diploma_school_leadership"] = programme(
    "Advanced Diploma in School Leadership and Management", "HU053",
    min_credits=120, level7=120, level_requirements={7: 120}, min_years=2,
    pathways={
        "first_semester_intake": path("First-semester intake", [
            all_courses("slm_first_core", "Modules in the first-semester intake pattern", slm_first, status="provisional", page=28),
            manual("slm_first_continuation", "Multi-year continuation allocation",
                   "Several W-coded workplace modules continue across registration years. The Faculty record must confirm their final credit allocation.",
                   status="unverified", page=28)], support=slm_first, status="provisional", page=28),
        "second_semester_intake": path("Second-semester intake", [
            all_courses("slm_second_core", "Modules in the second-semester intake pattern", slm_second, status="provisional", page=29),
            manual("slm_second_continuation", "Multi-year continuation allocation",
                   "Several W-coded workplace modules continue across registration years. The Faculty record must confirm their final credit allocation.",
                   status="unverified", page=29)], support=slm_second, status="provisional", page=29),
    }, pathway_required=True,
    admission=["Selection prioritises serving or aspirant school leaders and includes employment and experience conditions."],
    page=28,
)

# ---------------------------------------------------------------------------
# Structured bachelor routes
# ---------------------------------------------------------------------------
screen_core = ["FAM1000S", "FAM2013F", "FAM2014S", "FAM2004S",
               "FAM3016F", "FAM3017S", "FAM3005F", "FAM3003S"]
programmes["ba_screen_production"] = programme(
    "Bachelor of Arts specialising in Screen Production", "HB067",
    min_credits=360, level7=120, level_requirements={7: 120}, min_years=3, max_years=4,
    category="bachelor_specialisation",
    rules=[
        all_courses("screen_core", "Screen Production compulsory sequence", screen_core, page=40),
        count("screen_first_year", "Eight first-year semester courses", 8, filters={"nqf_levels": [5]}, page=40),
        count("screen_second_year", "Six second-year semester courses", 6, filters={"nqf_levels": [6]}, page=41),
        count("screen_third_year", "Six third-year semester courses", 6, filters={"nqf_levels": [7]}, page=41),
        manual("screen_selection", "Selection into Screen Production",
               "Admission after the first semester of second year depends on academic performance, portfolio/interview selection and programme capacity.",
               page=40),
    ], support=screen_core,
    admission=["Selection into the specialisation is competitive and is not established by transcript data alone."],
    page=40,
)

ppe_y1 = ["ECO1010F", "ECO1011S", "PHI1010S", "PHI1024F", "POL1004F", "POL1005S", "STA1000S", "MAM1010F"]
ppe_y2_fixed = ["ECO2003F", "ECO2004S", "ECO2007S", "PHI2041S", "PHI2042F", "POL2038F"]
ppe_pol2 = ["POL2002F", "POL2039F", "POL2042S", "POL2043S"]
ppe_other2 = ["ECO2008S", "PHI2012F", "PHI2016S", "PHI2037F", "PHI2040S", "PHI2043F", "PHI2043S", "PHI2044F", "PHI2045S"]
ppe_phi3 = ["PHI3023F", "PHI3024S"]
ppe_pol3 = ["POL3029F", "POL3030F", "POL3037F", "POL3038S", "POL3045S", "POL3046S"]
ppe_eco3 = ["ECO3009F", "ECO3016F", "ECO3020F", "ECO3021S", "ECO3022S", "ECO3023S", "ECO3024F"]
ppe_third_union = ["ECO3025S", *ppe_phi3, *ppe_pol3, *ppe_eco3]
programmes["bsocsc_ppe"] = programme(
    "Bachelor of Social Science in Philosophy, Politics and Economics", "HB027",
    min_credits=360, level7=120, level_requirements={7: 120}, min_years=3, max_years=4,
    category="bachelor_structured",
    rules=[
        all_courses("ppe_year1", "First-year PPE curriculum", ppe_y1, page=43),
        all_courses("ppe_year2_fixed", "Second-year compulsory courses", ppe_y2_fixed, page=43),
        choose("ppe_year2_politics", "One second-year Politics option", ppe_pol2, page=43),
        choose("ppe_year2_other", "One additional second-year option", ppe_other2, page=43),
        all_courses("ppe_eco3025", "Compulsory third-year Economics course", ["ECO3025S"], page=44),
        choose("ppe_phi3", "At least one third-year Philosophy option", ppe_phi3, page=44),
        choose("ppe_pol3", "At least one third-year Politics option", ppe_pol3, page=44),
        choose("ppe_eco3", "At least one additional third-year Economics option", ppe_eco3, page=44),
        count("ppe_third_count", "Six third-year PPE courses in total", 6, codes=ppe_third_union, page=44),
    ], support=[*ppe_y1, *ppe_y2_fixed, *ppe_pol2, *ppe_other2, *ppe_third_union],
    thresholds=[
        {"year": 1, "minimum_passed_courses": 5}, {"year": 2, "minimum_passed_courses": 10},
        {"year": 3, "minimum_passed_courses": 14, "minimum_senior_courses": 2},
        {"year": 4, "minimum_passed_courses": 20},
    ], page=42,
)

bsw_common = [
    rule_course("bsw_psy1", "First introductory Psychology course", ["PSY1009F", "PSY1004F"], page=46),
    rule_course("bsw_psy2", "Second introductory Psychology course", ["PSY1010S", "PSY1005S"], page=46),
    all_courses("bsw_first_common", "Other first-year BSW courses", ["SOC1001F", "SOC1005S", "SWK1006S", "SWK1005S", "SWK1013F"], page=46),
    all_courses("bsw_second_common", "Second-year Social Work sequence", ["SWK2001F", "SWK2060F", "SWK2065S", "SWK2070F", "SWK2075S"], page=46),
    all_courses("bsw_third_common", "Third-year Social Work sequence", ["SWK3061F", "SWK3066S", "SWK3070F", "SWK3075S"], page=47),
    all_courses("bsw_fourth", "Fourth-year Social Work sequence", ["SWK4015F", "SWK4016S", "SWK4030F", "SWK4031S", "SWK4032S", "SWK4033F"], page=47),
    manual("bsw_professional_suitability", "Professional suitability and field-practice approval",
           "Progression includes field-practice, ethical suitability and professional conduct judgments that require departmental confirmation.", page=45),
]
bsw_paths = {
    "psychology": path("Psychology professional-registration route", [
        choose("bsw_psy_second", "Two second-year Psychology courses", ["PSY2013F", "PSY2014S", "PSY2015F"], 2, page=46),
        all_courses("bsw_psy_third", "Required third-year Psychology pair", ["PSY3005F", "PSY3011S"], page=47),
    ], support=["PSY2013F", "PSY2014S", "PSY2015F", "PSY3005F", "PSY3011S"], page=46),
    "sociology": path("Sociology professional-registration route", [
        choose("bsw_soc_second", "Two second-year Sociology courses", ["PBL2800F", "SOC2004S", "SOC2015S", "SOC2019S", "SOC2030F", "SOC2032F", "SOC2036F"], 2, page=46),
        choose("bsw_soc_third", "Two prescribed third-year Sociology courses", ["SOC3007F", "SOC3027F", "SOC3031S", "SOC3029S", "SOC3028S"], 2, page=47),
    ], support=["PBL2800F", "SOC2004S", "SOC2015S", "SOC2019S", "SOC2030F", "SOC2032F", "SOC2036F", "SOC3007F", "SOC3027F", "SOC3031S", "SOC3029S", "SOC3028S"], page=46),
}
programmes["bachelor_social_work"] = programme(
    "Bachelor of Social Work", "HB063",
    min_credits=480, level7=120, level_requirements={7: 120, 8: 96}, min_years=4, max_years=5,
    category="professional_bachelor", rules=bsw_common, pathways=bsw_paths, pathway_required=True,
    support=list(codes_from_rules(bsw_common)),
    thresholds=[
        {"year": 1, "minimum_passed_courses": 4}, {"year": 2, "minimum_passed_courses": 8},
        {"year": 3, "minimum_passed_courses": 12, "minimum_senior_courses": 2},
        {"year": 4, "minimum_passed_courses": 16}, {"year": 5, "minimum_passed_courses": 20},
    ], page=45,
)

# Fine Art
fine_studio2 = ["FIN2011W", "FIN2012W", "FIN2013W", "FIN2024W", "FIN2025W"]
fine_studio3 = ["FIN3011W", "FIN3012W", "FIN3013W", "FIN3024W", "FIN3025W"]
fine_regular_rules = [
    all_courses("fa_y1", "First-year Fine Art core", ["FIN1001W", "FIN1005W", "FIN1006F", "FIN1009S"], page=52),
    count("fa_y1_elective", "One Humanities first-year elective", 1, filters={"nqf_levels": [5], "exclude_prefixes": ["FIN"], "general_elective": True}, page=52),
    choose("fa_studio2", "Two second-year studio courses", fine_studio2, 2, page=52),
    all_courses("fa_core2", "Second-year Fine Art core", ["FIN2026W", "FIN2028S"], page=52),
    choose("fa_discourse2", "One second-year Art History/Discourse course", ["FIN2027F", "FIN2029F"], page=52),
    count("fa_support2", "Two recommended Humanities electives", 2, filters={"nqf_levels": [5, 6], "exclude_prefixes": ["FIN"], "general_elective": True}, status="provisional", page=52),
    choose("fa_studio3", "One third-year studio course", fine_studio3, page=53),
    all_courses("fa_core3", "Third-year Fine Art core", ["FIN3030W"], page=53),
    choose("fa_discourse3a", "One third-year Art History/Discourse first-semester course", ["FIN3026F", "FIN3028F"], page=53),
    choose("fa_discourse3b", "One third-year Art History/Discourse second-semester course", ["FIN3027S", "FIN3029S"], page=53),
    all_courses("fa_y4", "Fourth-year Fine Art core", ["FIN4015W", "FIN4012W"], page=53),
    manual("fa_studio_coherence", "Studio-stream continuity and selection",
           "Studio choice, progression and fourth-year placement must be confirmed by Michaelis because competitive selection and stream continuity are not inferable from a transcript.", page=52),
]
programmes["ba_fine_art_regular"] = programme(
    "Bachelor of Arts in Fine Art - regular programme", "HB008",
    min_credits=480, level7=120, level_requirements={7: 120, 8: 96}, min_years=4, max_years=5,
    category="professional_bachelor", rules=fine_regular_rules,
    support=sorted(codes_from_rules(fine_regular_rules)), page=52,
)

fine_ext_rules = [
    all_courses("fae_y1", "Extended first-year core", ["FIN1001W", "FIN1008W", "DOH1005F"], page=54),
    all_courses("fae_y2_core", "Extended second-year core", ["FIN1006F", "FIN1009S", "FIN2026W"], page=54),
    choose("fae_studio2", "Two second-year studio courses", fine_studio2, 2, page=54),
    choose("fae_discourse3", "One second-year Art History/Discourse course", ["FIN2027F", "FIN2029F"], page=55),
    all_courses("fae_y3_core", "Extended third-year core", ["FIN2028S"], page=55),
    choose("fae_studio3", "One third-year studio course", fine_studio3, page=55),
    count("fae_hum_electives", "Two Humanities electives across years three and four", 2, filters={"nqf_levels": [5], "exclude_prefixes": ["FIN"], "general_elective": True}, page=55),
    all_courses("fae_y4_core", "Extended fourth-year Fine Art core", ["FIN3030W"], page=55),
    choose("fae_discourse4a", "One third-year Art History/Discourse first-semester course", ["FIN3026F", "FIN3028F"], page=55),
    choose("fae_discourse4b", "One third-year Art History/Discourse second-semester course", ["FIN3027S", "FIN3029S"], page=55),
    all_courses("fae_y5", "Extended fifth-year Fine Art core", ["FIN4015W", "FIN4012W"], page=55),
    manual("fae_augmenting", "Required augmenting-course allocation",
           "The transcript must show the augmenting courses linked to the selected Humanities electives; the exact pair depends on those electives.", status="unverified", page=55),
    manual("fae_studio_coherence", "Studio-stream continuity and selection",
           "Studio progression and final placement require Michaelis confirmation.", page=54),
]
programmes["ba_fine_art_extended"] = programme(
    "Bachelor of Arts in Fine Art - extended programme", "HB064",
    min_credits=480, level7=120, level_requirements={7: 120, 8: 96}, min_years=5, max_years=5,
    category="professional_bachelor", rules=fine_ext_rules,
    support=sorted(codes_from_rules(fine_ext_rules)), availability="continuing_only",
    availability_note="No new intake in 2026; continuing students only.", page=54,
)

# ---------------------------------------------------------------------------
# Music qualifications. Stream tables contain many instrument-specific one-of
# choices. The scope includes every listed option, the engine verifies credits
# and levels, and the exact instrument/ensemble combination remains an explicit
# manual verification node rather than an unsafe flattening of the table.
# ---------------------------------------------------------------------------
def music_pathways(family: str, page: int, *, continuing: bool = False,
                   credit_minima: dict[str, int] | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, data in music[family].items():
        all_codes: list[str] = []
        core_codes: list[str] = []
        for year_key, year_data in data.items():
            if year_key == "name" or not isinstance(year_data, dict):
                continue
            all_codes.extend(year_data.get("all", []))
            core_codes.extend(year_data.get("core", []))
        all_codes = list(dict.fromkeys(all_codes))
        core_codes = list(dict.fromkeys(core_codes))
        rules: list[dict[str, Any]] = []
        minimum = (credit_minima or {}).get(key)
        if minimum:
            rules.append({
                "id": f"{family}_{key}_credits", "type": "credits",
                "label": f"Minimum credits in the {data['name']} stream",
                "required": minimum, "verification_status": "verified",
                "source": src(page, f"{data['name']} stream curriculum"),
            })
        # Small core lists are genuinely fixed sequences; large bold lists are
        # instrument menus and are therefore not flattened into all-of rules.
        if 0 < len(core_codes) <= 10:
            rules.append(all_courses(f"{family}_{key}_core", f"Core sequence for {data['name']}", core_codes, status="provisional", page=page))
        rules.append(manual(
            f"{family}_{key}_combination", "Instrument, ensemble and theory combination",
            "The South African College of Music stream table contains instrument-specific and placement-dependent alternatives. The engine exposes every listed option and verifies credit/level totals, but the selected combination must be confirmed against the student's instrument and placement record.",
            status="unverified", page=page,
        ))
        out[key] = path(
            data["name"], rules, support=all_codes,
            status="provisional", availability="continuing_only" if continuing else "open",
            availability_note="No new intake in 2026; continuing students only." if continuing else "",
            page=page,
        )
    return out

programmes["diploma_music_performance_regular"] = programme(
    "Diploma in Music Performance - regular programme", "HU021",
    min_credits=360, level_requirements={6: 120}, min_years=3, max_years=4,
    category="diploma", pathways=music_pathways("dmp_regular", 63, credit_minima={
        "world_music": 413, "african_music": 414, "classical": 534, "jazz_studies": 402, "opera": 437,
    }), pathway_required=True,
    admission=["Admission and stream placement depend on audition and South African College of Music approval."],
    page=62,
)
programmes["diploma_music_performance_extended"] = programme(
    "Diploma in Music Performance - extended programme", "HU035",
    min_credits=360, level_requirements={6: 120}, min_years=4, max_years=4,
    category="diploma", pathways=music_pathways("dmp_extended_initial", 72, continuing=True),
    pathway_required=True, availability="continuing_only",
    availability_note="No new intake in 2026; continuing students only.", page=71,
)
programmes["advanced_diploma_opera"] = programme(
    "Advanced Diploma in Opera", "HU047", min_credits=144, level7=132,
    level_requirements={7: 132}, min_years=1, category="advanced_diploma",
    rules=[all_courses("ad_opera_core", "All Advanced Diploma in Opera modules",
                       ["MUZ3377H", "MUZ3702H", "MUZ3704W", "SLL1094H"], page=76)],
    availability="not_offered", availability_note="Not offered in 2026.", page=76,
)
programmes["advanced_diploma_music"] = programme(
    "Advanced Diploma in Music", "HU046", min_credits=120, level7=120,
    level_requirements={7: 120}, min_years=1, category="advanced_diploma",
    rules=[all_courses("ad_music_fixed", "Advanced performance modules",
                       ["MUZ3705H", "MUZ3706H"], page=77),
           choose("ad_music_option", "One advanced repertoire/transcription option",
                  ["MUZ3707H", "MUZ3708H", "MUZ3709H"], page=77)],
    availability="not_offered", availability_note="Not offered in 2026.", page=77,
)
programmes["bachelor_music_regular"] = programme(
    "Bachelor of Music - regular programme", "HB010",
    min_credits=480, level7=120, level_requirements={7: 120, 8: 96}, min_years=4, max_years=5,
    category="professional_bachelor", pathways=music_pathways("bmus_regular", 78), pathway_required=True,
    admission=["Admission and later stream placement can depend on audition, theory examination, performance standard and programme capacity."],
    page=77,
)
programmes["bachelor_music_extended"] = programme(
    "Bachelor of Music - extended programme", "HB034",
    min_credits=480, level7=120, level_requirements={7: 120, 8: 96}, min_years=5, max_years=5,
    category="professional_bachelor", pathways=music_pathways("bmus_extended_initial", 99, continuing=True), pathway_required=True,
    availability="continuing_only", availability_note="No new intake in 2026; continuing students only.",
    page=99,
)

# ---------------------------------------------------------------------------
# Theatre and performance qualifications
# ---------------------------------------------------------------------------
dip_t_common = [
    all_courses("dtp_y1", "First-year Diploma in Theatre and Performance core",
                ["TDP1046W", "TDP1017H", "TDP1027F", "TDP1045S", "TDP1029F", "DOH1005F"], page=112),
    all_courses("dtp_y2", "Second-year Diploma in Theatre and Performance core",
                ["TDP2010F", "TDP2011S", "TDP2042F", "TDP2013S", "TDP1018H", "TDP2040W"], page=112),
    all_courses("dtp_professional", "Third-year professional practice", ["TDP3052W"], page=113),
    minimum_mark("dtp_studiowork_mark", "First-year Studiowork progression mark",
                 ["TDP1046W"], 60, page=113),
    manual("dtp_concentration_selection", "Concentration selection",
           "Concentration is allocated after audition and is not guaranteed by transcript choice alone.", page=110),
]
dip_t_paths = {
    "acting": path("Acting", [all_courses("dtp_acting", "Acting third-year Studiowork", ["TDP3043W"], page=113)], support=["TDP3043W"], page=110),
    "dance_performance": path("Dance Performance", [all_courses("dtp_dance", "Dance third-year Studiowork", ["TDP3047W"], page=113)], support=["TDP3047W"], page=110),
    "performance_making": path("Performance Making", [all_courses("dtp_making", "Performance Making third-year Studiowork", ["TDP3041W"], page=113)], support=["TDP3041W"], page=110),
    "applied_pedagogy": path("Applied Performance / Pedagogy", [all_courses("dtp_applied", "Applied/Pedagogy third-year Studiowork", ["TDP3050W"], page=113)], support=["TDP3050W"], page=110),
    "scenography": path("Scenography", [all_courses("dtp_scenography", "Scenography third-year Studiowork", ["TDP3051W"], page=113)], support=["TDP3051W"], page=110),
}
programmes["diploma_theatre_performance"] = programme(
    "Diploma in Theatre and Performance", "HU020",
    min_credits=360, level_requirements={6: 120}, min_years=3, max_years=4,
    category="diploma", rules=dip_t_common, pathways=dip_t_paths, pathway_required=True,
    support=sorted(codes_from_rules(dip_t_common)),
    admission=["Admission is by audition and restricted selection."], page=109,
)
programmes["advanced_diploma_theatre"] = programme(
    "Advanced Diploma in Theatre", "HU050", min_credits=120, level7=120,
    level_requirements={7: 120}, min_years=1, category="advanced_diploma",
    rules=[all_courses("ad_theatre_core", "All Advanced Diploma in Theatre modules",
                       ["TDP3010F", "TDP3018S", "TDP3902W"], page=114)],
    availability="not_offered", availability_note="Not offered in 2026.", page=113,
)

batp_common = [
    all_courses("batp_y1_core", "First-year Theatre and Performance core",
                ["TDP1046W", "TDP1017H", "TDP1027F", "TDP1045S"], page=116),
    count("batp_y1_electives", "Two non-TDP first-year courses", 2, filters={"nqf_levels": [5], "exclude_prefixes": ["TDP"], "general_elective": True}, page=116),
    all_courses("batp_y2_core", "Second-year Theatre and Performance core",
                ["TDP2010F", "TDP2011S", "TDP1018H", "TDP2040W"], page=117),
    count("batp_y2_electives", "Two non-TDP second-year courses", 2, filters={"nqf_levels": [6], "exclude_prefixes": ["TDP"], "general_elective": True}, page=117),
    all_courses("batp_y3_core", "Third-year professional core",
                ["TDP3010F", "TDP3018S", "TDP3052W"], page=118),
    count("batp_y3_electives", "Two non-TDP third-year courses", 2, filters={"nqf_levels": [7], "exclude_prefixes": ["TDP"], "general_elective": True}, page=118),
    all_courses("batp_y4_research", "Fourth-year research component", ["TDP4000H"], page=119),
    minimum_mark("batp_studiowork_mark", "First-year Studiowork progression mark",
                 ["TDP1046W"], 60, page=119),
    manual("batp_progression", "Performance progression and selection",
           "Progression beyond the represented mark and course thresholds depends on successful auditions, prerequisites, professional conduct and concentration placement.", page=115),
]
batp_pairs = {
    "acting": ("Acting", "TDP3042W", "TDP4040W"),
    "dance_performance": ("Dance Performance", "TDP3046W", "TDP4045W"),
    "performance_making": ("Performance Making", "TDP3040W", "TDP4041W"),
    "applied_pedagogy": ("Applied Performance / Pedagogy", "TDP3049W", "TDP4047W"),
    "scenography": ("Scenography", "TDP3048W", "TDP4046W"),
}
batp_paths = {
    key: path(name, [all_courses(f"batp_{key}", f"Matched third- and fourth-year {name} Studiowork", [third, fourth], page=119)],
              support=[third, fourth], page=115)
    for key, (name, third, fourth) in batp_pairs.items()
}
programmes["ba_theatre_performance"] = programme(
    "Bachelor of Arts in Theatre and Performance", "HB014",
    min_credits=480, level7=120, level_requirements={7: 120, 8: 96}, min_years=4, max_years=5,
    category="professional_bachelor", rules=batp_common, pathways=batp_paths, pathway_required=True,
    support=sorted(codes_from_rules(batp_common)), admission=["Admission is restricted and requires audition/selection."],
    page=115,
)

# ---------------------------------------------------------------------------
# Add course facts needed by structured routes but absent from the department
# extraction. These are generated from the qualification tables and are kept in
# a separate small data file so provenance remains visible.
# ---------------------------------------------------------------------------
extra_path = DATA / "structured_course_additions_2026.json"
extras = json.loads(extra_path.read_text()) if extra_path.exists() else []
by_code = {c["code"]: c for c in courses}
for extra in extras:
    by_code.setdefault(extra["code"], extra)
courses = sorted(by_code.values(), key=lambda item: item["code"])

# Validate all direct references. Filter-based elective rules intentionally do
# not enumerate every course code.
references: set[str] = set()
for p in programmes.values():
    references.update(p.get("required_courses", []))
    references.update(p.get("support_course_codes", []))
    references.update(codes_from_rules(p.get("curriculum_rules", [])))
    for pathway in p.get("pathways", {}).values():
        references.update(pathway.get("required_courses", []))
        references.update(pathway.get("support_course_codes", []))
        references.update(codes_from_rules(pathway.get("curriculum_rules", [])))
missing = sorted(references - {c["code"] for c in courses})
if missing:
    raise SystemExit("Missing course facts for structured routes: " + ", ".join(missing))

req["catalogue_version"] = "2026.2-humanities-complete"
req["source"] = f"{HANDBOOK}; {GENERAL}"
REQ_PATH.write_text(json.dumps(req, indent=2, ensure_ascii=False) + "\n")
COURSE_PATH.write_text(json.dumps(courses, indent=2, ensure_ascii=False) + "\n")
print(f"Wrote {len(programmes)} programmes and {len(courses)} course facts.")
