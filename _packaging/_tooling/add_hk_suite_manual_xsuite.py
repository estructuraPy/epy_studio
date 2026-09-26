"""Wire the suite-manual duplication rule into every housekeeper.

Loaded BY PATH from ``_packaging/_tooling/suite_manual_block.py``, the same
convention ``source_ids_block.py``, ``v_selfcomparison_block.py`` and
``connect_layout_block.py`` use: a rule copied into thirty files drifts, and
the fix for a rule belongs in one file. The machinery below -- the stanza, the
``rindex``-free single-anchor patch, and the AST check that the strict variable
landed INSIDE the condition rather than merely near it -- is lifted from
``add_hk_source_ids_xsuite.py`` unchanged; only the block, the names and the
prose differ.

Why the rule exists: measured 2026-09-02, ``ePy_Suite_Capacidades.md`` existed
twice -- in ``references/`` and inside ``epy_docs/`` -- and had been drifting
apart for two months, the library copy two editions ahead. Building the next
edition on the wrong one would have resurrected the retired WebGL viewer, the
``.klito`` format and ``ePy_suite`` as a live orchestrator. Nobody was careless;
both files were edited by someone who believed theirs was canonical. That is
why it cannot be left to discipline.

Idempotent: a housekeeper already carrying the stanza is left untouched.
"""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

ROOT = Path(r"C:\Users\ingah\estructuraPy")

_MARKER = "suite_manual_block.py"
_STRICT_VAR = "suite_manual_violations"

STANZA = '''

# --- Suite-wide manual: one home, and it is not a library repo ---------------
# Imported from the ONE canonical source rather than copied. Measured
# 2026-09-02: ePy_Suite_Capacidades.md existed in references/ AND in epy_docs/,
# two editions apart after two months of independent edits. A second copy of a
# suite document inside a library repo always drifts, because that repo is
# where the person editing that library is looking.
_SUITE_MANUAL_BLOCK = (
    Path(__file__).resolve().parent.parent / "_packaging" / "_tooling"
    / "suite_manual_block.py"
)
if _SUITE_MANUAL_BLOCK.exists():
    import importlib.util as _ilu_sm

    _spec_sm = _ilu_sm.spec_from_file_location("_suite_manual_block", _SUITE_MANUAL_BLOCK)
    _mod_sm = _ilu_sm.module_from_spec(_spec_sm)
    _spec_sm.loader.exec_module(_mod_sm)
    audit_suite_manual = _mod_sm.audit_suite_manual
    report_suite_manual = _mod_sm.report_suite_manual
else:  # pragma: no cover - only when the tooling repo is absent

    def audit_suite_manual(lib_root):
        # The suite tooling is an OPTIONAL half, exactly like
        # epy_docs: a third party's clone of a public repository, or
        # a runner that checks out one repository, does not have it
        # and cannot run this rule. Reported by name, not failed on.
        # A tooling checkout that EXISTS and is missing this block is
        # a different thing, and stays loud: there the rule was
        # expected to run.
        _tooling = (
            Path(__file__).resolve().parent.parent
            / "_packaging" / "_tooling"
        )
        if not _tooling.is_dir():
            return {"ran": False, "why": None, "violations": []}
        return {
            "ran": True,
            "why": None,
            "violations": [
                ("_packaging/_tooling/suite_manual_block.py", "is missing, so the "
                 "suite-manual duplication rule was NOT checked. This is a loud "
                 "failure on purpose: a silently skipped rule is worse than none.")
            ],
        }

    def report_suite_manual(result):
        print("\\n" + "=" * 70)
        print("  SUITE-WIDE MANUAL (one home: references/, never a library repo)")
        print("=" * 70)
        for rel, why in result["violations"]:
            print(f"    - {rel}: {why}")
'''

CALL = """    # A suite-wide manual duplicated into a library repo will drift; the
    # canonical file lives in references/ and a pointer here is enough
    _suite_manual = audit_suite_manual(LIB_ROOT)
    report_suite_manual(_suite_manual)
    suite_manual_violations = _suite_manual["violations"]

"""


def discover_libs(root: Path) -> list[Path]:
    """Every checkout carrying a housekeeper.

    Args:
        root: Suite root holding the library checkouts.

    Returns:
        list[Path]: Library directories that ship a ``housekeeper.py``.

    """
    return sorted(
        p
        for p in root.iterdir()
        if p.is_dir() and not p.name.startswith(".") and (p / "housekeeper.py").is_file()
    )


def _strict_members(text: str) -> set[str] | None:
    """Names actually inside an ``if args.strict and (...)`` condition.

    Parsed, not grepped, and the UNION of every such condition: some repos carry
    a separate one-line ``if args.strict and <one_var>:`` ahead of the tuple.

    Args:
        text: Housekeeper source.

    Returns:
        set[str] | None: The names found, or None when nothing parsed.

    """
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return None
    found: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.If):
            continue
        test = node.test
        if not (isinstance(test, ast.BoolOp) and isinstance(test.op, ast.And)):
            continue
        if not any(
            isinstance(v, ast.Attribute)
            and v.attr == "strict"
            and isinstance(v.value, ast.Name)
            and v.value.id == "args"
            for v in ast.walk(test)
        ):
            continue
        found.update(n.id for n in ast.walk(test) if isinstance(n, ast.Name))
    return found if found else None


def patch(text: str) -> tuple[str, str | None]:
    """Return the patched source, or the original plus a reason to skip.

    Args:
        text: Housekeeper source.

    Returns:
        tuple[str, str | None]: Patched source and, when it could not be
        patched, why.

    """
    if _MARKER in text:
        return text, "already wired"

    anchor = "\ndef main() -> None:"
    if text.count(anchor) != 1:
        return text, f"expected one 'def main() -> None:', found {text.count(anchor)}"
    text = text.replace(anchor, STANZA + "\n" + anchor.lstrip("\n"), 1)

    strict_anchor = "    if args.strict and ("
    if text.count(strict_anchor) != 1:
        return text, f"expected one strict tuple, found {text.count(strict_anchor)}"
    text = text.replace(strict_anchor, CALL + strict_anchor, 1)

    head, sep, tail = text.partition(strict_anchor)
    close = "\n    ):"
    if close not in tail:
        return text, "strict tuple has no recognisable close"
    before, _, after = tail.partition(close)
    text = head + sep + before + f"\n        or {_STRICT_VAR}" + close + after

    members = _strict_members(text)
    if members is None:
        return text, "patched source does not parse"
    if _STRICT_VAR not in members:
        return text, f"{_STRICT_VAR} did not land INSIDE the strict condition"
    return text, None


def main() -> int:
    """Wire the rule into every discovered housekeeper.

    Returns:
        int: 1 if any repo refused the patch, else 0.

    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Write the changes.")
    parser.add_argument("--only", nargs="*", help="Limit to these library names.")
    args = parser.parse_args()

    libs = discover_libs(ROOT)
    if args.only:
        libs = [p for p in libs if p.name in set(args.only)]
    print(f"{len(libs)} housekeepers found\n")
    changed = skipped = failed = 0
    for lib in libs:
        hk = lib / "housekeeper.py"
        original = hk.read_text(encoding="utf-8")
        patched, reason = patch(original)
        if reason == "already wired":
            skipped += 1
            print(f"  = {lib.name}: already wired")
            continue
        if reason:
            failed += 1
            print(f"  ! {lib.name}: {reason}")
            continue
        changed += 1
        print(f"  + {lib.name}: wired")
        if args.apply:
            hk.write_text(patched, encoding="utf-8")

    print(f"\n{changed} to wire, {skipped} already wired, {failed} refused")
    if not args.apply:
        print("DRY RUN -- re-run with --apply")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
