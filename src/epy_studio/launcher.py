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

__all__ = ["main"]


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
    window = build_window(files)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
