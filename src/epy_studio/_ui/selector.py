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
import threading
from pathlib import Path
from typing import Any

from epy_export import (
    LEGACY_ORGANIZATIONS,
    ORGANIZATION,
    is_truthy,
)

from .._core import _i18n
from .._core._backends import (
    Backend,
    detect_docs,
    handoff_env,
)
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
    the organisation scope named by ``epy_export.ORGANIZATION``. Studio
    reads the same key rather than asking again: the selector is the
    FIRST window a reader sees, which is the wrong place to be asked
    something they answered the last time they opened an editor.

    Studio and epy_draft wrote under an unaccented spelling of the
    organisation before. Those two scopes are still read, after the
    current one, so a person who chose a language there keeps it.

    Falls back to the system language, and then to English. Neither is
    a guess about the reader -- it is the order that gets a Spanish
    system a Spanish window on a fresh install.

    Returns:
        A code from :data:`_i18n.LANGUAGES`.
    """
    from PySide6.QtCore import QLocale, QSettings  # noqa: PLC0415

    current = (
        "epy_studio",
        "epy_draft",
        "epy_reports",
        "epy_slides",
        "epy_papers",
    )
    scopes = [(ORGANIZATION, name) for name in current]
    scopes += [
        (legacy, name)
        for legacy in LEGACY_ORGANIZATIONS
        for name in ("epy_studio", "epy_draft")
    ]
    for organisation, name in scopes:
        stored = str(QSettings(organisation, name).value("language", ""))
        if stored in _i18n.LANGUAGES:
            return stored
    if QLocale.system().language() == QLocale.Language.Spanish:
        return "es"
    return "en"


_DETECT_WAIT_MS = 30_000
"""How long a LAUNCH waits for the machine to answer, in ms.

Only a launch waits, and only because the hint is what makes ePy
Docs reachable in a frozen bundle. The window itself never does.
"""

DOCS_OFFERED_KEY = "backends/offer_docs"
REMEMBERED_KEY = "backends/docs_seen"
"""The last answer about ePy Docs, as ``python|version|quarto``."""
"""Whether ePy Docs is offered to the applications Studio launches."""


def docs_offered() -> bool:
    """Report whether the reader wants ePy Docs offered as a renderer.

    Defaults to yes. Somebody who has installed a commercial add-on
    installed it to use it, and the applications keep their own engine
    as the DEFAULT either way -- so offering it changes what is
    available, never what happens when nobody chooses.

    Returns:
        The stored choice, or ``True`` when nothing is stored.
    """
    from PySide6.QtCore import QSettings  # noqa: PLC0415

    stored = QSettings(ORGANIZATION, "epy_studio").value(
        DOCS_OFFERED_KEY, "true"
    )
    # QSettings hands back a string on Windows and the stored type
    # elsewhere, so the answer is normalised rather than trusted.
    return is_truthy(str(stored))


def set_docs_offered(offered: bool) -> None:
    """Store whether ePy Docs is offered.

    Args:
        offered: The reader's choice.
    """
    from PySide6.QtCore import QSettings  # noqa: PLC0415

    QSettings(ORGANIZATION, "epy_studio").setValue(
        DOCS_OFFERED_KEY, "true" if offered else "false"
    )


def remembered_backend() -> Backend | None:
    """Return the last answer about ePy Docs, or None if never asked.

    A machine does not change between one launch and the next, and the
    question costs a subprocess per candidate interpreter: measured on
    a real machine, about half a minute. Using the last answer at once
    is what keeps a launch from waiting for a question already asked.

    Returns:
        What was seen last time, or ``None``.
    """
    from PySide6.QtCore import QSettings  # noqa: PLC0415

    stored = str(
        QSettings(ORGANIZATION, "epy_studio").value(REMEMBERED_KEY, "")
    )
    if not stored:
        return None
    python, _, rest = stored.partition("|")
    version, _, quarto = rest.partition("|")
    if not python or not Path(python).is_file():
        # The interpreter it named is gone, so the answer is gone too.
        return None
    return Backend(python=Path(python), version=version, quarto=quarto)


def remember_backend(backend: Backend) -> None:
    """Store what the machine answered, for the next launch.

    Args:
        backend: What :func:`detect_docs` found. An absent one is
            remembered as absence, so a machine without ePy Docs stops
            paying for the question every time.
    """
    from PySide6.QtCore import QSettings  # noqa: PLC0415

    value = (
        f"{backend.python}|{backend.version}|{backend.quarto}"
        if backend.python is not None
        else ""
    )
    QSettings(ORGANIZATION, "epy_studio").setValue(REMEMBERED_KEY, value)


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
    from PySide6.QtCore import (  # noqa: PLC0415
        QObject,
        Qt,  # noqa: PLC0415
        Signal,
    )
    from PySide6.QtGui import QDesktopServices, QFont, QIcon  # noqa: PLC0415
    from PySide6.QtWidgets import (  # noqa: PLC0415
        QCheckBox,
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
    # Not detected here. Asking the machine means starting a subprocess
    # per candidate interpreter, and inside the frozen bundle this
    # process is not one of them -- so it probes whatever `python` and
    # `py` mean on that machine. Measured on the installed bundle: 45
    # seconds before a window appeared. A shorter timeout would trade a
    # slow answer for a wrong one, and a wrong one silently withdraws
    # the feature.
    pending = backend is None
    recalled = remembered_backend() if pending else None
    # The last answer is used AT ONCE and the question asked again
    # anyway: a stale answer that is corrected a moment later beats a
    # window that waits, and beats a launch that waits more.
    found = backend if backend is not None else (recalled or Backend())

    class _Detector(QObject):
        """Asks the machine about ePy Docs, off the interface thread.

        A plain daemon thread rather than a QThread. Qt aborts the
        process when a QThread is destroyed while still running, so the
        window would have had to WAIT for it on close -- and the answer
        takes about half a minute on a real machine, which would make
        closing the selector as slow as opening it used to be. A daemon
        thread dies with the process and owes nobody a wait.
        """

        done = Signal(object)

        def ask(self) -> None:
            """Start asking. Returns at once."""
            threading.Thread(target=self._work, daemon=True).start()

        def _work(self) -> None:
            """Detect, and hand the answer back whatever it is.

            The signal crosses back to the interface thread by itself:
            a queued connection is what Qt does when the sender is not
            the receiver's thread.
            """
            self.done.emit(detect_docs())


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
                if app.optional and not (base / f"{app.app_id}.exe").is_file():
                    # An OPTIONAL application that is not installed
                    # is not offered at all -- not greyed. A greyed
                    # row says 'you could have this, re-run the
                    # installer'; an optional one is the owner's to
                    # hand out, and its absence is not an incomplete
                    # install.
                    continue
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
            # Offered only where there is something to offer: a
            # checkbox for a package nobody has is a question with
            # one answer, and the status strip already says so.
            docs_box = QCheckBox(
                _i18n.tr("Offer ePy Docs as a renderer"), root
            )
            docs_box.setChecked(docs_offered())
            docs_box.setToolTip(
                _i18n.tr(
                    "Adds ePy Docs to the export choices of the "
                    "applications launched from here. Each one keeps "
                    "its own renderer as the default."
                )
            )
            docs_box.toggled.connect(set_docs_offered)
            docs_box.setVisible(found.present)
            bottom.addWidget(docs_box)
            self._docs_box = docs_box
            bottom.addStretch(1)
            # One strip for the whole install, not one line per row: the
            # backend is a property of the machine, and repeating the
            # same sentence four times says nothing four times.
            status = QLabel(
                f'{_i18n.tr("Export backends: built-in")} · '
                + (
                    _i18n.tr("looking for ePy Docs…")
                    if pending and recalled is None
                    else found.describe()
                )
            )
            status.setWordWrap(True)
            bottom.addWidget(status)
            self._status = status
            layout.addLayout(bottom)
            layout.addStretch(1)
            self.setCentralWidget(root)

            # A caller that HANDED us the answer -- the language
            # switch, which rebuilds the window -- has answered it.
            # Reading this as unanswered made every launch after a
            # language change wait the full budget for a question
            # nobody had asked.
            self._answered = not pending or recalled is not None
            self._settled = threading.Event()
            if self._answered:
                self._settled.set()
            if pending:
                # Kept on the window so the signal has a live receiver.
                self._detector = _Detector(self)
                self._detector.done.connect(self._on_detected)
                self._detector.ask()

        def _on_detected(self, backend: Backend) -> None:
            """Record what the machine answered and say so.

            Args:
                backend: What :func:`detect_docs` found.
            """
            self._backend = backend
            self._answered = True
            self._settled.set()
            remember_backend(backend)
            self._status.setText(
                f'{_i18n.tr("Export backends: built-in")} · '
                f"{backend.describe()}"
            )
            # A checkbox for a package nobody has is a question with one
            # answer, so it appears only once there is something to
            # offer -- and never before the answer is in.
            self._docs_box.setVisible(backend.present)

        def _settled_backend(self) -> Backend:
            """Return the answer, waiting for it only if a launch needs it.

            The window never waits; a LAUNCH does, because the hint is
            what makes the entry reachable inside the frozen bundle and
            handing over an empty one would withdraw the feature without
            saying so.
            """
            if not self._answered:
                self._settled.wait(_DETECT_WAIT_MS / 1000)
            return self._backend

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
            QSettings(ORGANIZATION, "epy_studio").setValue(
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
                env={
                    **os.environ,
                    **handoff_env(
                        self._settled_backend(), offer=docs_offered()
                    ),
                },
            )
            self.close()

    return StudioWindow()
