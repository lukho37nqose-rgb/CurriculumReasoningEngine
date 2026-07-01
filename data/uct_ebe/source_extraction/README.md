# EBE extraction artefacts

These deterministic JSON artefacts were derived from the UCT 2026 EBE Undergraduate Handbook and are inputs to `tools/build_ebe_2026.py`.

- `programme_rows.json` contains curriculum-table rows plus handbook page metadata.
- `course_descriptions.json` contains course facts extracted from the departmental course-outline sections.

The generated catalogue remains subordinate to the official handbook. These artefacts are retained so the build can be reproduced and audited without depending on session-local `/mnt/data` files.
