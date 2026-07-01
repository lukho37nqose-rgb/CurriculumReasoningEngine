#!/usr/bin/env python3
"""Build the 2026 UCT Faculty of Health Sciences undergraduate catalogue.

Health Sciences is represented as a set of prescribed professional routes.  The
catalogue distinguishes standard and Fundamentals routes, academic-year gates,
clinical/professional conditions, and transcript-computable requirements from
conditions that still require Faculty or professional-body confirmation.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "uct_health"
TEXT_PATH = Path("/mnt/data/fhs2026.txt")
PDF_NAME = "2026 Faculty of Health Sciences Undergraduate Handbook"

PREFIX_DEPARTMENT = {
    "AAE": "Anaesthesia and Perioperative Medicine", "AHS": "Health and Rehabilitation Sciences",
    "ASL": "African Studies and Linguistics", "CEM": "Chemistry", "CHM": "Surgery",
    "FCE": "Family, Community and Emergency Care", "HSE": "Health Sciences Education",
    "HUB": "Human Biology", "IBS": "Integrative Biomedical Sciences", "MDN": "Medicine",
    "OBS": "Obstetrics and Gynaecology", "PED": "Paediatrics and Child Health",
    "PHY": "Physics", "PPH": "Public Health", "PRY": "Psychiatry and Mental Health",
    "PSY": "Psychology", "PTY": "Pathology", "SLL": "Languages and Literatures",
}


def prefix(code: str) -> str:
    match = re.match(r"[A-Z]+", code)
    return match.group(0) if match else ""


def offered_from_code(code: str) -> list[str]:
    suffix = code[-1:] if code and code[-1:].isalpha() else ""
    return {
        "F": ["First semester"], "S": ["Second semester"], "W": ["Whole year"],
        "H": ["Half course over whole year"], "X": ["Non-standard period"],
        "Z": ["Other/non-standard period"], "L": ["Winter term"], "P": ["Summer term"],
    }.get(suffix, [])


def expand_code(code: str) -> list[str]:
    code = re.sub(r"\s+", "", code.upper())
    match = re.fullmatch(r"([A-Z]{3}\d{4})([A-Z](?:/[A-Z])+)", code)
    if not match:
        return [code]
    stem, suffixes = match.groups()
    return [stem + suffix for suffix in suffixes.split("/")]


def extract_courses(text: str) -> tuple[dict[str, dict[str, Any]], dict[str, list[str]]]:
    heading = re.compile(r"(?m)^\s*([A-Z]{3}\d{4}[A-Z](?:/[A-Z])*)\s+([^\n]+?)\s*$")
    matches = list(heading.finditer(text))
    records: dict[str, dict[str, Any]] = {}
    aliases: dict[str, list[str]] = {}
    for index, match in enumerate(matches):
        raw_code = match.group(1).strip().upper()
        title = re.sub(r"\s+", " ", match.group(2)).strip(" .")
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        segment = text[match.end():end]
        credit = re.search(r"(\d+)\s+NQF credits? at NQF level\s+(\d+)", segment[:3000], re.I)
        if not credit:
            continue
        credits, level = int(credit.group(1)), int(credit.group(2))
        page = text.count("\f", 0, match.start()) + 1
        not_offered = bool(re.search(r"not offered in 2026|not on offer in 2026", title + " " + segment[:800], re.I))

        entry = re.search(
            r"Course entry requirements:\s*(.*?)(?:\n\s*Co-requisites:|\n\s*Course outline:|\n\s*DP requirements:|\Z)",
            segment[:6000], re.S | re.I,
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
            unsafe = re.search(
                r"\bor\b|permission|minimum|at least|acceptance|successful completion of all|equivalent|%|programme|year of study",
                entry_text, re.I,
            )
            if codes and not unsafe:
                prereqs = sorted(set(codes)); prereq_verified = True
        elif level == 5:
            prereq_verified = True

        co_match = re.search(r"Co-requisites:\s*(.*?)(?:\n\s*Course outline:|\n\s*DP requirements:|\Z)", segment[:6000], re.S | re.I)
        co_text = re.sub(r"\s+", " ", co_match.group(1)).strip() if co_match else ""
        co_reqs: list[str] = []
        if co_text and not re.fullmatch(r"None\.?", co_text, re.I):
            for found in re.findall(r"\b[A-Z]{3}\d{4}[A-Z]?(?:/[A-Z])?\b", co_text):
                co_reqs.extend(expand_code(found))
            co_reqs = sorted(set(co_reqs))

        outline = re.search(r"Course outline:\s*(.*?)(?:\n\s*Lecture times:|\n\s*DP requirements:|\n\s*Assessment:|\Z)", segment[:9000], re.S | re.I)
        description = re.sub(r"\s+", " ", outline.group(1)).strip()[:1000] if outline else ""

        canonical_codes = expand_code(raw_code)
        equivalent_codes = set(canonical_codes)
        equivalence_window = segment[:900]
        if re.search(r"equivalent courses", equivalence_window, re.I):
            equivalent_codes.update(re.findall(r"\b[A-Z]{3}\d{4}[A-Z]?\b", equivalence_window))
        for canonical in canonical_codes:
            aliases[canonical] = sorted(equivalent_codes)

        fact = {
            "name": title, "credits": credits, "nqf_level": level,
            "prerequisites": prereqs, "prerequisites_verified": prereq_verified,
            "co_requisites": co_reqs, "offering_verified": True,
            "description": description, "verification_status": "verified",
            "general_elective": False, "counts_towards_general_degree": True,
            "counts_as_humanities": False, "counts_as_science": False,
            "counts_towards_course_equivalents": False, "credit_bearing": credits > 0,
            "recognition_note": "Recognition is controlled by the selected Health Sciences professional programme.",
            "source": {"document": PDF_NAME, "page": page, "section": "Course outline"},
        }
        for code in sorted(equivalent_codes):
            candidate = dict(fact, code=code, department=PREFIX_DEPARTMENT.get(prefix(code), prefix(code)),
                             offered=[] if not_offered else offered_from_code(code))
            old = records.get(code)
            if old is None or (description and not old.get("description")):
                records[code] = candidate
    return records, aliases


def source(page: int, section: str = "Rules and curricula for undergraduate programmes") -> dict[str, Any]:
    return {"document": PDF_NAME, "page": page, "section": section}


def course_rule(codes: str | Iterable[str], label: str, rule_id: str, **extra: Any) -> dict[str, Any]:
    if isinstance(codes, str):
        codes = [codes]
    row = {"type": "course", "id": rule_id, "label": label, "course_codes": list(dict.fromkeys(codes))}
    row.update(extra)
    return row


def all_courses(codes: Iterable[str], label: str, rule_id: str, **extra: Any) -> dict[str, Any]:
    row = {"type": "all_courses", "id": rule_id, "label": label, "course_codes": list(dict.fromkeys(codes))}
    row.update(extra)
    return row


def all_of(children: list[dict[str, Any]], label: str, rule_id: str, **extra: Any) -> dict[str, Any]:
    row = {"type": "all_of", "id": rule_id, "label": label, "children": children}
    row.update(extra)
    return row


def any_of(children: list[dict[str, Any]], label: str, rule_id: str, **extra: Any) -> dict[str, Any]:
    row = {"type": "any_of", "id": rule_id, "label": label, "children": children}
    row.update(extra)
    return row


def manual(label: str, rule_id: str, note: str, *, status: str = "unverified", blocking: bool = True) -> dict[str, Any]:
    return {"type": "manual", "id": rule_id, "label": label, "note": note,
            "assumed_complete": True, "blocking": blocking, "status": status}


def weighted_average(label: str, rule_id: str, minimum: float, codes: list[str] | None = None, filters: dict[str, Any] | None = None) -> dict[str, Any]:
    row: dict[str, Any] = {"type": "weighted_average", "id": rule_id, "label": label, "minimum_average": minimum}
    if codes is not None: row["course_codes"] = codes
    if filters is not None: row["filters"] = filters
    return row


def no_failures(label: str, rule_id: str) -> dict[str, Any]:
    return {"type": "no_failures", "id": rule_id, "label": label}


def programme(
    *, name: str, code: str, minimum_credits: int, level7: int, level8: int = 0,
    minimum_years: int, maximum_years: int, required: list[str], rules: list[dict[str, Any]],
    progression: list[dict[str, Any]], awards: list[dict[str, Any]], page: int,
    route_type: str = "structured", availability: str = "open", availability_note: str = "",
    admission_notes: list[str] | None = None, progression_notes: list[str] | None = None,
    award_notes: list[str] | None = None, pathways: dict[str, Any] | None = None,
    pathway_required: bool = False,
) -> dict[str, Any]:
    return {
        "name": name, "minimum_nqf_credits": minimum_credits,
        "minimum_nqf_level_7_credits": level7,
        "level_credit_requirements": ({"8": level8} if level8 else {}),
        "minimum_semester_courses": 0, "minimum_senior_semester_courses": 0,
        "minimum_humanities_semester_courses": 0, "minimum_majors": 0,
        "minimum_humanities_majors": 0, "required_courses": required,
        "minimum_duration_years": minimum_years, "maximum_registration_years": maximum_years,
        "qualification_codes": [code], "major_keys": [], "elective_course_codes": [],
        "elective_departments": [], "scope_verified": True, "route_type": route_type,
        "degree_category": "Health Sciences", "programme_type": "health_professional",
        "curriculum_rules": rules, "pathways": pathways or {},
        "pathway_required": pathway_required, "default_pathway_key": "",
        "availability": availability, "availability_note": availability_note,
        "admission_notes": admission_notes or [], "progression_notes": progression_notes or [],
        "award_notes": award_notes or [], "progression_rules": progression,
        "award_rules": awards, "source": source(page),
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    text = TEXT_PATH.read_text(errors="replace")
    courses, aliases = extract_courses(text)

    # Canonical facts required by curriculum tables. These values come from the
    # programme tables and repair cases where the descriptive-course parser did
    # not encounter a standalone heading.
    facts: dict[str, tuple[str, int, int]] = {
        "PPH1001F": ("Becoming a Professional",15,5), "PPH1002S": ("Becoming a Health Professional",15,5),
        "AHS1003F": ("Speech and Hearing Sciences",18,5), "PSY1004F": ("Introduction to Psychology Part 1",18,5),
        "PSY1005S": ("Introduction to Psychology Part 2",18,5), "HUB1014S": ("Anatomy for Communication Sciences",20,5),
        "AHS1025S": ("Early Intervention",18,5), "AHS1042F": ("Human Communication Development",18,5),
        "ASL1300F": ("Introduction to Language Studies",15,5), "AHS1045S": ("Basis of Hearing and Balance",18,5),
        "ASL1301S": ("Introduction to Sociolinguistics",15,5), "PSY1006F": ("Introduction to Psychology Part 1+",10,5),
        "PSY1007S": ("Introduction to Psychology Part 2+",10,5), "SLL1028H": ("Xhosa for Health and Rehabilitation Sciences",18,5),
        "SLL1048H": ("Afrikaans for Health and Rehabilitation Sciences",18,5), "AHS1054W": ("South African Sign Language",8,5),
        "PSY2015F": ("Research in Psychology I",20,6), "PSY2014S": ("Cognitive Neuroscience and Abnormal Psychology",20,6),
        "AHS2047S": ("Paediatric Rehabilitative Audiology",18,6), "AHS2106F": ("Child Language",21,6),
        "AHS2046F": ("Diagnostic Audiology",18,6), "AHS2110W": ("Clinical Audiology I",24,6),
        "AHS2111S": ("Diagnostic Audiology in Special Populations",15,6), "AHS2107F": ("Child Speech",18,6),
        "AHS2108W": ("Clinical Speech Therapy I",24,6), "AHS2109S": ("School-Based Interventions",21,6),
        "AHS3078H": ("Research Methods and Biostatistics I",10,7), "AHS3008W": ("Clinical Audiology II",30,7),
        "AHS3062F": ("Rehabilitation Technology",22,7), "AHS3065S": ("Adult Rehabilitative Audiology",18,7),
        "AHS3075F": ("OAEs and Electrophysiology",22,7), "AHS3104S": ("Vestibular Management",15,7),
        "AHS3105F": ("Public Health Audiology",15,7), "AHS3005W": ("Clinical Speech Therapy II",30,7),
        "AHS3071F": ("Acquired Neurogenic Language Disorders",22,7), "AHS3072S": ("Paediatric Motor Speech Disorders and Dysphagia",22,7),
        "AHS3073F": ("Adult Motor Speech Disorders and Dysphagia",22,7), "AHS3102S": ("Adult Language Disorders",15,7),
        "AHS3103F": ("Fluency, Voice and Craniofacial Disorders",15,7), "AHS4000W": ("Research Project",30,8),
        "AHS4067S": ("Professional Practice",4,8), "AHS4008H": ("Clinical Audiology IIIA",45,8),
        "AHS4009H": ("Clinical Audiology IIIB",45,8), "AHS4005H": ("Clinical Speech Therapy IIIA",45,8),
        "AHS4006H": ("Clinical Speech Therapy IIIB",45,8), "HSE1001F": ("Fundamentals of Health Sciences",60,5),
        "HSE1001S": ("Fundamentals of Health Sciences",60,5),
        "HUB1019F": ("Anatomy and Physiology I for Health and Rehabilitation Sciences",18,5),
        "HUB1020S": ("Anatomy and Physiology II for Health and Rehabilitation Sciences",18,5),
        "AHS1032S": ("Introduction to Occupational Therapy",20,5), "AHS1035F": ("Occupation and Health",22,5),
        "AHS2002W": ("Professional Practice and Ethics",13,6), "PRY2002W": ("Mental Health",14,6),
        "PSY2013F": ("Social and Developmental Psychology",20,6), "HUB2015W": ("Anatomy and Physiology II for HRS",36,6),
        "AHS2043W": ("Occupational Therapy Theory and Practice",36,6), "AHS3107W": ("OT Theory and Practice in Physical Health",38,7),
        "AHS3108W": ("OT Theory and Practice in Mental Health",38,7), "AHS3113W": ("Foundation Theory for OT Practice I",26,7),
        "AHS4119W": ("Occupational Therapy Research and Practice Management",48,8),
        "AHS4120W": ("Foundation Theory for Occupational Therapy Practice II",48,8),
        "AHS4121W": ("Occupational Therapy Practice and Service Learning",48,8),
        "AHS4122X": ("Occupational Therapy Practice and Service Learning Part A",32,8),
        "AHS4123X": ("Occupational Therapy Practice and Service Learning Part B",16,8),
        "HUB1022F": ("Human Biology for Physiotherapy I",9,5), "AHS1033F": ("Movement Science I",18,5),
        "HUB1023S": ("Human Biology for Physiotherapy II",9,5), "AHS1034S": ("Introduction to Applied Physiotherapy",22,5),
        "HUB2023W": ("Human Biology for Physiotherapy III",9,6), "AHS2050H": ("Clinical Practice I",18,6),
        "AHS2052H": ("Movement Science II",38,6), "AHS2053H": ("Applied Physiotherapy II",32,6),
        "AHS3069W": ("Clinical Physiotherapy",62,7), "AHS3070H": ("Becoming a Rehabilitation Professional",22,7),
        "AHS3076H": ("Movement Science III",24,7), "AHS3077H": ("Applied Physiotherapy III",22,7),
        "AHS4065W": ("Clinical Physiotherapy",98,8), "AHS4066F": ("Becoming a Rehabilitation Professional",4,8),
        "AHS4185S": ("Becoming a Rehabilitation Professional",4,8), "AHS4071F": ("Applied Physiotherapy",20,8),
        "AHS4184S": ("Applied Physiotherapy",20,8), "AHS4072H": ("Research Methods and Biostatistics II",10,8),
        "MDN3005W": ("Cosmetic Science and Skin Biology",30,7), "MDN3006W": ("Cosmetic Formulation",30,7),
        "MDN3007W": ("Cosmetic Product Development",30,7), "MDN3008W": ("Cosmetic Regulation and Safety",15,7),
        "MDN3009W": ("Cosmetic Business and Marketing",15,7), "MDN3010W": ("In-service Training",0,7),
        "CEM1011F": ("Chemistry for Medical Students",18,5), "PHY1025F": ("Physics for Medical Students",18,5),
        "SLL1044S": ("Language for Medical Students I",18,5), "SLL1041S": ("Language for Medical Students II",18,5),
        "HUB1006F": ("Introduction to Integrated Health Sciences Part I",30,5),
        "IBS1007S": ("Introduction to Integrated Health Sciences Part II",35,5),
        "PTY2000S": ("Integrated Health Systems Part IB",47,6), "FCE2000W": ("Becoming a Doctor Part IA",21,6),
        "SLL2002H": ("Becoming a Doctor Part IB",18,6), "HSE2000W": ("Becoming a Doctor Part IC",22,6),
        "HUB2017H": ("Integrated Health Systems Part IA",57,6), "FCE3000F": ("Becoming a Doctor Part IIA",10,7),
        "MDN3001S": ("Becoming a Doctor Part IID",68,7), "SLL3002F": ("Becoming a Doctor Part IIB",30,7),
        "HSE3000F": ("Becoming a Doctor Part IIC",15,7), "PTY3009F": ("Integrated Health Systems Part II",59,7),
        "MDN2001S": ("Special Study Module",16,6), "SLL3003W": ("Language and Clinical Practice",0,8),
        "PRY4000W": ("Psychiatry",30,8), "AAE4002W": ("Anaesthesia Part I",20,8), "OBS4003W": ("Obstetrics",30,8),
        "MDN4011W": ("Medicine",40,8), "MDN4001W": ("Clinical Methods",20,8), "MDN4015W": ("Integrated Clinical Practice",20,8),
        "PED4016W": ("Paediatrics",10,8), "PED4049W": ("Child Health",10,8), "PPH4056W": ("Health in Context",40,8),
        "PED5005W": ("Paediatrics I",10,8), "PED5006W": ("Paediatrics II",30,8), "CHM5003W": ("Surgery I",40,8),
        "MDN5003H": ("Medicine I",20,8), "CHM5004H": ("Surgery II",10,8), "OBS5005W": ("Obstetrics and Gynaecology",20,8),
        "CHM5005H": ("Surgical Specialties I",10,8), "MDN5005W": ("Medicine II",10,8), "MDN5006W": ("Medicine III",10,8),
        "CHM5007W": ("Surgical Specialties II",20,8), "CHM5008W": ("Surgical Specialties III",10,8),
        "CHM5009W": ("Surgical Specialties IV",10,8), "CHM5010W": ("Surgical Specialties V",10,8),
        "CHM6000W": ("Surgery",41,8), "MDN6000W": ("Medicine",41,8), "OBS6000W": ("Obstetrics and Gynaecology",41,8),
        "PED6000W": ("Paediatrics and Child Health",30,8), "PED6004W": ("Child Health",10,8),
        "FCE6000W": ("Family Medicine and Palliative Care",21,8), "PRY6000W": ("Psychiatry",21,8),
        "AAE6000W": ("Anaesthesia",10,8), "FCE6001W": ("Primary Care",19,8), "FCE6005W": ("Emergency Medicine",10,8),
        "PTY6012W": ("Forensic Pathology",10,8), "HSE6004W": ("Final Integrated Assessment",0,8),
        "HUB3006F": ("Applied Human Biology",36,7), "HUB3007S": ("Human Neurosciences",36,7),
        "IBS3020W": ("Molecular Medicine",72,7),
        "AAE4003W": ("Anaesthesia NMFC",8,8), "MDN4017W": ("Medicine NMFC",15,8),
        "PED4017W": ("Paediatrics NMFC",7,8), "OBS4006W": ("Obstetrics NMFC",15,8), "PRY4001W": ("Psychiatry NMFC",15,8),
        "AAE5000W": ("Anaesthesia NMFC",10,8), "PTY5012W": ("Forensic Pathology NMFC",10,8),
        "OBS5006W": ("Obstetrics NMFC",27,8), "MDN5000W": ("Medicine NMFC",24,8), "OBS5007W": ("Gynaecology NMFC",41,8),
        "PED5004W": ("Paediatrics NMFC",40,8), "PRY5001W": ("Psychiatry NMFC",30,8), "CHM5011W": ("Surgery NMFC",19,8),
        "AHS1060F": ("Disability Practice Module 1",7,5), "AHS1060S": ("Disability Practice Module 1",7,5),
        "AHS1061F": ("Disability Practice Module 2",8,5), "AHS1061S": ("Disability Practice Module 2",8,5),
        "AHS1062F": ("Disability Practice Module 3",10,5), "AHS1062S": ("Disability Practice Module 3",10,5),
        "AHS1063F": ("Disability Practice Module 4",15,5), "AHS1063S": ("Disability Practice Module 4",15,5),
        "AHS1064F": ("Disability Practice Module 5",15,5), "AHS1064S": ("Disability Practice Module 5",15,5),
        "AHS1065F": ("Disability Practice Module 6",15,5), "AHS1065S": ("Disability Practice Module 6",15,5),
        "AHS1066F": ("Disability Practice Module 7",25,5), "AHS1066S": ("Disability Practice Module 7",25,5),
        "AHS1067F": ("Disability Practice Module 8",25,5), "AHS1067S": ("Disability Practice Module 8",25,5),
        "AHS1068W": ("Combined Disability Practice Modules 1 and 2",15,5),
        "AHS1069W": ("Combined Disability Practice Modules 4 and 5",30,5),
        "AHS1070W": ("Combined Disability Practice Modules 7 and 8",50,5),
    }
    for code, (name, credits, level) in facts.items():
        if code not in courses:
            courses[code] = {
                "code": code, "name": name, "credits": credits, "nqf_level": level,
                "prerequisites": [], "prerequisites_verified": level == 5,
                "co_requisites": [], "offered": offered_from_code(code), "offering_verified": True,
                "department": PREFIX_DEPARTMENT.get(prefix(code), prefix(code)), "description": "",
                "verification_status": "verified", "source": source(42, "Published programme curriculum table"),
                "general_elective": False, "counts_towards_general_degree": True,
                "counts_as_humanities": False, "counts_as_science": False,
                "counts_towards_course_equivalents": False, "credit_bearing": credits > 0,
                "recognition_note": "Prescribed or recognised only within the selected Health Sciences programme.",
            }
        aliases.setdefault(code, [code])

    # Psychology course renumbering is visible in the 2026 course descriptions.
    for old, new in (("PSY1004F", "PSY1009F"), ("PSY1005S", "PSY1010S")):
        if new in courses:
            aliases[old] = sorted(set(aliases.get(old, [old]) + [new]))

    def accepted(code: str) -> list[str]:
        return sorted(set(aliases.get(code, [code])))

    def direct_rules(codes: Iterable[str], stem: str) -> list[dict[str, Any]]:
        return [course_rule(accepted(code), courses[code]["name"], f"{stem}_{code.lower()}") for code in codes]

    clinical_manual = manual(
        "Clinical placement, practice hours and professional competencies",
        "clinical_professional_confirmation",
        "The transcript confirms course results but not all clinical hours, logbooks, placement sign-offs, fitness-to-practise findings or professional registration conditions.",
    )
    hpcsa_manual = manual(
        "HPCSA and Faculty professional requirements", "hpcsa_confirmation",
        "Registration with the relevant professional council, Hepatitis B requirements where applicable, and any professionalism or fitness-to-practise conditions require current Faculty confirmation.",
    )
    hrs_progress = [
        {"type":"repeat_failure","label":"No course failed more than once","maximum_failures":1},
        {"type":"failed_course_fraction","label":"From second year, do not fail half or more of the annual courses","threshold":0.5},
        {"type":"repeat_year_failure","label":"No failed course during a repeat year"},
    ]
    hrs_award = [{"name":"Degree with distinction","curriculum_rules":[weighted_average("Cumulative programme GPA", "hrs_gpa", 75)]}]

    # Audiology / SLP
    comm_common = ["PPH1001F","PPH1002S","AHS1003F","HUB1014S","AHS1025S","AHS1042F","ASL1300F",
                   "AHS1054W","PSY2015F","PSY2014S","AHS2047S","AHS2106F","AHS3078H","AHS4000W","AHS4067S"]
    comm_common_rules = direct_rules(comm_common, "comm") + [
        course_rule(accepted("PSY1004F"), "Introduction to Psychology Part 1", "comm_psy1"),
        course_rule(accepted("PSY1005S"), "Introduction to Psychology Part 2", "comm_psy2"),
        course_rule(["SLL1028H","SLL1048H"], "Approved Health and Rehabilitation Sciences language course", "comm_language"),
        clinical_manual, hpcsa_manual,
    ]
    aud_codes = ["AHS1045S","AHS2046F","AHS2110W","AHS2111S","AHS3008W","AHS3062F","AHS3065S","AHS3075F","AHS3104S","AHS3105F","AHS4008H","AHS4009H"]
    slp_codes = ["ASL1301S","AHS2107F","AHS2108W","AHS2109S","AHS3005W","AHS3071F","AHS3072S","AHS3073F","AHS3102S","AHS3103F","AHS4005H","AHS4006H"]

    first_sem_common = ["AHS1003F","PSY1004F","AHS1042F","ASL1300F"]
    aud_second = ["PSY1005S","AHS1025S","AHS1045S"]
    slp_second = ["PSY1005S","AHS1025S","ASL1301S"]
    comm_progress_base = hrs_progress + [
        {"type":"failed_courses_by_group","label":"First-year semester failure threshold", "groups":[
            {"label":"First semester communication-sciences courses","course_codes":first_sem_common,"threshold":2},
        ]},
        {"type":"maximum_years","label":"Ordinary maximum registration period","maximum":5},
    ]

    # Occupational Therapy
    ot_codes = ["PPH1001F","PPH1002S","HUB1019F","HUB1020S","AHS1032S","AHS1035F","AHS2002W","PRY2002W","PSY2013F","HUB2015W","AHS2043W","SLL1028H","SLL1048H","AHS3078H","AHS3107W","AHS3108W","AHS3113W","AHS4119W","AHS4120W"]
    ot_rules = direct_rules(ot_codes, "ot") + [
        course_rule(accepted("PSY1004F"), "Introduction to Psychology Part 1", "ot_psy1"),
        course_rule(accepted("PSY1005S"), "Introduction to Psychology Part 2", "ot_psy2"),
        any_of([
            course_rule("AHS4121W", "Complete AHS4121W", "ot_service_standard"),
            all_courses(["AHS4122X","AHS4123X"], "Complete the adjusted service-learning pair", "ot_service_adjusted"),
        ], "Occupational Therapy practice and service learning", "ot_service"),
        clinical_manual, hpcsa_manual,
    ]

    # Physiotherapy
    phys_codes = ["PPH1001F","PPH1002S","HUB1019F","HUB1020S","HUB1022F","HUB1023S","AHS1033F","AHS1034S","AHS2002W","HUB2015W","HUB2023W","AHS2050H","AHS2052H","AHS2053H","AHS3069W","AHS3070H","AHS3076H","AHS3077H","AHS3078H","AHS4065W","AHS4072H"]
    phys_rules = direct_rules(phys_codes, "phys") + [
        course_rule(accepted("PSY1004F"), "Introduction to Psychology Part 1", "phys_psy1"),
        course_rule(["SLL1028H","SLL1048H"], "Approved Health and Rehabilitation Sciences language course", "phys_language"),
        course_rule(["AHS4066F","AHS4185S"], "Becoming a Rehabilitation Professional", "phys_professional"),
        course_rule(["AHS4071F","AHS4184S"], "Applied Physiotherapy", "phys_applied"),
        clinical_manual, hpcsa_manual,
    ]

    # MBChB
    mbchb_years = {
        1:["PPH1001F","PPH1002S","HUB1006F","IBS1007S","CEM1011F","PHY1025F","SLL1044S","SLL1041S"],
        2:["PTY2000S","FCE2000W","SLL2002H","HSE2000W","HUB2017H"],
        3:["FCE3000F","MDN3001S","SLL3002F","HSE3000F","PTY3009F"],
        4:["SLL3003W","PRY4000W","AAE4002W","OBS4003W","MDN4011W","MDN4001W","MDN4015W","PED4016W","PED4049W","PPH4056W"],
        5:["PED5005W","PED5006W","CHM5003W","MDN5003H","CHM5004H","OBS5005W","CHM5005H","MDN5005W","MDN5006W","CHM5007W","CHM5008W","CHM5009W","CHM5010W"],
        6:["CHM6000W","MDN6000W","OBS6000W","PED6000W","PED6004W","FCE6000W","PRY6000W","AAE6000W","FCE6001W","FCE6005W","PTY6012W","HSE6004W"],
    }
    ssm = ["MDN2001S","AAE2001F","AAE2001S","AHS2054F","AHS2054S","CHM2001F","CHM2001S","FCE2003F","FCE2003S","HSE2001F","HSE2001S","HUB2020F","HUB2020S","IBS2001F","IBS2001S","OBS2001F","OBS2001S","PED2001F","PED2001S","PPH2002F","PPH2002S","PRY2001F","PRY2001S","PTY2002F","PTY2002S","RAY2004F","RAY2004S"]
    for code in ssm:
        if code not in courses:
            base = courses["MDN2001S"]
            courses[code] = dict(base, code=code, name="Special Study Module", offered=offered_from_code(code), department=PREFIX_DEPARTMENT.get(prefix(code),prefix(code)))
    mbchb_rules: list[dict[str,Any]] = []
    for year, codes in mbchb_years.items():
        for code in codes:
            mbchb_rules.append(course_rule(accepted(code), courses[code]["name"], f"mbchb_y{year}_{code.lower()}"))
    mbchb_rules += [course_rule(ssm, "Complete one approved Special Study Module", "mbchb_ssm"), clinical_manual, hpcsa_manual]
    mbchb_progress = [
        {"type":"repeat_failure","label":"No course failed more than once","maximum_failures":1},
        {"type":"failed_course_fraction","label":"Do not fail more than half of the annual courses","threshold":0.5},
        {"type":"repeat_year_failure","label":"No failed course during a repeat year"},
        {"type":"maximum_years","label":"Ordinary maximum registration period","maximum":7},
    ]
    mbchb_pathways = {
        "gpa_2024_plus": {
            "name":"First enrolled from 2024 — GPA award rules", "curriculum_rules":[], "progression_rules":[],
            "verification_status":"verified", "availability":"open", "source":source(34,"FGU11 award rules"),
            "award_rules":[
                {"name":"Honours in Basic Sciences","curriculum_rules":[weighted_average("Years 1–3 cumulative GPA", "mb_basic_gpa", 80, sum((mbchb_years[y] for y in (1,2,3)), []) + ssm)]},
                {"name":"Honours in Clinical Sciences","curriculum_rules":[weighted_average("Years 4–6 cumulative GPA", "mb_clinical_gpa", 75, sum((mbchb_years[y] for y in (4,5,6)), []))]},
                {"name":"Degree with honours","curriculum_rules":[weighted_average("Cumulative MBChB GPA", "mb_honours_gpa", 75)]},
                {"name":"Degree with first-class honours","curriculum_rules":[weighted_average("Cumulative MBChB GPA", "mb_first_gpa", 85)]},
            ],
        },
        "legacy_pre_2024": {
            "name":"First enrolled before 2024 — legacy points award rules", "curriculum_rules":[], "progression_rules":[],
            "verification_status":"verified", "availability":"continuing_only",
            "availability_note":"Use only for students first registered before 2024.", "source":source(34,"FGU11 legacy award rules"),
            "award_rules":[{"name":"Legacy MBChB award assessment","curriculum_rules":[manual("Legacy points-based award calculation","mb_legacy_award","The pre-2024 points system depends on the detailed historical award table and Faculty confirmation.",status="discretionary")]}],
        },
    }

    # BSc Medicine credit-recognition route
    bscmed_recognised = ["HUB1006F","IBS1007S","PHY1025F","PTY2000S","HUB2017H","MDN2001S","FCE2000W","SLL2002H","PTY3009F","HUB3006F","HUB3007S","IBS3020W","AHS3078H"]
    bscmed_rules = [
        {"type":"credits","id":"bscmed_total","label":"At least 360 approved credits","required":360},
        {"type":"level_credits","id":"bscmed_level7","label":"At least 120 level-7 credits","nqf_level":7,"required":120},
        {"type":"maximum_credit_pool","id":"bscmed_level5_cap","label":"No more than 96 level-5 credits","course_codes":bscmed_recognised,"filters":{"nqf_levels":[5]},"maximum":96},
    ]

    # Higher Certificate in Disability Practice
    split_groups = []
    for number in range(1060,1068):
        split_groups.append(course_rule([f"AHS{number}F",f"AHS{number}S"], f"Complete AHS{number} in either semester", f"disability_{number}"))
    combined = all_of([
        course_rule("AHS1068W","Combined modules 1 and 2","disability_1068"),
        course_rule(["AHS1062F","AHS1062S"],"Module 3","disability_1062_combined"),
        course_rule("AHS1069W","Combined modules 4 and 5","disability_1069"),
        course_rule(["AHS1065F","AHS1065S"],"Module 6","disability_1065_combined"),
        course_rule("AHS1070W","Combined modules 7 and 8","disability_1070"),
    ], "Combined whole-year curriculum", "disability_combined")
    disability_rules = [any_of([all_of(split_groups,"Split-semester curriculum","disability_split"), combined], "Complete an approved 120-credit Disability Practice curriculum", "disability_curriculum"), clinical_manual]

    # Cosmetic Formulation
    cosmetic_codes = ["MDN3005W","MDN3006W","MDN3007W","MDN3008W","MDN3009W","MDN3010W"]
    cosmetic_award = [{"name":"Diploma with distinction","curriculum_rules":[
        weighted_average("Cumulative diploma GPA","cosmetic_gpa",75),
        all_of([
            {"type":"minimum_mark","id":f"cosmetic_min_{code.lower()}","label":f"{code} mark","course_codes":[code],"minimum_mark":60}
            for code in cosmetic_codes if courses[code]["credits"] > 0
        ], "No credit-bearing course below 60%", "cosmetic_minimum"),
        no_failures("All courses passed at first attempt","cosmetic_no_failures"),
    ]}]

    # NMFC
    nmfc_codes = ["AAE4003W","MDN4017W","PED4017W","OBS4006W","PRY4001W","AAE5000W","PTY5012W","OBS5006W","MDN5000W","OBS5007W","CHM5005W","PED5004W","PRY5001W","CHM5011W","CHM5004W","HSE6004W"]
    nmfc_rules = direct_rules(nmfc_codes,"nmfc") + [manual("External qualification and final examination","nmfc_external_award","This collaboration route is controlled with the National Department of Health and the Cuban training institution; UCT does not independently confer the medical qualification from this transcript segment.",status="discretionary")]

    programmes: dict[str, dict[str,Any]] = {}
    programmes["advanced_diploma_cosmetic_formulation"] = programme(
        name="Advanced Diploma in Cosmetic Formulation Science", code="MU003", minimum_credits=120, level7=120,
        minimum_years=1, maximum_years=2, required=cosmetic_codes, rules=[], progression=[
            {"type":"failed_course_count","label":"Do not fail more than one course in the year","threshold":2},
            {"type":"repeat_failure","label":"No course failed more than once","maximum_failures":1},
            {"type":"maximum_years","label":"Complete within two years","maximum":2},
        ], awards=cosmetic_award, page=42, route_type="advanced_diploma",
        progression_notes=["The in-service training course must be completed and recorded."],
    )

    def add_comm(key: str, name: str, code: str, discipline_codes: list[str], second_group: list[str], fundamentals: bool) -> None:
        rules = comm_common_rules + direct_rules(discipline_codes,key)
        max_years = 6 if fundamentals else 5
        if fundamentals:
            rules = [course_rule(["HSE1001F","HSE1001S"],"Fundamentals of Health Sciences","fundamentals_course")] + rules
        progression = comm_progress_base[:-1] + [
            {"type":"failed_courses_by_group","label":"Second-semester first-year failure threshold","groups":[{"label":"Second semester professional courses","course_codes":second_group,"threshold":2}]},
            {"type":"maximum_years","label":"Ordinary maximum registration period","maximum":max_years},
        ]
        if fundamentals:
            progression.insert(0,{"type":"failed_any","label":"Fundamentals course must be passed","course_codes":["HSE1001F","HSE1001S"]})
        programmes[key] = programme(name=name,code=code,minimum_credits=480,level7=120,level8=96,minimum_years=5 if fundamentals else 4,maximum_years=max_years,required=[],rules=rules,progression=progression,awards=hrs_award,page=43,route_type="fundamentals" if fundamentals else "structured",admission_notes=["Professional-programme selection and capacity remain Faculty decisions."],progression_notes=["Clinical course progression can depend on subcomponents and placement performance not visible on an academic transcript."],award_notes=["Distinction requires an overall programme average of 75%." ])

    add_comm("bsc_audiology","BSc Audiology","MB011",aud_codes,aud_second,False)
    add_comm("bsc_audiology_fundamentals","BSc Audiology — Fundamentals of Health Sciences route","MB019",aud_codes,aud_second,True)
    add_comm("bsc_speech_language_pathology","BSc Speech-Language Pathology","MB010",slp_codes,slp_second,False)
    add_comm("bsc_speech_language_pathology_fundamentals","BSc Speech-Language Pathology — Fundamentals route","MB018",slp_codes,slp_second,True)

    def add_hrs(key: str, name: str, code: str, base_rules: list[dict[str,Any]], fundamentals: bool, page: int, first_year_groups: list[dict[str,Any]], *, level7: int = 120) -> None:
        rules = list(base_rules)
        max_years = 6 if fundamentals else 5
        if fundamentals:
            rules = [course_rule(["HSE1001F","HSE1001S"],"Fundamentals of Health Sciences","fundamentals_course")] + rules
        progression = list(hrs_progress) + [{"type":"failed_courses_by_group","label":"First-year semester failure threshold","groups":first_year_groups},{"type":"maximum_years","label":"Ordinary maximum registration period","maximum":max_years}]
        if fundamentals:
            progression.insert(0,{"type":"failed_any","label":"Fundamentals course must be passed","course_codes":["HSE1001F","HSE1001S"]})
        programmes[key] = programme(name=name,code=code,minimum_credits=480,level7=level7,level8=96,minimum_years=5 if fundamentals else 4,maximum_years=max_years,required=[],rules=rules,progression=progression,awards=hrs_award,page=page,route_type="fundamentals" if fundamentals else "structured",admission_notes=["Clinical placement and professional-programme admission remain Faculty decisions."],progression_notes=["All theoretical prerequisites and prior-year clinical requirements must be completed before progression where specified."],award_notes=["Distinction requires an overall programme average of 75%." ])

    ot_groups = [
        {"label":"Occupational Therapy first semester","course_codes":["PSY1004F","PSY1009F","PSY1006F","PPH1001F","HUB1019F","AHS1035F"],"threshold":2},
        {"label":"Occupational Therapy second semester","course_codes":["PSY1005S","PSY1010S","PSY1007S","PPH1002S","HUB1020S","AHS1032S"],"threshold":2},
    ]
    phys_groups = [
        {"label":"Physiotherapy first semester","course_codes":["PPH1001F","PSY1004F","PSY1009F","HUB1019F","HUB1022F","AHS1033F"],"threshold":2},
        {"label":"Physiotherapy second semester","course_codes":["PPH1002S","HUB1020S","HUB1023S","AHS1034S"],"threshold":2},
    ]
    # The printed OT curriculum totals 559 credits but its listed rows sum to 555
    # and only 112 credits are labelled level 7, while the general HEQSF note states
    # a 120-credit level-7 minimum. Surface the conflict rather than making the
    # published prescribed route mathematically impossible.
    ot_rules_with_conflict = ot_rules + [manual("Published Occupational Therapy credit reconciliation","ot_credit_conflict","The printed year totals and HEQSF level-7 minimum do not reconcile with the listed course rows. Faculty confirmation is required before a definitive graduation conclusion.",status="conflict")]
    add_hrs("bsc_occupational_therapy","BSc Occupational Therapy","MB003",ot_rules_with_conflict,False,56,ot_groups,level7=0)
    add_hrs("bsc_occupational_therapy_fundamentals","BSc Occupational Therapy — Fundamentals route","MB016",ot_rules_with_conflict,True,56,ot_groups,level7=0)
    add_hrs("bsc_physiotherapy","BSc Physiotherapy","MB004",phys_rules,False,59,phys_groups)
    add_hrs("bsc_physiotherapy_fundamentals","BSc Physiotherapy — Fundamentals route","MB017",phys_rules,True,59,phys_groups)

    programmes["mbchb"] = programme(name="Bachelor of Medicine and Bachelor of Surgery",code="MB014",minimum_credits=1214,level7=120,level8=96,minimum_years=6,maximum_years=7,required=[],rules=mbchb_rules,progression=mbchb_progress,awards=[],page=48,route_type="clinical",pathways=mbchb_pathways,pathway_required=True,admission_notes=["Admission and progression through clinical placements are controlled by the Faculty and professional requirements."],progression_notes=["Students ordinarily complete all prescribed courses of an academic year before entering the next year; years 4–6 use modular clinical blocks."],award_notes=["Award calculations differ by first-registration cohort." ])
    mb_fund_rules = [course_rule(["HSE1001F","HSE1001S"],"Fundamentals of Health Sciences","fundamentals_course")] + mbchb_rules
    mb_fund_progress = [{"type":"failed_any","label":"Fundamentals course must be passed","course_codes":["HSE1001F","HSE1001S"]}] + [dict(r, maximum=8) if r.get("type")=="maximum_years" else r for r in mbchb_progress]
    programmes["mbchb_fundamentals"] = programme(name="MBChB — Fundamentals of Health Sciences route",code="MB020",minimum_credits=1274,level7=120,level8=96,minimum_years=7,maximum_years=8,required=[],rules=mb_fund_rules,progression=mb_fund_progress,awards=[],page=62,route_type="fundamentals_clinical",pathways=mbchb_pathways,pathway_required=True,admission_notes=["Placement in the Fundamentals route is a Faculty decision."],progression_notes=["The Fundamentals course must be passed before progression into the standard MBChB curriculum."],award_notes=["Award calculations differ by first-registration cohort." ])

    programmes["bsc_medicine"] = programme(name="BSc Medicine",code="MB001",minimum_credits=360,level7=120,minimum_years=1,maximum_years=1,required=[],rules=bscmed_rules,progression=[{"type":"maximum_years","label":"Complete the BSc Medicine route within one year","maximum":1}],awards=[{"name":"Degree with distinction","curriculum_rules":[weighted_average("Cumulative BSc Medicine GPA","bscmed_gpa",75)]}],page=55,route_type="credit_recognition",admission_notes=["This route is available to eligible UCT MBChB students and admission is competitive."],progression_notes=["Only approved courses and credits can be recognised toward the qualification."],award_notes=["Distinction requires a cumulative GPA of at least 75%." ])
    programmes["higher_certificate_disability_practice"] = programme(name="Higher Certificate in Disability Practice",code="MU002",minimum_credits=120,level7=0,minimum_years=1,maximum_years=2,required=[],rules=disability_rules,progression=[{"type":"failed_course_count","label":"First-year course failure threshold","threshold":2},{"type":"repeat_failure","label":"No course failed more than once","maximum_failures":1},{"type":"maximum_years","label":"Complete within two years","maximum":2}],awards=[],page=64,route_type="higher_certificate",admission_notes=["Practice-learning and admission requirements may require current programme confirmation." ])
    programmes["nmfc_medical_training"] = programme(name="Nelson Mandela Fidel Castro Medical Training Programme",code="MZ010",minimum_credits=281,level7=0,level8=96,minimum_years=2,maximum_years=3,required=[],rules=nmfc_rules,progression=[{"type":"failed_any","label":"All first-semester courses must be passed before progression","course_codes":["AAE4003W","MDN4017W","PED4017W","OBS4006W","PRY4001W"]},{"type":"repeat_failure","label":"No repeated course failure","maximum_failures":1}],awards=[],page=65,route_type="restricted_collaboration",availability="restricted",availability_note="Restricted collaboration route for students designated under the NMFC programme.",admission_notes=["National Department of Health and partner-institution rules govern admission and final qualification." ])

    # Preserve a closed scoped course universe. BSc Medicine needs all recognised options.
    programmes["bsc_medicine"]["support_course_codes"] = bscmed_recognised

    data = {
        "catalogue_version":"2026.1-health", "source":PDF_NAME,
        "programmes":programmes, "majors":{}, "forbidden_major_combinations":[], "cross_credit_exclusions":[],
    }
    OUT.joinpath("courses.json").write_text(json.dumps(sorted(courses.values(),key=lambda row:row["code"]),indent=2,ensure_ascii=False)+"\n")
    OUT.joinpath("degree_requirements.json").write_text(json.dumps(data,indent=2,ensure_ascii=False)+"\n")
    extraction = OUT / "source_extraction"; extraction.mkdir(exist_ok=True)
    extraction.joinpath("course_descriptions.json").write_text(json.dumps(sorted(courses.values(),key=lambda row:row["code"]),indent=2,ensure_ascii=False)+"\n")
    extraction.joinpath("equivalent_course_map.json").write_text(json.dumps(aliases,indent=2,ensure_ascii=False)+"\n")
    print(f"Wrote {len(courses)} course facts and {len(programmes)} Health Sciences programme routes to {OUT}")


if __name__ == "__main__":
    main()
