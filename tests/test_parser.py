import inspect
import unittest
from unittest.mock import MagicMock, patch

from curriculum_reasoning_engine.adapters.transcripts import TranscriptAdapter
from curriculum_reasoning_engine.adapters.transcripts.uct import UCTTranscriptAdapter
from engine.parser import _parse_grade, parse_transcript_pdf, parse_transcript_text


class TestParseGrade(unittest.TestCase):
    def test_valid_grades(self):
        valid_grades = ["1", "2+", "2-", "3", "F", "P", "PA", "UP", "SP", "FS"]
        for grade in valid_grades:
            with self.subTest(grade=grade):
                self.assertEqual(_parse_grade(grade), grade)

    def test_valid_grades_with_whitespace(self):
        self.assertEqual(_parse_grade("  1  "), "1")
        self.assertEqual(_parse_grade("\tPA\n"), "PA")
        self.assertEqual(_parse_grade(" 2+ "), "2+")

    def test_invalid_grades(self):
        invalid_grades = ["A", "B", "4", "invalid", "", " ", "2", "1+", "0"]
        for grade in invalid_grades:
            with self.subTest(grade=grade):
                self.assertIsNone(_parse_grade(grade))

    def test_case_normalisation(self):
        self.assertEqual(_parse_grade("p"), "P")
        self.assertEqual(_parse_grade("pa"), "PA")
        self.assertEqual(_parse_grade("f"), "F")
        self.assertEqual(_parse_grade("Fs"), "FS")


class TestUCTTranscriptAdapter(unittest.TestCase):
    def test_uct_adapter_implements_transcript_contract(self):
        adapter = UCTTranscriptAdapter()
        self.assertIsInstance(adapter, TranscriptAdapter)
        self.assertEqual(adapter.adapter_id, "uct_transcript")
        self.assertEqual(adapter.institution_id, "uct")
        self.assertEqual(adapter.supported_formats, ("text", "pdf"))

    def test_parse_text_extracts_identity_programme_major_year_and_rows(self):
        text = "\n".join(
            [
                "Name: Nqose, Lukho Student Records Office",
                "Campus ID: abc123",
                "Programme: Bachelor of Social Science",
                "Specialisation: Philosophy Major",
                "Academic Year: 2024",
                "PHI 1024F Introduction To Philosophy 05 18 57 3",
                "POL 1004F Introduction To Politics 05 18 40 F",
                "Academic Year: 2025",
                "SOC 1001F Sociology 05 18 DPR",
                "ECO 1010F Microeconomics 05 18 DE",
                "MUS 1000F Music Practical 0",
            ]
        )

        student = UCTTranscriptAdapter().parse_text(text)

        self.assertEqual(student.student_id, "ABC123")
        self.assertEqual(student.name, "Lukho Nqose")
        self.assertEqual(student.programme, "Bachelor of Social Science")
        self.assertEqual(student.declared_majors, ["Philosophy"])
        self.assertEqual(
            [result.code for result in student.results],
            ["PHI1024F", "POL1004F", "SOC1001F", "ECO1010F", "MUS1000F"],
        )
        self.assertEqual(student.results[0].mark, 57)
        self.assertEqual(student.results[0].grade, "3")
        self.assertEqual(student.results[0].academic_year, 2024)
        self.assertEqual(student.results[1].mark, 40)
        self.assertEqual(student.results[1].grade, "F")
        self.assertEqual(student.results[2].mark, None)
        self.assertEqual(student.results[2].grade, "DPR")
        self.assertEqual(student.results[2].academic_year, 2025)
        self.assertEqual(student.results[3].grade, "DE")
        self.assertEqual(student.results[4].nqf_level, 0)
        self.assertEqual(student.results[4].nqf_credits, 0)
        self.assertEqual(student.results[4].grade, None)

    def test_empty_text_preserves_current_empty_record_behaviour(self):
        student = UCTTranscriptAdapter().parse_text("")
        self.assertEqual(student.student_id, "")
        self.assertEqual(student.name, "")
        self.assertEqual(student.programme, "")
        self.assertEqual(student.declared_majors, [])
        self.assertEqual(student.results, [])

    def test_engine_parser_text_shim_matches_uct_adapter(self):
        text = (
            "Name: Test, Student\n"
            "Programme: Bachelor of Arts\n"
            "HIS 1000F History 05 18 75 1"
        )
        self.assertEqual(
            parse_transcript_text(text), UCTTranscriptAdapter().parse_text(text)
        )


class TestParserPdf(unittest.TestCase):
    def test_parse_transcript_pdf_missing_pypdf(self):
        with patch.dict("sys.modules", {"pypdf": None}):
            with self.assertRaises(ImportError) as context:
                parse_transcript_pdf("dummy_path.pdf")
            self.assertIn("pypdf is required", str(context.exception))

    def test_uct_adapter_parse_pdf_success(self):
        mock_pdf_reader = MagicMock()
        mock_page_1 = MagicMock()
        mock_page_1.extract_text.return_value = "Name: Test, Student"
        mock_page_2 = MagicMock()
        mock_page_2.extract_text.return_value = "Programme: Bachelor of Arts"
        mock_pdf_reader.return_value.pages = [mock_page_1, mock_page_2]

        with patch.dict("sys.modules", {"pypdf": MagicMock(PdfReader=mock_pdf_reader)}):
            result = UCTTranscriptAdapter().parse_pdf("dummy_path.pdf")

        mock_pdf_reader.assert_called_once_with("dummy_path.pdf")
        self.assertEqual(result.name, "Student Test")
        self.assertEqual(result.programme, "Bachelor of Arts")

    def test_engine_parser_pdf_shim_matches_uct_adapter(self):
        mock_pdf_reader = MagicMock()
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "Name: Test, Student"
        mock_pdf_reader.return_value.pages = [mock_page]

        with patch.dict("sys.modules", {"pypdf": MagicMock(PdfReader=mock_pdf_reader)}):
            result = parse_transcript_pdf("dummy_path.pdf")

        self.assertEqual(result, UCTTranscriptAdapter().parse_text("Name: Test, Student"))

    def test_parse_transcript_pdf_none_text(self):
        mock_pdf_reader = MagicMock()
        mock_page_1 = MagicMock()
        mock_page_1.extract_text.return_value = None
        mock_pdf_reader.return_value.pages = [mock_page_1]

        with patch.dict("sys.modules", {"pypdf": MagicMock(PdfReader=mock_pdf_reader)}):
            result = parse_transcript_pdf("dummy_path.pdf")

        self.assertEqual(result, UCTTranscriptAdapter().parse_text(""))


def test_generic_transcript_contract_contains_no_uct_semantics():
    import curriculum_reasoning_engine.adapters.transcripts.base as base

    source = inspect.getsource(base).lower()
    for token in ("campus id", "specialisation", "uct_", "dpr", "bachelor of"):
        assert token not in source


def test_uct_parsing_is_owned_by_uct_adapter_not_engine_parser():
    import curriculum_reasoning_engine.adapters.transcripts.uct as uct
    import engine.parser as parser

    uct_source = inspect.getsource(uct)
    parser_source = inspect.getsource(parser)
    assert "Campus\\s+ID" in uct_source
    assert "UCTTranscriptAdapter" in parser_source
    assert "Campus\\s+ID" not in parser_source


if __name__ == "__main__":
    unittest.main()
