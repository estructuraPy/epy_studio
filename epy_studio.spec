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
    # Heavy scientific stack reachable through optional epy_docs paths;
    # never imported by the frozen editors themselves.
    "matplotlib",
    "pandas",
    "numpy",
    "epy_docs",
]

# pypandoc data + pandoc.exe (shared by the three apps; deduped in COLLECT).
_pandoc_datas = collect_data_files("pypandoc", include_py_files=False)
_pandoc_bins = collect_dynamic_libs("pypandoc")
_pandoc = pypandoc.get_pandoc_path()
if not _pandoc.lower().endswith(".exe"):
    _pandoc += ".exe"
_pandoc_bins = [*_pandoc_bins, (_pandoc, "pypandoc/files")]


def _app_assets(pkg: str) -> list[tuple[str, str]]:
    """Bundle <repo>/src/<pkg>/_config/_assets preserving package layout."""
    assets = _SUITE / pkg / "src" / pkg / "_config" / "_assets"
    src_root = _SUITE / pkg / "src" / pkg
    return [
        (str(p), str(_Path(pkg) / p.relative_to(src_root).parent))
        for p in assets.rglob("*")
        if p.is_file() and p.suffix != ".py"
    ]


def _app_hidden(pkg: str, extra_asset_pkgs: list[str]) -> list[str]:
    """Hidden imports: pypandoc + the dynamically-imported asset packages."""
    hidden = collect_submodules("pypandoc")
    hidden += [f"{pkg}._config", f"{pkg}._config._assets"]
    hidden += [f"{pkg}._config._assets.{sub}" for sub in extra_asset_pkgs]
    # Lazy-imported inside _pdf_footer.add_watermark; PyInstaller may miss
    # the in-function import.
    hidden += ["PIL", "PIL.Image"]
    return hidden


def _app_analysis(pkg: str, extra_asset_pkgs: list[str]) -> Analysis:  # noqa: F821
    """One Analysis per app, built from its repo's src/ tree."""
    return Analysis(  # noqa: F821 — PyInstaller build namespace
        [str(_SUITE / pkg / "src" / pkg / "__main__.py")],
        pathex=[str(_SUITE / pkg / "src")],
        binaries=list(_pandoc_bins),
        datas=list(_pandoc_datas) + _app_assets(pkg),
        hiddenimports=_app_hidden(pkg, extra_asset_pkgs),
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
a_launcher = Analysis(
    [str(_ROOT / "launcher.py")],
    pathex=[str(_ROOT)],
    binaries=[],
    datas=[],
    hiddenimports=["_assoc"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=_EXCLUDES + ["pypandoc"],
    noarchive=False,
)


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
    strip=False,
    upx=False,
    upx_exclude=[],
    name="epy_studio",
)
