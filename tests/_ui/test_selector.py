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
