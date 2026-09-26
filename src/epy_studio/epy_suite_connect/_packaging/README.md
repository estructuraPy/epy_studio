# `_packaging/_tooling/` — cross-suite standard and its enforcement scripts

The canonical templates every ePy lib repo is migrated to, plus the scripts
that enforce suite-wide conventions across all 24 repos at once.

## Why here

These files were rescued from `ePy_suite/src/epy_suite/_core/_tooling/` on
2026-08-07, before that repo is retired. They were the only copies in the
suite. `_packaging/` was chosen over `epy_python_kit/` because:

- `migrate_lib.py`, the direct consumer of `templates/`, already lives in
  `_packaging/`, and `quality_check.py` here is imported by every lib's
  `housekeeper.py`. Cross-repo maintenance is already this folder's job.
- `epy_python_kit` is a published dependency bundle whose only charter is
  installing third-party packages for the estructúrate courses. Suite-internal
  migration scripts and a 773-line audit record would ship to course users as
  package data with no runtime value.

Nothing here imports `epy_suite`, so the move costs no functionality. Paths
that were relative to the old location were repointed (see "Changes on
rescue").

## Contents

### `templates/` — the canonical repo skeleton

`migrate_lib.py` copies these verbatim into each lib repo.

| Template | Applied as |
|---|---|
| `STRUCTURE_STANDARD.md` | the written standard itself (repo layout, tests-root mirror rule, `_config` contract) |
| `housekeeper_minimal.py` | starting `housekeeper.py` for a repo that has none |
| `.github/workflows/ci.yml`, `cd.yml` | GitHub Actions CI and publish |
| `.coveragerc` | coverage config (`--cov-fail-under=80`) |
| `.gitignore` | canonical ignore set |
| `.pre-commit-config.yaml` | ruff + std hooks |
| `pyrightconfig.json` | pyright strict |

### Enforcement scripts

All are argparse CLIs with a `--check` / `--dry-run` mode; run those first.

| Script | Does |
|---|---|
| `_standards_helpers_sync.py` | Regenerates the vendored `standards_helpers_block` span in each lib's `_config/_loader.py` from `standards_helpers_block.py.tmpl`. Only the text between the `BEGIN`/`END` markers is ever touched. |
| `standards_helpers_block.py.tmpl` | The single source of truth that script renders. |
| `sync_tests_layout_rule.py` | Splices the canonical `audit_tests_layout()` / `report_tests_layout()` pair into every in-scope `housekeeper.py` (STRUCTURE_STANDARD.md 2.4). |
| `score_epyson_canon.py` | Scores every `.epyson` and its loader against the 5-rubric epyson canon (150 raw, normalised to 100). |
| `migrate_epyson_canon_xsuite.py` | Migrates `.epyson` files toward that canon. |
| `add_hk_loader_only_xsuite.py` | Adds the loader-only audit rule to each housekeeper. |
| `add_hk_rule13_xsuite.py` | Adds housekeeper rule 13 across the suite. |
| `rule8_skip_block.py` | The ONE canonical Rule 8 block (no skipped tests): `_skip_violations_in_source` + `audit_no_skipped_tests` + `report_skipped_tests`. Self-contained — the only name it needs from its host is `Path`. |
| `add_hk_rule8_xsuite.py` | SYNCS that block into every `housekeeper.py`, sweeps the superseded `_PYTEST_SKIP_RE` / `_SKIP_CALLS` / `_SKIP_MARKS` once nothing reads them, and wires `skip_violations` into the **terminal** `if args.strict and (...)` tuple. Dry-run by default; `--apply` to write. |
| `copy_schemas_variations_xsuite.py` | Propagates schema variations across libs. |

### Recorded audit

`epyson_canon_score.json` (773 lines) and `epyson_canon_score.md` are the
recorded output of `score_epyson_canon.py` — the baseline the canon campaign
was measured against. Keep them: rerunning the script does not reproduce the
state of the suite on the day it was scored.

## Changes on rescue

Only location-dependent code was touched; no logic was changed.

- `sync_tests_layout_rule.py` — suite root was `parents[5]` (from
  `ePy_suite/src/epy_suite/_core/_tooling/`), now `parents[2]`.
- `_standards_helpers_sync.py` — the docstring's usage examples invoked
  `python -m epy_suite._core._tooling._standards_helpers_sync`; they now name
  this path.
- `_packaging/migrate_lib.py` — its `TEMPLATES` constant pointed at
  `ePy_suite/src/epy_suite/_tooling/templates`, which never existed after the
  templates moved under `_core/`. That script raised `FileNotFoundError` on its
  first template copy; it now resolves `_tooling/templates` relative to its own
  file, and `REPO_ROOT` is derived instead of hardcoded.

The remaining scripts still carry `ROOT = Path(r"C:\Users\ingah\estructuraPy")`
as they did before the move. That is pre-existing and out of scope for the
rescue, but it is the obvious next cleanup.

## Known stale references — NOT fixed here

Twelve libs carry this breadcrumb above their `standards_helpers_block`:

```
# Regenerate via: python scripts/sync_standards_helpers.py --write
```

`scripts/sync_standards_helpers.py` exists in no repo in the suite. The real
implementation is `_packaging/_tooling/_standards_helpers_sync.py`. The
breadcrumb should read:

```
# Regenerate via: python _packaging/_tooling/_standards_helpers_sync.py --write
```

Affected files (line numbers as of 2026-08-07):

| Repo | File | Line |
|---|---|---|
| epy_bridges | `src/epy_bridges/_config/_loader.py` | 339 |
| epy_buildings | `src/epy_buildings/_config/_loader/__init__.py` | 339 |
| epy_connections | `src/epy_connections/_config/_loader/__init__.py` | 318 |
| epy_geotechnical | `src/epy_geotechnical/_config/_loader.py` | 269 |
| epy_houses | `src/epy_houses/_config/_loader.py` | 176 |
| epy_masonry | `src/epy_masonry/_config/_loader.py` | 1029 |
| epy_steel | `src/epy_steel/_config/_loader.py` | — |
| epy_structure | `src/epy_structure/_config/_loader.py` | 192 |
| epy_tall | `src/epy_tall/_config/_loader.py` | 197 |
| epy_tanks | `src/epy_tanks/_config/_loader.py` | 281 |
| epy_timber | `src/epy_timber/_config/_loader.py` | — |
| epy_towers | `src/epy_towers/_config/_loader.py` | 282 |

Do not fix these with a blind sweep: those twelve files are the same files
`_standards_helpers_sync.py --write` rewrites, and at the time of writing a
separate docstring campaign has them open. Edit the comment line only.
