"""Canonical dead-import gate, synced into every application repository.

THE REASON THIS EXISTS. When the PDF stamping moved to epy_export, two
call sites in epy_reports' window export kept importing the local
`_core._pdf_footer` that had gone with it. Both sit INSIDE the export
function, so the package still imported cleanly and nothing failed at
start-up; and the export tests patch `export_pdf` without running its
body, so no test reached them. `after_pass1` is on the main path, so
every PDF export from that window raised ModuleNotFoundError -- in a
build that had already shipped, and for six days.

An import that names nothing is invisible to review and to a green test
run. It is not invisible to a parser, and this costs milliseconds.

BOTH spellings are checked, because they fail differently:

    import pkg.gone            -> the module does not exist
    from pkg.mod import gone   -> pkg.mod exists and does not define it

A check that only resolved modules would pass the second, which is
exactly the one that shipped.

SYNCED from _packaging/_tooling/dead_import_block.py -- edit it THERE
and re-copy. A local edit here is overwritten by the next sync.
"""

from __future__ import annotations

import ast
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
PACKAGE = next(
    p for p in SRC.iterdir() if p.is_dir() and p.name.startswith("epy_")
)


def _own_imports(path: Path, tree: ast.AST, package: str) -> list[str]:
    """Dotted names a file imports from its OWN package.

    Absolute and RELATIVE both. Some packages here are written
    almost entirely in relative imports, and a dead one breaks in
    exactly the same way -- skipping them would leave the scan
    reaching nothing in the repositories that need it most.
    """
    # The file's own PACKAGE, which is what a relative import counts
    # from: drop the module name, and for a package __init__ that
    # name is "__init__" -- the same one step either way.
    here = path.relative_to(SRC).with_suffix("").parts[:-1]
    dotted: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            dotted += [
                alias.name
                for alias in node.names
                if alias.name.split(".")[0] == package
            ]
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = here[: len(here) - node.level + 1]
                if not base:
                    continue
                stem = ".".join([*base, node.module or ""]).rstrip(".")
            elif node.module and node.module.split(".")[0] == package:
                stem = node.module
            else:
                continue
            dotted += [f"{stem}.{a.name}" for a in node.names]
    return dotted


def _resolves(dotted: str) -> bool:
    """Whether ``dotted`` is a module, a package, or a name inside one."""
    target = SRC.joinpath(*dotted.split("."))
    if target.with_suffix(".py").is_file() or target.is_dir():
        return True
    parent = SRC.joinpath(*dotted.split(".")[:-1])
    leaf = dotted.rsplit(".", 1)[-1]
    for candidate in (parent.with_suffix(".py"), parent / "__init__.py"):
        if candidate.is_file():
            source = candidate.read_text(encoding="utf-8", errors="replace")
            return leaf in ast.dump(ast.parse(source))
    return False


def _source_files() -> list[Path]:
    return [
        path
        for path in sorted(PACKAGE.rglob("*.py"))
        if "__pycache__" not in path.parts
    ]


def test_no_source_file_imports_a_module_that_does_not_exist() -> None:
    # A lazy import inside a function is invisible until that line runs,
    # and the line that shipped broken was one nothing ran.
    dead: list[str] = []
    for path in _source_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), str(path))
        for dotted in _own_imports(path, tree, PACKAGE.name):
            if not _resolves(dotted):
                dead.append(f"{path.relative_to(SRC)} imports {dotted}")
    assert not dead, "imports naming nothing on disk: " + "; ".join(dead)


def test_the_check_can_see_a_missing_module() -> None:
    # The control. A resolver that answered True for everything would
    # pass the test above over any amount of rot.
    package = PACKAGE.name
    probe = PACKAGE / "__init__.py"
    tree = ast.parse(f"from {package}._core import _gone_module")
    assert _own_imports(probe, tree, package) == [
        f"{package}._core._gone_module"
    ]
    assert not _resolves(f"{package}._core._gone_module")


def test_the_check_can_see_a_missing_name_in_a_real_module() -> None:
    # The second control, and the half that actually shipped: the module
    # exists, the name in it does not. A module-only resolver says yes.
    package = PACKAGE.name
    probe = PACKAGE / "__init__.py"
    tree = ast.parse(f"from {package} import _a_name_that_is_not_there")
    assert _own_imports(probe, tree, package) == [
        f"{package}._a_name_that_is_not_there"
    ]
    assert not _resolves(f"{package}._a_name_that_is_not_there")


def test_the_scan_reaches_the_files_it_is_meant_to_guard() -> None:
    # The third control: a green run over zero files is not a green run.
    seen = sum(
        len(
            _own_imports(
                p, ast.parse(p.read_text(encoding="utf-8")), PACKAGE.name
            )
        )
        for p in _source_files()
    )
    assert seen >= 10, f"only {seen} own-package import(s) seen"
