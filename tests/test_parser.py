import unittest
from unittest.mock import patch, MagicMock

from engine.parser import _parse_grade, parse_transcript_pdf

class TestParseGrade(unittest.TestCase):
    def test_valid_grades(self):
        """Test that all valid grades are parsed correctly."""
        valid_grades = ["1", "2+", "2-", "3", "F", "P", "PA", "UP", "SP", "FS"]
        for grade in valid_grades:
            with self.subTest(grade=grade):
                self.assertEqual(_parse_grade(grade), grade)

    def test_valid_grades_with_whitespace(self):
        """Test that whitespace is stripped from valid grades."""
        self.assertEqual(_parse_grade("  1  "), "1")
        self.assertEqual(_parse_grade("\tPA\n"), "PA")
        self.assertEqual(_parse_grade(" 2+ "), "2+")

    def test_invalid_grades(self):
        """Test that invalid grades return None."""
        invalid_grades = ["A", "B", "4", "invalid", "", " ", "2", "1+", "0"]
        for grade in invalid_grades:
            with self.subTest(grade=grade):
                self.assertIsNone(_parse_grade(grade))

    def test_case_normalisation(self):
        """Transcript status tokens are normalised to uppercase."""
        self.assertEqual(_parse_grade("p"), "P")
        self.assertEqual(_parse_grade("pa"), "PA")
        self.assertEqual(_parse_grade("f"), "F")
        self.assertEqual(_parse_grade("Fs"), "FS")
from engine.parser import parse_transcript_pdf

class TestParserPdf(unittest.TestCase):
    def test_parse_transcript_pdf_missing_pypdf(self):
        """Test that missing pypdf raises an ImportError."""
        with patch.dict('sys.modules', {'pypdf': None}):
            with self.assertRaises(ImportError) as context:
                parse_transcript_pdf("dummy_path.pdf")
            self.assertIn("pypdf is required", str(context.exception))

    @patch("engine.parser.parse_transcript_text")
    def test_parse_transcript_pdf_success(self, mock_parse_text):
        """Test successful extraction and delegation to parse_transcript_text."""
        mock_pdf_reader = MagicMock()

        # Setup pages with some text
        mock_page_1 = MagicMock()
        mock_page_1.extract_text.return_value = "Page 1 Text"
        mock_page_2 = MagicMock()
        mock_page_2.extract_text.return_value = "Page 2 Text"

        mock_pdf_reader.return_value.pages = [mock_page_1, mock_page_2]

        mock_parse_text.return_value = "Mocked Record"

        with patch.dict('sys.modules', {'pypdf': MagicMock(PdfReader=mock_pdf_reader)}):
            result = parse_transcript_pdf("dummy_path.pdf")

            # Check PdfReader initialization
            mock_pdf_reader.assert_called_once_with("dummy_path.pdf")

            # Check parse_transcript_text call with concatenated text
            mock_parse_text.assert_called_once_with("Page 1 Text\nPage 2 Text")

            # Check result
            self.assertEqual(result, "Mocked Record")

    @patch("engine.parser.parse_transcript_text")
    def test_parse_transcript_pdf_none_text(self, mock_parse_text):
        """Test handling of pages where extract_text returns None."""
        mock_pdf_reader = MagicMock()

        # Setup page that returns None for text
        mock_page_1 = MagicMock()
        mock_page_1.extract_text.return_value = None

        mock_pdf_reader.return_value.pages = [mock_page_1]

        with patch.dict('sys.modules', {'pypdf': MagicMock(PdfReader=mock_pdf_reader)}):
            parse_transcript_pdf("dummy_path.pdf")

            # Check parse_transcript_text call with empty text and newline
            mock_parse_text.assert_called_once_with("")

if __name__ == '__main__':
    unittest.main()
