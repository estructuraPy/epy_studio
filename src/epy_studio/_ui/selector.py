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
import shutil
import subprocess
import threading
from pathlib import Path
from typing import Any

from epy_export import (
    DEFAULT_THEME,
    LEGACY_ORGANIZATIONS,
    ORGANIZATION,
    apply_theme,
    is_truthy,
    theme_names,
)

from .._core import _i18n
from .._core._backends import (
    Backend,
    detect_docs,
    handoff_env,
)
from .._core._catalog import (
    SHIPS_INSTALLED,
    App,
    apps,
    craft_env,
    download_page,
    external_exe_env,
    install_dir,
    installed_exe,
)

__all__ = ["APP_NAME", "blender_launch_command", "build_window", "manual_path"]

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


ENV_BLENDER_LAUNCH = "EPY_BLENDER_LAUNCH"
"""Names the command that opens Blender with the ePy Suite."""


def blender_launch_command() -> str:
    """Return the command that opens Blender with the suite, or ``""``.

    The launcher is a Python entry point -- ``epy_blender-launch``, installed
    by the ``epy_blender`` package -- not an executable this repository builds,
    so a machine without it simply has no Blender action. The variable is the
    escape hatch for a workspace checkout, where the launcher is
    ``python -m epy_blender``.
    """
    named = os.environ.get(ENV_BLENDER_LAUNCH, "")
    if named:
        return named
    return shutil.which("epy_blender-launch") or ""


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


_GRID_COLUMNS = 3
"""How many application cards share a row by default."""

_GRID_CHOICES = (2, 3, 4, 5)
"""The column counts the reader may choose from."""


def current_columns() -> int:
    """Return the stored column count, falling back to the default."""
    from PySide6.QtCore import QSettings  # noqa: PLC0415

    stored = str(
        QSettings(ORGANIZATION, "epy_studio").value("columns", "")
    )
    try:
        value = int(stored)
    except (TypeError, ValueError):
        return _GRID_COLUMNS
    return value if value in _GRID_CHOICES else _GRID_COLUMNS


def remember_columns(count: int) -> None:
    """Store the reader's chosen column count."""
    from PySide6.QtCore import QSettings  # noqa: PLC0415

    QSettings(ORGANIZATION, "epy_studio").setValue("columns", count)


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


THEME_KEY = "theme"
"""QSettings key remembering the reader's chosen palette."""


def current_theme() -> str:
    """Return the stored theme name, falling back to the default."""
    from PySide6.QtCore import QSettings  # noqa: PLC0415

    stored = str(
        QSettings(ORGANIZATION, "epy_studio").value(THEME_KEY, "")
    )
    return stored if stored in theme_names() else DEFAULT_THEME


def remember_theme(name: str) -> None:
    """Store the reader's chosen palette."""
    from PySide6.QtCore import QSettings  # noqa: PLC0415

    QSettings(ORGANIZATION, "epy_studio").setValue(THEME_KEY, name)
EXTERNAL_KEY = "external/{}"
"""QSettings key naming a user-located adopted application's exe."""


def remember_external_path(app_id: str, path: str | Path) -> None:
    """Store where the reader pointed at an adopted application.

    Studio never installs an adopted application, so when the reader has
    one the resolver would not find, they point at it once and Studio
    remembers it -- the stored form of the ``EPY_<ID>_EXE`` escape hatch.

    Args:
        app_id: The catalog id, e.g. ``cadcraft``.
        path: The executable the reader chose.
    """
    from PySide6.QtCore import QSettings  # noqa: PLC0415

    QSettings(ORGANIZATION, "epy_studio").setValue(
        EXTERNAL_KEY.format(app_id), str(path)
    )


def load_external_paths() -> dict[str, str]:
    """Return every adopted application the reader located, by id.

    Read once, as the window is built, and published through the
    ``EPY_<ID>_EXE`` variable the resolver (:func:`installed_exe`)
    already honours, so a located application behaves exactly like one
    found on ``PATH``. A stored path that is no longer on disk is
    dropped rather than offered.

    Returns:
        id -> executable path, for the entries still on disk.
    """
    from PySide6.QtCore import QSettings  # noqa: PLC0415

    settings = QSettings(ORGANIZATION, "epy_studio")
    found: dict[str, str] = {}
    for app in apps():
        if app.ships != SHIPS_INSTALLED:
            continue
        stored = str(settings.value(EXTERNAL_KEY.format(app.app_id), ""))
        if stored and Path(stored).is_file():
            found[app.app_id] = stored
            os.environ[external_exe_env(app.exe_stem)] = stored
    return found


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
        QUrl,  # noqa: PLC0415
        Signal,
    )
    from PySide6.QtGui import QDesktopServices  # noqa: PLC0415
    from PySide6.QtWidgets import (  # noqa: PLC0415
        QCheckBox,
        QComboBox,
        QFileDialog,
        QFrame,
        QGridLayout,
        QHBoxLayout,
        QLabel,
        QMainWindow,
        QMenu,
        QPushButton,
        QScrollArea,
        QVBoxLayout,
        QWidget,
    )

    _i18n.set_language(language or preferred_language())
    # A located adopted application is given back to the resolver before
    # any row is built, so it shows as installed from the first draw.
    load_external_paths()
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
            layout.setContentsMargins(30, 28, 30, 18)
            layout.setSpacing(14)

            title = QLabel(APP_NAME, root)
            title.setObjectName("AppTitle")
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
            subtitle.setObjectName("AppSubtitle")
            subtitle.setWordWrap(True)
            layout.addWidget(subtitle)

            base = install_dir()
            grid = QGridLayout()
            grid.setHorizontalSpacing(16)
            grid.setVerticalSpacing(16)
            grid.setContentsMargins(0, 0, 0, 0)
            index = 0
            columns = current_columns()
            for app in apps():
                exe = installed_exe(app)
                if (
                    app.optional
                    and exe is None
                    and app.ships != SHIPS_INSTALLED
                ):
                    # An OPTIONAL application of OURS that is not
                    # installed is not offered at all -- not greyed. A
                    # greyed row says 'you could have this, re-run the
                    # installer'. An ADOPTED application is the
                    # exception: Studio never installs it, so the reader
                    # must be able to install it or point at it, and
                    # that needs the row to be there whether it is
                    # installed yet or not.
                    continue
                grid.addWidget(
                    self._app_card(base, app),
                    index // columns,
                    index % columns,
                )
                index += 1
            holder = QWidget()
            holder.setLayout(grid)
            scroll = QScrollArea(root)
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.Shape.NoFrame)
            scroll.setWidget(holder)
            layout.addWidget(scroll, 1)

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
            # ePy Blender: a real launcher COMMAND, not an executable this
            # repository builds. Disabled, with the reason, when it is absent.
            blender = blender_launch_command()
            blender_btn = QPushButton(_i18n.tr("ePy Blender"), root)
            if blender:
                blender_btn.setToolTip(
                    _i18n.tr("Open Blender with the ePy Suite addon loaded.")
                )
                blender_btn.clicked.connect(
                    lambda _checked=False, c=blender: self._launch_command(c)
                )
            else:
                blender_btn.setEnabled(False)
                blender_btn.setToolTip(
                    _i18n.tr(
                        "Not available: install epy_blender, or set "
                        "EPY_BLENDER_LAUNCH to the launcher command."
                    )
                )
            bottom.addWidget(blender_btn)
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
            theme_btn = QPushButton(_i18n.tr("Theme"), root)
            theme_menu = QMenu(theme_btn)
            for name in theme_names():
                action = theme_menu.addAction(name.capitalize())
                action.setCheckable(True)
                action.setChecked(name == current_theme())
                action.triggered.connect(
                    lambda _checked=False, n=name: self._set_theme(n)
                )
            theme_btn.setMenu(theme_menu)
            bottom.addWidget(theme_btn)
            columns_label = QLabel(_i18n.tr("Columns"), root)
            bottom.addWidget(columns_label)
            columns_combo = QComboBox(root)
            for count in _GRID_CHOICES:
                columns_combo.addItem(str(count), count)
            columns_combo.setCurrentText(str(current_columns()))
            columns_combo.currentIndexChanged.connect(
                lambda _index: self._set_columns(
                    int(columns_combo.currentData())
                )
            )
            bottom.addWidget(columns_combo)
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

        def _set_theme(self, name: str) -> None:
            """Apply a palette and rebuild the window under it."""
            from PySide6.QtWidgets import QApplication  # noqa: PLC0415

            apply_theme(QApplication.instance(), name)
            remember_theme(name)
            replacement = build_window(self._files, backend=self._backend)
            replacement.show()
            self.close()

        def _set_columns(self, count: int) -> None:
            """Store the column count and rebuild the grid."""
            remember_columns(count)
            replacement = build_window(self._files, backend=self._backend)
            replacement.show()
            self.close()

        def _app_card(self, base: Path, app: App) -> Any:
            """Build one application card for the grid.

            ``base`` is where the applications Studio BUILDS live. One that
            ships with its own installer is somewhere else entirely, so the
            path is resolved by the catalog rather than assembled here.
            """
            exe_path = installed_exe(app) or base / f"{app.app_id}.exe"
            card = QFrame(self)
            card.setObjectName("AppCard")
            card.setFrameShape(QFrame.Shape.NoFrame)
            card.setMinimumWidth(240)
            column = QVBoxLayout(card)
            column.setContentsMargins(18, 18, 18, 16)
            column.setSpacing(8)

            badge = QLabel(card)
            badge.setObjectName("AppBadge")
            badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            badge.setFixedSize(68, 68)
            badge.setText(app.display[:1].upper())
            column.addWidget(badge, alignment=Qt.AlignmentFlag.AlignHCenter)

            name = QLabel(app.display, card)
            name.setObjectName("AppName")
            name.setAlignment(Qt.AlignmentFlag.AlignCenter)
            name.setWordWrap(True)
            column.addWidget(name)

            desc = QLabel(_i18n.tr(app.description), card)
            desc.setObjectName("AppDesc")
            desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
            desc.setWordWrap(True)
            column.addWidget(desc)
            column.addStretch(1)

            if exe_path.is_file():
                button = QPushButton(_i18n.tr("Open"), card)
                button.setObjectName("Primary")
                button.clicked.connect(
                    lambda _checked=False, p=exe_path: self._launch(p)
                )
                column.addWidget(button)
                return card
            if app.ships == SHIPS_INSTALLED:
                desc.setText(
                    _i18n.tr(app.description)
                    + "  "
                    + _i18n.tr("(not installed)")
                )
                page = download_page(app)
                actions = QHBoxLayout()
                install = QPushButton(_i18n.tr("Install..."), card)
                install.setEnabled(bool(page))
                install.setToolTip(
                    _i18n.tr("Get it from its own project:") + f" {page}"
                    if page
                    else _i18n.tr(
                        "No download page is declared for this "
                        "application."
                    )
                )
                install.clicked.connect(
                    lambda _checked=False, p=page: self._open(p)
                )
                actions.addWidget(install)
                locate = QPushButton(_i18n.tr("Locate..."), card)
                locate.setToolTip(
                    _i18n.tr(
                        "Point Studio at an executable already on disk."
                    )
                )
                locate.clicked.connect(
                    lambda _checked=False, a=app: self._locate(a)
                )
                actions.addWidget(locate)
                column.addLayout(actions)
                return card
            button = QPushButton(_i18n.tr("Open"), card)
            button.setEnabled(False)
            button.setToolTip(
                _i18n.tr(
                    "Not installed — re-run the installer to "
                    "add it."
                )
                if app.built_here
                else _i18n.tr(
                    "Not installed — it ships on its own; install "
                    "it and this row becomes available."
                )
            )
            desc.setText(
                _i18n.tr(app.description)
                + "  "
                + _i18n.tr("(not installed)")
            )
            column.addWidget(button)
            return card

        def _open(self, url: str) -> None:
            """Open a URL in the reader's browser, ignoring an empty one."""
            if url:
                QDesktopServices.openUrl(QUrl(url))

        def _locate(self, app: App) -> None:
            """Ask for an adopted application's executable, remember it."""
            chosen, _filter = QFileDialog.getOpenFileName(
                self,
                _i18n.tr("Locate {app}").format(app=app.display),
                "",
                "Executable (*.exe)",
            )
            if not chosen:
                return
            remember_external_path(app.app_id, chosen)
            os.environ[external_exe_env(app.exe_stem)] = chosen
            replacement = build_window(self._files, backend=self._backend)
            replacement.show()
            self.close()

        def _launch_command(self, command: str) -> None:
            """Start a launcher command (a path, or ``python -m ...``)."""
            subprocess.Popen(  # noqa: S602 - the command is the user's own setting
                command,
                shell=True,
            )
            self.close()

        def _launch(self, exe_path: Path) -> None:
            """Start the selected tool, forwarding files and the hints."""
            subprocess.Popen(  # noqa: S603 — fixed path in our install dir
                [str(exe_path), *self._files],
                cwd=str(exe_path.parent),
                env={
                    **os.environ,
                    **handoff_env(
                        self._settled_backend(), offer=docs_offered()
                    ),
                    # The adopted ArtCraft CLIs found on this machine, so a
                    # drawing flow the launched app drives can reach them.
                    **craft_env(),
                },
            )
            self.close()

    return StudioWindow()
