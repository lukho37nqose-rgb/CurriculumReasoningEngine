import unittest

from engine.utils import _infer_faculty_key

class InferFacultyKeyTests(unittest.TestCase):
    def test_commerce(self):
        self.assertEqual(_infer_faculty_key("Bachelor of Commerce"), "uct_commerce")
        self.assertEqual(_infer_faculty_key("BCom in Accounting"), "uct_commerce")
        self.assertEqual(_infer_faculty_key("Commerce (Information Systems)"), "uct_commerce")

    def test_engineering(self):
        self.assertEqual(_infer_faculty_key("Bachelor of Science in Engineering"), "uct_ebe")
        self.assertEqual(_infer_faculty_key("BSc(Eng) in Civil"), "uct_ebe")
        self.assertEqual(_infer_faculty_key("BSc (Eng) Electrical"), "uct_ebe")

    def test_humanities(self):
        self.assertEqual(_infer_faculty_key("Bachelor of Social Science"), "uct_humanities")
        self.assertEqual(_infer_faculty_key("Bachelor of Social Work"), "uct_humanities")
        self.assertEqual(_infer_faculty_key("Bachelor of Arts"), "uct_humanities")
        self.assertEqual(_infer_faculty_key("Bachelor of Social"), "uct_humanities")
        self.assertEqual(_infer_faculty_key("Social Science"), "uct_humanities")

    def test_science(self):
        self.assertEqual(_infer_faculty_key("Bachelor of Science"), "uct_science")
        self.assertEqual(_infer_faculty_key("BSc in Computer Science"), "uct_science")
        self.assertEqual(_infer_faculty_key("Science Faculty"), "uct_science")

    def test_law(self):
        self.assertEqual(_infer_faculty_key("Bachelor of Laws"), "uct_law")
        self.assertEqual(_infer_faculty_key("LLB"), "uct_law")
        self.assertEqual(_infer_faculty_key("Law Degree"), "uct_law")

    def test_case_insensitivity(self):
        self.assertEqual(_infer_faculty_key("BACHELOR OF COMMERCE"), "uct_commerce")
        self.assertEqual(_infer_faculty_key("bachelor of commerce"), "uct_commerce")
        self.assertEqual(_infer_faculty_key("bSc"), "uct_science")
        self.assertEqual(_infer_faculty_key("LaW"), "uct_law")

    def test_humanities_precedence_over_science(self):
        # Even though "science" is in the string, "social science" matches humanities first
        self.assertEqual(_infer_faculty_key("Bachelor of Social Science"), "uct_humanities")

    def test_fallback_default(self):
        self.assertEqual(_infer_faculty_key("Unknown Programme"), "unknown_faculty")
        self.assertEqual(_infer_faculty_key("Music Diploma"), "uct_humanities")

if __name__ == "__main__":
    unittest.main()
