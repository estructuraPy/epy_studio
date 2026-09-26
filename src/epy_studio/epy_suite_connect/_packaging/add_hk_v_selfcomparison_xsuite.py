"""Wire the V_ self-comparison rule into every housekeeper.

Loaded BY PATH from ``_packaging/_tooling/v_selfcomparison_block.py``, the
convention ``connect_layout_block.py`` and ``doc_standard_refs_block.py``
already use here: injection is how Rule 13's copies drifted apart until the
same rule behaved differently per library, and the fix for a rule belongs in
one file, not twenty-nine.

What this inserts is a fixed stanza, not a rule body:

* the path-loading import with a LOUD fallback -- a rule that silently stops
  running is worse than one that fails;
* the call and the report, immediately before the ``--strict`` tuple;
* ``or v_selfcomparison_violations`` INSIDE that tuple, verified by parsing the
  patched text back and asserting membership. That last step is how
  ``module_mirror_violations`` was once computed, printed, and never made a
  member: the gate detected and exited 0.

No baseline: the corpus was swept to zero on 2026-08-27 before this landed, so
the rule is a hard failure from the first run.

Idempotent: a housekeeper already carrying the stanza is left untouched.
"""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

ROOT = Path(r"C:\Users\ingah\estructuraPy")

_MARKER = "v_selfcomparison_block.py"
_STRICT_VAR = "v_selfcomparison_violations"

STANZA = '''

# --- V_ validation rows (a comparison needs two numbers) ---------------------
# Imported from the ONE canonical source rather than copied. Measured
# 2026-08-27: 31,208 of 32,527 comparison rows across 570 V_ documents in 16
# repositories put the SAME number in the library column and in the hand-calc
# column, so each read "+0.00 % / PASS" while comparing nothing. Documents
# certified by a fixture under tests/_benchmarks/ are exempt, because there the
# two numbers come from the clause and from the library inside one test.
_V_SELFCMP_BLOCK = (
    Path(__file__).resolve().parent.parent / "_packaging" / "_tooling"
    / "v_selfcomparison_block.py"
)
if _V_SELFCMP_BLOCK.exists():
    import importlib.util as _ilu_vs

    _spec_vs = _ilu_vs.spec_from_file_location("_v_selfcomparison_block", _V_SELFCMP_BLOCK)
    _mod_vs = _ilu_vs.module_from_spec(_spec_vs)
    _spec_vs.loader.exec_module(_mod_vs)
    audit_v_selfcomparison = _mod_vs.audit_v_selfcomparison
    report_v_selfcomparison = _mod_vs.report_v_selfcomparison
else:  # pragma: no cover - only when the tooling repo is absent

    def audit_v_selfcomparison(lib_root):
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
            return []
        return [
            "v-selfcomparison: _packaging/_tooling/v_selfcomparison_block.py is "
            "missing, so the V_ validation rows were NOT checked. This is a loud "
            "failure on purpose: a silently skipped rule is worse than none."
        ]

    def report_v_selfcomparison(violations):
        print("\\n" + "=" * 70)
        print("  V_ VALIDATION ROWS (a comparison needs two numbers)")
        print("=" * 70)
        for v in violations:
            print(f"    - {v}")
'''

CALL = """    # A validation row must compare two independently obtained numbers; a
    # value compared with itself reads PASS and verifies nothing
    v_selfcomparison_violations = audit_v_selfcomparison(LIB_ROOT)
    report_v_selfcomparison(v_selfcomparison_violations)

"""


def discover_libs(root: Path) -> list[Path]:
    """Every checkout carrying a housekeeper."""
    return sorted(
        p
        for p in root.iterdir()
        if p.is_dir() and not p.name.startswith(".") and (p / "housekeeper.py").is_file()
    )


def _strict_members(text: str) -> set[str] | None:
    """Names actually inside an ``if args.strict and (...)`` condition.

    Parsed, not grepped, and the UNION of every such condition: two repos carry
    a separate one-line ``if args.strict and <one_var>:`` ahead of the tuple,
    and reading only the first made a correctly wired patch look unwired there.
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
    """Return the patched source, or the original plus a reason to skip."""
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
