# First safe migration procedure

This procedure is designed for the existing public-release repository. It does not move or rewrite current catalogue files.

## 1. Merge only the new files

Extract this patch into a new branch. Confirm that no existing path is overwritten. The patch adds only:

- `catalogue_governance/`
- `tools/catalogue_guard.py`
- `governance/`
- `docs/CURRICULUM_DATA_GOVERNANCE.md`
- `docs/FIRST_SAFE_MIGRATION.md`
- new governance tests

## 2. Run the existing test suite unchanged

The existing test result is the behavioural baseline. Any existing failure must be investigated before proceeding.

## 3. Create the first checksum baseline

From the project root:

```bash
python tools/catalogue_guard.py snapshot \
  --data-root data \
  --output governance/releases/uct-2026-public-baseline.json \
  --release-id uct-2026-public-baseline \
  --academic-year 2026 \
  --created-by "CurriculumAdvisor project team"
```

The command refuses to replace an existing manifest unless `--force` is explicitly supplied.

## 4. Verify immediately

```bash
python tools/catalogue_guard.py verify \
  --data-root data \
  --manifest governance/releases/uct-2026-public-baseline.json
```

Expected result: `ok: true`, no missing files, no changed files. New untracked files under `data/` are listed as `unexpected` and do not silently enter the baseline.

## 5. Commit the manifest separately

The baseline commit must contain no curriculum data changes. This makes later diffs legible.

## 6. Do not integrate timetable data into reasoning yet

Validate an example operational file with:

```bash
python tools/catalogue_guard.py validate-offerings \
  governance/templates/course_offerings.example.json
```

A later milestone can add a read-only `/offerings` endpoint. It must remain separate from `/catalogue` and from graduation reasoning until route- and term-specific tests exist.

## Rollback

Because this patch does not modify catalogue files or existing application code, rollback consists of reverting the patch commit. The baseline manifest remains a record of the pre-admin state.
