"""The selector window: one row per application, launch on click.

A module-level class, which it was not. ``StudioWindow`` used to be
defined INSIDE the function that built it, so no test could import it,
and ``TOOLS`` and ``install_dir`` were module globals a test could not
redirect. Nothing here could be exercised except by starting the
program. Pulling the class out is what makes any of this testable --
it is not ceremony, and the backend detection about to land is exactly
the kind of logic whose failure mode is a wrong answer rather than a
crash.

Qt is imported at call time, so the module loads without it and the
registration CLI still runs before any Qt import.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

from .._core import _i18n
from .._core._backends import Backend, detect_docs, handoff_env
from .._core._catalog import App, apps, install_dir

__all__ = ["APP_NAME", "build_window", "manual_path"]

APP_NAME = "ePy Studio"


def manual_path() -> Path | None:
    """Locate the bundled user manual for the current UI language."""
    from PySide6.QtCore import QLocale  # noqa: PLC0415

    docs = install_dir() / "docs"
    spanish = QLocale.system().language() == QLocale.Language.Spanish
    order = (
        ["USER_MANUAL_es.md", "USER_MANUAL.md"]
        if spanish
        else ["USER_MANUAL.md", "USER_MANUAL_es.md"]
    )
    for name in order:
        candidate = docs / name
        if candidate.is_file():
            return candidate
    return None


def preferred_language() -> str:
    """Return the language this reader already chose, if any.

    The four applications each store the choice under ``language`` in
    the ``ANM Ingenieria`` organisation. Studio reads the same key
    rather than asking again: the selector is the FIRST window a reader
    sees, which is the wrong place to be asked something they answered
    the last time they opened an editor.

    Falls back to the system language, and then to English. Neither is
    a guess about the reader -- it is the order that gets a Spanish
    system a Spanish window on a fresh install.

    Returns:
        A code from :data:`_i18n.LANGUAGES`.
    """
    from PySide6.QtCore import QLocale, QSettings  # noqa: PLC0415

    for name in ("epy_studio", "epy_reports", "epy_slides", "epy_papers"):
        stored = str(QSettings("ANM Ingenieria", name).value("language", ""))
        if stored in _i18n.LANGUAGES:
            return stored
    if QLocale.system().language() == QLocale.Language.Spanish:
        return "es"
    return "en"


def build_window(
    files: list[str],
    *,
    backend: Backend | None = None,
    language: str | None = None,
) -> Any:
    """Build the selector window.

    Args:
        files: Documents to forward to whichever application is picked.
        backend: What was found for ePy Docs. Detected when not given;
            injectable so a test does not pay for a subprocess.
        language: Which language to build in. Resolved from the
            reader's stored choice when not given -- and passed
            explicitly by the language switch, which would
            otherwise have its choice overwritten by the resolver
            on the very rebuild meant to apply it.

    Returns:
        The window, ready to show.
    """
    from PySide6.QtCore import Qt  # noqa: PLC0415
    from PySide6.QtGui import QDesktopServices, QFont, QIcon  # noqa: PLC0415
    from PySide6.QtWidgets import (  # noqa: PLC0415
        QFrame,
        QHBoxLayout,
        QLabel,
        QMainWindow,
        QMenu,
        QPushButton,
        QVBoxLayout,
        QWidget,
    )

    _i18n.set_language(language or preferred_language())
    found = detect_docs() if backend is None else backend

    class StudioWindow(QMainWindow):
        """One row per application; launching closes the selector."""

        def __init__(self) -> None:
            super().__init__()
            self.setWindowTitle(APP_NAME)
            self.setMinimumWidth(560)
            self._files = files
            self._backend = found

            root = QWidget(self)
            layout = QVBoxLayout(root)
            layout.setContentsMargins(24, 24, 24, 24)
            layout.setSpacing(12)

            title = QLabel(APP_NAME, root)
            title_font = QFont()
            title_font.setPointSize(18)
            title_font.setBold(True)
            title.setFont(title_font)
            layout.addWidget(title)

            if self._files:
                names = ", ".join(Path(f).name for f in self._files)
                subtitle = QLabel(
                    _i18n.tr("Open <b>{names}</b> with:").format(
                        names=names
                    ),
                    root,
                )
            else:
                subtitle = QLabel(
                    _i18n.tr("Choose the editor for your document:"),
                    root,
                )
            layout.addWidget(subtitle)

            base = install_dir()
            for app in apps():
                layout.addWidget(self._tool_row(base, app))

            bottom = QHBoxLayout()
            manual = manual_path()
            manual_btn = QPushButton(_i18n.tr("User manual"), root)
            if manual is not None:
                manual_btn.clicked.connect(
                    lambda _checked=False, p=manual: QDesktopServices.openUrl(
                        f"file:///{p.as_posix()}"
                    )
                )
            else:
                manual_btn.setEnabled(False)
            bottom.addWidget(manual_btn)
            # A reader who changes it here changes it for the selector
            # only; each application keeps its own, because each stores
            # the choice under its own name. Studio writes its own key
            # so the next launch remembers.
            language_btn = QPushButton(_i18n.tr("Language"), root)
            language_menu = QMenu(language_btn)
            for code, name in _i18n.LANGUAGES.items():
                action = language_menu.addAction(name)
                action.setCheckable(True)
                action.setChecked(code == _i18n.current_language())
                action.triggered.connect(
                    lambda _checked=False, c=code: self._set_language(c)
                )
            language_btn.setMenu(language_menu)
            bottom.addWidget(language_btn)
            bottom.addStretch(1)
            # One strip for the whole install, not one line per row: the
            # backend is a property of the machine, and repeating the
            # same sentence four times says nothing four times.
            status = QLabel(
                f'{_i18n.tr("Export backends: built-in")} · '
                f"{found.describe()}"
            )
            status.setWordWrap(True)
            bottom.addWidget(status)
            layout.addLayout(bottom)
            layout.addStretch(1)
            self.setCentralWidget(root)

        def _set_language(self, code: str) -> None:
            """Store the choice and rebuild the window in that language.

            Rebuilt rather than relabelled: the selector is small and
            built in one pass, so a second pass is cheaper than a
            registry of every widget that carries a string -- and a
            registry is what silently misses the one label somebody
            added last.
            """
            from PySide6.QtCore import QSettings  # noqa: PLC0415

            _i18n.set_language(code)
            QSettings("ANM Ingenieria", "epy_studio").setValue(
                "language", code
            )
            replacement = build_window(
                self._files, backend=self._backend, language=code
            )
            replacement.show()
            self.close()

        def _tool_row(self, base: Path, app: App) -> Any:
            """Build one launchable row."""
            exe_path = base / f"{app.app_id}.exe"
            row = QFrame(self)
            row.setFrameShape(QFrame.Shape.StyledPanel)
            line = QHBoxLayout(row)

            text_col = QVBoxLayout()
            name_label = QLabel(app.display, row)
            name_font = QFont()
            name_font.setPointSize(12)
            name_font.setBold(True)
            name_label.setFont(name_font)
            text_col.addWidget(name_label)
            desc_label = QLabel(_i18n.tr(app.description), row)
            desc_label.setWordWrap(True)
            text_col.addWidget(desc_label)
            line.addLayout(text_col, stretch=1)

            button = QPushButton(_i18n.tr("Open"), row)
            button.setMinimumWidth(96)
            if exe_path.is_file():
                button.clicked.connect(
                    lambda _checked=False, p=exe_path: self._launch(p)
                )
                button.setIcon(QIcon(str(exe_path)))
            else:
                button.setEnabled(False)
                button.setToolTip(
                    _i18n.tr(
                        "Not installed — re-run the installer to "
                        "add it."
                    )
                )
                desc_label.setText(
                    _i18n.tr(app.description)
                    + "  "
                    + _i18n.tr("(not installed)")
                )
            line.addWidget(button, alignment=Qt.AlignmentFlag.AlignVCenter)
            return row

        def _launch(self, exe_path: Path) -> None:
            """Start the selected tool, forwarding files and the hint."""
            subprocess.Popen(  # noqa: S603 — fixed path in our install dir
                [str(exe_path), *self._files],
                cwd=str(exe_path.parent),
                env={**os.environ, **handoff_env(self._backend)},
            )
            self.close()

    return StudioWindow()
