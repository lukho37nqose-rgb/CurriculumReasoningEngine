# EBE 2026 route build

## Delivered coverage

The website now exposes all 28 undergraduate EBE routes represented by the 2026 handbook.

### Architecture, Planning and Geomatics

- Bachelor of Architectural Studies
- BSc Geomatics — Surveying, four-year and five-year/ASPECT
- BSc Geomatics — Geoinformatics/Computer Science, four-year and five-year/ASPECT
- continuing-student Geoinformatics/EGS variants

### Chemical Engineering

- four-year curriculum
- five-year/ASPECT curriculum
- transferee/conversion route
- University of Technology access route

### Civil Engineering

- four-year curriculum
- five-year/ASPECT curriculum
- University of Technology transferee route

### Construction Economics and Management

- BSc Construction Studies
- BSc Property Studies

### Electrical Engineering

- Electrical Engineering, four-year and five-year/ASPECT
- Electrical & Computer Engineering, four-year and five-year/ASPECT
- Mechatronics administered through Electrical Engineering, four-year and five-year/ASPECT
- University of Technology access route

### Mechanical Engineering

- Mechanical Engineering, four-year and five-year/ASPECT
- Mechanical & Mechatronic Engineering, four-year and five-year/ASPECT
- University of Technology access route

## Catalogue totals

- 28 programme routes
- 40 programme/pathway scope combinations
- 354 course facts
- 21 open routes
- 2 continuing-student-only routes
- 5 restricted transfer/access routes
- 14 verified scopes
- 26 intentionally unverified scopes

## Architecture added for EBE

- prescribed route curricula rather than major-based inference;
- current 560-credit and legacy 576-credit pathway separation;
- explicit ASPECT/five-year routes;
- annual and cumulative recognised-credit progression rules;
- supplementary/TRP/additional-assessment context retained as faculty notes rather than automatic entitlements;
- structured honours, first-class honours, and distinction rules;
- approved/open elective pools with provisional transcript allocation;
- transition, published-total conflict, and individual-transfer blockers;
- deterministic source extraction artefacts packaged with the repository.

## Elective logic

EBE does not have one universal elective rule. The build distinguishes:

- Chemical Engineering science, Humanities, advanced-engineering, and free-elective requirements;
- Civil approved electives;
- Electrical Engineering complementary studies and programme-specific elective cores;
- Electrical & Computer Engineering final elective totals that may include an approved senior Computer Science course;
- Mechanical complementary-studies and open-elective categories;
- Geomatics stream electives.

A transcript-only course enters a total only where the selected route expressly permits an approved/open pool. It remains provisional until faculty approval and registration eligibility are confirmed.

## Published conflicts and transition boundaries

- BAS, Construction Studies, and Property Studies contain curriculum-table totals that do not cleanly reconcile with the faculty minimum-credit rule. The engine records the conflict instead of returning a positive graduation result.
- The 2026 Geomatics curriculum is being phased in while an earlier curriculum is phased out. Later-year requirements remain cohort-sensitive.
- Several EBE programmes distinguish current 560-credit and older 576-credit cohorts.
- Transfer/access routes depend on individually granted credits, exemptions, and approved curricula.

## Automated verification

- all 28 programme routes loaded;
- all 40 programme/pathway scopes built without exceptions;
- current and legacy cohort scopes remain separate;
- corrected Chemical Engineering level-8 elective credits are regression-tested;
- Chemical Engineering Humanities inclusions and exclusions are tested;
- unlisted free/open electives are provisional, not verified;
- Electrical & Computer Engineering complementary and senior CSC allocations cannot consume the same course;
- first-year Chemical Engineering progression is tested;
- BAS, Construction Studies, and Property Studies conflicts block false eligibility;
- restricted transfer routes cannot self-certify;
- EBE faculty and programme API metadata are tested.

The combined repository currently passes **135 tests and 19 subtests**.
