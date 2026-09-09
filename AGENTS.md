# Curriculum Reasoning Engine Repository Map

CRE is the curriculum reasoning product/engine in the broader Cacisa Systems context. The repository is a modular monolith with a working UCT demonstrator and an executable synthetic Northstar reference institution. Both use the shared student workspace; CurriculumAdvisor remains an existing UCT/interface/package name.

## Current Areas

- `app.py`: FastAPI analysis, routes, projections, goals/simulation, readiness and administration; mounts Northstar orchestration.
- `engine/`: current curriculum/evidence models, scoping, assessment, recognition, reasoning, simulation and compatibility paths.
- `curriculum_reasoning_engine/institutions/` and `adapters/`: release/framework contracts and canonical transcript adapters.
- `curriculum_advisor/`: product metadata, student/advisor projections and guarded admin metadata overlays.
- `static/`: UCT and Northstar acquisition shells, `StudentWorkspace`, `StudentPortal`, `StudentLanguage`, and admin UI.
- `northstar/`: synthetic identity, native records, evidence adapter and package; distinct from `tests/fixtures/northstar/`.
- `data/uct_*`: represented UCT curriculum packages and source-extraction provenance.
- `catalogue_governance/` and `governance/`: technical verification, manifests, schemas and provenance records.
- `tools/`: builders and integrity tools; older browser rehearsal scripts need selector updates before current use.
- `tests/`: cross-institution, product, browser, UCT and compatibility regression contracts.

## Architectural Rules

- Preserve current UCT 2026 behaviour unless a change is explicitly part of a reviewed migration step.
- Do not turn provisional, discretionary, conflict, unverified, or `requires_verification` semantics into deterministic pass/fail rules.
- Do not silently repair source conflicts or normalize institutional data conflicts.
- Keep this as a modular monolith.
- Prefer compatibility shims and small PRs over a large directory migration.
- Treat UCT-specific transcript parsing, grade semantics, faculty names, award/readmission rules, and course-code assumptions as institutional implementation, not generic engine primitives.


## Current Documentation and Compatibility

- Start with `docs/README.md`, `docs/CURRENT_ARCHITECTURE.md`, `docs/CURRENT_LIMITATIONS.md` and `docs/RUNNING_AND_VALIDATION.md`.
- Shared workspace and policy-legibility reports are accepted milestone evidence; historical extraction plans are not current implementation instructions.
- Keep parser shims, legacy Report fields, route aliases, explicit frontend wrappers, projection-only helpers and independent Northstar fixtures until a separate compatibility review authorizes changes.
- Do not infer institutional approval from test/gate success or promote legacy Boolean summaries into canonical student truth.
- Follow artifact guidance in `docs/RUNNING_AND_VALIDATION.md`; generated review evidence and governed source files are not disposable merely because generated.
