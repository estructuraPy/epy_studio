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
        "epy_outreach", "epy_lab",
        # The adopted ArtCraft Crafting Apps (MIT/Apache-2.0), in catalog
        # order, under their ePy FAMILY names; `binary` carries the upstream
        # stem the resolver actually looks for on disk.
        "epy_cadcraft", "epy_photocraft", "epy_lightcraft", "epy_filmcraft",
        "epy_vectorcraft", "epy_pdfcraft", "epy_deckcraft", "epy_gridcraft",
        "epy_soundcraft", "epy_wordcraft", "epy_designcraft",
        "epy_effectcraft",
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
PRIVATE = frozenset(
    {"epy_draft", "epy_quoting", "epy_outreach", "epy_lab"}
)


def test_an_application_is_optional_when_it_is_private_or_adopted() -> None:
    # Privacy is what decides whether a checkout may be ABSENT, so it is
    # what decides `optional`. epy_studio is public: a stranger who
    # clones it must be able to build the public editors, and before
    # this rule the build refused because ePy Draft was marked required
    # while its repository is private.
    #
    # An ADOPTED application is optional for the other reason: most
    # machines do not have it, and a missing one is not an incomplete
    # install -- so the row is absent, not greyed. The two reasons are
    # different and the same flag answers both.
    for app in _catalog.apps():
        adopted = app.ships == _catalog.SHIPS_INSTALLED
        expected = app.app_id in PRIVATE or adopted
        assert app.optional == expected, app.app_id


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
        assert app.register in _catalog.REGISTER_MODES
        assert app.ships in _catalog.SHIPS_MODES
        if not app.built_here:
            # The build-time columns are empty ON PURPOSE for an application
            # Studio does not build: there is nothing to collect assets for,
            # nothing to hide imports from, and no icon to give an executable
            # this repository never produces. Asserting them would demand
            # invented values, which is worse than a blank label.
            assert not app.asset_packages
            assert not app.hidden_imports
            assert not app.icon
            if app.ships == _catalog.SHIPS_INSTALLED:
                # Studio's INSTALLER installs it, so it NEEDS a component (the
                # .iss [Components] entry that draws its checkbox) and its
                # provenance. It has no Inno AppId of its own -- our installer
                # is what writes the uninstall key.
                assert app.component, f"{app.app_id} installs nothing"
                assert app.upstream, f"adopted {app.app_id} names no source"
                assert not app.own_install_appid, app.app_id
            else:
                # It supplies its own installer: no component OUR .iss draws,
                # and the AppId its own installer records is how we find it.
                assert not app.component
                assert app.own_install_appid, f"{app.app_id} cannot be found"
            continue
        assert app.component
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


def _unbuilt_ids() -> set[str]:
    """Every application Studio never builds, by id.

    The own-installer one (epy_lab) and the adopted ArtCraft ones are
    different KINDS of omission but the same build decision, and a
    hard-coded count in a test is what breaks the day another is adopted.
    """
    return {app.app_id for app in _catalog.apps() if not app.built_here}


def test_an_absent_optional_application_is_skipped_by_name(
    tmp_path: Path,
) -> None:
    # Said, never silent: a bundle missing an application looks identical
    # from the outside.
    suite = _suite_with(
        tmp_path, "epy_reports", "epy_slides", "epy_papers", "epy_draft"
    )  # every optional one but epy_quoting and epy_outreach
    built, skipped = _catalog.for_build(suite)
    assert [app.app_id for app in built] == [
        "epy_reports", "epy_slides", "epy_papers", "epy_draft",
    ]
    # Two kinds of omission, and they are DIFFERENT: epy_quoting and
    # epy_outreach are absent from this suite, while every application that
    # reaches the user by another route is never built here at all.
    absent = {line.split()[3].rstrip(":") for line in skipped
              if "SKIPPED optional" in line}
    assert absent == {"epy_quoting", "epy_outreach"}
    unbuilt = {line.split()[3].rstrip(":") for line in skipped
               if "NOT BUILT HERE" in line}
    assert unbuilt == _unbuilt_ids()
    assert "epy_lab" in unbuilt
    assert {"epy_cadcraft", "epy_photocraft"} <= unbuilt


def test_a_present_optional_application_is_built(tmp_path: Path) -> None:
    # The entry point's EXISTENCE is the switch.
    suite = _suite_with(
        tmp_path, "epy_reports", "epy_slides", "epy_papers", "epy_draft",
        "epy_quoting", "epy_outreach", "epy_lab",
    )
    built, skipped = _catalog.for_build(suite)
    assert [app.app_id for app in built][-1] == "epy_outreach"
    # epy_lab is present in the suite AND still not built: the switch for an
    # application that ships on its own is the catalog, not the file. Checking
    # the entry point would build it, because it has one.
    assert (suite / "epy_lab" / "src" / "epy_lab" / "__main__.py").is_file()
    assert "epy_lab" not in [app.app_id for app in built]
    assert len(skipped) == len(_unbuilt_ids())
    assert all("NOT BUILT HERE" in line for line in skipped)


def test_an_absent_required_application_refuses_the_build(
    tmp_path: Path,
) -> None:
    # The behaviour there always was, now naming the application. A
    # PUBLIC editor is not the owner's to hand out: a bundle without it
    # is a broken build, not a smaller one.
    suite = _suite_with(tmp_path, "epy_reports", "epy_slides")
    with pytest.raises(SystemExit, match="epy_papers"):
        _catalog.for_build(suite)


def test_install_dir_is_the_launchers_own_folder_when_frozen(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # Frozen, every tool shares the launcher executable's own folder --
    # the branch a source checkout (every other test in this file) never
    # takes, because building from source has no executables to share.
    import sys

    exe = tmp_path / "epy_studio.exe"
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(exe))
    assert _catalog.install_dir() == tmp_path


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
    assert len(skipped) == 3 + len(_unbuilt_ids())
    assert {"epy_draft", "epy_quoting", "epy_outreach"} == {
        line.split()[3].rstrip(":") for line in skipped
        if line.startswith("SKIPPED")
    }
    assert sum("NOT BUILT HERE" in line for line in skipped) == len(
        _unbuilt_ids())


# --- adopted (external) applications -----------------------------------


def _cadcraft() -> _catalog.App:
    return next(app for app in _catalog.apps() if app.app_id == "epy_cadcraft")


class TestTheAdoptedApplications:
    def test_the_three_non_osi_artcraft_projects_are_not_here(self) -> None:
        # artcraft (the flagship) and artcraft-services use a non-OSI
        # fair-source licence forbidding commercial resale and competing
        # products, and artcraftx carries no LICENSE file at all. Adapting
        # any of them into a redistributable bundle is the kind of claim
        # this repository refuses to ship.
        ids = {app.app_id for app in _catalog.apps()}
        assert "artcraft" not in ids
        assert "artcraft-services" not in ids
        assert "artcraftx" not in ids

    def test_an_adopted_entry_without_upstream_is_refused(
            self, monkeypatch, tmp_path):
        data = json.loads(_catalog.catalog_path().read_text(encoding="utf-8"))
        entry = next(
            item for item in data["apps"] if item["id"] == "epy_cadcraft")
        entry.pop("upstream")
        path = tmp_path / "apps.epyson"
        path.write_text(json.dumps(data), encoding="utf-8")
        monkeypatch.setattr(_catalog, "catalog_path", lambda: path)
        with pytest.raises(ValueError, match="needs upstream"):
            _catalog.apps()

    def test_every_adopted_entry_records_its_licence(self) -> None:
        adopted = [app for app in _catalog.apps()
                   if app.ships == _catalog.SHIPS_INSTALLED]
        assert adopted
        for app in adopted:
            assert app.upstream, app.app_id
            assert "MIT OR Apache-2.0" in app.upstream, app.app_id

    def test_the_env_var_name_is_the_documented_shape(self) -> None:
        assert _catalog.external_exe_env("cadcraft") == "EPY_CADCRAFT_EXE"


class TestFindingAnAdoptedApplication:
    @staticmethod
    def _no_env(monkeypatch) -> None:
        monkeypatch.delenv("EPY_CADCRAFT_EXE", raising=False)
        monkeypatch.setattr(_catalog.shutil, "which", lambda _name: None)

    def test_the_environment_variable_wins(self, monkeypatch, tmp_path):
        exe = tmp_path / "cadcraft.exe"
        exe.write_bytes(b"MZ")
        self._no_env(monkeypatch)
        monkeypatch.setenv("EPY_CADCRAFT_EXE", str(exe))
        assert _catalog.installed_exe(_cadcraft()) == exe

    def test_then_path(self, monkeypatch, tmp_path):
        exe = tmp_path / "cadcraft.exe"
        exe.write_bytes(b"MZ")
        self._no_env(monkeypatch)
        monkeypatch.setattr(
            _catalog.shutil, "which",
            lambda name: str(exe) if name == "cadcraft" else None)
        assert _catalog.installed_exe(_cadcraft()) == exe

    def test_then_the_conventional_folder(self, monkeypatch, tmp_path):
        self._no_env(monkeypatch)
        monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
        folder = tmp_path / "Programs" / "cadcraft"
        folder.mkdir(parents=True)
        exe = folder / "cadcraft.exe"
        exe.write_bytes(b"MZ")
        assert _catalog.installed_exe(_cadcraft()) == exe

    def test_an_absent_adopted_application_reads_as_not_installed(
            self, monkeypatch, tmp_path):
        # Absence is the NORMAL answer -- most machines do not have it -- so
        # it comes back as None rather than raising.
        self._no_env(monkeypatch)
        monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
        monkeypatch.delenv("PROGRAMFILES", raising=False)
        monkeypatch.delenv("PROGRAMFILES(X86)", raising=False)
        assert _catalog.installed_exe(_cadcraft()) is None

    def test_it_never_reads_the_registry(self, monkeypatch, tmp_path):
        # An adopted application was not installed by OUR installer, so there
        # is no Inno uninstall key to read -- reaching for one would ask the
        # registry a question it can never answer.
        self._no_env(monkeypatch)
        monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
        monkeypatch.setattr(
            _catalog, "_own_install_dirs",
            lambda _app: pytest.fail("an adopted app read the registry"))
        assert _catalog.installed_exe(_cadcraft()) is None


def _clear_cli_env(monkeypatch) -> None:
    """Unset every adopted CLI variable, so a machine's own state is inert."""
    for app in _catalog.apps():
        if app.ships == _catalog.SHIPS_INSTALLED:
            monkeypatch.delenv(
                _catalog.adopted_cli_env(app.exe_stem), raising=False)


class TestHandingTheCraftsToALaunchedApp:
    """The hint Studio passes to whatever it launches, so a drawing flow it
    starts can reach the adopted CLIs. A hint, never a dependency."""

    def test_the_cli_env_name_is_the_documented_shape(self) -> None:
        assert _catalog.adopted_cli_env("cadcraft") == "EPY_CADCRAFT_CLI"
        # A SEPARATE variable from the GUI executable's -- two executables.
        assert (
            _catalog.adopted_cli_env("cadcraft")
            != _catalog.external_exe_env("cadcraft")
        )

    def test_nothing_installed_is_an_empty_hint(self, monkeypatch) -> None:
        _clear_cli_env(monkeypatch)
        monkeypatch.setattr(_catalog.shutil, "which", lambda _n: None)
        monkeypatch.setattr(_catalog, "installed_exe", lambda _app: None)
        assert _catalog.craft_env() == {}

    def test_the_named_cli_is_used(self, monkeypatch, tmp_path) -> None:
        cli = tmp_path / "cadcraft-cli.exe"
        cli.write_bytes(b"MZ")
        _clear_cli_env(monkeypatch)
        monkeypatch.setattr(_catalog.shutil, "which", lambda _n: None)
        monkeypatch.setattr(_catalog, "installed_exe", lambda _app: None)
        monkeypatch.setenv(_catalog.adopted_cli_env("cadcraft"), str(cli))
        assert _catalog.craft_env() == {"EPY_CADCRAFT_CLI": str(cli)}

    def test_the_cli_is_found_on_path(self, monkeypatch, tmp_path) -> None:
        cli = tmp_path / "cadcraft-cli"
        cli.write_bytes(b"MZ")
        _clear_cli_env(monkeypatch)
        monkeypatch.setattr(_catalog, "installed_exe", lambda _app: None)
        monkeypatch.setattr(
            _catalog.shutil, "which",
            lambda name: str(cli) if name == "cadcraft-cli" else None)
        assert _catalog.craft_env() == {"EPY_CADCRAFT_CLI": str(cli)}

    def test_the_cli_is_found_beside_the_gui_executable(
            self, monkeypatch, tmp_path) -> None:
        exe = tmp_path / "cadcraft.exe"
        exe.write_bytes(b"MZ")
        cli = tmp_path / "cadcraft-cli.exe"
        cli.write_bytes(b"MZ")
        _clear_cli_env(monkeypatch)
        monkeypatch.setattr(_catalog.shutil, "which", lambda _n: None)
        monkeypatch.setattr(
            _catalog, "installed_exe",
            lambda app: exe if app.app_id == "epy_cadcraft" else None)
        assert _catalog.craft_env() == {"EPY_CADCRAFT_CLI": str(cli)}

    def test_only_adopted_apps_get_a_cli_variable(
            self, monkeypatch, tmp_path) -> None:
        cli = tmp_path / "cadcraft-cli"
        cli.write_bytes(b"MZ")
        _clear_cli_env(monkeypatch)
        monkeypatch.setattr(_catalog, "installed_exe", lambda _app: None)
        monkeypatch.setattr(
            _catalog.shutil, "which",
            lambda name: str(cli) if name == "cadcraft-cli" else None)
        # No ePy editor, no sibling library: only the adopted tools.
        assert set(_catalog.craft_env()) == {"EPY_CADCRAFT_CLI"}


# ------------------------------------------------ the adopted download page


def _adopted(**extra) -> _catalog.App:
    """One adopted catalog entry, with the required upstream filled in."""
    fields = {
        "app_id": "cadcraft",
        "display": "ePy CAD",
        "description": "",
        "component": "",
        "register": "none",
        "ships": _catalog.SHIPS_INSTALLED,
        "upstream": "github.com/storytold/cadcraft — MIT OR Apache-2.0",
    }
    fields.update(extra)
    return _catalog.App(**fields)


def test_the_download_page_comes_from_the_upstream_repository() -> None:
    # Studio never ships an adopted application, so "install" means the
    # user fetches it from its own project. The page is derived from the
    # provenance the entry is REQUIRED to carry -- never invented.
    assert _catalog.download_page(_adopted()) == (
        "https://github.com/storytold/cadcraft/releases"
    )


def test_an_explicit_install_page_wins_over_the_derived_one() -> None:
    assert _catalog.download_page(
        _adopted(install_page="https://getartcraft.com/cadcraft")
    ) == "https://getartcraft.com/cadcraft"


def test_an_upstream_with_no_github_repository_has_no_page() -> None:
    # Nothing to derive and nothing declared: no link, rather than a
    # guessed one.
    assert _catalog.download_page(
        _adopted(upstream="example.org/x — MIT")
    ) == ""
