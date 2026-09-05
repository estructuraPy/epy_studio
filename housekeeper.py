#!/usr/bin/env python3
"""Minimal housekeeper — ePy Suite (auto-generated).

Usage:
    python housekeeper.py                # dry-run: report only
    python housekeeper.py --apply        # delete temp/cache
    python housekeeper.py --quality      # ruff + pyright + coverage report
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

# ── Root of THIS library ──────────────────────────────────────────────
LIB_ROOT = Path(__file__).resolve().parent

def _find_pkg_dir(lib_root: Path) -> Path | None:
    """Locate src/<pkg>/. Returns None if no src/ exists or no inner package found."""
    src = lib_root / "src"
    if not src.is_dir():
        return None
    for child in src.iterdir():
        if child.is_dir() and (child / "__init__.py").exists():
            return child
    return None


# ── Quality check (shared module) ─────────────────────────────────────
_QUALITY_CHECK_AVAILABLE = False
try:
    _repo_root = LIB_ROOT.parent
    _qc_path = _repo_root / "_packaging" / "quality_check.py"
    if _qc_path.is_file():
        import importlib.util
        _spec = importlib.util.spec_from_file_location("_quality_check", _qc_path)
        if _spec and _spec.loader:
            _mod = importlib.util.module_from_spec(_spec)
            _spec.loader.exec_module(_mod)
            _run_qc = _mod.run_quality_check
            _print_qr = _mod.print_report
            _QUALITY_CHECK_AVAILABLE = True
except Exception:
    pass

DIRS_TO_DELETE = {"__pycache__", ".pytest_cache", ".ruff_cache", ".mypy_cache"}
EXTENSIONS_TO_DELETE = {".pyc", ".pyo"}
PROTECTED = {"src", "tests", "docs", "pyproject.toml", "CLAUDE.md", "README.md",
             "LICENSE", ".gitignore", ".git", ".venv", "housekeeper.py"}


def collect_targets(root: Path) -> list[Path]:
    targets = []
    for path in root.rglob("*"):
        if any(part.startswith(".") and part in DIRS_TO_DELETE for part in path.parts):
            if path.is_dir() and path.name in DIRS_TO_DELETE:
                targets.append(path)
        elif path.suffix in EXTENSIONS_TO_DELETE:
            targets.append(path)
    return targets


def audit_tests_layout(lib_root: Path) -> list[str]:
    """Audit tests/ against the canonical mirror-of-src layout (STRUCTURE_STANDARD.md §2.4).

    Two independent constraints on the tests/ ROOT:

    * Files -- ONLY ``conftest.py`` and ``__init__.py`` may sit directly under
      tests/. Every other file (``test_*.py`` harness/facade suites,
      ``pytest.ini``, READMEs, ...) belongs inside the mirrored subpackage of
      the code it exercises (``tests/_core/``, ``tests/_design/``,
      ``tests/_analysis/`` ...), never at the root.
    * Directories -- allowed root dirs = {every top-level dir name actually
      present under ``src/<pkg>/``} UNION {"_benchmarks"}, derived DYNAMICALLY
      from src/ so the same rule works for every domain folder name
      (``_design`` vs ``_analysis`` vs ``_service`` ...) without hardcoding one.
      ``_benchmarks/`` is the single sanctioned non-mirror dir; ``_perf/`` is
      NOT sanctioned (desanctioned 2026-07-20).

    Returns a list of violation strings (empty = compliant).
    """
    pkg = _find_pkg_dir(lib_root)
    if pkg is None:
        return []
    tests_root = lib_root / "tests"
    if not tests_root.is_dir():
        return []

    allowed_files = {"conftest.py", "__init__.py"}
    allowed_dirs = {"_benchmarks"}
    for child in pkg.iterdir():
        if child.is_dir() and child.name != "__pycache__":
            allowed_dirs.add(child.name)

    violations: list[str] = []
    for child in sorted(tests_root.iterdir()):
        if child.name in {"__pycache__", ".pytest_cache"}:
            continue
        if child.is_file():
            if child.suffix in {".pyc", ".pyo"}:
                continue
            if child.name not in allowed_files:
                violations.append(
                    f"tests/{child.name} is a loose root file -- only conftest.py and "
                    f"__init__.py are allowed at tests/ root; move it into the matching "
                    f"tests/<mirror>/ subpackage (STRUCTURE_STANDARD.md §2.4)."
                )
            continue
        if child.is_dir() and child.name not in allowed_dirs:
            violations.append(
                f"tests/{child.name}/ has no matching src/{pkg.name}/{child.name}/ "
                f"and is not the sanctioned tests/_benchmarks/ exception -- forbidden "
                f"non-mirror folder (STRUCTURE_STANDARD.md §2.4)."
            )
    return violations


def report_tests_layout(violations: list[str]) -> None:
    if not violations:
        print("\n  Tests layout: OK (mirrors src/<pkg>/ + sanctioned _benchmarks/ exception)")
        return
    print(f"\n  TESTS-LAYOUT VIOLATIONS ({len(violations)} total):")
    for v in violations:
        print(f"    [!] {v}")


def _is_mirror_exempt(rel: str) -> bool:
    """Whether ``rel`` is not a unit-test target.

    Integration / packaging / schema / showcase modules are exempt.

    SYNCED from _packaging/_tooling/module_mirror_block.py -- edit it THERE
    and re-run add_hk_module_mirror_xsuite.py --apply. A local edit here is
    overwritten by the next sync.
    """
    name = rel.rsplit("/", 1)[-1]
    # No blanket exemption for ``epy_suite_connect/``, and none for
    # adapters: measured across the suite, 96 of the 110 adapter modules
    # already ship a mirroring test, so "integration code is not a
    # unit-test target" is not the convention here -- it was a licence for
    # the gate to go blind on whole packages. The clause that used to sit
    # here exempted ``adapters/`` -- and both spellings of it. The
    # canonical one is ``_adapters/``; the census belongs in
    # STRUCTURE_STANDARD.md 2.6, not in this comment, which said six and
    # five when the disk said fifteen and five. What the clause hid was
    # the one adapter nobody tests: ``_export_estrulab.py``,
    # byte-identical in seven repos.
    if "/_packaging/" in rel or name in (
        "download_wheels.py",
        "install_offline.py",
        "__main__.py",
    ):
        return True
    if "_schemas/" in rel:
        return True
    return name in ("_famous.py", "_demo.py", "_showcase.py")


def _mirror_import_roots(src: Path) -> set[str]:
    """Top-level import roots this repo ships under ``src/``.

    Every directory directly under ``src/`` is a root, with or without an
    ``__init__.py``: PEP 420 namespace packages are importable too, and a
    root filter that demanded ``__init__.py`` would simply stop checking
    whatever lives in one.
    """
    if not src.is_dir():
        return set()
    return {
        c.name
        for c in src.iterdir()
        if c.is_dir() and c.name != "__pycache__"
    }


def _mirror_module_exists(src: Path, dotted: str) -> bool:
    """Whether ``dotted`` resolves to a real module or package under src/.

    PEP 420 aware ON PURPOSE. A directory WITHOUT ``__init__.py`` is a
    legitimate namespace package and imports fine; an earlier probe that
    required ``__init__.py`` reported 20 false positives on exactly those
    directories. The three accepted shapes are therefore ``<path>.py``,
    ``<path>/__init__.py``, and a bare ``<path>/`` directory.
    """
    target = src.joinpath(*dotted.split("."))
    if target.with_suffix(".py").is_file():
        return True
    return target.is_dir()


def _mirror_dead_imports(
    test_path: Path, src: Path, roots: set[str]
) -> list[str]:
    """Dotted imports in ``test_path`` naming no module under ``src/``.

    THE REASON THIS RULE EXISTS. The mirror gate used to be pure PRESENCE:
    it collected the NAME of every ``tests/**/test_*.py`` into a flat set
    and never opened the file. The file
    ``epy_buildings/tests/_core/test_optimization.py`` imported
    ``epy_buildings._core._optimization``, which does not exist -- the
    module is at ``_design/_optimization.py``. Every pytest collection of
    that repo raised ModuleNotFoundError from 2026-07-23 to 2026-08-20,
    and this gate counted the broken file as coverage the whole time.

    Only imports rooted in a package this repo ships are checked; a sibling
    library's module is not on this repo's disk and is none of this gate's
    business. Relative imports are skipped -- resolving them needs the
    test's own package identity, which the flat-name convention that this
    gate is built on does not pin down.
    """
    import ast as _ast

    try:
        source = test_path.read_text(encoding="utf-8", errors="replace")
        tree = _ast.parse(source)
    except SyntaxError as e:
        return [f"does not parse, so its imports cannot be verified - {e}"]

    dead: list[str] = []
    seen: set[str] = set()
    for node in _ast.walk(tree):
        dotted_names: list[str] = []
        if isinstance(node, _ast.Import):
            dotted_names = [a.name for a in node.names]
        elif isinstance(node, _ast.ImportFrom):
            if node.level or not node.module:
                continue
            dotted_names = [node.module]
        for dotted in dotted_names:
            if dotted in seen or dotted.split(".")[0] not in roots:
                continue
            seen.add(dotted)
            if not _mirror_module_exists(src, dotted):
                dead.append(f"imports `{dotted}`, which does not exist")
    return dead


_MIRROR_ADVISORY: list[str] = []
"""Where the path-parity advisory waits between audit and report."""


def _mirror_advisory(store: list[str] | None = None) -> list[str]:
    """Carry the path-parity advisory from the audit to the report.

    ``report_module_mirror(violations)`` is called with exactly one
    argument in all twenty-nine housekeepers; widening that signature would
    make this sync rewrite twenty-nine call sites in ``main()`` as well. A
    tiny accessor keeps the wiring untouched and keeps the advisory out of
    the ``--strict`` failure tuple, which is the point: path parity is a
    WARNING, never a failure.
    """
    if store is not None:
        _MIRROR_ADVISORY[:] = store
    return list(_MIRROR_ADVISORY)


def audit_module_mirror(lib_root: Path) -> list[str]:
    """Every real src module needs a mirroring test whose imports RESOLVE.

    Two checks, both failures:

    1. PRESENCE -- a ``test_<stem>.py`` or ``test_<stem>_*.py`` exists
       somewhere under ``tests/``. Closes the gap left by the folder-level
       tests-layout audit, which reports OK even when a module has no test.
    2. IMPORTABILITY -- every crediting test parses, and every dotted
       import it makes into a package this repo ships resolves to a real
       module or package on disk. A test that cannot be imported is not
       coverage, and for a month one of them was counted as coverage.

    Path parity -- does the test sit at the MIRRORED path? -- is
    deliberately NOT a failure. Measured 2026-08-21 across the suite: 359
    mirrors, 26% of them, live at a non-mirrored path, and the bulk of
    those follow two conventions the suite chose on purpose. It is
    reported as an advisory instead; see ``report_module_mirror``.

    SYNCED from _packaging/_tooling/module_mirror_block.py -- edit it THERE
    and re-run add_hk_module_mirror_xsuite.py --apply. A local edit here is
    overwritten by the next sync.
    """
    pkg = _find_pkg_dir(lib_root)
    if pkg is None:
        return [
            f"src/<pkg>/ not found under {lib_root} -- cannot audit "
            f"module mirror."
        ]
    src = pkg.parent
    roots = _mirror_import_roots(src)

    tests = lib_root / "tests"
    # stem -> the test files carrying that stem. The old gate kept only the
    # NAMES, in a flat set, and threw the paths away -- which is why it
    # could neither open the file nor say where the mirror actually lived.
    by_name: dict[str, list[Path]] = {}
    if tests.is_dir():
        for p in tests.rglob("test_*.py"):
            if "__pycache__" not in p.parts:
                by_name.setdefault(p.name, []).append(p)

    violations: list[str] = []
    crediting: dict[Path, None] = {}
    off_mirror: list[tuple[str, str]] = []

    for m in sorted(pkg.rglob("*.py")):
        if "__pycache__" in m.parts or m.name == "__init__.py":
            continue
        rel = m.relative_to(pkg).as_posix()
        if _is_mirror_exempt(rel):
            continue
        bare = m.name[:-3].lstrip("_")
        if bare in ("utils", "types", "constants", "typing", "protocols"):
            continue
        mirrors = list(by_name.get(f"test_{bare}.py", []))
        for name, paths in by_name.items():
            if name.startswith(f"test_{bare}_") and name.endswith(".py"):
                mirrors.extend(paths)
        if not mirrors:
            violations.append(
                f"src module without mirroring test: "
                f"src/{pkg.name}/{rel} -- add tests/.../test_{bare}.py "
                f"(suite-wide tests-mirror DNA)."
            )
            continue
        for t in mirrors:
            crediting[t] = None
        # Path parity, advisory only. The mirrored home of
        # src/<pkg>/a/b/c.py is tests/a/b/test_c.py.
        want_dir = (tests / rel).parent
        if not any(t.parent == want_dir for t in mirrors):
            where = mirrors[0].relative_to(lib_root).parent.as_posix()
            off_mirror.append((rel, where))

    for t in sorted(crediting):
        where = t.relative_to(lib_root).as_posix()
        for problem in _mirror_dead_imports(t, src, roots):
            violations.append(
                f"mirroring test {where} {problem} -- it cannot be "
                f"collected, so it is not coverage; point it at the real "
                f"module or delete it."
            )

    # Two conventions the suite adopted deliberately. They are named here
    # so the advisory does NOT advise against them.
    flat_connect = sum(
        1 for rel, _ in off_mirror if "epy_suite_connect/" in rel
    )
    root_designer = sum(
        1
        for rel, _ in off_mirror
        if "/" not in rel and rel.endswith("_designer.py")
    )
    advisory: list[str] = []
    if off_mirror:
        residual = len(off_mirror) - flat_connect - root_designer
        advisory.append(
            f"{len(off_mirror)} mirroring test(s) sit at a non-mirrored "
            f"path ({flat_connect} flat epy_suite_connect, "
            f"{root_designer} root designer, {residual} other). Advisory "
            f"only -- the mirror is credited either way."
        )
        for rel, where in off_mirror[:8]:
            advisory.append(f"src/{pkg.name}/{rel} -> {where}/")
        if len(off_mirror) > 8:
            advisory.append(f"... and {len(off_mirror) - 8} more")
    _mirror_advisory(advisory)
    return violations


def report_module_mirror(violations: list[str]) -> None:
    """Print the module-mirror result, then the path-parity advisory.

    The advisory prints separately and never enters the ``--strict``
    failure tuple. The two conventions it names are SANCTIONED, and must
    not be "fixed":

    * the flat ``tests/epy_suite_connect/test_*.py`` layout mirroring
      ``epy_suite_connect/{adapters,_adapters,_contract}/*.py``;
    * root designer modules ``src/<pkg>/<x>_designer.py`` tested from
      ``tests/_design/``.
    """
    if not violations:
        print(
            "\n  Module mirror: OK (every real src module has a mirroring "
            "test, and every one of them imports)"
        )
    else:
        print(f"\n  MODULE-MIRROR VIOLATIONS ({len(violations)} total):")
        for v in violations:
            print(f"    - {v}")
    advisory = _mirror_advisory()
    if advisory:
        print(
            f"\n  Module mirror path parity (advisory, NOT a failure): "
            f"{advisory[0]}"
        )
        for line in advisory[1:]:
            print(f"    . {line}")


# ============================================================
#                    TUTORIALS LAYOUT (3 categories)
# ============================================================

# The only three tutorial categories the suite recognises. A library
# teaches at three levels and nothing else: undergraduate, professional
# practice, research.
TUTORIAL_CATEGORIES = ("educational", "professional", "research")


# ============================================================
#                    TUTORIALS LAYOUT (3 categories)
# ============================================================

# The only three tutorial categories the suite recognises. A library
# teaches at three levels and nothing else: undergraduate, professional
# practice, research.
TUTORIAL_CATEGORIES = ("educational", "professional", "research")


def _skip_violations_in_source(text: str) -> list[tuple[int, str]]:
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
        print("\n  Shadowed tests: OK (none)")
        return
    print(f"\n  SHADOWED-TEST VIOLATIONS ({len(violations)} total):")
    for v in violations[:30]:
        print(f"    [!] {v}")
    if len(violations) > 30:
        print(f"    ... and {len(violations) - 30} more")


def audit_tutorials_layout(lib_root: Path) -> list[str]:
    """``tutorials/`` holds exactly the three canonical categories.

    Infrastructure directories (leading ``_`` or ``.``) are exempt: they
    are not tutorial categories. Everything else is a violation.
    ``pedagogical/``, ``validation/``, ``api/``, ``case/``, ``examples/``
    and the numbered tracks were folded into the three during ORDER O4,
    and without this gate nothing stops them coming back.

    Empty list = compliant. A repo with no ``tutorials/`` is compliant.
    """
    tutorials = lib_root / "tutorials"
    if not tutorials.is_dir():
        return []
    present = {c.name for c in tutorials.iterdir() if c.is_dir()}
    if not present & set(TUTORIAL_CATEGORIES):
        # A repo publishing none of the three is a different family: a
        # book (epy_docs: chapters/, images/), a paper, an app.
        # STRUCTURE_STANDARD Sec.1 forbids cross-applying one family's
        # layout rules to another, so the law binds only a repo that
        # teaches at these levels at all.
        return []
    violations: list[str] = []
    for child in sorted(tutorials.iterdir()):
        if not child.is_dir():
            continue
        name = child.name
        if name.startswith(("_", ".")):
            continue
        if name in TUTORIAL_CATEGORIES:
            continue
        violations.append(
            f"tutorials/{name}/ is not a tutorial category -- tutorials/ "
            f"holds exactly {', '.join(TUTORIAL_CATEGORIES)}. Move its "
            f"contents into one of them (STRUCTURE_STANDARD.md Sec.2.7)."
        )
    return violations


def report_tutorials_layout(violations: list[str]) -> None:
    """Print the tutorials-layout verdict."""
    if not violations:
        print("\n  Tutorials layout: OK (the three categories only)")
    else:
        print(f"\n  TUTORIALS-LAYOUT VIOLATIONS ({len(violations)} total):")
        for v in violations:
            print(f"    - {v}")



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
        print("\n" + "=" * 70)
        print("  SOURCE.md REFERENCE IDS (the filename is the identity)")
        print("=" * 70)
        for rel, why in result["violations"]:
            print(f"    - {rel}: {why}")


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
        print("\n" + "=" * 70)
        print("  SUITE-WIDE MANUAL (one home: references/, never a library repo)")
        print("=" * 70)
        for rel, why in result["violations"]:
            print(f"    - {rel}: {why}")


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
        return [
            "v-selfcomparison: _packaging/_tooling/v_selfcomparison_block.py is "
            "missing, so the V_ validation rows were NOT checked. This is a loud "
            "failure on purpose: a silently skipped rule is worse than none."
        ]

    def report_v_selfcomparison(violations):
        print("\n" + "=" * 70)
        print("  V_ VALIDATION ROWS (a comparison needs two numbers)")
        print("=" * 70)
        for v in violations:
            print(f"    - {v}")

def main() -> None:
    parser = argparse.ArgumentParser(description="ePy Suite Minimal Housekeeper")
    parser.add_argument("--apply", action="store_true", help="Delete temp/cache files")
    parser.add_argument("--quality", action="store_true", help="Run ruff + pyright + coverage checks")
    parser.add_argument(
        "--audit", action="store_true", help="Run only the read-only audits (tests layout, etc.)"
    )
    parser.add_argument(
        "--strict", action="store_true",
        help="Exit code 1 if any audit reports violations.",
    )
    args = parser.parse_args()

    lib_name = LIB_ROOT.name
    print("=" * 60)
    print(f"  Housekeeper: {lib_name}")
    print(f"  Root: {LIB_ROOT}")
    print("=" * 60)

    # ── Cleanup ───────────────────────────────────────────────────────
    targets = collect_targets(LIB_ROOT)
    if targets:
        for t in targets:
            print(f"    {t.relative_to(LIB_ROOT)}")
        print(f"\n  Total items: {len(targets)}")
        if args.apply:
            for t in targets:
                if t.is_dir():
                    shutil.rmtree(t, ignore_errors=True)
                else:
                    t.unlink(missing_ok=True)
            print("  DONE — removed.")
        else:
            print("  Re-run with --apply to delete.")
    else:
        print("\n  Library is clean.")

    # ── Quality check ─────────────────────────────────────────────────
    if args.quality:
        if _QUALITY_CHECK_AVAILABLE:
            qc_result = _run_qc(LIB_ROOT)
            _print_qr(qc_result, lib_name)
        else:
            print("\n  --quality requires _packaging/quality_check.py")

    # ── Structure audit (basic) ───────────────────────────────────────
    src_dir = LIB_ROOT / "src"
    if not src_dir.is_dir():
        print("\n  WARNING: no src/ directory (library may not be built yet)")

    # ── Tests layout audit (mirrors src/<pkg>/ + sanctioned _benchmarks/ exception) ──
    tests_layout_violations = audit_tests_layout(LIB_ROOT)
    report_tests_layout(tests_layout_violations)

    module_mirror_violations = audit_module_mirror(LIB_ROOT)
    report_module_mirror(module_mirror_violations)

    tutorials_layout_violations = audit_tutorials_layout(LIB_ROOT)
    report_tutorials_layout(tutorials_layout_violations)

    # Skipped-test audit (Rule 8: a test that cannot run is fixed or
    # deleted, never skipped)
    skip_violations = audit_no_skipped_tests(LIB_ROOT)
    report_skipped_tests(skip_violations)

    # Shadowed-test audit (a definition discarded by a later one of
    # the same name takes every test inside it out of collection)
    shadowed_violations = audit_no_shadowed_tests(LIB_ROOT)
    report_shadowed_tests(shadowed_violations)

    # A cited references.db id must resolve to a document the file names; the
    # store was renumbered once and every stale id still resolved to something
    _source_ids = audit_source_ids(LIB_ROOT)
    report_source_ids(_source_ids)
    source_ids_violations = _source_ids["violations"]

    # A suite-wide manual duplicated into a library repo will drift; the
    # canonical file lives in references/ and a pointer here is enough
    _suite_manual = audit_suite_manual(LIB_ROOT)
    report_suite_manual(_suite_manual)
    suite_manual_violations = _suite_manual["violations"]

    # A validation row must compare two independently obtained numbers; a
    # value compared with itself reads PASS and verifies nothing
    v_selfcomparison_violations = audit_v_selfcomparison(LIB_ROOT)
    report_v_selfcomparison(v_selfcomparison_violations)

    if args.strict and (
        module_mirror_violations or tutorials_layout_violations
        or skip_violations
        or shadowed_violations
        or source_ids_violations
        or suite_manual_violations
        or v_selfcomparison_violations
    ):
        sys.exit(1)

    print()


if __name__ == "__main__":
    main()
