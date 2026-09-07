"""Generic transcript adapter contract."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from engine.models import StudentRecord


@runtime_checkable
class TranscriptAdapter(Protocol):
    """Parse external transcript evidence into the current StudentRecord model."""

    adapter_id: str
    institution_id: str
    supported_formats: tuple[str, ...]

    def parse_text(self, text: str) -> StudentRecord:
        """Parse extracted transcript text."""

    def parse_pdf(self, pdf_path_or_file) -> StudentRecord:
        """Parse a transcript PDF or file-like object."""
