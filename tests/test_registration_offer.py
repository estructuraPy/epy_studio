"""The first-run registration offer, and the six times it must stay quiet.

Every ``[Run]`` entry in the installer carries ``skipifsilent``, so a
silent deployment installs ePy Studio and registers nothing: documents it
was installed for keep opening in whatever handled them before. The offer
below is the only moment a person is present to answer.

The registry is never touched here. ``winreg`` is imported inside the
functions under test, so a stand-in module injected into ``sys.modules``
answers every read and records every write -- which is what lets these
tests assert the one property that matters most: when the reader says no,
NOTHING is written.
"""

from __future__ import annotations

import sys
from typing import Any

import pytest

from epy_studio import launcher
from epy_studio._core import winreg_assoc

# conftest pins ICU before any test module loads, which is what lets
# PySide6 import under conda. Qt is a hard dependency of this package, so
# a failure to import it is a broken environment and must be read as one:
# skipping here would turn the whole file green on a machine where the
# launcher cannot start.


class _FakeKey:
    """Context-managed stand-in for an open registry key."""

    def __init__(self, path: str) -> None:
        self.path = path

    def __enter__(self) -> _FakeKey:
        return self

    def __exit__(self, *_exc: object) -> bool:
        return False


class _FakeWinreg:
    """Just enough of ``winreg`` to answer and record."""

    HKEY_CURRENT_USER = 0
    REG_SZ = 1
    REG_NONE = 0
    KEY_SET_VALUE = 2

    def __init__(self, values: dict[str, str] | None = None) -> None:
        self.values = dict(values or {})
        self.writes: list[tuple[str, str, str]] = []
        self.read_error: type[OSError] | None = None

    def OpenKey(  # noqa: N802 - winreg API name
        self, _root: int, path: str, *_args: object
    ) -> _FakeKey:
        if self.read_error is not None:
            raise self.read_error("blocked by policy")
        if path not in self.values:
            raise FileNotFoundError(path)
        return _FakeKey(path)

    def QueryValueEx(  # noqa: N802 - winreg API name
        self, key: _FakeKey, _name: str
    ) -> tuple[str, int]:
        return self.values[key.path], self.REG_SZ

    def CreateKey(  # noqa: N802 - winreg API name
        self, _root: int, path: str
    ) -> _FakeKey:
        return _FakeKey(path)

    def SetValueEx(  # noqa: N802 - winreg API name
        self, key: _FakeKey, name: str, _reserved: int, _kind: int,
        value: object,
    ) -> None:
        self.writes.append((key.path, name, str(value)))


class _ScratchSettings:
    """In-memory QSettings stand-in sharing one dict per test."""

    def __init__(self, store: dict[str, Any]) -> None:
        self._store = store

    def value(self, key: str, default: Any = None) -> Any:
        return self._store.get(key, default)

    def setValue(self, key: str, value: Any) -> None:  # noqa: N802 - Qt API
        self._store[key] = value


@pytest.fixture(scope="module")
def qt_app() -> Any:
    """One offscreen QApplication for the file."""
    import os

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


@pytest.fixture
def installed(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Pretend to be a frozen Windows install with a scratch settings tree."""
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(
        winreg_assoc.sys, "platform", "win32", raising=False
    )
    store: dict[str, Any] = {}
    from PySide6 import QtCore

    monkeypatch.setattr(
        QtCore, "QSettings", lambda *_a: _ScratchSettings(store)
    )
    return store


def _use(monkeypatch: pytest.MonkeyPatch, fake: _FakeWinreg) -> None:
    monkeypatch.setitem(sys.modules, "winreg", fake)


def _answer(monkeypatch: pytest.MonkeyPatch, yes: bool) -> list[str]:
    """Make the question answer itself, recording that it was asked."""
    from PySide6.QtWidgets import QMessageBox

    asked: list[str] = []

    def _question(_parent: object, title: str, *_rest: object) -> object:
        asked.append(title)
        return (
            QMessageBox.StandardButton.Yes
            if yes
            else QMessageBox.StandardButton.No
        )

    monkeypatch.setattr(QMessageBox, "question", staticmethod(_question))
    return asked


def _command_key() -> str:
    return f"Software\\Classes\\{winreg_assoc.PROGID}\\shell\\open\\command"


# ------------------------------------------------- is_registered


def test_a_missing_progid_reads_as_unregistered(
    monkeypatch: pytest.MonkeyPatch
) -> None:
    # This is the silent install: the bundle is on disk and nothing in
    # the registry points at it.
    monkeypatch.setattr(winreg_assoc.sys, "platform", "win32")
    _use(monkeypatch, _FakeWinreg({}))
    assert winreg_assoc.is_registered() is False


def test_a_command_naming_another_folder_reads_as_unregistered(
    monkeypatch: pytest.MonkeyPatch
) -> None:
    # A reinstall into a different folder leaves the old command behind:
    # a double-clicked document would start a program that is gone.
    monkeypatch.setattr(winreg_assoc.sys, "platform", "win32")
    _use(
        monkeypatch,
        _FakeWinreg({_command_key(): '"C:\\Old\\epy_studio.exe" "%1"'}),
    )
    assert winreg_assoc.is_registered() is False


def test_our_own_command_reads_as_registered(
    monkeypatch: pytest.MonkeyPatch
) -> None:
    # CONTROL: a helper that always answered False would nag every start.
    monkeypatch.setattr(winreg_assoc.sys, "platform", "win32")
    _use(
        monkeypatch,
        _FakeWinreg({_command_key(): winreg_assoc._open_command()}),
    )
    assert winreg_assoc.is_registered() is True


def test_a_registry_that_cannot_be_read_is_left_alone(
    monkeypatch: pytest.MonkeyPatch
) -> None:
    # A locked-down machine must not be asked the same question forever.
    monkeypatch.setattr(winreg_assoc.sys, "platform", "win32")
    fake = _FakeWinreg({})
    fake.read_error = PermissionError
    _use(monkeypatch, fake)
    assert winreg_assoc.is_registered() is True


# ------------------------------------------------- the offer


def test_an_unregistered_install_offers_and_registers(
    qt_app: Any, installed: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    # Without this a silent install leaves every .md opening in whatever
    # handled it before, with nothing on screen to say why.
    fake = _FakeWinreg({})
    _use(monkeypatch, fake)
    asked = _answer(monkeypatch, yes=True)
    monkeypatch.setattr(launcher, "_register_siblings", lambda: [])

    assert launcher.offer_registration() == "done"
    assert len(asked) == 1
    assert any(
        winreg_assoc.PROGID in path for path, _n, _v in fake.writes
    )
    assert installed[launcher._PROMPT_KEY] == "done"


def test_no_writes_nothing_and_is_never_asked_again(
    qt_app: Any, installed: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    # Consent is the whole point: a refusal must leave the registry
    # untouched, and must not come back on the next start.
    fake = _FakeWinreg({})
    _use(monkeypatch, fake)
    asked = _answer(monkeypatch, yes=False)

    assert launcher.offer_registration() == "declined"
    assert fake.writes == []
    assert installed[launcher._PROMPT_KEY] == "declined"
    assert launcher.offer_registration() == "skipped"
    assert len(asked) == 1


def test_an_already_registered_install_is_not_asked(
    qt_app: Any, installed: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = _FakeWinreg({_command_key(): winreg_assoc._open_command()})
    _use(monkeypatch, fake)
    asked = _answer(monkeypatch, yes=True)

    assert launcher.offer_registration() == "skipped"
    assert asked == []
    assert fake.writes == []


def test_a_source_checkout_never_writes_the_registry(
    qt_app: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The command a checkout would store points at the interpreter, not
    # at an installed bundle: it would break every document it claimed.
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    monkeypatch.setattr(sys, "platform", "win32")
    fake = _FakeWinreg({})
    _use(monkeypatch, fake)
    asked = _answer(monkeypatch, yes=True)

    assert launcher.offer_registration() == "skipped"
    assert asked == []
    assert fake.writes == []


def test_a_non_windows_run_never_asks(
    qt_app: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "platform", "linux")
    asked = _answer(monkeypatch, yes=True)

    assert launcher.offer_registration() == "skipped"
    assert asked == []


def test_the_siblings_are_asked_to_register_themselves(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    # The editors own their own extensions and ProgIDs; the launcher
    # cannot register .md for epy_reports on its behalf. A component the
    # reader did not install is skipped, not an error.
    from epy_studio._core import _catalog

    ids = [app.app_id for app in _catalog.apps()]
    (tmp_path / f"{ids[0]}.exe").write_bytes(b"MZ")
    monkeypatch.setattr(_catalog, "install_dir", lambda: tmp_path)
    started: list[list[str]] = []

    import subprocess

    monkeypatch.setattr(
        subprocess, "Popen", lambda cmd, **_k: started.append(list(cmd))
    )
    assert launcher._register_siblings() == [ids[0]]
    assert started[0][1] == "--register"
