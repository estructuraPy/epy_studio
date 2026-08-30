#!/usr/bin/env python3
"""Minimal housekeeper — ePy Suite (auto-generated).

Usage:
    python housekeeper.py                # dry-run: report only
    python housekeeper.py --apply        # delete temp/cache
    python housekeeper.py --quality      # ruff + pyright + coverage report
"""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

# ── Root of THIS library ──────────────────────────────────────────────
LIB_ROOT = Path(__file__).resolve().parent

def _find_pkg_dir(lib_root: Path) -> Path | None:
    """Locate src/<pkg>/. Returns None if no src/ exists or no inner package found."""
    src = lib_root / "src"
    if not src.is_dir():
        return None
    for child in src.iterdir():
        if child.is_dir() and (child / "__init__.py").exists():
            return child
    return None


# ── Quality check (shared module) ─────────────────────────────────────
_QUALITY_CHECK_AVAILABLE = False
try:
    _repo_root = LIB_ROOT.parent
    _qc_path = _repo_root / "_packaging" / "quality_check.py"
    if _qc_path.is_file():
        import importlib.util
        _spec = importlib.util.spec_from_file_location("_quality_check", _qc_path)
        if _spec and _spec.loader:
            _mod = importlib.util.module_from_spec(_spec)
            _spec.loader.exec_module(_mod)
            _run_qc = _mod.run_quality_check
            _print_qr = _mod.print_report
            _QUALITY_CHECK_AVAILABLE = True
except Exception:
    pass

DIRS_TO_DELETE = {"__pycache__", ".pytest_cache", ".ruff_cache", ".mypy_cache"}
EXTENSIONS_TO_DELETE = {".pyc", ".pyo"}
PROTECTED = {"src", "tests", "docs", "pyproject.toml", "CLAUDE.md", "README.md",
             "LICENSE", ".gitignore", ".git", ".venv", "housekeeper.py"}


def collect_targets(root: Path) -> list[Path]:
    targets = []
    for path in root.rglob("*"):
        if any(part.startswith(".") and part in DIRS_TO_DELETE for part in path.parts):
            if path.is_dir() and path.name in DIRS_TO_DELETE:
                targets.append(path)
        elif path.suffix in EXTENSIONS_TO_DELETE:
            targets.append(path)
    return targets


def audit_tests_layout(lib_root: Path) -> list[str]:
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
    return violations


def report_tests_layout(violations: list[str]) -> None:
    if not violations:
        print("\n  Tests layout: OK (mirrors src/<pkg>/ + sanctioned _benchmarks/ exception)")
        return
    print(f"\n  TESTS-LAYOUT VIOLATIONS ({len(violations)} total):")
    for v in violations:
        print(f"    [!] {v}")


def _is_mirror_exempt(rel: str) -> bool:
    """Whether ``rel`` is not a unit-test target.

    Integration / packaging / schema / showcase modules are exempt.
    """
    name = rel.rsplit("/", 1)[-1]
    # No blanket exemption for ``epy_suite_connect/``, and none for
    # adapters: measured across the suite, 96 of the 110 adapter modules
    # already ship a mirroring test, so "integration code is not a
    # unit-test target" is not the convention here -- it was a licence for
    # the gate to go blind on whole packages. The clause that used to sit
    # here exempted ``adapters/`` (six repos spell it that way, five spell
    # it ``_adapters/``), and what it hid was the one adapter nobody
    # tests: ``_export_estrulab.py``, byte-identical in seven repos.
    if "/_packaging/" in rel or name in (
        "download_wheels.py", "install_offline.py", "__main__.py",
    ):
        return True
    if "_schemas/" in rel:
        return True
    return name in ("_famous.py", "_demo.py", "_showcase.py")


def audit_module_mirror(lib_root: Path) -> list[str]:
    """Every real src module must have a mirroring test.

    A mirroring test is ``test_<stem>.py`` or ``test_<stem>_*.py``
    anywhere under tests/. Closes the gap left by the folder-level
    tests-layout audit, which reports OK even when a module has no
    test (suite-wide tests-mirror DNA).
    """
    pkg = _find_pkg_dir(lib_root)
    if pkg is None:
        return [
            f"src/<pkg>/ not found under {lib_root} -- cannot "
            "audit module mirror."
        ]
    tests = lib_root / "tests"
    test_names: set[str] = set()
    if tests.is_dir():
        for p in tests.rglob("test_*.py"):
            if "__pycache__" not in p.parts:
                test_names.add(p.name)
    violations: list[str] = []
    for m in pkg.rglob("*.py"):
        if "__pycache__" in m.parts or m.name == "__init__.py":
            continue
        rel = m.relative_to(pkg).as_posix()
        if _is_mirror_exempt(rel):
            continue
        bare = m.name[:-3].lstrip("_")
        if bare in ("utils", "types", "constants", "typing", "protocols"):
            continue
        if f"test_{bare}.py" in test_names:
            continue
        if any(
            n.startswith(f"test_{bare}_") and n.endswith(".py")
            for n in test_names
        ):
            continue
        violations.append(
            f"src module without mirroring test: "
            f"src/{pkg.name}/{rel} -- add "
            f"tests/.../test_{bare}.py (suite-wide tests-mirror DNA)."
        )
    return violations


def report_module_mirror(violations: list[str]) -> None:
    """Print the module-mirror audit result."""
    if not violations:
        print(
            "\n  Module mirror: OK (every real src module has a "
            "mirroring test)"
        )
    else:
        print(f"\n  MODULE-MIRROR VIOLATIONS ({len(violations)} total):")
        for v in violations:
            print(f"    - {v}")


# ============================================================
#                    TUTORIALS LAYOUT (3 categories)
# ============================================================

# The only three tutorial categories the suite recognises. A library
# teaches at three levels and nothing else: undergraduate, professional
# practice, research.
TUTORIAL_CATEGORIES = ("educational", "professional", "research")


# ============================================================
#                    TUTORIALS LAYOUT (3 categories)
# ============================================================

# The only three tutorial categories the suite recognises. A library
# teaches at three levels and nothing else: undergraduate, professional
# practice, research.
TUTORIAL_CATEGORIES = ("educational", "professional", "research")


def audit_tutorials_layout(lib_root: Path) -> list[str]:
    """``tutorials/`` holds exactly the three canonical categories.

    Infrastructure directories (leading ``_`` or ``.``) are exempt: they
    are not tutorial categories. Everything else is a violation.
    ``pedagogical/``, ``validation/``, ``api/``, ``case/``, ``examples/``
    and the numbered tracks were folded into the three during ORDER O4,
    and without this gate nothing stops them coming back.

    Empty list = compliant. A repo with no ``tutorials/`` is compliant.
    """
    tutorials = lib_root / "tutorials"
    if not tutorials.is_dir():
        return []
    present = {c.name for c in tutorials.iterdir() if c.is_dir()}
    if not present & set(TUTORIAL_CATEGORIES):
        # A repo publishing none of the three is a different family: a
        # book (epy_docs: chapters/, images/), a paper, an app.
        # STRUCTURE_STANDARD Sec.1 forbids cross-applying one family's
        # layout rules to another, so the law binds only a repo that
        # teaches at these levels at all.
        return []
    violations: list[str] = []
    for child in sorted(tutorials.iterdir()):
        if not child.is_dir():
            continue
        name = child.name
        if name.startswith(("_", ".")):
            continue
        if name in TUTORIAL_CATEGORIES:
            continue
        violations.append(
            f"tutorials/{name}/ is not a tutorial category -- tutorials/ "
            f"holds exactly {', '.join(TUTORIAL_CATEGORIES)}. Move its "
            f"contents into one of them (STRUCTURE_STANDARD.md Sec.2.7)."
        )
    return violations


def report_tutorials_layout(violations: list[str]) -> None:
    """Print the tutorials-layout verdict."""
    if not violations:
        print("\n  Tutorials layout: OK (the three categories only)")
    else:
        print(f"\n  TUTORIALS-LAYOUT VIOLATIONS ({len(violations)} total):")
        for v in violations:
            print(f"    - {v}")


def main() -> None:
    parser = argparse.ArgumentParser(description="ePy Suite Minimal Housekeeper")
    parser.add_argument("--apply", action="store_true", help="Delete temp/cache files")
    parser.add_argument("--quality", action="store_true", help="Run ruff + pyright + coverage checks")
    parser.add_argument(
        "--audit", action="store_true", help="Run only the read-only audits (tests layout, etc.)"
    )
    args = parser.parse_args()

    lib_name = LIB_ROOT.name
    print("=" * 60)
    print(f"  Housekeeper: {lib_name}")
    print(f"  Root: {LIB_ROOT}")
    print("=" * 60)

    # ── Cleanup ───────────────────────────────────────────────────────
    targets = collect_targets(LIB_ROOT)
    if targets:
        for t in targets:
            print(f"    {t.relative_to(LIB_ROOT)}")
        print(f"\n  Total items: {len(targets)}")
        if args.apply:
            for t in targets:
                if t.is_dir():
                    shutil.rmtree(t, ignore_errors=True)
                else:
                    t.unlink(missing_ok=True)
            print("  DONE — removed.")
        else:
            print("  Re-run with --apply to delete.")
    else:
        print("\n  Library is clean.")

    # ── Quality check ─────────────────────────────────────────────────
    if args.quality:
        if _QUALITY_CHECK_AVAILABLE:
            qc_result = _run_qc(LIB_ROOT)
            _print_qr(qc_result, lib_name)
        else:
            print("\n  --quality requires _packaging/quality_check.py")

    # ── Structure audit (basic) ───────────────────────────────────────
    src_dir = LIB_ROOT / "src"
    if not src_dir.is_dir():
        print("\n  WARNING: no src/ directory (library may not be built yet)")

    # ── Tests layout audit (mirrors src/<pkg>/ + sanctioned _benchmarks/ exception) ──
    tests_layout_violations = audit_tests_layout(LIB_ROOT)
    report_tests_layout(tests_layout_violations)

    module_mirror_violations = audit_module_mirror(LIB_ROOT)
    report_module_mirror(module_mirror_violations)

    tutorials_layout_violations = audit_tutorials_layout(LIB_ROOT)
    report_tutorials_layout(tutorials_layout_violations)

    print()


if __name__ == "__main__":
    main()
