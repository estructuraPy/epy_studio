"""Sync the CORE-ONLY placement rule (structural audit 2c) into every housekeeper.

Why this exists
---------------
``ALLOWED_CORE_LOOSE_FILES`` only ever PERMITTED ``_initialization.py`` and
``_optimization.py`` at ``src/<pkg>/_core/`` root. It never FORBADE them
anywhere else. A permission is not a rule, and the suite paid for the
difference: on 2026-07-28 a single "reorganize loose files" sweep moved both
modules into ``_design/`` in FIVE libraries -- timber ``d65e59b``, steel
``f616068``, buildings ``627fea0``, connections ``082ba9b``, concrete
``31d60949`` -- and every housekeeper stayed green, including timber's, which
had been the reference layout for exactly this DNA (``da74fc6``).

Rule 2b already states the mirror image of this for resistance kernels
(``CANONICAL_STRENGTH_MODULES`` must live in ``_core/_strength/`` and nowhere
else). 2c is the same shape applied to the cross-cutting loose modules, and it
is derived from ``ALLOWED_CORE_LOOSE_FILES`` by ALIAS rather than by a second
literal, so a permitted-here list and a required-here list can never drift into
disagreeing with each other.

Strategy
--------
Both edits are anchored by AST source spans, never by regex over the text:

1. the constant goes immediately after the ``ALLOWED_CORE_LOOSE_FILES``
   assignment's ``end_lineno``;
2. the check goes immediately after the ``end_lineno`` of the ``for`` statement
   inside ``audit_structure`` whose iterator is ``CANONICAL_STRENGTH_MODULES``
   -- i.e. the end of block 2b, so 2c lands as its sibling.

A housekeeper missing either anchor is REPORTED AND SKIPPED, never guessed at.
Six repos are in that state on purpose (analysis, blender, plotter, simulation
carry a different family layout; geotechnical and tall are material libraries
whose housekeepers were never given the family constants at all -- that is a
real gap and it is listed in the output rather than silently patched, because
bringing them up to family standard is a content decision, not a sync).

Refusals, in the spirit of the injector defects this suite has already paid for
(one injector deleted foreign functions; another reported "already canonical"
after inspecting only the function and not the rule):

* the patched source must still parse;
* it must not lose a single top-level definition;
* "already present" requires BOTH the constant AND a loop that iterates it --
  finding one without the other is a half-application and gets repaired.

Usage::

    python add_hk_core_only_modules_xsuite.py            # dry-run every repo
    python add_hk_core_only_modules_xsuite.py --apply

Author: Ing. Angel Navarro-Mora M.Sc.
"""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

#: Repo root, derived from this file's own location -- never a hardcoded
#: absolute path (a shipped launcher in this suite already had to be rebuilt
#: once for exactly that reason).
ROOT = Path(__file__).resolve().parents[2]

CONST_NAME = "CORE_ONLY_LOOSE_MODULES"
ANCHOR_CONST = "ALLOWED_CORE_LOOSE_FILES"
ANCHOR_LOOP_ITER = "CANONICAL_STRENGTH_MODULES"

CONST_BLOCK = '''
# The mirror of ALLOWED_CORE_LOOSE_FILES: the same modules, stated as a
# REQUIREMENT instead of a permission. Aliased rather than re-declared so a
# "permitted here" list and a "required here" list can never drift apart --
# which is the failure mode that let five libraries move both modules into
# _design/ on 2026-07-28 with every gate still reporting green.
CORE_ONLY_LOOSE_MODULES = ALLOWED_CORE_LOOSE_FILES
'''

CHECK_BLOCK = '''
    # 2c. Mirror of 2b for the cross-cutting loose modules: they live at _core/
    #     root and NOWHERE else -- never in _design/, which holds orchestrators
    #     only. Permitting them in _core/ was never enough; nothing forbade them
    #     elsewhere, so a single "reorganize loose files" sweep relocated them in
    #     five libraries and no gate objected. A placement rule has to bite from
    #     both sides or it is not a rule.
    core_root = pkg / "_core"
    for mod in CORE_ONLY_LOOSE_MODULES:
        for hit in pkg.rglob(mod):
            if "__pycache__" in hit.parts:
                continue
            if hit.parent != core_root:
                rel = hit.relative_to(pkg).as_posix()
                where = hit.parent.relative_to(pkg).as_posix()
                violations.append(
                    f"cross-cutting module src/{pkg.name}/{rel} must live at _core/ "
                    f"root (suite-wide layout DNA), not {where}/."
                )
'''


def discover(root: Path) -> list[Path]:
    """Housekeepers, found by glob. A hardcoded list in an earlier injector
    skipped ``ePy_plotter`` for a year over one capital letter."""
    return sorted(root.glob("*/housekeeper.py"), key=lambda p: p.parent.name.lower())


def _top_level_names(tree: ast.Module) -> set[str]:
    out: set[str] = set()
    for n in tree.body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out.add(n.name)
        elif isinstance(n, ast.Assign):
            for t in n.targets:
                if isinstance(t, ast.Name):
                    out.add(t.id)
    return out


def _has_rule(tree: ast.Module) -> tuple[bool, bool]:
    """(constant present, a loop iterating it present)."""
    const = CONST_NAME in _top_level_names(tree)
    loop = any(
        isinstance(n, ast.For) and isinstance(n.iter, ast.Name) and n.iter.id == CONST_NAME
        for n in ast.walk(tree)
    )
    return const, loop


def patch(src: str) -> tuple[str | None, str]:
    """Return (patched source or None, human-readable status)."""
    tree = ast.parse(src)
    fn = next(
        (n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "audit_structure"),
        None,
    )
    if fn is None:
        return None, "SKIP no audit_structure"

    const_node = next(
        (
            n
            for n in tree.body
            if isinstance(n, ast.Assign)
            and isinstance(n.targets[0], ast.Name)
            and n.targets[0].id == ANCHOR_CONST
        ),
        None,
    )
    loop_node = None
    for n in ast.walk(fn):
        if isinstance(n, ast.For) and isinstance(n.iter, ast.Name) and n.iter.id == ANCHOR_LOOP_ITER:
            loop_node = n
    if const_node is None or loop_node is None:
        missing = []
        if const_node is None:
            missing.append(ANCHOR_CONST)
        if loop_node is None:
            missing.append(f"block 2b (for ... in {ANCHOR_LOOP_ITER})")
        return None, "SKIP family anchors absent: " + " + ".join(missing)

    have_const, have_loop = _has_rule(tree)
    if have_const and have_loop:
        return None, "already canonical (constant AND rule both present)"
    if have_const != have_loop:
        half = "constant without rule" if have_const else "rule without constant"
        return None, f"REFUSE half-applied ({half}) -- repair by hand, not by sync"

    lines = src.splitlines(keepends=True)
    # Insert the deeper anchor first so the shallower line number stays valid.
    out = lines[: loop_node.end_lineno] + [CHECK_BLOCK] + lines[loop_node.end_lineno :]
    out = out[: const_node.end_lineno] + [CONST_BLOCK] + out[const_node.end_lineno :]
    new = "".join(out)

    try:
        new_tree = ast.parse(new)
    except SyntaxError as e:
        return None, f"REFUSE patched source does not parse: {e}"
    lost = _top_level_names(tree) - _top_level_names(new_tree)
    if lost:
        return None, f"REFUSE patch loses top-level names: {sorted(lost)}"
    has_c, has_l = _has_rule(new_tree)
    if not (has_c and has_l):
        return None, "REFUSE patch did not install both halves"
    return new, "PATCHED"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true", help="write the patched housekeepers")
    ap.add_argument(
        "--skip",
        nargs="*",
        default=[],
        metavar="REPO",
        help=(
            "repo directories to leave alone. Installing 2c turns an existing "
            "violation into a red gate, so a repo another thread is mid-edit on "
            "gets skipped by NAME and reported, rather than handed a failure it "
            "did not cause and cannot explain."
        ),
    )
    args = ap.parse_args()

    patched = skipped = refused = done = 0
    for hk in discover(ROOT):
        if hk.parent.name in args.skip:
            skipped += 1
            print(f"{hk.parent.name:<18} SKIP by request (claimed by another thread)")
            continue
        src = hk.read_text(encoding="utf-8")
        new, status = patch(src)
        name = hk.parent.name
        if new is None:
            if status.startswith("REFUSE"):
                refused += 1
            elif status.startswith("SKIP"):
                skipped += 1
            else:
                done += 1
            print(f"{name:<18} {status}")
            continue
        patched += 1
        print(f"{name:<18} {status}{'' if args.apply else ' (dry-run)'}")
        if args.apply:
            # Byte-level write: several .py files in this suite carry CRLF and a
            # text-mode round-trip silently rewrites every line ending.
            hk.write_bytes(new.encode("utf-8"))

    print(
        f"\n{patched} patched, {done} already canonical, {skipped} skipped "
        f"(no family anchors), {refused} REFUSED"
    )
    return 1 if refused else 0


if __name__ == "__main__":
    sys.exit(main())
