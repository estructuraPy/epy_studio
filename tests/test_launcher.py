"""The registration CLI, which must answer before any Qt import.

The installer calls --register on a machine where nothing needs a
display. Importing Qt to read a command-line flag is how a post-install
step starts failing on a server, so the ordering in main() is the thing
worth testing: the CLI is handled first, and only then is Qt touched.
"""

from __future__ import annotations

import sys

import pytest

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


def test_register_as_default_also_opens_settings(monkeypatch) -> None:
    # Windows still requires the reader to confirm a default -- Settings
    # is opened to the page that lets them do it.
    from epy_studio._core import winreg_assoc

    monkeypatch.setattr(winreg_assoc, "register", lambda **_k: ["done"])
    opened: list[bool] = []
    monkeypatch.setattr(
        winreg_assoc,
        "open_default_apps_settings",
        lambda: opened.append(True),
    )
    assert launcher.run_cli(["--register", "--as-default"]) == 0
    assert opened == [True]


def test_register_without_as_default_does_not_open_settings(
    monkeypatch,
) -> None:
    # The paired case: --register alone only adds the "Open with" entry.
    from epy_studio._core import winreg_assoc

    monkeypatch.setattr(winreg_assoc, "register", lambda **_k: ["done"])
    opened: list[bool] = []
    monkeypatch.setattr(
        winreg_assoc,
        "open_default_apps_settings",
        lambda: opened.append(True),
    )
    assert launcher.run_cli(["--register"]) == 0
    assert opened == []


def test_set_default_only_opens_settings(monkeypatch) -> None:
    # --set-default never writes the association itself; it just gets
    # the reader to the page where Windows lets them confirm one.
    from epy_studio._core import winreg_assoc

    called: list[str] = []
    monkeypatch.setattr(
        winreg_assoc, "register", lambda **_k: called.append("register")
    )
    monkeypatch.setattr(
        winreg_assoc,
        "open_default_apps_settings",
        lambda: called.append("settings"),
    )
    assert launcher.run_cli(["--set-default"]) == 0
    assert called == ["settings"]


def test_main_builds_and_shows_the_window_when_no_cli_flag_is_given(
    monkeypatch,
) -> None:
    # The GUI path: no CLI flag handled, so main() offers registration,
    # builds the selector with the non-flag arguments as files, shows
    # it, and hands back Qt's own exit code untouched.
    from epy_studio._ui import selector

    monkeypatch.setattr(
        sys, "argv", ["epy_studio", "report.md", "--flag"]
    )
    offered: list[bool] = []
    monkeypatch.setattr(
        launcher, "offer_registration", lambda: offered.append(True)
    )

    built: dict[str, object] = {}

    class _FakeWindow:
        def show(self) -> None:
            built["shown"] = True

    def fake_build_window(files):
        built["files"] = files
        return _FakeWindow()

    monkeypatch.setattr(selector, "build_window", fake_build_window)

    class _FakeApp:
        def __init__(self, argv) -> None:
            built["app_argv"] = argv

        def exec(self) -> int:
            return 42

    from PySide6 import QtWidgets

    monkeypatch.setattr(QtWidgets, "QApplication", _FakeApp)

    assert launcher.main() == 42
    assert offered == [True]
    assert built["files"] == ["report.md"]
    assert built["shown"] is True
    assert built["app_argv"] == sys.argv


def test_dunder_main_runs_main_and_exits_with_its_code(monkeypatch) -> None:
    """The bottom ``if __name__ == "__main__":`` guard.

    ``runpy`` re-executes the whole file, so it defines its OWN fresh
    ``main``/``run_cli`` rather than reusing the ones this test module
    imported -- patching ``launcher.main`` beforehand does not reach
    them. What DOES reach them is ``sys.argv`` and whatever the fresh
    run imports from an already-loaded module, so this drives the run
    through the CLI branch (dispatched entirely through
    ``winreg_assoc``) rather than the GUI branch, which would otherwise
    build a real window and block on a real Qt event loop.
    """
    import runpy

    from epy_studio._core import winreg_assoc

    monkeypatch.setattr(sys, "argv", ["epy_studio", "--unregister"])
    monkeypatch.setattr(winreg_assoc, "unregister", lambda: ["removed"])
    with pytest.raises(SystemExit) as excinfo:
        runpy.run_module("epy_studio.launcher", run_name="__main__")
    assert excinfo.value.code == 0
