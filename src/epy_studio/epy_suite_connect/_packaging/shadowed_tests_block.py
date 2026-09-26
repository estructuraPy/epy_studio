"""Canonical housekeeper block: no test may be shadowed by a later definition.

Python binds names in order and keeps the LAST one. A module that defines
``class TestFoo`` twice discards the first class WHOLE -- every test inside it
stops being collected. pytest says nothing, because nothing is wrong from its
point of view: the file imports, the classes it finds run, the suite is green.
The tests are simply not there any more.

This is the same species of defect as a skipped test nobody declared, and it
is harder to see: a skip at least leaves an ``s`` in the output. A shadowed
class leaves the total slightly lower than it should be, and nobody knows what
it should be.

Measured on 2026-08-22 across the suite: 3023 test files, and **29 tests in
five repos** were being discarded this way -- six in epy_buildings, nine in
epy_concrete, six each in epy_tall and epy_tanks, two in epy_houses. All 29
passed once woken, so they were correct the whole time and simply were not
executed. The one in epy_buildings surfaced only because an unrelated edit
changed the suite total by four more than the tests it had removed; the
arithmetic caught it, not the run.

The rule covers module-level classes and module-level test functions. A method
redefined inside one class is the same bug at a smaller scale, and is caught
too. Names bound in different classes do not collide and are not reported.
"""

SHADOWED_TESTS_BLOCK = '''
def _shadowed_definitions_in_source(path: Path, source: str) -> list[str]:
    """Return every test definition discarded by a later one of the same name.

    Walks the module body (and each class body) rather than reading lines: a
    duplicate is a fact about the AST, and a name appearing twice in a
    docstring or a string literal is not one.

    Only definitions that actually CONTAIN tests are reported. A duplicated
    helper class with no ``test_`` methods costs nothing at collection time
    and is a style question, not a lost test.
    """
    import ast as _ast
    import collections as _collections

    try:
        tree = _ast.parse(source)
    except SyntaxError as exc:
        return [f"{path}:{exc.lineno or 0}: cannot parse ({exc.msg})"]

    found: list[str] = []

    def _tests_in(node) -> list[str]:
        return [
            child.name
            for child in node.body
            if isinstance(child, (_ast.FunctionDef, _ast.AsyncFunctionDef))
            and child.name.startswith("test_")
        ]

    def _scan(body, scope: str) -> None:
        seen = _collections.defaultdict(list)
        for node in body:
            if isinstance(node, (_ast.ClassDef, _ast.FunctionDef, _ast.AsyncFunctionDef)):
                seen[node.name].append(node)
        for name, defs in seen.items():
            if len(defs) < 2:
                continue
            survivor = defs[-1]
            for shadowed in defs[:-1]:
                if isinstance(shadowed, _ast.ClassDef):
                    lost = _tests_in(shadowed)
                    kind = "class"
                elif shadowed.name.startswith("test_"):
                    lost = [shadowed.name]
                    kind = "test"
                else:
                    continue
                if not lost:
                    continue
                where = f"{scope}{name}" if scope else name
                found.append(
                    f"{path}:{shadowed.lineno}: {kind} {where} is redefined at "
                    f"line {survivor.lineno}; {len(lost)} test(s) never run "
                    f"({', '.join(lost[:4])}{'...' if len(lost) > 4 else ''})"
                )

    _scan(tree.body, "")
    for node in tree.body:
        if isinstance(node, _ast.ClassDef):
            _scan(node.body, f"{node.name}.")
    return found


def audit_no_shadowed_tests(lib_root: Path) -> list[str]:
    """Scan tests/ for definitions discarded by a later one of the same name.

    Python keeps the last binding, so an earlier ``class TestFoo`` is thrown
    away whole and every test in it stops being collected. Nothing reports
    this: the module imports, the surviving class runs, the suite is green.

    Fix by renaming, never by deleting the earlier definition unexamined --
    every one of the 29 found suite-wide on 2026-08-22 PASSED once woken, so
    deleting them would have thrown away working coverage to silence a gate.
    """
    tests_dir = lib_root / "tests"
    if not tests_dir.is_dir():
        return []
    violations: list[str] = []
    for path in sorted(tests_dir.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        try:
            source = path.read_text(encoding="utf-8")
        except OSError as exc:
            violations.append(f"{path}: unreadable ({exc})")
            continue
        violations.extend(
            _shadowed_definitions_in_source(path.relative_to(lib_root), source)
        )
    return violations


def report_shadowed_tests(violations: list[str]) -> None:
    """Print the shadowed-test result.

    Keep the substrings ``Shadowed tests: OK`` and ``SHADOWED-TEST
    VIOLATIONS`` intact when rewording: housekeeper tests assert on them.
    """
    if not violations:
        print("\\n  Shadowed tests: OK (none)")
        return
    print(f"\\n  SHADOWED-TEST VIOLATIONS ({len(violations)} total):")
    for v in violations[:30]:
        print(f"    [!] {v}")
    if len(violations) > 30:
        print(f"    ... and {len(violations) - 30} more")
'''
