"""Recognition rules for courses credited toward a selected programme.

The transcript records what a student passed.  The faculty handbook decides
which of those passes may be recognised toward the selected qualification.
Keeping that distinction in one module prevents credit totals, readmission
counts, and explanations from drifting apart.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable
import re

from .models import Catalogue, CourseFact, CourseResult, StudentRecord


@dataclass(frozen=True)
class RecognitionExclusion:
    code: str
    reason: str


@dataclass(frozen=True)
class ProvisionalCreditAllocation:
    """Transcript credits tentatively allocated to an approved/open pool.

    These are not catalogue facts.  They are used only where the selected
    programme expressly permits an approved, complementary, free or open
    elective whose complete option list is not published in the handbook.
    """

    rule_id: str
    label: str
    results: tuple[CourseResult, ...]
    recognised_codes: tuple[str, ...]
    recognised_credits: int
    provisional_credits: int
    required_credits: int
    note: str


def _walk_rules(rules: Iterable[dict[str, Any]]) -> Iterable[dict[str, Any]]:
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        yield rule
        children = rule.get("children", [])
        if isinstance(children, list):
            yield from _walk_rules(
                child for child in children if isinstance(child, dict)
            )


def approved_credit_pool_rules(catalogue: Catalogue) -> list[dict[str, Any]]:
    """Return approved/open elective rules active in the selected scope."""
    programme = catalogue.programmes.get(catalogue.programme_key)
    if programme is None:
        return []
    rules = list(_walk_rules(programme.curriculum_rules))
    pathway = (
        programme.pathways.get(catalogue.pathway_key) if catalogue.pathway_key else None
    )
    if pathway is not None:
        rules.extend(_walk_rules(pathway.curriculum_rules))
    return [
        rule
        for rule in rules
        if str(rule.get("type", "")).strip().lower() == "approved_credit_pool"
    ]


def _result_matches_filters(result: CourseResult, filters: dict[str, Any]) -> bool:
    levels = {int(value) for value in filters.get("nqf_levels", [])}
    if levels and result.nqf_level not in levels:
        return False
    year_levels = {int(value) for value in filters.get("year_levels", [])}
    if year_levels and _course_year_level(result.code) not in year_levels:
        return False
    prefixes = tuple(
        str(value).strip().upper()
        for value in filters.get("prefixes", [])
        if str(value).strip()
    )
    if prefixes and not result.code.startswith(prefixes):
        return False
    excluded_prefixes = tuple(
        str(value).strip().upper()
        for value in filters.get("exclude_prefixes", [])
        if str(value).strip()
    )
    if excluded_prefixes and result.code.startswith(excluded_prefixes):
        return False
    minimum_credits = int(filters.get("minimum_credits", 0) or 0)
    if minimum_credits and result.nqf_credits < minimum_credits:
        return False
    maximum_credits = int(filters.get("maximum_credits", 0) or 0)
    if maximum_credits and result.nqf_credits > maximum_credits:
        return False
    return True


def provisional_open_credit_allocations(
    student: StudentRecord,
    catalogue: Catalogue,
) -> list[ProvisionalCreditAllocation]:
    """Allocate transcript-only passes to published approved/open credit pools.

    The transcript may contain a legitimate elective that is outside the
    programme-scoped catalogue because the handbook permits *any approved*
    course or refers to a separate live list.  Such a course may be counted
    provisionally, never as a verified programme fact.  Allocation is capped
    by the published pool requirement and each unknown course is allocated at
    most once across the active route.
    """
    rules = approved_credit_pool_rules(catalogue)
    if not rules:
        return []

    recognised, _ = recognised_credited_pairs(student, catalogue)
    recognised_by_code = {result.code: fact for result, fact in recognised}
    transcript_only_results = [
        result
        for result in student.credited_results()
        if result.code not in catalogue.courses and result.nqf_credits > 0
    ]
    allocated_codes: set[str] = set()
    allocated_known_codes: set[str] = set()
    allocations: list[ProvisionalCreditAllocation] = []

    for index, rule in enumerate(rules):
        rule_id = str(rule.get("id", f"approved_credit_pool_{index}"))
        label = str(rule.get("label", "Approved elective credits"))
        required = int(rule.get("required", 0))
        maximum = int(rule.get("maximum", 0))
        target = required if required > 0 else maximum
        explicit = {
            str(code).strip().upper()
            for code in rule.get("course_codes", [])
            if str(code).strip()
        }
        transcript_explicit = {
            str(code).strip().upper()
            for code in rule.get("transcript_course_codes", [])
            if str(code).strip()
        }
        if not transcript_explicit and not bool(
            rule.get("allow_unlisted_transcript_courses", False)
        ):
            transcript_explicit = set(explicit)
        excluded = {
            str(code).strip().upper()
            for code in rule.get("exclude_course_codes", [])
            if str(code).strip()
        }
        filters = rule.get("transcript_filters", {})
        if not isinstance(filters, dict):
            filters = {}

        known_credits = 0
        known_codes: list[str] = []
        rule_transcript_only = bool(rule.get("transcript_only", False))
        if not rule_transcript_only:
            for code, fact in recognised_by_code.items():
                if code in allocated_known_codes or code in excluded:
                    continue
                if explicit and code not in explicit:
                    continue
                result = student.passed_result_for(code)
                if result is None:
                    continue
                # ``transcript_filters`` constrain unlisted/transcript-only
                # options. Explicit handbook-listed courses are already
                # members of the pool and must not be rejected merely
                # because those provisional-option filters differ.
                if not explicit and not _result_matches_filters(result, filters):
                    continue
                known_codes.append(code)
                allocated_known_codes.add(code)
                known_credits += fact.nqf_credits

        selected: list[CourseResult] = []
        provisional_credits = 0
        if known_credits < target:
            for result in transcript_only_results:
                if result.code in allocated_codes or result.code in excluded:
                    continue
                if transcript_explicit and result.code not in transcript_explicit:
                    continue
                if not _result_matches_filters(result, filters):
                    continue
                selected.append(result)
                allocated_codes.add(result.code)
                provisional_credits += result.nqf_credits
                if known_credits + provisional_credits >= target:
                    break

        note = str(
            rule.get(
                "approval_note",
                "The transcript records these credits, but the static catalogue cannot verify faculty approval.",
            )
        )
        allocations.append(
            ProvisionalCreditAllocation(
                rule_id=rule_id,
                label=label,
                results=tuple(selected),
                recognised_codes=tuple(known_codes),
                recognised_credits=known_credits,
                provisional_credits=provisional_credits,
                required_credits=target,
                note=note,
            )
        )

    return allocations


def provisional_open_credit_results(
    student: StudentRecord,
    catalogue: Catalogue,
) -> list[CourseResult]:
    """Flatten provisionally allocated transcript-only elective results."""
    return [
        result
        for allocation in provisional_open_credit_allocations(student, catalogue)
        for result in allocation.results
    ]


def _course_year_level(code: str) -> int:
    """Return the conventional 1000/2000/3000 level from a UCT code."""
    match = re.match(r"^[A-Z]+([1-9])", code.strip().upper())
    return int(match.group(1)) if match else 0


def recognised_credited_pairs(
    student: StudentRecord,
    catalogue: Catalogue,
) -> tuple[list[tuple[CourseResult, CourseFact]], list[RecognitionExclusion]]:
    """Return one recognised passing attempt per code plus visible exclusions.

    Humanities rule FB5.5 limits recognition of South African College of Music
    courses in a general BA/BSocSc to four 1000-level, four 2000-level, and two
    3000-level course codes.  Transcript order is used when more courses than
    the limit were passed; the report flags that the final allocation should be
    confirmed by the faculty because a transcript does not state which excess
    course the faculty will elect to disregard.
    """
    recognised: list[tuple[CourseResult, CourseFact]] = []
    exclusions: list[RecognitionExclusion] = []
    programme = catalogue.programmes.get(catalogue.programme_key)
    general_degree = programme is None or programme.programme_type == "general_degree"
    music_limits = {1: 4, 2: 4, 3: 2}
    music_counts = {1: 0, 2: 0, 3: 0}

    for result in student.credited_results():
        fact = catalogue.courses.get(result.code)
        if fact is None:
            continue
        if not fact.credit_bearing:
            continue
        if general_degree and not fact.counts_towards_general_degree:
            continue

        if general_degree and result.code.startswith("MUZ"):
            year_level = _course_year_level(result.code)
            limit = music_limits.get(year_level)
            if limit is not None:
                if music_counts[year_level] >= limit:
                    exclusions.append(
                        RecognitionExclusion(
                            result.code,
                            f"Humanities rule FB5.5 recognises no more than {limit} "
                            f"South African College of Music course codes at {year_level}000 level.",
                        )
                    )
                    continue
                music_counts[year_level] += 1

        recognised.append((result, fact))

    return recognised, exclusions
