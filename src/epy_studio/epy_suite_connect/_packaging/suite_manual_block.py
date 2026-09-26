"""The suite-wide manual has ONE home, and a library repo is not it.

Measured 2026-09-02: ``ePy_Suite_Capacidades.md`` existed twice -- at
``references/`` and inside ``epy_docs/`` -- and the two copies had been
evolving apart for two months. The ``epy_docs`` copy was at v0.8.0
(2026-08-14) and had already corrected the retirement of ``ePy_suite``, the
``_core/*`` module paths and the ``.klito`` -> ``.kepy`` rename. The
``references/`` copy was still at v0.6.0 (2026-06-29) and still described the
orchestrator as live.

Nobody was wrong at any point: both files were edited in good faith by someone
who believed they held the canonical one. That is precisely why this cannot be
left to discipline. A second copy of a suite-wide document inside a library
repo will always drift, because the library repo is where the person editing
that library is looking.

The rule: no library repo may carry a suite-wide manual. The canonical file
lives in ``references/`` at the suite root. A pointer is fine -- and is what
``epy_docs`` now ships -- so a file that merely says where the manual went
passes; a file that carries the manual does not.

Loaded by path from each library's ``housekeeper.py``; edit it HERE.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

# The ONE tree walk, live-loaded from the canonical file next door rather than
# copied: a walk that dies on a dangling junction takes the whole audit with it,
# and four call sites drifting apart is how the rule became four rules.
def _load_safe_rglob():
    """Bind ``safe_rglob`` from ``safe_walk_block.py``, or fall back to rglob."""
    import importlib.util as _ilu

    block = Path(__file__).resolve().parent / "safe_walk_block.py"
    if not block.exists():  # pragma: no cover - only when the tooling repo is partial
        return lambda root, pattern="*": sorted(Path(root).rglob(pattern))
    spec = _ilu.spec_from_file_location("_safe_walk_block", block)
    mod = _ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.safe_rglob


safe_rglob = _load_safe_rglob()

# Documents that belong to the suite, not to any one library. Matched
# case-insensitively against the file STEM, so ``ePy_Suite_Capacidades``,
# ``epy_suite_capacidades_v2`` and ``ePy_Suite_Capacidades (copia)`` all land.
_SUITE_DOC_STEMS = (
    "epy_suite_capacidades",
    "epy_suite_cumplimiento",
)

# A pointer is short by nature. The threshold is generous on purpose: the point
# is to catch a manual, not to police how much prose a pointer may carry. The
# real v2 manual is ~1600 lines; the pointer that replaced the duplicate is 20.
_POINTER_MAX_LINES = 60

# Directories whose contents are not shipped and are already ignored elsewhere.
_SKIP_PARTS = frozenset({"_archive", ".git", "__pycache__", "build", ".venv", "node_modules"})


def audit_suite_manual(lib_root: Path) -> dict[str, Any]:
    """Return every suite-wide manual a library repo carries as a full copy.

    Args:
        lib_root: Root of the library repository being audited.

    Returns:
        dict[str, Any]: ``ran`` (always True -- this rule needs nothing but the
        filesystem), ``why`` and the list of ``violations`` as
        ``(relative_path, reason)`` pairs.

    """
    violations: list[tuple[str, str]] = []

    for path in safe_rglob(lib_root, "*.md"):
        if _SKIP_PARTS.intersection(path.parts):
            continue
        stem = path.stem.lower()
        if not any(stem.startswith(known) for known in _SUITE_DOC_STEMS):
            continue

        rel = path.relative_to(lib_root).as_posix()
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError as exc:  # pragma: no cover - unreadable file
            violations.append((rel, f"could not be read to tell manual from pointer: {exc}"))
            continue

        if len(lines) > _POINTER_MAX_LINES:
            violations.append(
                (rel, f"is {len(lines)} lines -- a copy of a suite-wide manual, not a "
                      f"pointer to it. The canonical file lives in the suite's "
                      f"references/ folder; a second copy here WILL drift, because "
                      f"this repo is where someone editing this library looks. "
                      f"Replace it with a pointer (<= {_POINTER_MAX_LINES} lines).")
            )

    return {"ran": True, "why": None, "violations": violations}


def report_suite_manual(result: dict[str, Any]) -> None:
    """Print the audit result.

    Args:
        result: Payload returned by :func:`audit_suite_manual`.

    """
    print()
    print("=" * 70)
    print("  SUITE-WIDE MANUAL (one home: references/, never a library repo)")
    print("=" * 70)
    if not result["ran"]:
        # a rule that cannot run must say so; silence reads as a pass
        print(f"  NOT RUN - {result['why']}")
        return
    if not result["violations"]:
        print("  OK - no suite-wide manual is duplicated into this repo.")
        return
    print(f"  {len(result['violations'])} duplicated suite document(s):")
    for rel, why in result["violations"]:
        print(f"    [x] {rel}: {why}")
