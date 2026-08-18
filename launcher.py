"""ePy Studio launcher — pick the right editor for the document at hand.

A minimal selector window with one entry per installed tool:

- ePy Reports: technical reports with live preview (PDF / Word / HTML).
- ePy Slides:  presentation decks (reveal.js / PowerPoint).
- ePy Papers:  academic manuscripts (journal templates).

When Windows opens a document through the Studio association
(double-click on a ``.md`` / ``.markdown`` / ``.qmd``), the selector
shows the file and forwards it to whichever editor the user picks.
Each button launches the sibling executable from the shared install
directory (all tools live in one PyInstaller bundle over a single real
``_internal``). A tool whose executable is missing (component not
installed) shows disabled with a hint, so a partial install stays honest.

CLI (used by the installer):
    epy_studio --register [--as-default]   register .md/.markdown/.qmd handler
    epy_studio --unregister                remove the registration
    epy_studio --set-default               open Settings > Default apps

This launcher deliberately contains no editing logic — zero duplication
with the apps themselves.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

APP_NAME = "ePy Studio"

TOOLS: list[tuple[str, str, str]] = [
    (
        "epy_reports",
        "ePy Reports",
        "Technical reports — live preview, PDF / Word / HTML export",
    ),
    (
        "epy_slides",
        "ePy Slides",
        "Presentation decks — reveal.js / PowerPoint export",
    ),
    (
        "epy_papers",
        "ePy Papers",
        "Academic manuscripts — journal templates and citations",
    ),
    (
        "epy_craft",
        "ContextCraft",
        "Batch LLM processing over your own reference library",
    ),
]


def install_dir() -> Path:
    """Return the directory holding the tool executables.

    Frozen: the directory of the launcher executable (all tools share
    it). Dev run: this script's directory has no exes, so the buttons
    simply disable — launching from source uses each repo's
    ``python -m`` entry instead.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).parent


def manual_path() -> Path | None:
    """Locate the bundled user manual for the current UI language."""
    from PySide6.QtCore import QLocale

    docs = install_dir() / "docs"
    spanish = QLocale.system().language() == QLocale.Language.Spanish
    candidates = (
        ["USER_MANUAL_es.md", "USER_MANUAL.md"]
        if spanish
        else ["USER_MANUAL.md", "USER_MANUAL_es.md"]
    )
    for name in candidates:
        p = docs / name
        if p.is_file():
            return p
    return None


def _run_cli(argv: list[str]) -> int | None:
    """Handle the registration CLI before any Qt import.

    Returns an exit code when a CLI mode ran, ``None`` for GUI startup.
    """
    import _assoc

    if "--register" in argv:
        for line in _assoc.register(make_default="--as-default" in argv):
            print(line)
        print(
            "\nDone. Documents opened via ePy Studio show the editor "
            "selector.\nWindows requires confirming the default in "
            "Settings > Default apps."
        )
        if "--as-default" in argv:
            _assoc.open_default_apps_settings()
        return 0
    if "--unregister" in argv:
        for line in _assoc.unregister():
            print(line)
        return 0
    if "--set-default" in argv:
        _assoc.open_default_apps_settings()
        return 0
    return None


def build_window(files: list[str]):
    """Build the selector window (Qt imported here, after CLI handling)."""
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QDesktopServices, QFont, QIcon
    from PySide6.QtWidgets import (
        QFrame,
        QHBoxLayout,
        QLabel,
        QMainWindow,
        QPushButton,
        QVBoxLayout,
        QWidget,
    )

    class StudioWindow(QMainWindow):
        """Selector window: one row per tool, launch on click."""

        def __init__(self) -> None:
            super().__init__()
            self.setWindowTitle(APP_NAME)
            self.setMinimumWidth(560)
            self._files = files

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
            for exe_name, display, description in TOOLS:
                layout.addWidget(
                    self._tool_row(base, exe_name, display, description)
                )

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
            layout.addLayout(bottom)
            layout.addStretch(1)
            self.setCentralWidget(root)

        def _tool_row(
            self, base: Path, exe_name: str, display: str, description: str
        ) -> QFrame:
            """Build one launchable tool row."""
            exe_path = base / f"{exe_name}.exe"
            row = QFrame(self)
            row.setFrameShape(QFrame.Shape.StyledPanel)
            h = QHBoxLayout(row)

            text_col = QVBoxLayout()
            name_label = QLabel(display, row)
            name_font = QFont()
            name_font.setPointSize(12)
            name_font.setBold(True)
            name_label.setFont(name_font)
            text_col.addWidget(name_label)
            desc_label = QLabel(description, row)
            desc_label.setWordWrap(True)
            text_col.addWidget(desc_label)
            h.addLayout(text_col, stretch=1)

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
                desc_label.setText(description + "  (not installed)")
            h.addWidget(button, alignment=Qt.AlignmentFlag.AlignVCenter)
            return row

        def _launch(self, exe_path: Path) -> None:
            """Start the selected tool (forwarding any opened files)."""
            subprocess.Popen(  # noqa: S603 — fixed path in our install dir
                [str(exe_path), *self._files], cwd=str(exe_path.parent)
            )
            self.close()

    return StudioWindow()


def main() -> int:
    """Launcher entry point: CLI registration modes, then the GUI."""
    argv = sys.argv[1:]
    cli_result = _run_cli(argv)
    if cli_result is not None:
        return cli_result

    from PySide6.QtWidgets import QApplication

    files = [a for a in argv if not a.startswith("-")]
    app = QApplication(sys.argv)
    window = build_window(files)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
