"""An application Studio OFFERS without BUILDING.

ePy Lab is the first. It is a front end over the design libraries
rather than a self-contained editor: its own PyInstaller spec collects
eighteen packages -- itself plus epy_analysis, epy_plotter, epy_units
and fourteen design libraries -- together with the openseespy and
Pynite engines. Studio's ``_app_analysis`` gives each application
``pathex=[its own src]`` and one ``_config`` tree, and the bundle
already stands at 6.7 GB, so bundling that one would mean teaching the
spec to carry a dependency closure.

So it keeps its own installer and its own folder. ``ships`` is a third axis,
independent of ``optional`` and ``register``: ``optional`` says the sibling
checkout may be absent when Studio is BUILT, ``ships`` says Studio never builds
the application at all.

Author: Ing. Angel Navarro-Mora M.Sc.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from epy_studio._core import _catalog
from epy_studio._core._catalog import (
    SHIPS_OWN_INSTALLER,
    SHIPS_WITH_STUDIO,
    App,
    apps,
    installed_exe,
)


def _lab() -> App:
    return next(app for app in apps() if app.app_id == "epy_lab")


def _own(ships: str = SHIPS_OWN_INSTALLER, appid: str = "{GUID}") -> App:
    return App(app_id="probe", display="Probe", description="d", component="",
               register="none", optional=True, ships=ships,
               own_install_appid=appid)


_LAB_GUID = "{3C1F6B2E-9A74-4E0D-8B5A-6F2D1C0E7A91}"
_LAB_KEY = (r"Software\Microsoft\Windows\CurrentVersion\Uninstall"
            rf"\{_LAB_GUID}_is1")


class _FakeWinreg:
    """Just the four names :func:`_uninstall_location` uses.

    ``HKEY_CURRENT_USER`` and ``HKEY_LOCAL_MACHINE`` are 0 and 1 here, so a
    fixture keys its entries by ``(hive, key)`` and a lookup in the wrong
    hive misses the way a real one would.
    """

    HKEY_CURRENT_USER = 0
    HKEY_LOCAL_MACHINE = 1

    def __init__(self, entries: dict[tuple[int, str], str]) -> None:
        self._entries = entries

    def OpenKey(self, root, key):  # noqa: N802 - winreg's own spelling
        if (root, key) not in self._entries:
            raise OSError(2, "no such key")
        return _FakeKey(self._entries[(root, key)])

    @staticmethod
    def QueryValueEx(handle, name):  # noqa: N802 - winreg's own spelling
        if name != "InstallLocation":
            raise OSError(2, "no such value")
        return handle.value, 1


class _FakeKey:
    """A context manager, because the real key is used as one."""

    def __init__(self, value: str) -> None:
        self.value = value

    def __enter__(self) -> _FakeKey:
        return self

    def __exit__(self, *_exc: object) -> bool:
        return False


class TestTheAxesAreIndependent:
    def test_the_lab_is_optional_registers_nothing_and_is_not_built_here(self):
        lab = _lab()
        assert lab.optional
        assert not lab.registers
        assert not lab.built_here
        assert lab.ships == SHIPS_OWN_INSTALLER

    def test_every_other_application_is_built_here(self):
        """The default: adding one does not silently opt out."""
        others = [app for app in apps() if app.app_id != "epy_lab"]
        assert others
        assert all(app.built_here for app in others)
        assert all(app.ships == SHIPS_WITH_STUDIO for app in others)

    def test_an_optional_application_is_not_therefore_unbuilt(self):
        """ePy Draft and ePy Quoting are optional AND built here."""
        by_id = {app.app_id: app for app in apps()}
        assert by_id["epy_draft"].optional and by_id["epy_draft"].built_here
        quoting = by_id["epy_quoting"]
        assert quoting.optional and quoting.built_here


class TestTheCatalogueRefusesAnIncompleteEntry:
    @staticmethod
    def _with(monkeypatch, tmp_path, **changes) -> None:
        data = json.loads(_catalog.catalog_path().read_text(encoding="utf-8"))
        data["apps"][-1].update(changes)
        path = tmp_path / "apps.epyson"
        path.write_text(json.dumps(data), encoding="utf-8")
        monkeypatch.setattr(_catalog, "catalog_path", lambda: path)

    def test_an_unknown_ships_mode_is_refused_rather_than_defaulted(
            self, monkeypatch, tmp_path):
        """Defaulting would put an application into the build that was
        meant to stay out -- the opposite of the safe direction."""
        self._with(monkeypatch, tmp_path, ships="someday")
        with pytest.raises(ValueError, match="ships is 'someday'"):
            _catalog.apps()

    def test_shipping_on_its_own_without_an_appid_is_refused(
            self, monkeypatch, tmp_path):
        """Without it the selector can only guess at the default folder,
        and an application installed elsewhere reads as not installed."""
        self._with(monkeypatch, tmp_path, own_install_appid="")
        with pytest.raises(ValueError, match="needs own_install_appid"):
            _catalog.apps()

    def test_an_absent_ships_key_means_studio_builds_it(
            self, monkeypatch, tmp_path):
        """The five that were here before this axis existed carry no key."""
        data = json.loads(_catalog.catalog_path().read_text(encoding="utf-8"))
        entry = data["apps"][-1]
        entry.pop("ships")
        entry.pop("own_install_appid")
        path = tmp_path / "apps.epyson"
        path.write_text(json.dumps(data), encoding="utf-8")
        monkeypatch.setattr(_catalog, "catalog_path", lambda: path)
        assert _catalog.apps()[-1].built_here


class TestItIsSkippedByNameAtBuildTime:
    @staticmethod
    def _suite(tmp_path: Path, *ids: str) -> Path:
        for app_id in ids:
            script = tmp_path / app_id / "src" / app_id / "__main__.py"
            script.parent.mkdir(parents=True)
            script.write_text("", encoding="utf-8")
        return tmp_path

    def test_the_catalogue_decides_and_not_the_file(self, tmp_path):
        """Its entry point EXISTS -- checking the file would build it.

        For every other application the file's existence is the
        switch, so this is the one case where the rule had to change
        rather than be reused.
        """
        suite = self._suite(tmp_path, "epy_reports", "epy_slides",
                            "epy_papers", "epy_lab")
        entry = suite / "epy_lab" / "src" / "epy_lab" / "__main__.py"
        assert entry.is_file()
        built, skipped = _catalog.for_build(suite)
        assert "epy_lab" not in [app.app_id for app in built]
        assert any("NOT BUILT HERE" in line and "epy_lab" in line
                   for line in skipped)

    def test_the_line_says_which_kind_of_omission_it_is(self, tmp_path):
        """Two reasons an application can be missing from a bundle,
        and a reader has to be able to tell them apart."""
        suite = self._suite(tmp_path, "epy_reports", "epy_slides",
                            "epy_papers", "epy_lab")
        _built, skipped = _catalog.for_build(suite)
        unbuilt = [line for line in skipped if "NOT BUILT HERE" in line]
        absent = [line for line in skipped if "SKIPPED optional" in line]
        assert len(unbuilt) == 1
        assert "own installer" in unbuilt[0]
        assert {"epy_draft", "epy_quoting"} == {
            line.split()[3].rstrip(":") for line in absent}

    def test_it_never_refuses_the_build(self, tmp_path):
        """A required application's absence refuses; this one's never does."""
        suite = self._suite(tmp_path, "epy_reports", "epy_slides",
                            "epy_papers")
        built, _skipped = _catalog.for_build(suite)
        assert [app.app_id for app in built] == [
            "epy_reports", "epy_slides", "epy_papers"]


class TestFindingAnApplicationThatInstalledItself:
    def test_a_built_application_is_looked_for_beside_the_launcher(
            self, monkeypatch, tmp_path):
        monkeypatch.setattr(_catalog, "install_dir", lambda: tmp_path)
        reports = next(app for app in apps() if app.app_id == "epy_reports")
        assert installed_exe(reports) is None
        (tmp_path / "epy_reports.exe").write_bytes(b"MZ")
        assert installed_exe(reports) == tmp_path / "epy_reports.exe"

    def test_the_declared_default_folder_is_the_second_route(
            self, monkeypatch, tmp_path):
        """``{localappdata}\\Programs\\epy_lab``, its declared default."""
        monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
        monkeypatch.setattr(_catalog, "_uninstall_location", lambda _a: None)
        lab = _lab()
        assert installed_exe(lab) is None
        own = tmp_path / "Programs" / "epy_lab"
        own.mkdir(parents=True)
        (own / "epy_lab.exe").write_bytes(b"MZ")
        assert installed_exe(lab) == own / "epy_lab.exe"

    def test_the_recorded_location_wins_over_the_default(
            self, monkeypatch, tmp_path):
        """The user may have chosen another folder during setup, so the
        folder is READ and not assumed."""
        chosen = tmp_path / "elsewhere"
        chosen.mkdir()
        (chosen / "epy_lab.exe").write_bytes(b"MZ")
        default = tmp_path / "Programs" / "epy_lab"
        default.mkdir(parents=True)
        (default / "epy_lab.exe").write_bytes(b"MZ")
        monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
        monkeypatch.setattr(_catalog, "_uninstall_location", lambda _a: chosen)
        assert installed_exe(_lab()) == chosen / "epy_lab.exe"

    def test_a_recorded_location_that_holds_nothing_falls_through(
            self, monkeypatch, tmp_path):
        """A stale uninstall key is not a reason to report it installed."""
        stale = tmp_path / "gone"
        stale.mkdir()
        monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
        monkeypatch.setattr(_catalog, "_uninstall_location", lambda _a: stale)
        assert installed_exe(_lab()) is None

    def test_no_localappdata_is_not_a_crash(self, monkeypatch):
        monkeypatch.delenv("LOCALAPPDATA", raising=False)
        monkeypatch.setattr(_catalog, "_uninstall_location", lambda _a: None)
        assert installed_exe(_lab()) is None
        assert _catalog._own_install_dirs(_own()) == ()


class TestReadingTheUninstallKey:
    def test_an_empty_appid_asks_nothing(self):
        """The guard that keeps a built application off the registry path."""
        assert _catalog._uninstall_location("") is None

    def test_an_appid_nothing_registered_reads_as_absent(self):
        """Absence is the NORMAL answer -- it is simply not installed -- so
        it comes back as None rather than raising."""
        assert _catalog._uninstall_location("{00000000-DEAD-BEEF-0000-"
                                           "000000000000}") is None

    def test_the_lab_appid_is_the_form_the_registry_holds(self):
        """The GUID is a contract between two repositories.

        Its counterpart is ``#define AppId "{{<this>"`` in ePy Lab's own
        installer script: Inno doubles the leading brace in a ``#define``
        and suffixes the key with ``_is1``, so the catalogue must carry
        the SINGLE-brace form the registry actually holds.

        Checked by shape and not by reading that file. This repository is
        PUBLIC and ePy Lab's is not, so a test here that opened the
        sibling would pass only on the owner's machine -- and the rule is
        that a test does not step aside when its subject is absent.
        """
        appid = _lab().own_install_appid
        assert appid.startswith("{") and appid.endswith("}")
        assert not appid.startswith("{{")
        assert len(appid) == 38, appid          # {8-4-4-4-12}
        assert appid.count("-") == 4
        assert appid[1:-1].replace("-", "").isalnum()

    def test_a_recorded_location_is_read_back(self, monkeypatch, tmp_path):
        """The success path, against a FAKE registry.

        Standing up a real HKCU key would write to the machine running the
        suite, and the logic under test is ours -- which hive to try, which
        key name to build, what to do with the value -- not Windows'.
        """
        monkeypatch.setitem(
            sys.modules, "winreg",
            _FakeWinreg({(0, _LAB_KEY): str(tmp_path)}))
        assert _catalog._uninstall_location(_LAB_GUID) == tmp_path

    def test_the_machine_hive_is_tried_after_the_user_one(
            self, monkeypatch, tmp_path):
        """A per-user install lands in HKCU, but the owner may have run the
        installer for all users."""
        monkeypatch.setitem(
            sys.modules, "winreg",
            _FakeWinreg({(1, _LAB_KEY): str(tmp_path)}))
        assert _catalog._uninstall_location(_LAB_GUID) == tmp_path

    def test_a_key_that_exists_and_records_nothing_reads_as_absent(
            self, monkeypatch):
        """An empty InstallLocation is not a path."""
        monkeypatch.setitem(
            sys.modules, "winreg", _FakeWinreg({(0, _LAB_KEY): ""}))
        assert _catalog._uninstall_location(_LAB_GUID) is None

    def test_the_key_name_carries_innos_own_suffix(
            self, monkeypatch, tmp_path):
        """``_is1``. Without it the lookup asks for a key Inno never wrote."""
        wrong = _LAB_KEY.removesuffix("_is1")
        monkeypatch.setitem(
            sys.modules, "winreg", _FakeWinreg({(0, wrong): str(tmp_path)}))
        assert _catalog._uninstall_location(_LAB_GUID) is None

    def test_a_platform_without_winreg_reads_as_absent(self, monkeypatch):
        """The lookup is Windows-only and must not break a Linux checkout."""
        import builtins

        real = builtins.__import__

        def refuse(name, *args, **kwargs):
            if name == "winreg":
                raise ImportError("no winreg here")
            return real(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", refuse)
        assert _catalog._uninstall_location("{GUID}") is None
