# Running, validation and repository artifact guidance

Current commands from the repository root. Python CI uses 3.13; Python dependencies are in `requirements*.txt`. The frontend is plain JavaScript: no npm install/build step is defined. [Documentation index](README.md).

## Local application

```bash
python -m pip install -r requirements.txt
python -m uvicorn app:app --reload
```

Open UCT at `http://127.0.0.1:8000/` and Northstar at `http://127.0.0.1:8000/northstar`. Northstar's listed synthetic accounts use `northstar-demo`; this publicly documented code is demonstration access, not production authentication. UCT accepts user-supplied upload/manual/empty entry, not live institutional retrieval.

`/admin` is read-only by default. `ADMIN_WRITES_ENABLED`, `ADMIN_WRITE_TOKEN` and optional `ADMIN_AUDIT_DIR` configure guarded Tier 1 metadata overlays. Published catalogue JSON is not rewritten; append-only audit events default to `governance/admin/quick_edits.jsonl`. This capability is not an institutional identity, approval or publishing service. Do not commit tokens or local audit records.

`/health` is liveness; `/ready` loads enabled UCT catalogues; `/docs` exposes API documentation. Northstar uses `/api/northstar/*`; the UCT/product API uses `/api/v1` and retained unversioned aliases.

## Tests and browser requirements

Install Node.js and ensure `node` is on `PATH`: Python component tests execute JavaScript through it. Install Python development and browser dependencies:

```bash
python -m pip install -r requirements-dev.txt
python -m playwright install chromium
python -m pytest -q
```

Linux CI uses `python -m playwright install --with-deps chromium`. Browser tests start an ephemeral local server; the current regression entry point does not require a persistent server on ports 8765/8770.

Focused product checks:

```bash
python -m pytest -q tests/test_shared_student_workspace.py tests/test_policy_legibility.py
python -m pytest -q tests/test_shared_workspace_browser.py
```

The full suite also covers Northstar service failures and institutional/compatibility contracts. Exact milestone counts remain in dated closure reports. Old `tools/qa_northstar_browser.py` and `tools/qa_ppe_browser.py` contain superseded labels/selectors; they are retained for later tooling review, **not current recommended rehearsal commands**. Preserve their unique scenarios before retirement.

## Quality and release verification

Current CI quality commands (scoped checks, not a claim of whole-tree lint/security coverage):

```bash
python -m ruff check app.py curriculum_advisor catalogue_governance tools/catalogue_guard.py tests/test_product_redesign.py
python -m bandit -q -c pyproject.toml -r app.py curriculum_advisor engine
python -m pip_audit -r requirements.txt
```

Dependency auditing needs network access to its vulnerability service. The release gate includes the full pytest suite and separate governance Ruff/Bandit targets:

```bash
python -m catalogue_governance --institution uct --release uct-2026-uploaded-baseline --json
```

For a documentation-only inspection that does not rerun quality checks:

```bash
python -m catalogue_governance --institution uct --release uct-2026-uploaded-baseline --skip-quality --json
```

`--skip-quality` is a partial gate invocation, not fresh proof that tests/lint/security passed. The gate does not write packages/manifests. A direct data-manifest check uses the actual `--data-root` option:

```bash
python tools/catalogue_guard.py verify --data-root data --manifest governance/releases/uct-2026-uploaded-baseline.manifest.json
```

See [current limitations](CURRENT_LIMITATIONS.md) for `PASS_WITH_WARNINGS`, archive provenance and `NOT_ASSESSED` institutional approval.

## GitHub workflows

| Workflow | Triggers | Actual checks |
|---|---|---|
| [CurriculumAdvisor checks](../.github/workflows/ci.yml) | Push to `main`; pull requests | Python 3.13, dependencies, Chromium, full pytest, scoped application/product/governance Ruff, app/product/engine Bandit, runtime dependency audit |
| [CRE release verification](../.github/workflows/release-verification.yml) | Pushes without a branch filter; pull requests | Python 3.13, dependencies, Chromium, UCT technical release gate including full pytest and governance quality checks |

Both currently run the full suite. Node availability is implicit in the runner rather than declared by a setup step. Quality-target coverage and repeated test work are known tooling follow-ups; workflows and their names are unchanged here. Passing checks do not establish institutional authority or student comprehension.

## Deployment configuration

`railway.toml` installs runtime requirements and launches `app:app` with platform `$PORT`, forwarded proxy headers, one worker and `/ready` health checks. `Procfile` retains an alternative Uvicorn launcher. These are repository configuration, not proof of an active hosted service or production readiness. Do not delete either without checking platform consumers. Historical package-adoption/rollback narrative remains in [Deployment and migration](DEPLOYMENT_AND_MIGRATION.md), clearly labelled as history.

## Generated and intentionally retained files

- Existing ignore rules exclude local logs, Python bytecode, environment files, JSONL audit output and temporary directories; pytest/Ruff caches are local tooling output. Keep secrets and local records out of Git.
- Use an ignored `tmp/` or `temp/` subdirectory for transient browser output. To opt into workspace captures, set `CRE_WORKSPACE_SCREENSHOTS` to that directory in your shell before running the browser suite; leave it unset for ordinary tests.
- The canonical current review set is `artifacts/policy-legibility/after/`; `artifacts/shared-workspace/` is the accepted earlier extraction snapshot. Images document a reviewed state, not live production or real-user validation.
- Other artifact collections and `docs/redesign-*.png` are historical review evidence. Keep closure reports, observations, digests and links intact. A generated report can still be intentional versioned evidence; label its milestone and validation scope.
- Do not broadly ignore `artifacts/`, PNGs, governed JSON or `data/`: selected screenshots, institutional provenance and synthetic reference data are intentionally tracked. `.gitattributes` preserves JSON bytes for manifest/parity checks.
- Duplicate screenshot deletion, stale-script repair, compatibility removal and checksum/archive relocation belong to later reviewed slices. This guidance does not authorize them.
