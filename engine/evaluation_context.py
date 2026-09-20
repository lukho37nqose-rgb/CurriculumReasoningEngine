"""Report-scoped inputs and lazy recognition state.

Inputs must remain stable for the lifetime of a context. Tuple caches protect
only the outer collections; contained result and catalogue objects are shared.
"""

from dataclasses import dataclass
from functools import cached_property

from curriculum_reasoning_engine.institutions import (
    AcademicCreditFramework,
    CourseCodeScheme,
    CourseLoadFramework,
    GradingScheme,
)

from .models import Catalogue, CourseFact, CourseResult, StudentRecord
from .recognition import (
    RecognitionExclusion,
    provisional_open_credit_results,
    recognised_credited_pairs,
)


@dataclass(frozen=True, eq=False)
class EvaluationContext:
    student: StudentRecord
    catalogue: Catalogue
    grading_scheme: GradingScheme | None
    credit_framework: AcademicCreditFramework | None
    course_code_scheme: CourseCodeScheme | None
    course_load_framework: CourseLoadFramework | None

    @cached_property
    def recognition(self) -> tuple[
        tuple[tuple[CourseResult, CourseFact], ...], tuple[RecognitionExclusion, ...]
    ]:
        pairs, exclusions = recognised_credited_pairs(
            self.student, self.catalogue, self.grading_scheme, self.course_code_scheme
        )
        return tuple(pairs), tuple(exclusions)

    @cached_property
    def provisional_results(self) -> tuple[CourseResult, ...]:
        return tuple(provisional_open_credit_results(
            self.student, self.catalogue, self.grading_scheme,
            self.credit_framework, self.course_code_scheme,
        ))
