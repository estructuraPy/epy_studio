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


def build_window(files: list[str], *, backend: Backend | None = None) -> Any:
    """Build the selector window.

    Args:
        files: Documents to forward to whichever application is picked.
        backend: What was found for ePy Docs. Detected when not given;
            injectable so a test does not pay for a subprocess.

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
        QPushButton,
        QVBoxLayout,
        QWidget,
    )

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
                subtitle = QLabel(f"Open <b>{names}</b> with:", root)
            else:
                subtitle = QLabel("Choose the editor for your document:", root)
            layout.addWidget(subtitle)

            base = install_dir()
            for app in apps():
                layout.addWidget(self._tool_row(base, app))

            bottom = QHBoxLayout()
            manual = manual_path()
            manual_btn = QPushButton("User manual", root)
            if manual is not None:
                manual_btn.clicked.connect(
                    lambda _checked=False, p=manual: QDesktopServices.openUrl(
                        f"file:///{p.as_posix()}"
                    )
                )
            else:
                manual_btn.setEnabled(False)
            bottom.addWidget(manual_btn)
            bottom.addStretch(1)
            # One strip for the whole install, not one line per row: the
            # backend is a property of the machine, and repeating the
            # same sentence four times says nothing four times.
            status = QLabel(f"Export backends: built-in · {found.detail}")
            status.setWordWrap(True)
            bottom.addWidget(status)
            layout.addLayout(bottom)
            layout.addStretch(1)
            self.setCentralWidget(root)

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
            desc_label = QLabel(app.description, row)
            desc_label.setWordWrap(True)
            text_col.addWidget(desc_label)
            line.addLayout(text_col, stretch=1)

            button = QPushButton("Open", row)
            button.setMinimumWidth(96)
            if exe_path.is_file():
                button.clicked.connect(
                    lambda _checked=False, p=exe_path: self._launch(p)
                )
                button.setIcon(QIcon(str(exe_path)))
            else:
                button.setEnabled(False)
                button.setToolTip(
                    "Not installed — re-run the installer to add it."
                )
                desc_label.setText(app.description + "  (not installed)")
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
