"""Splice the canonical tests-layout audit into every in-scope housekeeper.py.

Campaign: strict tests-root mirror layout (STRUCTURE_STANDARD.md Section 2.4,
2026-07-20). This tool replaces the two live variants of
``audit_tests_layout()`` / ``report_tests_layout()`` (the ``_benchmarks``
variant carried by most repos and the ``_perf``-sanctioning variant in
ePy_suite / ePy_plotter / epy_units) with the single canonical pair that:

* forbids loose files at the tests/ root (only ``conftest.py`` and
  ``__init__.py`` are allowed there), and
* keeps ``_benchmarks/`` as the ONE sanctioned non-mirror root directory
  (``_perf/`` is desanctioned).

Splice strategy (anchor range, not byte equality -- the two live variants
plus docstring drift make byte-matching brittle):

1. ``a`` = start of ``def audit_tests_layout(``.
2. ``r`` = start of ``def report_tests_layout(`` after ``a``.
3. ``end`` = the newline that opens the next ``def `` after ``r``
   (tier-agnostic: the next def is ``main`` on the minimal tier and
   ``apply`` on the full tier).
4. Structural drift guard on the old span: it must start with the exact
   canonical def line and contain ``_find_pkg_dir(lib_root)`` and
   ``allowed_dirs = {``; anything else is reported as "UNEXPECTED shape"
   and skipped for manual review.
5. The span is replaced by the canonical pair; the result must ``ast.parse``
   and keep the function-def counts unchanged (2 replaced by 2).
6. Cosmetic normalize outside the span: the stale main() banner citation
   ``sanctioned _perf/ exception -- EPY_SUITE_RULES.md Sec.9`` becomes
   ``sanctioned _benchmarks/ exception -- STRUCTURE_STANDARD.md §2.4``.

Idempotent: the canonical payload introduces ``allowed_files = {"conftest.py"``
which no legacy variant contains; its presence marks a target as already
patched.

Line endings: each target is rewritten with the newline convention it already
uses (CRLF-carrying files stay CRLF, LF files stay LF).

Usage:
    python sync_tests_layout_rule.py                       # dry-run: all 24 repos + template
    python sync_tests_layout_rule.py --lib epy_masonry     # dry-run one repo (case-insensitive)
    python sync_tests_layout_rule.py --template-only       # just the packaged template
    python sync_tests_layout_rule.py --apply [...]         # write (byte-verified after write)

The script stays in-tree after the campaign (precedent:
``add_hk_rule13_xsuite.py``).
"""
from __future__ import annotations

import argparse
import ast
import difflib
import sys
from pathlib import Path

# Suite root: this file lives at <suite-root>/_packaging/_tooling/.
ROOT = Path(__file__).resolve().parents[2]

# The 24 in-scope repos (real on-disk casing). EXCLUDED and never touched:
# epy_docs, epy_papers, epy_slides, epy_reports, epy_python_kit.
IN_SCOPE = [
    "epy_aluminum", "epy_analysis", "epy_blender", "epy_bridges",
    "epy_buildings", "epy_compose", "epy_concrete", "epy_connections",
    "epy_geotechnical", "epy_houses", "epy_ifc", "epy_masonry",
    "ePy_plotter", "epy_project", "epy_signal", "epy_simulation",
    "epy_steel", "epy_structure", "ePy_suite", "epy_tall", "epy_tanks",
    "epy_timber", "epy_towers", "epy_units",
]

# The packaged minimal-housekeeper template is an explicit extra target.
TEMPLATE_NAME = "template:housekeeper_minimal.py"
TEMPLATE_PATH = Path(__file__).resolve().parent / "templates" / "housekeeper_minimal.py"

# Exact def line every legacy variant starts with (drift guard, part 1).
DEF_LINE = "def audit_tests_layout(lib_root: Path) -> list[str]:"

# The canonical payload introduces this; no legacy variant contains it.
SENTINEL = 'allowed_files = {"conftest.py"'

# Stale main() banner citation normalized outside the spliced span.
BANNER_OLD = "sanctioned _perf/ exception -- EPY_SUITE_RULES.md Sec.9"
BANNER_NEW = "sanctioned _benchmarks/ exception -- STRUCTURE_STANDARD.md §2.4"

NEW_AUDIT = r'''def audit_tests_layout(lib_root: Path) -> list[str]:
    """Audit tests/ against the canonical mirror-of-src layout (STRUCTURE_STANDARD.md §2.4).

    Two independent constraints on the tests/ ROOT:

    * Files -- ONLY ``conftest.py`` and ``__init__.py`` may sit directly under
      tests/. Every other file (``test_*.py`` harness/facade suites,
      ``pytest.ini``, READMEs, ...) belongs inside the mirrored subpackage of
      the code it exercises (``tests/_core/``, ``tests/_design/``,
      ``tests/_analysis/`` ...), never at the root.
    * Directories -- allowed root dirs = {every top-level dir name actually
      present under ``src/<pkg>/``} UNION {"_benchmarks"}, derived DYNAMICALLY
      from src/ so the same rule works for every domain folder name
      (``_design`` vs ``_analysis`` vs ``_service`` ...) without hardcoding one.
      ``_benchmarks/`` is the single sanctioned non-mirror dir; ``_perf/`` is
      NOT sanctioned (desanctioned 2026-07-20).

    Returns a list of violation strings (empty = compliant).
    """
    pkg = _find_pkg_dir(lib_root)
    if pkg is None:
        return []
    tests_root = lib_root / "tests"
    if not tests_root.is_dir():
        return []

    allowed_files = {"conftest.py", "__init__.py"}
    allowed_dirs = {"_benchmarks"}
    for child in pkg.iterdir():
        if child.is_dir() and child.name != "__pycache__":
            allowed_dirs.add(child.name)

    violations: list[str] = []
    for child in sorted(tests_root.iterdir()):
        if child.name in {"__pycache__", ".pytest_cache"}:
            continue
        if child.is_file():
            if child.suffix in {".pyc", ".pyo"}:
                continue
            if child.name not in allowed_files:
                violations.append(
                    f"tests/{child.name} is a loose root file -- only conftest.py and "
                    f"__init__.py are allowed at tests/ root; move it into the matching "
                    f"tests/<mirror>/ subpackage (STRUCTURE_STANDARD.md §2.4)."
                )
            continue
        if child.is_dir() and child.name not in allowed_dirs:
            violations.append(
                f"tests/{child.name}/ has no matching src/{pkg.name}/{child.name}/ "
                f"and is not the sanctioned tests/_benchmarks/ exception -- forbidden "
                f"non-mirror folder (STRUCTURE_STANDARD.md §2.4)."
            )
    return violations'''

NEW_REPORT = r'''def report_tests_layout(violations: list[str]) -> None:
    if not violations:
        print("\n  Tests layout: OK (mirrors src/<pkg>/ + sanctioned _benchmarks/ exception)")
        return
    print(f"\n  TESTS-LAYOUT VIOLATIONS ({len(violations)} total):")
    for v in violations:
        print(f"    [!] {v}")'''

REPLACEMENT = NEW_AUDIT + "\n\n\n" + NEW_REPORT + "\n\n\n"


class ShapeError(RuntimeError):
    """Raised when a target does not match the expected legacy shape."""


def load_text(path: Path) -> tuple[str, bool]:
    """Read a file as UTF-8, returning LF-normalized text + whether it was CRLF."""
    raw = path.read_bytes().decode("utf-8")
    crlf = "\r\n" in raw
    return (raw.replace("\r\n", "\n") if crlf else raw), crlf


def save_text(path: Path, text: str, crlf: bool) -> None:
    """Write LF-domain text back with the file's original newline convention."""
    out = text.replace("\n", "\r\n") if crlf else text
    path.write_bytes(out.encode("utf-8"))


def count_defs(text: str) -> int:
    """Count every function def (top-level and nested) via ast."""
    return sum(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        for node in ast.walk(ast.parse(text))
    )


def splice(text: str) -> str:
    """Return the patched text, or raise ShapeError for manual review."""
    a = text.find("def audit_tests_layout(")
    if a == -1:
        raise ShapeError("no `def audit_tests_layout(` anchor")
    if text.count("def audit_tests_layout(") != 1:
        raise ShapeError("multiple `def audit_tests_layout(` defs")
    r = text.find("def report_tests_layout(", a)
    if r == -1:
        raise ShapeError("no `def report_tests_layout(` anchor after audit")
    nl = text.find("\ndef ", r)
    if nl == -1:
        raise ShapeError("no `def` follows report_tests_layout (span end not found)")

    old_span = text[a : nl + 1]
    # Structural drift guard: exact def line + the two load-bearing internals.
    if not old_span.startswith(DEF_LINE):
        raise ShapeError(f"span does not start with the exact def line `{DEF_LINE}`")
    if "_find_pkg_dir(lib_root)" not in old_span:
        raise ShapeError("span lacks `_find_pkg_dir(lib_root)`")
    if "allowed_dirs = {" not in old_span:
        raise ShapeError("span lacks `allowed_dirs = {`")

    prefix = text[:a]
    suffix = text[nl + 1 :]
    new_text = prefix + REPLACEMENT + suffix
    # Defensive self-check: never rewrite anything outside the anchor range.
    if new_text[: len(prefix)] != prefix or new_text[len(prefix) + len(REPLACEMENT) :] != suffix:
        raise ShapeError("splice invariant violated -- refusing to continue")

    # Cosmetic normalize of the stale main() banner citation (outside the span).
    new_text = new_text.replace(BANNER_OLD, BANNER_NEW)

    # Post-splice assertions: parseable, def counts unchanged, one def each.
    try:
        ast.parse(new_text)
    except SyntaxError as exc:
        raise ShapeError(f"patched text does not ast.parse: {exc}") from exc
    if new_text.count("def audit_tests_layout(") != 1:
        raise ShapeError("patched text must contain exactly one audit_tests_layout def")
    if new_text.count("def report_tests_layout(") != 1:
        raise ShapeError("patched text must contain exactly one report_tests_layout def")
    if count_defs(new_text) != count_defs(text):
        raise ShapeError("function-def count changed across the splice")
    return new_text


def summarize_diff(name: str, old_text: str, new_text: str) -> str:
    """Compact unified-diff summary for one target (imitates _standards_helpers_sync)."""
    diff = difflib.unified_diff(
        old_text.splitlines(keepends=True),
        new_text.splitlines(keepends=True),
        fromfile=f"{name} (current)",
        tofile=f"{name} (canonical)",
        n=1,
    )
    lines = list(diff)
    changed = sum(
        1 for line in lines if line.startswith(("+", "-")) and not line.startswith(("+++", "---"))
    )
    preview = "".join(lines[:40])
    more = "" if len(lines) <= 40 else f"\n  ... ({len(lines) - 40} more diff lines)"
    return f"  {changed} changed line(s):\n{preview}{more}"


def process_target(name: str, path: Path, *, apply: bool, verbose_diff: bool) -> str:
    """Patch (or dry-run) one target. Returns a one-line status for the summary."""
    if not path.is_file():
        print(f"[FAIL] {name}: missing file {path}")
        return "MISSING FILE"
    text, crlf = load_text(path)
    if SENTINEL in text:
        print(f"[skip] {name}: already patched")
        return "already patched"
    try:
        new_text = splice(text)
    except ShapeError as exc:
        print(f"[FAIL] {name}: UNEXPECTED shape -- manual review ({exc})")
        return f"UNEXPECTED shape ({exc})"

    if not apply:
        print(f"[dry]  {name}: spliceable")
        if verbose_diff:
            print(summarize_diff(name, text, new_text))
        return "spliceable (clean anchor match)"

    save_text(path, new_text, crlf)
    # Byte-verify: re-read from disk, confirm the canonical payload landed
    # verbatim and the file still parses.
    reread, _ = load_text(path)
    if NEW_AUDIT not in reread or NEW_REPORT not in reread:
        print(f"[FAIL] {name}: byte-verify FAILED after write -- inspect {path}")
        return "byte-verify FAILED"
    ast.parse(reread)
    print(f"[applied] {name}: PATCHED (byte-verified)")
    return "PATCHED (byte-verified)"


def main() -> int:
    # Widen stdout/stderr to UTF-8 so diff previews never crash on cp1252.
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="backslashreplace")

    parser = argparse.ArgumentParser(description="Sync the canonical tests-layout audit rule.")
    parser.add_argument("--apply", action="store_true", help="Write changes (default: dry-run).")
    scope = parser.add_mutually_exclusive_group()
    scope.add_argument(
        "--lib", default=None,
        help="Limit to one repo dirname, case-insensitive (e.g. --lib epy_masonry).",
    )
    scope.add_argument(
        "--template-only", action="store_true",
        help="Patch only the packaged housekeeper_minimal.py template.",
    )
    parser.add_argument(
        "--no-diff", action="store_true",
        help="Suppress unified-diff previews in dry-run output.",
    )
    args = parser.parse_args()

    targets: list[tuple[str, Path]] = []
    if args.template_only:
        targets.append((TEMPLATE_NAME, TEMPLATE_PATH))
    elif args.lib:
        matches = [lib for lib in IN_SCOPE if lib.lower() == args.lib.lower()]
        if not matches:
            print(f"ERROR: --lib {args.lib!r} is not one of the 24 in-scope repos.", file=sys.stderr)
            return 2
        targets.extend((lib, ROOT / lib / "housekeeper.py") for lib in matches)
    else:
        targets.extend((lib, ROOT / lib / "housekeeper.py") for lib in IN_SCOPE)
        targets.append((TEMPLATE_NAME, TEMPLATE_PATH))

    results: dict[str, str] = {}
    for name, path in targets:
        results[name] = process_target(
            name, path, apply=args.apply, verbose_diff=not args.no_diff
        )

    failed = [n for n, s in results.items() if "UNEXPECTED" in s or "FAILED" in s or "MISSING" in s]
    print("\n" + "=" * 60)
    print(f"  {len(targets)} target(s): "
          f"{sum('spliceable' in s for s in results.values())} spliceable, "
          f"{sum('PATCHED' in s for s in results.values())} patched, "
          f"{sum(s == 'already patched' for s in results.values())} already patched, "
          f"{len(failed)} failed")
    if failed:
        print(f"  FAILED: {', '.join(failed)}")
    print("=" * 60)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
