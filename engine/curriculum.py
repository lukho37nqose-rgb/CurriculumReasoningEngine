"""Composable curriculum-rule evaluation for structured Humanities routes.

The general BA/BSocSc degrees are expressed through majors and aggregate
thresholds.  Professional, performance, education, fine-art and music
qualifications instead prescribe curricula with streams, alternatives and
manual selection conditions.  This module evaluates a small handbook-grounded
rule language without turning discretionary institutional decisions into facts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any, Iterable

from .models import Catalogue, CourseFact, CourseResult, StudentRecord
from .recognition import recognised_credited_pairs, provisional_open_credit_allocations
from .utils import _course_weight


@dataclass
class RuleEvaluation:
    id: str
    label: str
    complete: bool
    current: float
    required: float
    detail: str
    status: str = "verified"
    confidence: float = 1.0
    blocking: bool = True
    used_course_codes: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    source: dict[str, Any] = field(default_factory=dict)


def _normalise_codes(values: Iterable[Any]) -> list[str]:
    return [str(value).strip().upper() for value in values if str(value).strip()]


def collect_rule_course_codes(
    rule: dict[str, Any], catalogue: Catalogue | None = None
) -> set[str]:
    """Collect every course that a rule may require or recommend."""
    codes = set(_normalise_codes(rule.get("course_codes", [])))
    code = str(rule.get("course_code", "")).strip().upper()
    if code:
        codes.add(code)
    for child in rule.get("children", []):
        if isinstance(child, dict):
            codes.update(collect_rule_course_codes(child, catalogue))
    filters = (
        rule.get("filters", {}) if isinstance(rule.get("filters", {}), dict) else {}
    )
    codes.update(_normalise_codes(filters.get("course_codes", [])))
    if catalogue and filters:
        candidates = codes or set(catalogue.courses)
        for course_code in list(candidates):
            fact = catalogue.courses.get(course_code)
            if fact is not None and _fact_matches_filters(course_code, fact, filters):
                codes.add(course_code)
    return codes


def collect_curriculum_course_codes(
    rules: Iterable[dict[str, Any]],
    catalogue: Catalogue | None = None,
) -> set[str]:
    codes: set[str] = set()
    for rule in rules:
        if isinstance(rule, dict):
            codes.update(collect_rule_course_codes(rule, catalogue))
    return codes


def _year_level(code: str) -> int:
    match = re.match(r"^[A-Z]+([1-9])", code)
    return int(match.group(1)) if match else 0


def _fact_matches_filters(code: str, fact: CourseFact, filters: dict[str, Any]) -> bool:
    explicit = set(_normalise_codes(filters.get("course_codes", [])))
    if explicit and code not in explicit:
        return False
    prefixes = [
        str(p).strip().upper() for p in filters.get("prefixes", []) if str(p).strip()
    ]
    if prefixes and not any(code.startswith(prefix) for prefix in prefixes):
        return False
    excluded_prefixes = [
        str(p).strip().upper()
        for p in filters.get("exclude_prefixes", [])
        if str(p).strip()
    ]
    if excluded_prefixes and any(
        code.startswith(prefix) for prefix in excluded_prefixes
    ):
        return False
    levels = {int(value) for value in filters.get("nqf_levels", [])}
    if levels and fact.nqf_level not in levels:
        return False
    years = {int(value) for value in filters.get("year_levels", [])}
    if years and _year_level(code) not in years:
        return False
    if filters.get("senior") is True and fact.nqf_level < 6:
        return False
    if filters.get("humanities") is True and not fact.counts_as_humanities:
        return False
    if filters.get("science") is True and not fact.counts_as_science:
        return False
    if filters.get("general_elective") is True and not fact.general_elective:
        return False
    if filters.get("credit_bearing") is True and not fact.credit_bearing:
        return False
    if filters.get("departments"):
        departments = {str(value).strip().lower() for value in filters["departments"]}
        if fact.department.strip().lower() not in departments:
            return False
    return True


def _combine_status(statuses: list[str], fallback: str = "verified") -> str:
    if not statuses:
        return fallback
    order = {
        "conflict": 5,
        "discretionary": 4,
        "unverified": 3,
        "provisional": 2,
        "verified": 1,
    }
    return max(statuses, key=lambda value: order.get(value, 3))


class CurriculumEvaluator:
    def __init__(self, student: StudentRecord, catalogue: Catalogue):
        self.student = student
        self.catalogue = catalogue
        pairs, _ = recognised_credited_pairs(student, catalogue)
        self.pairs = pairs
        self.fact_by_code = {fact.code: fact for _, fact in pairs}
        self.result_by_code: dict[str, CourseResult] = {}
        for result, _ in pairs:
            self.result_by_code[result.code] = result
        self.passed = set(self.result_by_code)
        # Zero-credit practical, project, skills and assessment courses may be
        # compulsory even though they do not contribute to credit totals.
        # Keep them available for course-completion rules without adding them
        # to the recognised credit maps.
        self.passed.update(
            result.code
            for result in student.credited_results()
            if result.code in catalogue.courses
        )
        self.open_credit_allocations = provisional_open_credit_allocations(
            student, catalogue
        )
        self.open_allocation_by_id = {
            allocation.rule_id: allocation
            for allocation in self.open_credit_allocations
        }
        self.provisional_results = [
            result
            for allocation in self.open_credit_allocations
            for result in allocation.results
        ]
        self.provisional_result_by_code = {
            result.code: result for result in self.provisional_results
        }
        self.provisional_codes = set(self.provisional_result_by_code)
        self.credits = sum(fact.nqf_credits for _, fact in pairs) + sum(
            result.nqf_credits for result in self.provisional_results
        )
        self.credits_by_level: dict[int, int] = {}
        for _, fact in pairs:
            self.credits_by_level[fact.nqf_level] = (
                self.credits_by_level.get(fact.nqf_level, 0) + fact.nqf_credits
            )
        for result in self.provisional_results:
            self.credits_by_level[result.nqf_level] = (
                self.credits_by_level.get(result.nqf_level, 0) + result.nqf_credits
            )

    def evaluate_many(self, rules: Iterable[dict[str, Any]]) -> list[RuleEvaluation]:
        return [self.evaluate(rule) for rule in rules if isinstance(rule, dict)]

    def evaluate(self, rule: dict[str, Any]) -> RuleEvaluation:
        rule_type = str(rule.get("type", "course")).strip().lower()
        rule_id = str(rule.get("id", rule.get("label", rule_type))).strip() or rule_type
        label = str(rule.get("label", rule_id)).strip()
        status = str(rule.get("verification_status", rule.get("status", "verified")))
        blocking = bool(rule.get("blocking", True))
        source = (
            rule.get("source", {}) if isinstance(rule.get("source", {}), dict) else {}
        )

        if rule_type == "manual":
            assumed_complete = bool(rule.get("assumed_complete", True))
            manual_status = str(rule.get("status", "discretionary"))
            note = str(
                rule.get(
                    "note",
                    "This condition requires confirmation by the relevant academic authority.",
                )
            )
            return RuleEvaluation(
                id=rule_id,
                label=label,
                complete=assumed_complete,
                current=1.0 if assumed_complete else 0.0,
                required=1.0,
                detail=note,
                status=manual_status,
                confidence=0.0,
                blocking=blocking,
                assumptions=[note],
                source=source,
            )

        if rule_type == "credits":
            required = float(rule.get("required", 0))
            current = float(self.credits)
            evaluation_status = "unverified" if self.provisional_codes else status
            assumptions = []
            detail = f"{int(current)} of {int(required)} recognised or provisionally allocated NQF credits completed."
            if self.provisional_codes:
                assumptions.append(
                    "Includes transcript credits allocated to an approved/open elective pool whose faculty approval is not verified."
                )
                detail += (
                    " Provisional elective codes: "
                    + ", ".join(sorted(self.provisional_codes))
                    + "."
                )
            return RuleEvaluation(
                rule_id,
                label,
                current >= required,
                current,
                required,
                detail,
                evaluation_status,
                (
                    0.45
                    if self.provisional_codes
                    else (1.0 if status == "verified" else 0.7)
                ),
                blocking,
                used_course_codes=sorted(self.passed | self.provisional_codes),
                assumptions=assumptions,
                source=source,
            )

        if rule_type == "level_credits":
            level = int(rule.get("nqf_level", 0))
            required = float(rule.get("required", 0))
            current = float(self.credits_by_level.get(level, 0))
            used = sorted(
                code
                for code, fact in self.fact_by_code.items()
                if fact.nqf_level == level
            )
            return RuleEvaluation(
                rule_id,
                label,
                current >= required,
                current,
                required,
                f"{int(current)} of {int(required)} credits at NQF level {level} completed.",
                status,
                1.0 if status == "verified" else 0.7,
                blocking,
                used_course_codes=used,
                source=source,
            )

        if rule_type == "minimum_mark":
            codes = _normalise_codes(rule.get("course_codes", []))
            threshold = int(rule.get("minimum_mark", rule.get("required", 0)))
            matched = [
                self.result_by_code[code]
                for code in codes
                if code in self.result_by_code
            ]
            if not matched:
                return RuleEvaluation(
                    rule_id,
                    label,
                    False,
                    0.0,
                    float(threshold),
                    f"No passing result was found for any of: {', '.join(codes)}.",
                    status,
                    1.0,
                    blocking,
                    source=source,
                )
            known_marks = [result.mark for result in matched if result.mark is not None]
            if not known_marks:
                note = "The course is passed, but the transcript does not expose a numeric mark for this threshold."
                return RuleEvaluation(
                    rule_id,
                    label,
                    True,
                    0.0,
                    float(threshold),
                    note,
                    "unverified",
                    0.0,
                    blocking,
                    used_course_codes=[result.code for result in matched],
                    assumptions=[note],
                    source=source,
                )
            current = float(max(known_marks))
            return RuleEvaluation(
                rule_id,
                label,
                current >= threshold,
                current,
                float(threshold),
                f"Best recorded mark is {int(current)}%; at least {threshold}% is required.",
                status,
                1.0,
                blocking,
                used_course_codes=[result.code for result in matched],
                source=source,
            )

        if rule_type in {"course", "choose_n"} and rule.get("children"):
            children = [
                self.evaluate(child)
                for child in rule.get("children", [])
                if isinstance(child, dict)
            ]
            required = int(
                rule.get("required", 1 if rule_type == "course" else len(children))
            )
            complete_children = [child for child in children if child.complete]
            used = sorted(
                {
                    code
                    for child in complete_children
                    for code in child.used_course_codes
                }
            )
            child_status = _combine_status(
                [child.status for child in complete_children], status
            )
            return RuleEvaluation(
                rule_id,
                label,
                len(complete_children) >= required,
                float(len(complete_children)),
                float(required),
                f"{len(complete_children)} of {required} alternatives completed.",
                _combine_status([status, child_status]),
                min([child.confidence for child in complete_children] or [1.0]),
                blocking,
                used,
                source=source,
            )

        if rule_type in {"course", "choose_n", "all_courses"}:
            codes = _normalise_codes(rule.get("course_codes", []))
            if rule_type == "course":
                required = int(rule.get("required", 1))
            elif rule_type == "all_courses":
                required = len(codes)
            else:
                required = int(rule.get("required", 1))
            completed = [code for code in codes if code in self.passed]
            missing = [code for code in codes if code not in self.passed]
            if rule_type == "course" and required == 1:
                detail = (
                    f"Completed via {completed[0]}."
                    if completed
                    else "Complete one of: " + ", ".join(codes) + "."
                )
            else:
                detail = (
                    f"{len(completed)} of {required} required course choices completed."
                )
                if len(completed) < required and missing:
                    detail += (
                        " Remaining options include: "
                        + ", ".join(missing[:12])
                        + ("…" if len(missing) > 12 else "")
                    )
            return RuleEvaluation(
                rule_id,
                label,
                len(completed) >= required,
                float(len(completed)),
                float(required),
                detail,
                status,
                1.0 if status == "verified" else 0.7,
                blocking,
                completed,
                source=source,
            )

        if rule_type == "approved_credit_pool":
            required = float(rule.get("required", 0))
            maximum = float(rule.get("maximum", 0))
            allocation = self.open_allocation_by_id.get(rule_id)
            if allocation is None:
                detail = "No approved/open elective allocation could be constructed for this rule."
                optional_only = required <= 0 and maximum > 0
                return RuleEvaluation(
                    rule_id,
                    label,
                    optional_only,
                    0.0,
                    maximum if optional_only else required,
                    detail,
                    "unverified",
                    0.0,
                    blocking,
                    assumptions=[detail],
                    source=source,
                )
            current = float(
                allocation.recognised_credits + allocation.provisional_credits
            )
            provisional_codes = [result.code for result in allocation.results]
            known_codes = sorted(allocation.recognised_codes)
            if required > 0:
                detail = f"{int(current)} of {int(required)} credits identified for this approved/open elective pool."
            elif maximum > 0:
                detail = f"{int(current)} credits identified in this optional pool; up to {int(maximum)} may be recognised."
            else:
                detail = f"{int(current)} credits identified in this optional approved/open elective pool."
            assumptions: list[str] = []
            evaluation_status = status if status != "verified" else "unverified"
            confidence = 0.55
            if provisional_codes:
                detail += (
                    " Transcript-only course(s) provisionally allocated: "
                    + ", ".join(provisional_codes)
                    + "."
                )
                assumptions.append(allocation.note)
                confidence = 0.35
            else:
                detail += " Faculty approval and live registration eligibility still require confirmation."
                assumptions.append(allocation.note)
            complete = (
                current >= required
                if required > 0
                else (current <= maximum if maximum > 0 else True)
            )
            display_required = required if required > 0 else maximum
            return RuleEvaluation(
                rule_id,
                label,
                complete,
                current,
                display_required,
                detail,
                evaluation_status,
                confidence,
                blocking,
                used_course_codes=sorted(set(known_codes + provisional_codes)),
                assumptions=assumptions,
                source=source,
            )

        if rule_type == "credit_pool":
            filters = (
                rule.get("filters", {})
                if isinstance(rule.get("filters", {}), dict)
                else {}
            )
            explicit = set(_normalise_codes(rule.get("course_codes", [])))
            required = float(rule.get("required", 0))
            matched = sorted(
                code
                for code, fact in self.fact_by_code.items()
                if (not explicit or code in explicit)
                and _fact_matches_filters(code, fact, filters)
            )
            current = float(
                sum(self.fact_by_code[code].nqf_credits for code in matched)
            )
            detail = f"{int(current)} of {int(required)} credits completed in this approved course pool."
            if explicit and current < required:
                remaining = sorted(explicit - set(matched))
                if remaining:
                    detail += (
                        " Remaining recorded options include: "
                        + ", ".join(remaining[:12])
                        + ("…" if len(remaining) > 12 else "")
                    )
            return RuleEvaluation(
                rule_id,
                label,
                current >= required,
                current,
                required,
                detail,
                status,
                1.0 if status == "verified" else 0.7,
                blocking,
                matched,
                source=source,
            )

        if rule_type == "maximum_credit_pool":
            filters = (
                rule.get("filters", {})
                if isinstance(rule.get("filters", {}), dict)
                else {}
            )
            explicit = set(_normalise_codes(rule.get("course_codes", [])))
            maximum = float(rule.get("maximum", rule.get("required", 0)))
            matched = sorted(
                code
                for code, fact in self.fact_by_code.items()
                if (not explicit or code in explicit)
                and _fact_matches_filters(code, fact, filters)
            )
            current = float(
                sum(self.fact_by_code[code].nqf_credits for code in matched)
            )
            return RuleEvaluation(
                rule_id,
                label,
                current <= maximum,
                current,
                maximum,
                f"{int(current)} credits completed in this pool; no more than {int(maximum)} are permitted.",
                status,
                1.0 if status == "verified" else 0.7,
                blocking,
                matched,
                source=source,
            )

        if rule_type == "same_department_credit_pool":
            filters = (
                rule.get("filters", {})
                if isinstance(rule.get("filters", {}), dict)
                else {}
            )
            transcript_filters = (
                rule.get("transcript_filters", {})
                if isinstance(rule.get("transcript_filters", {}), dict)
                else {}
            )
            explicit = set(_normalise_codes(rule.get("course_codes", [])))
            required = float(rule.get("required", 0))
            grouped: dict[str, list[str]] = {}
            grouped_credits: dict[str, int] = {}
            for code, fact in self.fact_by_code.items():
                if (explicit and code not in explicit) or not _fact_matches_filters(
                    code, fact, filters
                ):
                    continue
                group = fact.department.strip() or re.match(r"^[A-Z]+", code).group(0)
                grouped.setdefault(group, []).append(code)
                grouped_credits[group] = (
                    grouped_credits.get(group, 0) + fact.nqf_credits
                )
            provisional_groups: set[str] = set()
            if bool(rule.get("allow_unlisted_transcript_courses", False)):
                for result in self.student.credited_results():
                    if result.code in self.catalogue.courses or result.nqf_credits <= 0:
                        continue
                    pseudo = CourseFact(
                        code=result.code,
                        name=result.name,
                        nqf_credits=result.nqf_credits,
                        nqf_level=result.nqf_level,
                        prerequisites=[],
                        offered=[],
                        department=(
                            re.match(r"^[A-Z]+", result.code).group(0)
                            if re.match(r"^[A-Z]+", result.code)
                            else ""
                        ),
                    )
                    if not _fact_matches_filters(
                        result.code, pseudo, transcript_filters
                    ):
                        continue
                    group = (
                        re.match(r"^[A-Z]+", result.code).group(0)
                        if re.match(r"^[A-Z]+", result.code)
                        else ""
                    )
                    grouped.setdefault(group, []).append(result.code)
                    grouped_credits[group] = (
                        grouped_credits.get(group, 0) + result.nqf_credits
                    )
                    provisional_groups.add(group)
            best_group = max(grouped_credits, key=grouped_credits.get, default="")
            current = float(grouped_credits.get(best_group, 0))
            used = sorted(grouped.get(best_group, []))
            evaluation_status = status
            assumptions: list[str] = []
            confidence = 1.0 if status == "verified" else 0.7
            if best_group in provisional_groups:
                evaluation_status = _combine_status([status, "unverified"])
                confidence = 0.35
                assumptions.append(
                    "This discipline pool includes transcript-only courses whose programme recognition must be confirmed."
                )
            detail = (
                f"{int(current)} of {int(required)} credits completed in one discipline"
            )
            if best_group:
                detail += f" ({best_group})"
            detail += "."
            return RuleEvaluation(
                rule_id,
                label,
                current >= required,
                current,
                required,
                detail,
                evaluation_status,
                confidence,
                blocking,
                used,
                assumptions=assumptions,
                source=source,
            )

        if rule_type == "no_failures":
            filters = (
                rule.get("filters", {})
                if isinstance(rule.get("filters", {}), dict)
                else {}
            )
            explicit = set(_normalise_codes(rule.get("course_codes", [])))
            failures: list[str] = []
            for result in self.student.results:
                if not result.is_failed():
                    continue
                fact = self.catalogue.courses.get(result.code)
                if explicit and result.code not in explicit:
                    continue
                if (
                    fact is not None
                    and filters
                    and not _fact_matches_filters(result.code, fact, filters)
                ):
                    continue
                failures.append(result.code)
            complete = not failures
            note = (
                "No failed course attempts are recorded."
                if complete
                else "Failed attempt(s) recorded for: "
                + ", ".join(sorted(set(failures)))
                + "."
            )
            eval_status = status
            assumptions: list[str] = []
            if failures and bool(rule.get("condonable", False)):
                eval_status = "discretionary"
                note += " The handbook permits Senate to condone a failure for award purposes."
                assumptions.append(
                    "Any condonation must be confirmed from an official Senate or faculty decision."
                )
            return RuleEvaluation(
                rule_id,
                label,
                complete,
                0.0 if complete else float(len(set(failures))),
                0.0,
                note,
                eval_status,
                1.0 if eval_status == "verified" else 0.0,
                blocking,
                sorted(set(failures)),
                assumptions=assumptions,
                source=source,
            )

        if rule_type == "passed_mark_equivalents":
            filters = (
                rule.get("filters", {})
                if isinstance(rule.get("filters", {}), dict)
                else {}
            )
            explicit = set(_normalise_codes(rule.get("course_codes", [])))
            threshold = float(rule.get("minimum_mark", 75))
            required = float(rule.get("required", 1))
            equivalents = 0.0
            used: list[str] = []
            unknown: list[str] = []
            for code, result in self.result_by_code.items():
                fact = self.fact_by_code[code]
                if (explicit and code not in explicit) or not _fact_matches_filters(
                    code, fact, filters
                ):
                    continue
                if result.mark is None:
                    unknown.append(code)
                elif result.mark >= threshold:
                    unit = float(rule.get("equivalent_credit_unit", 0) or 0)
                    equivalents += (
                        (fact.nqf_credits / unit) if unit else _course_weight(code)
                    )
                    used.append(code)
            eval_status = (
                status if not unknown else _combine_status([status, "unverified"])
            )
            assumptions = (
                ["Numeric marks are missing for: " + ", ".join(sorted(unknown))]
                if unknown
                else []
            )
            return RuleEvaluation(
                rule_id,
                label,
                equivalents >= required,
                equivalents,
                required,
                f"{equivalents:g} of {required:g} full-course equivalents have marks of at least {threshold:g}%.",
                eval_status,
                1.0 if not unknown else 0.0,
                blocking,
                sorted(used),
                assumptions=assumptions,
                source=source,
            )

        if rule_type == "first_class_group":
            codes = _normalise_codes(rule.get("course_codes", []))
            required = int(rule.get("required", len(codes) or 1))
            threshold = float(rule.get("minimum_mark", 75))
            lower = float(rule.get("minimum_individual_mark", 70))
            allow_average = bool(rule.get("allow_group_average", True))
            candidates: list[tuple[str, CourseResult, CourseFact]] = []
            unknown: list[str] = []
            repeated_or_supp: list[str] = []
            for code in codes:
                result = self.result_by_code.get(code)
                fact = self.fact_by_code.get(code)
                if result is None or fact is None:
                    continue
                attempts = [
                    r
                    for r in self.student.results
                    if r.code == code and not r.is_pending()
                ]
                grade = " ".join(str(result.grade or "").strip().upper().split())
                if len(attempts) != 1 or grade == "SP":
                    repeated_or_supp.append(code)
                    continue
                if result.mark is None:
                    unknown.append(code)
                    continue
                candidates.append((code, result, fact))
            candidates.sort(
                key=lambda row: (row[1].mark or -1, row[2].nqf_credits), reverse=True
            )
            selected = candidates[:required]
            marks = [float(row[1].mark) for row in selected if row[1].mark is not None]
            complete = len(selected) >= required and all(
                mark >= threshold for mark in marks
            )
            average_used = False
            if not complete and allow_average and len(selected) >= required:
                credits = {row[2].nqf_credits for row in selected}
                if len(credits) == 1:
                    credit = next(iter(credits))
                    averaging_allowed = (required == 2 and credit in {24, 36}) or (
                        required == 4 and credit == 12
                    )
                    if (
                        averaging_allowed
                        and min(marks, default=0) >= lower
                        and sum(marks) / len(marks) >= threshold
                    ):
                        complete = True
                        average_used = True
            status_out = status
            assumptions: list[str] = []
            if unknown:
                status_out = _combine_status([status_out, "unverified"])
                assumptions.append(
                    "Numeric marks are missing for: " + ", ".join(sorted(unknown))
                )
            if repeated_or_supp:
                assumptions.append(
                    "Repeated or supplementary passes do not count for Science distinction: "
                    + ", ".join(sorted(repeated_or_supp))
                )
            detail = (
                f"{len(selected)} of {required} first-attempt course results assessed; "
            )
            if marks:
                detail += f"selected average {sum(marks)/len(marks):.2f}% and minimum {min(marks):.0f}%."
            else:
                detail += "no eligible numeric marks are available."
            if repeated_or_supp:
                detail += (
                    " Repeated or supplementary passes were excluded: "
                    + ", ".join(sorted(repeated_or_supp))
                    + "."
                )
            if average_used:
                detail += " The FB8.1(b) group-averaging concession was applied."
            return RuleEvaluation(
                rule_id,
                label,
                complete,
                float(len(selected)),
                float(required),
                detail,
                status_out,
                1.0 if status_out == "verified" else 0.0,
                blocking,
                [row[0] for row in selected],
                assumptions=assumptions,
                source=source,
            )

        if rule_type == "best_n_average":
            codes = _normalise_codes(rule.get("course_codes", []))
            mandatory = set(_normalise_codes(rule.get("mandatory_course_codes", [])))
            required = int(rule.get("required", 1))
            threshold = float(
                rule.get("minimum_average", rule.get("required_average", 0))
            )
            minimum_mark = float(rule.get("minimum_mark", 0))
            minimum_mark_count = int(rule.get("minimum_mark_count", 0))
            candidates: list[tuple[str, float, int]] = []
            missing_marks: list[str] = []
            for code in codes:
                result = self.result_by_code.get(code)
                fact = self.fact_by_code.get(code)
                if result is None or fact is None:
                    continue
                if result.mark is None:
                    missing_marks.append(code)
                    continue
                candidates.append((code, float(result.mark), max(1, fact.nqf_credits)))
            selected: list[tuple[str, float, int]] = []
            for code in mandatory:
                match = next((row for row in candidates if row[0] == code), None)
                if match is not None:
                    selected.append(match)
            remaining = [
                row
                for row in candidates
                if row[0] not in {item[0] for item in selected}
            ]
            remaining.sort(key=lambda row: row[1], reverse=True)
            selected.extend(remaining[: max(0, required - len(selected))])
            denominator = sum(weight for _, _, weight in selected)
            average = (
                sum(mark * weight for _, mark, weight in selected) / denominator
                if denominator
                else 0.0
            )
            mandatory_met = mandatory <= {code for code, _, _ in selected}
            mark_count = (
                sum(mark >= minimum_mark for _, mark, _ in selected)
                if minimum_mark
                else len(selected)
            )
            complete = (
                len(selected) >= required
                and mandatory_met
                and average >= threshold
                and mark_count >= minimum_mark_count
            )
            eval_status = status
            assumptions: list[str] = []
            if missing_marks:
                eval_status = _combine_status([eval_status, "unverified"])
                assumptions.append(
                    "Numeric marks are missing for: " + ", ".join(sorted(missing_marks))
                )
            detail = f"Best {len(selected)} of {required} eligible results average {average:.2f}%; at least {threshold:g}% is required."
            if mandatory and not mandatory_met:
                detail += (
                    " Mandatory course result(s) missing: "
                    + ", ".join(sorted(mandatory - {code for code, _, _ in selected}))
                    + "."
                )
            if minimum_mark_count:
                detail += f" {mark_count} of {minimum_mark_count} required results meet {minimum_mark:g}%."
            return RuleEvaluation(
                rule_id,
                label,
                complete,
                average,
                threshold,
                detail,
                eval_status,
                1.0 if eval_status == "verified" else 0.0,
                blocking,
                [code for code, _, _ in selected],
                assumptions=assumptions,
                source=source,
            )

        if rule_type == "first_attempt_weighted_average":
            explicit = set(_normalise_codes(rule.get("course_codes", [])))
            filters = (
                rule.get("filters", {})
                if isinstance(rule.get("filters", {}), dict)
                else {}
            )
            threshold = float(rule.get("minimum_average", rule.get("required", 0)))
            level_weights_raw = (
                rule.get("level_weights", {})
                if isinstance(rule.get("level_weights", {}), dict)
                else {}
            )
            level_weights = {
                int(level): float(weight) for level, weight in level_weights_raw.items()
            }
            include_failed_as_zero = bool(rule.get("include_failed_as_zero", True))
            first_by_code: dict[str, CourseResult] = {}
            for result in self.student.results:
                if result.is_pending() or result.code in first_by_code:
                    continue
                fact = self.catalogue.courses.get(result.code)
                if fact is None:
                    continue
                if explicit and result.code not in explicit:
                    continue
                if filters and not _fact_matches_filters(result.code, fact, filters):
                    continue
                first_by_code[result.code] = result
            weighted_total = 0.0
            denominator = 0.0
            used: list[str] = []
            unknown: list[str] = []
            for code, result in first_by_code.items():
                fact = self.catalogue.courses[code]
                multiplier = level_weights.get(fact.nqf_level, 1.0)
                weight = max(1, fact.nqf_credits) * multiplier
                normalised_grade = " ".join(
                    str(result.grade or "").strip().upper().split()
                )
                if normalised_grade in {"AB", "DPR", "INC", "EXA"}:
                    mark = 0.0
                elif result.mark is not None:
                    mark = float(result.mark)
                elif result.is_failed() and include_failed_as_zero:
                    mark = 0.0
                else:
                    unknown.append(code)
                    continue
                weighted_total += mark * weight
                denominator += weight
                used.append(code)
            if denominator == 0:
                note = "No first-attempt numeric results are available for this programme average."
                return RuleEvaluation(
                    rule_id,
                    label,
                    False,
                    0.0,
                    threshold,
                    note,
                    "unverified",
                    0.0,
                    blocking,
                    assumptions=[note],
                    source=source,
                )
            average = weighted_total / denominator
            eval_status = status
            assumptions: list[str] = []
            if unknown:
                eval_status = _combine_status([eval_status, "unverified"])
                assumptions.append(
                    "First-attempt numeric marks are missing for: "
                    + ", ".join(sorted(unknown))
                )
            return RuleEvaluation(
                rule_id,
                label,
                average >= threshold,
                average,
                threshold,
                f"First-attempt programme average is {average:.2f}%; at least {threshold:g}% is required.",
                eval_status,
                1.0 if eval_status == "verified" else 0.0,
                blocking,
                sorted(used),
                assumptions=assumptions,
                source=source,
            )

        if rule_type == "weighted_average":
            filters = (
                rule.get("filters", {})
                if isinstance(rule.get("filters", {}), dict)
                else {}
            )
            explicit = set(_normalise_codes(rule.get("course_codes", [])))
            threshold = float(rule.get("minimum_average", rule.get("required", 0)))
            matched_codes = sorted(
                code
                for code, fact in self.fact_by_code.items()
                if (not explicit or code in explicit)
                and _fact_matches_filters(code, fact, filters)
            )
            marked = [
                (self.result_by_code[code], max(1, self.fact_by_code[code].nqf_credits))
                for code in matched_codes
                if self.result_by_code[code].mark is not None
            ]
            missing_marks = [
                code for code in matched_codes if self.result_by_code[code].mark is None
            ]
            provisional_codes: list[str] = []
            # A cumulative degree average includes approved open/free electives.
            # Transcript-only electives are included provisionally only for an
            # unfiltered average; a filtered award rule must name its own pool.
            if not explicit and not filters:
                for result in self.provisional_results:
                    provisional_codes.append(result.code)
                    if result.mark is None:
                        missing_marks.append(result.code)
                    else:
                        marked.append((result, max(1, result.nqf_credits)))
            if not marked:
                note = "No numeric marks are available for the courses in this average."
                return RuleEvaluation(
                    rule_id,
                    label,
                    False,
                    0.0,
                    threshold,
                    note,
                    "unverified",
                    0.0,
                    blocking,
                    used_course_codes=matched_codes + provisional_codes,
                    assumptions=[note],
                    source=source,
                )
            denominator = sum(weight for _, weight in marked)
            average = (
                sum(result.mark * weight for result, weight in marked) / denominator
            )
            evaluation_status = status
            assumptions: list[str] = []
            confidence = 1.0 if status == "verified" else 0.7
            if provisional_codes:
                evaluation_status = _combine_status([status, "unverified"])
                confidence = min(confidence, 0.35)
                assumptions.append(
                    "The average includes transcript-only elective credits whose programme approval is not verified: "
                    + ", ".join(sorted(provisional_codes))
                )
            if missing_marks:
                evaluation_status = _combine_status([evaluation_status, "unverified"])
                confidence = 0.0
                assumptions.append(
                    "Some passed courses have no numeric mark and were excluded: "
                    + ", ".join(sorted(set(missing_marks)))
                )
            return RuleEvaluation(
                rule_id,
                label,
                average >= threshold,
                average,
                threshold,
                f"Credit-weighted average is {average:.2f}%; at least {threshold:g}% is required.",
                evaluation_status,
                confidence,
                blocking,
                sorted(set(matched_codes + provisional_codes)),
                assumptions=assumptions,
                source=source,
            )

        if rule_type == "passed_mark_count":
            filters = (
                rule.get("filters", {})
                if isinstance(rule.get("filters", {}), dict)
                else {}
            )
            explicit = set(_normalise_codes(rule.get("course_codes", [])))
            excluded = set(_normalise_codes(rule.get("exclude_course_codes", [])))
            threshold = float(rule.get("minimum_mark", 75))
            required = int(rule.get("required", 1))
            matched: list[str] = []
            unknown: list[str] = []
            for code, result in self.result_by_code.items():
                fact = self.fact_by_code[code]
                if (
                    code in excluded
                    or (explicit and code not in explicit)
                    or not _fact_matches_filters(code, fact, filters)
                ):
                    continue
                if result.mark is None:
                    unknown.append(code)
                elif result.mark >= threshold:
                    matched.append(code)
            eval_status = (
                status if not unknown else _combine_status([status, "unverified"])
            )
            assumptions = (
                ["Numeric marks are missing for: " + ", ".join(sorted(unknown))]
                if unknown
                else []
            )
            return RuleEvaluation(
                rule_id,
                label,
                len(matched) >= required,
                float(len(matched)),
                float(required),
                f"{len(matched)} of {required} passed courses have marks of at least {threshold:g}%.",
                eval_status,
                1.0 if not unknown else 0.0,
                blocking,
                sorted(matched),
                assumptions=assumptions,
                source=source,
            )

        if rule_type == "course_count":
            filters = (
                rule.get("filters", {})
                if isinstance(rule.get("filters", {}), dict)
                else {}
            )
            required = int(rule.get("required", 0))
            matched = sorted(
                code
                for code, fact in self.fact_by_code.items()
                if _fact_matches_filters(code, fact, filters)
            )
            return RuleEvaluation(
                rule_id,
                label,
                len(matched) >= required,
                float(len(matched)),
                float(required),
                f"{len(matched)} of {required} matching courses completed.",
                status,
                1.0 if status == "verified" else 0.7,
                blocking,
                matched,
                source=source,
            )

        if rule_type in {"all_of", "any_of"}:
            children = [
                self.evaluate(child)
                for child in rule.get("children", [])
                if isinstance(child, dict)
            ]
            if rule_type == "all_of":
                complete = all(child.complete for child in children)
                current = sum(1 for child in children if child.complete)
                required = len(children)
            else:
                complete = any(child.complete for child in children)
                current = 1 if complete else 0
                required = 1
            used = sorted(
                {
                    code
                    for child in children
                    if child.complete
                    for code in child.used_course_codes
                }
            )
            statuses = [child.status for child in children if child.complete] + [status]
            detail = f"{current} of {required} component requirements completed."
            if not complete:
                incomplete = [child.label for child in children if not child.complete]
                if incomplete:
                    detail += (
                        " Outstanding: "
                        + "; ".join(incomplete[:8])
                        + ("…" if len(incomplete) > 8 else "")
                    )
            return RuleEvaluation(
                rule_id,
                label,
                complete,
                float(current),
                float(required),
                detail,
                _combine_status(statuses),
                min([c.confidence for c in children] or [1.0]),
                blocking,
                used,
                source=source,
            )

        note = f"Unsupported curriculum rule type {rule_type!r}; manual verification is required."
        return RuleEvaluation(
            rule_id,
            label,
            True,
            0.0,
            1.0,
            note,
            "unverified",
            0.0,
            blocking,
            assumptions=[note],
            source=source,
        )
