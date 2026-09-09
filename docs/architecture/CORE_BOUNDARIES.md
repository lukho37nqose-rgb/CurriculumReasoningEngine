> **Historical document**
> This file describes an earlier stage of CRE and is retained for development history. It should not be treated as the current architecture or product specification. See [current architecture](../CURRENT_ARCHITECTURE.md) and the [documentation index](../README.md). Original content below is preserved; counts, screenshots, commands and claims retain their original milestone context.

# Core Boundaries

The Curriculum Core should express curriculum primitives and evaluation mechanics without depending on UCT as an institution. Today, the boundary is partial: the core package contains useful generic components, but also UCT-specific policy and parsing assumptions.

## Generic Core Primitives

These concepts are suitable for the engine core:

- Student record as extracted facts.
- Course attempt/result as a raw academic evidence item.
- Course fact with credits, level, prerequisites, offerings, verification, provenance, and recognition notes.
- Programme, pathway, major, choice group, and curriculum-rule structures.
- Programme scope construction from selected programme/pathway and catalogue facts.
- Rule evaluation over explicit rule types.
- Recognition pipeline that distinguishes transcript facts from recognised programme credit.
- Planning, simulation, dependency graphing, and explanation views.
- Status vocabulary: `verified`, `provisional`, `unverified`, `discretionary`, `conflict`, and `requires_verification`.

## Institutional Configuration

These should become configuration supplied by an institution release:

- Grading scheme: pass, fail, pending, supplementary, absent, deferred, and special status tokens. Stage 5 implements this for UCT through `InstitutionRelease.grading_scheme`.
- Credit framework: NQF or another level system, credit units, course-equivalent rules, senior-course definition, suffix weights.
- Terminology: faculty, school, department, programme, plan, pathway, course, module, major.
- Academic units and organizational routing.
- Authority and verification rules: who can approve concessions, substitutions, double-counting, open elective credit, readmission, progression, and award exceptions.
- Programme labels and aliases used for transcript routing. Stage 2 implements this for UCT through `InstitutionRelease.route_resolver`.
- Major aliases and display-name normalization.
- Course-code grammar and level inference.

## Institutional Data Package

These belong in institution release data:

- Course catalogue facts.
- Programme requirements.
- Major requirements.
- Pathways and streams.
- Forbidden combinations.
- Cross-credit exclusions.
- Source extraction summaries and conflicts.
- Release manifests and checksums.
- Verification status and source provenance.
- Catalogue package resolution from stable academic-unit keys to release package descriptors. Stage 3 implements this for UCT while leaving `data/uct_*` in place.

## Adapters

These should be separate adapters:

- UCT transcript PDF parsing. Stage 4 implements this as `UCTTranscriptAdapter.parse_pdf`.
- UCT transcript text parsing. Stage 4 implements this as `UCTTranscriptAdapter.parse_text`.
- CSV import.
- SIS/API imports.
- Future transcript formats.

Adapters should return neutral `StudentRecord` and `CourseResult` facts plus adapter metadata. They should not compute graduation, repair source conflicts, or infer discretionary approvals.

## Current Boundary Violations

| File | Violation | Target |
| --- | --- | --- |
| `engine/models.py` | Legacy no-argument result-classification helpers still exist | Continue migrating core callers to explicit `GradingScheme` |
| `curriculum_reasoning_engine/institutions/uct_grading.py` | UCT grade pass/fail/pending sets now live here by design | Later move to physical UCT release package/config if needed |
| `engine/parser.py` | Legacy UCT transcript parser import path remains | Remove once callers use adapter boundary |
| `curriculum_reasoning_engine/adapters/transcripts/uct.py` | UCT transcript parsing now lives here by design | Later add non-UCT adapters without editing this implementation |
| `engine/utils.py` | UCT major aliases and suffix weights; legacy route-inference shims | Institution major normalization and credit framework config |
| `curriculum_reasoning_engine/institutions/uct.py` | UCT programme/faculty inference now lives here by design | Later split UCT release policy into smaller modules if needed |
| `engine/catalogue.py` | Direct legacy loader still supports `data/{faculty_key}` path and default `uct_humanities` | Later lower-level loader behind institution descriptors |
| `curriculum_reasoning_engine/institutions/uct.py` | Stable academic-unit to UCT catalogue package mapping now lives here by design | Later point descriptors at physical institution package paths |
| `engine/rule_engine.py` | UCT faculty branches and rule labels | Policy hooks or configured rule modules |
| `engine/recognition.py` | UCT Humanities FB5.5 encoded in generic recognition | UCT policy recognition hook |
| `app.py` | Active release is fixed to UCT 2026 and route-family checks remain local | Product reads institution registry; policy checks move behind release hooks |

## Non-Negotiable Semantics

The migration must preserve existing distinctions:

- Verified facts and conclusions remain distinct from provisional and unverified ones.
- Discretionary rules remain human-discretion conditions.
- Conflicts remain visible and are not silently resolved.
- `requires_verification` remains a graduation state when represented rules pass but verification is incomplete.
- Transcript-only/open elective credit remains provisional unless the institution package explicitly verifies it.
