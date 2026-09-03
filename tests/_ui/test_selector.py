"""The selector window, in both languages."""

from __future__ import annotations

import pytest

from epy_studio._core._backends import Backend

# In a conda environment Qt does not import until ICU is pinned.
# epy_export owns that workaround for the whole family; Studio is a
# launcher and never needed it at run time, because the frozen
# bundle strips the conda ICU that shadows the system one. A source
# checkout has no such stripping, so the test asks for the pin.
try:
    from epy_export import pin_system_icu

    pin_system_icu()
except ImportError:  # pragma: no cover - epy_export is optional here
    pass

pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)


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


def test_every_application_gets_a_row(qt_app) -> None:
    from epy_studio._core._catalog import apps
    from epy_studio._ui.selector import build_window

    texts = _labels(build_window([], backend=Backend(), language="en"))
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
