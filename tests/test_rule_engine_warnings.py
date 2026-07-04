import unittest

from engine.models import (
    Catalogue,
    CourseFact,
    CourseResult,
    MajorDefinition,
    StudentRecord,
)
from engine.rule_engine import _compute_warnings


class TestComputeWarnings(unittest.TestCase):
    def setUp(self):
        self.catalogue = Catalogue(
            courses={
                "CSC1015F": CourseFact(
                    "CSC1015F", "CS1", 18, 5, [], ["Semester 1"], "Computer Science"
                ),
                "MAM1000W": CourseFact(
                    "MAM1000W", "Math1", 36, 5, [], ["Whole year"], "Mathematics"
                ),
            },
            majors={
                "CS": MajorDefinition(
                    key="CS",
                    name="Computer Science",
                    qualification="BSc",
                    required_courses=[],
                ),
                "MATH": MajorDefinition(
                    key="MATH",
                    name="Mathematics",
                    qualification="BSc",
                    required_courses=[],
                ),
                "STATS": MajorDefinition(
                    key="STATS",
                    name="Statistics",
                    qualification="BSc",
                    required_courses=[],
                ),
            },
            programmes={},
            forbidden_combinations=[("CS", "MATH")],
        )

    def test_no_warnings(self):
        student = StudentRecord(
            student_id="TEST01",
            name="Test",
            programme="BSc",
            declared_majors=["CS", "STATS"],
            results=[
                CourseResult(
                    code="CSC1015F",
                    name="CS1",
                    nqf_level=5,
                    nqf_credits=18,
                    mark=75,
                    grade="1",
                ),
            ],
        )
        major_keys = ["CS", "STATS"]

        warnings = _compute_warnings(student, self.catalogue, major_keys)
        self.assertEqual(warnings, [])

    def test_failed_course_warning(self):
        student = StudentRecord(
            student_id="TEST01",
            name="Test",
            programme="BSc",
            declared_majors=["CS"],
            results=[
                CourseResult(
                    code="CSC1015F",
                    name="CS1",
                    nqf_level=5,
                    nqf_credits=18,
                    mark=45,
                    grade="F",
                ),
            ],
        )
        major_keys = ["CS"]

        warnings = _compute_warnings(student, self.catalogue, major_keys)
        self.assertEqual(len(warnings), 1)
        self.assertIn("CSC1015F (CS1): fail result 45%", warnings[0])

    def test_forbidden_major_combination_warning(self):
        student = StudentRecord(
            student_id="TEST01",
            name="Test",
            programme="BSc",
            declared_majors=["CS", "MATH"],
            results=[],
        )
        major_keys = ["CS", "MATH"]

        warnings = _compute_warnings(student, self.catalogue, major_keys)
        self.assertEqual(len(warnings), 1)
        self.assertIn(
            "Forbidden major combination: CS and MATH cannot be taken together.",
            warnings[0],
        )

    def test_major_not_in_catalogue_warning(self):
        student = StudentRecord(
            student_id="TEST01",
            name="Test",
            programme="BSc",
            declared_majors=["FAKE_MAJOR"],
            results=[],
        )
        major_keys = ["FAKE_MAJOR"]

        warnings = _compute_warnings(student, self.catalogue, major_keys)
        self.assertEqual(len(warnings), 1)
        self.assertIn("Major 'FAKE_MAJOR' is not in the course catalogue", warnings[0])

    def test_multiple_warnings(self):
        student = StudentRecord(
            student_id="TEST01",
            name="Test",
            programme="BSc",
            declared_majors=["CS", "MATH", "FAKE_MAJOR"],
            results=[
                CourseResult(
                    code="CSC1015F",
                    name="CS1",
                    nqf_level=5,
                    nqf_credits=18,
                    mark=45,
                    grade="F",
                ),
                CourseResult(
                    code="MAM1000W",
                    name="Math1",
                    nqf_level=5,
                    nqf_credits=36,
                    mark=30,
                    grade="F",
                ),
            ],
        )
        major_keys = ["CS", "MATH", "FAKE_MAJOR"]

        warnings = _compute_warnings(student, self.catalogue, major_keys)
        self.assertEqual(len(warnings), 4)

        warning_str = " ".join(warnings)
        self.assertIn("CSC1015F", warning_str)
        self.assertIn("MAM1000W", warning_str)
        self.assertIn("Forbidden major combination", warning_str)
        self.assertIn("FAKE_MAJOR", warning_str)


if __name__ == "__main__":
    unittest.main()
