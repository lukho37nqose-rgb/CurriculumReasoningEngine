import unittest

from engine.catalogue import load_catalogue
from engine.models import ChoiceGroup, CourseResult, MajorDefinition, StudentRecord
from engine.reasoning import (
    build_credit_reasoning_graph,
    build_major_completion_graph,
    build_total_nqf_credits_graph,
    detect_conflicts,
    evaluate_total_nqf_credits,
    imported_course_completion_conclusion,
)
from engine.rule_engine import compute_report


class ReasoningTraceTests(unittest.TestCase):
    def _student(self) -> StudentRecord:
        return StudentRecord(
            student_id="TST001",
            name="Test Student",
            programme="Bachelor of Social Science",
            declared_majors=[],
            results=[
                CourseResult(
                    code="PHI1024F",
                    name="Introduction To Philosophy",
                    nqf_level=5,
                    nqf_credits=18,
                    mark=65,
                    grade="2-",
                ),
                CourseResult(
                    code="POL1004F",
                    name="Introduction To Politics",
                    nqf_level=5,
                    nqf_credits=18,
                    mark=45,
                    grade="F",
                ),
            ],
        )

    def test_total_nqf_credit_reasoning_keeps_rule_and_transcript_evidence(self):
        conclusion = evaluate_total_nqf_credits(
            student=self._student(),
            required_credits=360,
            programme_key="regular_programme",
            programme_name="Regular Programme",
            assumptions=["Programme rules inferred from programme title."],
        )

        self.assertFalse(conclusion.result)
        self.assertEqual(conclusion.current, 18)
        self.assertEqual(conclusion.required, 360)
        self.assertEqual(conclusion.missing, 342)
        self.assertEqual(conclusion.status, "provisional")
        self.assertEqual(conclusion.confidence, 0.95)
        self.assertEqual(conclusion.applied_rules, ["REGULAR_PROGRAMME_TOTAL_NQF_CREDITS"])
        self.assertEqual(conclusion.assumptions, ["Programme rules inferred from programme title."])
        self.assertEqual(conclusion.depends_on, ["credit_awarded:PHI1024F"])
        self.assertIn("342 more needed", conclusion.explanation)
        self.assertTrue(any(e.source_id == "PHI1024F" for e in conclusion.evidence))
        self.assertFalse(any(e.source_id == "POL1004F" for e in conclusion.evidence))

    def test_total_credit_requirement_lives_in_reasoning_graph(self):
        graph = build_total_nqf_credits_graph(
            student=self._student(),
            required_credits=360,
            programme_key="regular_programme",
            programme_name="Regular Programme",
            assumptions=["Programme rules inferred from programme title."],
        )
        requirement = graph.conclusions["REGULAR_PROGRAMME_TOTAL_NQF_CREDITS"]

        self.assertEqual(requirement.layer, "requirement")
        self.assertEqual(requirement.fact_key, "requirement:REGULAR_PROGRAMME_TOTAL_NQF_CREDITS")
        self.assertEqual(requirement.depends_on, ["credit_awarded:PHI1024F"])
        self.assertEqual(len(graph.by_layer("academic_fact")), 4)
        self.assertEqual(graph.by_layer("requirement"), [requirement])

    def test_credit_reasoning_graph_composes_course_pass_into_credit_awarded(self):
        graph = build_credit_reasoning_graph(self._student())

        self.assertTrue(graph.conclusions["course_pass:PHI1024F"].result)
        self.assertEqual(graph.conclusions["course_pass:PHI1024F"].layer, "academic_fact")
        self.assertEqual(
            graph.conclusions["course_pass:PHI1024F"].fact_key,
            "course_completion:PHI1024F",
        )
        self.assertEqual(
            graph.conclusions["credit_awarded:PHI1024F"].depends_on,
            ["course_pass:PHI1024F"],
        )
        self.assertFalse(graph.conclusions["course_pass:POL1004F"].result)
        self.assertEqual(graph.conclusions["credit_awarded:POL1004F"].current, 0)

    def test_conflicting_course_completion_sources_require_manual_verification(self):
        transcript_pass = build_credit_reasoning_graph(
            StudentRecord(
                student_id="TST002",
                name="Conflict Student",
                programme="Bachelor of Social Science",
                declared_majors=[],
                results=[
                    CourseResult(
                        code="POL1004F",
                        name="Introduction To Politics",
                        nqf_level=5,
                        nqf_credits=18,
                        mark=65,
                        grade="2-",
                    )
                ],
            )
        ).conclusions["course_pass:POL1004F"]
        imported_incomplete = imported_course_completion_conclusion(
            course_code="POL1004F",
            completed=False,
            source_type="imported_planner",
            source_id="planner_snapshot_001",
        )

        conflicts = detect_conflicts([transcript_pass, imported_incomplete])

        self.assertEqual(len(conflicts), 1)
        conflict = conflicts[0]
        self.assertEqual(conflict.status, "conflict")
        self.assertEqual(conflict.confidence, 0.0)
        self.assertEqual(conflict.fact_key, "course_completion:POL1004F")
        self.assertEqual(
            conflict.applied_rules,
            ["CONFLICTING_EVIDENCE_REQUIRES_MANUAL_VERIFICATION"],
        )
        self.assertIn("Manual verification required", conflict.explanation)
        self.assertTrue(any(e.source_type == "transcript" for e in conflict.evidence))
        self.assertTrue(any(e.source_type == "imported_planner" for e in conflict.evidence))
        self.assertEqual(
            conflict.depends_on,
            [
                "course_pass:POL1004F",
                "imported_planner:planner_snapshot_001:course_completion:POL1004F",
            ],
        )

    def test_major_completion_graph_explains_required_and_choice_requirements(self):
        major = MajorDefinition(
            key="test_major",
            name="Test Major",
            qualification="BA",
            required_courses=["PHI1024F", "PHI2043F"],
            choice_groups=[
                ChoiceGroup(
                    label="Senior elective",
                    required=1,
                    courses=["POL1004F", "ASL1201S"],
                )
            ],
        )
        student = StudentRecord(
            student_id="TST003",
            name="Major Student",
            programme="Bachelor of Social Science",
            declared_majors=["Test Major"],
            results=[
                CourseResult("PHI1024F", "Intro Philosophy", 5, 18, 65, "2-"),
                CourseResult("ASL1201S", "Representations of Africa", 5, 18, 70, "2+"),
            ],
        )

        graph = build_major_completion_graph(student, major)
        required_done = graph.conclusions["major_required_course:test_major:PHI1024F"]
        required_missing = graph.conclusions["major_required_course:test_major:PHI2043F"]
        choice_group = graph.conclusions["major_choice_group:test_major:0"]
        major_complete = graph.conclusions["major_complete:test_major"]

        self.assertTrue(required_done.result)
        self.assertEqual(required_done.depends_on, ["course_pass:PHI1024F"])
        self.assertFalse(required_missing.result)
        self.assertEqual(required_missing.depends_on, [])
        self.assertTrue(choice_group.result)
        self.assertEqual(choice_group.current, 1)
        self.assertEqual(choice_group.depends_on, ["course_pass:ASL1201S"])
        self.assertFalse(major_complete.result)
        self.assertEqual(
            major_complete.depends_on,
            [
                "major_required_course:test_major:PHI1024F",
                "major_required_course:test_major:PHI2043F",
                "major_choice_group:test_major:0",
            ],
        )
        self.assertIn("1 requirement(s) outstanding", major_complete.explanation)

    def test_report_credits_requirement_includes_reasoning_trace(self):
        catalogue = load_catalogue("uct_humanities")
        report = compute_report(self._student(), catalogue)
        credits_req = next(r for r in report.requirements if r.id == "credits")

        self.assertFalse(credits_req.complete)
        self.assertEqual(credits_req.current, 15)
        self.assertEqual(credits_req.status, "unverified")
        self.assertEqual(credits_req.confidence, 0.5)
        self.assertEqual(credits_req.applied_rules, ["BSOCSC_REGULAR_TOTAL_NQF_CREDITS"])
        self.assertEqual(credits_req.depends_on, ["credit_awarded:PHI1024F"])
        self.assertEqual(credits_req.assumptions, ["The selected programme scope contains unresolved catalogue references."])
        self.assertIn("requirement incomplete", credits_req.explanation)
        self.assertTrue(any(e.source_type == "catalogue" for e in credits_req.evidence))
        self.assertTrue(any(e.source_id == "PHI1024F" for e in credits_req.evidence))


if __name__ == "__main__":
    unittest.main()
