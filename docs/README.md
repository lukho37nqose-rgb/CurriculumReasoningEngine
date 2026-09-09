# Documentation index and authority hierarchy

Start with the [repository README](../README.md). This index separates current implementation descriptions from accepted milestone evidence, design intentions and development history. Source code and tests remain the implementation evidence; no document grants institutional authority.

The [validation contract](VALIDATION_CONTRACT.md) owns current CI/local/gate dependencies, scope boundaries and check-name stability.

## Current product, architecture and operations

1. [Current CRE architecture](CURRENT_ARCHITECTURE.md): physical layout, truth owners, active surfaces and intentionally retained compatibility interfaces.
2. [Current limitations and governance status](CURRENT_LIMITATIONS.md): institutional/source boundaries, known semantic gaps and release-warning meaning.
3. [Running, validation and artifact guidance](RUNNING_AND_VALIDATION.md): supported local/test/gate commands and actual workflow scope.
4. [Northstar reference institution](../northstar/README.md): synthetic records, adapter, demonstration boundaries and portability cases.

When a historical architecture document disagrees with this current map, use the current map and verify against code; do not implement a historical target directory tree as though it already existed.

## Accepted implementation and review records

- [Shared Student Workspace v1](SHARED_STUDENT_WORKSPACE_V1.md): accepted shared composition and shell boundaries; its navigation/copy and screenshots precede the policy-language slice.
- [Policy Legibility & Action Language v1](CRE_POLICY_LEGIBILITY_V1.md): subsequent accepted wording/disclosures, current presentation screenshot set, bounded fidelity gaps and human-review preparation.
- [Current Documentation & Historical Labelling v1](CRE_CURRENT_DOCUMENTATION_V1.md): documentation changes and validation for this slice.

These are dated milestone records, not rolling test counts. “No commit or push” in earlier closure text refers to that original task; the two presentation slices were later committed together at `73f07140765cc0d9a0db36b4fbcd1296cbb43c37`.

## Governance: implemented status versus design history

Use [current governance status](CURRENT_LIMITATIONS.md) and [verification commands](RUNNING_AND_VALIDATION.md) for today's technical boundary. The [active manifest](../governance/releases/uct-2026-uploaded-baseline.manifest.json) and [source-archive record](../governance/releases/source_archive_verification.json) are preserved evidence.

[Curriculum-data governance](CURRICULUM_DATA_GOVERNANCE.md) records governance principles and an earlier proposed process. It is not proof that institutional editor/approver roles or full publication workflows are implemented. Top-level historical checksum files are delivery snapshots, not the current gate.

## Historical / migration documents

- Earlier descriptions: [Architecture](ARCHITECTURE.md), [Product decisions](PRODUCT_DECISIONS.md), [Data architecture](../DATA_ARCHITECTURE.md), [route snapshot](../ROUTE_MANIFEST.md).
- Extraction-era plans/contracts: [Product architecture](architecture/PRODUCT_ARCHITECTURE.md), [Core boundaries](architecture/CORE_BOUNDARIES.md), [Institution package contract](architecture/INSTITUTION_PACKAGE_CONTRACT.md), [Adapter contracts](architecture/ADAPTER_CONTRACTS.md), [Product extraction plan](migration/PRODUCT_EXTRACTION_PLAN.md). Some contracts remain implemented; their stage inventories and target layouts are historical.
- Adoption history: [First safe migration](FIRST_SAFE_MIGRATION.md), [Deployment and migration](DEPLOYMENT_AND_MIGRATION.md), [governance foundation](../README_GOVERNANCE_FOUNDATION.md), [merge validation](../MERGE_VALIDATION_REPORT.md).
- Root build reports: [general build](../BUILD_REPORT.md), [redesign](../REDESIGN_BUILD_REPORT.md), [governance foundation build](../GOVERNANCE_FOUNDATION_BUILD_REPORT.md), [Commerce](../COMMERCE_BUILD.md), [EBE](../EBE_BUILD.md), [Health](../HEALTH_BUILD.md), [Humanities](../HUMANITIES_BUILD.md), [Law](../LAW_BUILD.md), [Science](../SCIENCE_BUILD.md). Counts and certainty/availability language describe their original scope, not current institutional validation.
- Earlier Northstar presentation: [Student interface](../northstar/STUDENT_INTERFACE.md), [Human legibility](../northstar/HUMAN_LEGIBILITY.md). Old browser commands/labels are superseded by the current validation guide.

## Screenshots and artifact collections

| Collection | Authority / use |
|---|---|
| `artifacts/policy-legibility/after/` | Canonical current accepted presentation screenshots; README selects UCT and Northstar desktop overviews |
| `artifacts/shared-workspace/` | Accepted earlier workspace extraction snapshot; before-state for policy language |
| `artifacts/northstar-legibility/`, `northstar-student-interface/`, `northstar-v1-browser/`, `ppe-browser-qa/` | Historical milestone/scenario evidence; retain labels, observations and closure records |
| `docs/redesign-*.png` | Historical UCT redesign, not current shared interface |

For artifact-specific status see [artifact index](../artifacts/README.md). [Hygiene Slice 1](REPOSITORY_HYGIENE_SLICE1.md) records the limited source-capture deduplication and remaining candidates. There is no general approval to delete other duplicate paths: historical links and review context remain dependencies.
