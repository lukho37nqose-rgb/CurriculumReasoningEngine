# Northstar onboarding gate

## Programme entry extension

The optional `advanced_inquiry` pathway now supplies one synthetic academic
entry policy in `degree_requirements.json`. It requires `(ORA-K7 held OR
FOUND-X7 completed) AND ORION-CERT / OR-MATH >= 7`. Its authority remains
unverified. It does not establish an offer, admission decision or registration.

Programme metadata may supply `programme_entry_eligibility`; an exact
`pathway_entry_eligibility[pathway_key]` replaces that default without merging.
Each spec supplies `eligibility_spec_id`, `programme_key`, optional `pathway_key`,
`condition`, `verification_status` and `source_reference`. Conditions reuse the
academic leaves and two-level `all_of`/`one_of` language; no planning projections
apply. No spec means no canonical entry assessment, not presumed eligibility.

Register the fixture release with the existing test registry, select
`programme_key=systems_inquiry` and `pathway_key=advanced_inquiry`, and submit
existing prior-qualification/external-subject evidence to `/analyse/json` or
`/analyse/text`. The additive `programme_entry_eligibility_assessment` preserves
condition truth, completeness and bounded authority. Local achievement negatives
use `course_attempt_coverage`, never academic completion coverage.

Run `python -m pytest tests/test_programme_entry_eligibility.py -q` for the
current gate. The original onboarding account and its historical limits follow.

Synthetic integration institution, not a production catalogue or real regulation.
Run from the repository root:

```text
python -m pytest tests/test_northstar_onboarding_stage9g.py -q
```

An institution supplies:

- `release.json`: identity, academic unit, route, grading threshold, load table,
  and explicit cycle-to-academic-year mapping.
- `courses.json`: opaque identities, credit/level metadata, offerings, and
  structured prerequisites. Codes carry no academic meaning.
- `degree_requirements.json`: curriculum, progression and award policies.
- `scenarios.json`: seven raw student inputs, including the six required gate
  cases and an additional high-achievement case.
- `__init__.py`: institution-owned framework implementations, exact route and
  catalogue resolution, and a JSON adapter with separate recognition ingestion.

`select_release` is a test-only explicit selection edge. It does not register a
production tenant or alter the application's active UCT release. `analyse`
passes every framework explicitly to the existing engine and uses the actual
app dataclass serializer. No generic evidence-bundle abstraction is needed.

Result coverage and recognition-decision coverage are independent opt-in
assertions. Missing or empty input does not declare either collection complete.
Recognition never creates a module result, numeric mark, or earned credit.

Policy status is unverified. Verified fixture facts/decisions mean test-authorised
evidence for exercising authority propagation, not independently verified real
institutional policy. Existing compatibility names such as `faculty_key`,
`nqf_credits`, and `nqf_level` carry unit, credit and ordinal-tier metadata;
this does not certify a South African NQF relationship. Their public labels remain
product vocabulary debt. The bounded fixture does not claim opaque grade scales,
teaching-period scheduling, admissions, clinical evidence or production ingestion.

## Integration limits exposed

- The production registry registers UCT only; `app.py` selects UCT 2026.
  The gate uses explicit internal release selection, not the production HTTP route.
- Report serialization works unchanged, but generic report wording still includes
  NQF and faculty terminology. Structured progression outcomes remain distinct.
- Release identity is retained by the harness/release object; the legacy Report
  does not provide a dedicated institution/release envelope.
- Academic levels remain numeric metadata, and cycle labels are mapped explicitly
  by this adapter. This fixture does not establish arbitrary grade/level scales or
  automatic calendar interpretation.
- No generic runtime changes were needed. Do not treat this bounded gate as proof
  that every institution or every institutional policy is supported.
