"""The release's version is one number, in three files that must agree.

``pyproject.toml`` carries a static version, ``__init__`` carries
``__version__``, and the Inno Setup script carries its own
``#define AppVersion`` -- which also NAMES the installer that is built,
so a stale one publishes an artifact whose filename is a claim about
contents it does not have.

``build.py`` refuses on a mismatch, and that refusal runs only in a
build. Measured in epy_reports on 2026-09-08: the release gate was
green -- ruff, the whole suite, housekeeper and pyright -- the tag was
pushed, and the installer pipeline was the first thing to say the
number had been bumped in one file out of two. A check the local gate
cannot run is a check that reports after the release.

The .iss is read here as ``utf-8-sig``: it carries a BOM on purpose,
because Inno reads a UTF-8 file without one in the machine's ANSI
codepage and the accented strings in it come out wrong.
"""

from __future__ import annotations

import re
from pathlib import Path

import epy_studio

ROOT = Path(__file__).resolve().parents[1]


def _match(rel: str, pattern: str, encoding: str = "utf-8") -> str:
    path = ROOT / rel
    found = re.search(pattern, path.read_text(encoding=encoding), re.M)
    assert found, f"{rel} declares no version"
    return found.group(1)


def test_every_file_that_declares_the_version_agrees() -> None:
    declared = {
        "__init__.py": epy_studio.__version__,
        "pyproject.toml": _match(
            "pyproject.toml", r'^version\s*=\s*"([^"]+)"'
        ),
        "epy_studio.iss": _match(
            "windows/epy_studio.iss",
            r'^#define\s+AppVersion\s+"([^"]+)"',
            encoding="utf-8-sig",
        ),
    }
    assert len(set(declared.values())) == 1, declared


def test_it_is_a_release_number() -> None:
    assert re.fullmatch(r"\d+\.\d+\.\d+", epy_studio.__version__)


def test_the_changelog_has_a_heading_for_it() -> None:
    # A tag whose changelog says "Unreleased" is a release nobody can
    # read the notes for.
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert f"## [{epy_studio.__version__}]" in changelog
