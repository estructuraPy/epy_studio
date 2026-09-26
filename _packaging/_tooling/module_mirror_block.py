"""The ONE canonical module-mirror block, and the only place it is edited.

The module-mirror rule asserts that every real module under ``src/<pkg>/``
has a mirroring test, and -- new here -- that the test crediting it can
actually be imported.

WHY ONE SOURCE INSTEAD OF TWENTY-NINE COPIES
--------------------------------------------
This was the last housekeeper rule with no canonical block: twenty-nine
hand-maintained copies and no way to reconcile them. Measured 2026-08-21,
they had already forked four ways in ``_is_mirror_exempt`` and four ways in
``audit_module_mirror``:

* ``epy_connections`` still exempted ``/adapters/``, an exemption the other
  twenty-eight had already removed; its own copy recorded the reason the others
  gave for removing it -- the clause hid ``_export_virtual_test.py``. Measured
  2026-08-21, the exemption was keeping three adapter modules in that repo
  outside the gate. It dies here, by sync, and all three turn out to have
  mirrors.
* ``epy_compose`` and ``epy_timber`` carried a literal U+FFFD REPLACEMENT
  CHARACTER in their user-facing violation message, where five others carried a
  real em dash and the rest carried ``--``. A mojibake em dash printed to the
  console is what a lone copy looks like after a round trip through the wrong
  codec.
* Docstrings, wrapping and the final ``return`` differed in four more repos.

None of that changed a verdict. What DID change verdicts is the defect the
rule was rewritten to close.

THE DEFECT: PRESENCE IS NOT COVERAGE
------------------------------------
The old gate collected ``p.name`` for every ``tests/**/test_*.py`` into a FLAT
SET and threw the path away, so ``tests/<anywhere>/test_<stem>.py`` satisfied
ANY src module with that stem. It never opened the file: no parse, no import
check.

``epy_buildings/tests/_core/test_optimization.py`` imported
``epy_buildings._core._optimization``, a module that does not exist -- the
source is at ``_design/_optimization.py``. Every pytest collection of that
repo raised ModuleNotFoundError from 2026-07-23 to 2026-08-20, a full month
in which the suite was not runnable, and this gate counted the broken file as
coverage for the whole of it.

So the block now parses each crediting test and resolves every dotted import
rooted in a package this repo ships. It is PEP 420 aware on purpose: a
directory with no ``__init__.py`` is a legitimate namespace package. Measured
across all twenty-nine repos, five distinct dotted names in twenty-five import
statements resolve ONLY that way (``epy_analysis.epy_suite_connect._reporting``
and four siblings); a checker that demanded ``__init__.py`` would report every
one of them as a false positive.

Measured 2026-08-21 before the sync: the import check exercises 11,464 in-repo
dotted imports across 2,460 test files and fails ZERO of them. It is pure
insurance. That is the intended state -- if it ever fails, something real
broke.

WHY PATH PARITY IS A WARNING AND NOT A FAILURE
----------------------------------------------
359 mirrors -- 26% of them -- sit at a path that does not mirror their module,
and the bulk of that is two conventions the suite adopted deliberately:

* the flat ``epy_suite_connect`` convention, where
  ``epy_suite_connect/{adapters,_adapters,_contract}/*.py`` is mirrored flat at
  ``tests/epy_suite_connect/test_*.py`` (206 of the 359);
* root designer modules, where ``src/<pkg>/<x>_designer.py`` is tested from
  ``tests/_design/`` (12 of the 359).

Failing on those would mean a gate demanding the suite unlearn its own layout.
The advisory names the count and splits out both sanctioned conventions so the
residual is visible and neither convention is ever advised against.
"""

from __future__ import annotations

#: Injected verbatim into each housekeeper. It stays a string because the
#: housekeepers are standalone scripts with no dependency on this package --
#: they are SYNCED, not imported.
MODULE_MIRROR_BLOCK = 'def _is_mirror_exempt(rel: str) -> bool:\n    """Whether ``rel`` is not a unit-test target.\n\n    Integration / packaging / schema / showcase modules are exempt.\n\n    SYNCED from _packaging/_tooling/module_mirror_block.py -- edit it THERE\n    and re-run add_hk_module_mirror_xsuite.py --apply. A local edit here is\n    overwritten by the next sync.\n    """\n    name = rel.rsplit("/", 1)[-1]\n    # No blanket exemption for ``epy_suite_connect/``, and none for\n    # adapters: measured across the suite, 96 of the 110 adapter modules\n    # already ship a mirroring test, so "integration code is not a\n    # unit-test target" is not the convention here -- it was a licence for\n    # the gate to go blind on whole packages. The clause that used to sit\n    # here exempted ``adapters/`` -- and both spellings of it. The\n    # canonical one is ``_adapters/``; the census belongs in\n    # STRUCTURE_STANDARD.md 2.6, not in this comment, which said six and\n    # five when the disk said fifteen and five. What the clause hid was\n    # the one adapter nobody tests: ``_export_virtual_test.py``,\n    # byte-identical in seven repos.\n    if "/_packaging/" in rel or name in (\n        "download_wheels.py",\n        "install_offline.py",\n        "__main__.py",\n    ):\n        return True\n    if "_schemas/" in rel:\n        return True\n    return name in ("_famous.py", "_demo.py", "_showcase.py")\n\n\ndef _mirror_import_roots(src: Path) -> set[str]:\n    """Top-level import roots this repo ships under ``src/``.\n\n    Every directory directly under ``src/`` is a root, with or without an\n    ``__init__.py``: PEP 420 namespace packages are importable too, and a\n    root filter that demanded ``__init__.py`` would simply stop checking\n    whatever lives in one.\n    """\n    if not src.is_dir():\n        return set()\n    return {\n        c.name\n        for c in src.iterdir()\n        if c.is_dir() and c.name != "__pycache__"\n    }\n\n\ndef _mirror_module_exists(src: Path, dotted: str) -> bool:\n    """Whether ``dotted`` resolves to a real module or package under src/.\n\n    PEP 420 aware ON PURPOSE. A directory WITHOUT ``__init__.py`` is a\n    legitimate namespace package and imports fine; an earlier probe that\n    required ``__init__.py`` reported 20 false positives on exactly those\n    directories. The three accepted shapes are therefore ``<path>.py``,\n    ``<path>/__init__.py``, and a bare ``<path>/`` directory.\n    """\n    target = src.joinpath(*dotted.split("."))\n    if target.with_suffix(".py").is_file():\n        return True\n    return target.is_dir()\n\n\ndef _mirror_dead_imports(\n    test_path: Path, src: Path, roots: set[str]\n) -> list[str]:\n    """Dotted imports in ``test_path`` naming no module under ``src/``.\n\n    THE REASON THIS RULE EXISTS. The mirror gate used to be pure PRESENCE:\n    it collected the NAME of every ``tests/**/test_*.py`` into a flat set\n    and never opened the file. The file\n    ``epy_buildings/tests/_core/test_optimization.py`` imported\n    ``epy_buildings._core._optimization``, which does not exist -- the\n    module is at ``_design/_optimization.py``. Every pytest collection of\n    that repo raised ModuleNotFoundError from 2026-07-23 to 2026-08-20,\n    and this gate counted the broken file as coverage the whole time.\n\n    Only imports rooted in a package this repo ships are checked; a sibling\n    library\'s module is not on this repo\'s disk and is none of this gate\'s\n    business. Relative imports are skipped -- resolving them needs the\n    test\'s own package identity, which the flat-name convention that this\n    gate is built on does not pin down.\n    """\n    import ast as _ast\n\n    try:\n        source = test_path.read_text(encoding="utf-8", errors="replace")\n        tree = _ast.parse(source)\n    except SyntaxError as e:\n        return [f"does not parse, so its imports cannot be verified - {e}"]\n\n    dead: list[str] = []\n    seen: set[str] = set()\n    for node in _ast.walk(tree):\n        dotted_names: list[str] = []\n        if isinstance(node, _ast.Import):\n            dotted_names = [a.name for a in node.names]\n        elif isinstance(node, _ast.ImportFrom):\n            if node.level or not node.module:\n                continue\n            dotted_names = [node.module]\n        for dotted in dotted_names:\n            if dotted in seen or dotted.split(".")[0] not in roots:\n                continue\n            seen.add(dotted)\n            if not _mirror_module_exists(src, dotted):\n                dead.append(f"imports `{dotted}`, which does not exist")\n    return dead\n\n\n_MIRROR_ADVISORY: list[str] = []\n"""Where the path-parity advisory waits between audit and report."""\n\n\ndef _mirror_advisory(store: list[str] | None = None) -> list[str]:\n    """Carry the path-parity advisory from the audit to the report.\n\n    ``report_module_mirror(violations)`` is called with exactly one\n    argument in all twenty-nine housekeepers; widening that signature would\n    make this sync rewrite twenty-nine call sites in ``main()`` as well. A\n    tiny accessor keeps the wiring untouched and keeps the advisory out of\n    the ``--strict`` failure tuple, which is the point: path parity is a\n    WARNING, never a failure.\n    """\n    if store is not None:\n        _MIRROR_ADVISORY[:] = store\n    return list(_MIRROR_ADVISORY)\n\n\ndef audit_module_mirror(lib_root: Path) -> list[str]:\n    """Every real src module needs a mirroring test whose imports RESOLVE.\n\n    Two checks, both failures:\n\n    1. PRESENCE -- a ``test_<stem>.py`` or ``test_<stem>_*.py`` exists\n       somewhere under ``tests/``. Closes the gap left by the folder-level\n       tests-layout audit, which reports OK even when a module has no test.\n    2. IMPORTABILITY -- every crediting test parses, and every dotted\n       import it makes into a package this repo ships resolves to a real\n       module or package on disk. A test that cannot be imported is not\n       coverage, and for a month one of them was counted as coverage.\n\n    Path parity -- does the test sit at the MIRRORED path? -- is\n    deliberately NOT a failure. Measured 2026-08-21 across the suite: 359\n    mirrors, 26% of them, live at a non-mirrored path, and the bulk of\n    those follow two conventions the suite chose on purpose. It is\n    reported as an advisory instead; see ``report_module_mirror``.\n\n    SYNCED from _packaging/_tooling/module_mirror_block.py -- edit it THERE\n    and re-run add_hk_module_mirror_xsuite.py --apply. A local edit here is\n    overwritten by the next sync.\n    """\n    pkg = _find_pkg_dir(lib_root)\n    if pkg is None:\n        return [\n            f"src/<pkg>/ not found under {lib_root} -- cannot audit "\n            f"module mirror."\n        ]\n    src = pkg.parent\n    roots = _mirror_import_roots(src)\n\n    tests = lib_root / "tests"\n    # stem -> the test files carrying that stem. The old gate kept only the\n    # NAMES, in a flat set, and threw the paths away -- which is why it\n    # could neither open the file nor say where the mirror actually lived.\n    by_name: dict[str, list[Path]] = {}\n    if tests.is_dir():\n        for p in tests.rglob("test_*.py"):\n            if "__pycache__" not in p.parts:\n                by_name.setdefault(p.name, []).append(p)\n\n    violations: list[str] = []\n    crediting: dict[Path, None] = {}\n    off_mirror: list[tuple[str, str]] = []\n\n    for m in sorted(pkg.rglob("*.py")):\n        if "__pycache__" in m.parts or m.name == "__init__.py":\n            continue\n        rel = m.relative_to(pkg).as_posix()\n        if _is_mirror_exempt(rel):\n            continue\n        bare = m.name[:-3].lstrip("_")\n        if bare in ("utils", "types", "constants", "typing", "protocols"):\n            continue\n        mirrors = list(by_name.get(f"test_{bare}.py", []))\n        for name, paths in by_name.items():\n            if name.startswith(f"test_{bare}_") and name.endswith(".py"):\n                mirrors.extend(paths)\n        if not mirrors:\n            violations.append(\n                f"src module without mirroring test: "\n                f"src/{pkg.name}/{rel} -- add tests/.../test_{bare}.py "\n                f"(suite-wide tests-mirror DNA)."\n            )\n            continue\n        for t in mirrors:\n            crediting[t] = None\n        # Path parity, advisory only. The mirrored home of\n        # src/<pkg>/a/b/c.py is tests/a/b/test_c.py.\n        want_dir = (tests / rel).parent\n        if not any(t.parent == want_dir for t in mirrors):\n            where = mirrors[0].relative_to(lib_root).parent.as_posix()\n            off_mirror.append((rel, where))\n\n    for t in sorted(crediting):\n        where = t.relative_to(lib_root).as_posix()\n        for problem in _mirror_dead_imports(t, src, roots):\n            violations.append(\n                f"mirroring test {where} {problem} -- it cannot be "\n                f"collected, so it is not coverage; point it at the real "\n                f"module or delete it."\n            )\n\n    # Two conventions the suite adopted deliberately. They are named here\n    # so the advisory does NOT advise against them.\n    flat_connect = sum(\n        1 for rel, _ in off_mirror if "epy_suite_connect/" in rel\n    )\n    root_designer = sum(\n        1\n        for rel, _ in off_mirror\n        if "/" not in rel and rel.endswith("_designer.py")\n    )\n    advisory: list[str] = []\n    if off_mirror:\n        residual = len(off_mirror) - flat_connect - root_designer\n        advisory.append(\n            f"{len(off_mirror)} mirroring test(s) sit at a non-mirrored "\n            f"path ({flat_connect} flat epy_suite_connect, "\n            f"{root_designer} root designer, {residual} other). Advisory "\n            f"only -- the mirror is credited either way."\n        )\n        for rel, where in off_mirror[:8]:\n            advisory.append(f"src/{pkg.name}/{rel} -> {where}/")\n        if len(off_mirror) > 8:\n            advisory.append(f"... and {len(off_mirror) - 8} more")\n    _mirror_advisory(advisory)\n    return violations\n\n\ndef report_module_mirror(violations: list[str]) -> None:\n    """Print the module-mirror result, then the path-parity advisory.\n\n    The advisory prints separately and never enters the ``--strict``\n    failure tuple. The two conventions it names are SANCTIONED, and must\n    not be "fixed":\n\n    * the flat ``tests/epy_suite_connect/test_*.py`` layout mirroring\n      ``epy_suite_connect/{adapters,_adapters,_contract}/*.py``;\n    * root designer modules ``src/<pkg>/<x>_designer.py`` tested from\n      ``tests/_design/``.\n    """\n    if not violations:\n        print(\n            "\\n  Module mirror: OK (every real src module has a mirroring "\n            "test, and every one of them imports)"\n        )\n    else:\n        print(f"\\n  MODULE-MIRROR VIOLATIONS ({len(violations)} total):")\n        for v in violations:\n            print(f"    - {v}")\n    advisory = _mirror_advisory()\n    if advisory:\n        print(\n            f"\\n  Module mirror path parity (advisory, NOT a failure): "\n            f"{advisory[0]}"\n        )\n        for line in advisory[1:]:\n            print(f"    . {line}")\n'
