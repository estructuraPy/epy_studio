"""The page where a person chooses which tools to install.

The installer offers every application as its own component, so a
machine can take three of them and not the fourth. That choice is only
real if three things hold, and each fails quietly on its own: every
application in the catalogue has a component, every component's name is
translated into both languages the installer speaks, and the file Inno
reads is decoded the way it was written.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ISS = ROOT / "windows" / "epy_studio.iss"
CATALOG = ROOT / "src" / "epy_studio" / "_config" / "apps.epyson"

LANGUAGES = ("english", "spanish")


def _script() -> str:
    return ISS.read_text(encoding="utf-8-sig")


def _apps() -> list[dict[str, str]]:
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    return [
        {"id": str(app["id"]), "component": str(app["component"])}
        for app in data["apps"]
    ]


def _messages() -> dict[str, set[str]]:
    """Return the custom message names defined for each language."""
    found: dict[str, set[str]] = {name: set() for name in LANGUAGES}
    block = _script().split("[CustomMessages]", 1)[1].split("\n[", 1)[0]
    for line in block.splitlines():
        match = re.match(r"(\w+)\.(\w+)=", line.strip())
        if match and match.group(1) in found:
            found[match.group(1)].add(match.group(2))
    return found


def test_every_application_is_its_own_component() -> None:
    # Otherwise two tools share one checkbox and nobody can take one
    # without the other.
    script = _script()
    components = set(re.findall(r'^Name: "(\w+)"; Description:', script, re.M))
    assert {app["component"] for app in _apps()} <= components


def test_the_installer_offers_a_choice_at_all() -> None:
    # A custom type is what turns the components page from a list into a
    # choice: without it the page shows what will be installed and the
    # boxes cannot be changed.
    script = _script()
    assert "[Types]" in script
    assert "Flags: iscustom" in script
    # And nothing may suppress the page a person chooses on.
    assert "DisableReadyPage" not in script
    assert "DisableWelcomePage" not in script


def test_every_name_on_that_page_is_translated() -> None:
    # The one page that must not be half translated. Inno translates its
    # own chrome from the .isl file; these strings are ours.
    script = _script()
    used = set(re.findall(r"\{cm:(\w+)\}", script))
    offered = {name for name in used if name.startswith(("Comp", "Type"))}
    assert offered, "the components page carries no translated name"
    defined = _messages()
    for language in LANGUAGES:
        missing = offered - defined[language]
        assert not missing, f"{language} is missing {sorted(missing)}"


def test_no_component_name_is_a_bare_literal() -> None:
    # A literal is a name that cannot be translated, and it reads as
    # English inside a Spanish window without anything saying so.
    for line in _script().splitlines():
        if line.startswith("Name: ") and "Description:" in line:
            assert "{cm:" in line, line


def test_the_script_says_how_to_decode_it() -> None:
    # It carries em dashes. Inno reads a file with no byte-order mark in
    # the machine's ANSI codepage, so without one the names on the
    # choosing page are decoded by luck -- correctly on the machine that
    # wrote them and as mojibake on somebody else's.
    raw = ISS.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf"), "no UTF-8 byte-order mark"
    assert any(byte > 127 for byte in raw), "nothing that needs it"


def test_the_shared_runtime_is_never_optional() -> None:
    # Every component installs one executable; they all share one
    # _internal. A component that could switch the runtime off would
    # leave the others unable to start.
    for line in _script().splitlines():
        if line.startswith('Source: "{#DistDir}\\_internal'):
            assert "Components:" not in line, line
