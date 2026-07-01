# CurriculumAdvisor redesign build report

## Delivered

- complete student-facing information architecture redesign;
- decision-oriented report organised around position, blockers and next options;
- separate HTML, CSS and JavaScript assets;
- responsive and printable interface;
- accessible landmarks, labels, live regions, dialogs and keyboard-operable controls;
- explicit network-failure guidance that reports the current deployment origin;
- read-only governance desk;
- catalogue baseline integrity endpoint;
- versioned `/api/v1` routes with legacy compatibility aliases;
- shallow `/health` and catalogue-loading `/ready` separation;
- Railway readiness deployment configuration;
- corrected development dependency file and CI workflow;
- end-to-end transcript-report regression coverage;
- architecture, product and migration documentation.

## Preserved

- every file under `data/`;
- the programme-scoping model;
- academic rule computation;
- major evaluation;
- prerequisite and simulation behaviour;
- governance manifests and provenance warning;
- legacy API endpoints.

## Validation

- 200 tests passed;
- 19 subtests passed;
- all 22 catalogue files match the baseline manifest;
- Ruff passed on the application, product and governance surface;
- Bandit passed with B104 and B105 excluded as documented false positives:
  - B104 is the required Railway `0.0.0.0` process binding;
  - B105 mistakes a transcript-grade regular expression for a password;
- JavaScript syntax passed for both interfaces;
- Python compilation passed;
- mock-browser visual checks produced the included landing, route, report and administration screenshots.

`pip-audit` is configured in CI but could not query PyPI from the offline build container.

## Known boundary

The redesign does not claim that all 2,731 catalogue course facts have received current institutional confirmation. It preserves the existing evidence states and catalogue provenance. Interface quality cannot convert provisional source authority into verified institutional authority.
