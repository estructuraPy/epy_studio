"""The application catalog, and what it is allowed to say."""

from __future__ import annotations

import json

from epy_studio._core import _catalog


def test_every_shipped_application_is_listed() -> None:
    ids = [app.app_id for app in _catalog.apps()]
    assert ids == ["epy_reports", "epy_slides", "epy_papers", "epy_craft"]


def test_craft_advertises_open_with_and_never_claims_the_default() -> None:
    # The rule lived as a prose comment in the installer script, which
    # is exactly what gets lost when a fifth application is added. ePy
    # Craft consumes Markdown and text as batch INPUT and authors
    # neither, so claiming the default would hand it documents it does
    # not edit.
    by_id = {app.app_id: app for app in _catalog.apps()}
    assert not by_id["epy_craft"].claims_default
    assert by_id["epy_reports"].claims_default


def test_every_entry_is_complete() -> None:
    # A half-filled entry produces a row with a blank label rather than
    # an error, which is the kind of thing nobody notices in a picker.
    for app in _catalog.apps():
        assert app.app_id and app.display and app.description
        assert app.component
        assert app.register in {"default", "openwith"}


def test_the_catalog_is_rule_13_shaped() -> None:
    data = json.loads(_catalog.catalog_path().read_text(encoding="utf-8"))
    assert data["config_id"] == _catalog.catalog_path().stem
    assert data["version"].count(".") == 2
    assert len(data["description"]) >= 20
    assert data["audit_status"]


def test_a_missing_catalog_is_loud(monkeypatch, tmp_path) -> None:
    # Raised rather than defaulted. A spec that walks _config too
    # narrowly has silently dropped catalogs before -- all five of one
    # application's, whose loader then raised on first use. An empty
    # selector looks like "nothing is installed", which sends the reader
    # to the installer instead of to the build.
    monkeypatch.setattr(
        _catalog, "catalog_path", lambda: tmp_path / "absent.epyson"
    )
    try:
        _catalog.apps()
    except FileNotFoundError as error:
        assert "catalog" in str(error)
    else:  # pragma: no cover - the assertion above is the point
        raise AssertionError("a missing catalog passed silently")
