# Deployment and migration

## No GitHub changes were made

This package was built locally. It does not alter the connected repository.

## Safe adoption sequence

1. Create a new branch from the repository state you intend to deploy.
2. Copy this package into a separate working directory rather than overwriting the live checkout.
3. Compare `data/` against the included baseline manifest.
4. Run the full test suite.
5. Run the application locally and test at least one transcript from each faculty model.
6. Deploy to a Railway preview service or non-production environment.
7. Confirm `/ready` returns `200` and all six faculties are listed.
8. Confirm browser requests use the deployed origin and `/api/v1/analyse`.
9. Merge only after the preview report matches expected academic outcomes.

## Commands

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
python tools/catalogue_guard.py verify \
  --root data \
  --manifest governance/releases/uct-2026-uploaded-baseline.manifest.json
python -m uvicorn app:app --reload
```

## Railway

The included `railway.toml` uses:

```toml
[deploy]
startCommand = "uvicorn app:app --host 0.0.0.0 --port $PORT --proxy-headers --forwarded-allow-ips='*' --workers 1"
healthcheckPath = "/ready"
```

A public domain must be generated in Railway networking. Students should open that HTTPS domain, not `127.0.0.1`.

## Rollback

The release is easy to roll back because:

- the catalogue data was not migrated;
- legacy endpoints remain;
- the redesign is primarily application and static presentation code;
- the original baseline manifest remains valid;
- no database schema was introduced.

Revert the application commit or redeploy the prior Railway deployment. Do not attempt to repair a bad release by editing historical catalogue JSON in production.

## Acceptance checks

- `/health` returns the product version;
- `/ready` loads all six faculties;
- `/api/v1/bootstrap` returns six lightweight faculty cards;
- `/api/v1/governance/status` reports no missing, changed or unexpected catalogue files;
- a PDF upload reaches `/api/v1/analyse` and produces a programme-scoped report;
- no frontend source contains a hard-coded localhost API base;
- `/admin` cannot publish or mutate data;
- print view contains the complete report sections.
