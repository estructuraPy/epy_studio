"""Patch housekeeper.py of every lib to add the loader-only rule.

The rule enforces a standing user directive: inside a library, ``.epyson``
files are read ONLY through that library's own ``_config/_loader``. A raw
``json.load`` / ``read_text`` on an epyson path anywhere else bypasses the
loader's typed-id validation, its "available ids" error messages and its
``audit_status`` warning — which is exactly how a suite-wide audit found 54
raw readers across 11 libraries, three of them silently substituting
hardcoded normative data when the read failed.

Auditing that by hand does not hold: this makes the housekeeper fail on it,
so the rule is enforced instead of periodically re-discovered.

Idempotent: a lib whose housekeeper already defines ``audit_loader_only`` is
skipped.

Strategy (mirrors add_hk_rule13_xsuite.py)
------------------------------------------
1. Insert the two function blocks (``audit_loader_only`` +
   ``report_loader_only``) immediately before ``def audit_directory_depth(``.
2. Inject the call + report before the ``if args.strict and (`` block.
3. Extend the strict-check tuple with ``or loader_only_violations``.

Usage:
  python add_hk_loader_only_xsuite.py            # dry-run all libs
  python add_hk_loader_only_xsuite.py --apply
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(r"C:\Users\ingah\estructuraPy")
LIBS = [
    "epy_analysis", "epy_bridges", "epy_buildings", "epy_compose",
    "epy_concrete", "epy_connections", "epy_geotechnical", "epy_houses",
    "epy_masonry", "epy_plotter", "epy_steel", "epy_structure",
    "epy_suite", "epy_tall", "epy_tanks", "epy_timber", "epy_towers",
]

FUNC_BLOCK = '''def audit_loader_only(lib_root: Path) -> list[str]:
    """Verify `.epyson` files are read ONLY through `_config/_loader`.

    A raw `json.load` / `read_text` on an epyson path outside the loader
    bypasses typed-id validation, the "available ids" error message and the
    `audit_status` warning. Worse, every such reader historically grew its
    own failure handling, and several degraded into hardcoded normative
    data when the read failed.

    Two kinds of read are NOT violations and are skipped:
    - housekeeping/migration tooling that walks every `.epyson` by design
      (`_core/_tooling/`, `_packaging/format_epyson`, `_packaging/validate_epyson`);
    - loaders of a CALLER-SUPPLIED file (a path the user passes in), which
      are an input contract, not a bundled catalog. Those are recognised by
      the file taking its path as a parameter rather than deriving it from
      `__file__`.
    """
    pkg = _find_pkg_dir(lib_root)
    if pkg is None:
        return []

    raw_read = re.compile(r"json\\.loads?\\s*\\(|\\.read_text\\s*\\(|\\bopen\\s*\\(")
    epyson_ref = re.compile(r"\\.epyson\\b")
    derives_own_path = re.compile(r"__file__")
    tooling_parts = {"_tooling", "format_epyson", "validate_epyson"}

    violations: list[str] = []
    for path in sorted(pkg.rglob("*.py")):
        parts = set(path.parts)
        if parts & tooling_parts:
            continue
        # the loader itself is the sanctioned reader
        if "_loader" in path.parts or path.name == "_loader.py":
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if not epyson_ref.search(text) or not raw_read.search(text):
            continue
        # a module that never derives a path from its own location is reading
        # something the caller handed it - an input contract, not a catalog
        if not derives_own_path.search(text):
            continue
        rel = path.relative_to(lib_root)
        violations.append(
            f"{rel}: reads a bundled .epyson directly; route it through "
            f"_config/_loader (add an accessor there if one is missing)"
        )
    return violations


def report_loader_only(violations: list[str]) -> None:
    if not violations:
        print("\\n  loader-only (.epyson access): OK (every bundled catalog read goes through _config/_loader)")
        return
    print(f"\\n  loader-only (.epyson access): {len(violations)} violation(s):")
    for v in violations[:30]:
        print(f"    - {v}")
    if len(violations) > 30:
        print(f"    ... and {len(violations) - 30} more")


'''

WIRE_INSERT = (
    "    # .epyson loader-only access audit\n"
    "    loader_only_violations = audit_loader_only(LIB_ROOT)\n"
    "    report_loader_only(loader_only_violations)\n\n"
)


def patch_hk(text: str) -> tuple[str, list[str]]:
    notes: list[str] = []
    if "audit_loader_only" in text:
        return text, ["already patched"]

    if "def audit_directory_depth(" not in text:
        return text, ["no audit_directory_depth anchor"]
    text = text.replace(
        "def audit_directory_depth(",
        FUNC_BLOCK + "def audit_directory_depth(",
        1,
    )
    notes.append("inserted audit_loader_only + report functions")

    if "if args.strict and (" not in text:
        return text, ["no strict-check anchor"]
    text = text.replace(
        "    if args.strict and (",
        WIRE_INSERT + "    if args.strict and (",
        1,
    )
    notes.append("wired into main()")

    m = re.search(r"if args\.strict and \([^)]*\):", text)
    if m:
        old = m.group(0)
        new = old[:-2].rstrip() + "\n        or loader_only_violations\n    ):"
        text = text.replace(old, new, 1)
        notes.append("extended strict tuple")
    else:
        notes.append("WARNING: could not extend strict tuple - wire manually")

    return text, notes


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true", help="write changes (default: dry-run)")
    ap.add_argument("--libs", nargs="*", default=LIBS, help="subset of libs to patch")
    args = ap.parse_args()

    rc = 0
    for lib in args.libs:
        hk = ROOT / lib / "housekeeper.py"
        if not hk.is_file():
            print(f"{lib}: no housekeeper.py - skipped")
            continue
        text = hk.read_text(encoding="utf-8")
        patched, notes = patch_hk(text)
        status = "APPLY" if (args.apply and patched != text) else "dry-run"
        print(f"{lib}: {status} - {'; '.join(notes)}")
        if any(n.startswith(("no ", "WARNING")) for n in notes):
            rc = 1
        if args.apply and patched != text:
            hk.write_text(patched, encoding="utf-8")
    return rc


if __name__ == "__main__":
    sys.exit(main())
