"""
Knowledge Graph — represents courses and their relationships explicitly.
Supports dependency traversal, finding prerequisites, corequisites,
and what courses are unlocked or blocked by passing/failing a course.
"""
from typing import Set, List, Dict, Tuple, Optional
import re
from .models import Catalogue, CourseFact


class KnowledgeGraph:
    def __init__(self, catalogue: Catalogue):
        self.catalogue = catalogue
        self.courses = catalogue.courses
        # Build adjacency lists
        self.prereq_of: Dict[str, Set[str]] = {code: set() for code in self.courses}
        self.depends_on: Dict[str, Set[str]] = {code: set() for code in self.courses}

        for code, course in self.courses.items():
            for prereq in course.prerequisites:
                prereq = prereq.upper()
                if prereq in self.courses:
                    self.prereq_of[prereq].add(code)
                    self.depends_on[code].add(prereq)
                    continue

                # Handbook prerequisite text often omits semester suffixes.
                # Link each matching transcript variant as an unlock edge, but
                # preserve the raw stem as the dependency when several variants
                # exist so one failed variant is not treated as proof that every
                # route is blocked.
                match = re.fullmatch(r"([A-Z]{2,4}\d{4})", prereq)
                variants = (
                    sorted(c for c in self.courses if c.startswith(match.group(1)))
                    if match else []
                )
                for variant in variants:
                    self.prereq_of[variant].add(code)
                if len(variants) == 1:
                    self.depends_on[code].add(variants[0])
                else:
                    self.depends_on[code].add(prereq)

    def get_prerequisites(self, course_code: str) -> Set[str]:
        """Return the direct prerequisites of a course."""
        return self.depends_on.get(course_code, set())

    def get_all_prerequisites(self, course_code: str, visited: Optional[Set[str]] = None) -> Set[str]:
        """Return all direct and indirect prerequisites of a course (transitive closure)."""
        if visited is None:
            visited = set()
        prereqs = self.get_prerequisites(course_code)
        result = set(prereqs)
        for p in prereqs:
            if p not in visited:
                visited.add(p)
                result.update(self.get_all_prerequisites(p, visited))
        return result

    def get_unlocked_courses(self, course_code: str) -> Set[str]:
        """Return courses that directly require this course."""
        return self.prereq_of.get(course_code, set())

    def get_all_unlocked_courses(self, course_code: str, visited: Optional[Set[str]] = None) -> Set[str]:
        """Return all courses that directly or indirectly require this course (transitive closure)."""
        if visited is None:
            visited = set()
        unlocked = self.get_unlocked_courses(course_code)
        result = set(unlocked)
        for u in unlocked:
            if u not in visited:
                visited.add(u)
                result.update(self.get_all_unlocked_courses(u, visited))
        return result

    def get_dependency_path(self, start_code: str, end_code: str) -> List[str]:
        """Find a path of prerequisites from start_code to end_code using BFS."""
        if start_code == end_code:
            return [start_code]
        
        queue: List[List[str]] = [[start_code]]
        visited = {start_code}
        
        while queue:
            path = queue.pop(0)
            node = path[-1]
            
            for neighbor in self.prereq_of.get(node, set()):
                if neighbor == end_code:
                    return path + [neighbor]
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(path + [neighbor])
        return []

    def get_blocked_courses(self, failed_courses: Set[str]) -> Set[str]:
        """Return all courses that are blocked because one of their prerequisites is failed/not passed."""
        blocked = set()
        for code in self.courses:
            all_prereqs = self.get_all_prerequisites(code)
            if any(p in failed_courses for p in all_prereqs):
                blocked.add(code)
        return blocked
