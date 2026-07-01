# CurriculumAdvisor curriculum-data governance

## Non-negotiable boundary

The published curriculum catalogue, term-specific operational data, and individual institutional decisions are separate evidence layers.

1. **Curriculum rules** determine what a qualification requires.
2. **Operational offerings and timetables** indicate what is scheduled in a particular term.
3. **Individual institutional decisions** include concessions, substitutions, placements, approvals and committee decisions.

An operational record must never rewrite a curriculum requirement. An individual decision must never become a general rule merely because it was granted once.

## Ownership

- Faculty administration owns faculty-wide qualification and progression rules.
- Departments own their course facts and departmental curriculum requirements.
- Timetabling or academic administration owns term-specific offering data.
- The CurriculumAdvisor platform team owns schemas, validation, publishing controls and auditability.
- Publication requires a reviewer or approver distinct from the person who entered the change wherever practical.

## Change states

`draft → submitted → validated → approved → published → superseded`

Students must only receive published curriculum data. Draft operational data may be displayed only when clearly labelled provisional and must never create a verified positive academic conclusion.

## Historical protection

A new academic year creates a new release. It does not overwrite the previous year's catalogue. Transitional rules must identify the cohorts to which they apply.

## First implementation boundary

This foundation does not introduce a database or an administrator login. It creates the integrity and data-contract layer required before either is safe:

- checksum baselines;
- immutable release manifests;
- explicit change requests;
- faculty extraction profiles;
- separate operational offering/timetable records;
- dry-run verification before any future publication.
