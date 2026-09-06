"""A release cannot quietly ship fewer applications than it promised.

The build is deliberately permissive: an OPTIONAL application is
optional because its repository is private, so a checkout without it is
a normal checkout and the build says so and carries on. The release is
where that permissiveness becomes dangerous, because a short bundle is
indistinguishable from a complete one once it is an installer.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "windows" / "build_support"))
import verify_release  # noqa: E402 - build_support, on sys.path above


def _built(tmp_path: Path, *app_ids: str) -> Path:
    """Return a fake dist folder holding an executable for each name."""
    target = tmp_path / "epy_studio"
    target.mkdir()
    for app_id in app_ids:
        (target / f"{app_id}.exe").write_bytes(b"MZ")
    return target


def test_the_manifest_promises_what_the_catalog_can_carry() -> None:
    # A promise the catalog cannot honour is a typo, and a typo here
    # would promise nothing at all.
    ids = verify_release.promised()
    known = {
        str(app["id"])
        for app in json.loads(
            verify_release.CATALOG.read_text(encoding="utf-8")
        )["apps"]
    }
    assert ids, "the manifest promises nothing"
    assert set(ids) <= known


def test_the_current_promise_includes_the_private_editor() -> None:
    # ePy Draft is optional to the BUILD, because its repository is
    # private, and promised by this RELEASE. Those are the two different
    # questions the manifest exists to keep apart.
    assert "epy_draft" in verify_release.promised()


def test_a_complete_bundle_passes(tmp_path: Path, capsys) -> None:
    target = _built(tmp_path, *verify_release.promised())
    assert verify_release.main(["--target", str(target)]) == 0
    assert "promise kept" in capsys.readouterr().out


def test_a_bundle_short_of_a_promised_application_is_refused(
    tmp_path: Path, capsys
) -> None:
    # The defect this exists to catch: the sibling checkout was not
    # there that day, the build printed one SKIP line nobody read, and
    # the installer went out three applications short.
    promised = verify_release.promised()
    target = _built(tmp_path, *promised[:-1])
    assert verify_release.main(["--target", str(target)]) == 1
    out = capsys.readouterr().out
    assert f"{promised[-1]}.exe" in out
    assert "release.epyson" in out


def test_an_unbuilt_bundle_is_refused(tmp_path: Path) -> None:
    assert verify_release.main(["--target", str(tmp_path / "absent")]) == 1


def test_an_unknown_id_in_the_manifest_is_refused(tmp_path: Path) -> None:
    bad = tmp_path / "release.epyson"
    bad.write_text(
        json.dumps({"must_carry": ["epy_reports", "epy_nope"]}),
        encoding="utf-8",
    )
    with pytest.raises(SystemExit, match="epy_nope"):
        verify_release.promised(bad)


def test_a_missing_manifest_is_loud(tmp_path: Path) -> None:
    # Raised rather than defaulted to "promise nothing", which would
    # make the check pass on every bundle including an empty one.
    with pytest.raises(SystemExit, match="no release manifest"):
        verify_release.promised(tmp_path / "absent.epyson")


def test_the_manifest_is_rule_13_shaped() -> None:
    data = json.loads(verify_release.MANIFEST.read_text(encoding="utf-8"))
    assert data["config_id"] == verify_release.MANIFEST.stem
    assert data["version"].count(".") == 2
    assert len(data["description"]) >= 20
    assert data["audit_status"]
