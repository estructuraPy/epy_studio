"""build.py refuses a bundle whose installer script would lie.

The installer script cannot read the catalog, so it keeps its own copy
and ``build.py`` checks the two agree. An OPTIONAL application adds a
second thing to check: its lines must sit inside ``#ifexist`` blocks
naming its executable, and nowhere else -- one unguarded line is enough
for ISCC to refuse to compile the day the executable is not there,
which is the whole case an optional application exists for.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import build  # noqa: E402 - the repository root, on sys.path above


def _tree(tmp_path: Path) -> Path:
    """Copy the three files _verify_manifest reads into a scratch root."""
    for rel in (
        "src/epy_studio/_config/apps.epyson",
        "src/epy_studio/__init__.py",
        "windows/epy_studio.iss",
    ):
        target = tmp_path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / rel, target)
    return tmp_path


def test_the_real_installer_script_agrees_with_the_catalog(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(build, "ROOT", _tree(tmp_path))
    build._verify_manifest()


def test_every_optional_application_is_guarded_and_no_required_one_is(
) -> None:
    # Stated structurally rather than by name, so it keeps holding as
    # applications are added in either direction. An optional
    # application's every line sits inside an #ifexist naming its own
    # executable; a required one's lines sit in the open, because a
    # build without it is a broken build and ISCC should say so.
    iss = (ROOT / "windows" / "epy_studio.iss").read_text(encoding="utf-8")
    guards = list(build._GUARD.finditer(iss))
    assert guards, "no #ifexist block at all"
    # An application Studio does not BUILD is not guarded, because the
    # installer does not name it at all: there is nothing to guard.
    unbuilt = build._own_installer_ids()
    optional = build._optional_ids() - unbuilt
    guarded_exes = {match.group("exe") for match in guards}
    assert guarded_exes == {f"{app_id}.exe" for app_id in optional}

    outside = build._GUARD.sub("", iss)
    for app in build._catalog_apps():
        app_id, component = str(app["id"]), str(app["component"])
        exe = f"{app_id}.exe"
        if app_id in unbuilt:
            assert exe not in iss, f"{exe} is not built and the .iss names it"
            continue
        if app_id in optional:
            assert exe not in outside, f"{exe} names itself outside a guard"
            assert f"Components: {component}" not in outside, component
            assert f'Name: "{component}"' not in outside, component
        else:
            assert exe in outside, f"{exe} is required but only guarded"


def test_a_guard_body_names_the_application_it_guards() -> None:
    # A guard that wraps the wrong lines would compile and install the
    # wrong thing. The [Components] block carries only the component
    # name; every other block carries the executable.
    iss = (ROOT / "windows" / "epy_studio.iss").read_text(encoding="utf-8")
    by_exe = {
        f"{app['id']}.exe": str(app["component"])
        for app in build._catalog_apps()
    }
    for match in build._GUARD.finditer(iss):
        exe = match.group("exe")
        body = match.group("body")
        component = by_exe[exe]
        assert exe in body or f'Name: "{component}"' in body, body


def test_an_optional_line_outside_its_guard_refuses_the_build(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The defect this exists to catch: someone adds the fifth
    # application's Source line the way the other four are written,
    # and the installer compiles on this machine -- where the exe
    # exists -- and refuses on the next, where it does not.
    root = _tree(tmp_path)
    iss = root / "windows" / "epy_studio.iss"
    text = iss.read_text(encoding="utf-8")
    text += (
        '\nSource: "{#DistDir}\\epy_quoting.exe"; DestDir: "{app}"; '
        'Flags: ignoreversion; Components: quoting\n'
    )
    iss.write_text(text, encoding="utf-8")
    monkeypatch.setattr(build, "ROOT", root)
    with pytest.raises(SystemExit, match="epy_quoting"):
        build._verify_manifest()


def test_an_optional_application_with_no_guard_refuses_the_build(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _tree(tmp_path)
    iss = root / "windows" / "epy_studio.iss"
    text = iss.read_text(encoding="utf-8")
    stripped = build._GUARD.sub("", text)
    assert stripped != text
    iss.write_text(stripped, encoding="utf-8")
    monkeypatch.setattr(build, "ROOT", root)
    with pytest.raises(SystemExit, match="epy_quoting"):
        build._verify_manifest()


def test_an_optional_component_with_no_exe_line_refuses_the_build(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The component is declared inside its guard and its Source line is
    # not: the installer would offer a component that installs nothing.
    # Isolated from the no-guard case above, which the component check
    # refuses before this one gets a turn.
    root = _tree(tmp_path)
    iss = root / "windows" / "epy_studio.iss"
    text = iss.read_text(encoding="utf-8")
    kept = build._GUARD.sub(
        lambda m: "" if "epy_quoting.exe" in m.group("body") else m.group(0),
        text,
    )
    assert kept != text
    assert 'Name: "quoting"' in kept
    iss.write_text(kept, encoding="utf-8")
    monkeypatch.setattr(build, "ROOT", root)
    with pytest.raises(SystemExit, match="epy_quoting.exe"):
        build._verify_manifest()


def test_a_required_application_missing_from_the_script_still_refuses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The contract that was always there.
    root = _tree(tmp_path)
    iss = root / "windows" / "epy_studio.iss"
    text = iss.read_text(encoding="utf-8")
    text = text.replace("epy_papers.exe", "epy_nope.exe")
    iss.write_text(text, encoding="utf-8")
    monkeypatch.setattr(build, "ROOT", root)
    with pytest.raises(SystemExit, match="epy_papers"):
        build._verify_manifest()


def test_the_optional_ids_come_from_the_catalog() -> None:
    # The private applications, plus the adopted ArtCraft ones: both may be
    # absent from a bundle -- the first because its checkout may be missing,
    # the second because it is a foreign program Studio never builds.
    adopted = frozenset(
        str(app["id"]) for app in build._catalog_apps()
        if app.get("ships") == "external"
    )
    private = frozenset(
        {"epy_draft", "epy_quoting", "epy_outreach", "epy_lab"}
    )
    assert build._optional_ids() == private | adopted
    # A separate axis: everything Studio OFFERS but never builds -- epy_lab
    # supplies itself, the adopted ones come from upstream.
    assert build._own_installer_ids() == frozenset({"epy_lab"}) | adopted


def test_the_adopted_applications_are_absent_from_the_installer() -> None:
    # An adopted app is one Studio never installs, so the Inno script -- which
    # cannot read JSON -- must NOT name its executable: a stray line would try
    # to copy a binary this build never produces. Checked in the negative for
    # every adopted row, against the REAL script.
    adopted = [
        str(app["id"]) for app in build._catalog_apps()
        if app.get("ships") == "external"
    ]
    assert adopted
    iss = (build.ROOT / "windows" / "epy_studio.iss").read_text(
        encoding="utf-8", errors="replace")
    for app_id in adopted:
        assert f"{app_id}.exe" not in iss, app_id


def test_the_real_manifest_still_agrees() -> None:
    # The catalog gained twelve adopted rows this session; the installer
    # contract must still hold. This runs the SAME refusal the build runs, so a
    # drift between the catalog and the .iss fails here and not at ship time.
    build._verify_manifest()
