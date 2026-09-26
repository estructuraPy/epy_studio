#!/usr/bin/env python3
"""Shared quality-check module for ePy Suite housekeepers.

Usage from housekeeper.py:
    from _packaging.quality_check import run_quality_check
    run_quality_check(LIB_ROOT)

Standalone (any lib):
    python _packaging/quality_check.py C:\\path\\to\\epy_concrete

Reports:
    - ruff remaining errors (F841, E741)
    - pyright errors (typing)
    - pytest --cov (coverage percentage)
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any


def _run(cmd: list[str], cwd: Path, timeout: int = 120) -> tuple[str, str, int]:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd, timeout=timeout)
        return r.stdout, r.stderr, r.returncode
    except FileNotFoundError:
        return "", f"command not found: {cmd[0]}", -1
    except subprocess.TimeoutExpired:
        return "", "timed out", -1


def run_quality_check(lib_root: Path, *, verbose: bool = False) -> dict[str, Any]:
    """Run quality checks on a library directory.

    Returns dict with keys: ruff_count, pyright_count, coverage_pct, errors.
    """
    result: dict[str, Any] = {
        "ruff_count": -1,
        "pyright_count": -1,
        "coverage_pct": -1.0,
        "errors": [],
    }

    src_dir = lib_root / "src"
    if not src_dir.is_dir():
        result["errors"].append(f"no src/ directory in {lib_root}")
        return result

    lib_name = lib_root.name

    # ── ruff ─────────────────────────────────────────────────────────
    ruff_out, ruff_err, rc = _run(
        ["ruff", "check", "--select", "E,W,F,I,UP,B,C4,SIM", "--ignore", "N803,N806,E501",
         "--output-format", "json", str(src_dir)],
        lib_root, timeout=60,
    )
    if rc == 0 or rc == 1:
        try:
            issues = json.loads(ruff_out) if ruff_out.strip() else []
        except json.JSONDecodeError:
            issues = []
        # Count only non-auto-fixable rules (F841 = unused-var, etc.)
        fixable = sum(1 for i in issues if i.get("fix") is not None)
        unfixable = len(issues) - fixable
        result["ruff_count"] = unfixable
        result["ruff_total"] = len(issues)
        result["ruff_fixable"] = fixable
        # Summarize by rule
        rule_counts: dict[str, int] = {}
        for i in issues:
            rule = i.get("code", "?")
            rule_counts[rule] = rule_counts.get(rule, 0) + 1
        result["ruff_by_rule"] = dict(sorted(rule_counts.items(), key=lambda x: -x[1]))
    else:
        result["errors"].append(f"ruff failed: {ruff_err[:200]}")

    # ── pyright ──────────────────────────────────────────────────────
    pyright_out, pyright_err, rc = _run(
        ["pyright", str(src_dir)],
        lib_root, timeout=120,
    )
    if rc in (0, 1, 2):
        count = 0
        for line in pyright_out.splitlines():
            if "error:" in line and "could not be resolved" not in line:
                count += 1
        result["pyright_count"] = count
        result["pyright_total"] = pyright_out.count("error:")
    else:
        result["errors"].append(f"pyright failed: {pyright_err[:200]}")

    # ── pytest --cov ──────────────────────────────────────────────────
    # Libs without a tests/ directory (e.g. epy_python_kit) skip coverage.
    if not (lib_root / "tests").is_dir():
        result["coverage_pct"] = -2.0  # sentinel: not applicable
        return result

    # Detect the package name under src/ so --cov targets only this lib's
    # source (not the whole venv). The lib dir is sometimes capitalized
    # (ePy_plotter, ePy_suite) but the package dir under src/ is always
    # lowercase.
    pkg_dir = next(
        (p for p in src_dir.iterdir()
         if p.is_dir() and not p.name.endswith(".egg-info")),
        None,
    )
    if pkg_dir is None:
        result["errors"].append(f"no package dir under {src_dir}")
        return result
    pkg_name = pkg_dir.name

    cov_out, cov_err, rc = _run(
        [
            "python", "-m", "pytest", "tests/",
            # Some libs (e.g. epy_simulation) set
            # `--cov --cov-report=term-missing --cov-fail-under=80` in
            # `[tool.pytest.ini_options].addopts`, which clashes with our
            # explicit flags (the missing-line report fragments the TOTAL
            # parse and the fail-under aborts the run before the TOTAL is
            # emitted). Reset addopts so only our flags below apply.
            "-o", "addopts=",
            f"--cov={pkg_name}",
            "--cov-report=term",
            "--cov-fail-under=0",
            "--ignore=tests/_benchmarks",
            "-q", "--tb=no", "-W", "ignore", "--no-header",
        ],
        lib_root, timeout=900,
    )
    if rc in (0, 1):
        for line in cov_out.splitlines():
            if "TOTAL" in line:
                parts = line.strip().split()
                if parts:
                    try:
                        pct = float(parts[-1].rstrip("%"))
                        result["coverage_pct"] = pct
                    except (ValueError, IndexError):
                        pass
                break
    else:
        result["errors"].append(f"pytest failed: {cov_err[:200]}")

    return result


def print_report(result: dict[str, Any], lib_name: str) -> None:
    """Pretty-print the quality report."""
    print()
    print("=" * 60)
    print(f"  Quality Report: {lib_name}")
    print("=" * 60)

    # Ruff
    rc = result.get("ruff_count", -1)
    if rc >= 0:
        total = result.get("ruff_total", 0)
        fixable = result.get("ruff_fixable", 0)
        print(f"\n  ruff:       {rc} non-fixable errors ({total} total, {fixable} auto-fixable)")
        by_rule = result.get("ruff_by_rule", {})
        if by_rule:
            for rule, count in list(by_rule.items())[:5]:
                print(f"    {rule}: {count}")
            if len(by_rule) > 5:
                print(f"    ... and {len(by_rule) - 5} more rule(s)")
    else:
        print(f"\n  ruff:       N/A ({result.get('errors', ['?'])[0]})")

    # Pyright
    pc = result.get("pyright_count", -1)
    if pc >= 0:
        print(f"  pyright:    {pc} typing errors (non-import)")
    else:
        print(f"  pyright:    N/A")

    # Coverage
    cv = result.get("coverage_pct", -1)
    if cv >= 0:
        status = "OK" if cv >= 80 else "BELOW THRESHOLD"
        print(f"  coverage:   {cv:.1f}%  [{status}]")
    elif cv == -2.0:
        print(f"  coverage:   N/A (no tests/ directory)")
    else:
        errs = result.get("errors", [])
        last_err = errs[-1] if errs else "no TOTAL line in pytest output"
        print(f"  coverage:   cannot measure ({last_err})")

    # Errors
    errs = result.get("errors", [])
    if errs:
        print(f"\n  Warnings/errors:")
        for e in errs[:3]:
            print(f"    ! {e}")

    print()
    print("  Recommendation: fix ruff+pyright file by file during feature work.")
    print("  Run: ruff check --fix src/  (for auto-fixable issues)")
    print("=" * 60)


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python _packaging/quality_check.py <lib_path>", file=sys.stderr)
        return 1
    lib_root = Path(sys.argv[1]).resolve()
    if not lib_root.is_dir():
        print(f"Error: {lib_root} is not a directory", file=sys.stderr)
        return 1
    result = run_quality_check(lib_root)
    print_report(result, lib_root.name)
    return 0 if result.get("ruff_count", 1) == 0 and result.get("pyright_count", 1) == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
