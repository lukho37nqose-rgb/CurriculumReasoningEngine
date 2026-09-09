> **Historical document**
> This file describes an earlier stage of CRE and is retained for development history. It should not be treated as the current architecture or product specification. See [current architecture](../CURRENT_ARCHITECTURE.md) and the [documentation index](../README.md). Original content below is preserved; counts, screenshots, commands and claims retain their original milestone context.

# Adapter Contracts

Adapters convert external evidence into neutral engine facts. They do not compute curriculum conclusions.

## Implemented Today

Stage 4 implements a transcript adapter boundary:

- `curriculum_reasoning_engine/adapters/transcripts/base.py` defines the generic `TranscriptAdapter` protocol.
- `curriculum_reasoning_engine/adapters/transcripts/uct.py` implements `UCTTranscriptAdapter`.
- `engine/parser.py` remains as a legacy compatibility shim exposing `parse_transcript_text`, `parse_transcript_pdf`, `_parse_grade`, and `_normalise_name`.
- `app.py` uses the active `InstitutionRelease.transcript_adapter` for PDF/text transcript ingestion.

`UCTTranscriptAdapter` preserves the former parser behaviour: it looks for labels such as `Name:`, `Campus ID:`, `Programme:`, and `Specialisation:`, parses UCT-style course rows, preserves raw marks/status tokens, and returns the existing `StudentRecord`.

## Target Adapter Interface

```python
class TranscriptAdapter:
    adapter_id: str
    institution_id: str | None
    supported_formats: tuple[str, ...]

    def parse_text(self, text: str) -> StudentRecord: ...
    def parse_pdf(self, pdf_path_or_file) -> StudentRecord: ...
```

Adapters should preserve raw evidence where useful, including unrecognized rows and warnings, but should not silently reinterpret conflicts. A richer `ParsedTranscript` wrapper is not implemented yet.

Stage 5 separates transcript evidence from result interpretation. `UCTTranscriptAdapter` still extracts raw marks and grade/status tokens into `CourseResult`; it does not decide whether a result passed, failed, or remains pending. UCT result interpretation is implemented by `UCTGradingScheme` and exposed through `InstitutionRelease.grading_scheme`.

## Adapter Types

- UCT PDF/text transcript adapter: implemented as `UCTTranscriptAdapter`.
- CSV adapter: normalized student/course attempt import.
- SIS/API adapter: institutional API integration.
- Future transcript adapters: institution-specific parsers registered by package.

## Contract Rules

- Adapter output is evidence, not a decision.
- Course attempts should preserve code, name, level, credits, mark, grade, academic year, and source metadata where available.
- Unknown grades should remain unknown rather than guessed.
- Adapter-specific route inference may suggest an institution/unit/programme, but product selection must still bind the student to an explicit route.
- Parser failures should expose adapter-level confidence or errors without implying academic ineligibility.

## Migration Path

1. Create `curriculum_reasoning_engine/adapters/transcripts/base.py` with the `TranscriptAdapter` protocol. Implemented.
2. Wrap current `parse_transcript_text` and `parse_transcript_pdf` as `UCTTranscriptAdapter`. Implemented.
3. Keep old parser functions as compatibility shims. Implemented.
4. Change `app.py` to resolve the adapter through institution release configuration. Implemented.
5. Add CSV adapter tests after UCT parser parity is locked.
