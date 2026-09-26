"""The ONE canonical Rule 8 block, and the only place it is edited.

Rule 8: a test that cannot run is fixed or deleted. It is never skipped.
``pytest.skip``, ``pytest.importorskip``, ``@pytest.mark.skip``,
``@pytest.mark.skipif`` and ``@pytest.mark.xfail`` are forbidden in committed
tests, and the gate below is what makes ``housekeeper.py --strict`` refuse a
repo that carries one.

WHY THIS FILE EXISTS
--------------------
The rule was never the problem. Measured by AST across all twenty-nine repos
on 2026-08-21:

* the 17 repos whose housekeeper carries ``audit_no_skipped_tests`` hold
  **0** violations between them;
* the 12 that do not hold **119**.

Seventeen enforce it and every one of them is at zero. The rule works; it was
simply never deployed to the rest. There was no canonical source to deploy
FROM -- the gate existed only as hand-copies -- so this file becomes that
source and ``add_hk_rule8_xsuite.py`` becomes the way it travels.

THE DIVERGENCE THE HAND-COPIES HAD ALREADY ACCUMULATED
------------------------------------------------------
Measured the same day, the 17 copies were not one gate but three:

* **6 repos** (epy_analysis, epy_compose, epy_concrete, epy_masonry,
  epy_steel, epy_timber) carried the AST walk, byte-identical.
* **11 repos** (epy_blender, epy_bridges, epy_buildings, epy_connections,
  epy_geotechnical, epy_houses, epy_simulation, epy_structure, epy_tall,
  epy_tanks, epy_towers) still carried the superseded per-LINE
  ``_PYTEST_SKIP_RE`` -- blind to the assigned form
  ``NAME = pytest.mark.skipif(...)``, tripped by prose, and therefore forced
  to exempt ``test_housekeeper.py`` WHOLESALE by filename. Their two
  sub-variants of the audit differ only in where the message wraps; the regex
  itself is byte-identical in all eleven.
* ``report_skipped_tests`` was the one function all 17 agreed on, to the byte.

All 17 do reach the terminal ``if args.strict and (...)`` tuple, so where the
gate exists it does fail the run. The gap here was never wiring; it was reach.

WHAT THIS BLOCK CHANGES AGAINST THE 6-REPO AST COPY
----------------------------------------------------
1. **No module-level state.** ``_SKIP_CALLS`` / ``_SKIP_MARKS`` become locals
   and ``ast`` is imported inside the function. Nine of the twenty-nine
   housekeepers carry no top-level ``import ast``; a block that needed one
   would be a block that could not be dropped in. It also means the sync owns
   its whole footprint: three function definitions, nothing else.
2. **A file that does not parse is a violation, not a silent ``[]``.** The
   previous ``except SyntaxError: return []`` made an uncollectable test
   module indistinguishable from a clean one -- the same outcome Rule 8
   forbids, reached by a different route. Measured across all twenty-nine
   repos, zero test files currently fail to parse, so this reddens nothing
   today and closes the hole for tomorrow. An unreadable file is reported the
   same way, instead of being dropped by ``except OSError: continue``.
3. **``xfail`` is detected.** Rule 8 bans it and neither the regex nor the AST
   copy looked for it. Measured across the suite, the only ``xfail`` marks are
   two in ``epy_project``, a repo that is red on Rule 8 regardless -- so
   closing this hole reddens nothing that was green.
4. **A count in the report header**, and a cap at 30 with an overflow line,
   matching every other reporter in the housekeeper. Both substrings the
   suite's own tests assert on -- ``Skipped tests: OK`` and
   ``SKIPPED-TEST VIOLATIONS`` -- are preserved verbatim.

WHAT DEPLOYING THIS BLOCK COSTS
-------------------------------
Two repos that report green today do so falsely, and this block says so:

* ``epy_structure/tests/_design/test_sheet_set.py:458`` binds
  ``_case_kepy_present = pytest.mark.skipif(...)``. That is the ASSIGNED form.
  Its per-line regex demands a leading ``@``, so the repo has been reporting
  ``Skipped tests: OK (none)`` while carrying one.
* ``epy_aluminum/tests/_core/test_scoreboard.py:21`` sets
  ``pytestmark = pytest.mark.skip(...)``, silencing the whole module. That
  repo has no gate at all.

Neither is a regression introduced here. Both are debt the previous gate could
not see, which is the entire argument for replacing it.

THE LESSON THE DOCSTRINGS CARRY, AND WHY IT STAYS VERBATIM
-----------------------------------------------------------
The by-name exemption of ``test_housekeeper.py`` was justified as "it must
mention these regex patterns to test them". The patterns it mentions live in
STRINGS, which an AST walk never visits -- so the justification was void the
moment the walk replaced the regex. What the exemption was actually doing by
then was hiding a plain, unconditional ``@pytest.mark.skip`` that the very
same file also carried. **The audit could not see its own debt.**

There is no by-name exemption in this block, and there must never be one
again. That sentence lives inside ``audit_no_skipped_tests``' own docstring,
in every repo, on purpose.

EDITING THIS BLOCK
------------------
``RULE8_SKIP_BLOCK`` is a RAW triple-single-quoted literal holding real,
readable Python -- not a hand-escaped one-liner. Edit it in place, then run
``add_hk_rule8_xsuite.py`` (dry) to confirm it still parses: the injector
calls ``ast.parse`` on the block before it will write a single file.
"""

from __future__ import annotations

#: Injected verbatim into each housekeeper. It stays a string because the
#: housekeepers are standalone scripts with no dependency on this package --
#: they are SYNCED, not imported. The only name the block needs from its host
#: is ``Path``, which all twenty-nine already import.
RULE8_SKIP_BLOCK = r'''def _skip_violations_in_source(text: str) -> list[tuple[int, str]]:
    """Every live pytest skip in one module, found by AST rather than by line.

    Catches four shapes:

    * ``@pytest.mark.skip`` / ``@pytest.mark.skipif`` / ``@pytest.mark.xfail``
      as a decorator, bare or called;
    * ``pytest.skip(...)``, ``pytest.importorskip(...)`` and
      ``pytest.xfail(...)`` as calls, at any depth -- including inside an
      ``except`` handler, which turns a real error into a green skip;
    * ``NAME = pytest.mark.skipif(...)``, the ASSIGNED form the per-line regex
      could not see because it has no leading ``@``;
    * ``pytestmark = pytest.mark.skip...``, which silences a whole module.

    ``xfail`` is in scope because Rule 8 puts it there. A non-strict xfail
    stops reporting the moment the code starts working, and a strict one is
    still a committed test whose result the suite has agreed not to act on.
    The per-line regex it replaces named only skip/skipif/importorskip, so it
    could not have seen either.

    WHY AN AST WALK AND NOT A REGEX
    -------------------------------
    Eleven housekeepers in this suite still matched these four alternatives
    per LINE, and that regex was blind in both directions.

    It MISSED the assigned form, ``NAME = pytest.mark.skipif(...)``, because
    its first alternative demands a leading ``@``. Three such marks gated 54
    tests across this suite, and one repo reported a clean 0 while 23 of one
    file's 55 tests were silenced by one of them.

    And it MATCHED prose. Any docstring or comment naming
    ``pytest.importorskip`` while explaining why it must not be used counted
    as a violation -- which is precisely why the one file documenting these
    patterns had to be exempted WHOLESALE by filename. See
    ``audit_no_skipped_tests`` for what that exemption cost.

    Walking the AST removes both blind spots at once: comments and strings are
    not nodes, and an assignment is.

    SYNCED from _packaging/_tooling/rule8_skip_block.py -- edit it THERE and
    re-run add_hk_rule8_xsuite.py --apply. A local edit here is overwritten by
    the next sync.
    """
    import ast as _ast

    # Imported locally, not at module level: nine housekeepers in this suite
    # carry no top-level ``import ast``, and the block has to drop into all
    # twenty-nine unchanged. The two tuples are local for the same reason --
    # the block owns no module-level state, so nothing it needs can be left
    # stranded behind a sync or shadowed by a repo-local edit.
    skip_calls = ("skip", "importorskip", "xfail")
    skip_marks = ("skip", "skipif", "xfail")

    try:
        tree = _ast.parse(text)
    except SyntaxError as exc:
        # NOT a silent []. A test module that does not parse cannot be
        # collected, so pytest never runs it -- the same outcome this rule
        # forbids, reached by a different route. Returning no violations here
        # would make an unparseable file indistinguishable from a clean one,
        # which is the exact shape of failure the rule exists to catch.
        line = getattr(exc, "lineno", None) or 1
        return [(line, f"module does not parse, so it never runs -- {exc.msg}")]

    # WHICH NAMES MEAN PYTEST HERE. Matching the literal string "pytest" let
    # six shapes through, each verified to skip a real test while the gate
    # reported zero: `import pytest as pt` then `pt.skip(...)`, and
    # `from pytest import skip` then a bare `skip(...)`. The module is read
    # for its own import statements instead.
    pytest_aliases = {"pytest"}
    unittest_aliases = {"unittest"}
    bare_skip_names: set = set()
    bare_mark_root: set = set()
    for node in _ast.walk(tree):
        if isinstance(node, _ast.Import):
            for a in node.names:
                if a.name == "pytest":
                    pytest_aliases.add(a.asname or "pytest")
                elif a.name == "unittest":
                    unittest_aliases.add(a.asname or "unittest")
        elif isinstance(node, _ast.ImportFrom):
            if node.module == "pytest":
                for a in node.names:
                    local = a.asname or a.name
                    if a.name in skip_calls:
                        bare_skip_names.add(local)
                    elif a.name == "mark":
                        bare_mark_root.add(local)
            elif node.module == "unittest":
                for a in node.names:
                    if a.name in ("skip", "skipIf", "skipUnless", "expectedFailure"):
                        bare_skip_names.add(a.asname or a.name)

    def _dotted(node: object) -> str:
        parts: list[str] = []
        while isinstance(node, _ast.Attribute):
            parts.append(node.attr)
            node = node.value
        if isinstance(node, _ast.Name):
            parts.append(node.id)
        return ".".join(reversed(parts))

    def _skip_mark(node: object) -> str:
        """The bare mark name if `node` is a forbidden mark, else empty."""
        target = node.func if isinstance(node, _ast.Call) else node
        parts = _dotted(target).split(".")
        if len(parts) >= 3 and parts[0] in pytest_aliases and parts[1] == "mark":
            bare = parts[-1]
            return bare if bare in skip_marks else ""
        # `from pytest import mark` then `mark.skipif(...)`
        if len(parts) == 2 and parts[0] in bare_mark_root:
            return parts[-1] if parts[-1] in skip_marks else ""
        # unittest decorators silence a test just as completely
        if len(parts) == 2 and parts[0] in unittest_aliases and parts[-1] in (
            "skip", "skipIf", "skipUnless", "expectedFailure"
        ):
            return parts[-1]
        if len(parts) == 1 and parts[0] in bare_skip_names:
            return parts[0]
        return ""

    def _marks_anywhere(node: _ast.AST) -> list[str]:
        """Forbidden marks anywhere inside an expression.

        The assigned form was matched only at the top of the value, so
        `pytestmark = [pytest.mark.skipif(...)]` -- pytest's own documented
        multi-mark idiom -- and a ternary around the same mark both read as
        clean while skipping a real test.
        """
        out: list[str] = []
        for sub in _ast.walk(node):
            mark = _skip_mark(sub)
            if mark:
                out.append(mark)
        return out

    definitions = (_ast.FunctionDef, _ast.AsyncFunctionDef, _ast.ClassDef)
    found: set = set()
    for node in _ast.walk(tree):
        if isinstance(node, definitions):
            for dec in node.decorator_list:
                mark = _skip_mark(dec)
                if mark:
                    found.add((dec.lineno, f"@...{mark} on {node.name}"))
        elif isinstance(node, _ast.Call):
            # Exactly the module-level skip calls, not any dotted name ending
            # in one of them: `pytest.mark.skip(...)` is a Call too, and
            # matching it here reported every decorator twice.
            parts = _dotted(node.func).split(".")
            if len(parts) == 2 and parts[0] in pytest_aliases and parts[1] in skip_calls:
                found.add((node.lineno, f"{'.'.join(parts)}(...)"))
            elif len(parts) == 1 and parts[0] in bare_skip_names:
                found.add((node.lineno, f"{parts[0]}(...) imported from pytest"))
            elif len(parts) == 2 and parts[1] == "skipTest":
                # unittest's runtime skip, reached through self/cls
                found.add((node.lineno, f"{'.'.join(parts)}(...)"))
        elif isinstance(node, (_ast.Assign, _ast.AnnAssign)):
            value = node.value
            if value is None:
                continue
            marks = _marks_anywhere(value)
            if marks:
                targets = (
                    node.targets
                    if isinstance(node, _ast.Assign)
                    else [node.target]
                )
                name = next(
                    (t.id for t in targets if isinstance(t, _ast.Name)), "<assign>"
                )
                found.add((
                    node.lineno,
                    f"{name} = ...{marks[0]}... (assigned)",
                ))
    return sorted(found)


def audit_no_skipped_tests(lib_root: Path) -> list[str]:
    """Scan tests/ for forbidden skip markers (Rule 8). Returns violations.

    A test that cannot run is fixed or deleted. It is never skipped.
    ``pytest.skip``, ``pytest.importorskip``, ``pytest.xfail``,
    ``@pytest.mark.skip``, ``@pytest.mark.skipif`` and ``@pytest.mark.xfail``
    are all forbidden in committed tests, in decorator, call and ASSIGNED
    form.

    THERE IS NO BY-NAME EXEMPTION, AND THERE MUST NEVER BE ONE AGAIN.
    ``test_housekeeper.py`` used to be exempted entirely, on the grounds that
    it "must mention these regex patterns to test them" -- but the patterns it
    mentions live in STRINGS, which the AST walk never visits, while the plain
    ``@pytest.mark.skip`` that same file also carried was real and thereby
    invisible. The audit could not see its own debt. The exemption existed
    only to paper over the per-line regex's habit of matching prose; once the
    walk stopped reading prose, the exemption had nothing left to justify it
    and everything to hide.

    A guard against a missing import is not exempt either. Measured
    2026-08-21 across this suite, every one of the 18 modules named by a
    ``pytest.importorskip`` call was installed, and most were declared as
    REQUIRED dependencies of the very package whose tests guarded against
    them. A test guarding against the absence of a dependency the package
    cannot install without is dead weight that will one day silently disable
    itself instead of failing. Where an extra is genuinely optional, the test
    belongs behind that extra in the test matrix, not behind a runtime skip.

    SYNCED from _packaging/_tooling/rule8_skip_block.py -- edit it THERE and
    re-run add_hk_rule8_xsuite.py --apply. A local edit here is overwritten by
    the next sync.
    """
    tests_root = lib_root / "tests"
    if not tests_root.is_dir():
        return []
    violations: list[str] = []
    for py_file in sorted(tests_root.rglob("*.py")):
        if "__pycache__" in py_file.parts:
            continue
        rel = py_file.relative_to(lib_root)
        try:
            text = py_file.read_text(encoding="utf-8")
        except OSError as exc:
            # Unreadable is not clean. Say so rather than dropping the file.
            violations.append(
                f"{rel}: cannot be read, so it cannot be audited -- {exc}"
            )
            continue
        for line_no, what in _skip_violations_in_source(text):
            violations.append(
                f"{rel}:{line_no}: forbidden test skip ({what}) -- "
                f"either fix the test or delete it."
            )
    return violations


def report_skipped_tests(violations: list[str]) -> None:
    """Print the Rule 8 result.

    Two literals below are asserted on by housekeeper tests already shipping
    in this suite: ``Skipped tests: OK`` and ``SKIPPED-TEST VIOLATIONS``. Keep
    both substrings intact when rewording.
    """
    if not violations:
        print("\n  Skipped tests: OK (none)")
        return
    print(f"\n  SKIPPED-TEST VIOLATIONS ({len(violations)} total):")
    for v in violations[:30]:
        print(f"    [!] {v}")
    if len(violations) > 30:
        print(f"    ... and {len(violations) - 30} more")
'''
