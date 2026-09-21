# Decision Replay Laboratory Report

Status: exploratory branch, not institution-ready.

This experiment implements one replayable evaluation for the test Northstar
release `northstar-fixture-2027`, scenario `clean` (`S1`). It deliberately leaves
curriculum, progression, distinction, graduation, and award semantics unchanged.

## 1. Chosen scenario

`clean` was selected because it exercises opaque course codes, an explicit 60%
grading scheme, independent credit and load frameworks, explicit academic
periods, curriculum completion, progression policy, qualification distinction
calculation, unresolved coverage, and synthetic source/package metadata. It is
more useful than a trivial pass case while remaining small enough to inspect.

The resulting report is not fully complete: the student has passed the supplied
courses, but missing capstone coverage leaves qualification completion,
graduation, and award unresolved. That uncertainty is part of the artifact.

## 2. Added prototype

- `decision_replay/core.py`: canonicalization, fingerprints, bundle creation,
  artifact projection, embedded-package replay, and comparison.
- `decision_replay/__main__.py`: `create` and `replay` commands.
- `decision_replay/__init__.py`: small experimental API.
- `tests/test_decision_replay.py`: conformance and failure-injection tests.
- `replay-bundle/`: generated inspectable sample bundle for `clean`.

Run from the repository root:

```text
python -m decision_replay create replay-bundle --scenario clean
python -m decision_replay replay replay-bundle
```

## 3. Bundle structure

```text
replay-bundle/
  bundle-manifest.json
  evaluation-request.json
  evidence-bundle.json
  release-reference.json
  decision-artifact.json
  source-index.json
  replay-report.json
```

`release-reference.json` uses embedded mode in v0. It contains the three
fixture package files under a filename-keyed `package` object. This is larger
than a reference-only bundle, but it makes the first replay independently
testable and makes package drift observable.

## 4. Evidence schema

The evidence bundle preserves the native Northstar envelope rather than CRE
objects:

```text
person / subject_reference
institution_id / release_id
route
modules[]: module, score, period, attempt
domains: optional institution-owned evidence domains
```

The bundle contains no scenario purpose, expected outcome, UI label, or expected
decision. The adapter reconstructs `StudentRecord`, coverage, and recognition
inputs from it during replay.

## 5. Decision artifact v0

The artifact contains:

- deterministic evaluation event ID;
- institution and release identity;
- release and evidence fingerprints;
- engine file hashes, commit, Python version, and artifact schema;
- curated conclusion records for curriculum, completion, graduation, award,
  distinction, and progression;
- outcome, assessment completeness, status, confidence, current/required;
- applied rule IDs, dependencies, evidence IDs, missing evidence, assumptions;
- source references and a node/edge trace;
- warnings and a small labelled compatibility projection.

It does not copy the product-facing student or advisor views into the canonical
artifact.

## 6. Report, ReasoningGraph, and DecisionArtifact

The current `Report` is the only complete evaluation aggregate, but it mixes
canonical assessments, legacy scalar summaries, compatibility fields, and
values that are not always epistemically authoritative. It is therefore used as
raw material, not treated as the artifact schema.

`ReasoningGraph` is closer to a causal representation, but the selected report
does not expose one complete graph covering curriculum, completion, graduation,
award, distinction, and progression. The prototype uses explicit report
dependencies where available and records the trace origin honestly. A future
engine should emit a complete evaluation graph directly.

The likely production direction is:

```text
pure evaluator -> DecisionArtifact -> Report/product projections
```

The prototype currently runs in the opposite direction:

```text
existing evaluator -> Report -> DecisionArtifact projection
```

That inversion is the most important architectural finding.

## 7. Canonicalization and fingerprints

The prototype uses SHA-256 over UTF-8 canonical JSON:

- dictionary keys sorted;
- compact separators;
- newline-terminated output;
- tuples and sets converted to arrays, with sets deterministically sorted;
- paths converted to POSIX strings;
- floats rounded to ten decimal places;
- `NaN` and infinity rejected;
- timestamps excluded from semantic fingerprints.

The guarantee is semantic/byte determinism for this JSON representation under
the captured engine and Python identity. It is not a guarantee of deterministic
execution across arbitrary Python versions, operating systems, or dependency
builds.

## 8. Replay and comparison

Replay loads and validates the bundle, reconstructs a temporary embedded
release, adapts native evidence, runs the existing evaluator, creates a fresh
artifact, and compares it with the recorded artifact.

Current statuses include:

- `EXACT_MATCH`;
- `INPUT_OR_RELEASE_MISMATCH`;
- `ENGINE_VERSION_MISMATCH`;
- `DECISION_DIFFERS`;
- `TRACE_DIFFERS`;
- `UNSUPPORTED_REPLAY`;
- `INVALID_BUNDLE`.

The report includes individual fingerprint checks, decision comparison,
trace comparison, event IDs, and errors. It does not reduce replay to a boolean.

## 9. Failure injection results

The tests deliberately perform these mutations:

| Mutation | Observed result |
|---|---|
| Change one evidence mark | `INPUT_OR_RELEASE_MISMATCH`; evidence fingerprint and decision differ |
| Change one embedded release rule | `INPUT_OR_RELEASE_MISMATCH`; release fingerprint differs |
| Tamper with recorded artifact | `INPUT_OR_RELEASE_MISMATCH`; artifact fingerprint differs |
| Change manifest engine metadata | `ENGINE_VERSION_MISMATCH` |
| Recreate equivalent bundle | byte-identical generated files |

This shows the bundle captures several causal inputs, but it also reveals a
limitation: package fingerprints identify that a package changed, not which
policy expression caused a changed conclusion. A production trace needs rule
identity and evaluated operands, not just a rule label.

## 10. Findings by category

### A. Existing concept sufficient

- `InstitutionRelease` is sufficient to identify the selected fixture release
  and its grading, credit, load, code, and period frameworks.
- Northstar's adapter boundary is sufficient to preserve native evidence without
  embedding expected answers.
- Existing package fingerprint and manifest ideas are reusable.
- Existing status vocabulary is useful for canonical outcomes.

### B. Small missing serialization/interface

- A stable serializer for canonical evidence and decision artifacts is missing.
- Release packages need a first-class export/import API instead of fixture-root
  mutation.
- Engine build identity needs a defined contract rather than ad hoc file hashes.

### C. Mixed canonical/presentation responsibility

- `Report` contains canonical assessments beside legacy scalar summaries.
- `app._to_dict` adds student and advisor projections while serializing a report.
- Product projections are correctly non-evaluating, but the boundary is not a
  persisted artifact boundary.

### D. Hidden reasoning input

- The evaluator depends on the exact framework objects passed by the caller.
- Catalogue loading and programme scoping affect the result but are not present
  as a complete serialized evaluation context.
- Coverage absence versus complete coverage changes unresolved versus negative
  outcomes.
- Some legacy fields remain populated even when their canonical epistemic state
  is unresolved.

### E. Non-determinism

- Generated IDs and timestamps require explicit treatment.
- Runtime/Python/dependency identity is not fully captured by Git commit.
- The current prototype uses temporary filesystem replay and fixture module
  global mutation, which is deterministic only under controlled execution.

### F. Release/versioning gap

- The generic governance CLI still verifies a fixed UCT baseline rather than a
  truly selected arbitrary release.
- Release identity is partly data and partly Python construction.
- Artifact schema, evaluator version, and policy package version need separate
  compatibility rules.

### G. Provenance gap

- The fixture release has useful source strings but no complete `ReleaseProvenance`
  object, so source indexing is reconstructed from package text.
- Source references do not yet identify every evidence witness and rule operand.

### H. Architectural dependency

- The replay module imports the test fixture package and temporarily changes its
  `ROOT` global. This is an intentional laboratory hack, not a production seam.
- The complete causal graph cannot be recovered without changing evaluator
  interfaces to emit it.

## 11. Historical replay requirements

The minimum credible historical replay package is:

1. immutable release/package contents or content-addressed retrieval;
2. canonical evidence bundle as it existed at evaluation time;
3. evaluation request and framework configuration;
4. engine/evaluator implementation identity plus runtime/dependency identity;
5. artifact schema version and canonicalization rules;
6. source index and provenance status;
7. correction, supersession, or migration metadata when later releases differ.

A Git commit alone is insufficient. A 2026 decision must retain the 2026
release package even after 2027 becomes the active release. A future production
system may reference immutable package storage, but v0 embeds the package to
avoid making retrieval availability part of replay correctness.

## 12. What to discard before production

- global mutation of the fixture module's `ROOT`;
- dependency on `tests/fixtures` from runtime infrastructure;
- heuristic outcome reconstruction from legacy report fields;
- the ad hoc source-index reconstruction;
- treating engine source-file hashes as a complete runtime identity;
- the small compatibility projection inside the artifact;
- the assumption that a flat list of conclusion nodes is a complete reasoning
  graph.

## 13. What deserves production migration

- a first-class canonical evidence bundle contract;
- an immutable release export/import interface;
- a pure evaluator context object containing every reasoning input;
- a first-class `DecisionArtifact` emitted by the evaluator;
- trace nodes with evaluated operands, evidence witnesses, source links, and
  explicit missing/unknown/conflict causes;
- versioned canonicalization and comparison rules;
- replay reports as structured governance records;
- conformance tests that use native institution adapters and never UI payloads.

## 14. Recommended production architecture

```text
Institution adapter
        -> CanonicalEvidenceBundle
Release resolver
        -> Immutable ReleasePackage
EvaluationContext(release, evidence, options, engine identity)
        -> Pure evaluator
        -> DecisionArtifact
        -> Report/student/advisor/governance projections
```

The evaluator should accept a fully explicit `EvaluationContext`, return a
DecisionArtifact, and optionally expose a graph/trace builder. The report should
become a projection or compatibility wrapper. Replay should operate on a
bundle without importing test modules, mutating globals, or depending on the UI.

## 15. Migration sequence

1. Add canonical serializers for existing evidence and release packages.
2. Introduce an explicit `EvaluationContext` and capture every current
   `compute_report` argument.
3. Emit a complete evaluation trace from the evaluator without changing policy
   outcomes.
4. Define `DecisionArtifact` as a versioned core contract and project current
   `Report` from it where possible.
5. Replace fixture-root mutation with a release package loader.
6. Generalize the release gate to selected institution/release manifests.
7. Add historical release fixtures and replay tests across package versions.
8. Only then migrate UCT and Northstar production paths toward the artifact.

## 16. Audit before merging

This branch should be audited for:

- every `compute_report` argument not represented in `evaluation-request.json`;
- every Report field omitted from `decision-artifact.json` and whether omission
  is intentional;
- every conclusion whose evidence IDs are inferred rather than emitted;
- source and provenance completeness;
- package loader behavior when embedded and referenced modes diverge;
- stable behavior across supported Python and dependency versions;
- whether `outcome`, `status`, and `assessment_complete` are consistently
  canonical across all assessment classes;
- whether the final trace is complete enough to explain a changed decision.

The prototype proves a useful vertical slice. It does not prove institutional
policy correctness, source authority, production security, or universal replay.