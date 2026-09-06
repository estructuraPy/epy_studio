"""The application catalog, and what it is allowed to say."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from epy_studio._core import _catalog

# What the PyInstaller spec carried IN CODE for each application before
# the lists moved into the catalog. Frozen here so the move can be shown
# to have changed nothing: a bundle built from the data must be the
# bundle that was built from the code.
SPEC_LISTS_BEFORE_THE_MOVE = {
    "epy_reports": (
        (
            "branding", "themes", "reference_docx", "mathjax", "csl",
            "mermaid", "nomnoml",
        ),
        (),
    ),
    "epy_slides": (
        (
            "branding", "themes", "reference_pptx", "mathjax", "revealjs",
            "mermaid", "nomnoml",
        ),
        (),
    ),
    "epy_papers": (
        ("branding", "themes", "mathjax", "csl", "mermaid", "nomnoml"),
        (),
    ),
    "epy_draft": (
        ("branding", "prompts"),
        (
            "keyring.backends", "keyring.backends.Windows",
            "keyring.backends.SecretService", "keyring.backends.chainer",
            "keyring.backends.fail", "yaml", "pypdf",
        ),
    ),
}


def test_every_shipped_application_is_listed() -> None:
    ids = [app.app_id for app in _catalog.apps()]
    assert ids == [
        "epy_reports", "epy_slides", "epy_papers", "epy_draft", "epy_quoting",
    ]


def test_draft_advertises_open_with_and_never_claims_the_default() -> None:
    # The rule lived as a prose comment in the installer script, which
    # is exactly what gets lost when a fifth application is added. ePy
    # Draft consumes Markdown and text as batch INPUT and authors
    # neither, so claiming the default would hand it documents it does
    # not edit.
    by_id = {app.app_id: app for app in _catalog.apps()}
    assert not by_id["epy_draft"].claims_default
    assert by_id["epy_reports"].claims_default


# The applications whose repositories are PRIVATE. Kept as a literal
# rather than derived, because the fact lives on GitHub and a test that
# asked the network would answer differently offline.
PRIVATE = frozenset({"epy_draft", "epy_quoting"})


def test_an_application_is_optional_exactly_when_it_is_private() -> None:
    # Privacy is what decides whether a checkout may be ABSENT, so it is
    # what decides `optional`. epy_studio is public: a stranger who
    # clones it must be able to build the public editors, and before
    # this rule the build refused because ePy Draft was marked required
    # while its repository is private.
    for app in _catalog.apps():
        assert app.optional == (app.app_id in PRIVATE), app.app_id


def test_optional_and_register_are_independent_axes() -> None:
    # ePy Draft is optional AND registers document types; ePy Quoting is
    # optional and registers none. Collapsing the two into one flag
    # would have left Draft's [Run] lines unguarded, which is the case
    # that breaks the installer on a machine without its executable.
    by_id = {app.app_id: app for app in _catalog.apps()}
    assert by_id["epy_draft"].optional and by_id["epy_draft"].registers
    assert by_id["epy_quoting"].optional
    assert not by_id["epy_quoting"].registers
    assert by_id["epy_reports"].registers
    assert not by_id["epy_reports"].optional
    # No application claims the default except the ones that author the
    # type: ePy Draft consumes Markdown as batch input and authors none.
    assert not by_id["epy_draft"].claims_default


def test_the_build_lists_match_what_the_spec_carried() -> None:
    # The lists moved from code to data. A dropped asset package is a
    # loader that raises on first use; a dropped hidden import is an
    # ImportError on the user's machine. Neither shows at build time.
    by_id = {app.app_id: app for app in _catalog.apps()}
    for app_id, (assets, hidden) in SPEC_LISTS_BEFORE_THE_MOVE.items():
        assert by_id[app_id].asset_packages == assets, app_id
        assert by_id[app_id].hidden_imports == hidden, app_id
        assert by_id[app_id].icon.endswith(f"{app_id}.ico")


def test_every_entry_is_complete() -> None:
    # A half-filled entry produces a row with a blank label rather than
    # an error, which is the kind of thing nobody notices in a picker.
    for app in _catalog.apps():
        assert app.app_id and app.display and app.description
        assert app.component
        assert app.register in _catalog.REGISTER_MODES
        assert app.asset_packages, f"{app.app_id} bundles no assets"
        assert app.icon


def test_an_unknown_register_mode_is_refused(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    data = json.loads(_catalog.catalog_path().read_text(encoding="utf-8"))
    data["apps"][0]["register"] = "sometimes"
    bad = tmp_path / "apps.epyson"
    bad.write_text(json.dumps(data), encoding="utf-8")
    monkeypatch.setattr(_catalog, "catalog_path", lambda: bad)
    with pytest.raises(ValueError, match="sometimes"):
        _catalog.apps()


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


# --- what the build may carry ------------------------------------------


def _suite_with(tmp_path: Path, *present: str) -> Path:
    """Return a fake suite root holding an entry point for each name."""
    for app_id in present:
        script = tmp_path / app_id / "src" / app_id / "__main__.py"
        script.parent.mkdir(parents=True)
        script.write_text("", encoding="utf-8")
    return tmp_path


def test_an_absent_optional_application_is_skipped_by_name(
    tmp_path: Path,
) -> None:
    # Said, never silent: a bundle missing an application looks identical
    # from the outside.
    suite = _suite_with(
        tmp_path, "epy_reports", "epy_slides", "epy_papers", "epy_draft"
    )  # every optional one but epy_quoting
    built, skipped = _catalog.for_build(suite)
    assert [app.app_id for app in built] == [
        "epy_reports", "epy_slides", "epy_papers", "epy_draft",
    ]
    assert len(skipped) == 1
    assert "epy_quoting" in skipped[0]
    assert "SKIPPED optional" in skipped[0]


def test_a_present_optional_application_is_built(tmp_path: Path) -> None:
    # The entry point's EXISTENCE is the switch.
    suite = _suite_with(
        tmp_path, "epy_reports", "epy_slides", "epy_papers", "epy_draft",
        "epy_quoting",
    )
    built, skipped = _catalog.for_build(suite)
    assert [app.app_id for app in built][-1] == "epy_quoting"
    assert skipped == []


def test_an_absent_required_application_refuses_the_build(
    tmp_path: Path,
) -> None:
    # The behaviour there always was, now naming the application. A
    # PUBLIC editor is not the owner's to hand out: a bundle without it
    # is a broken build, not a smaller one.
    suite = _suite_with(tmp_path, "epy_reports", "epy_slides")
    with pytest.raises(SystemExit, match="epy_papers"):
        _catalog.for_build(suite)


def test_the_public_editors_alone_are_a_buildable_bundle(
    tmp_path: Path,
) -> None:
    # What a stranger who clones the PUBLIC repository has. Before the
    # privacy rule this refused, because ePy Draft was required and its
    # repository is private.
    suite = _suite_with(tmp_path, "epy_reports", "epy_slides", "epy_papers")
    built, skipped = _catalog.for_build(suite)
    assert [app.app_id for app in built] == [
        "epy_reports", "epy_slides", "epy_papers",
    ]
    assert len(skipped) == 2
    assert {"epy_draft", "epy_quoting"} == {
        line.split()[3].rstrip(":") for line in skipped
    }
