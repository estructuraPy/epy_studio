"""Patch housekeeper.py of every lib to add Rule 13 (audit_epyson_canon).

SYNC, not add-once: a library that already carries the block gets it REPLACED
with the canonical one. Skipping is what let five copies drift apart -- the
injector could add but never reconcile, so no two of the five messages
matched and four of them differed in BEHAVIOUR (fail-open on a missing
package, an unstripped description length, a different truncation, the
**kwargs finding filed under the wrong rule).

Strategy
--------
1. Insert the two function blocks (`audit_epyson_canon` + `report_epyson_canon`)
   immediately before `def audit_directory_depth(`.
2. Inject `epyson_violations = audit_epyson_canon(LIB_ROOT)` + report call
   before the `if args.strict and (` block in `main()`.
3. Extend the strict-check tuple with `or epyson_violations`.

Usage:
  python add_hk_rule13_xsuite.py            # dry-run all 16 libs
  python add_hk_rule13_xsuite.py --apply
"""
from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path

ROOT = Path(r"C:\Users\ingah\estructuraPy")
LIBS = [
    # "epy_plotter" only worked via Windows case-insensitivity (the directory
    # is `ePy_plotter`; a case-sensitive runner would skip it) and "epy_suite"
    # named a retired repo; both fixed 2026-08-19 when blender/simulation
    # joined for their strict gates.
    "epy_aluminum", "epy_analysis", "epy_blender", "epy_bridges",
    "epy_buildings", "epy_compose", "epy_concrete", "epy_docs",
    "epy_connections", "epy_geotechnical", "epy_houses",
    "epy_masonry", "ePy_plotter", "epy_simulation", "epy_steel",
    "epy_structure", "epy_tall", "epy_tanks", "epy_timber", "epy_towers",
]

# The block lives in ONE place. Editing it here instead of there is how the
# copies drifted in the first place.
sys.path.insert(0, str(Path(__file__).parent))
from rule13_canon_block import RULE13_BLOCK as FUNC_BLOCK  # noqa: E402


WIRE_INSERT = (
    "    # .epyson canon audit (Rule 13)\n"
    "    epyson_violations = audit_epyson_canon(LIB_ROOT)\n"
    "    report_epyson_canon(epyson_violations)\n\n"
)


def _ensure_import_re(text: str) -> tuple[str, bool]:
    """The block compiles a semver regex, so the host needs `re`.

    Most housekeepers already import it, which is why the assumption went
    unnoticed until a slimmer one (aluminum) took the block and died on
    NameError at the first catalog it walked.
    """
    for line in text.splitlines():
        if line.strip() in ("import re", "import re  # noqa"):
            return text, False
    # Insert in sorted position: a plain "first import wins" placement puts
    # `import re` above `import argparse` and trips isort (I001), turning a
    # green lint gate red.
    plain = [
        ln for ln in text.splitlines()
        if ln.startswith("import ") and " as " not in ln and "," not in ln
    ]
    anchor = next((ln for ln in plain if ln > "import re"), None) or (
        plain[-1] if plain else None
    )
    if anchor is None:
        return text, False
    if anchor > "import re":
        return text.replace(anchor, "import re" + chr(10) + anchor, 1), True
    return text.replace(anchor, anchor + chr(10) + "import re", 1), True



#: Every top-level function the canonical block owns. The span below covers
#: the whole contiguous run of these names, so a re-sync REPLACES the helper
#: instead of stranding it above the window. The first rollout of the
#: helper-carrying block did exactly that: _canon_span started at
#: audit_epyson_canon, the replacement re-inserted the full block (helper
#: included), and the previous helper survived untouched above it -- one
#: duplicate copy per sync, in all sixteen repos.
_CANON_FUNCTIONS = frozenset(
    {"_declared_audit_statuses", "audit_epyson_canon", "report_epyson_canon"}
)


def _canon_span(text: str) -> tuple[int, int] | None:
    """Return the character span covering the canonical block's own functions.

    The span runs over the contiguous run of top-level definitions whose names
    the block owns (duplicates of the helper included, so a prior sync's
    stranded copy is swept up). Anything ELSE sitting inside that run belongs
    to somebody else, and the sync refuses rather than swallowing it.
    """
    tree = ast.parse(text)
    defs = [n for n in tree.body if isinstance(n, ast.FunctionDef)]
    owned = [i for i, n in enumerate(defs) if n.name in _CANON_FUNCTIONS]
    if not owned or "audit_epyson_canon" not in {defs[i].name for i in owned}:
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
    # end_lineno is inclusive and 1-based; the block is written with a trailing
    # blank-line separator, which the canonical text carries too.
    start = offsets[first.lineno - 1]
    end = offsets[last.end_lineno]
    while end < len(text) and text[end] == chr(10):
        end += 1
    return start, end


def _module_functions(text: str) -> set[str]:
    """Top-level function names, for the before/after check below."""
    return {
        n.name for n in ast.parse(text).body if isinstance(n, ast.FunctionDef)
    }


def patch_hk(text: str) -> tuple[str, list[str]]:
    notes = []
    text, added_re = _ensure_import_re(text)
    if added_re:
        notes.append("added missing `import re`")
    if "audit_epyson_canon" in text:
        # Replace exactly the two canon functions, bounded by their own source
        # spans. This used to run from `def audit_epyson_canon(` to the next
        # `def audit_directory_depth(` / `def main(`, on the assumption that
        # one of those "always follows them" -- which held when it was written
        # and stopped holding the moment another campaign inserted
        # audit_doc_standard_refs_strict in between. The sync then swallowed
        # that function whole, and every housekeeper it touched died on
        # NameError at the call main() still made.
        span = _canon_span(text)
        if span is None:
            return text, ["existing block present but its two functions are not adjacent"]
        start, end = span
        if text[start:end] == FUNC_BLOCK:
            return text, ["already canonical"]
        return text[:start] + FUNC_BLOCK + text[end:], ["resynced to canonical"]

    # 1. insert the function block before a stable anchor. audit_directory_depth
    # is the usual one, but the slimmer housekeepers (aluminum, docs, plotter)
    # never had it -- which is exactly why they never got Rule 13.
    insert_anchor = next(
        (a for a in ("def audit_directory_depth(", "def main(") if a in text),
        None,
    )
    if insert_anchor is None:
        return text, ["no insertion anchor (neither audit_directory_depth nor main)"]
    text = text.replace(
        insert_anchor,
        FUNC_BLOCK + insert_anchor,
        1,
    )
    notes.append("inserted audit_epyson_canon + report functions")

    # 2. insert wire-up before `if args.strict and (`
    if "if args.strict and (" not in text:
        return text, ["no strict-check anchor"]
    text = text.replace(
        "    if args.strict and (",
        WIRE_INSERT + "    if args.strict and (",
        1,
    )
    notes.append("wired into main()")

    # 3. extend strict tuple — find the closing `):` of strict block
    # patterns vary; we add `or epyson_violations` before the closing `):`
    m = re.search(r"if args\.strict and \([^)]*\):", text)
    if m:
        old = m.group(0)
        # insert before the last `)` of the tuple
        new = re.sub(r"\):", "\n        or epyson_violations\n    ):", old, count=1)
        text = text.replace(old, new, 1)
        notes.append("extended strict-check tuple")
    # The strict-tuple rewrite splits a line and leaves trailing whitespace
    # behind, which trips W293 and turns a green lint gate red. Normalise
    # what this script writes rather than leaving it for a human.
    text = re.sub(r"[ 	]+" + chr(10), chr(10), text)
    return text, notes


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument(
        "--only",
        nargs="+",
        help="restrict to these libs -- the suite routinely has campaigns "
             "mid-flight in other repos, and a sync must not land in a dirty tree",
    )
    args = ap.parse_args()

    for lib in (args.only or LIBS):
        hk = ROOT / lib / "housekeeper.py"
        if not hk.is_file():
            print(f"  [skip] {lib}: no housekeeper.py")
            continue
        text = hk.read_text(encoding="utf-8")
        new_text, notes = patch_hk(text)
        lost = _module_functions(text) - _module_functions(new_text)
        # Deduplication of the block's own helper is sanctioned; losing any
        # OTHER name is not.
        lost -= _CANON_FUNCTIONS & _module_functions(new_text)
        if lost:
            # The failure this exists for: a sync that deletes somebody else's
            # function leaves a housekeeper that still calls it, and the repo
            # only finds out at the next run.
            print(f"  [REFUSED] {lib}: patch would delete {sorted(lost)}")
            return 1
        if new_text == text:
            print(f"  [skip] {lib}: {'; '.join(notes)}")
            continue
        print(f"  [{'apply' if args.apply else 'dry'}] {lib}: {'; '.join(notes)}")
        if args.apply:
            hk.write_text(new_text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
