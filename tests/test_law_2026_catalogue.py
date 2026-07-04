import unittest
from fastapi.testclient import TestClient

from app import app
from engine.catalogue import load_catalogue
from engine.models import CourseResult, StudentRecord
from engine.rule_engine import compute_report
from engine.scope import build_programme_scope


class LawCatalogueTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalogue = load_catalogue("uct_law")

    def scoped(self, programme, pathway=""):
        return build_programme_scope("uct_law", self.catalogue, programme, pathway)[0]

    @staticmethod
    def passed(scoped, codes, mark=76, year=2026):
        rows = []
        for code in codes:
            fact = scoped.courses[code]
            rows.append(
                CourseResult(
                    code, fact.name, fact.nqf_level, fact.nqf_credits, mark, None, year
                )
            )
        return rows

    def test_routes_and_scopes_are_verified(self):
        self.assertEqual(
            set(self.catalogue.programmes),
            {
                "llb_three_year_graduate",
                "llb_two_year_combined",
                "llb_four_year_undergraduate",
                "llb_five_year_continuing",
            },
        )
        self.assertEqual(
            self.catalogue.programmes["llb_five_year_continuing"].availability,
            "continuing_only",
        )
        for key, programme in self.catalogue.programmes.items():
            pathways = list(programme.pathways) or [""]
            for pathway in pathways:
                _, scope = build_programme_scope(
                    "uct_law", self.catalogue, key, pathway
                )
                self.assertEqual(scope.status, "verified")

    def test_complete_three_year_graduate_route_is_eligible(self):
        scoped = self.scoped("llb_three_year_graduate")
        programme = scoped.programmes["llb_three_year_graduate"]
        codes = programme.required_courses + [
            "CML4401H",
            "CML4602S",
            "PBL4502F",
            "PVL4505F",
        ]
        student = StudentRecord(
            "1",
            "Law Student",
            "LLB three-year graduate",
            [],
            self.passed(scoped, codes),
            "uct_law",
            "llb_three_year_graduate",
            "",
            3,
        )
        report = compute_report(student, scoped)
        self.assertEqual(report.graduation_status, "eligible")
        self.assertEqual(report.credits_completed, 504)
        self.assertTrue(report.distinction.qualification_eligible)
        self.assertEqual(report.distinction.subjects[0].major, "Magna cum laude")

    def test_research_elective_is_required(self):
        scoped = self.scoped("llb_three_year_graduate")
        programme = scoped.programmes["llb_three_year_graduate"]
        lecture_only = ["CML4501S", "CML4504S", "CML4506F", "CML4507S"]
        student = StudentRecord(
            "2",
            "Lecture Only",
            "LLB",
            [],
            self.passed(scoped, programme.required_courses + lecture_only),
            "uct_law",
            "llb_three_year_graduate",
            "",
            3,
        )
        report = compute_report(student, scoped)
        research = next(
            r for r in report.requirements if r.id == "curriculum:research_requirement"
        )
        self.assertFalse(research.complete)
        self.assertEqual(report.graduation_status, "not_eligible")

    def test_final_electives_cannot_exceed_54_credits(self):
        scoped = self.scoped("llb_three_year_graduate")
        programme = scoped.programmes["llb_three_year_graduate"]
        electives = [
            "CML4401H",
            "CML4602S",
            "PBL4502F",
            "PVL4505F",
            "CML4501S",
            "CML4504S",
            "CML4506F",
        ]
        student = StudentRecord(
            "3",
            "Too Many Electives",
            "LLB",
            [],
            self.passed(scoped, programme.required_courses + electives),
            "uct_law",
            "llb_three_year_graduate",
            "",
            3,
        )
        report = compute_report(student, scoped)
        maximum = next(
            r
            for r in report.requirements
            if r.id == "curriculum:maximum_final_electives"
        )
        self.assertFalse(maximum.complete)
        self.assertEqual(maximum.current, 63)

    def test_four_year_numeracy_pathways_are_separate(self):
        with_mam = self.scoped(
            "llb_four_year_undergraduate", "numeracy_course_required"
        )
        passed_test = self.scoped("llb_four_year_undergraduate", "numeracy_test_passed")
        self.assertIn(
            "MAM1013F",
            with_mam.programmes["llb_four_year_undergraduate"]
            .pathways["numeracy_course_required"]
            .required_courses,
        )
        self.assertNotIn(
            "MAM1013F",
            passed_test.programmes["llb_four_year_undergraduate"]
            .pathways["numeracy_test_passed"]
            .required_courses,
        )

    def test_route_specific_preliminary_prerequisites(self):
        graduate = self.scoped("llb_three_year_graduate")
        undergraduate = self.scoped(
            "llb_four_year_undergraduate", "numeracy_course_required"
        )
        self.assertEqual(graduate.courses["PBL2000W"].prerequisites, [])
        self.assertEqual(
            undergraduate.courses["PBL2000W"].prerequisites,
            ["PVL1003W", "PVL1004F", "PVL1008H"],
        )

    def test_four_year_route_can_be_completed_with_known_nonlaw_courses(self):
        scoped = self.scoped("llb_four_year_undergraduate", "numeracy_course_required")
        programme = scoped.programmes["llb_four_year_undergraduate"]
        nonlaw = [
            "ELL1013F",
            "MAM1013F",
            "AFS1100S",
            "ANS1400F",
            "SLL1060F",
            "SLL1061S",
            "ELL2000F",
            "ELL2001S",
        ]
        electives = ["CML4401H", "CML4602S", "PBL4502F", "PVL4505F"]
        student = StudentRecord(
            "4",
            "Undergraduate",
            "Bachelor of Laws",
            [],
            self.passed(scoped, programme.required_courses + nonlaw + electives),
            "uct_law",
            "llb_four_year_undergraduate",
            "numeracy_course_required",
            4,
        )
        report = compute_report(student, scoped)
        self.assertEqual(report.credits_completed, 637)
        self.assertEqual(report.graduation_status, "eligible")

    def test_four_failed_half_course_equivalents_trigger_risk(self):
        scoped = self.scoped("llb_three_year_graduate")
        failed_codes = ["CML4004S", "PBL4801F", "PBL4802F", "PVL4008H"]
        rows = []
        for code in failed_codes:
            fact = scoped.courses[code]
            rows.append(
                CourseResult(
                    code, fact.name, fact.nqf_level, fact.nqf_credits, 40, None, 2026
                )
            )
        student = StudentRecord(
            "5",
            "At Risk",
            "LLB",
            [],
            rows,
            "uct_law",
            "llb_three_year_graduate",
            "",
            3,
        )
        report = compute_report(student, scoped)
        self.assertTrue(report.exclusion_risk.at_risk)
        self.assertTrue(any("4" in reason for reason in report.exclusion_risk.reasons))

    def test_law_repeat_warning_does_not_cite_humanities_rule(self):
        scoped = self.scoped("llb_three_year_graduate")
        fact = scoped.courses["PVL1003W"]
        student = StudentRecord(
            "6",
            "Repeat",
            "LLB",
            [],
            [
                CourseResult(
                    fact.code,
                    fact.name,
                    fact.nqf_level,
                    fact.nqf_credits,
                    40,
                    None,
                    2025,
                ),
                CourseResult(
                    fact.code,
                    fact.name,
                    fact.nqf_level,
                    fact.nqf_credits,
                    45,
                    None,
                    2026,
                ),
            ],
            "uct_law",
            "llb_three_year_graduate",
            "",
            2,
        )
        report = compute_report(student, scoped)
        warning = " ".join(report.warnings)
        self.assertIn("FP7-FP11", warning)
        self.assertNotIn("Humanities rule F5", warning)

    def test_explicit_law_route_mismatch_is_rejected(self):
        client = TestClient(app)
        payload = {
            "faculty": "uct_law",
            "programme_key": "llb_four_year_undergraduate",
            "pathway_key": "numeracy_course_required",
            "student_id": "7",
            "name": "Mismatch",
            "programme": "LLB three-year graduate stream",
            "declared_majors": [],
            "results": [],
        }
        response = client.post("/analyse/json", json=payload)
        self.assertEqual(response.status_code, 422)
        self.assertIn("appears to match programme", response.json()["detail"])

    def test_law_faculty_is_enabled_in_api(self):
        client = TestClient(app)
        response = client.get("/faculties/uct_law")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "available")
        self.assertEqual(len(body["programmes"]), 4)


if __name__ == "__main__":
    unittest.main()
