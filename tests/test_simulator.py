import unittest
from unittest.mock import patch, MagicMock

from engine.models import StudentRecord, CourseResult, Catalogue, CourseFact, MajorDefinition, ProgrammeRules
from engine.knowledge_graph import KnowledgeGraph
from engine.simulator import SimulationEngine

class TestSimulationEngine(unittest.TestCase):
    def setUp(self):
        self.student = StudentRecord(
            student_id="TST001",
            name="Test Student",
            programme="Bachelor of Science",
            declared_majors=[],
            results=[
                CourseResult("CSC1015F", "Computer Science 1015", 5, 18, 65, "2-"),
            ],
        )
        self.catalogue = Catalogue(
            courses={
                "CSC1015F": CourseFact("CSC1015F", "Computer Science 1015", 18, 5, [], ["Semester 1"], "Computer Science", ""),
                "CSC1016S": CourseFact("CSC1016S", "Computer Science 1016", 18, 5, ["CSC1015F"], ["Semester 2"], "Computer Science", ""),
                "CSC2001F": CourseFact("CSC2001F", "Computer Science 2001", 24, 6, ["CSC1015F", "CSC1016S"], ["Semester 1"], "Computer Science", ""),
                "MAM1000W": CourseFact(code="MAM1000W", name="Math 1", nqf_credits=36, nqf_level=5, prerequisites=[], offered=["Full Year"], department="Math")
            },
            majors={
                "computer_science": MajorDefinition(key="computer_science", name="Computer Science", qualification="BSc", required_courses=["CSC1015F"]),
                "mathematics": MajorDefinition(key="mathematics", name="Mathematics", qualification="BSc", required_courses=["MAM1000W"])
            },
            programmes={
                "bsc": ProgrammeRules(
                    key="bsc", name="BSc", total_nqf_credits=360, level_7_nqf_credits=120,
                    semester_course_equivalents=20, senior_course_equivalents=10, humanities_course_equivalents=0,
                    required_majors=2, required_humanities_majors=0
                )
            },
            forbidden_combinations=[]
        )
        self.graph = KnowledgeGraph(self.catalogue)
        self.engine = SimulationEngine(self.student, self.catalogue, self.graph)

    @patch('engine.simulator.compute_report')
    def test_simulate_fail_course_existing(self, mock_compute_report):
        mock_compute_report.return_value = "MockReport"

        report, blocked = self.engine.simulate_fail_course("CSC1015F")

        args, _ = mock_compute_report.call_args
        sim_student = args[0]

        self.assertEqual(sim_student.results[0].code, "CSC1015F")
        self.assertEqual(sim_student.results[0].mark, 40)
        self.assertEqual(sim_student.results[0].grade, "F")

        self.assertIn("CSC1016S", blocked)
        self.assertIn("CSC2001F", blocked)
        self.assertEqual(report, "MockReport")

    @patch('engine.simulator.compute_report')
    def test_simulate_fail_course_new(self, mock_compute_report):
        mock_compute_report.return_value = "MockReport"

        report, blocked = self.engine.simulate_fail_course("CSC1016S")

        args, _ = mock_compute_report.call_args
        sim_student = args[0]

        self.assertEqual(len(sim_student.results), 2)
        new_course = sim_student.results[1]
        self.assertEqual(new_course.code, "CSC1016S")
        self.assertEqual(new_course.name, "Computer Science 1016")
        self.assertEqual(new_course.mark, 40)
        self.assertEqual(new_course.grade, "F")

        self.assertEqual(blocked, ["CSC2001F"])
        self.assertEqual(report, "MockReport")

    @patch('engine.simulator.compute_report')
    def test_simulate_fail_course_new_not_in_catalogue(self, mock_compute_report):
        mock_compute_report.return_value = "MockReport"

        report, blocked = self.engine.simulate_fail_course("MAM1000W")

        args, _ = mock_compute_report.call_args
        sim_student = args[0]

        self.assertEqual(len(sim_student.results), 2)
        new_course = sim_student.results[1]
        self.assertEqual(new_course.code, "MAM1000W")
        self.assertEqual(new_course.name, "Math 1")
        self.assertEqual(new_course.mark, 40)
        self.assertEqual(new_course.grade, "F")

        self.assertEqual(blocked, [])

    @patch('engine.simulator.compute_report')
    def test_simulate_pass_course_existing(self, mock_compute_report):
        mock_compute_report.return_value = "MockReport"

        report = self.engine.simulate_pass_course("CSC1015F", mark=80)

        args, _ = mock_compute_report.call_args
        sim_student = args[0]

        self.assertEqual(sim_student.results[0].code, "CSC1015F")
        self.assertEqual(sim_student.results[0].mark, 80)
        self.assertEqual(sim_student.results[0].grade, "1")
        self.assertEqual(report, "MockReport")

    @patch('engine.simulator.compute_report')
    def test_simulate_pass_course_new(self, mock_compute_report):
        mock_compute_report.return_value = "MockReport"

        report = self.engine.simulate_pass_course("CSC1016S", mark=72)

        args, _ = mock_compute_report.call_args
        sim_student = args[0]

        self.assertEqual(len(sim_student.results), 2)
        new_course = sim_student.results[1]
        self.assertEqual(new_course.code, "CSC1016S")
        self.assertEqual(new_course.mark, 72)
        self.assertEqual(new_course.grade, "2+")
        self.assertEqual(report, "MockReport")

    @patch('engine.simulator.compute_report')
    def test_simulate_future_semester(self, mock_compute_report):
        mock_compute_report.return_value = "MockReport"

        courses = [("CSC1016S", 65), ("MAM1000W", 78), ("CSC1015F", 55)]
        report = self.engine.simulate_future_semester(courses)

        args, _ = mock_compute_report.call_args
        sim_student = args[0]

        self.assertEqual(len(sim_student.results), 4)
        c1 = next(r for r in sim_student.results if r.code == "CSC1016S")
        self.assertEqual(c1.mark, 65)
        self.assertEqual(c1.grade, "2-")
        c2 = next(r for r in sim_student.results if r.code == "MAM1000W")
        self.assertEqual(c2.mark, 78)
        self.assertEqual(c2.grade, "1")
        # The historical attempt is preserved and the simulated future attempt
        # is appended rather than replacing transcript history.
        c3 = [r for r in sim_student.results if r.code == "CSC1015F"][-1]
        self.assertEqual(c3.mark, 55)
        self.assertEqual(c3.grade, "3")

    @patch('engine.simulator.compute_report')
    def test_simulate_switch_majors_single(self, mock_compute_report):
        mock_compute_report.return_value = "MockReport"
        self.student.declared_majors = ["Computer Science"]

        report = self.engine.simulate_switch_majors(["Mathematics"])

        self.assertEqual(self.student.declared_majors, ["Computer Science"])

        args, _ = mock_compute_report.call_args
        sim_student = args[0]
        self.assertEqual(sim_student.declared_majors, ["Mathematics"])
        self.assertEqual(report, "MockReport")

    @patch('engine.simulator.compute_report')
    def test_simulate_switch_majors_multiple(self, mock_compute_report):
        mock_compute_report.return_value = "MockReport"
        self.student.declared_majors = ["Computer Science"]

        report = self.engine.simulate_switch_majors(["Computer Science", "Mathematics"])

        self.assertEqual(self.student.declared_majors, ["Computer Science"])

        args, _ = mock_compute_report.call_args
        sim_student = args[0]
        self.assertEqual(sim_student.declared_majors, ["Computer Science", "Mathematics"])
        self.assertEqual(report, "MockReport")

    @patch('engine.simulator.compute_report')
    def test_simulate_switch_majors_empty(self, mock_compute_report):
        mock_compute_report.return_value = "MockReport"
        self.student.declared_majors = ["Computer Science"]

        report = self.engine.simulate_switch_majors([])

        self.assertEqual(self.student.declared_majors, ["Computer Science"])

        args, _ = mock_compute_report.call_args
        sim_student = args[0]
        self.assertEqual(sim_student.declared_majors, [])
        self.assertEqual(report, "MockReport")


    @patch('engine.simulator.compute_report')
    def test_simulate_switch_majors(self, mock_compute_report):
        mock_compute_report.return_value = "MockReport"

        report = self.engine.simulate_switch_majors(["Computer Science", "Mathematics"])

        args, _ = mock_compute_report.call_args
        sim_student = args[0]

        self.assertEqual(sim_student.declared_majors, ["Computer Science", "Mathematics"])
        self.assertEqual(report, "MockReport")

if __name__ == "__main__":
    unittest.main()
