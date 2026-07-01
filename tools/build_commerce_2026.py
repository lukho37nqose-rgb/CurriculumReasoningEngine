#!/usr/bin/env python3
"""Build the 2026 UCT Commerce undergraduate catalogue.

Commerce is represented as programme-specific prescribed curricula rather than
as a faculty-wide elective catalogue.  Each BCom/BBusSci specialisation and its
standard, augmented or extended route is a separate reasoning scope.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "uct_commerce"
TEXT_PATH = Path("/mnt/data/commerce2026.txt")
PDF_NAME = "2026 Faculty of Commerce Undergraduate Handbook"

PREFIX_DEPARTMENT = {
    "ACC": "College of Accounting", "BUS": "School of Management Studies",
    "DOC": "Education Development Unit", "ECO": "School of Economics",
    "FTX": "Finance and Tax", "GPP": "Nelson Mandela School of Public Governance",
    "GSB": "Graduate School of Business", "INF": "Information Systems",
    "STA": "Statistical Sciences", "CML": "Commercial Law", "CSC": "Computer Science",
    "EGS": "Environmental and Geographical Science", "END": "Engineering and the Built Environment",
    "GEO": "Geological Sciences", "MAM": "Mathematics and Applied Mathematics",
    "PHI": "Philosophy", "POL": "Political Studies", "PSY": "Psychology",
    "PVL": "Private Law", "PBL": "Public Law", "SLL": "Languages and Literatures",
    "REL": "Religious Studies",
}

WORD_NUMBERS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8,
}

SUBSTITUTIONS: dict[str, list[list[str]]] = {
    "ACC1021F": [["ACC1006F"], ["ACC1020H"]],
    "ACC1022Z": [["ACC1011S"], ["ACC1012S"], ["ACC1020H"]],
    "ACC3020W": [["ACC3009W"]],
    "BUS1036F": [["ACC1015F"], ["ACC1015S"], ["REL1012F"], ["REL1013H"], ["PHI1025F"], ["PHI1024F", "POL1004F"]],
    "BUS1036S": [["ACC1015F"], ["ACC1015S"], ["REL1012F"], ["REL1013H"], ["PHI1025F"], ["PHI1024F", "POL1004F"]],
    "BUS2010F": [["BUS2011F"]], "BUS2010S": [["BUS2011F"]],
    "BUS2033F": [["BUS2035S"]], "BUS2033S": [["BUS2035S"]],
    "FTX2020F": [["FTX2024F"], ["FTX2024S"]],
    "INF1002F": [["CSC1015F"], ["CSC1015S"], ["CSC1010H"]],
    "INF1002S": [["CSC1015F"], ["CSC1015S"], ["CSC1010H"]],
    "INF1003F": [["CSC1016S"], ["CSC1011H"]],
    "INF2003F": [["CSC1016S"]], "INF2007F": [["CSC2001F"]], "INF2010S": [["CSC2002S"]],
    "STA1000F": [["STA1006S"], ["STA1007S"], ["STA1106H"], ["STA1100S"]],
    "STA1000S": [["STA1006S"], ["STA1007S"], ["STA1106H"], ["STA1100S"]],
    "STA1006S": [["STA1106H"]],
    "STA2020F": [["STA2005S"], ["STA2007F"], ["STA2007H"], ["STA2007S"]],
    "STA2020S": [["STA2005S"], ["STA2007F"], ["STA2007H"], ["STA2007S"]],
    "STA2030S": [["STA2004F"]],
    "MAM1000W": [["MAM1004F", "MAM1008S"], ["MAM1020F", "MAM1021S"], ["MAM1031F", "MAM1032S"], ["MAM1005H", "MAM1006H"]],
    "MAM1031F": [["MAM1005H"]], "MAM1032S": [["MAM1006H"]],
    "MAM1010F": [["MAM1005H"], ["MAM1020F"], ["MAM1031F"]],
    "MAM1012S": [["MAM1006H"], ["MAM1021S"]],
    "PHI1010S": [["PHI2037F"]],
    "POL1005S": [["POL2034S"], ["POL2039F"]],
}


def prefix(code: str) -> str:
    match = re.match(r"[A-Z]+", code)
    return match.group(0) if match else ""


def offered_from_code(code: str) -> list[str]:
    suffix = re.sub(r"^[A-Z]+\d{4}", "", code)
    return {
        "F": ["First semester"], "S": ["Second semester"], "W": ["Whole year"],
        "H": ["Half course over whole year"], "Z": ["Non-standard period"],
        "P": ["Summer term"], "U": ["Summer term"], "L": ["Winter term"],
        "Q": ["Online first semester"], "R": ["Online second semester"],
    }.get(suffix, [])


def expand_code(raw: str) -> list[str]:
    raw = raw.strip().upper().replace(" ", "")
    match = re.fullmatch(r"([A-Z]{3}\d{4})([A-Z])(?:/([A-Z]))+", raw)
    if not match:
        return [raw]
    stem = match.group(1)
    suffixes = re.findall(r"(?:^|/)([A-Z])", raw[len(stem):])
    return [stem + suffix for suffix in suffixes]


def source(page: int, section: str = "Programmes of Study") -> dict[str, Any]:
    return {"document": PDF_NAME, "page": page, "section": section}


def course_rule(codes: Iterable[str], label: str, rule_id: str, **extra: Any) -> dict[str, Any]:
    codes = list(dict.fromkeys(codes))
    row: dict[str, Any] = {"type": "course", "id": rule_id, "label": label, "course_codes": codes}
    row.update(extra)
    return row


def all_courses(codes: Iterable[str], label: str, rule_id: str, **extra: Any) -> dict[str, Any]:
    row: dict[str, Any] = {"type": "all_courses", "id": rule_id, "label": label, "course_codes": list(dict.fromkeys(codes))}
    row.update(extra)
    return row


def all_of(children: list[dict[str, Any]], label: str, rule_id: str, **extra: Any) -> dict[str, Any]:
    row: dict[str, Any] = {"type": "all_of", "id": rule_id, "label": label, "children": children}
    row.update(extra)
    return row


def any_of(children: list[dict[str, Any]], label: str, rule_id: str, **extra: Any) -> dict[str, Any]:
    row: dict[str, Any] = {"type": "any_of", "id": rule_id, "label": label, "children": children}
    row.update(extra)
    return row


def choose(codes: Iterable[str], required: int, label: str, rule_id: str, **extra: Any) -> dict[str, Any]:
    row: dict[str, Any] = {"type": "choose_n", "id": rule_id, "label": label,
                           "course_codes": list(dict.fromkeys(codes)), "required": required}
    row.update(extra)
    return row


def manual(label: str, rule_id: str, note: str, status: str = "unverified", blocking: bool = True) -> dict[str, Any]:
    return {"type": "manual", "id": rule_id, "label": label, "note": note,
            "status": status, "blocking": blocking, "assumed_complete": True}


def parse_course_descriptions(text: str) -> dict[str, dict[str, Any]]:
    heading = re.compile(r"(?m)^\s*([A-Z]{3}\d{4}[A-Z](?:/[A-Z])*)\s+([^\n]+?)\s*$")
    matches = list(heading.finditer(text))
    records: dict[str, dict[str, Any]] = {}
    for index, match in enumerate(matches):
        raw_code = match.group(1)
        title = re.sub(r"\s+", " ", match.group(2)).strip(" .")
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        segment = text[match.end():end]
        credit = re.search(r"(\d+)\s+NQF credits? at NQF level\s+(\d+)", segment[:2200], re.I)
        if not credit:
            continue
        credits, level = int(credit.group(1)), int(credit.group(2))
        if level not in {5, 6, 7, 8}:
            continue
        page = text.count("\f", 0, match.start()) + 1
        entry = re.search(r"Course entry requirements:\s*(.*?)(?:\n\s*Co-requisites?:|\n\s*Course outline:|\n\s*DP requirements:|\Z)", segment[:6000], re.S | re.I)
        entry_text = re.sub(r"\s+", " ", entry.group(1)).strip() if entry else ""
        prereqs: list[str] = []
        prereq_verified = False
        if entry_text and re.fullmatch(r"None\.?|Admission to (?:the )?degree\.?.*", entry_text, re.I):
            prereq_verified = True
        elif entry_text:
            found: list[str] = []
            for token in re.findall(r"\b[A-Z]{3}\d{4}[A-Z](?:/[A-Z])?\b", entry_text):
                found.extend(expand_code(token))
            unsafe = re.search(r"\bor\b|permission|average|minimum|at least|concurrent|equivalent|registration for|%|admission", entry_text, re.I)
            if found and not unsafe:
                prereqs = sorted(set(found)); prereq_verified = True
        elif level == 5:
            prereq_verified = True
        coreq_match = re.search(r"Co-requisites?:\s*(.*?)(?:\n\s*Course outline:|\n\s*DP requirements:|\Z)", segment[:6000], re.S | re.I)
        co_reqs: list[str] = []
        if coreq_match:
            coreq_text = re.sub(r"\s+", " ", coreq_match.group(1)).strip()
            if not re.fullmatch(r"None\.?", coreq_text, re.I):
                for token in re.findall(r"\b[A-Z]{3}\d{4}[A-Z](?:/[A-Z])?\b", coreq_text):
                    co_reqs.extend(expand_code(token))
        outline = re.search(r"Course outline:\s*(.*?)(?:\n\s*Lecture times:|\n\s*DP requirements:|\n\s*Assessment:|\Z)", segment[:7000], re.S | re.I)
        description = re.sub(r"\s+", " ", outline.group(1)).strip()[:900] if outline else ""
        not_offered = bool(re.search(r"not offered in 2026", title + " " + segment[:700], re.I))
        for code in expand_code(raw_code):
            candidate = {
                "code": code, "name": title, "credits": credits, "nqf_level": level,
                "prerequisites": prereqs, "prerequisites_verified": prereq_verified,
                "co_requisites": sorted(set(co_reqs)), "offered": [] if not_offered else offered_from_code(code),
                "offering_verified": True, "department": PREFIX_DEPARTMENT.get(prefix(code), prefix(code)),
                "description": description, "verification_status": "verified",
                "source": source(page, "Course outline"), "general_elective": False,
                "counts_towards_general_degree": True, "counts_as_humanities": False,
                "counts_as_science": False, "counts_towards_course_equivalents": True,
                "credit_bearing": credits > 0,
                "recognition_note": "Recognition is controlled by the selected Commerce programme curriculum.",
            }
            previous = records.get(code)
            if previous is None or (description and not previous.get("description")):
                records[code] = candidate
    return records


SPECIALISATIONS_BBUS = [
    ("BUS01", "Actuarial Science"), ("BUS09", "Actuarial Science specialising in Quantitative Finance"),
    ("STA13", "Statistics and Data Science"), ("FTX05", "Finance"),
    ("FTX04", "Finance with Accounting"), ("CSC05", "Computer Science"),
    ("INF01", "Information Systems"), ("ECO01", "Economics"),
    ("ECO03", "Economics with Law"), ("BUS07", "Marketing"),
    ("BUS28", "Industrial and Organisational Psychology"),
]
SPECIALISATIONS_BCOM = [
    ("BUS01", "Actuarial Science"), ("BUS09", "Actuarial Science specialising in Quantitative Finance"),
    ("ACC08", "Financial Accounting: General Accounting"),
    ("ACC04", "Financial Accounting: Chartered Accountant"),
    ("INF01", "Information Systems"), ("INF06", "Information Systems and Computer Science"),
    ("INF11", "Information Systems and Finance"),
    ("PHI03", "Philosophy, Politics and Economics"),
    ("ECO02", "Economics and Finance"), ("ECO04", "Economics and Statistics"),
    ("ECO03", "Economics with Law"), ("BUS06", "Management Studies"),
]


def route_specs() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = [
        {"code": "CU020BUS01", "name": "Advanced Diploma in Actuarial Science", "family": "advanced", "mode": "standard", "page": 20},
        {"code": "CU021GSB48", "qualification_codes": ["CU021GSB48", "CU022GSB48", "CU023GSB48"], "name": "Advanced Diploma in Management Development", "family": "advanced", "mode": "standard", "page": 21},
        {"code": "CU017ACC01", "name": "Advanced Diploma in Accounting", "family": "advanced", "mode": "standard", "page": 23},
    ]
    bb_prefixes = {
        "standard": ("CB003", "CB004", 4),
        "augmented": ("CB025", "CB024", 4),
        "extended": ("CB018", "CB015", 5),
    }
    for mode, (act_prefix, other_prefix, minimum_years) in bb_prefixes.items():
        for suffix, title in SPECIALISATIONS_BBUS:
            if mode == "extended" and suffix == "CSC05":
                continue
            prefix_code = act_prefix if suffix in {"BUS01", "BUS09"} else other_prefix
            rows.append({"code": prefix_code + suffix, "name": f"Bachelor of Business Science in {title}",
                         "family": "bbussci", "mode": mode, "minimum_years": minimum_years})
    bcom_prefixes = {
        "standard": ("CB019", "CB001", 3),
        "augmented": ("CB026", "CB023", 3),
        "extended": ("CB020", "CB011", 4),
    }
    for mode, (act_prefix, other_prefix, minimum_years) in bcom_prefixes.items():
        for suffix, title in SPECIALISATIONS_BCOM:
            prefix_code = act_prefix if suffix in {"BUS01", "BUS09"} else other_prefix
            if suffix in {"BUS01", "BUS09"}:
                name = f"Bachelor of Commerce in {title}"
            else:
                name = f"Bachelor of Commerce specialising in {title}"
            rows.append({"code": prefix_code + suffix, "name": name,
                         "family": "bcom", "mode": mode, "minimum_years": minimum_years})
    return rows


ROW_RE = re.compile(r"^\s*([A-Z]{3}\d{4}[A-Z](?:/[A-Z])*)\s+(.+?)\s+(\d+)(?:-\d+)?\+?\s+([5-8])\s*$")
YEAR_RE = re.compile(r"^(First|Second|Third|Fourth|Fifth) Year (?:Core )?Modules", re.I)


def normalise_line(line: str) -> str:
    return re.sub(r"\s+", " ", line).strip()


def parse_row(line: str, page: int) -> dict[str, Any] | None:
    clean = normalise_line(line.replace("…", "."))
    if not re.match(r"^[A-Z]{3}\d{4}", clean):
        return None
    match = ROW_RE.match(clean)
    if not match:
        # Strip dot leaders before retrying.
        clean2 = re.sub(r"\.{2,}", " ", clean)
        clean2 = re.sub(r"\s+", " ", clean2)
        match = ROW_RE.match(clean2)
    if not match:
        return None
    raw_code, title, credits, level = match.groups()
    title = re.sub(r"\.{2,}", " ", title).strip(" .")
    return {"raw_code": raw_code, "codes": expand_code(raw_code), "name": title,
            "credits": int(credits), "level": int(level), "page": page}


def positions_for_specs(text: str, specs: list[dict[str, Any]]) -> list[tuple[int, dict[str, Any]]]:
    """Locate the actual programme heading, not its table-of-contents or rule reference.

    Commerce programme codes recur in the contents, faculty rules and curriculum
    headings.  A genuine programme heading is followed shortly by either a
    prescribed-curriculum heading or a first-year curriculum table.
    """
    positions: list[tuple[int, dict[str, Any]]] = []
    for spec in specs:
        code = spec["code"]
        candidates = [m.start() for m in re.finditer(r"\[" + re.escape(code) + r"\]", text)]
        if not candidates:
            # Some rules mention codes without brackets, while the actual programme
            # heading still normally uses brackets. Keep a conservative fallback.
            candidates = [m.start() for m in re.finditer(r"\b" + re.escape(code) + r"\b", text)]
        ranked: list[tuple[int, int]] = []
        for candidate in candidates:
            page = text.count("\f", 0, candidate) + 1
            after = text[candidate:candidate + 3500]
            before = text[max(0, candidate - 260):candidate]
            has_curriculum = bool(re.search(r"First Year (?:Core )?Modules|Prescribed curriculum", after, re.I))
            heading_context = bool(re.search(r"Bachelor|Advanced Diploma", before + after[:240], re.I))
            if has_curriculum and heading_context:
                # Prefer the earliest genuine curriculum heading. Later repeats are
                # usually prescribed-curriculum labels inside the same programme.
                ranked.append((page, candidate))
        if not ranked:
            raise RuntimeError(f"Could not locate programme curriculum heading for {code}")
        ranked.sort(key=lambda item: (item[0], item[1]))
        positions.append((ranked[0][1], spec))
    return sorted(positions, key=lambda item: item[0])


def split_year_blocks(segment: str, start_page: int) -> list[tuple[str, list[tuple[int, str]]]]:
    lines = segment.splitlines()
    blocks: list[tuple[str, list[tuple[int, str]]]] = []
    current = "Programme"
    current_rows: list[tuple[int, str]] = []
    page = start_page
    for line in lines:
        if "\f" in line:
            page += line.count("\f")
            line = line.replace("\f", "")
        clean = normalise_line(line)
        year_match = YEAR_RE.match(clean)
        if year_match:
            if current_rows:
                blocks.append((current, current_rows))
            current = year_match.group(1).title() + " Year"
            current_rows = []
            continue
        current_rows.append((page, line))
    if current_rows:
        blocks.append((current, current_rows))
    return blocks


def marker_number(text: str, default: int = 1) -> int:
    match = re.search(r"\b(\d+)\b", text)
    if match:
        return int(match.group(1))
    for word, value in WORD_NUMBERS.items():
        if re.search(rf"\b{word}\b", text, re.I):
            return value
    return default


def row_rule(row: dict[str, Any], route_code: str, index: int) -> dict[str, Any]:
    codes = row["codes"]
    children: list[dict[str, Any]] = []
    for code in codes:
        alternatives = SUBSTITUTIONS.get(code, [])
        if alternatives:
            branches = [course_rule([code], f"Complete {code}", f"{route_code}_{index}_{code.lower()}")]
            for alt_index, alt_codes in enumerate(alternatives):
                if len(alt_codes) == 1:
                    branches.append(course_rule(alt_codes, f"Complete recognised substitute {alt_codes[0]}", f"{route_code}_{index}_{code.lower()}_sub{alt_index}"))
                else:
                    branches.append(all_courses(alt_codes, "Complete recognised substitute sequence", f"{route_code}_{index}_{code.lower()}_sub{alt_index}"))
            children.append(any_of(branches, f"{row['name']} or recognised equivalent", f"{route_code}_{index}_{code.lower()}_equiv"))
        else:
            children.append(course_rule([code], f"Complete {row['name']} ({code})", f"{route_code}_{index}_{code.lower()}"))
    if len(children) == 1:
        return children[0]
    return any_of(children, f"Complete {row['name']}", f"{route_code}_{index}_variant")


def parse_block(block_name: str, block_lines: list[tuple[int, str]], route_code: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    # Degree year blocks end at their final printed total.  Truncating there
    # prevents explanatory notes and later departmental course descriptions
    # from being misread as curriculum electives.
    if block_name != "Programme":
        normalised = [normalise_line(line) for _, line in block_lines]
        totals = [
            index for index, line in enumerate(normalised)
            if re.match(r"^Total credits(?:\s+(?:per year|for (?:the )?year|for the degree|of NQF level))?", line, re.I)
        ]
        if totals:
            block_lines = block_lines[: max(totals) + 1]

    rules: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []
    warnings: list[str] = []
    for line_index, (page, line) in enumerate(block_lines):
        row = parse_row(line, page)
        if row:
            row["line_index"] = line_index
            rows.append(row)

    consumed: set[int] = set()
    represented_lines: set[int] = set()
    explicit_pool_lines: set[int] = set()
    clean_lines = [normalise_line(line) for _, line in block_lines]

    # Named option branches (especially statistics streams).
    option_markers: list[tuple[int, str]] = []
    for index, clean in enumerate(clean_lines):
        if re.search(r"(?:Mathematical Statistics|Applied Statistics) Option", clean, re.I):
            option_markers.append((index, clean))
    if len(option_markers) >= 2:
        branches: list[dict[str, Any]] = []
        for marker_index, (start, label) in enumerate(option_markers):
            end = option_markers[marker_index + 1][0] if marker_index + 1 < len(option_markers) else len(clean_lines)
            group = [row for row in rows if start < row["line_index"] < end]
            if marker_index + 1 == len(option_markers):
                # Stop the final option at a Plus/Total marker.
                stops = [i for i in range(start + 1, len(clean_lines)) if re.search(r"^(Plus|Total)", clean_lines[i], re.I)]
                if stops:
                    group = [row for row in group if row["line_index"] < min(stops)]
            if group:
                consumed.update(row["line_index"] for row in group)
                branch_rules = [row_rule(row, route_code, row["line_index"]) for row in group]
                branches.append(all_of(branch_rules, label.strip(" :."), f"{route_code}_{block_name}_option_{marker_index}"))
        if len(branches) >= 2:
            rules.append(any_of(branches, f"{block_name}: complete one statistics option", f"{route_code}_{block_name}_statistics_option"))

    # Explicit 'Plus N courses from' and final-level elective lists.
    for index, clean in enumerate(clean_lines):
        explicit_pool = None
        if re.search(r"\bfrom\b|students are required to take", clean, re.I):
            explicit_pool = re.search(r"(?:Plus,?|Take|.*students are required to take)\s+(\d+|one|two|three|four)\s+(?:other\s+)?(?:NQF[^:]*\s+)?(?:courses?|options?|electives?)\s*(?:from(?: the list below)?)?\s*(?::|in)?", clean, re.I)
        if not explicit_pool:
            continue
        required = marker_number(explicit_pool.group(1), 0)
        if required <= 0:
            continue
        stop_candidates = [
            i for i in range(index + 1, len(clean_lines))
            if re.search(r"^(Total credits|First Year|Second Year|Third Year|Fourth Year|Fifth Year|Plus \d+|Plus one|Plus two|Plus three)", clean_lines[i], re.I)
        ]
        end = min(stop_candidates) if stop_candidates else len(clean_lines)
        explicit_pool_lines.update(range(index, end))
        pool_rows = [row for row in rows if index < row["line_index"] < end and row["line_index"] not in consumed]
        generic_options = [
            clean_lines[i] for i in range(index + 1, end)
            if re.match(r"^(Any |OR NQF|NQF level|[123]000 level)", clean_lines[i], re.I)
        ]
        represented_lines.add(index)
        if pool_rows:
            consumed.update(row["line_index"] for row in pool_rows)
        if generic_options:
            levels = sorted({int(value) for value in re.findall(r"NQF(?: Level)?\s*([5-8])", " ".join([clean] + generic_options), re.I)})
            filters = {"nqf_levels": levels} if levels else {}
            rules.append({
                "type": "approved_credit_pool", "id": f"{route_code}_{block_name}_mixed_pool_{index}",
                "label": f"{block_name}: complete {required} courses from the mixed published/approved option pool",
                "required": required * 18, "allow_unlisted_transcript_courses": True,
                "transcript_filters": filters,
                "approval_note": "The published option pool mixes named courses with discipline/level categories. Individual selections require programme verification.",
                "verification_status": "unverified",
            })
            warnings.append(clean)
        elif pool_rows:
            rules.append(choose([code for row in pool_rows for code in row["codes"]], required,
                                f"{block_name}: choose {required} from the published option list",
                                f"{route_code}_{block_name}_pool_{index}"))

    # Simple OR-linked rows.
    row_by_line = {row["line_index"]: row for row in rows}
    available = [row for row in rows if row["line_index"] not in consumed]
    i = 0
    while i < len(available):
        group = [available[i]]
        j = i
        while j + 1 < len(available):
            between = clean_lines[available[j]["line_index"] + 1:available[j + 1]["line_index"]]
            if any(re.fullmatch(r"OR[ .]*", item, re.I) or re.search(r"\.\.OR\.", item, re.I) for item in between):
                group.append(available[j + 1]); j += 1
            else:
                break
        if len(group) > 1:
            consumed.update(row["line_index"] for row in group)
            branches = [row_rule(row, route_code, row["line_index"]) for row in group]
            rules.append(any_of(branches, f"{block_name}: complete one published alternative", f"{route_code}_{block_name}_or_{group[0]['line_index']}"))
            i = j + 1
        else:
            i += 1

    # Remaining rows are compulsory.
    remaining = [row for row in rows if row["line_index"] not in consumed]
    for row in remaining:
        rules.append(row_rule(row, route_code, row["line_index"]))

    # Mixed open alternatives printed on one line, e.g. "ECO2008S and one
    # level-6 course or two level-7 courses".
    for index, clean in enumerate(clean_lines):
        mixed_and = re.search(
            r"^Plus\s+([A-Z]{3}\d{4}[A-Z])\s+and\s+(\d+|one|two)\s+NQF(?: level)?\s*([5-8])\s+courses?\s+or\s+(\d+|one|two)\s+NQF(?: level)?\s*([5-8])\s+courses?",
            clean, re.I,
        )
        mixed_or = re.search(
            r"^Plus\s+([A-Z]{3}\d{4}[A-Z])\s+or\s+(\d+|one|two)\s+NQF(?: level)?\s*([5-8])\s+courses?",
            clean, re.I,
        )
        if mixed_and:
            code, count1, level1, count2, level2 = mixed_and.groups()
            n1, n2 = marker_number(count1), marker_number(count2)
            branch1 = all_of([
                course_rule([code.upper()], f"Complete {code.upper()}", f"{route_code}_{block_name}_mixed_{index}_course"),
                {"type": "approved_credit_pool", "id": f"{route_code}_{block_name}_mixed_{index}_a", "label": f"Complete {n1} approved NQF level {level1} course(s)", "required": n1 * 18, "allow_unlisted_transcript_courses": True, "transcript_filters": {"nqf_levels": [int(level1)]}, "approval_note": "Individual elective approval is not visible on the transcript.", "verification_status": "unverified"},
            ], f"{code.upper()} plus approved electives", f"{route_code}_{block_name}_mixed_{index}_branch1")
            branch2 = {"type": "approved_credit_pool", "id": f"{route_code}_{block_name}_mixed_{index}_b", "label": f"Complete {n2} approved NQF level {level2} course(s)", "required": n2 * 18, "allow_unlisted_transcript_courses": True, "transcript_filters": {"nqf_levels": [int(level2)]}, "approval_note": "Individual elective approval is not visible on the transcript.", "verification_status": "unverified"}
            rules.append(any_of([branch1, branch2], f"{block_name}: complete one published elective alternative", f"{route_code}_{block_name}_mixed_{index}"))
            represented_lines.add(index)
        elif mixed_or:
            code, count, level = mixed_or.groups()
            n = marker_number(count)
            rules.append(any_of([
                course_rule([code.upper()], f"Complete {code.upper()}", f"{route_code}_{block_name}_mixed_or_{index}_course"),
                {"type": "approved_credit_pool", "id": f"{route_code}_{block_name}_mixed_or_{index}_pool", "label": f"Complete {n} approved NQF level {level} course(s)", "required": n * 18, "allow_unlisted_transcript_courses": True, "transcript_filters": {"nqf_levels": [int(level)]}, "approval_note": "Individual elective approval is not visible on the transcript.", "verification_status": "unverified"},
            ], f"{block_name}: complete one published elective alternative", f"{route_code}_{block_name}_mixed_or_{index}"))
            represented_lines.add(index)

    # Open/generic elective requirements.
    for index, clean in enumerate(clean_lines):
        if index in explicit_pool_lines or index in represented_lines:
            continue
        if "from:" in clean.lower() or "from the list" in clean.lower():
            continue
        if re.match(r"^(Total credits|Notes?|Additional information|Assessment|Readmission|Distinction|Graduation)", clean, re.I):
            continue
        if re.fullmatch(r"Elective Courses?:?\s*\.*", clean, re.I):
            continue
        if not re.search(r"elective|approved course|other NQF|other ECO|NQF level \d .*course|NQF \d .*course|2000 level course", clean, re.I):
            continue
        if re.search(r"suggested|recommended|not available|option to choose|may choose|may be taken|register for this elective|course consists", clean, re.I):
            continue
        # A curriculum requirement normally appears as a table-style line with
        # dot leaders/credit information or begins with an explicit quantifier.
        if not (".." in clean or re.match(r"^(Any|One|Two|Three|Four|Plus)", clean, re.I)):
            continue
        context = clean
        if index + 1 < len(clean_lines) and re.search(r"credits|minimum", clean_lines[index + 1], re.I):
            context += " " + clean_lines[index + 1]
        count_match = re.search(r"^(?:Plus\s+)?(\d+|one|two|three|four)\b", clean, re.I)
        required_count = marker_number(count_match.group(1), 1) if count_match else 1
        total_match = re.search(r"totalling\s+(?:a\s+)?(?:minimum\s+of\s+)?(\d+)\s+credits", context, re.I)
        credit_match = re.search(r"(?:\.{2,}|\s)(\d+)\+?\s+([5-8])\s*$", clean)
        level_match = re.search(r"NQF(?: level)?\s*([5-8])|([123])000 level|first year level", clean, re.I)
        nqf_level = 5 if re.search(r"first year level", clean, re.I) else (int(next(v for v in level_match.groups() if v)) if level_match else 0)
        if total_match:
            required_credits = int(total_match.group(1))
        elif credit_match:
            printed_credits = int(credit_match.group(1))
            nqf_level = int(credit_match.group(2))
            required_credits = printed_credits * required_count if required_count > 1 and printed_credits <= 24 else printed_credits
        else:
            required_credits = required_count * 18
        prefixes: list[str] = []
        if re.search(r"\bECO\b", clean): prefixes = ["ECO"]
        if re.search(r"\bPOL\b", clean): prefixes = ["POL"]
        filters: dict[str, Any] = {}
        if nqf_level: filters["nqf_levels"] = [nqf_level]
        if prefixes: filters["prefixes"] = prefixes
        represented_lines.add(index)
        rules.append({
            "type": "approved_credit_pool", "id": f"{route_code}_{block_name}_open_{index}",
            "label": f"{block_name}: {clean.strip(' .')}", "required": required_credits,
            "allow_unlisted_transcript_courses": True, "transcript_filters": filters,
            "approval_note": "The programme permits an approved elective, but the static handbook cannot verify the student's individual approval or current timetable fit.",
            "verification_status": "unverified",
        })

    unresolved = [(index, clean) for index, clean in enumerate(clean_lines) if re.search(r"\bOR\b|Plus|Elective Courses|approved courses|^Any ", clean, re.I)]
    represented_text = " ".join(str(rule) for rule in rules)
    for line_index, line in unresolved:
        if line_index in represented_lines:
            continue
        if re.search(r"not offered|option to choose|or equivalent|supplementary", line, re.I):
            continue
        codes_in_line = re.findall(r"\b[A-Z]{3}\d{4}[A-Z](?:/[A-Z])?\b", line)
        if codes_in_line and all(any(code in represented_text for code in expand_code(raw)) for raw in codes_in_line):
            continue
        if re.match(r"^OR[ .]*$", line, re.I):
            continue
        if re.search(r"^Any |Plus .*NQF|approved courses", line, re.I):
            warnings.append(line)
    return rules, rows, warnings


def advanced_curriculum(spec: dict[str, Any], segment: str, start_page: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    """Build the three advanced-diploma curricula from their closed tables."""
    rows: list[dict[str, Any]] = []
    page = start_page
    for line in segment.splitlines():
        if "\f" in line:
            page += line.count("\f")
            line = line.replace("\f", "")
        row = parse_row(line, page)
        if row:
            rows.append(row)
    code = spec["code"]
    rules: list[dict[str, Any]] = []
    warnings: list[str] = []
    if code == "CU020BUS01":
        prescribed_codes = {"STA3041F", "STA3045F", "STA3047S", "STA3048S", "BUS3018F", "BUS3024S"}
        prescribed = [row for row in rows if any(c in prescribed_codes for c in row["codes"])]
        electives = [row for row in rows if not any(c in prescribed_codes for c in row["codes"])]
        for row in prescribed:
            rules.append(row_rule(row, code, row["page"] * 100 + len(rules)))
        rules.append(choose(
            [c for row in electives for c in row["codes"]], 2,
            "Complete two published elective courses", f"{code}_electives",
        ))
        warnings.append("The distinction paragraph refers to five prescribed courses while the curriculum table lists six; the award calculation uses the best four of the six listed courses and is flagged for confirmation.")
    elif code == "CU021GSB48":
        for index, row in enumerate(rows):
            rules.append(row_rule(row, code, index))
    else:
        for index, row in enumerate(rows):
            rules.append(row_rule(row, code, index))
    return rules, rows, warnings


def add_table_fact(courses: dict[str, dict[str, Any]], row: dict[str, Any]) -> None:
    for code in row["codes"]:
        if code in courses:
            continue
        courses[code] = {
            "code": code, "name": row["name"], "credits": row["credits"], "nqf_level": row["level"],
            "prerequisites": [], "prerequisites_verified": row["level"] == 5,
            "co_requisites": [], "offered": offered_from_code(code), "offering_verified": True,
            "department": PREFIX_DEPARTMENT.get(prefix(code), prefix(code)), "description": "",
            "verification_status": "verified", "source": source(row["page"], "Programme curriculum table"),
            "general_elective": False, "counts_towards_general_degree": True,
            "counts_as_humanities": False, "counts_as_science": False,
            "counts_towards_course_equivalents": True, "credit_bearing": row["credits"] > 0,
            "recognition_note": "Course facts are verified from the selected programme curriculum table; detailed entry requirements may require confirmation.",
        }


def programme_progression(spec: dict[str, Any], curriculum_codes: set[str]) -> list[dict[str, Any]]:
    family, mode, code = spec["family"], spec["mode"], spec["code"]
    rules: list[dict[str, Any]] = []
    if family == "advanced":
        if code == "CU020BUS01":
            return [{"type": "annual_course_equivalents", "label": "Pass at least two courses in the first year", "minimum": 2},
                    {"type": "repeat_failure", "label": "No course may be failed more than once", "maximum_failures": 1},
                    {"type": "maximum_years", "label": "Complete within two years", "maximum": 2}]
        if code == "CU021GSB48":
            return [{"type": "failed_course_count", "label": "No more than three compulsory courses may be failed", "threshold": 4},
                    {"type": "repeat_failure", "label": "A failed compulsory course may be repeated only once", "maximum_failures": 1}]
        return [{"type": "repeat_failure", "label": "No programme course may be failed twice", "maximum_failures": 1}]

    rules.append({"type": "repeat_failure", "label": "No required course may be failed more than once", "maximum_failures": 1})
    rules.append({"type": "failed_course_equivalents", "label": "Annual failure load", "threshold": 5})
    if family == "bbussci":
        if mode == "extended":
            thresholds = {1: 3, 2: 7, 3: 13, 4: 19}; annual = 3
        else:
            thresholds = {1: 4, 2: 10, 3: 18}; annual = 4
        rules.append({"type": "cumulative_failed_course_equivalents", "label": "Fewer than seven failed semester-course equivalents over the degree", "threshold": 7})
    else:
        if mode == "extended":
            thresholds = {1: 3, 2: 6, 3: 10, 4: 15}; annual = 3
        else:
            thresholds = {1: 4, 2: 8, 3: 15}; annual = 4
    for year, minimum in thresholds.items():
        rules.append({"type": "course_equivalents_cumulative", "label": f"End of year {year} course-equivalent threshold", "year": year, "minimum": minimum})
    rules.append({"type": "annual_course_equivalents", "label": "Annual completed course-equivalent threshold", "minimum": annual})
    rules.append({"type": "maximum_years", "label": "Complete within the standard period unless Senate grants a concession", "maximum": spec["minimum_years"]})

    if code.endswith(("BUS01", "BUS09")):
        actuarial_first = [
            "MAM1031F", "MAM1032S", "MAM1005H", "MAM1006H", "STA1006S", "STA1106H",
            "ECO1010F", "ECO1010S", "ECO1110F", "ECO1110S", "ECO1011S", "ECO1111S",
            "ACC1006F", "ACC1106F", "ACC1011S", "ACC1111S",
        ]
        rules.append({"type": "failed_any", "label": "Actuarial first-year exclusion courses", "course_codes": actuarial_first})
    return rules


def degree_award_rules(spec: dict[str, Any], all_codes: list[str]) -> list[dict[str, Any]]:
    code, family = spec["code"], spec["family"]
    if family == "advanced":
        if code == "CU020BUS01":
            prescribed = ["STA3041F", "STA3045F", "STA3047S", "STA3048S", "BUS3018F", "BUS3024S"]
            return [{"name": "Diploma with distinction", "curriculum_rules": [{
                "type": "best_n_average", "id": "adv_actuarial_best4", "label": "Best four prescribed results",
                "course_codes": prescribed, "required": 4, "minimum_average": 75,
                "verification_status": "conflict",
            }]}]
        if code == "CU021GSB48":
            return [{"name": "Diploma with distinction", "curriculum_rules": [{
                "type": "weighted_average", "id": "adv_management_average", "label": "Coursework weighted average",
                "minimum_average": 75,
            }]}]
        return [{"name": "Diploma with distinction", "curriculum_rules": [
            {"type": "weighted_average", "id": "adv_accounting_average", "label": "Four professional-subject average", "course_codes": ["ACC3009W", "ACC3023W", "ACC3022W", "ACC3004W"], "minimum_average": 75},
            *[{"type": "minimum_mark", "id": f"adv_acc_min_{c.lower()}", "label": f"{c} minimum", "course_codes": [c], "minimum_mark": 60} for c in ["ACC3009W", "ACC3023W", "ACC3022W", "ACC3004W"]],
            {"type": "no_failures", "id": "adv_acc_first_attempt", "label": "Only first-attempt passes count", "course_codes": ["ACC3009W", "ACC3023W", "ACC3022W", "ACC3004W"]},
        ]}]

    level_weights = {"5": 1, "6": 1, "7": 2, "8": 2}
    degree_rules: list[dict[str, Any]] = [{
        "type": "first_attempt_weighted_average", "id": "commerce_degree_distinction",
        "label": "First-attempt programme average", "course_codes": all_codes,
        "minimum_average": 80, "level_weights": level_weights,
        "include_failed_as_zero": True,
    }]
    award: dict[str, Any] = {"name": "Degree with distinction", "curriculum_rules": degree_rules}
    if family == "bcom":
        degree_rules.append({"type": "no_failures", "id": "bcom_no_failures", "label": "No failed course attempts", "course_codes": all_codes})
        award["complete_within_years"] = spec["minimum_years"]
    rules = [award]

    suffix = code[-5:]
    if suffix == "FTX05":
        if family == "bbussci":
            rules.append({"name": "Finance subject distinction", "curriculum_rules": [
                {"type": "weighted_average", "id": "finance3", "label": "FTX3044F and FTX3045S average", "course_codes": ["FTX3044F", "FTX3045S"], "minimum_average": 75},
                {"type": "weighted_average", "id": "finance4", "label": "Final-year Finance average", "course_codes": ["FTX4056S", "FTX4057F", "FTX4087S"], "minimum_average": 75},
                *[{"type": "minimum_mark", "id": f"finance_min_{c.lower()}", "label": f"{c} minimum", "course_codes": [c], "minimum_mark": 70} for c in ["FTX3044F", "FTX3045S", "FTX4056S", "FTX4057F", "FTX4087S"]],
            ]})
        else:
            rules.append({"name": "Finance subject distinction", "curriculum_rules": [
                {"type": "weighted_average", "id": "bcom_finance2", "label": "Financial Management average", "course_codes": ["FTX2024F", "FTX2024S"], "minimum_average": 75},
                {"type": "weighted_average", "id": "bcom_finance3", "label": "Investment Management average", "course_codes": ["FTX3044F", "FTX3045S"], "minimum_average": 75},
            ]})
    elif suffix in {"ECO01", "ECO02", "ECO03", "ECO04"}:
        eco3000 = [c for c in all_codes if c.startswith("ECO3")]
        rules.append({"name": "Economics subject distinction", "curriculum_rules": [
            {"type": "best_n_average", "id": "economics_best3", "label": "ECO3020F plus two other third-year Economics courses", "course_codes": eco3000, "required": 3, "mandatory_course_codes": ["ECO3020F"], "minimum_average": 80, "minimum_mark_count": 2, "minimum_mark": 75},
        ]})
    elif suffix in {"INF01", "INF06", "INF11"}:
        final_inf = [c for c in all_codes if c.startswith("INF3") or c.startswith("INF4")]
        rules.append({"name": "Information Systems subject distinction", "curriculum_rules": [{"type": "weighted_average", "id": "is_final_average", "label": "Final-year Information Systems weighted average", "course_codes": final_inf, "minimum_average": 75}]})
    elif suffix == "BUS07":
        marketing = ["BUS4026W", "BUS4052H", "BUS4058F", "BUS3041F", "BUS3043S", "BUS3008W"]
        rules.append({"name": "Marketing subject distinction", "curriculum_rules": [
            {"type": "weighted_average", "id": "marketing_average", "label": "Marketing course weighted average", "course_codes": marketing, "minimum_average": 75},
            *[{"type": "minimum_mark", "id": f"marketing_min_{c.lower()}", "label": f"{c} minimum", "course_codes": [c], "minimum_mark": 70} for c in marketing],
        ]})
    elif suffix == "BUS28":
        rules.append({"name": "Industrial and Organisational Psychology subject distinction", "curriculum_rules": [
            {"type": "weighted_average", "id": "iop_average", "label": "BUS4006W and BUS4030H average", "course_codes": ["BUS4006W", "BUS4030H"], "minimum_average": 75},
            {"type": "minimum_mark", "id": "iop_course1", "label": "BUS4006W minimum", "course_codes": ["BUS4006W"], "minimum_mark": 70},
            {"type": "minimum_mark", "id": "iop_course2", "label": "BUS4030H minimum", "course_codes": ["BUS4030H"], "minimum_mark": 70},
            manual("Coursework and research-report component subminima", "iop_components", "The transcript does not expose component marks; both coursework and the research report require at least 70%.", blocking=True),
        ]})
    elif suffix in {"STA13"} or suffix == "ECO04":
        stats2 = [c for c in all_codes if c.startswith("STA2")]
        stats3 = [c for c in all_codes if c.startswith("STA3")]
        rules.append({"name": "Statistics subject distinction", "curriculum_rules": [
            {"type": "passed_mark_count", "id": "stats2_firsts", "label": "Two second-year Statistics firsts", "course_codes": stats2, "required": 2, "minimum_mark": 75},
            {"type": "passed_mark_count", "id": "stats3_firsts", "label": "Two third-year Statistics firsts", "course_codes": stats3, "required": 2, "minimum_mark": 75},
        ]})
    return rules


def programme_specific_rules(spec: dict[str, Any]) -> list[dict[str, Any]]:
    code = spec["code"]
    rules: list[dict[str, Any]] = []
    if code.endswith("CSC05"):
        for course_code in ["CSC1015F", "CSC1016S", "CSC2001F", "CSC2002S", "CSC3002F", "CSC3003S"]:
            rules.append({"type": "minimum_mark", "id": f"cs65_{course_code.lower()}", "label": f"Minimum 65% in {course_code}", "course_codes": [course_code], "minimum_mark": 65})
    if code.endswith("FTX05"):
        rules.append({"type": "weighted_average", "id": "finance_entry_average", "label": "FTX3044F and FTX3045S progression average", "course_codes": ["FTX3044F", "FTX3045S"], "minimum_average": 60})
    if code.endswith("FTX04"):
        rules.extend([
            {"type": "minimum_mark", "id": "acc1011_60", "label": "ACC1011S progression mark", "course_codes": ["ACC1011S", "ACC1111S"], "minimum_mark": 60},
            {"type": "weighted_average", "id": "finance_accounting_entry", "label": "FTX3044F and FTX3045S progression average", "course_codes": ["FTX3044F", "FTX3045S"], "minimum_average": 60},
            manual("Final-year Chartered Accounting course admission", "ca_course_admission", "Admission to ACC3009W is subject to the published weighted-average, timing and subminimum rules and may depend on entrance examinations.", status="discretionary", blocking=False),
        ])
    if code.endswith("ECO03"):
        rules.append(manual("Allocation of limited Law-course places", "law_place_allocation", "The 63% eligibility threshold does not guarantee a place; allocation is competitive and subject to Law Faculty capacity and redress targets.", status="discretionary", blocking=True))
    if code.endswith(("BUS01", "BUS09")) and spec["family"] != "advanced":
        rules.append(manual("Actuarial professional exemptions", "actuarial_exemptions", "Professional-body exemptions depend on individual course performance and external examiner decisions; they are not part of degree completion.", status="discretionary", blocking=False))
    return rules


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    text = TEXT_PATH.read_text(errors="replace")
    courses = parse_course_descriptions(text)
    specs = route_specs()
    located = positions_for_specs(text, specs)
    programmes: dict[str, Any] = {}
    extraction_summary: dict[str, Any] = {}
    table_observations: dict[str, list[dict[str, Any]]] = {}

    for position_index, (start, spec) in enumerate(located):
        if position_index + 1 < len(located):
            end = located[position_index + 1][0]
        else:
            end = text.find("DEPARTMENTS IN THE FACULTY OF", start)
            if end <= start:
                end = len(text)
        segment = text[start:end]
        start_page = text.count("\f", 0, start) + 1
        spec["page"] = spec.get("page", start_page)
        curriculum_rules: list[dict[str, Any]] = []
        table_rows: list[dict[str, Any]] = []
        unresolved: list[str] = []
        if spec["family"] == "advanced":
            curriculum_rules, table_rows, unresolved = advanced_curriculum(spec, segment, start_page)
        else:
            for block_name, block_lines in split_year_blocks(segment, start_page):
                block_rules, rows, warnings = parse_block(block_name, block_lines, spec["code"])
                curriculum_rules.extend(block_rules); table_rows.extend(rows); unresolved.extend(warnings)
        for row in table_rows:
            add_table_fact(courses, row)
            for course_code in row["codes"]:
                table_observations.setdefault(course_code, []).append({
                    "programme": spec["code"], "credits": row["credits"],
                    "nqf_level": row["level"], "page": row["page"], "name": row["name"],
                })
        all_codes = sorted({code for row in table_rows for code in row["codes"]})
        curriculum_rules.extend(programme_specific_rules(spec))

        family = spec["family"]
        if family == "advanced":
            if spec["code"] == "CU020BUS01":
                minimum_credits, level7, duration, max_years = 180, 120, 1, 2
            elif spec["code"] == "CU021GSB48":
                minimum_credits, level7, duration, max_years = 120, 120, 1, 2
            else:
                minimum_credits, level7, duration, max_years = 174, 120, 1, 2
            degree_category = "Advanced Diploma"
        elif family == "bbussci":
            minimum_credits, level7, duration, max_years = 528, 0, spec["minimum_years"], spec["minimum_years"]
            degree_category = "Bachelor of Business Science"
        else:
            minimum_credits, level7, duration, max_years = 440, 120, spec["minimum_years"], spec["minimum_years"]
            degree_category = "Bachelor of Commerce"

        # Add faculty-level credit/level requirements explicitly so curriculum output is intelligible.
        curriculum_rules.insert(0, {"type": "credits", "id": f"{spec['code']}_total_credits", "label": "Minimum qualification credits", "required": minimum_credits})
        if family == "bbussci":
            curriculum_rules.insert(1, {"type": "level_credits", "id": f"{spec['code']}_level8", "label": "Minimum NQF level 8 credits", "nqf_level": 8, "required": 120})
        elif family == "bcom":
            curriculum_rules.insert(1, {"type": "level_credits", "id": f"{spec['code']}_level7", "label": "Minimum NQF level 7 credits", "nqf_level": 7, "required": 120})

        # Preserve explicit source conflicts such as the Management Studies 416-credit table.
        printed_total_match = re.search(r"Total credits for the degree\D+(\d+)", segment, re.I)
        if printed_total_match and int(printed_total_match.group(1)) < minimum_credits:
            curriculum_rules.append(manual(
                "Published programme-total reconciliation", f"{spec['code']}_credit_conflict",
                f"The programme table states {printed_total_match.group(1)} credits while the faculty rule requires at least {minimum_credits}. Faculty confirmation is required.",
                status="conflict", blocking=True,
            ))
        if unresolved:
            if spec["code"] == "CU020BUS01" and all("distinction paragraph" in item for item in unresolved):
                curriculum_rules.append(manual(
                    "Advanced Diploma distinction-source reconciliation", f"{spec['code']}_distinction_conflict",
                    unresolved[0], status="conflict", blocking=False,
                ))
            else:
                curriculum_rules.append(manual(
                    "Unresolved programme-table choice wording", f"{spec['code']}_choice_verification",
                    "One or more choice/elective statements could not be reduced to a closed static list without academic interpretation. Verify the approved curriculum with a Commerce student advisor.",
                    status="unverified", blocking=True,
                ))

        key = spec["code"].lower()
        programmes[key] = {
            "name": spec["name"], "minimum_nqf_credits": minimum_credits,
            "minimum_nqf_level_7_credits": level7,
            "level_credit_requirements": ({"8": 120} if family == "bbussci" else {}),
            "minimum_semester_courses": 0, "minimum_senior_semester_courses": 0,
            "minimum_humanities_semester_courses": 0, "minimum_majors": 0,
            "minimum_humanities_majors": 0, "required_courses": [],
            "minimum_duration_years": duration, "maximum_registration_years": max_years,
            "qualification_codes": spec.get("qualification_codes", [spec["code"]]),
            "major_keys": [], "elective_course_codes": [], "elective_departments": [],
            "support_course_codes": [], "scope_verified": True,
            "route_type": spec["mode"], "degree_category": degree_category,
            "programme_type": "commerce_structured", "curriculum_rules": curriculum_rules,
            "pathways": {}, "pathway_required": False, "default_pathway_key": "",
            "availability": "open", "availability_note": "",
            "admission_notes": [
                "Admission, professional-body recognition and limited-course placement are separate from curriculum completion.",
            ],
            "progression_notes": [
                "Readmission and programme-change outcomes remain decisions of the Faculty Examinations Committee and Senate.",
                "Commerce GPA ordinarily uses first attempts; AB, DPR and INC contribute zero where the handbook specifies.",
            ],
            "award_notes": ["Distinction calculations use only programme-relevant first attempts and do not round up."],
            "progression_rules": programme_progression(spec, set(all_codes)),
            "award_rules": degree_award_rules(spec, all_codes),
            "source": source(spec["page"]),
        }
        extraction_summary[key] = {"course_rows": len(table_rows), "codes": len(all_codes), "unresolved": unresolved}

    # Ensure all substitution facts referenced by curriculum rules exist. Prefer facts
    # from this handbook; otherwise import a conservative shell from table evidence.
    referenced_substitutes = sorted({c for groups in SUBSTITUTIONS.values() for group in groups for c in group})
    for code in referenced_substitutes:
        if code in courses:
            continue
        level_digit = int(re.search(r"\d", code).group())
        level = {1: 5, 2: 6, 3: 7, 4: 8}.get(level_digit, 0)
        courses[code] = {
            "code": code, "name": f"Recognised substitute {code}", "credits": 18, "nqf_level": level,
            "prerequisites": [], "prerequisites_verified": False, "co_requisites": [],
            "offered": offered_from_code(code), "offering_verified": False,
            "department": PREFIX_DEPARTMENT.get(prefix(code), prefix(code)), "description": "",
            "verification_status": "provisional", "source": source(260, "Commerce interfaculty course substitutions"),
            "general_elective": False, "counts_towards_general_degree": True,
            "counts_as_humanities": False, "counts_as_science": False,
            "counts_towards_course_equivalents": True, "credit_bearing": True,
            "recognition_note": "The substitution relationship is handbook-grounded; the precise credit value or current offering should be confirmed where no course outline is printed in this handbook.",
        }

    requirements = {
        "catalogue_version": "UCT Commerce Undergraduate 2026",
        "source": PDF_NAME,
        "programmes": programmes,
        "majors": {}, "forbidden_major_combinations": [], "cross_credit_exclusions": [],
    }
    (OUT / "courses.json").write_text(json.dumps([courses[c] for c in sorted(courses)], indent=2, ensure_ascii=False) + "\n")
    (OUT / "degree_requirements.json").write_text(json.dumps(requirements, indent=2, ensure_ascii=False) + "\n")
    source_dir = OUT / "source_extraction"; source_dir.mkdir(exist_ok=True)
    (source_dir / "programme_extraction_summary.json").write_text(json.dumps(extraction_summary, indent=2, ensure_ascii=False) + "\n")
    conflicts: list[dict[str, Any]] = []
    for course_code, observations in sorted(table_observations.items()):
        published = sorted({(item["credits"], item["nqf_level"]) for item in observations})
        if len(published) <= 1:
            continue
        canonical = courses.get(course_code, {})
        conflicts.append({
            "course_code": course_code,
            "published_credit_level_pairs": [
                {"credits": credits, "nqf_level": level} for credits, level in published
            ],
            "canonical_course_fact": {
                "credits": canonical.get("credits"), "nqf_level": canonical.get("nqf_level"),
                "source": canonical.get("source", {}),
            },
            "observations": observations,
            "resolution": "The department course-outline fact is retained; the conflicting curriculum-table rows are recorded for faculty confirmation.",
        })
    (source_dir / "course_fact_conflicts.json").write_text(json.dumps(conflicts, indent=2, ensure_ascii=False) + "\n")
    print(f"Wrote {len(courses)} Commerce course facts and {len(programmes)} programme routes; recorded {len(conflicts)} table conflicts")


if __name__ == "__main__":
    main()
