# Product Extraction Plan

This plan prepares CurriculumAdvisor for extraction into the first standalone product of Cacisa Systems: Curriculum Reasoning Engine. It deliberately avoids the large-scale module migration.

## Dependency Analysis

Generic logic currently depends on UCT and institution-specific assumptions in these places:

- UCT: `app.py`, `curriculum_reasoning_engine/institutions/uct.py`, `curriculum_reasoning_engine/adapters/transcripts/uct.py`, `engine/catalogue.py`, `engine/parser.py`, `engine/utils.py`, `engine/rule_engine.py`, `engine/recognition.py`, `curriculum_advisor/product.py`, `static/`, tests, and build tools.
- Faculty name/key: `curriculum_reasoning_engine/institutions/uct.py` now owns UCT 2026 academic-unit metadata, external programme-label route inference, and stable academic-unit to legacy catalogue package mapping; `app.py` retains a compatibility projection, legacy cache keys, and route validation; `engine/scope.py` scope metadata; tests; `data/uct_*`.
- UCT transcript formatting: `curriculum_reasoning_engine/adapters/transcripts/uct.py`; `engine/parser.py` is a compatibility shim; upload and text analysis messages remain in `app.py`.
- UCT grade semantics: `curriculum_reasoning_engine/institutions/uct_grading.py` now owns pass/fail/pending interpretation. `engine/models.py` retains compatibility helpers, and some simulator/planner/reasoning paths still rely on those helpers when no explicit scheme is passed.
- UCT course codes: `engine/utils.py`, `engine/catalogue.py`, `engine/curriculum.py`, `engine/recognition.py`, `engine/rule_engine.py`, graph/planning logic where level and suffix matter.
- UCT award/readmission rules: `engine/rule_engine.py`, `engine/curriculum.py`, UCT catalogue JSON rule objects.
- Humanities-specific assumptions: `engine/catalogue.py` defaults, `engine/models.py` fields, `engine/rule_engine.py`, `engine/recognition.py`, `engine/utils.py`.
- Institution-specific terminology: product copy in `app.py`, `curriculum_advisor/product.py`, `static/`, model field names such as faculty/programme/major/NQF.

## Proposed Target Tree

```text
curriculum_reasoning_engine/
  __init__.py
  product/
    api.py
    workspaces/
      student.py
      advisor.py
      governance.py
  core/
    models.py
    catalogue.py
    programme_scope.py
    rule_language.py
    rule_evaluator.py
    recognition.py
    reasoning.py
    planner.py
    simulator.py
    knowledge_graph.py
  institutions/
    contract.py
    registry.py
    uct/
      releases/
        y2026/
          package.py
          config/
          data/
          policy/
  adapters/
    transcript/
      base.py
      uct.py
      csv.py
    sis/
  governance/
  compatibility/
```

Existing `engine.*` and `curriculum_advisor.*` modules should remain import-compatible until the migration is complete.

## PR-Sized Migration Sequence

1. Document and pin architecture baseline.
   - Files touched: `AGENTS.md`, `docs/architecture/*`, `docs/migration/PRODUCT_EXTRACTION_PLAN.md`.
   - Behaviour unchanged: all academic outputs.
   - Abstraction introduced: documented product/core/institution/adapter boundaries.
   - Tests required: full existing test suite.
   - Rollback: revert documentation files.

2. Add institution release identity without moving data.
   - Files touched: new `institutions/` or `engine/institutions.py`, `app.py`, tests.
   - Behaviour unchanged: same faculty list and catalogues.
   - Abstraction introduced: `InstitutionRelease` and `InstitutionRegistry` for `uct:2026`.
   - Tests required: readiness, bootstrap, faculty routing, catalogue loading.
   - Rollback: restore direct `FACULTY_META` and `load_catalogue` calls.
   - Status: implemented in `curriculum_reasoning_engine/institutions/`; `app.py` derives the legacy faculty projection from the active UCT 2026 release.

3. Extract UCT faculty metadata into the UCT release wrapper.
   - Files touched: institution wrapper, `app.py`, product tests.
   - Behaviour unchanged: same `/faculties` payload.
   - Abstraction introduced: release-provided academic unit cards.
   - Tests required: snapshot/field assertions for faculty payloads.
   - Rollback: move metadata back to `app.py`.
   - Status: implemented for metadata only; no data package or policy migration has occurred.

4. Introduce grading scheme service.
   - Files touched: `engine/models.py`, new grading config/module, simulator tests.
   - Behaviour unchanged: same pass/fail/pending decisions for UCT transcripts.
   - Abstraction introduced: `GradingScheme` injected or resolved from catalogue/release.
   - Tests required: grade token classification, transcript parsing, simulations.
   - Rollback: restore static grade sets.
   - Status: implemented as `ResultState`, `GradingScheme`, and `UCTGradingScheme`. `InstitutionRelease` exposes `grading_scheme`; `app.py` passes the active scheme to the main report path; `CourseResult` and `StudentRecord` retain legacy-compatible no-argument helpers.

5. Wrap current parser as UCT transcript adapter.
   - Files touched: `engine/parser.py`, new adapter module, `app.py`.
   - Behaviour unchanged: same parsed `StudentRecord` and same upload errors.
   - Abstraction introduced: `TranscriptAdapter`.
   - Tests required: parser tests, app upload/text tests.
   - Rollback: app calls old parser functions directly.
   - Status: implemented. `UCTTranscriptAdapter` owns UCT text/PDF parsing; `engine.parser` delegates to it for legacy callers.

6. Move programme/faculty inference behind UCT route policy.
   - Files touched: `engine/utils.py`, UCT policy module, `app.py`, route tests.
   - Behaviour unchanged: same inferred faculty/programme and mismatch errors.
   - Abstraction introduced: `RouteInferencePolicy`.
   - Tests required: faculty routing, app endpoints, transcript mismatch tests.
   - Rollback: re-export old `_infer_*` functions as direct implementations.
   - Status: implemented as `InstitutionRouteResolver` and `RouteResolution`. The UCT implementation owns the existing inference behaviour; `engine.utils._infer_*` remains as a compatibility shim.

6a. Move catalogue package resolution behind UCT release policy.
   - Files touched: `curriculum_reasoning_engine/institutions/*`, `app.py`, institution tests.
   - Behaviour unchanged: same catalogue data, public faculty keys, readiness output, programme scopes, and academic reports.
   - Abstraction introduced: `CatalogueDescriptor` and `InstitutionCatalogueResolver`.
   - Tests required: catalogue resolution, legacy loader compatibility, readiness/product/API tests, cache isolation, full suite.
   - Rollback: restore direct `load_catalogue(faculty_key)` in `app.py`.
   - Status: implemented. The active release resolves stable unit aliases and legacy keys to existing UCT catalogue packages before the app delegates to `engine.catalogue.load_catalogue`.

7. Introduce credit framework configuration.
   - Files touched: `engine/utils.py`, `engine/catalogue.py`, `engine/curriculum.py`, tests.
   - Behaviour unchanged: same NQF, suffix-weight, senior-level calculations for UCT.
   - Abstraction introduced: `CreditFramework`.
   - Tests required: rule engine, catalogue, recognition, simulator tests.
   - Rollback: restore direct helper calls.

8. Extract UCT recognition hooks.
   - Files touched: `engine/recognition.py`, UCT policy module, recognition tests.
   - Behaviour unchanged: same FB5.5 music-credit exclusions and provisional open-credit behaviour.
   - Abstraction introduced: recognition policy hook chain.
   - Tests required: recognition, Humanities catalogue, safety regressions.
   - Rollback: inline hook back into `engine/recognition.py`.

9. Extract UCT award/readmission/science policy branches.
   - Files touched: `engine/rule_engine.py`, UCT policy module, catalogue data if needed.
   - Behaviour unchanged: same requirements, statuses, warnings, and graduation status.
   - Abstraction introduced: policy requirement providers.
   - Tests required: rule engine, Science, Humanities, Law, Health, EBE, Commerce, reasoning.
   - Rollback: restore branches in `engine/rule_engine.py`.

10. Add institution package contract tests.
    - Files touched: new contract tests, package wrapper.
    - Behaviour unchanged: no production output changes.
    - Abstraction introduced: conformance suite for future institutions.
    - Tests required: package contract plus full suite.
    - Rollback: remove contract tests and wrapper.

11. Add compatibility package names.
    - Files touched: new `curriculum_reasoning_engine/` package, shim imports, packaging metadata.
    - Behaviour unchanged: old imports still work.
    - Abstraction introduced: target namespace.
    - Tests required: import tests and full suite.
    - Rollback: remove new namespace.

12. Begin physical migration in later work.
    - Files touched: not part of this task.
    - Behaviour unchanged: required before each moved module.
    - Abstraction introduced: real target tree.
    - Tests required: full suite after every move.
    - Rollback: use compatibility shims and git revert for the small PR.

## Current Architecture Summary

The current repository has a good modular-monolith foundation: facts are stored in JSON, programme scoping exists, and many rule outcomes preserve verification status. Its portability weakness is not the monolith; it is that UCT is still the implicit platform.

## Most Serious Portability Violations

1. UCT faculty/catalogue keys are still the public route identifiers, though their metadata, external-label route inference, and catalogue package resolution are now supplied by `InstitutionRelease`.
2. UCT transcript parsing is implemented by a UCT adapter, and UCT result interpretation is implemented by a UCT grading scheme, but `StudentRecord` remains the old downstream evidence object.
3. Some core/planner/simulator/reasoning paths still rely on no-argument classification compatibility helpers instead of receiving an explicit `GradingScheme`.
4. UCT major normalization and course-code interpretation still live in generic utilities.
5. UCT Humanities and Science policy branches live inside the main rule engine.
6. Direct legacy catalogue loading still assumes `data/{faculty_key}`; application catalogue access now begins from the active institution release.

## Baseline Portability Answer

Adding a second South African university tomorrow would no longer require independently redefining academic-unit metadata, programme-label routing, catalogue package mapping, transcript parsing entry points, or canonical grade/result-status interpretation inside `app.py` or `engine.models`, provided the new release, resolvers, adapter, and grading scheme were registered. It would still require modifying or extending direct catalogue loading, course-code level logic, recognition policy, UCT-specific rule branches, product copy, UI assumptions, and tests. After extraction, those should be supplied through an institution package, adapter, grading/credit configuration, and policy hooks.
