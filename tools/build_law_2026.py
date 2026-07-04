#!/usr/bin/env python3
"""Build the 2026 UCT Law undergraduate (LLB) catalogue.

The Law faculty is modelled as a level-based curriculum rather than a major-
based degree.  The generator keeps the four-year, graduate, combined and
continuing five-year routes separate, preserves route-specific prerequisite
patterns, and represents Final Level research/elective choices explicitly.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "uct_law"
HUM_COURSES = ROOT / "data" / "uct_humanities" / "courses.json"
SOURCE = "2026 Faculty of Law Handbook"
GENERAL = "2026 General Rules and Policies Handbook"

PREFIX_DEPARTMENT = {
    "CML": "Commercial Law",
    "PVL": "Private Law",
    "PBL": "Public Law",
    "DOL": "Dean of Law",
    "ELL": "English Literary Studies",
    "SLL": "Languages and Literatures",
    "MAM": "Mathematics and Applied Mathematics",
    "PTY": "Pathology",
}


def prefix(code: str) -> str:
    m = re.match(r"[A-Z]+", code)
    return m.group(0) if m else ""


def offering(code: str) -> list[str]:
    suffix = re.sub(r"^[A-Z]+\d{4}", "", code)
    return {
        "F": ["First semester"],
        "S": ["Second semester"],
        "W": ["Whole year"],
        "H": ["Half course over whole year"],
        "X": ["Non-standard period"],
        "Z": ["Other/non-standard period"],
    }.get(suffix, [])


def fact(
    code: str,
    name: str,
    credits: int,
    level: int,
    page: int,
    *,
    offered: bool = True,
    prerequisites: list[str] | None = None,
    co_requisites: list[str] | None = None,
    note: str = "",
) -> dict[str, Any]:
    return {
        "code": code,
        "name": name,
        "credits": credits,
        "nqf_level": level,
        "prerequisites": prerequisites or [],
        "prerequisites_verified": True,
        "co_requisites": co_requisites or [],
        "offered": offering(code) if offered else [],
        "offering_verified": True,
        "department": PREFIX_DEPARTMENT.get(prefix(code), prefix(code)),
        "description": "",
        "verification_status": "verified",
        "source": {
            "document": SOURCE,
            "page": page,
            "section": "LLB curriculum/course outline",
        },
        "general_elective": False,
        "counts_towards_general_degree": True,
        "counts_as_humanities": False,
        "counts_towards_course_equivalents": False,
        "credit_bearing": credits > 0,
        "recognition_note": note
        or "Counts only inside a selected LLB route or its published elective/research component.",
    }


def course_rule(code: str, label: str | None = None) -> dict[str, Any]:
    return {
        "type": "course",
        "id": f"course_{code.lower()}",
        "label": label or f"Pass {code}",
        "course_codes": [code],
    }


def choose(
    rule_id: str, label: str, codes: list[str], required: int = 1
) -> dict[str, Any]:
    return {
        "type": "choose_n",
        "id": rule_id,
        "label": label,
        "course_codes": codes,
        "required": required,
    }


def credit_pool(
    rule_id: str, label: str, codes: list[str], required: int, **extra: Any
) -> dict[str, Any]:
    row = {
        "type": "credit_pool",
        "id": rule_id,
        "label": label,
        "course_codes": codes,
        "required": required,
    }
    row.update(extra)
    return row


def approved_pool(
    rule_id: str,
    label: str,
    required: int,
    *,
    filters: dict[str, Any],
    exclude: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "type": "approved_credit_pool",
        "id": rule_id,
        "label": label,
        "required": required,
        "course_codes": [],
        "transcript_course_codes": [],
        "exclude_course_codes": exclude or [],
        "transcript_filters": filters,
        "transcript_only": True,
        "allow_unlisted_transcript_courses": True,
        "verification_status": "unverified",
        "approval_note": "The transcript course fits the published category, but its use in this LLB curriculum must be confirmed by the Faculty.",
    }


def any_of(rule_id: str, label: str, children: list[dict[str, Any]]) -> dict[str, Any]:
    return {"type": "any_of", "id": rule_id, "label": label, "children": children}


PRELIMINARY = {
    "PVL1003W": ("Foundations of South African Law", 36, 5),
    "PVL1004F": ("South African Private Law: System and Context", 18, 5),
    "PVL1008H": ("Law of Persons and Family", 18, 5),
    "PBL2000W": ("Constitutional Law", 36, 7),
    "PVL2002H": ("Law of Property", 18, 6),
    "PVL2003H": ("Law of Succession", 18, 7),
}
INTERMEDIATE = {
    "CML3001W": ("Corporation Law", 36, 7),
    "PBL3001F": ("International Law", 18, 7),
    "PBL3801W": ("Criminal Law", 36, 7),
    "PVL3003S": ("African Customary Law", 18, 7),
    "PVL3003F": ("Law of Delict", 18, 7),
    "PVL3005W": ("Law of Contract", 36, 7),
    "PVL3006S": ("Jurisprudence", 18, 7),
    "DOL3001X": ("Community Service", 0, 7),
    "DOL3002X": ("Intermediate Year Skills Component", 0, 7),
}
FINAL_CORE = {
    "CML4004S": ("Labour Law", 18, 8),
    "CML4006W": ("Commercial Transactions Law", 36, 8),
    "PBL4001W": ("Administrative Law", 36, 8),
    "PBL4801F": ("Law of Evidence", 18, 8),
    "PBL4802F": ("Criminal Procedure", 18, 8),
    "PVL4008H": ("Civil Procedure", 18, 8),
    "DOL4000H": ("Integrative Assessment Moot", 0, 8),
}

LECTURE_ELECTIVES = {
    "DOL4500F": ("Legal Practice", True),
    "DOL4500S": ("Legal Practice", True),
    "CML4501S": ("Dispute Resolution", True),
    "CML4502F": ("Insurance Law", False),
    "CML4503F": ("Copyright and Patents", False),
    "CML4504S": ("Trademarks and Unlawful Competition", True),
    "CML4505F": ("International Trade and Maritime Law", False),
    "CML4506F": ("Fundamental Principles of Tax Law", True),
    "CML4507S": ("Statutory Tax Law", True),
    "CML4508S": ("Trusts and Estate Planning", False),
    "CML4509S": ("Ways of Doing Business", False),
    "CML4510F": ("Cyberlaw", True),
    "PVL4504S": ("Mineral Law", True),
    "PVL4505F": ("Law of Cession", True),
    "PVL4507F": ("Conflict of Laws", True),
    "PVL4511F": ("Unjustified Enrichment", True),
    "PVL4512S": ("Advanced African Customary Law", True),
    "PVL4513F": ("Advanced Contract Law", True),
    "PBL4111S": ("Public Interest Litigation", True),
    "PBL4501F": ("Criminology: Selected Issues", True),
    "PBL4502F": ("Environmental Law", True),
    "PBL4503F": ("European Union Law", False),
    "PBL4504F": ("International Criminal Law and Africa", True),
    "PBL4505S": ("International Human Rights Law and the Constitution", True),
    "PBL4506F": ("Refugee and Immigration Law", True),
    "PBL4508F": ("Local Government Law", False),
    "PTY4008S": ("Medicina Forensis", True),
    "DOL4501S": ("Law, Democracy and Social Justice", False),
}
RESEARCH_ELECTIVES = {
    "CML4401H": ("Independent Research Paper: Commercial Law", True),
    "CML4601F": ("Theory and Practice of Commercial Regulation", False),
    "CML4602S": ("Competition Law", True),
    "CML4603S": ("Banking Law", True),
    "CML4604F": ("Current Developments in Company Law", False),
    "CML4605F": ("Law, Development, Labour and Social Policy", False),
    "CML4606H": ("Moot Caput: Commercial Law", True),
    "CML4629S": ("Law and Regional Integration in Africa", True),
    "PVL4401H": ("Independent Research Paper: Private Law", True),
    "PVL4601S": ("Advanced Property Law", True),
    "PVL4602S": ("Civil Justice Reform", True),
    "PVL4603F": ("Jurisprudence and South African Law", False),
    "PVL4604S": ("Rhetoric, Law and Society", False),
    "PVL4606F": ("Spatial Justice and the Law", True),
    "PVL4608S": ("Law of Delict: Theoretical and Comparative Perspectives", False),
    "PVL4609H": ("Moot Caput: Private Law", True),
    "PBL4401H": ("Independent Research Paper: Public Law", True),
    "PBL4402H": ("Independent Research Paper: Criminal Justice", True),
    "PBL4601S": ("Constitutional Litigation", True),
    "PBL4602F": ("Criminal Justice and the Constitution", True),
    "PBL4604F": ("Social Justice and the Constitution", True),
    "PBL4605F": ("Women and Law", True),
    "PBL4606H": ("Moot Caput: Public Law", True),
}
INDEPENDENT_RESEARCH = ["CML4401H", "PVL4401H", "PBL4401H", "PBL4402H"]
ALL_FINAL_ELECTIVES = sorted(
    set(LECTURE_ELECTIVES) | set(RESEARCH_ELECTIVES) | {"DOL3000X"}
)
SEMINAR_RESEARCH = sorted(set(RESEARCH_ELECTIVES) - set(INDEPENDENT_RESEARCH))

LANGUAGE_PAIRS = [
    ["SLL1022F", "SLL1023S"],
    ["SLL1050F", "SLL1051S"],
    ["SLL1052F", "SLL1053S"],
    ["SLL1058F", "SLL1059S"],
    ["SLL1060F", "SLL1061S"],
    ["SLL1062F", "SLL1063S"],
    ["SLL1064F", "SLL1065S"],
    ["SLL1073F", "SLL1074S"],
    ["SLL1075F", "SLL1076S"],
    ["SLL1082F", "SLL1083S"],
    ["SLL1101F", "SLL1102S"],
    ["SLL1121F", "SLL1122S"],
    ["SLL1131F", "SLL1132S"],
]


def final_component_rules() -> list[dict[str, Any]]:
    return [
        credit_pool(
            "final_elective_credits",
            "Final Level research/elective component",
            ALL_FINAL_ELECTIVES,
            36,
        ),
        any_of(
            "research_requirement",
            "Seminar/research-paper requirement",
            [
                choose(
                    "seminar_research_elective",
                    "Complete a seminar and research-paper elective",
                    SEMINAR_RESEARCH,
                    1,
                ),
                choose(
                    "independent_research_paper",
                    "Complete an 8,000-word independent research paper",
                    INDEPENDENT_RESEARCH,
                    1,
                ),
                course_rule(
                    "DOL3000X",
                    "Approved Moot Competition substitution (Moot Caput option)",
                ),
            ],
        ),
        {
            "type": "maximum_credit_pool",
            "id": "maximum_final_electives",
            "label": "Maximum Final Level elective credits",
            "course_codes": ALL_FINAL_ELECTIVES,
            "maximum": 54,
            "blocking": True,
        },
    ]


def language_rule() -> dict[str, Any]:
    known = [
        {
            "type": "all_courses",
            "id": f"language_pair_{i}",
            "label": "Complete a two-semester language sequence",
            "course_codes": pair,
        }
        for i, pair in enumerate(LANGUAGE_PAIRS, 1)
    ]
    known.append(
        approved_pool(
            "unlisted_language_sequence",
            "Other approved whole/two-semester language sequence",
            30,
            filters={"prefixes": ["SLL"], "nqf_levels": [5]},
        )
    )
    return any_of("language_requirement", "Language requirement", known)


def other_faculty_rule(
    codes: list[str], required: int, rule_id: str, label: str
) -> dict[str, Any]:
    return any_of(
        rule_id,
        label,
        [
            credit_pool(
                rule_id + "_known", label + " (catalogued options)", codes, required
            ),
            approved_pool(
                rule_id + "_unlisted",
                label + " (other transcript course)",
                required,
                filters={
                    "nqf_levels": [5],
                    "exclude_prefixes": ["CML", "PVL", "PBL", "DOL"],
                },
            ),
        ],
    )


def award_rules(min_years: int) -> list[dict[str, Any]]:
    law_filter = {"prefixes": ["CML", "PVL", "PBL", "DOL"], "credit_bearing": True}
    return [
        {
            "name": "Magna cum laude",
            "complete_within_years": min_years,
            "curriculum_rules": [
                {
                    "type": "no_failures",
                    "id": "magna_no_failures",
                    "label": "No failed course attempts",
                    "condonable": True,
                },
                {
                    "type": "weighted_average",
                    "id": "magna_average",
                    "label": "Average across UCT law courses",
                    "filters": law_filter,
                    "minimum_average": 75,
                },
                {
                    "type": "passed_mark_equivalents",
                    "id": "magna_firsts",
                    "label": "First-class law-course equivalents",
                    "filters": law_filter,
                    "minimum_mark": 75,
                    "required": 9,
                    "equivalent_credit_unit": 36,
                },
            ],
        },
        {
            "name": "Cum laude",
            "complete_within_years": min_years,
            "curriculum_rules": [
                {
                    "type": "no_failures",
                    "id": "cum_no_failures",
                    "label": "No failed course attempts",
                    "condonable": True,
                },
                {
                    "type": "weighted_average",
                    "id": "cum_average",
                    "label": "Average across UCT law courses",
                    "filters": law_filter,
                    "minimum_average": 70,
                },
                {
                    "type": "passed_mark_equivalents",
                    "id": "cum_firsts",
                    "label": "First-class law-course equivalents",
                    "filters": law_filter,
                    "minimum_mark": 75,
                    "required": 6,
                    "equivalent_credit_unit": 36,
                },
            ],
        },
    ]


def progression(max_years: int, failed_threshold: int = 4) -> list[dict[str, Any]]:
    return [
        {
            "type": "failed_course_equivalents",
            "label": "Annual failed-course-equivalent threshold",
            "threshold": failed_threshold,
        },
        {
            "type": "maximum_years",
            "label": "Prescribed time plus one year",
            "maximum": max_years,
        },
    ]


def programme(
    name: str,
    code: str,
    total: int,
    years: int,
    required: list[str],
    page: int,
    *,
    rules: list[dict[str, Any]] | None = None,
    availability: str = "open",
    availability_note: str = "",
    max_years: int | None = None,
    pathways: dict[str, Any] | None = None,
    pathway_required: bool = False,
    prereq_overrides: dict[str, list[str]] | None = None,
    coreq_overrides: dict[str, list[str]] | None = None,
    admission_notes: list[str] | None = None,
    failed_threshold: int = 4,
) -> dict[str, Any]:
    return {
        "name": name,
        "minimum_nqf_credits": total,
        "minimum_nqf_level_7_credits": 0,
        "minimum_semester_courses": 0,
        "minimum_senior_semester_courses": 0,
        "minimum_humanities_semester_courses": 0,
        "minimum_majors": 0,
        "minimum_humanities_majors": 0,
        "required_courses": required,
        "qualification_codes": [code],
        "scope_verified": True,
        "route_type": "structured",
        "degree_category": "Law",
        "minimum_duration_years": years,
        "maximum_registration_years": max_years or years + 1,
        "programme_type": "structured",
        "curriculum_rules": rules or [],
        "pathways": pathways or {},
        "pathway_required": pathway_required,
        "default_pathway_key": "",
        "availability": availability,
        "availability_note": availability_note,
        "progression_rules": progression(max_years or years + 1, failed_threshold),
        "award_rules": award_rules(years),
        "prerequisite_overrides": prereq_overrides or {},
        "co_requisite_overrides": coreq_overrides or {},
        "admission_notes": admission_notes or [],
        "progression_notes": [
            "FP7-FP10 regulate how many outstanding courses may be carried into the next level and require timetable compatibility.",
            "The readmission indicator is not a Faculty Examinations Committee or Senate decision.",
            "FP14's 45% final-examination subminimum cannot be verified from an ordinary transcript total alone.",
        ],
        "award_notes": [
            "FP18 permits Senate to condone a failure and permits exceptional treatment of transferred courses.",
            "Cum laude and magna cum laude remain Senate awards, not automatic software decisions.",
        ],
        "source": {
            "document": SOURCE,
            "page": page,
            "section": "Admission and Curriculum Rules",
        },
    }


def route_overrides(mode: str) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    prelim = list(PRELIMINARY)
    first = ["PVL1003W", "PVL1004F", "PVL1008H"]
    second = ["PBL2000W", "PVL2002H", "PVL2003H"]
    intermediate = list(INTERMEDIATE)
    prior_all = prelim + intermediate
    prereq: dict[str, list[str]] = {}
    coreq: dict[str, list[str]] = {}
    if mode == "graduate":
        for code in prelim:
            prereq[code] = []
            coreq[code] = [other for other in prelim if other != code]
    else:
        for code in first:
            prereq[code] = []
            coreq[code] = [other for other in first if other != code]
        for code in second:
            prereq[code] = first
            coreq[code] = [other for other in second if other != code]
    for code in intermediate:
        prereq[code] = prelim
    for code in list(FINAL_CORE) + ALL_FINAL_ELECTIVES:
        prereq[code] = prior_all
    return prereq, coreq


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    courses: dict[str, dict[str, Any]] = {}
    for code, (name, credits, level) in PRELIMINARY.items():
        courses[code] = fact(code, name, credits, level, 54)
    for code, (name, credits, level) in INTERMEDIATE.items():
        courses[code] = fact(code, name, credits, level, 57)
    for code, (name, credits, level) in FINAL_CORE.items():
        courses[code] = fact(code, name, credits, level, 61)
    courses["DOL3000X"] = fact(
        "DOL3000X",
        "Moot Competition",
        9,
        7,
        57,
        note="May substitute for one seminar/research-paper elective only with the published Moot Caput permission conditions.",
    )
    for code, (name, is_offered) in {**LECTURE_ELECTIVES, **RESEARCH_ELECTIVES}.items():
        note = "Final Level elective."
        if code == "CML4505F":
            note += " The handbook list prints CML4505S while the course outline prints CML4505F; it is not offered in 2026 and the code must be confirmed before future use."
        courses[code] = fact(code, name, 9, 8, 63, offered=is_offered, note=note)

    courses["MAM1013F"] = fact(
        "MAM1013F", "Law That Counts: Quantitative Literacy for Law", 18, 5, 55
    )
    courses["SLL1002S"] = fact("SLL1002S", "Word Power", 15, 5, 55)

    # Continuing-stream equivalences retained as transcript-recognition facts.
    old = {
        "PVL1006W": ("Foundations of South African Law (5YP)", 36, 5),
        "PVL1009S": ("Law of Persons and Family (5YP)", 18, 5),
        "PVL1007F": ("South African Private Law: System and Context (5YP)", 18, 5),
        "PBL2002W": ("Constitutional Law (5YP)", 36, 7),
    }
    for code, (name, credits, level) in old.items():
        courses[code] = fact(
            code,
            name,
            credits,
            level,
            52,
            offered=False,
            note="Legacy five-year LLB course retained for continuing-student transcript recognition; replacement course applies if incomplete.",
        )

    hum = json.loads(HUM_COURSES.read_text())
    hum_by_code = {row["code"]: row for row in hum}
    required_hum = {code for pair in LANGUAGE_PAIRS for code in pair} | {
        "ELL1013F",
        "ELL1016S",
    }
    for code, row in hum_by_code.items():
        if code not in required_hum and not (
            row.get("general_elective") and row.get("nqf_level") in {5, 6}
        ):
            continue
        copied = dict(row)
        copied["general_elective"] = False
        copied["counts_towards_course_equivalents"] = False
        copied["recognition_note"] = (
            "Potential non-law component for the LLB; it counts only when it satisfies the selected route's published non-law category."
        )
        courses.setdefault(code, copied)

    english_options = [
        code for code in ["ELL1013F", "ELL1016S", "SLL1002S"] if code in courses
    ]
    reserved_level5 = (
        set(english_options)
        | {"MAM1013F"}
        | {code for pair in LANGUAGE_PAIRS for code in pair}
    )
    first_year_nonlaw = sorted(
        code
        for code, row in courses.items()
        if row.get("nqf_level") == 5
        and prefix(code) not in {"CML", "PVL", "PBL", "DOL"}
        and code not in reserved_level5
    )
    second_year_nonlaw = sorted(
        code
        for code, row in courses.items()
        if row.get("nqf_level") == 6
        and prefix(code) not in {"CML", "PVL", "PBL", "DOL"}
    )

    law_core = list(PRELIMINARY) + list(INTERMEDIATE) + list(FINAL_CORE)
    common_final = final_component_rules()
    grad_pr, grad_co = route_overrides("graduate")
    ug_pr, ug_co = route_overrides("undergraduate")

    four_common = [
        choose(
            "english_or_word_power", "English course or Word Power", english_options, 1
        ),
        language_rule(),
        {
            "type": "same_department_credit_pool",
            "id": "second_year_nonlaw_discipline",
            "label": "Two 2000-level semester courses in one non-law discipline",
            "course_codes": second_year_nonlaw,
            "required": 40,
            "filters": {
                "nqf_levels": [6],
                "exclude_prefixes": ["CML", "PVL", "PBL", "DOL"],
            },
            "transcript_filters": {
                "nqf_levels": [6],
                "year_levels": [2],
                "exclude_prefixes": ["CML", "PVL", "PBL", "DOL"],
            },
            "allow_unlisted_transcript_courses": True,
        },
        *common_final,
    ]
    pathways = {
        "numeracy_course_required": {
            "name": "Numeracy test below 66% - MAM1013F required",
            "required_courses": ["MAM1013F"],
            "curriculum_rules": [
                other_faculty_rule(
                    first_year_nonlaw,
                    30,
                    "first_year_other_faculty_30",
                    "First-year courses in another faculty",
                )
            ],
            "verification_status": "verified",
            "availability": "open",
            "source": {"document": SOURCE, "page": 43, "rule": "FP5.2-FP5.3"},
        },
        "numeracy_test_passed": {
            "name": "Numeracy test at least 66% - additional non-law semester course",
            "required_courses": [],
            "curriculum_rules": [
                other_faculty_rule(
                    first_year_nonlaw,
                    45,
                    "first_year_other_faculty_45",
                    "First-year courses in another faculty",
                )
            ],
            "verification_status": "verified",
            "availability": "open",
            "source": {"document": SOURCE, "page": 43, "rule": "FP5.2 and FP5.3.1"},
        },
    }

    # Five-year replacements use all_of/any_of instead of pretending the old courses are still offered.
    five_replacement_rules = [
        any_of(
            "five_foundations",
            "Foundations of South African Law",
            [course_rule("PVL1006W"), course_rule("PVL1003W")],
        ),
        any_of(
            "five_persons",
            "Law of Persons and Family",
            [course_rule("PVL1009S"), course_rule("PVL1008H")],
        ),
        any_of(
            "five_private_system",
            "South African Private Law: System and Context",
            [course_rule("PVL1007F"), course_rule("PVL1004F")],
        ),
        any_of(
            "five_constitutional",
            "Constitutional Law",
            [course_rule("PBL2002W"), course_rule("PBL2000W")],
        ),
    ]
    five_required = [
        code
        for code in law_core
        if code not in {"PVL1003W", "PVL1004F", "PVL1008H", "PBL2000W"}
    ] + ["SLL1002S", "MAM1013F"]

    programmes = {
        "llb_three_year_graduate": programme(
            "LLB - Three-year graduate stream",
            "LP001",
            504,
            3,
            law_core,
            41,
            rules=common_final,
            max_years=4,
            prereq_overrides=grad_pr,
            coreq_overrides=grad_co,
            admission_notes=[
                "Admission requires an appropriate completed bachelor's degree and Faculty admission under the Undergraduate Prospectus."
            ],
        ),
        "llb_two_year_combined": programme(
            "LLB - Two-year graduate stream after Law and Humanities/Commerce",
            "LP001",
            504,
            2,
            law_core,
            50,
            rules=common_final,
            max_years=3,
            prereq_overrides=ug_pr,
            coreq_overrides=ug_co,
            admission_notes=[
                "The six Preliminary Level law courses must already have been completed in the prior BA, BSocSc, BCom or BBusSc route.",
                "Admission to the graduate part is not automatic and remains subject to the Undergraduate Prospectus and Faculty decision.",
            ],
        ),
        "llb_four_year_undergraduate": programme(
            "LLB - Four-year undergraduate stream",
            "LB002",
            637,
            4,
            law_core,
            43,
            rules=four_common,
            max_years=5,
            pathways=pathways,
            pathway_required=True,
            prereq_overrides=ug_pr,
            coreq_overrides=ug_co,
            admission_notes=[
                "Select the numeracy pathway using the official test outcome; the test may not be attempted a second time."
            ],
        ),
        "llb_five_year_continuing": programme(
            "LLB - Five-year undergraduate curriculum (continuing students)",
            "LB003",
            637,
            5,
            five_required,
            52,
            rules=[
                *five_replacement_rules,
                other_faculty_rule(
                    first_year_nonlaw,
                    30,
                    "five_first_year_nonlaw",
                    "First/second-year non-law option credits",
                ),
                language_rule(),
                {
                    "type": "same_department_credit_pool",
                    "id": "five_second_year_nonlaw_discipline",
                    "label": "Two 2000-level semester courses in one non-law discipline",
                    "course_codes": second_year_nonlaw,
                    "required": 40,
                    "filters": {
                        "nqf_levels": [6],
                        "exclude_prefixes": ["CML", "PVL", "PBL", "DOL"],
                    },
                    "transcript_filters": {
                        "nqf_levels": [6],
                        "year_levels": [2],
                        "exclude_prefixes": ["CML", "PVL", "PBL", "DOL"],
                    },
                    "allow_unlisted_transcript_courses": True,
                },
                *common_final,
            ],
            availability="continuing_only",
            availability_note="For continuing students who first registered for LB003 in or before 2019; no new intake.",
            max_years=6,
            prereq_overrides=ug_pr,
            coreq_overrides=ug_co,
            admission_notes=[
                "Legacy courses no longer offered are recognised through their published replacement-course alternatives."
            ],
            failed_threshold=3,
        ),
    }

    requirements = {
        "source": f"{SOURCE}; {GENERAL}",
        "catalogue_version": "2026.1-law",
        "programmes": programmes,
        "majors": {},
        "forbidden_major_combinations": [],
        "cross_credit_exclusions": [],
    }
    (OUT / "courses.json").write_text(
        json.dumps(sorted(courses.values(), key=lambda row: row["code"]), indent=2)
        + "\n"
    )
    (OUT / "degree_requirements.json").write_text(
        json.dumps(requirements, indent=2) + "\n"
    )
    print(
        f"Wrote {len(courses)} Law-scoped course facts and {len(programmes)} LLB routes."
    )


if __name__ == "__main__":
    main()
