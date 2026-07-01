import unittest

from engine.models import (
    Catalogue, CourseFact, CourseResult, ProgrammeRules,
    ReadmissionThreshold, StudentRecord,
)
from engine.rule_engine import _compute_exclusion_risk


class TestExclusionRisk(unittest.TestCase):
    def setUp(self):
        courses = {}
        for i in range(30):
            for level in (1, 2):
                code = f"AAA{level}00{i}F"
                courses[code] = CourseFact(
                    code, f"Course {i}", 18 if level == 1 else 20,
                    5 if level == 1 else 6, [], ["Semester 1"], "Test"
                )
        regular_thresholds = [
            ReadmissionThreshold(1, 5, 0),
            ReadmissionThreshold(2, 9, 0),
            ReadmissionThreshold(3, 13, 2),
            ReadmissionThreshold(4, 20, 10),
        ]
        extended_thresholds = [
            ReadmissionThreshold(1, 4, 0),
            ReadmissionThreshold(2, 8, 0),
            ReadmissionThreshold(3, 12, 2),
            ReadmissionThreshold(4, 15, 4),
            ReadmissionThreshold(5, 20, 10),
        ]
        self.catalogue = Catalogue(
            courses=courses,
            majors={},
            programmes={
                "regular_ba_bsocsc": ProgrammeRules(
                    key="regular_ba_bsocsc", name="Regular BA/BSocSc",
                    total_nqf_credits=360, level_7_nqf_credits=120,
                    semester_course_equivalents=20, senior_course_equivalents=10,
                    humanities_course_equivalents=12, required_majors=2,
                    required_humanities_majors=1,
                    readmission_thresholds=regular_thresholds,
                ),
                "extended_ba_bsocsc": ProgrammeRules(
                    key="extended_ba_bsocsc", name="Extended BA/BSocSc",
                    total_nqf_credits=360, level_7_nqf_credits=120,
                    semester_course_equivalents=20, senior_course_equivalents=10,
                    humanities_course_equivalents=12, required_majors=2,
                    required_humanities_majors=1,
                    readmission_thresholds=extended_thresholds,
                ),
            },
            forbidden_combinations=[],
        )

    def _create_results(self, count: int, passed: int, senior: int) -> list[CourseResult]:
        results = []
        for i in range(count):
            is_passed = i < passed
            is_senior = i < senior
            code = f"AAA{'2' if is_senior else '1'}00{i}F"
            results.append(CourseResult(
                code=code, name=f"Course {i}",
                nqf_level=6 if is_senior else 5,
                nqf_credits=20 if is_senior else 18,
                mark=60 if is_passed else 40,
                grade="2-" if is_passed else "F",
            ))
        return results

    def _create_student(self, attempted: int, passed: int, senior: int = 0) -> StudentRecord:
        return StudentRecord(
            student_id="TEST01", name="Test Student", programme="Some Programme",
            declared_majors=[], results=self._create_results(attempted, passed, senior),
        )

    def test_missing_programme(self):
        risk = _compute_exclusion_risk(self._create_student(5, 5), self.catalogue, "unknown_prog")
        self.assertFalse(risk.at_risk)
        self.assertFalse(risk.assessed)
        self.assertEqual(risk.status, "unverified")
        self.assertIn("No verified readmission threshold", risk.reasons[0])

    def test_regular_year_1_not_at_risk(self):
        self.assertFalse(_compute_exclusion_risk(self._create_student(8, 5), self.catalogue, "regular_ba_bsocsc").at_risk)

    def test_regular_year_1_at_risk(self):
        risk = _compute_exclusion_risk(self._create_student(8, 4), self.catalogue, "regular_ba_bsocsc")
        self.assertTrue(risk.at_risk)
        self.assertIn("requires at least 5", risk.reasons[0])

    def test_regular_year_2_not_at_risk(self):
        self.assertFalse(_compute_exclusion_risk(self._create_student(16, 9), self.catalogue, "regular_ba_bsocsc").at_risk)

    def test_regular_year_2_at_risk(self):
        risk = _compute_exclusion_risk(self._create_student(16, 8), self.catalogue, "regular_ba_bsocsc")
        self.assertTrue(risk.at_risk)
        self.assertIn("requires at least 9", risk.reasons[0])

    def test_regular_year_3_not_at_risk(self):
        self.assertFalse(_compute_exclusion_risk(self._create_student(24, 13, 2), self.catalogue, "regular_ba_bsocsc").at_risk)

    def test_regular_year_3_at_risk_passed(self):
        risk = _compute_exclusion_risk(self._create_student(24, 12, 2), self.catalogue, "regular_ba_bsocsc")
        self.assertTrue(risk.at_risk)
        self.assertEqual(len(risk.reasons), 1)

    def test_regular_year_3_at_risk_senior(self):
        risk = _compute_exclusion_risk(self._create_student(24, 13, 1), self.catalogue, "regular_ba_bsocsc")
        self.assertTrue(risk.at_risk)
        self.assertIn("senior", risk.reasons[0])

    def test_regular_year_3_at_risk_both(self):
        risk = _compute_exclusion_risk(self._create_student(24, 12, 1), self.catalogue, "regular_ba_bsocsc")
        self.assertTrue(risk.at_risk)
        self.assertEqual(len(risk.reasons), 2)

    def test_regular_year_4(self):
        risk = _compute_exclusion_risk(self._create_student(25, 12, 1), self.catalogue, "regular_ba_bsocsc")
        self.assertTrue(risk.at_risk)
        self.assertEqual(len(risk.reasons), 2)

    def test_extended_year_1_not_at_risk(self):
        self.assertFalse(_compute_exclusion_risk(self._create_student(8, 4), self.catalogue, "extended_ba_bsocsc").at_risk)

    def test_extended_year_1_at_risk(self):
        self.assertTrue(_compute_exclusion_risk(self._create_student(8, 3), self.catalogue, "extended_ba_bsocsc").at_risk)

    def test_extended_year_2_not_at_risk(self):
        self.assertFalse(_compute_exclusion_risk(self._create_student(16, 8), self.catalogue, "extended_ba_bsocsc").at_risk)

    def test_extended_year_2_at_risk(self):
        self.assertTrue(_compute_exclusion_risk(self._create_student(16, 7), self.catalogue, "extended_ba_bsocsc").at_risk)

    def test_extended_year_3_not_at_risk(self):
        self.assertFalse(_compute_exclusion_risk(self._create_student(24, 12, 2), self.catalogue, "extended_ba_bsocsc").at_risk)

    def test_extended_year_3_at_risk(self):
        self.assertTrue(_compute_exclusion_risk(self._create_student(24, 12, 1), self.catalogue, "extended_ba_bsocsc").at_risk)

    def test_extended_year_4_not_at_risk(self):
        self.assertFalse(_compute_exclusion_risk(self._create_student(25, 15, 4), self.catalogue, "extended_ba_bsocsc").at_risk)

    def test_extended_year_4_at_risk(self):
        risk = _compute_exclusion_risk(self._create_student(25, 14, 4), self.catalogue, "extended_ba_bsocsc")
        self.assertTrue(risk.at_risk)
        self.assertEqual(len(risk.reasons), 1)


if __name__ == "__main__":
    unittest.main()
