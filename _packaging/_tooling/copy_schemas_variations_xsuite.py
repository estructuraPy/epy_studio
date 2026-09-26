"""Drop canonical `_schemas/` package and `VARIATIONS.md` into every lib's `_config/`.

The schema files are minimal stubs that adapt to each lib's family set.
Existing files are preserved (skipped). Idempotent.

Usage:
  python copy_schemas_variations_xsuite.py            # dry-run
  python copy_schemas_variations_xsuite.py --apply
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(r"C:\Users\ingah\estructuraPy")
LIBS = [
    "epy_analysis", "epy_bridges", "epy_buildings", "epy_compose",
    "epy_connections", "epy_geotechnical", "epy_houses",
    "epy_masonry", "epy_plotter", "epy_steel", "epy_structure",
    "epy_suite", "epy_tall", "epy_tanks", "epy_timber", "epy_towers",
]

BASE_PY = '''"""Identity fields shared by every `<algo>_id` family."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar

VALID_AUDIT_STATUS = frozenset({
    "verified",
    "partial",
    "needs_source_verification",
    "n_a",
})


@dataclass(frozen=True)
class EpysonIdentity:
    """Mandatory identity contract for any `.epyson`."""

    id_field: str
    id_value: str
    version: str
    description: str
    audit_status: str

    REQUIRED_KEYS: ClassVar[tuple[str, ...]] = (
        "version", "description", "audit_status",
    )


def validate_against_schema(data: dict[str, Any], schema_cls: type, stem: str) -> None:
    """Raise ValueError on any schema deviation. Identity check only by default."""
    if not isinstance(data, dict):
        raise ValueError(f"{stem}.epyson: top-level must be a JSON object, got {type(data).__name__}")
    id_field = schema_cls.ID_FIELD
    if id_field not in data:
        raise ValueError(f"{stem}.epyson: missing required field '{id_field}'")
    if data[id_field] != stem:
        raise ValueError(
            f"{stem}.epyson: id mismatch - '{id_field}'='{data[id_field]!r}' "
            f"must equal filename stem '{stem}'"
        )
    for k in EpysonIdentity.REQUIRED_KEYS:
        if k not in data:
            raise ValueError(f"{stem}.epyson: missing required identity field '{k}'")
    if data["audit_status"] not in VALID_AUDIT_STATUS:
        raise ValueError(
            f"{stem}.epyson: audit_status='{data['audit_status']!r}' not in {sorted(VALID_AUDIT_STATUS)}"
        )
'''

INIT_PY_TEMPLATE = '''"""Canonical schemas for every `<algo>_id` family present in {lib}.

Identity contract: every `.epyson` carries `<algo>_id`, `version`, `description`,
`audit_status`. Family-specific physics fields stay inside `properties` /
`dimensions` / model-specific buckets and are documented in VARIATIONS.md.
"""
from .{lib_safe}_schemas_base import (VALID_AUDIT_STATUS, EpysonIdentity,
                                       validate_against_schema)

__all__ = [
    "VALID_AUDIT_STATUS",
    "EpysonIdentity",
    "validate_against_schema",
]
'''

VARIATIONS_MD = '''# Allowed variations per `<algo>_id` family in {lib}

This document is the contract for what may differ between `.epyson` files of
the same family within {lib} and across the rest of the ePy Suite. Anything
not listed here is a violation and will be flagged by `audit_epyson_canon()`
in `housekeeper.py` (Rule 13).

**Canon vs. variation.** Every `.epyson` carries the identity contract
(`<algo>_id`, `version`, `description`, `audit_status`). Family-specific
physics fields are listed below. Variations are allowed only inside the CALC
and METADATA buckets — never at the top level.

## Identity bucket (locked, every family)

- `<algo>_id` matches filename stem
- `version` semver (e.g. `"1.0.0"`)
- `description` ≥ 20 chars, English-only (except `tutorials/professional/case/`)
- `audit_status` ∈ {{verified, partial, needs_source_verification, n_a}}

## Calc / Relations / Metadata buckets

| Family | CALC (physics) | RELATIONS | METADATA |
|---|---|---|---|
| `standard_id` | `country`, `edition_year`, `philosophy`, physics sections (vary by code) | `complement_with` for scope-limited local codes | `audit_notes`, `references[]`, `unit_system` |
| `material_id` | `type`, `properties` (numeric, unit suffix) | cost/GWP via `epy_suite._design._components.economics` | `metadata.*` |
| `section_id` | `type`, `shape`, `dimensions` (per-shape body) | `material_id` may co-exist | `reference`, `metadata.*` |
| `layout_id` | `font`, `typography`, `palette`, `figures`, `lines` | — | — |
| `constitutive_id` | `material_type`, `points[]`, `hysteresis_rules`, `degradation` | `export_config.{{opensees,sap2000,etabs}}` | `metadata.*` |
| `config_id` | `payload` | — | — |

## Cross-lib parity

The IDENTITY bucket must be IDENTICAL across all 17 ePy libs. CALC and
RELATIONS may differ for domain-specific physics (concrete vs steel sections).

If you need a top-level key that isn't documented above, update this file
first and add the matching field to `_schemas/`. Otherwise `audit_epyson_canon`
will fail.
'''


def write_if_missing(p: Path, content: str, apply: bool) -> str:
    if p.exists():
        return f"skip (exists): {p.name}"
    if apply:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    return f"{'wrote' if apply else 'would write'}: {p.name}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    for lib in LIBS:
        cfg = ROOT / lib / "src" / lib.lower() / "_config"
        if not cfg.exists():
            print(f"  [skip] {lib}: no _config/")
            continue
        schemas_dir = cfg / "_schemas"
        # use a lib-prefixed base file name to avoid shadowing any package globals
        lib_safe = lib.lower().replace("epy_", "epy_") + "_base_schema"
        notes = []
        notes.append(write_if_missing(
            schemas_dir / "__init__.py",
            INIT_PY_TEMPLATE.format(lib=lib, lib_safe=lib_safe),
            args.apply,
        ))
        notes.append(write_if_missing(
            schemas_dir / f"{lib_safe}.py",
            BASE_PY,
            args.apply,
        ))
        notes.append(write_if_missing(
            cfg / "VARIATIONS.md",
            VARIATIONS_MD.format(lib=lib),
            args.apply,
        ))
        print(f"  [{lib}] {'; '.join(notes)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
