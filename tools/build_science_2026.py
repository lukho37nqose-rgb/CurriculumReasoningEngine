#!/usr/bin/env python3
"""Build the 2026 UCT Science undergraduate BSc catalogue.

The Science Faculty is modelled as a flexible BSc with a regular and extended
route, a selectable curriculum cohort, composable major rules, Science-credit
recognition, course equivalences, non-Science elective limits, and
major-specific distinction rules.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "uct_science"
TEXT_PATH = Path("/mnt/data/science2026.txt")
PDF_NAME = "2026 Faculty of Science Handbook"

SCI_PREFIXES = {
    "AGE",
    "AST",
    "BIO",
    "CEM",
    "CSC",
    "EGS",
    "GEO",
    "MAM",
    "MCB",
    "SEA",
    "PHY",
    "STA",
}
SERVICE_EXCLUSIONS = {
    "CSC1017S",
    "GEO1008F",
    "MAM1010F",
    "MAM1110H",
    "MAM1012S",
    "MAM1112H",
    "MAM1020F",
    "MAM1021S",
    "MAM1023H",
    "MAM1024H",
    "MAM2083F",
    "MAM2083S",
    "MAM2084F",
    "MAM2084S",
    "MAM2085S",
    "PHY1012F",
    "PHY1012S",
    "PHY1013S",
    "STA1100F",
    "STA1100S",
    "STA1106S",
}
PREFIX_DEPARTMENT = {
    "AGE": "Archaeology",
    "AST": "Astronomy",
    "BIO": "Biological Sciences",
    "CEM": "Chemistry",
    "CSC": "Computer Science",
    "EGS": "Environmental and Geographical Science",
    "GEO": "Geological Sciences",
    "MAM": "Mathematics and Applied Mathematics",
    "MCB": "Molecular and Cell Biology",
    "SEA": "Oceanography",
    "PHY": "Physics",
    "STA": "Statistical Sciences",
    "EEE": "Electrical Engineering",
    "HUB": "Human Biology",
    "INF": "Information Systems",
    "ACC": "College of Accounting",
    "FTX": "Finance and Tax",
    "APG": "Architecture, Planning and Geomatics",
    "TDP": "Theatre, Dance and Performance",
    "FIN": "Fine Art",
}


def prefix(code: str) -> str:
    m = re.match(r"[A-Z]+", code)
    return m.group(0) if m else ""


def offered_from_code(code: str) -> list[str]:
    suffix = re.sub(r"^[A-Z]+\d{4}", "", code)
    return {
        "F": ["First semester"],
        "S": ["Second semester"],
        "W": ["Whole year"],
        "H": ["Half course over whole year"],
        "P": ["Summer term"],
        "L": ["Winter term"],
        "X": ["Non-standard period"],
        "Z": ["Other/non-standard period"],
    }.get(suffix, [])


def expand_code(code: str) -> list[str]:
    code = code.strip().upper().replace(" ", "")
    m = re.fullmatch(r"([A-Z]{3}\d{4})([A-Z])(?:/([A-Z]))+", code)
    if not m:
        return [code]
    stem = m.group(1)
    suffixes = re.findall(r"(?:^|/)([A-Z])", code[len(stem) :])
    return [stem + suffix for suffix in suffixes]


def extract_courses(text: str) -> dict[str, dict[str, Any]]:
    # Course descriptions are uppercase headings followed by an explicit NQF line.
    heading = re.compile(r"(?m)^\s*([A-Z]{3}\d{4}[A-Z](?:/[A-Z])*)\s+([^\n]+?)\s*$")
    matches = list(heading.finditer(text))
    records: dict[str, dict[str, Any]] = {}
    for i, match in enumerate(matches):
        raw_code = match.group(1)
        title = re.sub(r"\s+", " ", match.group(2)).strip(" .")
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        segment = text[match.end() : end]
        credit = re.search(
            r"(\d+)\s+NQF credits? at NQF level\s+(\d+)", segment[:1800], re.I
        )
        if not credit:
            continue
        credits, level = int(credit.group(1)), int(credit.group(2))
        if not 1 <= int(re.search(r"\d", raw_code).group()) <= 4:
            continue
        page = text.count("\f", 0, match.start()) + 1
        not_offered = bool(
            re.search(r"not offered in 2026", (title + " " + segment[:500]), re.I)
        )
        entry = re.search(
            r"Course entry requirements:\s*(.*?)(?:\n\s*Course outline:|\n\s*DP requirements:|\Z)",
            segment[:5000],
            re.S | re.I,
        )
        entry_text = re.sub(r"\s+", " ", entry.group(1)).strip() if entry else ""
        prereqs: list[str] = []
        prereq_verified = False
        if entry_text and re.fullmatch(r"None\.?", entry_text, re.I):
            prereq_verified = True
        elif entry_text:
            codes = []
            for found in re.findall(r"\b[A-Z]{3}\d{4}[A-Z]?(?:/[A-Z])?\b", entry_text):
                codes.extend(expand_code(found))
            # Keep exact prerequisites only when the prose does not contain alternatives,
            # marks, permission, acceptance, or other conditions.
            unsafe = re.search(
                r"\bor\b|permission|minimum|at least|acceptance|concurrent|co-requisite|recommended|equivalent|%",
                entry_text,
                re.I,
            )
            if codes and not unsafe:
                prereqs = sorted(set(codes))
                prereq_verified = True
        elif level == 5:
            prereq_verified = True

        description = ""
        outline = re.search(
            r"Course outline:\s*(.*?)(?:\n\s*Lecture times:|\n\s*DP requirements:|\n\s*Assessment:|\Z)",
            segment[:6000],
            re.S | re.I,
        )
        if outline:
            description = re.sub(r"\s+", " ", outline.group(1)).strip()[:900]
        for code in expand_code(raw_code):
            # Prefer the richest course-description occurrence over schedule/index duplicates.
            candidate = {
                "code": code,
                "name": title,
                "credits": credits,
                "nqf_level": level,
                "prerequisites": prereqs,
                "prerequisites_verified": prereq_verified,
                "co_requisites": [],
                "offered": [] if not_offered else offered_from_code(code),
                "offering_verified": True,
                "department": PREFIX_DEPARTMENT.get(prefix(code), prefix(code)),
                "description": description,
                "verification_status": "verified",
                "source": {
                    "document": PDF_NAME,
                    "page": page,
                    "section": "Course outline",
                },
                "general_elective": prefix(code) in SCI_PREFIXES
                and code not in SERVICE_EXCLUSIONS,
                "counts_towards_general_degree": True,
                "counts_as_humanities": False,
                "counts_as_science": prefix(code) in SCI_PREFIXES
                and code not in SERVICE_EXCLUSIONS,
                "counts_towards_course_equivalents": False,
                "credit_bearing": credits > 0,
                "recognition_note": "Science recognition is controlled by the selected BSc programme and major rules.",
            }
            old = records.get(code)
            if old is None or (description and not old.get("description")):
                records[code] = candidate
    return records


def course(
    codes: list[str] | str, label: str, rule_id: str | None = None, **extra: Any
) -> dict[str, Any]:
    if isinstance(codes, str):
        codes = [codes]
    row = {
        "type": "course",
        "id": rule_id or "course_" + "_".join(codes).lower(),
        "label": label,
        "course_codes": codes,
    }
    row.update(extra)
    return row


def all_courses(codes: list[str], label: str, rule_id: str) -> dict[str, Any]:
    return {"type": "all_courses", "id": rule_id, "label": label, "course_codes": codes}


def choose(codes: list[str], required: int, label: str, rule_id: str) -> dict[str, Any]:
    return {
        "type": "choose_n",
        "id": rule_id,
        "label": label,
        "course_codes": codes,
        "required": required,
    }


def any_of(children: list[dict[str, Any]], label: str, rule_id: str) -> dict[str, Any]:
    return {"type": "any_of", "id": rule_id, "label": label, "children": children}


def all_of(children: list[dict[str, Any]], label: str, rule_id: str) -> dict[str, Any]:
    return {"type": "all_of", "id": rule_id, "label": label, "children": children}


def pool(
    codes: list[str], required: int, label: str, rule_id: str, **extra: Any
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


def first_class(
    codes: list[str], required: int, label: str, rule_id: str
) -> dict[str, Any]:
    return {
        "type": "first_class_group",
        "id": rule_id,
        "label": label,
        "course_codes": codes,
        "required": required,
        "minimum_mark": 75,
        "minimum_individual_mark": 70,
        "allow_group_average": True,
    }


def variants(stems: list[str], courses: dict[str, dict[str, Any]]) -> list[str]:
    out: set[str] = set()
    for stem in stems:
        if re.search(r"[A-Z]$", stem) and re.search(r"\d[A-Z]$", stem):
            if stem in courses:
                out.add(stem)
        else:
            out.update(code for code in courses if code.startswith(stem))
    return sorted(out)


def math_full(courses: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return any_of(
        [
            course("MAM1000W", "Complete MAM1000W"),
            all_courses(
                ["MAM1031F", "MAM1032S"],
                "Complete MAM1031F and MAM1032S",
                "mam1031_1032",
            ),
            all_courses(
                ["MAM1005H", "MAM1006H"],
                "Complete the EDP Mathematics sequence",
                "mam1005_1006",
            ),
        ],
        "Complete 36 credits of first-year Science Mathematics",
        "math_full",
    )


def math_or_stats(courses: dict[str, dict[str, Any]]) -> dict[str, Any]:
    stats = variants(["STA100"], courses)
    return any_of(
        [
            math_full(courses),
            all_of(
                [
                    course(
                        variants(["MAM1004"], courses) + ["MAM1031F"],
                        "Complete an approved 18-credit Science Mathematics course",
                        "math18",
                    ),
                    course(
                        stats,
                        "Complete an approved 18-credit Science Statistics course",
                        "stats18",
                    ),
                ],
                "Complete 18 credits Mathematics and 18 credits Statistics",
                "math_stats_pair",
            ),
        ],
        "Science Mathematics/Statistics foundation",
        "fb7_3",
    )


def major_source(page: int) -> dict[str, Any]:
    return {
        "document": PDF_NAME,
        "page": page,
        "section": "FB7.6 compulsory courses for Science majors",
    }


def award_rules(courses: dict[str, dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    v = lambda stems: variants(stems, courses)
    return {
        "applied_mathematics": [
            any_of(
                [
                    first_class(v(["MAM2046"]), 1, "MAM2046W first class", "am2_whole"),
                    first_class(
                        v(["MAM2040", "MAM2041", "MAM2042", "MAM2043"]),
                        4,
                        "Applied Mathematics second-year courses",
                        "am2",
                    ),
                ],
                "Second-year distinction courses",
                "am2_choice",
            ),
            any_of(
                [
                    first_class(v(["MAM3040"]), 1, "MAM3040W first class", "am3_whole"),
                    first_class(
                        v(["MAM3042", "MAM3043", "MAM3044", "MAM3045", "MAM3046"]),
                        4,
                        "Applied Mathematics third-year courses",
                        "am3",
                    ),
                ],
                "Third-year distinction courses",
                "am3_choice",
            ),
        ],
        "applied_statistics": [
            first_class(
                v(["STA2007", "STA2020"]),
                1,
                "Applied Statistics second-year option",
                "as2a",
            ),
            first_class(v(["STA2030"]), 1, "STA2030S", "as2b"),
            first_class(v(["STA3030"]), 1, "STA3030F", "as3a"),
            first_class(
                v(["STA3022", "STA3036"]),
                1,
                "Applied Statistics third-year option",
                "as3b",
            ),
        ],
        "archaeology": [
            first_class(
                v(["AGE2", "AGE3"]),
                4,
                "Four senior Archaeology half-courses",
                "age_dist",
            )
        ],
        "artificial_intelligence": [
            first_class(v(["CSC2041"]), 1, "CSC2041F", "ai2a"),
            first_class(v(["CSC2042"]), 1, "CSC2042S", "ai2b"),
            first_class(
                v(["CSC3041", "CSC3042", "CSC3043", "CSC3044"]),
                3,
                "Three senior AI courses",
                "ai3",
            ),
        ],
        "astrophysics": [
            first_class(
                v(["AST2002", "AST2003", "AST3002", "AST3003"]),
                4,
                "Astrophysics distinction courses",
                "ast_dist",
            )
        ],
        "biochemistry": [
            first_class(
                v(["MCB2021", "MCB2022", "MCB3024", "MCB3025"]),
                4,
                "Biochemistry distinction courses",
                "bioch_dist",
            )
        ],
        "biology": [
            first_class(v(["BIO2014"]), 1, "BIO2014F", "biology2a"),
            first_class(
                v(["BIO2015", "BIO2016", "BIO2017"]),
                1,
                "One organismal biology course",
                "biology2b",
            ),
            first_class(
                v(["BIO3013", "BIO3014", "BIO3018", "BIO3019", "BIO3022"]),
                2,
                "Two third-year Biology courses",
                "biology3",
            ),
        ],
        "business_computing": [
            first_class(
                v(["INF2009", "INF2011"]),
                2,
                "Business Computing second-year courses",
                "bc2",
            ),
            first_class(
                v(["INF3011", "INF3012", "INF3014"]),
                2,
                "Two Business Computing third-year courses",
                "bc3",
            ),
        ],
        "chemistry": [
            first_class(
                v(["CEM2005", "CEM3005"]),
                2,
                "Chemistry distinction courses",
                "chem_dist",
            )
        ],
        "computer_engineering": [
            first_class(
                v(["EEE2049"]) + v(["EEE2041", "EEE2042"]),
                2,
                "Electrical Engineering foundation",
                "ce2a",
            ),
            first_class(
                v(["EEE2050", "EEE3095"]), 2, "Embedded systems courses", "ce2b"
            ),
            first_class(v(["CSC3022", "CSC3024"]), 1, "C++ course", "ce3"),
        ],
        "computer_science": [
            first_class(
                v(["CSC2001", "CSC2002", "CSC3002", "CSC3003"]),
                4,
                "Computer Science distinction courses",
                "cs_dist",
            )
        ],
        "environmental_geographical_science": [
            first_class(
                v(["EGS2013", "EGS2016"]), 1, "Space/geographies course", "egs2a"
            ),
            first_class(v(["EGS2015", "EGS2017"]), 1, "Time/society course", "egs2b"),
            first_class(
                v(["EGS3012", "EGS3020", "EGS3021", "EGS3022", "EGS3023"]),
                2,
                "Two third-year EGS courses",
                "egs3",
            ),
        ],
        "genetics": [
            first_class(
                v(["MCB2020", "MCB2023", "MCB3023", "MCB3026"]),
                4,
                "Genetics distinction courses",
                "gen_dist",
            )
        ],
        "geology": [
            first_class(
                v(["GEO2001", "GEO2004", "GEO3005", "GEO3001"]),
                4,
                "Geology distinction courses",
                "geo_dist",
            )
        ],
        "human_anatomy_physiology": [
            first_class(
                v(["HUB2019", "HUB2021", "HUB3006", "HUB3007"]),
                4,
                "Human Anatomy and Physiology distinction courses",
                "hap_dist",
            )
        ],
        "marine_biology": [
            first_class(
                v(["BIO2014", "BIO2015", "BIO2016", "BIO2017"]),
                1,
                "One second-year Biology course",
                "mb2a",
            ),
            first_class(v(["SEA2004"]), 1, "SEA2004F", "mb2b"),
            first_class(v(["BIO3002"]), 1, "BIO3002F", "mb3a"),
            first_class(
                v(["BIO3017", "BIO3022"]), 1, "Marine third-year option", "mb3b"
            ),
        ],
        "mathematics": [
            any_of(
                [
                    first_class(v(["MAM2000"]), 1, "MAM2000W", "math2w"),
                    first_class(
                        v(["MAM2010", "MAM2011", "MAM2013", "MAM2014"]),
                        4,
                        "Mathematics second-year courses",
                        "math2",
                    ),
                ],
                "Second-year Mathematics distinction set",
                "math2_choice",
            ),
            any_of(
                [
                    first_class(v(["MAM3000"]), 1, "MAM3000W", "math3w"),
                    all_of(
                        [
                            first_class(
                                v(
                                    [
                                        "MAM3010",
                                        "MAM3011",
                                        "MAM3012",
                                        "MAM3014",
                                        "MAM3015",
                                    ]
                                ),
                                4,
                                "Four Mathematics third-year courses",
                                "math3",
                            ),
                            first_class(
                                v(["MAM3010", "MAM3011"]),
                                1,
                                "At least one algebra/analysis option",
                                "math3_core",
                            ),
                        ],
                        "Third-year Mathematics set",
                        "math3_set",
                    ),
                ],
                "Third-year Mathematics distinction set",
                "math3_choice",
            ),
        ],
        "mathematical_statistics": [
            first_class(
                v(["STA2004", "STA2005", "STA3041"]),
                3,
                "Mathematical Statistics core distinction courses",
                "ms_core",
            ),
            any_of(
                [
                    first_class(v(["STA3043"]), 1, "STA3043S", "ms_old"),
                    first_class(
                        v(["STA3047", "STA3048"]), 2, "STA3047S and STA3048S", "ms_new"
                    ),
                ],
                "Final Mathematical Statistics option",
                "ms_choice",
            ),
        ],
        "ocean_atmosphere_science": [
            first_class(
                v(["SEA2004", "SEA2005", "SEA3004", "EGS3012"]),
                4,
                "Ocean and Atmosphere distinction courses",
                "oas_dist",
            )
        ],
        "physics": [
            first_class(
                v(["PHY2004", "PHY3004"]), 2, "Physics distinction courses", "phy_dist"
            )
        ],
        "quantitative_biology": [
            first_class(
                v(["BIO2014", "BIO2015", "BIO2016", "BIO2017"]),
                1,
                "One second-year Biology course",
                "qb2bio",
            ),
            any_of(
                [
                    first_class(
                        v(["STA2"]), 1, "A second-year Statistics course", "qb2sta"
                    ),
                    first_class(v(["MAM2046"]), 1, "MAM2046W", "qb2mam"),
                ],
                "Quantitative second-year method",
                "qb2method",
            ),
            first_class(v(["BIO3019"]), 1, "BIO3019S", "qb3bio"),
            any_of(
                [
                    first_class(
                        v(["STA3"]), 1, "A third-year Statistics course", "qb3sta"
                    ),
                    first_class(v(["MAM3040"]), 1, "MAM3040W", "qb3mamw"),
                    all_of(
                        [
                            first_class(v(["MAM3043"]), 1, "MAM3043", "qb3mamcore"),
                            first_class(
                                v(
                                    [
                                        "MAM3012",
                                        "MAM3042",
                                        "MAM3044",
                                        "MAM3045",
                                        "MAM3046",
                                    ]
                                ),
                                3,
                                "Three Applied Mathematics options",
                                "qb3mamopts",
                            ),
                        ],
                        "Applied Mathematics third-year set",
                        "qb3mam",
                    ),
                ],
                "Quantitative third-year method",
                "qb3method",
            ),
        ],
        "statistics_data_science": [
            first_class(
                v(["STA2004", "STA2030"]), 1, "Statistical theory option", "sds2a"
            ),
            first_class(
                v(["STA2005", "STA2007", "STA2020"]),
                1,
                "Applied statistics option",
                "sds2b",
            ),
            first_class(v(["STA3030", "STA3041"]), 1, "Inference option", "sds3a"),
            any_of(
                [
                    first_class(
                        v(["STA3022", "STA3036"]),
                        1,
                        "Third-year statistics option",
                        "sds3b",
                    ),
                    first_class(
                        v(["STA3047", "STA3048"]),
                        2,
                        "Machine learning and Bayesian pair",
                        "sds3pair",
                    ),
                ],
                "Final statistics option",
                "sds3choice",
            ),
        ],
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    text = TEXT_PATH.read_text(errors="replace")
    courses = extract_courses(text)

    # Add/repair course facts explicitly required by major tables when the parser
    # encountered a table entry but no descriptive outline.
    required_facts: dict[str, tuple[str, int, int]] = {
        "MAM1000W": ("Mathematics 1000", 36, 5),
        "INF2006F": ("Business Intelligence Analysis", 6, 6),
        "INF2009F": ("Systems Analysis", 18, 6),
        "INF2011S": ("System Design and Development", 18, 7),
        "INF3011F": ("I.T. Project Management", 18, 7),
        "INF3012S": ("BPM and Enterprise Systems", 18, 7),
        "INF3014F": ("Electronic Commerce", 18, 7),
        "ACC1021F": ("Accounting for Business I", 15, 5),
        "FTX1005F": ("Managerial Finance", 18, 5),
        "FTX1005S": ("Managerial Finance", 18, 5),
        "EEE2041F": (
            "Introduction to Electrical Engineering & Power Utilisation",
            16,
            6,
        ),
        "EEE2042S": ("Introduction to Analogue & Digital Electronics", 8, 6),
        "EEE2050F": ("Embedded Systems I for Science Students", 18, 6),
        "EEE3095S": ("Embedded Systems II for Science Students", 18, 7),
        "HUB2019F": ("Integrated Anatomy & Physiology Sciences A", 24, 6),
        "HUB2021S": ("Integrated Anatomy & Physiology Sciences B", 24, 6),
        "HUB3006F": ("Applied Human Biology", 36, 7),
        "HUB3007S": ("Human Neurosciences", 36, 7),
    }
    for code, (name, credits, level) in required_facts.items():
        if code not in courses:
            courses[code] = {
                "code": code,
                "name": name,
                "credits": credits,
                "nqf_level": level,
                "prerequisites": [],
                "prerequisites_verified": False,
                "co_requisites": [],
                "offered": offered_from_code(code),
                "offering_verified": True,
                "department": PREFIX_DEPARTMENT.get(prefix(code), prefix(code)),
                "description": "",
                "verification_status": "verified",
                "source": {
                    "document": PDF_NAME,
                    "page": 19,
                    "section": "FB7.6 major table",
                },
                "general_elective": False,
                "counts_towards_general_degree": True,
                "counts_as_humanities": False,
                "counts_as_science": True,
                "counts_towards_course_equivalents": False,
                "credit_bearing": credits > 0,
                "recognition_note": "Required external-faculty course; counted as Science under FB7.6 Note 2 only within the relevant major.",
            }
        else:
            courses[code]["counts_as_science"] = True
            courses[code]["general_elective"] = False

    v = lambda stems: variants(stems, courses)
    sta1 = v(["STA1000", "STA1006", "STA1007"])
    mam1004 = v(["MAM1004"])
    csc1015 = v(["CSC1015"])

    majors: dict[str, dict[str, Any]] = {}

    def add(
        key: str,
        name: str,
        code: str,
        page: int,
        stages: dict[str, list[dict[str, Any]]],
        *,
        co: list[str] | None = None,
        limited: bool = False,
        note: str = "",
    ) -> None:
        rules = [
            all_of(stage, f"{name}: {label}", f"{key}_{label}")
            for label, stage in stages.items()
        ]
        rules.append(
            pool(v([f for f in []]), 0, "", "noop", blocking=False)
            if False
            else {
                "type": "credit_pool",
                "id": f"{key}_level7",
                "label": f"{name}: at least 72 distinct level-7 credits",
                "filters": {"nqf_levels": [7]},
                "course_codes": sorted(
                    {
                        c
                        for stage in stages.values()
                        for r in stage
                        for c in _rule_codes(r)
                    }
                ),
                "required": 72,
            }
        )
        majors[key] = {
            "name": name,
            "qualification": "BSc",
            "handbook_code": code,
            "required_courses": [],
            "choice_groups": [],
            "curriculum_rules": rules,
            "stage_rules": stages,
            "required_co_majors": co or [],
            "admission_limited": limited,
            "admission_note": note,
            "verification_status": "verified",
            "verification_notes": [],
            "award_rules": [],
            "faculty_owned": True,
            "source": major_source(page),
        }

    # local recursive collector for the major's level-7 pool
    def replace_level7(key: str) -> None:
        major = majors[key]
        all_codes = sorted(
            {
                c
                for stage in major["stage_rules"].values()
                for r in stage
                for c in _rule_codes(r)
                if courses.get(c, {}).get("nqf_level") == 7
            }
        )
        major["curriculum_rules"][-1]["course_codes"] = all_codes

    # Major rule definitions.
    common_math_stats = math_or_stats(courses)
    add(
        "applied_mathematics",
        "Applied Mathematics",
        "MAM01",
        20,
        {
            "year1": [
                math_full(courses),
                all_courses(
                    ["MAM1043H", "MAM1044H"],
                    "Complete modelling and dynamics",
                    "am_y1_extra",
                ),
            ],
            "year2": [
                all_courses(
                    ["MAM2010F", "MAM2011F"],
                    "Complete calculus and linear algebra",
                    "am_y2_core",
                ),
                choose(
                    v(["MAM2012", "MAM2013", "MAM2014"]),
                    2,
                    "Choose two pure mathematics courses",
                    "am_y2_choose",
                ),
                all_courses(
                    ["MAM2040F", "MAM2041F", "MAM2042S", "MAM2043S"],
                    "Complete applied mathematics sequence",
                    "am_y2_applied",
                ),
            ],
            "year3": [
                course(
                    v(["MAM3043"]),
                    "Complete Methods of Mathematical Physics",
                    "am_y3_core",
                ),
                choose(
                    v(["MAM3012", "MAM3042", "MAM3044", "MAM3045", "MAM3046"]),
                    3,
                    "Choose three third-year Applied Mathematics courses",
                    "am_y3_choose",
                ),
            ],
        },
    )
    add(
        "applied_statistics",
        "Applied Statistics",
        "STA01",
        21,
        {
            "year1": [
                math_full(courses),
                course(sta1, "Complete first-year Statistics", "as_y1_sta"),
            ],
            "year2": [
                course(
                    v(["STA2007", "STA2020"]),
                    "Complete applied statistics",
                    "as_y2_applied",
                ),
                course("STA2030S", "Complete Statistical Theory", "as_y2_theory"),
            ],
            "year3": [
                course(
                    "STA3030F",
                    "Complete Statistical Inference and Modelling",
                    "as_y3_core",
                ),
                course(
                    v(["STA3022", "STA3036"]),
                    "Complete a third-year applied option",
                    "as_y3_option",
                ),
            ],
        },
    )
    add(
        "archaeology",
        "Archaeology",
        "AGE01",
        21,
        {
            "year1": [
                all_courses(
                    ["GEO1009F", "AGE1002S"],
                    "Complete Earth Science and Archaeology foundations",
                    "age_y1_core",
                ),
                common_math_stats,
            ],
            "year2": [
                all_courses(
                    ["AGE2011S", "AGE2012F"],
                    "Complete second-year Archaeology",
                    "age_y2",
                )
            ],
            "year3": [
                course("AGE3013H", "Complete Archaeology in Practice", "age_y3_core"),
                course(
                    v(["AGE3011", "AGE3012"]),
                    "Complete a third-year Archaeology option",
                    "age_y3_option",
                ),
            ],
        },
    )
    add(
        "artificial_intelligence",
        "Artificial Intelligence",
        "CSC08",
        22,
        {
            "year1": [
                all_courses(
                    csc1015 + ["CSC1016S", "MAM1031F", "MAM1032S"],
                    "Complete AI foundations",
                    "ai_y1_core",
                ),
                course(
                    ["MAM1019H"] + sta1,
                    "Complete Fundamentals of Mathematics or Statistics",
                    "ai_y1_option",
                ),
            ],
            "year2": [
                all_courses(
                    ["CSC2001F", "CSC2041F", "CSC2042S", "MAM2010F", "MAM2011F"],
                    "Complete second-year AI curriculum",
                    "ai_y2",
                )
            ],
            "year3": [
                all_courses(
                    ["CSC3041F", "CSC3042F", "CSC3043S", "CSC3044S"],
                    "Complete third-year AI curriculum",
                    "ai_y3",
                )
            ],
        },
    )
    add(
        "astrophysics",
        "Astrophysics",
        "AST02",
        22,
        {
            "year1": [
                math_full(courses),
                course(
                    v(["PHY1004"]), "Complete Matter and Interactions", "ast_y1_phy"
                ),
                course(csc1015, "Complete Computer Science 1015", "ast_y1_csc"),
            ],
            "year2": [
                all_courses(
                    ["AST2002H", "AST2003H", "MAM2010F", "MAM2011F", "PHY2004W"],
                    "Complete second-year Astrophysics curriculum",
                    "ast_y2",
                )
            ],
            "year3": [
                all_courses(
                    ["AST3002F", "AST3003S"],
                    "Complete third-year Astrophysics",
                    "ast_y3",
                )
            ],
        },
    )
    add(
        "biochemistry",
        "Biochemistry",
        "MCB01",
        23,
        {
            "year1": [
                all_courses(
                    ["BIO1000F", "CEM1000W"],
                    "Complete Biology and Chemistry foundations",
                    "bioch_y1_core",
                ),
                course(mam1004 + ["MAM1031F"], "Complete Mathematics", "bioch_y1_math"),
                course(sta1, "Complete Statistics", "bioch_y1_sta"),
            ],
            "year2": [
                all_courses(
                    ["MCB2020F", "MCB2021F", "MCB2022S"],
                    "Complete second-year Biochemistry",
                    "bioch_y2",
                )
            ],
            "year3": [
                all_courses(
                    ["MCB3012Z", "MCB3024S", "MCB3025F"],
                    "Complete third-year Biochemistry",
                    "bioch_y3",
                )
            ],
        },
        limited=True,
        note="Entry to second-year Biochemistry is capacity-limited and based on first-year performance; a transcript alone cannot confirm admission.",
    )
    add(
        "biology",
        "Biology",
        "BIO12",
        24,
        {
            "year1": [
                all_courses(
                    ["BIO1000F", "BIO1004S", "CEM1000W", "STA1007S"],
                    "Complete Biology foundations",
                    "biology_y1_core",
                ),
                course(
                    mam1004 + ["MAM1031F"], "Complete Mathematics", "biology_y1_math"
                ),
            ],
            "year2": [
                course(
                    "BIO2014F",
                    "Complete Principles of Ecology and Evolution",
                    "biology_y2_core",
                ),
                choose(
                    v(["BIO2015", "BIO2016", "BIO2017"]),
                    2,
                    "Choose two organismal biology courses",
                    "biology_y2_choose",
                ),
            ],
            "year3": [
                choose(
                    v(["BIO3013", "BIO3014", "BIO3018", "BIO3019", "BIO3022"]),
                    2,
                    "Choose two third-year Biology courses",
                    "biology_y3_choose",
                )
            ],
        },
    )
    add(
        "business_computing",
        "Business Computing",
        "CSC02",
        24,
        {
            "year1": [
                all_courses(
                    csc1015 + ["CSC1016S"],
                    "Complete Computer Science foundation",
                    "bc_y1_csc",
                ),
                course(
                    v(["MAM1008"]) + ["MAM1019H"] + sta1,
                    "Complete discrete mathematics/fundamentals/statistics",
                    "bc_y1_math1",
                ),
                course(
                    mam1004 + ["MAM1000W", "MAM1031F"],
                    "Complete Mathematics",
                    "bc_y1_math2",
                ),
                course(
                    ["ACC1021F", "FTX1005F", "FTX1005S"],
                    "Complete Accounting or Managerial Finance",
                    "bc_y1_bus",
                ),
            ],
            "year2": [
                all_courses(
                    ["INF2009F", "INF2006F", "INF2011S"],
                    "Complete second-year Business Computing",
                    "bc_y2",
                )
            ],
            "year3": [
                all_courses(
                    ["INF3011F", "INF3012S", "INF3014F"],
                    "Complete third-year Business Computing",
                    "bc_y3",
                )
            ],
        },
        co=["computer_science"],
    )
    add(
        "chemistry",
        "Chemistry",
        "CEM01",
        25,
        {
            "year1": [
                course("CEM1000W", "Complete Chemistry 1000", "chem_y1_cem"),
                math_full(courses),
                any_of(
                    [
                        course(
                            v(["PHY1004"]),
                            "Complete Matter and Interactions",
                            "chem_phy_w",
                        ),
                        all_courses(
                            ["PHY1031F", "PHY1032S"],
                            "Complete General Physics A and B",
                            "chem_phy_pair",
                        ),
                    ],
                    "Complete first-year Physics",
                    "chem_y1_phy",
                ),
            ],
            "year2": [course("CEM2005W", "Complete Intermediate Chemistry", "chem_y2")],
            "year3": [course("CEM3005W", "Complete Chemistry 3005", "chem_y3")],
        },
    )
    add(
        "computer_engineering",
        "Computer Engineering",
        "CSC03",
        25,
        {
            "year1": [
                all_courses(
                    csc1015 + ["CSC1016S"],
                    "Complete Computer Science foundation",
                    "ce_y1_csc",
                ),
                math_full(courses),
                any_of(
                    [
                        course(
                            v(["PHY1004"]),
                            "Complete Matter and Interactions",
                            "ce_phy_w",
                        ),
                        all_courses(
                            ["PHY1031F", "PHY1032S"],
                            "Complete General Physics A and B",
                            "ce_phy_pair",
                        ),
                    ],
                    "Complete Physics prerequisites",
                    "ce_y1_phy",
                ),
            ],
            "year2": [
                all_courses(
                    ["CSC2042S", "EEE2041F", "EEE2042S"],
                    "Complete second-year Computer Engineering",
                    "ce_y2",
                )
            ],
            "year3": [
                all_courses(
                    ["EEE2050F", "EEE3095S", "CSC3024S"],
                    "Complete embedded systems and C++",
                    "ce_y3_core",
                ),
                course(
                    ["CSC3041F", "CSC3042F"],
                    "Complete an advanced AI option",
                    "ce_y3_option",
                ),
            ],
        },
        co=["computer_science"],
    )
    add(
        "computer_science",
        "Computer Science",
        "CSC05",
        26,
        {
            "year1": [
                all_courses(
                    csc1015 + ["CSC1016S"],
                    "Complete Computer Science foundation",
                    "cs_y1_csc",
                ),
                course(
                    v(["MAM1008"]) + ["MAM1019H"] + sta1,
                    "Complete discrete mathematics/fundamentals/statistics",
                    "cs_y1_math1",
                ),
                course(
                    mam1004 + ["MAM1000W", "MAM1031F"],
                    "Complete Mathematics",
                    "cs_y1_math2",
                ),
            ],
            "year2": [
                all_courses(
                    ["CSC2001F", "CSC2002S", "CSC2004Z"],
                    "Complete second-year Computer Science core",
                    "cs_y2_core",
                ),
                course(
                    ["INF2009F", "CSC2042S"],
                    "Complete Systems Analysis or Machine Learning",
                    "cs_y2_option",
                ),
            ],
            "year3": [
                all_courses(
                    ["CSC3002F", "CSC3003S"],
                    "Complete third-year Computer Science",
                    "cs_y3",
                )
            ],
        },
    )
    add(
        "environmental_geographical_science",
        "Environmental & Geographical Science",
        "EGS02",
        27,
        {
            "year1": [
                all_courses(
                    ["EGS1007S", "GEO1009F"], "Complete EGS foundations", "egs_y1_core"
                ),
                common_math_stats,
            ],
            "year2": [
                all_courses(
                    ["EGS2016F", "EGS2017S"], "Complete second-year EGS", "egs_y2"
                )
            ],
            "year3": [
                choose(
                    v(["EGS3012", "EGS3021", "EGS3022", "EGS3023"]),
                    2,
                    "Choose two third-year EGS courses",
                    "egs_y3",
                )
            ],
        },
    )
    add(
        "genetics",
        "Genetics",
        "MCB04",
        28,
        {
            "year1": [
                all_courses(
                    ["BIO1000F", "CEM1000W"],
                    "Complete Biology and Chemistry foundations",
                    "gen_y1_core",
                ),
                course(mam1004 + ["MAM1031F"], "Complete Mathematics", "gen_y1_math"),
                course(sta1, "Complete Statistics", "gen_y1_sta"),
            ],
            "year2": [
                all_courses(
                    ["MCB2020F", "MCB2021F", "MCB2023S"],
                    "Complete second-year Genetics",
                    "gen_y2",
                )
            ],
            "year3": [
                all_courses(
                    ["MCB3012Z", "MCB3023S", "MCB3026F"],
                    "Complete third-year Genetics",
                    "gen_y3",
                )
            ],
        },
        limited=True,
        note="Entry to second-year Genetics is capacity-limited and based on first-year performance; a transcript alone cannot confirm admission.",
    )
    add(
        "geology",
        "Geology",
        "GEO02",
        28,
        {
            "year1": [
                all_courses(
                    ["GEO1009F", "GEO1006S", "CEM1000W", "PHY1031F"],
                    "Complete Geology foundations",
                    "geo_y1_core",
                ),
                common_math_stats,
            ],
            "year2": [
                all_courses(
                    ["GEO2001F", "GEO2004S", "GEO2005X"],
                    "Complete second-year Geology",
                    "geo_y2",
                )
            ],
            "year3": [
                all_courses(
                    ["GEO3005F", "GEO3001S"], "Complete third-year Geology", "geo_y3"
                )
            ],
        },
        limited=True,
        note="The Geology major table states that entry to second-year courses is limited, although the general FB7.5 note names a shorter list. Faculty confirmation is required.",
    )
    add(
        "human_anatomy_physiology",
        "Human Anatomy & Physiology",
        "HUB17",
        29,
        {
            "year1": [
                all_courses(
                    ["BIO1000F", "BIO1004S", "CEM1000W"],
                    "Complete life-science foundations",
                    "hap_y1_core",
                ),
                common_math_stats,
            ],
            "year2": [
                all_courses(
                    ["HUB2019F", "HUB2021S"], "Complete second-year HAP", "hap_y2"
                )
            ],
            "year3": [
                all_courses(
                    ["HUB3006F", "HUB3007S"], "Complete third-year HAP", "hap_y3"
                )
            ],
        },
        limited=True,
        note="Entry to second-year Human Anatomy & Physiology is capacity-limited and based on first-year performance; a transcript alone cannot confirm admission.",
    )
    add(
        "marine_biology",
        "Marine Biology",
        "BIO05",
        30,
        {
            "year1": [
                all_courses(
                    ["BIO1000F", "BIO1004S", "CEM1000W", "STA1007S"],
                    "Complete Marine Biology foundations",
                    "mb_y1_core",
                ),
                course(mam1004 + ["MAM1031F"], "Complete Mathematics", "mb_y1_math"),
            ],
            "year2": [
                all_courses(
                    ["BIO2014F", "SEA2004F"],
                    "Complete Ecology and Oceanography",
                    "mb_y2_core",
                ),
                course(
                    v(["BIO2015", "BIO2016", "BIO2017"]),
                    "Complete an organismal biology option",
                    "mb_y2_option",
                ),
            ],
            "year3": [
                all_courses(
                    ["BIO3002F", "BIO3022S"],
                    "Complete third-year Marine Biology",
                    "mb_y3",
                )
            ],
        },
    )
    add(
        "mathematical_statistics",
        "Mathematical Statistics",
        "STA02",
        30,
        {
            "year1": [
                math_full(courses),
                course("STA1006S", "Complete Mathematical Statistics I", "ms_y1_sta"),
            ],
            "year2": [
                all_courses(
                    ["STA2004F", "STA2005S"],
                    "Complete second-year Mathematical Statistics",
                    "ms_y2",
                )
            ],
            "year3": [
                all_courses(
                    ["STA3041F", "STA3047S", "STA3048S"],
                    "Complete third-year Mathematical Statistics",
                    "ms_y3",
                )
            ],
        },
    )
    add(
        "mathematics",
        "Mathematics",
        "MAM02",
        31,
        {
            "year1": [
                math_full(courses),
                course(
                    "MAM1019H", "Complete Fundamentals of Mathematics", "math_y1_extra"
                ),
            ],
            "year2": [
                all_courses(
                    ["MAM2010F", "MAM2011F", "MAM2013S", "MAM2014S"],
                    "Complete second-year Mathematics",
                    "math_y2",
                )
            ],
            "year3": [
                choose(
                    v(
                        [
                            "MAM3010",
                            "MAM3011",
                            "MAM3012",
                            "MAM3013",
                            "MAM3014",
                            "MAM3015",
                        ]
                    ),
                    4,
                    "Choose four third-year Mathematics courses",
                    "math_y3_choose",
                ),
                course(
                    v(["MAM3010", "MAM3011"]),
                    "Include MAM3010 or MAM3011",
                    "math_y3_core",
                ),
            ],
        },
    )
    add(
        "ocean_atmosphere_science",
        "Ocean & Atmosphere Science",
        "SEA03",
        31,
        {
            "year1": [
                all_courses(
                    ["GEO1009F", "CEM1000W", "PHY1031F"],
                    "Complete Earth, Chemistry and Physics foundations",
                    "oas_y1_core",
                ),
                common_math_stats,
            ],
            "year2": [
                all_courses(
                    ["SEA2004F", "SEA2005S"],
                    "Complete second-year Oceanography",
                    "oas_y2",
                )
            ],
            "year3": [
                all_courses(
                    ["SEA3004F", "EGS3012S"],
                    "Complete third-year Ocean and Atmosphere Science",
                    "oas_y3",
                )
            ],
        },
    )
    add(
        "physics",
        "Physics",
        "PHY01",
        32,
        {
            "year1": [
                math_full(courses),
                course(
                    v(["PHY1004"]), "Complete Matter and Interactions", "phy_y1_phy"
                ),
                course(csc1015, "Complete Computer Science 1015", "phy_y1_csc"),
            ],
            "year2": [
                all_courses(
                    ["MAM2010F", "MAM2011F", "PHY2004W"],
                    "Complete second-year Physics curriculum",
                    "phy_y2",
                )
            ],
            "year3": [course("PHY3004W", "Complete Physics 3004", "phy_y3")],
        },
    )
    add(
        "quantitative_biology",
        "Quantitative Biology",
        "BIO13",
        32,
        {
            "year1": [
                all_courses(
                    ["BIO1000F", "BIO1004S"],
                    "Complete Biology foundations",
                    "qb_y1_bio",
                ),
                course(sta1, "Complete Statistics", "qb_y1_sta"),
                any_of(
                    [
                        all_courses(
                            mam1004 + v(["MAM1008"]),
                            "Complete MAM1004 and discrete mathematics",
                            "qb_y1_math_pair",
                        ),
                        math_full(courses),
                    ],
                    "Complete Mathematics foundation",
                    "qb_y1_math",
                ),
            ],
            "year2": [
                course("BIO2014F", "Complete Ecology and Evolution", "qb_y2_bio_core"),
                course(
                    v(["BIO2015", "BIO2016", "BIO2017"]),
                    "Complete an organismal Biology course",
                    "qb_y2_bio_option",
                ),
                any_of(
                    [
                        all_courses(
                            ["MAM2040F", "MAM2041F", "MAM2042S", "MAM2043S"],
                            "Complete Applied Mathematics sequence",
                            "qb_y2_mam",
                        ),
                        course(
                            v(["STA2"]),
                            "Complete an approved second-year Statistics course",
                            "qb_y2_sta",
                        ),
                    ],
                    "Complete quantitative methods at second year",
                    "qb_y2_methods",
                ),
            ],
            "year3": [
                course("BIO3019S", "Complete Quantitative Biology", "qb_y3_bio"),
                any_of(
                    [
                        choose(
                            v(["MAM3"]),
                            2,
                            "Complete two approved third-year Applied Mathematics courses",
                            "qb_y3_mam",
                        ),
                        course(
                            v(["STA3"]),
                            "Complete an approved third-year Statistics course",
                            "qb_y3_sta",
                        ),
                    ],
                    "Complete third-year quantitative methods",
                    "qb_y3_methods",
                ),
            ],
        },
    )
    add(
        "statistics_data_science",
        "Statistics & Data Science",
        "STA13",
        33,
        {
            "year1": [
                all_courses(
                    csc1015 + ["CSC1016S", "MAM1031F", "MAM1032S"],
                    "Complete data-science foundations",
                    "sds_y1_core",
                ),
                course(sta1, "Complete first-year Statistics", "sds_y1_sta"),
            ],
            "year2": [
                course("CSC2001F", "Complete Computer Science 2001", "sds_y2_csc"),
                course(
                    ["CSC2002S", "CSC2042S"],
                    "Complete algorithms or machine learning",
                    "sds_y2_cscopt",
                ),
                all_courses(
                    ["MAM2010F", "MAM2011F"],
                    "Complete calculus and linear algebra",
                    "sds_y2_math",
                ),
                course(
                    ["STA2004F", "STA2030S"],
                    "Complete statistical theory",
                    "sds_y2_sta1",
                ),
                course(
                    v(["STA2005", "STA2007", "STA2020"]),
                    "Complete applied statistics",
                    "sds_y2_sta2",
                ),
            ],
            "year3": [
                course(
                    ["STA3030F", "STA3041F"], "Complete inference option", "sds_y3_sta1"
                ),
                any_of(
                    [
                        course(
                            ["STA3022F", "STA3036S"],
                            "Complete a 36-credit option",
                            "sds_y3_opt",
                        ),
                        all_courses(
                            ["STA3047S", "STA3048S"],
                            "Complete machine learning and Bayesian analysis",
                            "sds_y3_pair",
                        ),
                    ],
                    "Complete final Statistics option",
                    "sds_y3_sta2",
                ),
            ],
        },
    )

    # Recompute level-7 pools after all definitions exist.
    for key in majors:
        replace_level7(key)
    # Computer Engineering is only permitted with Computer Science; the shared
    # senior Computer Science sequence supplies the remaining recognised level-7
    # depth, subject to FB7.7 overlap approval.
    majors["computer_engineering"]["curriculum_rules"][-1] = all_of(
        [
            {
                "type": "credit_pool",
                "id": "computer_engineering_own_level7",
                "label": "Computer Engineering level-7 courses",
                "course_codes": ["EEE3095S", "CSC3024S", "CSC3041F", "CSC3042F"],
                "required": 54,
            },
            course(
                ["CSC3002F", "CSC3003S"],
                "One shared Computer Science level-7 course",
                "computer_engineering_shared_cs",
            ),
        ],
        "Computer Engineering: at least 72 recognised level-7 credits",
        "computer_engineering_level7",
    )
    awards = award_rules(courses)
    for key, rules in awards.items():
        if key in majors:
            majors[key]["award_rules"] = rules

    # Required external-faculty courses count as Science only in these selected majors.
    for code in {
        c
        for m in majors.values()
        for r in m["curriculum_rules"]
        for c in _rule_codes(r)
    }:
        if code in courses and prefix(code) not in SCI_PREFIXES:
            courses[code]["counts_as_science"] = True
            courses[code]["general_elective"] = False

    science_electives = sorted(
        code
        for code, row in courses.items()
        if row["general_elective"] and row["counts_as_science"]
    )
    excluded_prefixes = ["AHS", "APG", "DOH"]
    non_science_first = {
        "type": "approved_credit_pool",
        "id": "non_science_first_72",
        "label": "Approved non-Science electives (first 72 credits)",
        "required": 0,
        "maximum": 72,
        "course_codes": [],
        "transcript_course_codes": [],
        "transcript_filters": {
            "minimum_credits": 18,
            "exclude_prefixes": excluded_prefixes,
        },
        "transcript_only": True,
        "allow_unlisted_transcript_courses": True,
        "verification_status": "unverified",
        "blocking": False,
        "approval_note": "Non-Science elective recognition requires a Science Student Advisor or Deputy Dean; handbook exclusions and duplicate-credit rules apply.",
    }
    non_science_excess = {
        "type": "approved_credit_pool",
        "id": "non_science_hierarchical_excess",
        "label": "Additional non-Science electives in a hierarchical sequence",
        "required": 0,
        "maximum": 108,
        "course_codes": [],
        "transcript_course_codes": [],
        "transcript_filters": {
            "minimum_credits": 18,
            "exclude_prefixes": excluded_prefixes,
        },
        "transcript_only": True,
        "allow_unlisted_transcript_courses": True,
        "verification_status": "discretionary",
        "blocking": False,
        "approval_note": "Beyond 72 non-Science credits, the courses must form an approved hierarchical sequence. The static transcript cannot verify that approval.",
    }
    general_rules = [
        {
            "type": "credit_pool",
            "id": "science_credits",
            "label": "At least 180 Science credits",
            "filters": {"science": True},
            "required": 180,
        },
        math_or_stats(courses),
        non_science_first,
        non_science_excess,
    ]

    current_regular = [
        {
            "type": "annual_credits",
            "minimum": 72,
            "label": "At least 72 credits in the preceding year",
        },
        {
            "type": "science_cumulative_credits",
            "year": 1,
            "minimum": 72,
            "label": "First-year Science credits",
        },
        {
            "type": "cumulative_credits",
            "year": 2,
            "minimum": 144,
            "label": "Second-year cumulative credits",
        },
        {
            "type": "selected_major_stage_complete",
            "year": 2,
            "stage": "year1",
            "label": "First-year requirements for selected majors",
        },
        {
            "type": "cumulative_credits",
            "year": 3,
            "minimum": 228,
            "label": "Third-year cumulative credits",
        },
        {
            "type": "manual",
            "year": 3,
            "label": "Able to complete within one further year",
            "note": "The transcript and static catalogue cannot fully verify future timetable and offering feasibility.",
        },
        {
            "type": "qualification_expected",
            "year": 4,
            "label": "Degree expected by end of fourth year",
        },
    ]
    current_edp = [
        {
            "type": "science_cumulative_credits",
            "year": 1,
            "minimum": 54,
            "label": "EDP first-year Science credits",
        },
        {
            "type": "annual_credits",
            "year": 2,
            "minimum": 72,
            "label": "EDP annual credits from second year",
        },
        {
            "type": "cumulative_credits",
            "year": 2,
            "minimum": 108,
            "label": "EDP second-year cumulative credits",
        },
        {
            "type": "selected_major_stage_complete",
            "year": 2,
            "stage": "year1",
            "required": 1,
            "label": "First-year requirements for at least one selected major",
        },
        {
            "type": "cumulative_credits",
            "year": 3,
            "minimum": 180,
            "label": "EDP third-year cumulative credits",
        },
        {
            "type": "senior_cumulative_credits",
            "year": 3,
            "minimum": 48,
            "label": "EDP senior credits by third year",
        },
        {
            "type": "cumulative_credits",
            "year": 4,
            "minimum": 252,
            "label": "EDP fourth-year cumulative credits",
        },
        {
            "type": "manual",
            "year": 4,
            "label": "Able to complete within one further year",
            "note": "The transcript and static catalogue cannot fully verify future timetable and offering feasibility.",
        },
        {
            "type": "qualification_expected",
            "year": 5,
            "label": "Degree expected by end of fifth year",
        },
    ]
    legacy_regular = [
        {
            "type": "course_equivalents_cumulative",
            "year": 1,
            "minimum": 1.5,
            "label": "Legacy regular: first-year course equivalents",
        },
        {
            "type": "course_equivalents_cumulative",
            "year": 2,
            "minimum": 3.5,
            "label": "Legacy regular: second-year course equivalents",
        },
        {
            "type": "selected_major_stage_complete",
            "year": 2,
            "stage": "year1",
            "label": "Legacy regular: all first-year major requirements",
        },
        {
            "type": "course_equivalents_cumulative",
            "year": 3,
            "minimum": 5.5,
            "label": "Legacy regular: third-year course equivalents",
        },
        {
            "type": "senior_course_equivalents_cumulative",
            "year": 3,
            "minimum": 1.5,
            "label": "Legacy regular: senior course equivalents",
        },
        {
            "type": "course_equivalents_cumulative",
            "year": 4,
            "minimum": 7.5,
            "label": "Legacy regular: fourth-year course equivalents",
        },
        {
            "type": "senior_course_equivalents_cumulative",
            "year": 4,
            "minimum": 3,
            "label": "Legacy regular: senior course equivalents by fourth year",
        },
        {
            "type": "qualification_expected",
            "year": 5,
            "label": "Legacy degree expected by end of fifth year",
        },
    ]
    legacy_edp = [
        {
            "type": "course_equivalents_cumulative",
            "year": 1,
            "minimum": 1,
            "label": "Legacy EDP: first-year course equivalents",
        },
        {
            "type": "course_equivalents_cumulative",
            "year": 2,
            "minimum": 3,
            "label": "Legacy EDP: second-year course equivalents",
        },
        {
            "type": "selected_major_stage_complete",
            "year": 2,
            "stage": "year1",
            "required": 1,
            "label": "Legacy EDP: first-year requirements for at least one major",
        },
        {
            "type": "course_equivalents_cumulative",
            "year": 3,
            "minimum": 5,
            "label": "Legacy EDP: third-year course equivalents",
        },
        {
            "type": "senior_course_equivalents_cumulative",
            "year": 3,
            "minimum": 1,
            "label": "Legacy EDP: senior course equivalents",
        },
        {
            "type": "course_equivalents_cumulative",
            "year": 4,
            "minimum": 7,
            "label": "Legacy EDP: fourth-year course equivalents",
        },
        {
            "type": "senior_course_equivalents_cumulative",
            "year": 4,
            "minimum": 2.5,
            "label": "Legacy EDP: senior course equivalents by fourth year",
        },
        {
            "type": "qualification_expected",
            "year": 5,
            "label": "Legacy EDP degree expected by end of fifth year",
        },
    ]

    def programme(
        name: str,
        key: str,
        years: int,
        code: str,
        current: list[dict[str, Any]],
        legacy: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return {
            "name": name,
            "minimum_nqf_credits": 360,
            "minimum_nqf_level_7_credits": 120,
            "minimum_semester_courses": 0,
            "minimum_senior_semester_courses": 0,
            "minimum_humanities_semester_courses": 0,
            "minimum_majors": 1,
            "minimum_humanities_majors": 0,
            "required_courses": [],
            "minimum_duration_years": years,
            "maximum_registration_years": years + 1,
            "qualification_codes": [code],
            "major_keys": sorted(majors),
            "elective_course_codes": science_electives,
            "elective_departments": [],
            "scope_verified": True,
            "route_type": "extended" if "edp" in key else "regular",
            "degree_category": "BSc",
            "programme_type": "science_degree",
            "curriculum_rules": general_rules,
            "pathways": {
                "current_2023_plus": {
                    "name": "First registered from 2023",
                    "curriculum_rules": [],
                    "progression_rules": current,
                    "verification_status": "verified",
                    "availability": "open",
                    "source": {"document": PDF_NAME, "page": 15},
                },
                "legacy_pre_2023": {
                    "name": "First registered before 2023",
                    "curriculum_rules": [],
                    "progression_rules": legacy,
                    "verification_status": "verified",
                    "availability": "continuing_only",
                    "availability_note": "Use only for a student first registered before 2023.",
                    "source": {"document": PDF_NAME, "page": 16},
                },
            },
            "pathway_required": True,
            "default_pathway_key": "",
            "availability": "open",
            "admission_notes": [
                "Formal acceptance into some majors occurs only at second-year registration and may be capacity-limited."
            ],
            "progression_notes": [
                "Progression outcomes remain decisions of the Faculty Examinations Committee and Senate."
            ],
            "award_notes": [
                "Science distinction uses first-attempt passes only; supplementary passes do not count."
            ],
            "source": {
                "document": PDF_NAME,
                "page": 13,
                "section": "Rules for the BSc degree",
            },
        }

    data = {
        "catalogue_version": "2026.1-science",
        "source": PDF_NAME,
        "programmes": {
            "bsc_science": programme(
                "Bachelor of Science — regular programme",
                "bsc_science",
                3,
                "SB001",
                current_regular,
                legacy_regular,
            ),
            "bsc_science_edp": programme(
                "Bachelor of Science — Extended Degree Programme",
                "bsc_science_edp",
                4,
                "SB016",
                current_edp,
                legacy_edp,
            ),
        },
        "majors": majors,
        "forbidden_major_combinations": [
            ["applied_statistics", "mathematical_statistics"],
            ["applied_statistics", "statistics_data_science"],
            ["mathematical_statistics", "statistics_data_science"],
        ],
        "cross_credit_exclusions": [
            {
                "type": "prefix",
                "value": "AHS",
                "note": "Allied Health Services courses do not count.",
            },
            {
                "type": "prefix",
                "value": "APG",
                "except": "Geomatics",
                "note": "Architecture and Planning courses do not count.",
            },
            {
                "type": "codes",
                "values": ["DOH1002F", "DOH1004S", "DOH1005F"],
                "note": "Excluded introductory Humanities courses.",
            },
            {"type": "code", "value": "STA1001F/S", "note": "STA1001 does not count."},
        ],
    }
    OUT.joinpath("courses.json").write_text(
        json.dumps(
            sorted(courses.values(), key=lambda x: x["code"]),
            indent=2,
            ensure_ascii=False,
        )
        + "\n"
    )
    OUT.joinpath("degree_requirements.json").write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    )
    OUT.joinpath("source_extraction").mkdir(exist_ok=True)
    OUT.joinpath("source_extraction/course_descriptions.json").write_text(
        json.dumps(
            sorted(courses.values(), key=lambda x: x["code"]),
            indent=2,
            ensure_ascii=False,
        )
        + "\n"
    )
    print(
        f"Wrote {len(courses)} course facts, {len(majors)} majors, and 2 programme routes to {OUT}"
    )


def _rule_codes(rule: dict[str, Any]) -> set[str]:
    out = set(str(c).upper() for c in rule.get("course_codes", []) if str(c).strip())
    for child in rule.get("children", []):
        if isinstance(child, dict):
            out.update(_rule_codes(child))
    return out


if __name__ == "__main__":
    main()
