"""UCT transcript parser.

The parser extracts facts only. Programme rules, credits and course status are
interpreted later against the selected handbook catalogue.
"""

import re
from typing import Optional
from .models import StudentRecord, CourseResult

_NAME_RE = re.compile(r"^Name:\s+(.+)", re.IGNORECASE)
_ID_RE = re.compile(r"^Campus\s+ID:\s+([A-Z0-9]+)", re.IGNORECASE)
_PROG_RE = re.compile(r"^Programme:\s+(.+)", re.IGNORECASE)
_SPEC_RE = re.compile(r"^Specialisation:\s+(.+)$", re.IGNORECASE)
_YEAR_RE = re.compile(r"^(?:Academic\s+Year|Year)?:?\s*(20\d{2})\s*$", re.IGNORECASE)

# Standard numeric result row:
# PHI 1024F Introduction To Philosophy 05 18 57 3
_COURSE_RE = re.compile(
    r"^([A-Z]{2,4})\s+(\d{4}[A-Z]{1,2})\s+(.+?)\s+"
    r"(\d{2})\s+(\d{1,2})\s+(\d{1,3})\s+(\S+)\s*$",
    re.IGNORECASE,
)

# Status-only rows such as AB, DPR, INC, DE, PA, UP or SP.
_STATUS_TOKEN = (
    r"A/SF|UF\s+SM|DPR|INC|EXA|GIP|ATT|LOA|OSS|AB|DE|OS|PA|UP|SP|SF|FS|UF|F|P"
)
_COURSE_STATUS_RE = re.compile(
    rf"^([A-Z]{{2,4}})\s+(\d{{4}}[A-Z]{{1,2}})\s+(.+?)\s+"
    rf"(\d{{2}})\s+(\d{{1,2}})\s+({_STATUS_TOKEN})\s*$",
    re.IGNORECASE,
)
_COURSE_NO_RESULT_RE = re.compile(
    r"^([A-Z]{2,4})\s+(\d{4}[A-Z]{1,2})\s+(.+?)\s+0\s*$",
    re.IGNORECASE,
)

_VALID_GRADES = {
    "1",
    "2+",
    "2-",
    "3",
    "F",
    "P",
    "PA",
    "UP",
    "SP",
    "FS",
    "SF",
    "A/SF",
    "AB",
    "DPR",
    "INC",
    "DE",
    "OS",
    "ATT",
    "GIP",
    "LOA",
    "EXA",
    "UF",
    "UF SM",
    "OSS",
}


def _parse_grade(grade_str: str) -> Optional[str]:
    grade = " ".join(grade_str.strip().upper().split())
    return grade if grade in _VALID_GRADES else None


def _normalise_name(raw: str) -> str:
    raw = re.sub(r"\s+Student\s+Records\s+Office.*$", "", raw, flags=re.IGNORECASE)
    if "," in raw:
        surname, given = [part.strip() for part in raw.split(",", 1)]
        return f"{given} {surname}"
    return raw.strip()


def parse_transcript_text(text: str) -> StudentRecord:
    lines = text.splitlines()
    student_id = ""
    name = ""
    programme = ""
    declared_majors: list[str] = []
    results: list[CourseResult] = []
    current_academic_year: Optional[int] = None

    for raw_line in lines:
        line = " ".join(raw_line.strip().split())
        if not line:
            continue

        year_match = _YEAR_RE.match(line)
        if year_match:
            current_academic_year = int(year_match.group(1))
            continue

        match = _NAME_RE.match(line)
        if match and not name:
            name = _normalise_name(match.group(1))
            continue
        match = _ID_RE.match(line)
        if match and not student_id:
            student_id = match.group(1).strip().upper()
            continue
        match = _PROG_RE.match(line)
        if match and not programme:
            programme = match.group(1).strip()
            continue
        match = _SPEC_RE.match(line)
        if match:
            major_name = re.sub(
                r"\s+(Major|Specialisation|Specialization|Stream|Programme)\s*$",
                "",
                match.group(1).strip(),
                flags=re.IGNORECASE,
            )
            if major_name and major_name not in declared_majors:
                declared_majors.append(major_name)
            continue

        match = _COURSE_RE.match(line)
        if match:
            dept, number, course_name, level, credits, mark, grade = match.groups()
            mark_value = int(mark)
            if 0 <= mark_value <= 100:
                results.append(
                    CourseResult(
                        code=f"{dept.upper()}{number.upper()}",
                        name=course_name.strip(),
                        nqf_level=int(level),
                        nqf_credits=int(credits),
                        mark=mark_value,
                        grade=_parse_grade(grade),
                        academic_year=current_academic_year,
                    )
                )
                continue

        match = _COURSE_STATUS_RE.match(line)
        if match:
            dept, number, course_name, level, credits, grade = match.groups()
            results.append(
                CourseResult(
                    code=f"{dept.upper()}{number.upper()}",
                    name=course_name.strip(),
                    nqf_level=int(level),
                    nqf_credits=int(credits),
                    mark=None,
                    grade=_parse_grade(grade),
                    academic_year=current_academic_year,
                )
            )
            continue

        match = _COURSE_NO_RESULT_RE.match(line)
        if match:
            dept, number, course_name = match.groups()
            results.append(
                CourseResult(
                    code=f"{dept.upper()}{number.upper()}",
                    name=course_name.strip(),
                    nqf_level=0,
                    nqf_credits=0,
                    mark=None,
                    grade=None,
                    academic_year=current_academic_year,
                )
            )

    return StudentRecord(
        student_id=student_id,
        name=name,
        programme=programme,
        declared_majors=declared_majors,
        results=results,
    )


def parse_transcript_pdf(pdf_path_or_file) -> StudentRecord:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise ImportError("pypdf is required: pip install pypdf") from exc

    reader = PdfReader(
        pdf_path_or_file if hasattr(pdf_path_or_file, "read") else str(pdf_path_or_file)
    )
    full_text = "\n".join((page.extract_text() or "") for page in reader.pages)
    return parse_transcript_text(full_text)
