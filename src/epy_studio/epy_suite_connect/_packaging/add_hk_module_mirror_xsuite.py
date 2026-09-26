"""Sync the canonical module-mirror block into every housekeeper.py in the suite.

SYNC, not add-once. Twenty-nine repos carried a hand-maintained copy of
``audit_module_mirror`` with no canonical source anywhere, and they had already
forked four ways in ``_is_mirror_exempt`` and four ways in the audit itself --
including one repo still exempting ``/adapters/`` from the gate and two printing
a mojibake U+FFFD where the message wanted a dash. An injector that skipped
libraries which "already have it" is exactly how that happens, so this one
replaces.

Strategy
--------
1. Replace the contiguous run of top-level definitions the block owns, bounded
   by their OWN AST source spans.
2. If the block is absent, insert it before a stable anchor and wire it into
   ``main()``.
3. Refuse any patch whose result loses a top-level definition.

Usage:
  python add_hk_module_mirror_xsuite.py           # dry-run every repo
  python add_hk_module_mirror_xsuite.py --apply
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path

ROOT = Path(r"C:\Users\ingah\estructuraPy")

# Every sibling repo that carries a housekeeper. Discovery is by glob rather
# than a hardcoded list: the hardcoded list in the Rule 13 injector silently
# skipped `ePy_plotter` for a year because it spelled the directory
# `epy_plotter`, which only resolved at all thanks to Windows being
# case-insensitive, and it named a repo that had since been retired.


def discover_libs(root: Path) -> list[str]:
    """Repo directories under `root` that ship a housekeeper.py."""
    return sorted(
        (hk.parent.name for hk in root.glob("*/housekeeper.py")),
        key=str.lower,
    )


# The block lives in ONE place. Editing it here instead of there is how the
# twenty-nine copies drifted in the first place.
sys.path.insert(0, str(Path(__file__).parent))
from module_mirror_block import MODULE_MIRROR_BLOCK as FUNC_BLOCK  # noqa: E402

WIRE_INSERT = (
    "    # Module-level tests-mirror audit (every real src module has a mirroring\n"
    "    # test, and that test's imports resolve -- suite-wide DNA)\n"
    "    module_mirror_violations = audit_module_mirror(LIB_ROOT)\n"
    "    report_module_mirror(module_mirror_violations)\n\n"
)

#: Every top-level function the canonical block owns. The span below covers the
#: whole contiguous run of these names, so a re-sync REPLACES the helpers
#: instead of stranding them above the window. The first rollout of the Rule 13
#: block did exactly that -- the span started at the audit function, the
#: replacement re-inserted the full block, helper included, and the previous
#: helper survived untouched above it: one duplicate copy per sync, in sixteen
#: repos at once.
_MIRROR_FUNCTIONS = frozenset(
    {
        "_is_mirror_exempt",
        "_mirror_import_roots",
        "_mirror_module_exists",
        "_mirror_dead_imports",
        "_mirror_advisory",
        "audit_module_mirror",
        "report_module_mirror",
    }
)


def _mirror_span(text: str) -> tuple[int, int] | None:
    """Return the character span covering the block's own functions.

    The span runs over the contiguous run of top-level definitions whose names
    the block owns, duplicates included, so a prior sync's stranded copy is
    swept up. Anything ELSE sitting inside that run belongs to somebody else,
    and the sync refuses rather than swallowing it: the previous version of the
    Rule 13 injector ran from one `def` to a `def` it assumed "always follows",
    another campaign inserted a function in between, and the sync ate that
    function whole in every housekeeper it touched.
    """
    tree = ast.parse(text)
    defs = [n for n in tree.body if isinstance(n, ast.FunctionDef)]
    owned = [i for i, n in enumerate(defs) if n.name in _MIRROR_FUNCTIONS]
    if not owned or "audit_module_mirror" not in {defs[i].name for i in owned}:
        return None
    if owned != list(range(owned[0], owned[-1] + 1)):
        # A foreign function sits inside the run; replacing the span would
        # delete it. That is the failure mode the loss guard exists for.
        return None

    first, last = defs[owned[0]], defs[owned[-1]]
    lines = text.splitlines(keepends=True)
    offsets = [0]
    for line in lines:
        offsets.append(offsets[-1] + len(line))
    # end_lineno is inclusive and 1-based. Absorb the blank-line separator that
    # follows so re-writing it cannot accumulate or erase blank lines.
    start = offsets[first.lineno - 1]
    end = offsets[last.end_lineno]
    while end < len(text) and text[end] == "\n":
        end += 1
    return start, end


def _rendered(text: str, end: int) -> str:
    """The block plus the blank-line separator its position calls for.

    Two blank lines before whatever follows, per PEP 8; nothing extra when the
    block lands at end of file.
    """
    body = FUNC_BLOCK.rstrip("\n")
    return body + ("\n\n\n" if end < len(text) else "\n")


def _module_functions(text: str) -> set[str]:
    """Top-level function names, for the before/after loss check below."""
    return {n.name for n in ast.parse(text).body if isinstance(n, ast.FunctionDef)}


def _ensure_strict_wired(text: str) -> tuple[str, str | None]:
    """Make ``--strict`` actually listen to the mirror rule, idempotently.

    Syncing the FUNCTION is not the same as enforcing the RULE. Until
    2026-08-21 this script checked only that ``audit_module_mirror`` was
    present and then returned "already canonical", while ePy_plotter and
    epy_analysis computed ``module_mirror_violations``, printed the report,
    and exited 0 because the name was never a member of their
    ``if args.strict and (...)`` tuple. A rule that detects perfectly and
    exits 0 is not a gate, and both repos were unenforced for as long as the
    block had been installed. The old fresh-install path could not have
    fixed them either: it rewrote the FIRST tuple in the file, which is not
    necessarily the terminal gate.

    Returns the text and a note, or ``(text, None)`` when already wired.
    """
    anchor = "if args.strict and ("
    if anchor not in text:
        return text, "no strict tuple -- the rule runs but CANNOT fail the run"
    start = text.rindex(anchor)  # the terminal gate, not the first one
    close = text.index("    ):", start)
    if "module_mirror_violations" in text[start:close]:
        return text, None
    note = "WIRED into --strict (the rule ran but could not fail the run)"
    term = "        or module_mirror_violations\n"
    return text[:close] + term + text[close:], note


def patch_hk(text: str) -> tuple[str, list[str]]:
    """Return the patched housekeeper text and human-readable notes."""
    if "audit_module_mirror" in text:
        span = _mirror_span(text)
        if span is None:
            return text, ["existing block present but its functions are not adjacent"]
        start, end = span
        block = _rendered(text, end)
        note = "already canonical"
        if text[start:end] != block:
            text = text[:start] + block + text[end:]
            note = "resynced to canonical"
        text, wired = _ensure_strict_wired(text)
        return text, [note] + ([wired] if wired else [])

    notes: list[str] = []
    # 1. insert the function block before a stable anchor.
    insert_anchor = next(
        (
            a
            for a in (
                "def audit_tutorials_layout(",
                "def audit_directory_depth(",
                "def main(",
            )
            if a in text
        ),
        None,
    )
    if insert_anchor is None:
        return text, ["no insertion anchor"]
    text = text.replace(
        insert_anchor, FUNC_BLOCK.rstrip("\n") + "\n\n\n" + insert_anchor, 1
    )
    notes.append("inserted the module-mirror block")

    # 2. wire it into main() ahead of the strict check.
    if "if args.strict and (" not in text:
        return text, notes + ["no strict-check anchor -- block inserted but NOT wired"]
    text = text.replace(
        "    if args.strict and (", WIRE_INSERT + "    if args.strict and (", 1
    )
    notes.append("wired into main()")

    # 3. extend the strict-check tuple -- the TERMINAL one, through the same
    #    helper the resync path uses, so a fresh install and a resync wire
    #    identically.
    text, wired = _ensure_strict_wired(text)
    if wired:
        notes.append(wired)
    # The strict-tuple rewrite splits a line and leaves trailing whitespace
    # behind, which trips W293 and turns a green lint gate red. Normalise what
    # this script writes rather than leaving it for a human.
    text = re.sub(r"[ \t]+\n", "\n", text)
    return text, notes


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument(
        "--only",
        nargs="+",
        help="restrict to these repos -- the suite routinely has campaigns "
        "mid-flight elsewhere, and a sync must not land in a dirty tree",
    )
    ap.add_argument(
        "--root",
        type=Path,
        default=ROOT,
        help="suite root to sync (the detection proof points this at a tmp tree)",
    )
    args = ap.parse_args()
    root = args.root

    failed = 0
    for lib in args.only or discover_libs(root):
        hk = root / lib / "housekeeper.py"
        if not hk.is_file():
            print(f"  [skip] {lib}: no housekeeper.py")
            continue
        text = hk.read_text(encoding="utf-8")
        new_text, notes = patch_hk(text)
        lost = _module_functions(text) - _module_functions(new_text)
        # Deduplicating the block's OWN helpers is sanctioned; losing any other
        # name is not.
        lost -= _MIRROR_FUNCTIONS & _module_functions(new_text)
        if lost:
            # The failure this exists for: a sync that deletes somebody else's
            # function leaves a housekeeper that still calls it, and the repo
            # only finds out at the next run.
            print(f"  [REFUSED] {lib}: patch would delete {sorted(lost)}")
            failed = 1
            continue
        if new_text == text:
            print(f"  [skip] {lib}: {'; '.join(notes)}")
            continue
        print(f"  [{'apply' if args.apply else 'dry'}] {lib}: {'; '.join(notes)}")
        if args.apply:
            hk.write_text(new_text, encoding="utf-8")
    return failed


if __name__ == "__main__":
    sys.exit(main())
