# Current validation contract

This is the authoritative scope map for local validation, the two repository GitHub workflows and the technical UCT release gate. [Commands and setup](RUNNING_AND_VALIDATION.md) remain the quick-start guide. Make the validation contract explicit before optimizing it: a passing check is only meaningful if its scope is understood.

## Vocabulary and topology

- **Focused validation:** selected pytest modules relevant to a capability; it does not substitute for the full suite.
- **Full suite:** `python -m pytest -q` from the repository root. `pytest.ini` adds `.` to Python's import path; no testpaths, marker filters or special full-suite exclusions are configured. No explicit skip/xfail conditions were found in the current tests. Browser tests are ordinary tests, not opt-in skips.
- **Browser QA:** actual headless Chromium journeys using Python Playwright. This differs from Python assertions about markup and Node VM component execution.
- **Quality checks:** scoped Ruff, Bandit and separately requested syntax checks. Dependency vulnerability auditing is a different check.
- **Integrated full gate:** the existing governance CLI without `--skip-quality`; it combines governance checks with its own quality commands. It does not include every check in the general CI workflow.
- **Partial governance gate:** the CLI with `--skip-quality`; no new pytest, Ruff or Bandit execution. Running pytest and Ruff separately plus this flag is not an integrated full gate.

```text
LOCAL
  focused/full pytest → Python contracts + Node components + Chromium journeys
  optional explicit JS syntax; scoped Ruff/Bandit; runtime pip-audit
  integrated full gate OR partial governance inspection

CurriculumAdvisor checks / test-and-audit
  full pytest → scoped application Ruff/Bandit → runtime dependency audit

CRE release verification / verify
  integrated full gate
    manifest + source relationships
    full pytest + governance Ruff/Bandit
    declaration/conditional comparison status → technical disposition
```

The full-suite execution overlaps; release disposition and lint/security scopes do not. Both workflows need Python, Node and Chromium because both execute the ordinary full suite.

## Workflow ownership and stable identities

| Workflow/file | Job/check label | Trigger and filters | Main purpose | Dependencies and commands | Outputs/status | External stability concern |
|---|---|---|---|---|---|---|
| [CurriculumAdvisor checks](../.github/workflows/ci.yml) | `test-and-audit` (no separate job name) | Push to `main`; all pull requests; no path filters | Product regression, selected static checks and runtime dependency vulnerabilities | Python 3.13, Node 24, dev requirements, Chromium; full pytest; general Ruff/Bandit and pip-audit commands below | Job success/failure, step logs; 15-minute job timeout | PRESERVE UNTIL EXTERNAL SETTINGS VERIFIED |
| [CRE release verification](../.github/workflows/release-verification.yml) | `verify` (no separate job name) | All pushes and pull requests; no branch/path filters | Technical UCT package/release disposition including regression and governance quality | Python 3.13, Node 24, dev requirements, Chromium; integrated CLI below | JSON in job log, process exit code; no custom job timeout | PRESERVE UNTIL EXTERNAL SETTINGS VERIFIED |

Neither workflow uses manual dispatch, reusable workflows, matrices, explicit shell overrides or artifact upload/download. Ubuntu's default run shell is assumed. Existing workflow display names, job IDs and triggers remain unchanged.

**Before renaming or deleting a workflow/job, verify branch-protection and external required-check consumers.** Job/check name = potential external contract. A local workflow cannot establish whether its check is required.

## Dependencies and environment

- **Python:** CI declares 3.13 and Ruff targets `py313`. Local instructions should use 3.13 for parity; other versions are not a supported-version matrix. The declaration slice was checked locally on 3.14.4. `requirements.txt` pins runtime dependencies; `requirements-dev.txt` includes it plus bounded ranges for pytest, HTTPX, Ruff, Bandit, pip-audit and Playwright. CI installs directly with `python -m pip install -r requirements-dev.txt`; the general workflow first upgrades pip. No editable/package installation is required: tests use the repository path.
- **Node:** both workflows explicitly install major 24 using `actions/setup-node@v4`. Previously they depended on ambient runner Node. Major 24 is the declared validation version, matching the locally exercised major; this is not a claim that older majors fail. Node is mandatory for the full suite and the integrated gate, and for four focused modules: `test_policy_legibility.py`, `test_shared_student_workspace.py`, `test_northstar_student_interface.py`, `test_ppe_pilot_fidelity_repair.py`. They call `node -e`, using built-in `fs`/`vm` and string/component assertions. No npm dependency, jsdom, bundler or Node application server exists. Python-only focused checks and partial governance inspection do not require system Node.
- **Browser:** Python Playwright (`playwright>=1.58,<2`) installs its matched Chromium via `python -m playwright install --with-deps chromium` on Linux CI. Local `python -m playwright install chromium` assumes required OS libraries exist. Tests use `playwright.chromium.launch()` headlessly, not system-browser discovery, Selenium or pyppeteer. Playwright's browser driver is separate from the system Node used by component tests.
- **Browser coverage:** `tests/test_shared_workspace_browser.py`, `tests/test_browser_rehearsal_scenarios.py` and `tests/test_northstar_portal_browser.py` run in both workflows through full pytest. They start loopback servers on ephemeral ports and cover desktop/mobile layouts, source/evidence boundaries, service failures and synthetic scenarios. Real student comprehension and institutional fidelity review remain human work.

| Assumption | Classification | Implication |
|---|---|---|
| Ubuntu latest, Python 3.13, Node 24, Chromium install | DECLARED | Runner image and major tags still move; not byte-identical environments |
| Repository-root working directory / pytest pythonpath | DECLARED | Run commands from checkout root |
| Outbound package/browser/vulnerability-service access | IMPLICIT_RISK | Install/audit failures may be environmental |
| Available loopback ports and browser OS libraries | DECLARED by browser setup; local prerequisite | Constrained environments can fail journeys |
| Default Ubuntu shell, normal UTF-8 environment | IMPLICIT_BUT_SAFE in current CI | No Windows-only workflow commands; cross-platform parity is not universal certification |
| `/mnt/data` builder inputs | LOCAL_ONLY for earlier builder workflows | Not invoked by these CI commands; rebuilding all packages is not claimed |
| `CRE_WORKSPACE_SCREENSHOTS` | LOCAL_ONLY opt-in review output | Unset in workflows; normal tests do not request captures |
| Default token permission on release workflow | IMPLICIT_RISK | Effective repository/org policy was not verified |

## Exact static and frontend scope

General workflow Ruff:

```bash
python -m ruff check app.py curriculum_advisor catalogue_governance tools/catalogue_guard.py tests/test_product_redesign.py
```

This includes one test file and one tool, not all tests/tools; it excludes unlisted production roots such as `engine`, `northstar` and `curriculum_reasoning_engine`. `pyproject.toml` selects E4/E7/E9/F/I/B/UP, ignores E701/E702, excludes data/.venv/venv, and has B017 test and B008 app exceptions. Governance Ruff is only `python -m ruff check catalogue_governance`, using the same Ruff config. Do not say Ruff validates the whole repository.

General workflow Bandit:

```bash
python -m bandit -q -c pyproject.toml -r app.py curriculum_advisor engine
```

The config excludes tests/tools and skips B101 (assert), B104 (all-interface binding) and B105 (hardcoded-password string) checks. Unlisted roots, including Northstar and institution/adapters, are outside this invocation. Governance uses **`python -m bandit -q -r catalogue_governance`**, without `-c pyproject.toml`: the application skip list is not applied to that command. Inline `nosec` suppressions still apply. Bandit provides static security linting over the configured Python production scope. Bandit pass != security certification.

`python -m pip_audit -r requirements.txt` checks known vulnerabilities in resolved runtime requirements, not the development toolchain, runtime behavior or an application's complete attack surface. It runs only in the general workflow, not in the integrated gate.

Standalone syntax is a local change-review check, **not an explicit CI step**. For the relevant changed file use, for example, `node --check static/app.js`. Current production JS files are `admin.js`, `app.js`, `northstar.js`, `student-language.js`, `student-portal.js`, `student-workspace.js` under `static/`. This slice checked all six individually; it did not add that scope to CI. VM tests parse/execute selected components; Chromium loads student scripts. Neither establishes explicit all-file syntax coverage for the admin surface. No DOM/jsdom test system is configured. Syntax checking is not frontend behavioral testing.

## Governance anatomy and limits

Implemented by [release_gate.py](../catalogue_governance/release_gate.py). Supported integrated full gate:

```bash
python -m catalogue_governance --institution uct --release uct-2026-uploaded-baseline --json
```

Always checks the fixed UCT baseline manifest against `data`, records source-status warnings, and validates source relationships in packages that declare them. Packages without relationship metadata are skipped by that source-reference loop; this is not full source fidelity verification. CLI institution/release arguments label the report; they do not select a different manifest implementation.

Unless skipped, the gate invokes full pytest, governance-only Ruff and governance-only Bandit exactly as described above. It does not run pip-audit or an explicit JS syntax command. It does not rewrite packages/manifests.

Semantic/governance/provenance comparisons and correction reconciliation run **conditionally** when the Python API receives `baseline` and `governed` inputs (and corrections where supplied). The CLI does not expose those inputs. Fingerprint/rebuild algorithms have regression tests, but the ordinary CLI does not rebuild all packages or compare a supplied candidate to a previous release. It reports missing declarations and not-applicable rebuild/correction checks. Empty change arrays are not proof of human semantic review.

Blocking failures or unexplained drift produce `FAIL` and exit 1. Incomplete declarations/source status produce `PASS_WITH_WARNINGS`; otherwise `PASS`; both return exit 0. Conditional review flags must be inspected separately; technical disposition does not grant approval.

`PASS_WITH_WARNINGS` means technical checks passed while declared warnings remain, including `checksum_mismatch_unverified_source_archive` and `declaration not supplied` in the current baseline. Institutional approval stays `NOT_ASSESSED`. Technical gate status != institutional approval, source archive verification, source fidelity or human semantic review.

## Local / CI / gate parity

| Check | Local documented | General CI | Integrated gate / release CI | Browser/manual | Notes |
|---|---|---|---|---|---|
| Full pytest | Yes | Yes | Yes | Includes Chromium | Same discovery command |
| Focused pytest | Yes | No separate subset | No separate subset | Capability-specific | Different scope despite similar name |
| Browser journeys | Yes | Inside pytest | Inside pytest | Automated Chromium | Human comprehension not covered |
| JS syntax | Per-file review | No standalone step | No standalone step | Selected scripts execute elsewhere | Admin syntax gap remains declared |
| Ruff | Exact general command | Selected roots/file | Governance only | No browser | Not whole-tree lint |
| Bandit | Exact general command | App/product/engine, config skips | Governance only, no config argument | No runtime security testing | Different security-lint scopes |
| Runtime dependency audit | Yes | Yes | No | Network service | Not dev dependency audit |
| Manifest | Direct guard or gate | Regression tests only | Current manifest verification | No | Integrity, not source approval |
| Source relationships | Gate | Regression tests | Declared package references | Inspectable in UI | Not all rules reviewed |
| Semantic fingerprint/comparison | API + tests | Regression tests | Tests; comparison conditional API inputs | Human review remains | No live CLI candidate comparison |
| Provenance fingerprint | API + tests | Regression tests | Tests; declarations incomplete | Source verification external | Archive warning retained |
| Approval status | Gate reports boundary | Assertions, not approval | NOT_ASSESSED | Institution owns decision | Not a CI certification |
| Artifact cleanliness | Before/after status review | No explicit status assertion | No explicit status assertion | Captures opt-in | Prior hygiene proof is a snapshot, not continuous enforcement |

## Layering, actions and future changes

- **INTENTIONAL DEFENSE IN DEPTH:** a standalone release gate includes regression tests even when a separate workflow also runs them. Keeping the gate independently runnable protects its technical disposition.
- **DIFFERENT SCOPE DESPITE SIMILAR NAME:** general versus governance Bandit; general versus focused pytest. Governance Ruff overlaps the general command but the standalone gate owns its own check.
- **UNCERTAIN optimization:** two workflow executions of pytest and repeated setup. Execution duplication is established; lack of purpose is not. No repetition is established as safely removable HISTORICAL DUPLICATION in this slice.

Actions use major tags, not immutable SHAs: `actions/checkout@v4`, `actions/setup-python@v5`, and newly declared `actions/setup-node@v4`. No bulk action upgrades were made. `ubuntu-latest`, major runtime selectors and bounded dev dependency ranges also float. Review exact pinning as a separate hardening policy, not an incidental cleanup.

General CI uses setup-python's pip cache; release CI does not. Neither explicitly caches browsers or Node/npm dependencies. Caching reduces download work and does not replace dependency installation/validation. No workflow uploads or retains review screenshots/reports beyond ordinary GitHub job logs. Neither references secrets or deployment credentials. General CI explicitly grants `contents: read`; release CI inherits defaults. Checkout token handling remains the action default; absence of write commands is not proof of read-only effective permissions.

No README workflow badges exist to repair. GitHub also lists dynamic Copilot workflows; these are not the two source-controlled workflow files and are outside this contract's implementation scope.

| Later candidate | Risk | Required evidence before change |
|---|---|---|
| Action/runtime/dev-tool pinning policy | MEDIUM_RISK | Maintenance/update policy and hosted-run proof |
| Explicit release token permissions | MEDIUM_RISK | Effective defaults and action consumers |
| Explicit all-file syntax / artifact-cleanliness assertion | LOW_RISK_LATER | Agree new coverage; this would add validation semantics |
| Repeated setup/cache parity | LOW_RISK_LATER | Measure benefit and preserve independent execution |
| Ruff/Bandit omitted production roots | MEDIUM_RISK | Findings triage and deliberate scope expansion |
| Duplicate pytest execution / workflow consolidation | HIGH_RISK_EXTERNAL_CONTRACT | Required-check consumers and standalone gate guarantees |
| Job/workflow names, filters or trigger changes | HIGH_RISK_EXTERNAL_CONTRACT | Branch protection, rulesets and integration verification |

GitHub baseline evidence and slice-specific validation results belong in the closure report, not durable test-count claims. Branch-protection inspection returned 401 during this audit; required checks remain unverified. Do not infer absence of protection. This contract does not claim CI optimization, eliminated duplication, complete automatic validation or identical scopes across layers.
