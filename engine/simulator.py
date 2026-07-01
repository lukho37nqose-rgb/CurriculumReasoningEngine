"""
Simulation Engine — simulates future academic states.
Allows students to ask "What if" questions and see the impact on their graduation status.
"""
import copy
from typing import List, Dict, Set, Tuple, Optional, Any
from .models import StudentRecord, CourseResult, Catalogue
from .knowledge_graph import KnowledgeGraph
from .rule_engine import compute_report, Report
from .reasoner import GraduateGoal, HonoursReadinessGoal


class SimulationEngine:
    def __init__(self, student: StudentRecord, catalogue: Catalogue, graph: KnowledgeGraph):
        self.student = student
        self.catalogue = catalogue
        self.graph = graph

    def _course_fact(self, course_code: str):
        course_code = course_code.strip().upper()
        course = self.catalogue.courses.get(course_code)
        if course is None:
            raise ValueError(
                f"Course {course_code!r} is not present in the selected faculty catalogue."
            )
        return course

    @staticmethod
    def _validate_mark(mark: int) -> int:
        mark = int(mark)
        if not 0 <= mark <= 100:
            raise ValueError("Simulated marks must be between 0 and 100.")
        return mark

    def simulate_fail_course(self, course_code: str) -> Tuple[Report, List[str]]:
        """Simulate failing a course. Returns the new report and a list of blocked courses."""
        course_code = course_code.strip().upper()
        course_fact = self._course_fact(course_code)
        sim_student = copy.deepcopy(self.student)
        
        # Find the course result and set mark to 40 (fail)
        found = False
        for r in reversed(sim_student.results):
            if r.code == course_code:
                r.mark = 40
                r.grade = "F"
                found = True
                break
        
        if not found:
            # Add a failed attempt
            sim_student.results.append(CourseResult(
                code=course_code,
                name=course_fact.name,
                nqf_level=course_fact.nqf_level,
                nqf_credits=course_fact.nqf_credits,
                mark=40,
                grade="F"
            ))

        # Compute new report
        new_report = compute_report(sim_student, self.catalogue)
        
        # Find blocked courses
        blocked = self.graph.get_all_unlocked_courses(course_code)
        blocked_list = sorted(list(blocked))

        return new_report, blocked_list

    def simulate_pass_course(self, course_code: str, mark: int = 75) -> Report:
        """Simulate passing a course with a specific mark."""
        course_code = course_code.strip().upper()
        mark = self._validate_mark(mark)
        course_fact = self._course_fact(course_code)
        sim_student = copy.deepcopy(self.student)
        
        # Find the course result and set mark to pass
        found = False
        grade = "1" if mark >= 75 else "2+" if mark >= 70 else "2-" if mark >= 60 else "3"
        
        for r in reversed(sim_student.results):
            if r.code == course_code:
                r.mark = mark
                r.grade = grade
                found = True
                break
        
        if not found:
            sim_student.results.append(CourseResult(
                code=course_code,
                name=course_fact.name,
                nqf_level=course_fact.nqf_level,
                nqf_credits=course_fact.nqf_credits,
                mark=mark,
                grade=grade
            ))

        return compute_report(sim_student, self.catalogue)

    def simulate_switch_majors(self, new_majors: List[str]) -> Report:
        """Simulate switching to a new set of majors."""
        sim_student = copy.deepcopy(self.student)
        sim_student.declared_majors = new_majors
        return compute_report(sim_student, self.catalogue)

    def simulate_future_semester(self, courses_to_take: List[Tuple[str, int]]) -> Report:
        """Simulate taking a set of courses next semester with expected marks."""
        sim_student = copy.deepcopy(self.student)
        
        for code, mark in courses_to_take:
            code = code.strip().upper()
            mark = self._validate_mark(mark)
            course_fact = self._course_fact(code)
            grade = "1" if mark >= 75 else "2+" if mark >= 70 else "2-" if mark >= 60 else "3" if mark >= 50 else "F"

            # Preserve the historical attempt record and append the simulated
            # future attempt.  Removing prior failures corrupts risk/history.
            sim_student.results.append(CourseResult(
                code=code,
                name=course_fact.name,
                nqf_level=course_fact.nqf_level,
                nqf_credits=course_fact.nqf_credits,
                mark=mark,
                grade=grade
            ))

        return compute_report(sim_student, self.catalogue)
