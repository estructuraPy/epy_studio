"""The registration CLI, which must answer before any Qt import.

The installer calls --register on a machine where nothing needs a
display. Importing Qt to read a command-line flag is how a post-install
step starts failing on a server, so the ordering in main() is the thing
worth testing: the CLI is handled first, and only then is Qt touched.
"""

from __future__ import annotations

import sys

from epy_studio import launcher


def test_no_flags_means_the_gui_should_start() -> None:
    # None is the signal "nothing was handled, go build a window".
    assert launcher.run_cli([]) is None


def test_a_file_argument_is_not_a_cli_mode() -> None:
    # Documents arrive through the file association; they are forwarded
    # to whichever application the reader picks, not handled here.
    assert launcher.run_cli(["report.md"]) is None


def test_register_is_handled_without_qt(monkeypatch) -> None:
    # The property that matters: the CLI answers before Qt is imported.
    # Asserted by removing Qt from sys.modules and refusing the import.
    import builtins

    from epy_studio._core import winreg_assoc

    monkeypatch.setattr(winreg_assoc, "register", lambda **_k: ["done"])
    monkeypatch.setattr(
        winreg_assoc, "open_default_apps_settings", lambda: None
    )
    for name in [n for n in sys.modules if n.startswith("PySide6")]:
        monkeypatch.delitem(sys.modules, name, raising=False)

    real = builtins.__import__

    def refuse(name, *args, **kwargs):
        if name.split(".")[0] == "PySide6":
            raise AssertionError("the CLI imported Qt")
        return real(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", refuse)
    assert launcher.run_cli(["--register"]) == 0


def test_unregister_is_handled_too(monkeypatch) -> None:
    from epy_studio._core import winreg_assoc

    monkeypatch.setattr(winreg_assoc, "unregister", lambda: ["removed"])
    assert launcher.run_cli(["--unregister"]) == 0
