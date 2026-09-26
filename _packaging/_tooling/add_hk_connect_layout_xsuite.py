"""Wire the epy_suite_connect layout rule into every housekeeper.

Unlike the six injected blocks, this one is loaded BY PATH from
``_packaging/_tooling/connect_layout_block.py`` -- the convention
``doc_standard_refs_block.py`` already uses here. Injection was how Rule 13's
copies drifted apart until the same rule behaved differently per library, and
the fix for a rule is a rule change in one file, not twenty-nine.

So what this inserts is a fixed stanza, not a rule body:

* the path-loading import, with a LOUD fallback -- a rule that silently stops
  running is worse than one that fails;
* the call and the report, immediately before the ``--strict`` tuple;
* ``or connect_layout_violations`` INSIDE that tuple. Skipping this last step is
  how ``module_mirror_violations`` was computed, printed, and never made a
  member of the tuple in two repos: the gate detected and exited 0. Verified
  here by parsing the patched text back and asserting membership, not by
  assuming the replace landed.

Idempotent: a housekeeper already carrying the stanza is left untouched.
"""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

ROOT = Path(r"C:\Users\ingah\estructuraPy")

_MARKER = "connect_layout_block.py"
_STRICT_VAR = "connect_layout_violations"

STANZA = '''

# --- epy_suite_connect layout (three concerns + the prefix rule) -------------
# Imported from the ONE canonical source rather than copied. `audit_structure`
# only asks whether a file is somewhere inside the layer, so a module loose at
# its root satisfies it -- epy_towers, with six of them and a non-prefixed
# `adapters/`, printed "Structure: OK (canonical layout)" and exited 0.
_CONNECT_LAYOUT_BLOCK = (
    Path(__file__).resolve().parent.parent / "_packaging" / "_tooling"
    / "connect_layout_block.py"
)
if _CONNECT_LAYOUT_BLOCK.exists():
    import importlib.util as _ilu_cl

    _spec_cl = _ilu_cl.spec_from_file_location(
        "_connect_layout_block", _CONNECT_LAYOUT_BLOCK
    )
    _mod_cl = _ilu_cl.module_from_spec(_spec_cl)
    _spec_cl.loader.exec_module(_mod_cl)
    audit_connect_layout_strict = _mod_cl.audit_connect_layout_strict
    report_connect_layout = _mod_cl.report_connect_layout
else:  # pragma: no cover - only when the tooling repo is absent

    def audit_connect_layout_strict(lib_root):
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
            "connect-layout: _packaging/_tooling/connect_layout_block.py is "
            "missing, so the epy_suite_connect layout was NOT checked. This is "
            "a loud failure on purpose: a silently skipped rule is worse than "
            "none."
        ]

    def report_connect_layout(violations):
        print("\\n" + "=" * 70)
        print("  epy_suite_connect LAYOUT (three concerns + prefix rule)")
        print("=" * 70)
        for v in violations:
            print(f"    - {v}")
'''

CALL = """    # epy_suite_connect keeps its three concerns in three directories, and
    # the adapters folder carries the suite's underscore prefix
    connect_layout_violations = audit_connect_layout_strict(LIB_ROOT)
    report_connect_layout(connect_layout_violations)

"""


def discover_libs(root: Path) -> list[Path]:
    """Every checkout carrying a housekeeper."""
    return sorted(
        p
        for p in root.iterdir()
        if p.is_dir() and not p.name.startswith(".") and (p / "housekeeper.py").is_file()
    )


def _strict_members(text: str) -> set[str] | None:
    """Names actually inside the ``if args.strict and (...)`` condition.

    Parsed, not grepped. A previous rule was "wired" by a substitution that
    landed next to the tuple rather than inside it, and reading the source for
    the variable name found it either way.
    """
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return None
    # The UNION of every `args.strict` condition, not the first one found.
    # epy_analysis and ePy_plotter both carry a separate one-line
    # `if args.strict and tutorials_layout_violations:` ahead of the tuple, and
    # reading only the first condition made a correctly wired patch look
    # unwired in exactly those two repos.
    found: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.If):
            continue
        test = node.test
        if not (isinstance(test, ast.BoolOp) and isinstance(test.op, ast.And)):
            continue
        # `args.strict` specifically. A first draft accepted any `and` whose
        # condition merely mentioned `args`, and returned the FIRST match in
        # the module -- which in epy_analysis and ePy_plotter is a different
        # `if args.<something> and (...)` earlier in the file. Both refused
        # correctly wired patches. Those two are also the pair where
        # `module_mirror_violations` was found computed, printed and never a
        # member of this tuple, so a checker that reads the wrong condition in
        # exactly those two repos is the last thing this needs.
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

    # Insert the tuple member on the line before the tuple's closing "    ):".
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
    args = parser.parse_args()

    libs = discover_libs(ROOT)
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
