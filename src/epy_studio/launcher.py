"""Launcher entry point: the registration CLI, then the selector.

What is left here once the window, the catalog and the backend
detection have their own modules: parse the arguments, run the CLI
before any Qt import, otherwise start the GUI.

The CLI-before-Qt ordering is deliberate and load-bearing. The
installer calls ``--register`` on a machine where nothing needs a
display, and importing Qt to read a command-line flag is how a
post-install step starts failing on a server.

CLI (used by the installer)::

    epy_studio --register [--as-default]   handle .md / .markdown / .qmd
    epy_studio --unregister                remove the registration
    epy_studio --set-default               open Settings > Default apps
"""

from __future__ import annotations

import sys

__all__ = ["main", "offer_registration"]

_PROMPT_KEY = "registration_prompt"
"""Settings key remembering that the question below was already asked."""


def offer_registration() -> str:
    """Ask once whether ePy Studio should handle Markdown documents.

    Every ``[Run]`` entry in the installer carries ``skipifsilent``, so a
    silent deployment never runs ``--register`` and the documents it was
    installed for open in whatever handled them before. Asking on the
    first start is the only moment a person is present to answer, and
    the answer -- either answer -- is remembered so the question is
    asked exactly once.

    Nothing is ever taken silently: the registration only adds ePy Studio
    to the "Open with" list, and Windows still requires the reader to
    confirm a default in Settings.

    Returns:
        ``"done"`` when the registration ran, ``"declined"`` when the
        reader said no, or ``"skipped"`` when the question does not
        apply -- not a frozen Windows install, already registered, or
        already answered once.
    """
    from epy_export import ORGANIZATION  # noqa: PLC0415
    from PySide6.QtCore import QSettings  # noqa: PLC0415
    from PySide6.QtWidgets import QMessageBox  # noqa: PLC0415

    from ._core import _i18n, winreg_assoc  # noqa: PLC0415

    # A checkout must never write the registry: the command it would
    # store points at the interpreter, not at an installed bundle.
    if sys.platform != "win32" or not getattr(sys, "frozen", False):
        return "skipped"
    if winreg_assoc.is_registered():
        return "skipped"
    settings = QSettings(ORGANIZATION, "epy_studio")
    if settings.value(_PROMPT_KEY, "") not in ("", None):
        return "skipped"

    answer = QMessageBox.question(
        None,
        _i18n.tr("ePy Studio"),
        _i18n.tr(
            "ePy Studio is not set up to open your documents. Add it to "
            "the list of applications that handle Markdown files?\n\n"
            "This only adds it to “Open with”. Windows still asks you to "
            "confirm a default in Settings."
        ),
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.Yes,
    )
    if answer != QMessageBox.StandardButton.Yes:
        settings.setValue(_PROMPT_KEY, "declined")
        return "declined"

    winreg_assoc.register(make_default=False)
    _register_siblings()
    settings.setValue(_PROMPT_KEY, "done")
    return "done"


def _register_siblings() -> list[str]:
    """Run ``--register`` on every editor installed beside the launcher.

    The editors own their own extensions and their own ProgIDs, so the
    launcher cannot register them on their behalf. One failing sibling
    never stops the others: a missing executable is an uninstalled
    component, not an error.

    Returns:
        The ``app_id`` of every sibling whose registration was started.
    """
    import subprocess  # noqa: PLC0415

    from ._core._catalog import apps, install_dir  # noqa: PLC0415

    started: list[str] = []
    folder = install_dir()
    for app in apps():
        exe = folder / f"{app.app_id}.exe"
        if not exe.is_file():
            continue
        try:
            subprocess.Popen(  # noqa: S603 — fixed path in our install dir
                [str(exe), "--register"],
                cwd=str(folder),
                creationflags=0x08000000,  # CREATE_NO_WINDOW
            )
        except OSError:
            continue
        started.append(app.app_id)
    return started


def run_cli(argv: list[str]) -> int | None:
    """Handle the registration modes, before any Qt import.

    Args:
        argv: Arguments without the program name.

    Returns:
        An exit code when a CLI mode ran, None when the GUI should
        start.
    """
    from ._core import winreg_assoc  # noqa: PLC0415

    if "--register" in argv:
        for line in winreg_assoc.register(
            make_default="--as-default" in argv
        ):
            print(line)
        print(
            "\nDone. Documents opened via ePy Studio show the editor "
            "selector.\nWindows requires confirming the default in "
            "Settings > Default apps."
        )
        if "--as-default" in argv:
            winreg_assoc.open_default_apps_settings()
        return 0
    if "--unregister" in argv:
        for line in winreg_assoc.unregister():
            print(line)
        return 0
    if "--set-default" in argv:
        winreg_assoc.open_default_apps_settings()
        return 0
    return None


def main() -> int:
    """Run the CLI if one was asked for, otherwise show the selector."""
    argv = sys.argv[1:]
    handled = run_cli(argv)
    if handled is not None:
        return handled

    from PySide6.QtWidgets import QApplication  # noqa: PLC0415

    from ._ui.selector import build_window  # noqa: PLC0415

    files = [item for item in argv if not item.startswith("-")]
    app = QApplication(sys.argv)
    offer_registration()
    window = build_window(files)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
