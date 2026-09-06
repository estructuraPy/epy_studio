"""The selector window, in both languages."""

from __future__ import annotations

import pytest

from epy_studio._core._backends import Backend

# conftest pins ICU before any test module loads, which is what lets
# PySide6 import under conda. Qt is a hard dependency of this package,
# so a failure to import it is a broken environment and must be read as
# one: skipping here would turn the whole file green on a machine where
# the launcher cannot start.


@pytest.fixture(scope="module")
def qt_app():
    """One offscreen QApplication for the file."""
    import os

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def _labels(window) -> list[str]:
    from PySide6.QtWidgets import QLabel

    return [item.text() for item in window.findChildren(QLabel) if item.text()]


def test_the_window_builds_in_english(qt_app) -> None:
    from epy_studio._ui.selector import build_window

    texts = _labels(build_window([], backend=Backend(), language="en"))
    assert "Choose the editor for your document:" in texts
    assert any("live preview" in t for t in texts)


def test_the_window_builds_in_spanish(qt_app) -> None:
    from epy_studio._ui.selector import build_window

    texts = _labels(build_window([], backend=Backend(), language="es"))
    assert "Elija el editor para su documento:" in texts
    assert any("vista previa en vivo" in t for t in texts)


def test_a_caller_that_names_a_language_is_not_overridden(qt_app) -> None:
    # build_window resolved the reader's stored choice unconditionally,
    # so it ignored what the caller asked for -- which also meant the
    # language switch had its own choice overwritten on the very rebuild
    # meant to apply it. Caught by asking for English on a machine whose
    # stored choice is Spanish and getting Spanish.
    from epy_studio._ui.selector import build_window

    english = _labels(build_window([], backend=Backend(), language="en"))
    spanish = _labels(build_window([], backend=Backend(), language="es"))
    assert english != spanish


def test_every_required_application_gets_a_row(qt_app) -> None:
    # From a source checkout nothing is installed, so every required
    # application is offered greyed: that is a custom install the user
    # could complete, and the row says how.
    from epy_studio._core._catalog import apps
    from epy_studio._ui.selector import build_window

    texts = _labels(build_window([], backend=Backend(), language="en"))
    for app in apps():
        if app.optional:
            continue
        assert app.display in texts, f"{app.app_id} has no row"


def test_an_optional_application_without_its_exe_is_not_offered(
    qt_app,
) -> None:
    # The owner's rule: not greyed, ABSENT. An optional application is
    # handed out, not installed by leaving a box ticked, so a row for
    # one that is not there would advertise something the installer
    # cannot give.
    from epy_studio._core._catalog import apps
    from epy_studio._ui.selector import build_window

    optional = [app for app in apps() if app.optional]
    assert optional, "nothing optional to test against"
    texts = _labels(build_window([], backend=Backend(), language="en"))
    for app in optional:
        assert app.display not in texts, f"{app.app_id} was offered"


def test_an_optional_application_with_its_exe_is_offered(
    qt_app, tmp_path, monkeypatch
) -> None:
    # The control: present, it gets its row like any other.
    from epy_studio._core import _catalog
    from epy_studio._core._catalog import apps
    from epy_studio._ui import selector

    for app in apps():
        (tmp_path / f"{app.app_id}.exe").write_bytes(b"MZ")
    monkeypatch.setattr(selector, "install_dir", lambda: tmp_path)
    monkeypatch.setattr(_catalog, "install_dir", lambda: tmp_path)
    window = selector.build_window([], backend=Backend(), language="en")
    texts = _labels(window)
    for app in apps():
        assert app.display in texts, f"{app.app_id} has no row"


# ------------------------------------------- the stored language


@pytest.fixture()
def ini_settings(tmp_path, monkeypatch):
    """Route ``QSettings(org, app)`` to INI files under ``tmp_path``.

    One file per (organisation, application) pair, which is what the
    registry gives the real program: a language stored by one editor
    must be found by reading THAT scope and no other. The two-argument
    constructor IGNORES ``setDefaultFormat`` (Qt documents it) and goes
    to the registry, so the constructor itself is replaced, not the
    format. The system locale is pinned to English so the fallback
    cannot masquerade as a hit.
    """
    from PySide6 import QtCore

    real = QtCore.QSettings

    def scratch(organisation: str, name: str) -> object:
        return real(
            str(tmp_path / f"{organisation}__{name}.ini"),
            real.Format.IniFormat,
        )

    monkeypatch.setattr(QtCore, "QSettings", scratch)
    monkeypatch.setattr(
        QtCore.QLocale,
        "system",
        staticmethod(lambda: QtCore.QLocale(QtCore.QLocale.Language.English)),
    )
    return scratch


def test_the_language_an_editor_stored_is_found(qt_app, ini_settings) -> None:
    # Three editors save under the accented organisation and the selector
    # read the unaccented one: the person's choice was never found and
    # the first window kept asking what they had already answered.
    from epy_export import ORGANIZATION

    from epy_studio._ui import selector

    ini_settings(ORGANIZATION, "epy_reports").setValue("language", "es")
    assert selector.preferred_language() == "es"


def test_the_unaccented_scope_studio_wrote_is_still_read(
    qt_app, ini_settings
) -> None:
    # Studio and epy_draft stored under the old spelling until today; a
    # selector that forgot that scope would ask again after the update.
    from epy_studio._ui import selector

    ini_settings("ANM Ingenieria", "epy_studio").setValue("language", "es")
    assert selector.preferred_language() == "es"


def test_nothing_stored_falls_back_to_the_system_language(
    qt_app, ini_settings
) -> None:
    from epy_studio._ui import selector

    assert selector.preferred_language() == "en"


def test_the_organisation_is_not_spelt_inline() -> None:
    # The whole point: one constant, imported, so the five programs
    # cannot drift into two registry trees again.
    import inspect

    from epy_studio._ui import selector

    source = inspect.getsource(selector)
    assert 'QSettings("ANM' not in source
    assert "ORGANIZATION" in source


def _checkboxes(window) -> list[str]:
    from PySide6.QtWidgets import QCheckBox

    return [
        item.text() for item in window.findChildren(QCheckBox) if item.text()
    ]


def test_the_renderer_choice_appears_only_when_there_is_one(qt_app) -> None:
    # A checkbox for a package nobody has is a question with one answer,
    # and the status strip already says the package is absent.
    from pathlib import Path

    from epy_studio._core._backends import Backend
    from epy_studio._ui.selector import build_window

    absent = build_window([], backend=Backend(), language="en")
    assert not any("ePy Docs" in text for text in _checkboxes(absent))

    found = Backend(python=Path("C:/py/python.exe"), version="1.4")
    present = build_window([], backend=found, language="en")
    assert any("ePy Docs" in text for text in _checkboxes(present))


def test_the_choice_defaults_to_offering_it(monkeypatch) -> None:
    # Somebody who installed a commercial add-on installed it to use it.
    # Offering changes what is AVAILABLE; each application keeps its own
    # engine as the default, so nothing renders differently by itself.
    from epy_studio._ui import selector

    class _Settings:
        def __init__(self, *args: object) -> None:
            pass

        def value(self, key: str, default: object = None) -> object:
            return default

    monkeypatch.setattr(
        "PySide6.QtCore.QSettings", _Settings, raising=True
    )
    assert selector.docs_offered() is True


def test_the_choice_reaches_the_launched_application(
    qt_app, monkeypatch, tmp_path
) -> None:
    # The only place the choice has any effect. Everything else about
    # it can be right while the launcher never asks, and the whole
    # feature would be inert with every other test still green --
    # measured: planting exactly that broke nothing.
    from pathlib import Path

    from epy_studio._core._backends import ENV_PYTHON, Backend
    from epy_studio._ui import selector

    handed: dict[str, str] = {}

    def fake_popen(args, **kwargs):
        handed.clear()
        handed.update(kwargs.get("env", {}))

        class _Started:
            pass

        return _Started()

    monkeypatch.setattr(selector.subprocess, "Popen", fake_popen)
    found = Backend(python=Path("C:/py/python.exe"), version="1.4")
    exe = tmp_path / "epy_reports.exe"

    monkeypatch.setattr(selector, "docs_offered", lambda: True)
    selector.build_window([], backend=found, language="en")._launch(exe)
    assert ENV_PYTHON in handed

    monkeypatch.setattr(selector, "docs_offered", lambda: False)
    selector.build_window([], backend=found, language="en")._launch(exe)
    assert ENV_PYTHON not in handed
