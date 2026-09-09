# Current limitations, authority and governance

Current scope at the accepted shared-workspace/policy-legibility baseline. [Current architecture](CURRENT_ARCHITECTURE.md) and [documentation index](README.md) explain ownership; the accepted [policy report](CRE_POLICY_LEGIBILITY_V1.md) retains detailed PPE gaps and human-review preparation.

## Implemented is not institutionally validated

CRE explains how represented institutional rules apply to available student evidence. Technical tests cover implemented behavior, uncertainty/conflict distinctions and boundaries; they do not establish institutional approval, comprehensive handbook fidelity or student comprehension.

UCT is a bounded working demonstrator using represented undergraduate faculty packages and uploaded/manual/constructed evidence. No live UCT SIS integration is implemented. Northstar is an executable synthetic reference institution with no real student records, not production identity or institutional integration.

CRE does not aim to become a durable student system of record. Authoritative institutional records and formal decisions remain with the institution. Current demonstration behavior is not a production consent, evidence-revocation, retention or secure-deletion guarantee.

## Important semantic boundaries

- **PPE aggregate third-year count:** the existing “Six third-year PPE courses in total” projection remains under semantic review. The tested empty/manual cases can show a definitive aggregate shortfall while individual course requirements remain unresolved. Presentation renders that supplied result; this documentation does not resolve it. Safe PPE rule summaries and broader source fidelity remain bounded as recorded in the policy report.
- **Formal admission decisions:** source-blocked. Implemented entry eligibility is not admission, applicant acceptance or proof of registration.
- **Course registration/co-requisites:** source-blocked. Existing prerequisite evaluation/course exploration does not establish concurrent-registration semantics, timetable fit, capacity, places, permissions or a formal registration decision.
- **Qualification classification/taxonomy:** source-blocked. Exact prior-qualification evidence is not a general equivalence or taxonomy engine.
- **Completion, graduation, award:** academic completion does not establish every graduation condition; graduation eligibility is not formal approval or an award; explicit award evidence does not mean CRE conferred it.
- **Recognition and coverage:** recognition is not a fabricated attempt or mark. Received evidence is not necessarily used, complete beyond its named scope, or institutionally verified.
- **Northstar periods:** supported explicit-period semantics do not imply every legacy annual progression consumer has migrated; the reference uses supported cumulative metrics without inventing result years.
- **Human understanding:** real student comprehension and behavioral benefit remain unvalidated. The teach-back script is preparation, not a study result.

No claim is made of complete PPE fidelity beyond the reviewed scope, complete source fidelity across all UCT rules, official academic advising status, or institutional review of every represented programme.

## UCT technical governance status

The accepted baseline records **PASS_WITH_WARNINGS**, not an unexplained technical failure. The active data baseline is [uct-2026-uploaded-baseline.manifest.json](../governance/releases/uct-2026-uploaded-baseline.manifest.json). The [source archive record](../governance/releases/source_archive_verification.json) preserves:

```text
checksum_mismatch_unverified_source_archive
```

The gate also reports `declaration not supplied` where a rebuild/provenance declaration was not provided. A passing integrity check demonstrates agreement with its recorded baseline; it does not prove the uploaded archive equals a separately named public release or that institutional interpretation has been verified.

Institutional approval is **NOT_ASSESSED** (`NOT ASSESSED` in the text summary). The gate's blocked claims include `institutional_approval`, `source_fidelity` and `institutional_authorisation`. Technical reproducibility/gate success does not establish institutional source verification.

The CLI currently verifies the fixed UCT manifest and data packages despite accepting institution/release labels. It must not be advertised as a fully general Northstar release-approval gate. Northstar has synthetic builder-parity/regression evidence, not production governed institutional approval.

Top-level `SHA256SUMS.txt`, `PATCH_SHA256SUMS.txt`, merge reports and build reports are historical delivery snapshots. Do not refresh their hashes to make old evidence appear current. They are distinct from the active manifest.
