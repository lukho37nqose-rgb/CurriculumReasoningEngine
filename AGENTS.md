# Curriculum Reasoning Engine Repository Map

This repository currently ships the UCT 2026 implementation of CurriculumAdvisor. The product direction is Curriculum Reasoning Engine, with UCT 2026 becoming one institutional package rather than a dependency of generic engine code.

## Current Areas

- `app.py` is the FastAPI product boundary for the student workspace, faculty routing, analysis, simulation, goals, readiness, and admin endpoints.
- `static/` contains the browser UI for the student and admin workspaces.
- `curriculum_advisor/` contains product metadata, bootstrap payloads, and admin governance helpers.
- `engine/` contains the current curriculum models, catalogue loading, transcript parsing, programme scoping, rule evaluation, recognition, reasoning, simulation, and graph utilities.
- `data/uct_*` contains UCT 2026 faculty catalogue data and source-extraction artifacts.
- `catalogue_governance/` and `governance/` contain release integrity, operational offering, schema, template, and manifest support.
- `tools/` contains one-off and repeatable UCT catalogue build/guard scripts.
- `tests/` is the regression boundary for current UCT 2026 behaviour and outputs.

## Architectural Rules

- Preserve current UCT 2026 behaviour unless a change is explicitly part of a reviewed migration step.
- Do not turn provisional, discretionary, conflict, unverified, or `requires_verification` semantics into deterministic pass/fail rules.
- Do not silently repair source conflicts or normalize institutional data conflicts.
- Keep this as a modular monolith.
- Prefer compatibility shims and small PRs over a large directory migration.
- Treat UCT-specific transcript parsing, grade semantics, faculty names, award/readmission rules, and course-code assumptions as institutional implementation, not generic engine primitives.

## Planning Documents

- `docs/architecture/PRODUCT_ARCHITECTURE.md`
- `docs/architecture/CORE_BOUNDARIES.md`
- `docs/architecture/INSTITUTION_PACKAGE_CONTRACT.md`
- `docs/architecture/ADAPTER_CONTRACTS.md`
- `docs/migration/PRODUCT_EXTRACTION_PLAN.md`
