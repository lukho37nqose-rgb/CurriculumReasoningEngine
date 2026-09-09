> **Historical document**
> This file describes an earlier stage of CRE and is retained for development history. It should not be treated as the current architecture or product specification. See [current architecture](docs/CURRENT_ARCHITECTURE.md) and the [documentation index](docs/README.md). Original content below is preserved; counts, screenshots, commands and claims retain their original milestone context.

# CurriculumAdvisor governance foundation — additive patch

This is the first implementation milestone for adaptable, administrator-friendly curriculum maintenance.

## What is built

- deterministic SHA-256 catalogue baselines;
- non-destructive verification and manifest comparison;
- atomic manifest writing with overwrite refusal by default;
- a separate schema and validator for term-specific offerings/timetables;
- change-request and faculty-extractor-profile contracts;
- governance and migration documentation;
- tests proving that changed, missing and unexpected data are detected.

## What is deliberately not built yet

- no database;
- no login or admin interface;
- no modifications to the reasoning engine;
- no modifications to existing faculty JSON;
- no automatic publication;
- no timetable influence on graduation or prerequisite conclusions.

This sequencing is intentional. An admin interface without integrity controls would make it easier to corrupt authoritative data.
