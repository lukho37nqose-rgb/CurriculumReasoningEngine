"""
Reasoning Engine — defines Goals and reasons about how to achieve them.
Supports backward chaining, gap analysis, pathway optimization,
and honours readiness assessment.
"""

from dataclasses import dataclass, field
from typing import Any

from curriculum_reasoning_engine.institutions import (
    AcademicCreditFramework,
    CourseCodeScheme,
    CourseLoadFramework,
    GradingScheme,
)

from .completion import CourseCompletionRecognitionInput, CourseCompletionResolver
from .curriculum import CurriculumEvaluator, _combine_status
from .knowledge_graph import KnowledgeGraph
from .models import (
    Catalogue,
    ProgrammeRules,
    StudentRecord,
)
from .prerequisites import PrerequisiteEvaluator, ProjectedCourseCompletions
from .utils import (
    _infer_programme_key,
    _normalise_major_keys,
)


@dataclass
class GoalRequirement:
    id: str
    label: str
    complete: bool
    current: Any
    required: Any
    detail: str = ""


@dataclass
class PathwayStep:
    semester: str
    courses: list[str]
    reason: str


@dataclass
class GoalReport:
    goal_id: str
    name: str
    complete: bool
    requirements: list[GoalRequirement]
    gap_description: str
    recommended_path: list[PathwayStep] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class Goal:
    def __init__(
        self,
        student: StudentRecord,
        catalogue: Catalogue,
        graph: KnowledgeGraph,
        grading_scheme: GradingScheme | None = None,
        credit_framework: AcademicCreditFramework | None = None,
        course_code_scheme: CourseCodeScheme | None = None,
        course_load_framework: CourseLoadFramework | None = None,
        completion_recognition: CourseCompletionRecognitionInput | None = None,
    ):
        self.student = student
        self.catalogue = catalogue
        self.graph = graph
        self.grading_scheme = grading_scheme
        self.credit_framework = credit_framework
        self.course_code_scheme = course_code_scheme
        self.course_load_framework = course_load_framework
        self.completion_recognition = completion_recognition
        self.completion = CourseCompletionResolver(student, catalogue, grading_scheme, completion_recognition)

    def evaluate(self) -> GoalReport:
        raise NotImplementedError


class GraduateGoal(Goal):
    def evaluate(self) -> GoalReport:
        """Evaluate graduation through the single authoritative rule engine.

        The previous implementation duplicated credit, major, and programme
        logic and could disagree with ``compute_report``.  Keeping one source
        of truth prevents the goals endpoint from issuing a more optimistic
        conclusion than the main analysis endpoint.
        """
        from .rule_engine import compute_report

        report = compute_report(
            self.student,
            self.catalogue,
            self.grading_scheme,
            self.credit_framework,
            self.course_code_scheme,
            self.course_load_framework,
            completion_recognition=self.completion_recognition,
        )
        programme_key = self.student.programme_key or _infer_programme_key(self.student.programme)
        prog = self.catalogue.programmes.get(programme_key)

        reqs = [
            GoalRequirement(
                id=req.id,
                label=req.label,
                complete=req.complete,
                current=req.current,
                required=req.required,
                detail=(f"{req.detail} Status: {req.status}." if req.status != "verified" else req.detail),
            )
            for req in report.requirements
        ]

        incomplete = [req.label for req in report.requirements if req.blocking and not req.complete]
        if incomplete:
            gap_desc = "Outstanding: " + "; ".join(incomplete) + "."
        elif report.graduation_status == "requires_verification":
            details = report.verification_messages or [
                "One or more programme conclusions remain provisional."
            ]
            gap_desc = "Manual verification required: " + " ".join(details)
        else:
            gap_desc = "All verified graduation requirements are met."

        path: list[PathwayStep] = []
        if prog and report.graduation_status != "eligible":
            major_keys = _normalise_major_keys(self.student.declared_majors, self.catalogue)
            major_goals = [
                CompleteMajorGoal(
                    self.student,
                    self.catalogue,
                    self.graph,
                    key,
                    self.grading_scheme,
                    self.credit_framework,
                    completion_recognition=self.completion_recognition,
                ).evaluate()
                for key in major_keys
            ]
            path = self._compute_graduation_path(major_goals, prog)

        return GoalReport(
            "graduate",
            "Graduate",
            report.graduation_eligible,
            reqs,
            gap_desc,
            path,
            metadata={
                "status": report.graduation_status,
                "verification_messages": report.verification_messages,
            },
        )

    def _compute_graduation_path(
        self, major_goals: list[GoalReport], prog: ProgrammeRules
    ) -> list[PathwayStep]:
        """Recommend only courses whose recorded prerequisites are met."""
        passed = self.completion.completed_codes()
        outstanding_courses = set()

        for code in prog.required_courses:
            if code not in passed:
                outstanding_courses.add(code)

        for major_goal in major_goals:
            for req in major_goal.requirements:
                if not req.complete and req.id.startswith("compulsory_"):
                    outstanding_courses.add(req.id.split("_", 1)[1])
                elif not req.complete and req.id.startswith("choice_"):
                    group_name = req.id.split("_", 1)[1]
                    major_key = major_goal.goal_id.split("_", 1)[1]
                    major_def = self.catalogue.majors.get(major_key)
                    if major_def:
                        for group in major_def.choice_groups:
                            if group.label == group_name:
                                for code in group.courses:
                                    if code not in passed:
                                        outstanding_courses.add(code)

        remaining = sorted(
            outstanding_courses,
            key=lambda code: (
                (
                    self.credit_framework.academic_level(self.catalogue.courses[code])
                    if self.credit_framework is not None
                    else self.catalogue.courses[code].nqf_level
                    if code in self.catalogue.courses
                    else 99
                ),
                code,
            ),
        )
        projected: set[str] = set()
        steps: list[PathwayStep] = []
        semester_num = 1
        max_per_semester = prog.max_courses_per_semester or 4

        while remaining and semester_num <= 8:
            semester_courses = []
            prerequisite_evaluator = PrerequisiteEvaluator(
                self.student,
                self.catalogue,
                self.grading_scheme,
                self.credit_framework,
                self.course_code_scheme,
                self.course_load_framework,
                projected_course_completions=ProjectedCourseCompletions(tuple(sorted(projected))),
                completion_recognition=self.completion_recognition,
            )
            for code in list(remaining):
                course = self.catalogue.courses.get(code)
                if course and prerequisite_evaluator.evaluate_for_course(course).outcome == "satisfied":
                    semester_courses.append(code)
                    if len(semester_courses) >= max_per_semester:
                        break

            if not semester_courses:
                steps.append(
                    PathwayStep(
                        semester=f"Semester {semester_num}",
                        courses=[],
                        reason=(
                            "No remaining course can be safely recommended from the "
                            "recorded prerequisites. Catalogue data or prerequisites "
                            "require manual review."
                        ),
                    )
                )
                break

            for code in semester_courses:
                remaining.remove(code)
                projected.add(code)

            steps.append(
                PathwayStep(
                    semester=f"Semester {semester_num}",
                    courses=semester_courses,
                    reason=(
                        "Recorded prerequisites are met for these outstanding "
                        "programme or major requirements."
                    ),
                )
            )
            semester_num += 1

        return steps


class CompleteMajorGoal(Goal):
    def __init__(
        self,
        student: StudentRecord,
        catalogue: Catalogue,
        graph: KnowledgeGraph,
        major_key: str,
        grading_scheme: GradingScheme | None = None,
        credit_framework: AcademicCreditFramework | None = None,
        course_code_scheme: CourseCodeScheme | None = None,
        course_load_framework: CourseLoadFramework | None = None,
        completion_recognition: CourseCompletionRecognitionInput | None = None,
    ):
        super().__init__(
            student,
            catalogue,
            graph,
            grading_scheme,
            credit_framework,
            course_code_scheme,
            course_load_framework,
            completion_recognition,
        )
        self.major_key = major_key

    def evaluate(self) -> GoalReport:
        major_def = self.catalogue.majors.get(self.major_key)
        if not major_def:
            return GoalReport(
                f"major_{self.major_key}",
                f"Complete {self.major_key}",
                False,
                [],
                f"Major '{self.major_key}' not found in catalogue",
                [],
            )

        if not major_def.required_courses and not major_def.choice_groups:
            return GoalReport(
                f"major_{self.major_key}",
                major_def.name,
                False,
                [],
                "Major requirements are missing from the catalogue; manual verification is required.",
                [],
                metadata={"status": "unverified"},
            )

        reqs = []
        gaps = []
        evaluator = CurriculumEvaluator(
            self.student, self.catalogue, self.grading_scheme, self.credit_framework,
            self.course_code_scheme, self.course_load_framework, self.completion_recognition,
        )
        statuses = [major_def.verification_status]

        # Compulsory courses
        for code in major_def.required_courses:
            evaluated = evaluator.evaluate({"type": "course", "course_codes": [code]})
            is_done = evaluated.complete
            statuses.append(evaluated.status)
            reqs.append(
                GoalRequirement(
                    id=f"compulsory_{code}",
                    label=f"Pass {code}",
                    complete=is_done,
                    current=1 if is_done else 0,
                    required=1,
                    detail=f"Compulsory course {code}. {evaluated.detail} Status: {evaluated.status}.",
                )
            )
            if not is_done:
                gaps.append(f"Pass {code}.")

        # Choice groups
        for group in major_def.choice_groups:
            evaluated = evaluator.evaluate({
                "type": "choose_n", "course_codes": group.courses, "required": group.required,
            })
            satisfied = evaluated.used_course_codes
            statuses.append(evaluated.status)
            needed = group.required
            is_done = len(satisfied) >= needed
            reqs.append(
                GoalRequirement(
                    id=f"choice_{group.label}",
                    label=group.label,
                    complete=is_done,
                    current=len(satisfied),
                    required=needed,
                    detail=f"{evaluated.detail} Status: {evaluated.status}.",
                )
            )
            if not is_done:
                gaps.append(f"Need {needed - len(satisfied)} more from {group.label}.")

        complete = all(r.complete for r in reqs)
        gap_desc = " ".join(gaps) if gaps else f"All requirements for {major_def.name} major met!"

        return GoalReport(
            f"major_{self.major_key}", major_def.name, complete, reqs, gap_desc,
            metadata={"status": _combine_status(statuses)},
        )


class HonoursReadinessGoal(Goal):
    """Provide an indicative average without claiming verified admission readiness."""

    def __init__(
        self,
        student: StudentRecord,
        catalogue: Catalogue,
        graph: KnowledgeGraph,
        major_key: str,
        grading_scheme: GradingScheme | None = None,
        credit_framework: AcademicCreditFramework | None = None,
        course_code_scheme: CourseCodeScheme | None = None,
        course_load_framework: CourseLoadFramework | None = None,
        completion_recognition: CourseCompletionRecognitionInput | None = None,
    ):
        super().__init__(
            student,
            catalogue,
            graph,
            grading_scheme,
            credit_framework,
            course_code_scheme,
            course_load_framework,
            completion_recognition,
        )
        self.major_key = major_key

    def evaluate(self) -> GoalReport:
        major_def = self.catalogue.majors.get(self.major_key)
        if not major_def:
            return GoalReport(
                f"honours_{self.major_key}",
                f"Honours Readiness: {self.major_key}",
                False,
                [],
                "Major not found in the selected catalogue.",
                [],
                metadata={"status": "unverified"},
            )

        def is_senior_course(code: str) -> bool:
            course = self.catalogue.courses.get(code)
            if course is None:
                return False
            return (
                self.credit_framework.is_senior_level(course)
                if self.credit_framework is not None
                else course.nqf_level >= 6
            )

        required_senior = {code for code in major_def.required_courses if is_senior_course(code)}
        option_senior = {
            code for group in major_def.choice_groups for code in group.courses if is_senior_course(code)
        }
        assessed_codes = set(required_senior)
        assessed_codes.update(code for code in option_senior if self.student.result_for(code) is not None)

        marks = []
        for code in sorted(assessed_codes):
            result = self.student.result_for(code)
            if result and result.mark is not None:
                marks.append(result.mark)

        current_average = sum(marks) / len(marks) if marks else 0.0
        indicative_threshold = 70.0
        major_goal = CompleteMajorGoal(
            self.student,
            self.catalogue,
            self.graph,
            self.major_key,
            self.grading_scheme,
            self.credit_framework,
            completion_recognition=self.completion_recognition,
        ).evaluate()
        indicative_threshold_met = (
            bool(marks) and current_average >= indicative_threshold and major_goal.complete
        )

        requirements = [
            GoalRequirement(
                "indicative_average",
                "Indicative senior-major average",
                current_average >= indicative_threshold,
                round(current_average, 1),
                indicative_threshold,
                (
                    "This is an unweighted indicative calculation. The relevant "
                    "department's admission threshold and weighting are not encoded."
                ),
            ),
            GoalRequirement(
                "major_complete",
                "Undergraduate major complete",
                major_goal.complete,
                1 if major_goal.complete else 0,
                1,
                major_goal.gap_description,
            ),
        ]

        gap_description = (
            "Indicative threshold met, but honours admission cannot be verified "
            "without department-specific rules, weighting, capacity, and selection criteria."
            if indicative_threshold_met
            else (
                "Honours readiness cannot be verified. The current indicative "
                f"senior-major average is {current_average:.1f}% and the major "
                "must also be complete. Department-specific criteria are not encoded."
            )
        )

        return GoalReport(
            f"honours_{self.major_key}",
            f"Honours Readiness: {major_def.name}",
            False,
            requirements,
            gap_description,
            metadata={
                "status": "unverified",
                "current_average": round(current_average, 1),
                "indicative_threshold": indicative_threshold,
                "indicative_threshold_met": indicative_threshold_met,
                "courses_assessed": len(marks),
            },
        )
