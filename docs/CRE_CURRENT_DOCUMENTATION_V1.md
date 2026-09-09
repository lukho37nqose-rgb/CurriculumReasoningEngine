# CRE Current Documentation & Historical Labelling v1

**CLOSED as a bounded documentation slice.** Baseline: `73f07140765cc0d9a0db36b4fbcd1296cbb43c37`. Implemented 9 September 2026 using the accepted repository archaeology audit. No runtime cleanup or repository-wide cleanup completion is claimed.

> The repository now describes the current CRE architecture and product accurately, while clearly distinguishing active documentation, compatibility layers, historical material and unresolved institutional limitations.

## Completion report

| # | Requested finding | Result |
|---|---|---|
| 1 | README problems found | UCT-only identity, obsolete report ownership diagram/screenshots, old test totals, unconditional read-only admin description, universal API-version claim and missing Northstar entry. Audit sections 1–6 and 12 supplied the evidence. |
| 2 | README sections rewritten | Product, architecture, UCT, Northstar, current capabilities, non-claims, local run, validation/provenance, documentation map and limitations. |
| 3 | Current product framing | CRE is a governed institutional reasoning engine for curriculum, in the broader Cacisa Systems context; CurriculumAdvisor remains an existing compatibility/interface name. |
| 4 | Current architecture | Institution-specific acquisition, release/catalogue/evidence binding, Report reasoning, student/advisor projections and shared workspace. Physical paths and separate Northstar/UCT flows documented. |
| 5 | UCT framing | Working bounded undergraduate demonstrator over represented faculty packages; manual, uploaded and constructed evidence, without live SIS retrieval or blanket human fidelity validation. |
| 6 | Northstar framing | Executable synthetic reference institution for portability, evidence/institutional boundaries and shared student experience; materially non-UCT semantics; not production integration. |
| 7 | System-of-record wording | “CRE does not aim to become a durable student system of record.” Separate institutional/synthetic record ownership retained. |
| 8 | Authority wording | “Authoritative institutional records and formal decisions remain with the institution.” Eligibility, assessment and explicit award evidence do not confer decisions. |
| 9 | Capability claims | Represented cross-institution reasoning, uncertainty/conflict, recognition, progression, completion/graduation/award distinctions, source relationships, evidence receipts and shared presentation; implemented distinguished from institutionally validated. |
| 10 | Non-claims | No institutional approval, official advising status, production authentication, live UCT SIS, formal admission/registration decisions, complete UCT source fidelity or complete PPE fidelity. |
| 11 | Provenance wording | PASS_WITH_WARNINGS, checksum_mismatch_unverified_source_archive, declaration not supplied and NOT_ASSESSED retained. Technical success is not institutional source verification. |
| 12 | Historical docs labelled | 28 older architecture/planning/build/governance/portal/review documents receive consistent top notices. Original bodies preserved; two accepted presentation closure reports receive milestone-status notices instead. |
| 13 | Historical screenshots labelled | Artifact index and docs hierarchy identify old redesign, Northstar and PPE collections as historical; older closure comparisons retain explicit context. No image deleted or moved. |
| 14 | Current screenshot set | artifacts/policy-legibility/after/; README uses uct-overview-1440.png and northstar-overview-1440.png only. Shared-workspace images are the earlier accepted extraction snapshot. |
| 15 | Authority hierarchy | Current README/architecture/limitations/operations; accepted implementation records; governance evidence and principles; historical migration/build/review material. |
| 16 | Docs index | Added docs/README.md and artifacts/README.md, with current/historical classification and current pointers. |
| 17 | Launch instructions | Current Uvicorn root and /northstar entries, Node/Chromium requirements, ephemeral browser tests and actual --data-root guard option. Obsolete QA-script commands are explicitly historical, not silently removed from old reports. |
| 18 | Workflows | Names/triggers/actual target scope documented. Both run pytest; Node remains implicit; no workflow changed and no whole-tree lint/security claim added. |
| 19 | Compatibility | Parser exports, legacy Report/model/helper paths, route aliases, frontend wrappers/hidden controls, Northstar projection-only helper loading and separate test fixtures explained centrally. No deprecation or removal commitment. |
| 20 | Scale claims | Old standing test counts and catalogue totals removed from main README. Historical programme/faculty/test counts retain milestone labels; no new scale claims added. |
| 21 | Historical product claims | Older diagrams, unconditional admin/print claims, first-migration commands and certainty/availability statements remain visibly historical. No current chatbot framing was found to remove. |
| 22 | Known limitations | PPE aggregate third-year count, formal admission, registration/co-requisites and qualification taxonomy/classification surfaced; full source/authority and human-comprehension limits consolidated. |
| 23 | Artifact guidance | Ignored tmp/temp output for transient captures, local logs/caches/audit records kept out of Git, selected review images and governed generated files intentionally retained. No broad .gitignore rule added. |
| 24 | Link validation | 155 changed-document relative Markdown targets resolve, including both README images; 28 original historical bodies and balanced code fences checked. See validation record below. External services and URL/heading-anchor behavior are not certified. |
| 25 | Files changed | 39 Markdown files; exact list/reason mapping below. No deletions, moves or renames. |
| 26 | Runtime files touched | None. No evaluator, engine, adapter, frontend, API, manifest, rule, evidence, source-relationship or workflow file changed. |
| 27 | Intentionally unchanged | Scripts/tests, compatibility code, governed data, Northstar fixtures/records, all image bytes, checksum lists, build JSON, deployment and package manifests, .gitignore/.gitattributes and GitHub About metadata. AGENTS architectural rules preserved verbatim. |
| 28 | Later cleanup candidates | Previously audited stale browser scripts, definition-only frontend helpers, CSS overlap, old navigation metadata and duplicate screenshot paths remain candidates, not newly authorized removals. Explicit compatibility and provenance review still required. |
| 29 | Repository status | Documentation changes are left uncommitted on main over the named baseline; no commit or push requested for this slice. Only the listed Markdown paths differ. |
| 30 | Recommendation | CLOSED for current documentation and historical labelling. Repository cleanup as a whole is not complete. |

## Validation

- Five existing release-gate tests passed; no documentation-specific test suite was found in tracked tests.
- Direct catalogue manifest verification passed: content hash matches; no missing, changed or unexpected files.
- Partial release gate with --skip-quality: PASS_WITH_WARNINGS; manifest and source-reference checks pass, original warnings retained, institutional approval NOT_ASSESSED. This does not rerun or claim fresh full quality validation.
- Changed Markdown link/image paths, original historical bodies, code fences, whitespace/diff scope and unchanged non-document hashes checked before closure.
- No full pytest or browser rerun: no production file changed, and repository instructions do not require expensive checks for documentation-only work. Existing baseline validation is not presented as newly executed.

## Evidence and change map

The accepted archaeology report at the baseline established README/documentation corrections (sections 4 and 12), runtime/compatibility ownership (1–3, 6, 10–11), workflow/script guidance (5 and 7), historical/artifact provenance (8–9) and the documentation-first slice (13–16). No audit classification was converted into deletion authorization.

| File | Reason tied to accepted audit |
|---|---|
| `README.md` | outdated current claim; missing current architecture; obsolete screenshot/reference |
| `docs/CURRENT_ARCHITECTURE.md` | missing current architecture; compatibility layer needing explanation |
| `docs/CURRENT_LIMITATIONS.md` | outdated current claim; ambiguous file purpose; compatibility layer needing explanation |
| `docs/RUNNING_AND_VALIDATION.md` | misleading workflow/entry-point guidance; ambiguous file purpose |
| `docs/README.md` | historical material lacking a label; missing current architecture |
| `AGENTS.md` | outdated current claim; compatibility layer needing explanation |
| `BUILD_REPORT.md` | historical material lacking a label |
| `COMMERCE_BUILD.md` | historical material lacking a label |
| `DATA_ARCHITECTURE.md` | historical material lacking a label |
| `EBE_BUILD.md` | historical material lacking a label |
| `GOVERNANCE_FOUNDATION_BUILD_REPORT.md` | historical material lacking a label |
| `HEALTH_BUILD.md` | historical material lacking a label |
| `HUMANITIES_BUILD.md` | historical material lacking a label |
| `LAW_BUILD.md` | historical material lacking a label |
| `MERGE_VALIDATION_REPORT.md` | historical material lacking a label |
| `README_GOVERNANCE_FOUNDATION.md` | historical material lacking a label |
| `REDESIGN_BUILD_REPORT.md` | historical material lacking a label |
| `ROUTE_MANIFEST.md` | historical material lacking a label |
| `SCIENCE_BUILD.md` | historical material lacking a label |
| `docs/ARCHITECTURE.md` | historical material lacking a label |
| `docs/CURRICULUM_DATA_GOVERNANCE.md` | historical material lacking a label |
| `docs/DEPLOYMENT_AND_MIGRATION.md` | historical material lacking a label |
| `docs/FIRST_SAFE_MIGRATION.md` | historical material lacking a label |
| `docs/PRODUCT_DECISIONS.md` | historical material lacking a label |
| `docs/architecture/ADAPTER_CONTRACTS.md` | historical material lacking a label |
| `docs/architecture/CORE_BOUNDARIES.md` | historical material lacking a label |
| `docs/architecture/INSTITUTION_PACKAGE_CONTRACT.md` | historical material lacking a label |
| `docs/architecture/PRODUCT_ARCHITECTURE.md` | historical material lacking a label |
| `docs/migration/PRODUCT_EXTRACTION_PLAN.md` | historical material lacking a label |
| `northstar/HUMAN_LEGIBILITY.md` | historical material lacking a label |
| `northstar/STUDENT_INTERFACE.md` | historical material lacking a label |
| `artifacts/northstar-student-interface/CLOSURE.md` | historical material lacking a label |
| `artifacts/northstar-v1-browser/CLOSURE.md` | historical material lacking a label |
| `artifacts/ppe-browser-qa/REVIEW.md` | historical material lacking a label |
| `northstar/README.md` | outdated current claim; misleading workflow/entry-point guidance |
| `artifacts/README.md` | obsolete screenshot/reference; ambiguous file purpose |
| `docs/SHARED_STUDENT_WORKSPACE_V1.md` | historical material lacking a label; obsolete screenshot/reference |
| `docs/CRE_POLICY_LEGIBILITY_V1.md` | historical material lacking a label; obsolete screenshot/reference |
| `docs/CRE_CURRENT_DOCUMENTATION_V1.md` | documentation slice change record and validation |

## Later slices remain separate

Repair or retire old browser rehearsal scripts only after preserving their unique scenarios. Deduplicate screenshots only with a retained-path/link map and historical context. Review unused frontend helpers separately from explicit compatibility wrappers. Do not conflate similar engine modules or generated governed files with disposable output.

No parser, report-field, namespace, workflow, institutional-data or semantic cleanup is part of this closure.
