# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for ePy Studio: ONE onedir bundle carrying the three
# document apps (epy_reports, epy_slides, epy_papers) plus the launcher,
# all sharing a single REAL _internal/ runtime.
#
# This is the sanctioned dedup design (see the 2026-06-20 shared-runtime
# incident): no junctions, no symlinks — one bundle, several EXEs, one
# COLLECT. Identical (dest, source) entries across the per-app analyses
# (PySide6/Qt, pypandoc, pandoc.exe) deduplicate inside COLLECT, so the
# runtime ships once instead of three times.
#
# Build from this directory AFTER `pip install -e` of the three apps:
#   python build.py

from pathlib import Path as _Path

import pypandoc
from PyInstaller.utils.hooks import (
    collect_data_files,
    collect_dynamic_libs,
    collect_submodules,
)

_ROOT = _Path(SPECPATH)  # noqa: F821 — provided by PyInstaller
_SUITE = _ROOT.parent

_EXCLUDES = [
    "tkinter",
    "test",
    "unittest",
    # The build env may carry other Qt bindings (PyQt5 via matplotlib,
    # pulled in by sibling libs). The apps use PySide6 exclusively.
    "PyQt5",
    "PyQt6",
    # epy_docs is excluded for a reason of its own, and not the one this
    # comment used to give. It is a commercial, non-PyPI package; the
    # Studio installer is a free per-user download under MIT, so bundling
    # it would hand it to everyone who runs setup.exe. It would also not
    # work: epy_docs shells out to the `quarto` executable and a TeX
    # distribution, neither of which is a Python module PyInstaller can
    # collect -- the menu would enable itself and the export would die in
    # a worker thread. Reaching it is an out-of-process job, not a
    # bundling one.
    "epy_docs",
    # The scientific stack, excluded by measurement rather than by
    # reputation. NONE of these is named even once across the four apps'
    # source (checked: torch, tensorflow, sklearn, skimage, cv2, faiss,
    # nltk, pyarrow, numba, llvmlite, imageio, kaleido -> zero files).
    #
    # They arrive through one chain, and the chain starts at a dependency
    # nothing imports: epy_reports declares plotly, but its _core/_plotly
    # module imports only `re` -- the figures are rendered by the bundled
    # Plotly.js in the page, never by the Python package. PyInstaller
    # still finds plotly in the build environment, and its hook pulls
    # kaleido, then skimage, then scipy, then torch, then tensorflow.
    #
    # Measured on this machine: the bundle went from 872 MB (June, three
    # apps) to 6.7 GB / 12,840 files, of which torch is 3.5 GB and
    # tensorflow 1.2 GB. Worse than the size is what it means -- the
    # bundle's contents depend on what happens to be pip-installed on the
    # machine doing the build, so the same commit ships differently from
    # two laptops. Naming them here makes the answer the same everywhere.
    "matplotlib",
    "pandas",
    "numpy",
    "plotly",
    "kaleido",
    "skimage",
    "scipy",
    "torch",
    "tensorflow",
    "sklearn",
    "cv2",
    "faiss",
    "nltk",
    "pyarrow",
    "numba",
    "llvmlite",
    "imageio",
    "imageio_ffmpeg",
    "shapely",
]

# pypandoc data + pandoc.exe (shared by the three apps; deduped in COLLECT).
_pandoc_datas = collect_data_files("pypandoc", include_py_files=False)
_pandoc_bins = collect_dynamic_libs("pypandoc")
_pandoc = pypandoc.get_pandoc_path()
if not _pandoc.lower().endswith(".exe"):
    _pandoc += ".exe"
_pandoc_bins = [*_pandoc_bins, (_pandoc, "pypandoc/files")]


def _app_assets(pkg: str) -> list[tuple[str, str]]:
    """Bundle <repo>/src/<pkg>/_config preserving package layout.

    The whole _config tree, not only _config/_assets. Measured before
    widening it: epy_reports and epy_slides keep every non-.py file
    under _assets, so nothing changes for them. Two apps did lose files
    to the narrower walk -- epy_papers/_config/_data/journals.json, the
    50-journal profile catalog its export path is built around, and all
    five of epy_draft's .epyson catalogs, without which its loader
    raises on first use rather than defaulting.
    """
    config = _SUITE / pkg / "src" / pkg / "_config"
    src_root = _SUITE / pkg / "src" / pkg
    return [
        (str(p), str(_Path(pkg) / p.relative_to(src_root).parent))
        for p in config.rglob("*")
        if p.is_file()
        and p.suffix != ".py"
        and "__pycache__" not in p.parts
    ]


def _app_hidden(
    pkg: str, extra_asset_pkgs: list[str], extra: list[str] | None = None
) -> list[str]:
    """Hidden imports: pypandoc + the dynamically-imported asset packages.

    ``extra`` carries whatever else an app resolves at run time and the
    dependency graph cannot see -- entry-point plugins, for instance.
    """
    hidden = collect_submodules("pypandoc")
    hidden += [f"{pkg}._config", f"{pkg}._config._assets"]
    hidden += [f"{pkg}._config._assets.{sub}" for sub in extra_asset_pkgs]
    hidden += list(extra or [])
    # Lazy-imported inside _pdf_footer.add_watermark; PyInstaller may miss
    # the in-function import.
    hidden += ["PIL", "PIL.Image"]
    return hidden


def _app_analysis(  # noqa: F821
    pkg: str,
    extra_asset_pkgs: list[str],
    extra_hidden: list[str] | None = None,
) -> Analysis:  # noqa: F821
    """One Analysis per app, built from its repo's src/ tree."""
    return Analysis(  # noqa: F821 — PyInstaller build namespace
        [str(_SUITE / pkg / "src" / pkg / "__main__.py")],
        pathex=[str(_SUITE / pkg / "src")],
        binaries=list(_pandoc_bins),
        datas=list(_pandoc_datas) + _app_assets(pkg),
        hiddenimports=_app_hidden(pkg, extra_asset_pkgs, extra_hidden),
        hookspath=[],
        hooksconfig={},
        runtime_hooks=[],
        excludes=_EXCLUDES,
        noarchive=False,
)


def _icon(pkg: str, *parts: str) -> str | None:
    path = _SUITE / pkg / "src" / pkg / "_core" / "_packaging" / _Path(*parts)
    return str(path) if path.exists() else None


a_reports = _app_analysis(
    "epy_reports",
    ["branding", "themes", "reference_docx", "mathjax", "csl", "mermaid", "nomnoml"],
)
a_slides = _app_analysis(
    "epy_slides",
    ["branding", "themes", "reference_pptx", "mathjax", "revealjs", "mermaid", "nomnoml"],
)
a_papers = _app_analysis(
    "epy_papers",
    ["branding", "themes", "mathjax", "csl", "mermaid", "nomnoml"],
)
a_craft = _app_analysis(
    "epy_draft",
    ["branding", "prompts"],
    # keyring resolves its backend through entry points, which the
    # dependency graph cannot see. Without these the frozen app reports
    # "no recommended backend" and silently loses every stored API key.
    extra_hidden=[
        "keyring.backends",
        "keyring.backends.Windows",
        "keyring.backends.SecretService",
        "keyring.backends.chainer",
        "keyring.backends.fail",
        "yaml",
        "pypdf",
    ],
)
a_launcher = Analysis(
    [str(_ROOT / "src" / "epy_studio" / "__main__.py")],
    pathex=[str(_ROOT / "src"), str(_SUITE / "epy_export" / "src")],
    binaries=[],
    # The application catalog. It is DATA, and a build that does not
    # carry it produces an empty selector that looks like a broken
    # install rather than a broken build -- which is why the loader
    # raises instead of defaulting.
    datas=[(
        str(_ROOT / "src" / "epy_studio" / "_config" / "apps.epyson"),
        "epy_studio/_config",
    )],
    # _assoc was a top-level module on sys.path, where any collision
    # shadowed it silently. It is epy_studio._core.winreg_assoc now and
    # the dependency graph can see it.
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=_EXCLUDES + ["pypandoc"],
    noarchive=False,
)


def _drop_icu_dlls(analysis) -> None:
    """Strip any ICU DLL picked up from the build environment.

    PySide6 >= 6.9 links Qt6Core against the Windows system ICU
    (System32); a conda ICU copy bundled into _internal would shadow it
    on end-user machines and kill every Qt import with WinError 127.
    WebEngine's icudtl.dat is a data file, not a DLL — unaffected.
    """
    analysis.binaries = [
        entry
        for entry in analysis.binaries
        if not (
            (name := _Path(entry[0]).name.lower()).startswith("icu")
            and name.endswith(".dll")
        )
    ]


def _drop_qt_qml(analysis) -> None:
    """Strip the PySide6 qml/ tree.

    The apps are QtWidgets-only: the QML runtime is never loaded. The
    PySide6 wheel's qml/ tree is large and carries build debris
    (objects-Debug/*.obj) whose deep paths break the installer compile
    (MAX_PATH). Qt6Qml*.dll stay: they are link-time deps of WebEngine.
    """

    def keep(entry) -> bool:
        return not entry[0].replace("\\", "/").lower().startswith("pyside6/qml/")

    analysis.binaries = [entry for entry in analysis.binaries if keep(entry)]
    analysis.datas = [entry for entry in analysis.datas if keep(entry)]


for _a in (a_reports, a_slides, a_papers, a_craft, a_launcher):
    _drop_icu_dlls(_a)
    _drop_qt_qml(_a)


def _exe(analysis, name: str, icon: str | None) -> EXE:  # noqa: F821
    return EXE(  # noqa: F821
        PYZ(analysis.pure),  # noqa: F821
        analysis.scripts,
        [],
        exclude_binaries=True,
        name=name,
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,
        console=False,
        disable_windowed_traceback=False,
        icon=icon,
    )


exe_reports = _exe(
    a_reports, "epy_reports", _icon("epy_reports", "assets_build", "epy_reports.ico")
)
exe_slides = _exe(
    a_slides, "epy_slides", _icon("epy_slides", "assets_build", "epy_slides.ico")
)
exe_papers = _exe(
    a_papers, "epy_papers", _icon("epy_papers", "assets_build", "epy_papers.ico")
)
exe_craft = _exe(
    a_craft, "epy_draft", _icon("epy_draft", "assets_build", "epy_draft.ico")
)
exe_launcher = _exe(
    a_launcher, "epy_studio", _icon("epy_reports", "assets_build", "epy_reports.ico")
)

coll = COLLECT(  # noqa: F821
    exe_launcher,
    a_launcher.binaries,
    a_launcher.datas,
    exe_reports,
    a_reports.binaries,
    a_reports.datas,
    exe_slides,
    a_slides.binaries,
    a_slides.datas,
    exe_papers,
    a_papers.binaries,
    a_papers.datas,
    exe_craft,
    a_craft.binaries,
    a_craft.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="epy_studio",
)
