> **Historical document**
> This file describes an earlier stage of CRE and is retained for development history. It should not be treated as the current architecture or product specification. See [current architecture](../../docs/CURRENT_ARCHITECTURE.md) and the [documentation index](../../docs/README.md). Original content below is preserved; counts, screenshots, commands and claims retain their original milestone context.

# Northstar v1 Closure

Date: 7 September 2026. Recommendation: **CLOSED for the bounded synthetic
reference institution**, not production identity, SIS integration or institutional
approval.

## Final Evidence

| Check | Result |
|---|---|
| Northstar reference suite | 70 passed |
| Northstar + PPE fidelity/browser presentation + student presentation + requirement-source index | 159 passed |
| Full repository suite after final implementation/metadata changes | 1,114 passed |
| Actual browser login -> fetch -> report -> logout | 10 passed: NS-001, 003, 006, 011, 015 at 1440x1000 and 390x844 |
| Browser failures | Zero page errors; zero horizontal overflows |
| Frontend syntax | Both app.js and northstar.js pass Node syntax checks |
| Targeted Ruff | All changed Python services, presentation, builder, QA and tests pass |
| Targeted Bandit | New Northstar services, shared presentation and builder: no findings |
| Browser harness Bandit | Pass with B101 excluded for test assertions |
| Direct broader app.py Bandit scan | Existing B104 for the pre-existing 0.0.0.0 launcher remains; not introduced here |
| UCT 2026 technical release gate | PASS_WITH_WARNINGS; manifest, requirement sources, tests, configured Ruff/Bandit pass |
| Source/provenance authority | INCOMPLETE remains; institutional approval NOT ASSESSED |
| Northstar reproducibility | Five generated JSON files compare byte-for-byte; six ordinary source locators resolve |

Screenshots and `observations.json` are real browser captures of the running
application, not injected reports. The explicit award screenshot was visually
checked after fixing its former fallback explanation. It now says the award is
recorded by supplied institutional evidence, not inferred or conferred by CRE.

## Earned Claim

A synthetic Northstar subject authenticates, the separate Student Records owner
supplies a fresh native record, an institution-specific adapter emits existing CRE
evidence, and unchanged generic reasoning produces the shared student/advisor
projections. Session identity is not academic evidence. CRE adds no durable student
system of record. The browser clears the previous report on switching accounts.

The 15 cases and their individual expected UI/canonical distinctions are documented
in `northstar/README.md` and the non-runtime `northstar/cases.json`. NS-013/014/015
separately demonstrate academic completion, graduation eligibility and explicit
conferment. NS-011 does not establish admission. NS-012 uses explicit history to
count two active cycles, not academic-result years.

## Change Classification

- New `northstar/`: package/frameworks, identity, records boundary, adapter,
  orchestration, native records, synthetic registry, metadata and lifecycle guide.
- `app.py`: additive mounting of the Northstar application boundary only.
- `curriculum_advisor/presentation.py`: projection-only receipt, entry, clearance,
  consequence/award wording and legacy-separation improvements.
- `static/app.js`: shared renderer library mode and presentation improvements.
- New `static/northstar.html`, `.css`, `.js`: login, navigation, shared rendering,
  source directory and explicitly demo-only advisor surface.
- New builder, browser harness and 70-case integration module.
- **No engine module, UCT institutional data, UCT builder or UCT manifest was
  edited by this capability.** Existing dirty accepted work remains intact.

## Bounded Limitations

The full synthetic record is retrieved in one call, with seven independently
adapted domains. No remote service reliability or production freshness guarantee
is claimed. Malformed optional branches lose their associated coverage and remain
uncertain; an unavailable whole record returns no new report.

Ordinary result authority qualifiers cannot be retained by CourseResult today;
the adapter withholds explicitly qualified local results rather than upgrading
them. The annual ratio consumer still expects legacy year scope, so this package
uses the supported cumulative failed-attempt advisory. Neither issue was hidden
with invented years or new reasoning semantics.

Legacy NQF/semester/scalar-duration report summaries remain in a labelled
compatibility disclosure. They are not Northstar canonical eligibility truth.
Formal Admission, Course Registration/Co-requisites and Qualification Taxonomy
remain SOURCE-BLOCKED. No production SSO, advisor authorisation, revocation,
consent system, administrative integration or formal decision workflow was added.

Next recommendation: rehearse the documented Ms Loqo sequence, then perform a
bounded operational integration review of identity trust, subject/release binding,
evidence-domain access, provenance, consent and retention. Do not add more synthetic
case volume or new reasoning merely to extend the demo.
