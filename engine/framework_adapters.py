"""Shared institutional-framework adapters with existing legacy fallbacks."""

from curriculum_reasoning_engine.institutions import AcademicCreditFramework, CourseLoadFramework

from .models import CourseFact, CourseResult
from .utils import _course_weight


def _credit_value(
    item: CourseFact | CourseResult,
    credit_framework: AcademicCreditFramework | None,
) -> int:
    return credit_framework.credit_value(item) if credit_framework is not None else item.nqf_credits


def _is_senior_level(
    item: CourseFact | CourseResult,
    credit_framework: AcademicCreditFramework | None,
) -> bool:
    return credit_framework.is_senior_level(item) if credit_framework is not None else item.nqf_level >= 6


def _load_equivalent(
    item: CourseFact | CourseResult | str,
    course_load_framework: CourseLoadFramework | None,
) -> float:
    return (
        course_load_framework.load_equivalent(item)
        if course_load_framework is not None
        else _course_weight(item if isinstance(item, str) else item.code)
    )
