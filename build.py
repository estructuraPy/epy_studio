"""Build the ePy Studio unified bundle (three apps + launcher, one runtime).

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
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DIST = ROOT / "dist"
BUILD = ROOT / "build"
SPEC = ROOT / "epy_studio.spec"
APP_NAME = "epy_studio"


def _run(cmd: list[str]) -> None:
    """Run a subprocess and abort with its exit code on failure."""
    print("$", " ".join(cmd))
    result = subprocess.run(cmd, check=False)
    if result.returncode != 0:
        sys.exit(result.returncode)


def _clean() -> None:
    """Remove previous build and dist directories."""
    for path in (BUILD, DIST):
        if path.exists():
            print(f"removing {path}")
            shutil.rmtree(path)


def _build_onedir() -> Path:
    """Run PyInstaller via the project spec. Returns the dist folder."""
    _run([sys.executable, "-m", "PyInstaller", "--noconfirm", str(SPEC)])
    target = DIST / APP_NAME
    if not target.exists():
        sys.exit(f"PyInstaller did not produce {target}")
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
