"""Canonical rule: `epy_suite_connect/` separates its three concerns, and the
adapters folder carries the suite's underscore prefix.

WHY THIS EXISTS. `audit_structure` only checks that certain files live
*somewhere inside* `epy_suite_connect/`, so a module sitting loose at the layer
root satisfies it. Verified by running it: `epy_towers`, carrying six loose
modules and the non-prefixed `adapters/`, prints
``Structure: OK (canonical layout)`` and exits 0. Two campaigns have now moved
these modules and the spelling has drifted both ways, because nothing watched.

TWO SPELLINGS, ONE RULE. `adapters/` and `_adapters/` both shipped, each with a
written justification: `STRUCTURE_STANDARD.md` said `adapters/` is "the layer's
public surface, not a private detail", `epy_concrete/CLAUDE.md:38` said
`_adapters/` because "internal subdirectories always carry the `_` prefix".
Every thread applied whichever was nearer. Settled 2026-08-22 for the prefix
rule: it is what `_core`, `_design`, `_config`, `_contract` and `_data` already
do in every package here.

THE BASELINE, AND WHY IT IS ONE FILE. Deploying this as a hard failure today
would redden twenty of twenty-nine repos before the migration that fixes them
has run, blocking every other thread. `connect_layout_baseline.json` freezes
what exists on the day the rule lands, so the gate fails only on something NEW
-- a fresh loose module, or a fresh `adapters/`. It is suite-level rather than
per-repo on purpose: the remaining surface of the migration is then readable in
one place, and it can only shrink.

The baseline is NOT an exemption. An entry is a debt with an address.

TESTS DO NOT MOVE. The module mirror credits by BASENAME wherever the test
lives, and the flat `tests/epy_suite_connect/` layout is one of the two
conventions `report_module_mirror` states explicitly "must not be 'fixed'".
Moving `src/.../_base.py` under `_contract/` does not oblige moving
`test_base.py`.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

__all__ = [
    "audit_connect_layout",
    "audit_connect_layout_strict",
    "connect_layout_baseline_path",
    "connect_layout_load_baseline",
    "connect_layout_measure",
    "report_connect_layout",
]

#: The canonical spelling. `adapters/` is the one being migrated away from.
_CANONICAL_ADAPTERS = "_adapters"
_LEGACY_ADAPTERS = "adapters"

#: Files allowed to sit directly at the layer root. `__init__.py` is the
#: package marker and `epy_suite_registry.epyx` is packaged data whose loader
#: lives under `_data/`; the registry PYTHON module is not exempt, and two
#: repos still keep it loose.
_CONNECT_ROOT_ALLOWED = ("__init__.py",)


def _connect_dir(lib_root: Path) -> Path | None:
    """This library's ``epy_suite_connect/`` package, if it ships one."""
    for candidate in sorted((lib_root / "src").glob("*/epy_suite_connect")):
        if candidate.is_dir():
            return candidate
    return None


def connect_layout_measure(lib_root: Path) -> dict[str, list[str]]:
    """What this library's connect layer looks like right now.

    Returns ``{"loose": [names], "legacy_spelling": [name]}``. Separated from
    the audit so the baseline can be regenerated from the same measurement the
    rule reads -- a baseline written by different code than the gate is how a
    freeze silently stops matching what it froze.
    """
    connect = _connect_dir(lib_root)
    if connect is None:
        return {"loose": [], "legacy_spelling": []}
    loose = sorted(
        p.name
        for p in connect.glob("*.py")
        if p.name not in _CONNECT_ROOT_ALLOWED
    )
    legacy = []
    if (connect / _LEGACY_ADAPTERS).is_dir():
        legacy.append(_LEGACY_ADAPTERS)
    return {"loose": loose, "legacy_spelling": legacy}


def audit_connect_layout(lib_root: Path) -> list[str]:
    """Every departure from the canonical connect layout, baseline ignored."""
    connect = _connect_dir(lib_root)
    if connect is None:
        return []
    rel = connect.relative_to(lib_root).as_posix()
    state = connect_layout_measure(lib_root)
    out: list[str] = []
    for name in state["loose"]:
        out.append(
            f"{rel}/{name}: module loose at the layer root. The three concerns "
            f"are separate directories -- `_contract/` for the outbound "
            f"contract (_base, _elements, _trace), `_data/` for packaged "
            f"interconnection data (_kepy, _epyson, the registry loader), "
            f"`{_CANONICAL_ADAPTERS}/` for one module per producing sibling. "
            f"`audit_structure` accepts this file because it only asks whether "
            f"it is somewhere inside the layer."
        )
    for _ in state["legacy_spelling"]:
        out.append(
            f"{rel}/{_LEGACY_ADAPTERS}/: non-prefixed spelling. The canonical "
            f"name is `{_CANONICAL_ADAPTERS}/`, per the prefix rule every other "
            f"internal subpackage in this suite follows. Renaming the directory "
            f"is not enough on its own: the imports naming it move with it, "
            f"including any in sibling repos and in `_gallery/`."
        )
    return out


def connect_layout_baseline_path(lib_root: Path) -> Path:
    """The suite-level freeze, beside this rule."""
    # `.epyson`, not `.json`: MASTER_PLAN 2 does not authorize `.json`,
    # and this is configuration a gate reads, so it carries the identity
    # contract like every other config document in the suite.
    return Path(__file__).resolve().parent / "connect_layout_baseline.epyson"


def connect_layout_load_baseline(lib_root: Path) -> dict[str, dict[str, list[str]]]:
    """The frozen state, keyed by repo directory name.

    A missing or unreadable baseline freezes NOTHING, so the rule reports
    everything rather than passing silently. A freeze that cannot be read is
    not an empty freeze.
    """
    path = connect_layout_baseline_path(lib_root)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    known = data.get("known") if isinstance(data, dict) else None
    return known if isinstance(known, dict) else {}


def audit_connect_layout_strict(lib_root: Path) -> list[str]:
    """Violations this library has not frozen in the suite baseline.

    Matching is by NAME, not by count: adding a seventh loose module to a repo
    baselined at six is a new violation, and removing one never becomes a
    violation. That is the direction a burn-down needs.
    """
    connect = _connect_dir(lib_root)
    if connect is None:
        return []
    frozen = connect_layout_load_baseline(lib_root).get(lib_root.resolve().name, {})
    frozen_loose = set(frozen.get("loose") or ())
    frozen_legacy = set(frozen.get("legacy_spelling") or ())
    rel = connect.relative_to(lib_root).as_posix()
    state = connect_layout_measure(lib_root)
    out: list[str] = []
    for violation in audit_connect_layout(lib_root):
        head = violation.split(":", 1)[0]
        name = head[len(rel) + 1:].rstrip("/")
        if name in frozen_loose or name.rstrip("/") in frozen_legacy:
            continue
        out.append(violation)
    # A repo carrying nothing frozen and nothing new says so by returning [].
    del state
    return out


def report_connect_layout(violations: list[str]) -> None:
    """Print the connect-layout result."""
    print("\n" + "=" * 70)
    print("  epy_suite_connect LAYOUT (three concerns + prefix rule)")
    print("=" * 70)
    if not violations:
        print("  OK - no unfrozen loose modules and no non-prefixed adapters/.")
        return
    print(f"  {len(violations)} departure(s) not frozen in the baseline:\n")
    for violation in violations:
        print(f"    - {violation}")


def _self_test() -> int:
    """Prove the rule bites, on trees built here rather than on the suite.

    A gate is only worth its exit code if someone has watched it fail. Both
    halves are planted, and the clean tree is checked too -- a rule that fires
    on everything is as useless as one that fires on nothing.
    """
    import tempfile

    failures = 0

    def build(root: Path, *, loose: tuple[str, ...], adapters: str) -> Path:
        connect = root / "src" / "epy_demo" / "epy_suite_connect"
        (connect / adapters).mkdir(parents=True)
        (connect / "__init__.py").write_text("", encoding="utf-8")
        (connect / adapters / "_concrete.py").write_text("", encoding="utf-8")
        for name in loose:
            (connect / name).write_text("", encoding="utf-8")
        return root

    with tempfile.TemporaryDirectory() as tmp:
        clean = build(Path(tmp) / "clean", loose=(), adapters="_adapters")
        found = audit_connect_layout(clean)
        if found:
            print(f"  FAIL: canonical tree reported {len(found)} violation(s)")
            failures += 1
        else:
            print("  ok: canonical tree is silent")

        loose_tree = build(
            Path(tmp) / "loose", loose=("_base.py", "_kepy.py"), adapters="_adapters"
        )
        found = audit_connect_layout(loose_tree)
        if len(found) != 2:
            print(f"  FAIL: two loose modules reported {len(found)} violation(s)")
            failures += 1
        else:
            print("  ok: a loose module at the layer root is caught")

        spelled = build(Path(tmp) / "spelled", loose=(), adapters="adapters")
        found = audit_connect_layout(spelled)
        if len(found) != 1 or "_adapters" not in found[0]:
            print(f"  FAIL: non-prefixed adapters/ reported {found}")
            failures += 1
        else:
            print("  ok: the non-prefixed spelling is caught")

    print("  SELF-TEST PASSED" if not failures else f"  {failures} SELF-TEST FAILURE(S)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(_self_test())
