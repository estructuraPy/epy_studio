"""Deploy the canonical shadowed-test gate to every repo's housekeeper.

Derived from ``add_hk_rule8_xsuite.py``: the machinery -- AST-bounded spans
over the block's OWN functions, the refusal to drop a definition it does not
own, and wiring the audit into the TERMINAL ``if args.strict and (...)`` tuple
by ``rindex`` -- is rule-independent and was paid for four times over by
earlier rollouts. Only the block, the wiring snippet, the owned function
names and the strict variable differ.

The rule: Python keeps the LAST binding of a name, so an earlier ``class
TestFoo`` in the same module is discarded whole and every test inside it stops
being collected. Nothing reports it. Measured 2026-08-22: 29 such tests in
five repos, all of which PASSED once woken.
"""


from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path

ROOT = Path(r"C:\Users\ingah\estructuraPy")


def discover_libs(root: Path) -> list[str]:
    """Repo directories under `root` that ship a housekeeper.py.

    Discovery is by glob rather than a hardcoded list: the hardcoded list in
    the Rule 13 injector silently skipped `ePy_plotter` for a year because it
    spelled the directory `epy_plotter`, which only resolved at all thanks to
    Windows being case-insensitive.
    """
    return sorted(
        (hk.parent.name for hk in root.glob("*/housekeeper.py")),
        key=str.lower,
    )


# The block lives in ONE place. Editing it here instead of there is how the
# seventeen copies drifted in the first place.
sys.path.insert(0, str(Path(__file__).parent))
from shadowed_tests_block import SHADOWED_TESTS_BLOCK as FUNC_BLOCK  # noqa: E402

WIRE_INSERT = (
    "    # Shadowed-test audit (a definition discarded by a later one of\n"
    "    # the same name takes every test inside it out of collection)\n"
    "    shadowed_violations = audit_no_shadowed_tests(LIB_ROOT)\n"
    "    report_shadowed_tests(shadowed_violations)\n\n"
)

#: Every top-level function the canonical block owns. Each RUN of these names
#: is replaced, duplicates included, so a prior sync's stranded copy is swept
#: up. The first rollout of the Rule 13 block stranded one instead: its span
#: started at the audit function, the replacement re-inserted the full block,
#: helper included, and the previous helper survived untouched above it -- one
#: duplicate copy per sync, in sixteen repos at once.
#:
#: Mutable on purpose (a plain module attribute, not a constant folded into the
#: functions below): the detection proof rebinds it to include a name the block
#: does NOT define, which is how the "would delete a definition it does not
#: own" refusal in `main()` is exercised rather than merely asserted in a
#: comment.
_RULE8_FUNCTIONS = frozenset(
    {
        "_shadowed_definitions_in_source",
        "audit_no_shadowed_tests",
        "report_shadowed_tests",
    }
)

#: Module-level names the earlier copies of this gate needed and the canonical
#: block does not: the per-line regex it replaces, and the two sets that are
#: now locals inside `_skip_violations_in_source`. They are removed only when
#: NOTHING reads them any more -- see `_superseded_spans`. Leaving
#: `_PYTEST_SKIP_RE` behind would be worse than untidy: it is the exact blind
#: regex this block exists to retire, and a dead one sitting in the file is an
#: invitation to wire it back up.
#: Nothing predates this gate, so there is no earlier implementation to
#: sweep. Kept empty rather than removed: `_superseded_spans` reads it,
#: and an empty frozenset says 'checked, none' where a missing name would
#: say 'never considered'.
_SUPERSEDED_NAMES: frozenset[str] = frozenset()

#: The local `main()` binds the audit result to this name; membership of the
#: terminal strict tuple is what turns detection into enforcement.
_STRICT_VAR = "shadowed_violations"


def _line_offsets(text: str) -> list[int]:
    """Character offset of the start of each line, plus end-of-text."""
    offsets = [0]
    for line in text.splitlines(keepends=True):
        offsets.append(offsets[-1] + len(line))
    return offsets


def _node_span(text: str, first: ast.stmt, last: ast.stmt) -> tuple[int, int]:
    """Character span from the head of `first` to the tail of `last`.

    ``end_lineno`` is inclusive and 1-based. The trailing blank lines are
    absorbed so re-writing the span cannot accumulate or erase separators.
    """
    offsets = _line_offsets(text)
    start = offsets[first.lineno - 1]
    end = offsets[last.end_lineno]
    while end < len(text) and text[end] == "\n":
        end += 1
    return start, end


def _owned_runs(text: str) -> list[tuple[int, int]]:
    """Character spans of every maximal run of top-level definitions we own.

    Indexing is over ``tree.body``, so a run is broken by ANY intervening
    top-level node -- an import, a constant, an ``if`` -- not merely by another
    function. That is the whole guard: the previous version of the Rule 13
    injector ran from one `def` to a `def` it assumed "always follows",
    another campaign inserted a function in between, and the sync ate that
    function whole in every housekeeper it touched.
    """
    body = ast.parse(text).body
    owned = [
        i
        for i, n in enumerate(body)
        if isinstance(n, ast.FunctionDef) and n.name in _RULE8_FUNCTIONS
    ]
    runs: list[tuple[int, int]] = []
    start_i = None
    prev = None
    for i in owned:
        if start_i is None:
            start_i = i
        elif prev is not None and i != prev + 1:
            runs.append(_node_span(text, body[start_i], body[prev]))
            start_i = i
        prev = i
    if start_i is not None and prev is not None:
        runs.append(_node_span(text, body[start_i], body[prev]))
    return runs


def _rendered(at_eof: bool) -> str:
    """The block plus the blank-line separator its position calls for.

    Two blank lines before whatever follows, per PEP 8; nothing extra when the
    block lands at end of file.
    """
    return FUNC_BLOCK.rstrip("\n") + ("\n" if at_eof else "\n\n\n")


def _module_functions(text: str) -> list[str]:
    """Top-level function names, WITH duplicates, for the loss check below."""
    return [n.name for n in ast.parse(text).body if isinstance(n, ast.FunctionDef)]


def _name_loads(text: str, name: str) -> int:
    """How many times `name` is READ anywhere in the module.

    Assignment targets do not count -- only loads. This is what decides
    whether a superseded module constant is dead or still in service.
    """
    return sum(
        1
        for n in ast.walk(ast.parse(text))
        if isinstance(n, ast.Name) and n.id == name and isinstance(n.ctx, ast.Load)
    )


def _name_bound(text: str, name: str) -> bool:
    """Whether `name` is bound anywhere at module level."""
    return any(
        isinstance(n, ast.Name) and n.id == name and isinstance(n.ctx, ast.Store)
        for n in ast.walk(ast.parse(text))
    )


def _superseded_spans(text: str) -> list[tuple[int, int, str]]:
    """Spans of dead top-level assignments this block supersedes.

    Only names in `_SUPERSEDED_NAMES`, only at top level, and only when
    `_name_loads` says nothing reads them any more. The span absorbs the
    contiguous run of full-line `#` comments directly above the assignment --
    that run documents the constant and is meaningless without it.
    """
    body = ast.parse(text).body
    offsets = _line_offsets(text)
    lines = text.splitlines()
    spans: list[tuple[int, int, str]] = []
    for node in body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name) or target.id not in _SUPERSEDED_NAMES:
            continue
        if _name_loads(text, target.id):
            continue  # still in service somewhere -- leave it alone
        first_line = node.lineno  # 1-based
        while first_line > 1 and lines[first_line - 2].lstrip().startswith("#"):
            first_line -= 1
        start = offsets[first_line - 1]
        _, end = _node_span(text, node, node)
        spans.append((start, end, target.id))
    return spans


def _sweep_superseded(text: str) -> tuple[str, list[str]]:
    """Remove dead superseded constants, last span first so offsets hold."""
    spans = _superseded_spans(text)
    if not spans:
        return text, []
    for start, end, _ in sorted(spans, reverse=True):
        text = text[:start] + text[end:]
    names = sorted(name for _, _, name in spans)
    return text, [f"removed superseded `{n}`" for n in names]


def _ensure_strict_wired(text: str) -> tuple[str, str | None]:
    """Make ``--strict`` actually listen to Rule 8, idempotently.

    Syncing the FUNCTION is not the same as enforcing the RULE. The mirror
    injector checked only that its audit function was present and then reported
    "already canonical", while two repos computed the violations, printed the
    report, and exited 0 because the name was never a member of their
    ``if args.strict and (...)`` tuple. A rule that detects perfectly and exits
    0 is not a gate. Its old fresh-install path could not have fixed them
    either: it rewrote the FIRST tuple in the file, which is not necessarily
    the terminal gate -- epy_analysis, for one, carries an earlier
    ``if args.strict and tutorials_layout_violations:`` before it.

    Returns the text and a note, or ``(text, None)`` when already wired.
    """
    anchor = "if args.strict and ("
    if anchor not in text:
        return text, "no strict tuple -- the rule runs but CANNOT fail the run"
    start = text.rindex(anchor)  # the terminal gate, not the first one
    close = text.index("    ):", start)
    if _STRICT_VAR in text[start:close]:
        return text, None
    note = f"added `{_STRICT_VAR}` to the terminal --strict tuple"
    term = f"        or {_STRICT_VAR}\n"
    return text[:close] + term + text[close:], note


def _finish(text: str, original: str) -> str:
    """Normalise what this script writes, never what it merely read.

    The strict-tuple rewrite splits a line and leaves trailing whitespace
    behind, which trips W293 and turns a green lint gate red. Deleting a run at
    end of file leaves a pile of newlines.
    """
    if text == original:
        return text
    text = re.sub(r"[ \t]+\n", "\n", text)
    if original.endswith("\n"):
        text = text.rstrip("\n") + "\n"
    return text


def patch_hk(text: str) -> tuple[str, list[str]]:
    """Return the patched housekeeper text and human-readable notes."""
    original = text
    runs = _owned_runs(text)

    if runs:
        block = _rendered(at_eof=runs[0][1] >= len(text))
        # Delete every run last-first so the earlier offsets stay valid, then
        # re-insert the canonical block where the first one was. Scattered
        # copies converge on one contiguous, greppable unit.
        head = runs[0][0]
        for start, end in reversed(runs):
            text = text[:start] + text[end:]
        text = text[:head] + block + text[head:]
        notes = ["already canonical"] if text == original else ["resynced to canonical"]
        if len(runs) > 1 and text != original:
            notes.append(f"gathered {len(runs)} scattered definition runs into one")
        text, swept = _sweep_superseded(text)
        notes += swept
        text, wired = _ensure_strict_wired(text)
        if wired:
            # On the RESYNC path this is the loud one: the repo already had a
            # working audit, printed its report, and exited 0 regardless.
            notes.append(f"{wired} -- IT RAN BUT COULD NOT FAIL THE RUN")
        return _finish(text, original), notes

    notes: list[str] = []
    # 1. insert the function block before a stable anchor.
    insert_anchor = next(
        (
            a
            for a in (
                "def audit_tutorials_layout(",
                "def audit_module_mirror(",
                "def audit_directory_depth(",
                "def main(",
            )
            if a in text
        ),
        None,
    )
    if insert_anchor is None:
        return text, ["no insertion anchor"]
    text = text.replace(insert_anchor, _rendered(at_eof=False) + insert_anchor, 1)
    notes.append("inserted the shadowed-test block")

    # 2. wire it into main() ahead of the TERMINAL strict check. Not
    #    `str.replace(..., 1)`: that targets the FIRST tuple, and the first is
    #    not reliably the last.
    anchor = "    if args.strict and ("
    if anchor not in text:
        return text, notes + ["no strict-check anchor -- block inserted but NOT wired"]
    at = text.rindex(anchor)
    text = text[:at] + WIRE_INSERT + text[at:]
    notes.append("wired into main()")

    # 3. extend the strict-check tuple -- the TERMINAL one, through the same
    #    helper the resync path uses, so a fresh install and a resync wire
    #    identically.
    text, wired = _ensure_strict_wired(text)
    if wired:
        notes.append(wired)
    text, swept = _sweep_superseded(text)
    notes += swept
    return _finish(text, original), notes


def _refusal(original: str, patched: str) -> str | None:
    """Why this patch must not be written, or None if it is safe.

    Four ways a sync can quietly wreck a housekeeper, all of which have
    happened to one injector or another in this suite:
    it stops parsing; it loses a definition it does not own; it leaves two
    definitions of one name so the second silently shadows the first; or it
    removes a constant something still reads.
    """
    try:
        ast.parse(patched)
    except SyntaxError as exc:
        return f"patched file would not parse -- {exc}"

    before, after = _module_functions(original), _module_functions(patched)
    lost = sorted(set(before) - set(after))
    if lost:
        return f"patch would delete top-level {lost}"

    dupes = sorted({n for n in after if after.count(n) > 1})
    if dupes:
        return f"patch would leave duplicate top-level {dupes}"

    stranded = sorted(
        n
        for n in _SUPERSEDED_NAMES
        if _name_loads(patched, n) and not _name_bound(patched, n)
    )
    if stranded:
        return f"patch would strand references to {stranded}"
    return None


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

    # A block that does not parse would be written into twenty-nine files
    # before anything noticed. Check once, here, before touching any of them.
    try:
        ast.parse(FUNC_BLOCK)
    except SyntaxError as exc:
        print(f"  [ABORT] shadowed_tests_block.py does not parse: {exc}")
        return 1

    failed = 0
    for lib in args.only or discover_libs(root):
        hk = root / lib / "housekeeper.py"
        if not hk.is_file():
            print(f"  [skip ] {lib}: no housekeeper.py")
            continue
        text = hk.read_text(encoding="utf-8")
        new_text, notes = patch_hk(text)
        refusal = _refusal(text, new_text)
        if refusal:
            print(f"  [REFUSED] {lib}: {refusal}")
            failed = 1
            continue
        if new_text == text:
            print(f"  [ok   ] {lib}: {'; '.join(notes)}")
            continue
        print(f"  [{'apply' if args.apply else 'dry  '}] {lib}: {'; '.join(notes)}")
        if args.apply:
            hk.write_text(new_text, encoding="utf-8")
    return failed


if __name__ == "__main__":
    sys.exit(main())
