"""Legacy transcript parser compatibility surface.

The canonical UCT transcript parser now lives in
`curriculum_reasoning_engine.adapters.transcripts.uct`. These functions remain
for existing imports while the product extraction proceeds.
"""

from curriculum_reasoning_engine.adapters.transcripts.uct import (
    UCTTranscriptAdapter,
    normalise_name,
    parse_grade,
)
from engine.models import StudentRecord

_UCT_TRANSCRIPT_ADAPTER = UCTTranscriptAdapter()


def _parse_grade(grade_str: str) -> str | None:
    return parse_grade(grade_str)


def _normalise_name(raw: str) -> str:
    return normalise_name(raw)


def parse_transcript_text(text: str) -> StudentRecord:
    return _UCT_TRANSCRIPT_ADAPTER.parse_text(text)


def parse_transcript_pdf(pdf_path_or_file) -> StudentRecord:
    return _UCT_TRANSCRIPT_ADAPTER.parse_pdf(pdf_path_or_file)
