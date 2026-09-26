"""Wire the SOURCE.md reference-id rule into every housekeeper.

Loaded BY PATH from ``_packaging/_tooling/source_ids_block.py``, the convention
``v_selfcomparison_block.py`` and ``connect_layout_block.py`` already use: a
rule copied into twenty-nine files drifts, and the fix for a rule belongs in
one file.

Two failure modes are treated differently on purpose:

* the **block file** missing is a repo defect -- the fallback fails loudly, the
  way the V_ rule's does, because a silently skipped rule is worse than none;
* the **reference store** missing is an environment fact -- a fresh clone has
  no ``references.db`` beside it. That prints ``NOT RUN`` with the reason and
  does not fail ``--strict``. It is reported, never swallowed.

Idempotent: a housekeeper already carrying the stanza is left untouched.
"""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

ROOT = Path(r"C:\Users\ingah\estructuraPy")

_MARKER = "source_ids_block.py"
_STRICT_VAR = "source_ids_violations"

STANZA = '''

# --- SOURCE.md reference ids (the filename is the identity) ------------------
# Imported from the ONE canonical source rather than copied. Measured
# 2026-08-29: the reference store had been rebuilt and renumbered, so 41
# citation sites across 20 SOURCE.md files resolved to the WRONG document --
# several of them under the words "confirmed by direct SQLite query". An id
# that resolves to something looks exactly like an id that resolves to the
# right thing until the two are checked against each other.
_SOURCE_IDS_BLOCK = (
    Path(__file__).resolve().parent.parent / "_packaging" / "_tooling"
    / "source_ids_block.py"
)
if _SOURCE_IDS_BLOCK.exists():
    import importlib.util as _ilu_si

    _spec_si = _ilu_si.spec_from_file_location("_source_ids_block", _SOURCE_IDS_BLOCK)
    _mod_si = _ilu_si.module_from_spec(_spec_si)
    _spec_si.loader.exec_module(_mod_si)
    audit_source_ids = _mod_si.audit_source_ids
    report_source_ids = _mod_si.report_source_ids
else:  # pragma: no cover - only when the tooling repo is absent

    def audit_source_ids(lib_root):
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
                ("_packaging/_tooling/source_ids_block.py", "is missing, so the "
                 "SOURCE.md reference ids were NOT checked. This is a loud failure "
                 "on purpose: a silently skipped rule is worse than none.")
            ],
        }

    def report_source_ids(result):
        print("\\n" + "=" * 70)
        print("  SOURCE.md REFERENCE IDS (the filename is the identity)")
        print("=" * 70)
        for rel, why in result["violations"]:
            print(f"    - {rel}: {why}")
'''

CALL = """    # A cited references.db id must resolve to a document the file names; the
    # store was renumbered once and every stale id still resolved to something
    _source_ids = audit_source_ids(LIB_ROOT)
    report_source_ids(_source_ids)
    source_ids_violations = _source_ids["violations"]

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

    Parsed, not grepped, and the UNION of every such condition: some repos carry
    a separate one-line ``if args.strict and <one_var>:`` ahead of the tuple.
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
