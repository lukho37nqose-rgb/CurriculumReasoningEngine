#!/usr/bin/env python3
"""Build the 2026 EBE catalogue from the handbook extraction artefacts.

This generator deliberately separates prescribed courses from elective pools,
cohort-transition conditions, and discretionary transfer/access routes. It is
safe to re-run; the JSON files are deterministic.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "uct_ebe"
EXTRACTION = OUT / "source_extraction"
ROWS_PATH = EXTRACTION / "programme_rows.json"
DESCRIPTIONS_PATH = EXTRACTION / "course_descriptions.json"
HUM_COURSES_PATH = ROOT / "data" / "uct_humanities" / "courses.json"

SOURCE_DOCUMENT = "2026 EBE Undergraduate Handbook"
GENERAL_SOURCE = "2026 General Rules and Policies Handbook"

PREFIX_DEPARTMENT = {
    "ACC": "College of Accounting", "APG": "Architecture, Planning and Geomatics",
    "ASL": "African Studies and Linguistics", "BIO": "Biological Sciences",
    "CEM": "Chemistry", "CHE": "Chemical Engineering", "CIV": "Civil Engineering",
    "CML": "Commercial Law", "CON": "Construction Economics and Management",
    "CSC": "Computer Science", "ECO": "Economics", "EEE": "Electrical Engineering",
    "EGS": "Environmental and Geographical Science", "ELL": "English Literary Studies",
    "END": "Engineering and the Built Environment", "FAM": "Film and Media Studies",
    "GEO": "Geological Sciences", "HST": "Historical Studies", "HUB": "Human Biology",
    "INF": "Information Systems", "MAM": "Mathematics and Applied Mathematics",
    "MEC": "Mechanical Engineering", "PHI": "Philosophy", "PHY": "Physics",
    "POL": "Political Studies", "REL": "Study of Religions", "SLL": "Languages and Literatures",
    "SOC": "Sociology", "STA": "Statistical Sciences", "FTX": "Finance and Tax",
}



def prefix(code: str) -> str:
    match = re.match(r"([A-Z]+)", code)
    return match.group(1) if match else ""


def semester_from_code(code: str) -> list[str]:
    suffix = re.sub(r"^[A-Z]+\d{4}", "", code)
    return {
        "F": ["First semester"], "S": ["Second semester"], "W": ["Whole year"],
        "H": ["Half course over whole year"], "L": ["Winter term"],
        "P": ["Summer term"], "U": ["Summer term"], "J": ["Summer term"],
        "A": ["First quarter"], "B": ["Second quarter"], "C": ["Third quarter"],
        "D": ["Fourth quarter"], "X": ["Non-standard period"], "Z": ["Other/non-standard period"],
    }.get(suffix, [])


def course_rule(code: str, label: str | None = None, **extra: Any) -> dict[str, Any]:
    rule = {"type": "course", "id": f"course_{code.lower()}", "label": label or f"Pass {code}", "course_codes": [code]}
    rule.update(extra)
    return rule


def choose_rule(rule_id: str, label: str, codes: list[str], required: int, **extra: Any) -> dict[str, Any]:
    rule = {"type": "choose_n", "id": rule_id, "label": label, "course_codes": codes, "required": required}
    rule.update(extra)
    return rule


def credit_pool(rule_id: str, label: str, codes: list[str], required: int, **extra: Any) -> dict[str, Any]:
    rule = {"type": "credit_pool", "id": rule_id, "label": label, "course_codes": codes, "required": required}
    rule.update(extra)
    return rule


def approved_credit_pool(
    rule_id: str,
    label: str,
    required: int,
    *,
    codes: list[str] | None = None,
    transcript_course_codes: list[str] | None = None,
    exclude_codes: list[str] | None = None,
    transcript_filters: dict[str, Any] | None = None,
    approval_note: str = "Faculty approval and live registration eligibility must be confirmed.",
    transcript_only: bool = False,
    allow_unlisted_transcript_courses: bool = False,
    **extra: Any,
) -> dict[str, Any]:
    rule = {
        "type": "approved_credit_pool",
        "id": rule_id,
        "label": label,
        "required": required,
        "course_codes": codes or [],
        "transcript_course_codes": transcript_course_codes or [],
        "exclude_course_codes": exclude_codes or [],
        "transcript_filters": transcript_filters or {},
        "approval_note": approval_note,
        "verification_status": "unverified",
        "transcript_only": transcript_only,
        "allow_unlisted_transcript_courses": allow_unlisted_transcript_courses,
    }
    rule.update(extra)
    return rule


def manual(rule_id: str, label: str, note: str, *, blocking: bool = True, status: str = "discretionary") -> dict[str, Any]:
    return {
        "type": "manual", "id": rule_id, "label": label, "note": note,
        "assumed_complete": True, "blocking": blocking, "status": status,
    }


def annual_progress(first: int, concession: int | None, later: int, years: int, label: str) -> list[dict[str, Any]]:
    rules: list[dict[str, Any]] = [{
        "type": "annual_credits", "year": 1, "minimum": first,
        "concession_minimum": concession, "label": f"{label}: first-year progression",
    }]
    for year in range(2, years + 2):
        rules.append({
            "type": "annual_credits", "year": year, "minimum": later,
            "label": f"{label}: subsequent-year progression",
        })
    return rules


def engineering_awards(project_code: str, minimum_years: int) -> list[dict[str, Any]]:
    return [
        {
            "name": "First class honours",
            "complete_within_years": minimum_years,
            "curriculum_rules": [
                {"type": "weighted_average", "id": "first_class_cwa", "label": "Cumulative credit-weighted average", "minimum_average": 75},
                {"type": "minimum_mark", "id": "first_class_project", "label": f"Research project {project_code}", "course_codes": [project_code], "minimum_mark": 75},
            ],
        },
        {
            "name": "Honours",
            "complete_within_years": minimum_years,
            "curriculum_rules": [
                {"type": "weighted_average", "id": "honours_cwa", "label": "Cumulative credit-weighted average", "minimum_average": 65},
                {"type": "minimum_mark", "id": "honours_project", "label": f"Research project {project_code}", "course_codes": [project_code], "minimum_mark": 60},
            ],
        },
    ]


def pathway(name: str, *, rules: list[dict[str, Any]] | None = None, status: str = "verified", availability: str = "open", note: str = "", page: int = 0) -> dict[str, Any]:
    return {
        "name": name, "curriculum_rules": rules or [], "verification_status": status,
        "availability": availability, "availability_note": note,
        "source": {"document": SOURCE_DOCUMENT, "page": page},
    }


def programme(
    name: str, code: str, total: int, years: int, core: list[str], page: int,
    *, curriculum_rules: list[dict[str, Any]] | None = None,
    scope_verified: bool = True, availability: str = "open", availability_note: str = "",
    progression_rules: list[dict[str, Any]] | None = None,
    award_rules: list[dict[str, Any]] | None = None,
    pathways: dict[str, Any] | None = None, pathway_required: bool = False,
    default_pathway_key: str = "", notes: list[str] | None = None,
    max_years: int | None = None,
) -> dict[str, Any]:
    return {
        "name": name,
        "minimum_nqf_credits": total,
        "minimum_nqf_level_7_credits": 0,
        "minimum_semester_courses": 0,
        "minimum_senior_semester_courses": 0,
        "minimum_majors": 0,
        "minimum_humanities_semester_courses": 0,
        "minimum_humanities_majors": 0,
        "required_courses": core,
        "qualification_codes": [code],
        "scope_verified": scope_verified,
        "route_type": "structured",
        "degree_category": "EBE",
        "minimum_duration_years": years,
        "maximum_registration_years": max_years,
        "programme_type": "structured",
        "curriculum_rules": curriculum_rules or [],
        "pathways": pathways or {},
        "pathway_required": pathway_required,
        "default_pathway_key": default_pathway_key,
        "availability": availability,
        "availability_note": availability_note,
        "progression_rules": progression_rules or [],
        "award_rules": award_rules or [],
        "progression_notes": notes or [],
        "award_notes": ["Awards remain subject to Senate approval under FB9."],
        "source": {"document": SOURCE_DOCUMENT, "page": page, "section": "Programmes of Study"},
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rows: dict[str, list[dict[str, Any]]] = json.loads(ROWS_PATH.read_text())
    descriptions: list[dict[str, Any]] = json.loads(DESCRIPTIONS_PATH.read_text())
    hum_courses: list[dict[str, Any]] = json.loads(HUM_COURSES_PATH.read_text())

    facts: dict[str, dict[str, Any]] = {}
    for raw in descriptions:
        code = raw["code"].upper()
        facts[code] = {
            "code": code,
            "name": raw.get("name", "").title(),
            "credits": int(raw.get("credits", 0)),
            "nqf_level": int(raw.get("nqf_level", 0)),
            "prerequisites": raw.get("prerequisites", []),
            "prerequisites_verified": bool(raw.get("prerequisites_verified", False)),
            "co_requisites": raw.get("co_requisites", []),
            "offered": [] if raw.get("not_offered_2026") else raw.get("offered", []),
            "offering_verified": bool(raw.get("offering_verified", False)),
            "department": PREFIX_DEPARTMENT.get(prefix(code), prefix(code)),
            "description": "",
            "verification_status": raw.get("verification_status", "verified"),
            "source": raw.get("source", {"document": SOURCE_DOCUMENT}),
            "general_elective": False,
            "counts_towards_general_degree": True,
            "counts_as_humanities": False,
            "counts_towards_course_equivalents": False,
            "credit_bearing": int(raw.get("credits", 0)) > 0,
            "recognition_note": "Counts only when included in the selected EBE curriculum or approved elective pool.",
        }

    # Curriculum tables sometimes contain service courses whose full outline is
    # elsewhere in the handbook series. Preserve the table values as verified
    # curriculum facts and mark prerequisite extraction separately.
    for route_rows in rows.values():
        for raw in route_rows:
            code = raw["code"].upper()
            if code not in facts:
                facts[code] = {
                    "code": code, "name": raw["name"], "credits": int(raw["credits"]),
                    "nqf_level": int(raw["level"]), "prerequisites": [],
                    "prerequisites_verified": int(raw["level"]) == 5,
                    "co_requisites": [], "offered": semester_from_code(code),
                    "offering_verified": bool(semester_from_code(code)),
                    "department": PREFIX_DEPARTMENT.get(prefix(code), prefix(code)),
                    "description": "", "verification_status": "verified",
                    "source": {"document": SOURCE_DOCUMENT, "page": int(raw.get("page", 0)), "section": "Programme curriculum table"},
                    "general_elective": False, "counts_towards_general_degree": True,
                    "counts_as_humanities": False, "counts_towards_course_equivalents": False,
                    "credit_bearing": int(raw["credits"]) > 0,
                    "recognition_note": "Curriculum-table fact; prerequisites require confirmation if not stated in the EBE course outline.",
                }

    # Cross-faculty courses expressly used by the Chemical Engineering
    # Humanities-selection rule.  The handbook permits whole disciplinary
    # prefixes (with Linguistics excluded from ASL) plus a short named list.
    human_by_code = {c["code"]: c for c in hum_courses}
    african_studies_codes = {
        code for code, row in human_by_code.items()
        if code.startswith(("AFS", "ANS"))
        or (
            code.startswith("ASL")
            and not any(token in row.get("name", "").lower() for token in ("language", "linguist", "sociolingu"))
        )
    }
    broad_humanities_codes = {
        code for code in human_by_code
        if code.startswith(("AGE", "HST", "PHI", "SOC"))
    }
    named_humanities_codes = {
        "ELL1013F", "ELL1016S", "ELL2000F", "ELL2001S",
        "END1019L", "END1019Z",
        "FAM1001F", "FAM1001L", "FAM1001P",
        "REL1002F", "REL1006S",
        "SLL1054F", "SLL1057F", "SLL1068F", "SLL1068S", "SLL1068P",
        "SLL1097F", "SLL2058F", "SLL2090S",
        "POL1004F", "POL1004L", "POL1004P",
    }
    chemical_humanities_allowed_codes = sorted(
        african_studies_codes | broad_humanities_codes | named_humanities_codes
    )
    chemical_humanities_codes: list[str] = []
    for code in chemical_humanities_allowed_codes:
        if code in facts:
            chemical_humanities_codes.append(code)
            continue
        source = human_by_code.get(code)
        if source:
            copied = dict(source)
            copied["general_elective"] = False
            copied["counts_towards_course_equivalents"] = False
            copied["recognition_note"] = (
                "Permitted only where the selected Chemical Engineering Humanities-selection rule allows it."
            )
            facts[code] = copied
            chemical_humanities_codes.append(code)
            continue
        stem = re.sub(r"[A-Z]+$", "", code)
        sibling = next(
            (
                value for sibling_code, value in {**facts, **human_by_code}.items()
                if re.sub(r"[A-Z]+$", "", sibling_code) == stem
            ),
            None,
        )
        if sibling:
            copied = dict(sibling)
            copied["code"] = code
            copied["offered"] = semester_from_code(code)
            copied["offering_verified"] = False
            copied["verification_status"] = "provisional"
            copied["source"] = {
                "document": SOURCE_DOCUMENT,
                "page": 36,
                "section": "Chemical Engineering Humanities elective list",
            }
            copied["general_elective"] = False
            copied["counts_towards_course_equivalents"] = False
            copied["recognition_note"] = (
                "Permitted variant listed in the EBE elective rule; live offering and exact course outline require confirmation."
            )
            facts[code] = copied
            chemical_humanities_codes.append(code)

    # Named variants for which the handbook provides permission but no full
    # course outline remain transcript-only options.  They are not assigned
    # fabricated credits or prerequisites.
    chemical_humanities_transcript_only = sorted(
        set(chemical_humanities_allowed_codes) - set(chemical_humanities_codes)
    )

    # Explicit level-8 Chemical Engineering elective options omitted from the
    # compact programme-row extraction but stated in the elective section.
    chemical_level8_credits = {
        "CHE4057F": 8, "CHE4058Z": 8, "CHE4068F": 16,
        "CHE4069F": 16, "CHE4070F": 16, "CHE4072F": 16,
    }
    for code, elective_credits in chemical_level8_credits.items():
        if code not in facts:
            facts[code] = {
                "code": code, "name": code, "credits": elective_credits, "nqf_level": 8,
                "prerequisites": [], "prerequisites_verified": False,
                "co_requisites": [], "offered": semester_from_code(code),
                "offering_verified": False, "department": "Chemical Engineering",
                "description": "", "verification_status": "provisional",
                "source": {"document": SOURCE_DOCUMENT, "page": 37, "section": "Chemical Engineering advanced electives"},
                "general_elective": False, "counts_towards_general_degree": True,
                "counts_as_humanities": False, "counts_towards_course_equivalents": False,
                "credit_bearing": True,
                "recognition_note": "Elective option named in the programme section; current offering and prerequisites require confirmation.",
            }

    def codes(key: str) -> list[str]:
        return [row["code"] for row in rows[key]]

    # Reusable elective pools.
    chem_science = ["BIO1000F", "CHE2006S", "CEM2005W", "GEO1009F", "GEO2006S"]
    chem_advanced = ["CHE3067S", "CHE3068S", "CHE3069S", "CHE3070S", "CHE4057F", "CHE4058Z", "CHE4068F", "CHE4069F", "CHE4070F", "CHE4072F"]
    chem_core4 = codes("chem4")[:18]
    chem_core5 = codes("chem5")
    chem_elective_rules = [
        credit_pool("science_electives", "Science elective credits", chem_science, 42),
        credit_pool("science_level6", "Science elective credits at NQF level 6 or above", chem_science, 24, filters={"nqf_levels": [6, 7, 8]}),
        manual(
            "other_science_combination",
            "Other approved Science-elective combination",
            "The Programme Convener may approve other Science-elective combinations; a transcript alone cannot establish that approval.",
            blocking=False,
            status="discretionary",
        ),
        approved_credit_pool(
            "humanities_electives",
            "Approved Humanities elective credits",
            15,
            codes=chemical_humanities_codes,
            transcript_course_codes=chemical_humanities_allowed_codes,
            approval_note=(
                "The EBE handbook lists these Humanities disciplines/courses, but offering, prerequisites and any exceptional approval still require confirmation."
            ),
        ),
        credit_pool("advanced_engineering", "Advanced Engineering elective credits", chem_advanced, 32),
        manual(
            "other_advanced_engineering",
            "Other approved advanced EBE elective",
            "A third- or fourth-year EBE course outside the printed list may count only with Programme Convener approval and where content has not already been covered.",
            blocking=False,
            status="discretionary",
        ),
        credit_pool("advanced_level8", "Advanced Engineering credits at NQF level 8", chem_advanced, 16, filters={"nqf_levels": [8]}),
        approved_credit_pool(
            "free_elective",
            "Free elective credits",
            15,
            transcript_only=True,
            allow_unlisted_transcript_courses=True,
            approval_note=(
                "The handbook permits any UCT course for which prerequisites are met and content is not duplicated; the static catalogue cannot verify those conditions."
            ),
        ),
    ]

    programmes: dict[str, Any] = {}

    programmes["bas"] = programme(
        "Bachelor of Architectural Studies", "EB012APG01", 432, 3, codes("bas"), 22,
        scope_verified=False, max_years=4,
        curriculum_rules=[manual(
            "bas_credit_conflict", "Published BAS credit reconciliation",
            "FB3.2 states a 432-credit minimum, while the printed BAS curriculum table totals fewer credits. Faculty confirmation is required before a graduation conclusion can be definitive.",
            status="conflict",
        )],
        progression_rules=[
            {"type": "failed_any", "label": "No failed BAS major course", "course_codes": ["APG1003W", "APG1020W", "APG2021W", "APG2039W", "APG3023W", "APG3037W"]},
            {"type": "repeat_failure", "label": "No course failed more than once", "maximum_failures": 1},
            {"type": "pass_rate", "label": "Pass at least 80% of annual registered credits", "minimum": 0.8},
            {"type": "maximum_years", "label": "Complete within four years", "maximum": 4},
        ],
        award_rules=[{
            "name": "Degree with distinction", "complete_within_years": 3,
            "curriculum_rules": [
                {"type": "minimum_mark", "id": "studio3", "label": "Design & Theory Studio III", "course_codes": ["APG3037W"], "minimum_mark": 75},
                {"type": "minimum_mark", "id": "earlier_studio", "label": "Earlier Design & Theory Studio examination", "course_codes": ["APG1020W", "APG2039W"], "minimum_mark": 70},
                {"type": "passed_mark_count", "id": "additional_firsts", "label": "Three additional first-class BAS passes", "required": 3, "minimum_mark": 75, "exclude_course_codes": ["APG1020W", "APG2039W", "APG3037W"]},
            ],
        }],
    )

    # Geomatics curricula are in a documented 2026 transition. The route is
    # usable, but the current-intake sequence cannot be projected beyond the
    # years published in the handbook without verification.
    geom_awards = engineering_awards("APG4003Z", 4)
    for key, route_key, name, code, years, total, page, availability in [
        ("geomatics_surveying_4", "geom_survey4", "BSc Geomatics — Surveying (4-year)", "EB019APG09", 4, 519, 25, "open"),
        ("geomatics_surveying_5", "geom_survey5", "BSc Geomatics — Surveying (5-year ASPECT)", "EB819APG09", 5, 519, 26, "open"),
        ("geomatics_geoinformatics_cs_4", "geom_geo_cs4", "BSc Geomatics — Geoinformatics/Computer Science (4-year)", "EB019APG11", 4, 519, 28, "open"),
        ("geomatics_geoinformatics_cs_5", "geom_geo_cs5", "BSc Geomatics — Geoinformatics/Computer Science (5-year ASPECT)", "EB819APG11", 5, 519, 30, "open"),
        ("geomatics_geoinformatics_egs_4", "geom_geo_egs4", "BSc Geomatics — Geoinformatics/EGS (4-year, continuing students)", "EB019APG11", 4, 576, 31, "continuing_only"),
        ("geomatics_geoinformatics_egs_5", "geom_geo_egs5", "BSc Geomatics — Geoinformatics/EGS (5-year, continuing students)", "EB819APG11", 5, 576, 32, "continuing_only"),
    ]:
        all_codes = codes(route_key)
        rules: list[dict[str, Any]] = []
        core = all_codes
        if "_egs_" in key:
            egs_options = ["EGS3012S", "EGS3021F", "EGS3022S", "EGS3023F"]
            core = [c for c in all_codes if c not in egs_options]
            rules.append(choose_rule("egs_level7", "Choose two approved EGS level-7 electives", egs_options, 2))
        elif "surveying" in key:
            rules.append(approved_credit_pool(
                "surveying_elective",
                "Approved NQF level-7 elective",
                12,
                codes=["APG3039B"] if "APG3039B" in facts else [],
                transcript_filters={"nqf_levels": [7]},
                allow_unlisted_transcript_courses=True,
                approval_note=(
                    "The Surveying stream requires an approved 12-credit level-7 elective. APG3039B is recommended for an additional registration category, but other approvals require confirmation."
                ),
            ))
        rules.append(manual(
            "geomatics_transition", "Cohort transition confirmation",
            "The handbook states that a new 519-credit curriculum is being phased in from 2026 while a 576-credit curriculum is phased out. The student's intake-year curriculum must be confirmed.",
            status="unverified",
        ))
        first = 80 if years == 5 else 100
        programmes[key] = programme(
            name, code, total, years, core, page, curriculum_rules=rules,
            scope_verified=False, availability=availability,
            availability_note=("This EGS specialisation is being phased out and is not open to new 2026 entrants." if availability != "open" else ""),
            progression_rules=[
                {"type": "annual_credits", "year": 1, "minimum": first, "concession_minimum": 32 if years == 5 else 40, "label": "First-year Geomatics progression"},
                {"type": "manual", "label": "Rolling two-year credit rule", "note": f"Subsequent progression uses a rolling two-year threshold ({192 if years == 5 else 224} credits) and transfer/re-registration variants that require year-labelled records."},
            ],
            award_rules=geom_awards,
            notes=["Fieldwork, practical performance and professional registration conditions remain operational requirements."],
        )

    programmes["chemical_engineering_4"] = programme(
        "BSc Engineering — Chemical Engineering (4-year)", "EB001CHE01", 560, 4, chem_core4, 34,
        curriculum_rules=chem_elective_rules,
        progression_rules=annual_progress(102, 66, 108, 4, "Chemical Engineering 4-year"),
        award_rules=engineering_awards("CHE4045Z", 4),
        notes=["Mandatory reassessment replaces supplementary examinations in specified Chemical Engineering courses."],
    )
    programmes["chemical_engineering_5"] = programme(
        "BSc Engineering — Chemical Engineering (5-year ASPECT)", "EB801CHE01", 560, 5, chem_core5, 37,
        curriculum_rules=chem_elective_rules,
        progression_rules=annual_progress(66, 48, 82, 5, "Chemical Engineering 5-year"),
        award_rules=engineering_awards("CHE4045Z", 5),
    )

    civil_paths = {
        "current_560": pathway("Current 560-credit curriculum", page=40),
        "legacy_576": pathway("Legacy 576-credit curriculum", rules=[{"type": "credits", "id": "legacy_credits", "label": "Legacy curriculum credits", "required": 576}], status="provisional", page=40),
    }
    programmes["civil_engineering_4"] = programme(
        "BSc Engineering — Civil Engineering (4-year)", "EB002CIV01", 560, 4, codes("civil4"), 40,
        curriculum_rules=[approved_credit_pool(
            "civil_elective", "Approved Civil Engineering elective", 18,
            transcript_only=True, allow_unlisted_transcript_courses=True,
            approval_note="The handbook requires one approved elective of at least 18 credits but does not print the complete current list.",
        )],
        pathways=civil_paths, pathway_required=True, default_pathway_key="current_560",
        progression_rules=annual_progress(112, 68, 112, 4, "Civil Engineering 4-year"),
        award_rules=engineering_awards("CIV4044S", 4),
    )
    programmes["civil_engineering_5"] = programme(
        "BSc Engineering — Civil Engineering (5-year ASPECT)", "EB802CIV01", 560, 5, codes("civil5"), 43,
        curriculum_rules=[approved_credit_pool(
            "civil_elective", "Approved Civil Engineering elective", 18,
            transcript_only=True, allow_unlisted_transcript_courses=True,
            approval_note="The handbook requires one approved elective of at least 18 credits but does not print the complete current list.",
        )],
        pathways=civil_paths, pathway_required=True, default_pathway_key="current_560",
        progression_rules=annual_progress(94, 52, 94, 5, "Civil Engineering 5-year"),
        award_rules=engineering_awards("CIV4044S", 5),
    )

    programmes["construction_studies"] = programme(
        "BSc Construction Studies", "EB015CON04", 432, 3, codes("construction"), 45,
        scope_verified=False,
        curriculum_rules=[manual("construction_credit_conflict", "Published credit reconciliation", "FB3.2 requires at least 432 credits, while the printed prescribed-course table totals 422 credits. Faculty confirmation of the missing/transition credit component is required.", status="conflict")],
        progression_rules=[
            {"type": "cumulative_credits", "year": 1, "minimum": 100, "concession_minimum": 54, "label": "End of first year"},
            {"type": "cumulative_credits", "year": 2, "minimum": 200, "label": "End of second year"},
            {"type": "cumulative_credits", "year": 3, "minimum": 325, "label": "End of third year"},
            {"type": "cumulative_credits", "year": 4, "minimum": 432, "label": "End of fourth year"},
        ],
        award_rules=[{"name": "Degree with distinction", "curriculum_rules": [{"type": "weighted_average", "id": "distinction_cwa", "label": "Cumulative credit-weighted average", "minimum_average": 75}]}],
        max_years=4,
    )
    programmes["property_studies"] = programme(
        "BSc Property Studies", "EB017CON03", 452, 3, codes("property"), 46,
        scope_verified=False,
        curriculum_rules=[manual("property_credit_conflict", "Published credit reconciliation", "The programme text requires at least 452 credits, while the printed prescribed-course table totals fewer credits. Faculty confirmation of the remaining approved component is required.", status="conflict")],
        progression_rules=[
            {"type": "cumulative_credits", "year": 1, "minimum": 100, "concession_minimum": 54, "label": "End of first year"},
            {"type": "cumulative_credits", "year": 2, "minimum": 200, "label": "End of second year"},
            {"type": "cumulative_credits", "year": 3, "minimum": 325, "label": "End of third year"},
            {"type": "cumulative_credits", "year": 4, "minimum": 452, "label": "End of fourth year"},
        ],
        award_rules=[{"name": "Degree with distinction", "curriculum_rules": [{"type": "weighted_average", "id": "distinction_cwa", "label": "Cumulative credit-weighted average", "minimum_average": 75}]}],
        max_years=4,
    )

    eee_specs = [
        ("electrical_engineering_4", "ee4", "BSc Engineering — Electrical Engineering (4-year)", "EB009EEE01", 4, 48),
        ("electrical_engineering_5", "ee5", "BSc Engineering — Electrical Engineering (5-year ASPECT)", "EB809EEE01", 5, 49),
        ("electrical_computer_engineering_4", "ece4", "BSc Engineering — Electrical & Computer Engineering (4-year)", "EB022EEE02", 4, 52),
        ("electrical_computer_engineering_5", "ece5", "BSc Engineering — Electrical & Computer Engineering (5-year ASPECT)", "EB822EEE02", 5, 54),
        ("mechatronics_engineering_eee_4", "mechatronics_eee4", "BSc Engineering — Mechatronics (Electrical Engineering, 4-year)", "EB011EEE05", 4, 56),
        ("mechatronics_engineering_eee_5", "mechatronics_eee5", "BSc Engineering — Mechatronics (Electrical Engineering, 5-year ASPECT)", "EB811EEE05", 5, 58),
    ]
    for key, row_key, name, code, years, page in eee_specs:
        all_codes = codes(row_key)
        placeholder = {"EEE3000X"}
        rules: list[dict[str, Any]] = [approved_credit_pool(
            "complementary",
            "Approved complementary studies elective",
            18,
            transcript_only=True,
            allow_unlisted_transcript_courses=True,
            transcript_filters={
                "exclude_prefixes": [
                    "APG", "BIO", "CEM", "CHE", "CIV", "CON", "CSC",
                    "EEE", "END", "GEO", "MAM", "MEC", "PHY", "STA",
                ]
            },
            approval_note=(
                "The handbook refers to a separate approved complementary-studies list; course approval, prerequisites and live offering must be confirmed."
            ),
        )]
        if key.startswith("electrical_engineering"):
            primary = ["EEE4126F", "EEE4118F", "EEE4121F"]
            extra = ["EEE4114F", "EEE4117F", "HUB4049F"]
            option_codes = primary + extra
            rules += [choose_rule("elective_primary", "At least one primary Electrical Engineering elective", primary, 1), credit_pool("elective_total", "Fourth-year elective core credits", option_codes, 48)]
        elif key.startswith("electrical_computer"):
            mid = ["CSC2002S", "EEE3093S", "EEE3094S"]
            final_primary = ["EEE4114F", "EEE4118F", "EEE4120F", "EEE4121F"]
            final_extra = ["HUB4049F"]
            option_codes = mid + final_primary + final_extra
            rules += [
                choose_rule("third_year_options", "Choose two third-year options", mid, 2),
                choose_rule("final_primary", "At least two ECE elective-core courses", final_primary, 2),
                approved_credit_pool(
                    "final_total",
                    "Final elective-core credits",
                    48,
                    codes=final_primary + final_extra,
                    transcript_filters={"prefixes": ["CSC"], "year_levels": [3, 4], "nqf_levels": [7, 8]},
                    allow_unlisted_transcript_courses=True,
                    approval_note="An approved 3000-level Computer Science course may form part of the final elective total; departmental approval must be confirmed.",
                ),
            ]
        else:
            primary = ["EEE4117F", "EEE4118F", "EEE4119F"]
            extra = ["EEE4114F", "EEE4120F", "HUB4049F"]
            option_codes = primary + extra
            rules += [choose_rule("elective_primary", "Choose at least two Mechatronics elective-core courses", primary, 2), credit_pool("elective_total", "Final elective-core credits", option_codes, 48)]
        core = [c for c in all_codes if c not in placeholder and c not in set(option_codes)]
        # ECE's third-year alternatives are options, not simultaneous core.
        if key.startswith("electrical_computer"):
            core = [c for c in core if c not in {"CSC2002S", "EEE3093S", "EEE3094S"}]
        current_later = 112 if years == 4 else 92
        legacy_later = 116 if years == 4 else 96
        paths = {
            "current_560": pathway("Current 560-credit curriculum", page=page),
            "legacy_576": pathway("Legacy 576-credit curriculum", rules=[{"type": "credits", "id": "legacy_credits", "label": "Legacy curriculum credits", "required": 576}, manual("legacy_equivalents", "Legacy complementary-course equivalents", "Students on the 576-credit curriculum may need outstanding ASL1200S/CON2026S or approved equivalents.")], status="provisional", page=page),
        }
        programmes[key] = programme(
            name, code, 560, years, core, page, curriculum_rules=rules,
            pathways=paths, pathway_required=True, default_pathway_key="current_560",
            progression_rules=annual_progress(96 if years == 4 else 60, 66 if years == 4 else 48, current_later, years, name),
            award_rules=engineering_awards("EEE4022S", years),
            notes=[f"The legacy 576-credit curriculum uses a {legacy_later}-credit subsequent-year progression threshold; the current route uses {current_later}."],
        )

    mechanical_specs = [
        ("mechanical_engineering_4", "mech4", "BSc Engineering — Mechanical Engineering (4-year)", "EB005MEC01", 4, 61, 27),
        ("mechanical_engineering_5", "mech5", "BSc Engineering — Mechanical Engineering (5-year ASPECT)", "EB805MEC01", 5, 63, 27),
        ("mechanical_mechatronic_engineering_4", "mechmech4", "BSc Engineering — Mechanical & Mechatronic Engineering (4-year)", "EB010MEC05", 4, 65, 15),
        ("mechanical_mechatronic_engineering_5", "mechmech5", "BSc Engineering — Mechanical & Mechatronic Engineering (5-year ASPECT)", "EB810MEC05", 5, 67, 15),
    ]
    for key, row_key, name, code, years, page, open_credits in mechanical_specs:
        core = codes(row_key)
        paths = {
            "current_560": pathway("Current 560-credit curriculum", page=page),
            "legacy_576": pathway("Legacy 576-credit curriculum", rules=[{"type": "credits", "id": "legacy_credits", "label": "Legacy curriculum credits", "required": 576}], status="provisional", page=page),
        }
        programmes[key] = programme(
            name, code, 560, years, core, page,
            curriculum_rules=[
                approved_credit_pool(
                    "complementary_open_electives",
                    "Approved complementary and open elective credits",
                    15 + open_credits,
                    transcript_only=True,
                    allow_unlisted_transcript_courses=True,
                    approval_note=(
                        f"The route requires 15 approved category-(b) complementary-studies credits and {open_credits} approved open-elective credits. "
                        "The transcript does not establish category allocation, prerequisites, timetable fit or advisor approval."
                    ),
                ),
                manual(
                    "elective_category_allocation",
                    "Elective category allocation",
                    f"Faculty confirmation is required that at least 15 credits satisfy complementary-studies category (b) and at least {open_credits} credits satisfy the open-elective requirement.",
                    blocking=True,
                    status="unverified",
                ),
            ],
            pathways=paths, pathway_required=True, default_pathway_key="current_560",
            progression_rules=annual_progress(116 if years == 4 else 96, 90 if years == 4 else 70, 116 if years == 4 else 96, years, name),
            award_rules=engineering_awards("MEC4128Z", years),
        )

    # Restricted transfer/conversion routes are visible and scoped, but the
    # transcript alone cannot establish exemptions, prior-degree equivalence,
    # or Senate permission. They therefore cannot yield a false positive.
    restricted_routes = {
        "chemical_engineering_transfer_conversion": ("Chemical Engineering — transferee/conversion route", "EB001CHE06", 560, 3, 39, chem_core4, "Prior qualification credits, CHE1001P and individual exemption decisions must be confirmed."),
        "chemical_engineering_uot_access": ("Chemical Engineering — University of Technology access route", "EB001CHE06", 560, 3, 40, chem_core4, "Admission, exemption and the 436-credit access curriculum depend on an approved prior diploma record."),
        "civil_engineering_uot_access": ("Civil Engineering — University of Technology transferee route", "EB002CIV01", 560, 3, 45, codes("civil4"), "The department must approve transfer credits and the resulting individual curriculum."),
        "electrical_engineering_uot_access": ("Electrical Engineering programmes — University of Technology access", "EB009EEE01", 560, 3, 61, [], "Admission and course exemptions are individually determined from the prior diploma and cannot be inferred from the UCT transcript alone."),
        "mechanical_engineering_uot_access": ("Mechanical Engineering programmes — University of Technology access", "EB005MEC01", 560, 3, 69, [], "Admission and course exemptions are individually determined from the prior diploma and cannot be inferred from the UCT transcript alone."),
    }
    for key, (name, code, total, years, page, core, note) in restricted_routes.items():
        programmes[key] = programme(
            name, code, total, years, core, page,
            scope_verified=False, availability="restricted", availability_note=note,
            curriculum_rules=[manual("individual_curriculum", "Approved individual transfer curriculum", note)],
            progression_rules=[{"type": "manual", "label": "Transfer-specific progression", "note": "Faculty progression must be applied to the formally approved transfer curriculum."}],
        )

    requirements = {
        "source": f"{SOURCE_DOCUMENT}; {GENERAL_SOURCE}",
        "catalogue_version": "2026.1-ebe",
        "programmes": programmes,
        "majors": {},
        "forbidden_major_combinations": [],
        "cross_credit_exclusions": [],
    }

    # Keep only facts used by at least one route or its explicit rule pool.
    used: set[str] = set()
    def collect(obj: Any) -> None:
        if isinstance(obj, dict):
            for key, value in obj.items():
                if key in {"required_courses", "course_codes", "support_course_codes", "elective_course_codes"} and isinstance(value, list):
                    used.update(str(code).upper() for code in value)
                else:
                    collect(value)
        elif isinstance(obj, list):
            for value in obj:
                collect(value)
    collect(programmes)
    used.update(code for p in programmes.values() for code in p.get("required_courses", []))

    course_rows = [facts[code] for code in sorted(used) if code in facts]
    missing = sorted(used - set(facts))
    if missing:
        raise SystemExit("Missing course facts: " + ", ".join(missing))

    (OUT / "courses.json").write_text(json.dumps(course_rows, indent=2, ensure_ascii=False) + "\n")
    (OUT / "degree_requirements.json").write_text(json.dumps(requirements, indent=2, ensure_ascii=False) + "\n")
    print(f"Wrote {len(course_rows)} EBE course facts and {len(programmes)} programme routes to {OUT}")


if __name__ == "__main__":
    main()
