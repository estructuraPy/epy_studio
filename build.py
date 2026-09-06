"""Build the ePy Studio unified bundle (four apps + launcher, one runtime).

Run from this directory:

    python build.py              # build dist/epy_studio/ (installer input)

This produces ONE PyInstaller onedir layout under ``dist/epy_studio/``
holding ``epy_studio.exe`` (launcher), ``epy_reports.exe``,
``epy_slides.exe`` and ``epy_papers.exe`` over a single shared
``_internal/``. The Windows installer (``windows/epy_studio.iss``)
packages it with per-app components.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DIST = ROOT / "dist"
BUILD = ROOT / "build"
SPEC = ROOT / "epy_studio.spec"
APP_NAME = "epy_studio"
BUILD_SUPPORT = ROOT / "windows" / "build_support"
sys.path.insert(0, str(BUILD_SUPPORT))
import pyz_probe  # noqa: E402 - needs BUILD_SUPPORT on sys.path first

#: (executable stem, module inside it, literal that only exists because
#: of a shipped fix). The build fails when a produced exe lacks one.
#:
#: Why a literal and not a test: a fix that is in git is not a fix the
#: user has. The window's PDF export was repaired hours before the
#: installed bundle stopped raising, because nobody had rebuilt it. Each
#: row pins one such fix to the bytes that actually ship.
SHIPPED_FIXES = (
    # add_metadata is called with creator/producer; the producer literal
    # exists only because that call site was fixed (epy_reports d5a6ee6).
    ("epy_reports", "epy_reports._ui.tab", "epy_reports — ANM Ingeniería"),
    # A project is its store file, opened by .kepy or by folder, and
    # sealed into one .zepy (epy_draft 87b55f0, 86cf01b). The old
    # probe named _project_root_for, retired there: a stale probe
    # refusing the build is the probe working.
    ("epy_draft", "epy_draft.app", "open_path"),
    ("epy_draft", "epy_draft._core._project", "LEGACY_STORE_NAME"),
    ("epy_draft", "epy_draft._core._project.archive", "ARCHIVE_SUFFIX"),
    # The project owns its prompts, and the batch reads them from the
    # store (epy_draft 970fa9b); drawings are indexed (68626b2).
    ("epy_draft", "epy_draft._core._project.content", "doc_for"),
    ("epy_draft", "epy_draft._core._index.extract", "_DXF_SUFFIX"),
    # The optional autosave: its module constant only exists with it.
    ("epy_reports", "epy_reports.app", "AUTOSAVE_INTERVAL_MS"),
    ("epy_slides", "epy_slides.app", "AUTOSAVE_INTERVAL_MS"),
    ("epy_papers", "epy_papers.app", "AUTOSAVE_INTERVAL_MS"),
    # One settings organisation for the family; the launcher must
    # carry epy_export to read the language the editors stored.
    ("epy_studio", "epy_export._core._identity", "ANM Ingeniería"),
    # The offer a silent install needs, and the export that no
    # longer freezes the window while LaTeX runs.
    ("epy_studio", "epy_studio._core.winreg_assoc", "is_registered"),
    ("epy_papers", "epy_papers.app", "_run_off_thread"),
)


def _run(cmd: list[str], env: dict[str, str] | None = None) -> None:
    """Run a subprocess and abort with its exit code on failure."""
    print("$", " ".join(cmd))
    result = subprocess.run(cmd, check=False, env=env)
    if result.returncode != 0:
        sys.exit(result.returncode)


def _build_env() -> dict[str, str]:
    """Environment for PyInstaller: prepend the build-support dir.

    ``windows/build_support/sitecustomize.py`` pins the System32 ICU in
    every Python process of the build tree, so PyInstaller's isolated
    Qt introspection can import PySide6 under conda (see that module's
    docstring). Without it the Qt plugin collection fails SILENTLY and
    the frozen apps cannot initialize a platform plugin.
    """
    env = os.environ.copy()
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = (
        f"{BUILD_SUPPORT}{os.pathsep}{existing}"
        if existing
        else str(BUILD_SUPPORT)
    )
    return env


def _verify_qt_runtime(target: Path) -> None:
    """Fail the build when the Qt runtime is incomplete.

    Guards against the silent-skip failure mode above: a bundle that
    builds "successfully" but cannot start (missing platform plugin) or
    cannot render previews (missing WebEngine helper/resources).
    """
    internal = target / "_internal"
    required = {
        "Qt platform plugin": (
            internal / "PySide6" / "plugins" / "platforms" / "qwindows.dll"
        ),
        "WebEngine helper": (
            internal / "PySide6" / "QtWebEngineProcess.exe"
        ),
        "WebEngine ICU data": (
            internal / "PySide6" / "resources" / "icudtl.dat"
        ),
    }
    missing = [
        f"{label}: {path}"
        for label, path in required.items()
        if not path.is_file()
    ]
    poison = [
        str(p)
        for p in internal.rglob("icu*.dll")
        # Any bundled ICU DLL would shadow the System32 one Qt links
        # against on end-user machines (icudtl.dat is fine: data, not a DLL).
    ]
    if missing or poison:
        for line in missing:
            print(f"MISSING  {line}")
        for line in poison:
            print(f"POISON   bundled ICU DLL: {line}")
        sys.exit(
            "Qt runtime verification failed — refusing to ship "
            "this bundle."
        )
    print(
        "Qt runtime verified: platform plugin, WebEngine helper and "
        "resources present."
    )


def _verify_shipped_fixes(target: Path) -> None:
    """Fail the build when a produced exe does not carry a known fix.

    Reads the PYZ inside each executable and looks for the literal each
    row of :data:`SHIPPED_FIXES` names. Refuses loudly on a missing exe,
    an unreadable bundle, a module absent from the PYZ, or a literal
    absent from the module -- a bundle built from the wrong checkout looks
    identical from the outside, and this is the only place that can tell.
    """
    missing: list[str] = []
    skipped: list[str] = []
    optional = _optional_ids()
    for stem, module, literal in SHIPPED_FIXES:
        exe = target / f"{stem}.exe"
        if not exe.is_file():
            if stem in optional:
                # Not produced because its checkout was absent: said,
                # not failed. Its probes wait for the day it ships.
                skipped.append(
                    f"{exe.name}: optional, not built -- {literal!r} "
                    f"not probed"
                )
                continue
            missing.append(f"{exe.name}: not produced")
            continue
        try:
            if not pyz_probe.carries(exe, module, literal):
                missing.append(f"{exe.name}: {module} lacks {literal!r}")
        except pyz_probe.BundleProbeError as exc:
            missing.append(f"{exe.name}: {exc}")
    if missing:
        sys.exit(
            "Shipped-fix verification FAILED -- the bundle does not carry "
            "a fix that is in git:\n  " + "\n  ".join(missing)
        )
    for line in skipped:
        print(f"SKIPPED {line}")
    print(
        f"Shipped fixes verified: {len(SHIPPED_FIXES) - len(skipped)} "
        f"literal(s) present "
        f"in the produced executables."
    )


def _catalog_apps() -> list[dict[str, object]]:
    """Return the catalog's entries as written."""
    catalog = json.loads(
        (ROOT / "src" / "epy_studio" / "_config" / "apps.epyson").read_text(
            encoding="utf-8"
        )
    )
    return list(catalog["apps"])


def _optional_ids() -> frozenset[str]:
    """Return the ids of the applications the bundle may lack."""
    return frozenset(
        str(app["id"]) for app in _catalog_apps() if app.get("optional")
    )


_GUARD = re.compile(
    r"#ifexist[^\n]*?\b(?P<exe>[A-Za-z0-9_]+\.exe)\"[^\n]*\n(?P<body>.*?)#endif",
    re.S,
)


def _verify_manifest() -> None:
    """Refuse to build when the installer and the catalog disagree.

    The list of applications is stated in two places that cannot read
    each other: ``src/epy_studio/_config/apps.epyson``, which the
    launcher and this script read, and ``windows/epy_studio.iss``, which
    Inno Setup reads and which cannot parse JSON.

    Two is one more than one, and this repository has already paid for
    it: the list also lived in the spec, the README and this script's
    own docstring, and by the time a fourth application shipped three of
    those still said "three editors". Checking is cheaper than the
    drift.

    The version is checked the same way and for a sharper reason:
    ``OutputBaseFilename`` embeds ``AppVersion``, so a stale value
    silently overwrites the previous release's artifact. Two different
    bundles can ship under one filename.

    Raises:
        SystemExit: Naming what disagrees. Refusing to ship a bundle
            that lies is already this script's idiom for the Qt runtime.
    """
    catalog = json.loads(
        (ROOT / "src" / "epy_studio" / "_config" / "apps.epyson").read_text(
            encoding="utf-8"
        )
    )
    iss = (ROOT / "windows" / "epy_studio.iss").read_text(
        encoding="utf-8", errors="replace"
    )

    problems: list[str] = []
    # An OPTIONAL application's lines must sit inside #ifexist blocks
    # naming its own executable, and NOWHERE else: one unguarded line
    # is enough for ISCC to refuse to compile the day the executable is
    # not there, which is the whole case an optional application is
    # for. A required application's lines are checked as before.
    guarded: dict[str, str] = {}
    for match in _GUARD.finditer(iss):
        exe_name = match.group("exe")
        guarded[exe_name] = guarded.get(exe_name, "") + match.group("body")
    unguarded = _GUARD.sub("", iss)
    for app in catalog["apps"]:
        exe = f"{app['id']}.exe"
        component = f"Name: \"{app['component']}\""
        if app.get("optional"):
            inside = guarded.get(exe, "")
            if exe not in inside:
                problems.append(
                    f"{exe} is optional and has no #ifexist block of its "
                    f"own in the .iss"
                )
            if component not in inside:
                problems.append(
                    f"component {app['component']!r} of optional {exe} is "
                    f"not inside its #ifexist block"
                )
            if exe in unguarded or component in unguarded:
                problems.append(
                    f"{exe} is optional but a line names it outside its "
                    f"#ifexist block; ISCC would fail without the exe"
                )
            continue
        if exe not in unguarded:
            problems.append(f"{exe} is in the catalog, not the .iss")
        if component not in unguarded:
            problems.append(
                f"component {app['component']!r} is in the catalog, "
                f"not the .iss"
            )

    declared = re.search(r'#define AppVersion "([^"]+)"', iss)
    package = (ROOT / "src" / "epy_studio" / "__init__.py").read_text(
        encoding="utf-8"
    )
    ours = re.search(r'__version__ = "([^"]+)"', package)
    if declared and ours and declared.group(1) != ours.group(1):
        problems.append(
            f"AppVersion is {declared.group(1)} and __version__ is "
            f"{ours.group(1)}; OutputBaseFilename embeds the first, so "
            f"a stale value overwrites the previous release's artifact"
        )

    if problems:
        raise SystemExit(
            "refusing to build -- the installer and the catalog disagree:\n  "
            + "\n  ".join(problems)
        )
    print(
        f"Manifest verified: {len(catalog['apps'])} applications, "
        f"version {ours.group(1) if ours else '?'}."
    )


def _clean() -> None:
    """Remove previous build and dist directories."""
    for path in (BUILD, DIST):
        if path.exists():
            print(f"removing {path}")
            shutil.rmtree(path)


def _build_onedir() -> Path:
    """Run PyInstaller via the project spec. Returns the dist folder."""
    _run(
        [sys.executable, "-m", "PyInstaller", "--noconfirm", str(SPEC)],
        env=_build_env(),
    )
    target = DIST / APP_NAME
    if not target.exists():
        sys.exit(f"PyInstaller did not produce {target}")
    _verify_qt_runtime(target)
    _verify_shipped_fixes(target)
    return target


def main() -> int:
    """CLI entry point for the build script."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--keep",
        action="store_true",
        help="Skip the initial cleanup of build/ and dist/.",
    )
    args = parser.parse_args()

    _verify_manifest()
    if not args.keep:
        _clean()

    produced = _build_onedir()

    if BUILD.exists():
        print(f"cleaning {BUILD}")
        shutil.rmtree(BUILD, ignore_errors=True)

    print(f"\nDone. Installer input: {produced}")
    print("Next: build the installer (windows/epy_studio.iss).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
