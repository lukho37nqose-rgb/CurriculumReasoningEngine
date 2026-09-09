> **Historical document**
> This file describes an earlier stage of CRE and is retained for development history. It should not be treated as the current architecture or product specification. See [current architecture](../CURRENT_ARCHITECTURE.md) and the [documentation index](../README.md). Original content below is preserved; counts, screenshots, commands and claims retain their original milestone context.

# Product Architecture

This document describes the current UCT 2026 implementation and the intended Curriculum Reasoning Engine product architecture. It is descriptive where behaviour exists today and intentional where the target structure is not yet implemented.

## Implemented Today

The repository is a modular monolith centered on CurriculumAdvisor for UCT 2026.

- Product surface: `app.py`, `static/`, and `curriculum_advisor/`.
- Curriculum engine: `engine/`.
- Institutional data packages: `data/uct_commerce`, `data/uct_ebe`, `data/uct_health`, `data/uct_humanities`, `data/uct_law`, and `data/uct_science`.
- Governance support: `catalogue_governance/`, `governance/`, governance schemas, release manifests, and build reports.
- Catalogue build tooling: `tools/`.
- Institution release boundary: `curriculum_reasoning_engine/institutions/` defines immutable release metadata, route-resolution contracts, catalogue-resolution contracts, grading contracts, and the UCT 2026 academic-unit, route, catalogue, and grading implementations used by `app.py`.
- Regression boundary: `tests/`.

The current public top-level product partition is still a UCT faculty/catalogue key such as `uct_humanities`. Stage 1 routes product academic-unit metadata through `InstitutionRelease`. Stage 2 routes UCT programme-label and faculty-label inference through the active release's route resolver. Stage 3 routes application catalogue lookup through the active release's catalogue resolver before delegating to the existing `engine.catalogue.load_catalogue` implementation. Stage 4 routes transcript ingestion through the active release's UCT transcript adapter. Stage 5 routes UCT pass/fail/pending interpretation through the active release's grading scheme. Institution and academic year remain implicit in policy branches and physical data paths.

## Target Product Shape

The intended product is Curriculum Reasoning Engine, with CurriculumAdvisor becoming one product experience over that engine.

```text
curriculum_reasoning_engine/
  product/
    student_workspace/
    advisor_workspace/
    curriculum_governance/
  core/
    models.py
    programme_scope.py
    rule_language.py
    rule_evaluator.py
    recognition.py
    planning.py
    reasoning.py
    explanations.py
  institutions/
    contract.py
    uct/
      releases/
        y2026/
          config/
          data/
          policy/
  adapters/
    transcript/
      uct_pdf.py
      uct_text.py
      csv.py
    sis/
  governance/
  compatibility/
    engine/
    curriculum_advisor/
```

During migration, existing import paths should remain available through shims. The first priority is to make institution, release, adapter, and policy dependencies explicit without moving the whole tree.

## Architecture Inventory

| Area | Current files | Classification |
| --- | --- | --- |
| Product | `app.py`, `static/index.html`, `static/app.js`, `static/app.css`, `static/admin.html`, `static/admin.js`, `static/admin.css`, `curriculum_advisor/product.py` | Product |
| Product governance UI/API | `curriculum_advisor/admin_governance.py`, `curriculum_advisor/governance_status.py`, admin routes in `app.py` | Product, Curriculum governance |
| Institution release boundary | `curriculum_reasoning_engine/institutions/models.py`, `curriculum_reasoning_engine/institutions/routing.py`, `curriculum_reasoning_engine/institutions/catalogues.py`, `curriculum_reasoning_engine/institutions/grading.py`, `curriculum_reasoning_engine/institutions/uct.py`, `curriculum_reasoning_engine/institutions/uct_grading.py`, `curriculum_reasoning_engine/institutions/registry.py` | Institutional Configuration compatibility seam |
| Core models | `engine/models.py` | Curriculum Core evidence models with legacy grading compatibility helpers |
| Catalogue loading | `engine/catalogue.py` | Curriculum Core loader plus institutional package path convention |
| Programme scoping | `engine/scope.py` | Curriculum Core |
| Rule language/evaluator | `engine/curriculum.py` | Curriculum Core with some UCT-specific filter vocabulary |
| Rule report engine | `engine/rule_engine.py` | Curriculum Core plus UCT-specific policy branches |
| Recognition | `engine/recognition.py` | Curriculum Core plus UCT Humanities policy |
| Planning/simulation | `engine/planner.py`, `engine/simulator.py` | Curriculum Core |
| Reasoning/explanation | `engine/reasoning.py`, `engine/reasoner.py`, `engine/knowledge_graph.py` | Curriculum Core plus legacy duplication |
| Transcript adapter | `curriculum_reasoning_engine/adapters/transcripts/base.py`, `curriculum_reasoning_engine/adapters/transcripts/uct.py` | Adapter contract and UCT transcript adapter |
| Legacy transcript parser | `engine/parser.py` | Compatibility shim delegating to UCT transcript adapter |
| Utilities | `engine/utils.py` | Legacy mixed helper module: generic code parsing, UCT major aliases, and transitional route-inference shims |
| Extraction | `engine/extractor.py` | Adapter/extraction tooling, requires review before productization |
| UCT data | `data/uct_*` | Institutional Data Package |
| UCT source extraction | `data/uct_*/source_extraction` | Institutional Data Package provenance |
| Governance package | `catalogue_governance/*`, `governance/*` | Curriculum governance, institutional release governance |
| Build scripts | `tools/build_*_2026.py`, `tools/catalogue_guard.py` | UCT-specific package build tooling |
| Build reports | `*_BUILD.md`, `BUILD_REPORT.md`, `MERGE_VALIDATION_REPORT.md`, `SHA256SUMS.txt`, `PATCH_SHA256SUMS.txt` | Institutional release artifacts and legacy release documentation |
| Existing docs | `docs/*.md`, screenshots | Product and governance documentation; some legacy |
| Tests | `tests/*` | Regression constraints, mostly UCT 2026 |
| Deployment | `Procfile`, `railway.toml`, `requirements*.txt`, `pyproject*.toml`, `pytest.ini`, `.github/*` | Product operations and technical infrastructure |

## UCT-Specific Policy Inventory

- `app.py`: active UCT release selection, UCT transcript error copy, route-family checks for BA/BSocSc/LLB/BSc. Canonical faculty metadata, programme-label route inference, catalogue lookup, and transcript adapter selection now come from `InstitutionRelease`.
- `engine/models.py`: NQF-centric programme fields and legacy no-argument result-classification helpers. UCT grade categories now live in `curriculum_reasoning_engine/institutions/uct_grading.py`.
- `engine/utils.py`: UCT course suffix weights and UCT major aliases. `_infer_faculty_key` and `_infer_programme_key` remain as transitional shims delegating to the UCT release resolver.
- `curriculum_reasoning_engine/institutions/uct.py`: UCT programme and academic-unit label inference.
- `engine/catalogue.py`: `data/{faculty_key}` path convention, default `uct_humanities`, NQF inference from UCT-style course numbers, Humanities defaults.
- `curriculum_reasoning_engine/institutions/uct.py`: stable academic-unit aliases such as `humanities` mapped to existing UCT catalogue package keys such as `uct_humanities`.
- `curriculum_reasoning_engine/adapters/transcripts/uct.py`: UCT transcript labels, row formats, and raw status tokens.
- `engine/parser.py`: transitional parser shim for legacy imports.
- `engine/rule_engine.py`: UCT Humanities FB5.1, BA/BSocSc identity, Science co-major and overlap rules, FB3(e), exclusion/readmission/distinction assumptions.
- `engine/recognition.py`: Humanities FB5.5 South African College of Music limits and UCT course-code year-level inference.
- `tools/build_*_2026.py`: UCT faculty package construction.

## Critical Portability Question

If a second South African university were added tomorrow, these parts would require modification rather than configuration or a new adapter:

- `app.py`, because the active release is still selected as `uct:2026` and public route binding still uses legacy faculty/catalogue keys, even though canonical faculty metadata, route inference, and catalogue resolution are no longer independently redefined there.
- `engine.catalogue.load_catalogue`, because direct legacy callers can still resolve catalogues as `data/{faculty_key}/courses.json` and `degree_requirements.json`, with default `uct_humanities`.
- Transcript parsing for another institution would require a new adapter and release binding. It should not require editing `engine.parser`, which is now a UCT compatibility shim.
- Core callers that still use no-argument `CourseResult`/`StudentRecord` classification helpers, because they rely on the immutable UCT legacy default instead of explicit release grading. The canonical UCT grade policy is no longer hard-coded in `engine.models`.
- `engine.utils`, because major aliases, course-weight, and senior-level inference are UCT-specific; faculty/programme inference is now a compatibility shim.
- `engine.rule_engine`, because several policy branches check `catalogue.faculty_key == "uct_humanities"` or `"uct_science"` and embed UCT rule labels.
- `engine.recognition`, because Humanities music-credit recognition is hard-coded.
- `curriculum_advisor.product`, because product name and academic year are fixed to CurriculumAdvisor 2026.
- `static/` copy and route assumptions, depending on how strongly the UI exposes UCT faculties.
- Existing tests, because most fixtures and expectations are UCT 2026 outputs.

That list is the baseline portability gap. The target is that a second institution should require a new institution package, configured grade scheme, terminology, release manifest, policy hooks, and transcript/SIS adapter, not edits to generic core evaluation.
