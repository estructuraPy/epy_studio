"""Registering and unregistering ePy Studio as a document handler.

``winreg`` is imported inside every function under test, so a stand-in
module injected into ``sys.modules`` answers every read and records every
write -- exactly the pattern ``test_registration_offer.py`` uses. This
suite must never touch the reader's own registry, so ``_Registry`` below
models a full HKCU tree (multiple values per key, subkeys enumerable and
deletable) rather than the flatter stand-in that file needed: unregister()
walks and deletes trees that register() built, and proving that requires
a fake that actually holds structure.
"""

from __future__ import annotations

import sys

import pytest

from epy_studio._core import winreg_assoc


class _FakeKey:
    """Context-managed stand-in for an open registry key handle."""

    def __init__(self, path: str) -> None:
        self.path = path

    def __enter__(self) -> _FakeKey:
        return self

    def __exit__(self, *_exc: object) -> bool:
        return False


class _Registry:
    """An in-memory HKCU tree standing in for the real ``winreg`` module.

    ``register``/``unregister`` only ever touch HKCU, so nothing here
    models another hive. Every function below matches the real
    ``winreg`` signature closely enough for the module under test to
    call it unmodified.
    """

    HKEY_CURRENT_USER = object()
    REG_SZ = 1
    REG_NONE = 0
    KEY_SET_VALUE = 2
    #: `unregister` opens Software\Classes\<ext> for both, because it
    #: reads the default value before deciding whether to delete it.
    KEY_QUERY_VALUE = 1

    def __init__(self) -> None:
        self.tree: dict[str, dict[str, object]] = {}

    def CreateKey(self, _root: object, path: str) -> _FakeKey:  # noqa: N802
        # Real winreg.CreateKey creates every intermediate segment of the
        # path, not just the leaf -- "a\\b\\c" also creates "a" and
        # "a\\b". Without that, _delete_tree's recursive OpenKey on an
        # intermediate segment (e.g. the "shell" in
        # "...\\shell\\open\\command", never created on its own when
        # only the full "shell\\open\\command" path was) raises
        # FileNotFoundError, which _delete_tree swallows -- so the leaf
        # is never reached and never deleted, EnumKey keeps reporting
        # the same child forever, and unregister() spins forever.
        # Measured: this was a genuine infinite loop, not slowness.
        segments = path.split("\\")
        for depth in range(1, len(segments) + 1):
            self.tree.setdefault("\\".join(segments[:depth]), {})
        return _FakeKey(path)

    def OpenKey(  # noqa: N802 - winreg API name
        self, _root: object, path: str, *_args: object
    ) -> _FakeKey:
        if path not in self.tree:
            raise FileNotFoundError(path)
        return _FakeKey(path)

    def SetValueEx(  # noqa: N802 - winreg API name
        self,
        key: _FakeKey,
        name: str,
        _reserved: int,
        _kind: int,
        value: object,
    ) -> None:
        self.tree[key.path][name] = value

    def QueryValueEx(  # noqa: N802 - winreg API name
        self, key: _FakeKey, name: str
    ) -> tuple[object, int]:
        values = self.tree.get(key.path, {})
        if name not in values:
            raise FileNotFoundError(name)
        return values[name], self.REG_SZ

    def DeleteValue(self, key: _FakeKey, name: str) -> None:  # noqa: N802
        values = self.tree.get(key.path, {})
        if name not in values:
            raise FileNotFoundError(name)
        del values[name]

    def DeleteKey(self, _root: object, path: str) -> None:  # noqa: N802
        if path not in self.tree:
            raise FileNotFoundError(path)
        del self.tree[path]

    def EnumKey(self, key: _FakeKey, index: int) -> str:  # noqa: N802
        prefix = key.path + "\\"
        children = sorted(
            {
                path[len(prefix) :].split("\\")[0]
                for path in self.tree
                if path.startswith(prefix)
            }
        )
        if index >= len(children):
            raise OSError("no more data")
        return children[index]


def _use(monkeypatch: pytest.MonkeyPatch, fake: _Registry) -> None:
    monkeypatch.setitem(sys.modules, "winreg", fake)


@pytest.fixture()
def win32(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(winreg_assoc.sys, "platform", "win32")


# ------------------------------------------------- _require_windows


def test_a_non_windows_platform_refuses_to_touch_the_registry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(winreg_assoc.sys, "platform", "linux")
    with pytest.raises(RuntimeError, match="only supported on Windows"):
        winreg_assoc._require_windows()


def test_a_windows_platform_is_let_through(win32: None) -> None:
    # The control: nothing raises, so register()/unregister() below are
    # free to actually reach the registry calls they test.
    winreg_assoc._require_windows()


# ------------------------------------------------- is_registered


def test_is_registered_is_trivially_true_off_windows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Nothing below this check is Windows-specific, so a non-Windows
    # platform must answer without ever importing winreg -- proven here
    # by never injecting a fake: a real import would be the real registry.
    monkeypatch.setattr(winreg_assoc.sys, "platform", "linux")
    assert winreg_assoc.is_registered() is True


# ------------------------------------------------- register(make_default=)


def test_register_with_make_default_writes_the_legacy_default(
    win32: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = _Registry()
    _use(monkeypatch, fake)
    changes = winreg_assoc.register(make_default=True)
    assert any("Wrote legacy default" in line for line in changes)
    for ext in winreg_assoc.EXTENSIONS:
        assert fake.tree[f"Software\\Classes\\{ext}"][""] == (
            winreg_assoc.PROGID
        )


def test_register_without_make_default_leaves_the_legacy_default_alone(
    win32: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The paired case: the default handler is the user's call (Windows
    # requires confirming it in Settings anyway), so the plain register
    # must not write it. The key itself still exists -- registering the
    # OpenWithProgids entry creates it as an ancestor, same as the real
    # registry does for any key under it -- but its "(Default)" value,
    # which is what actually makes it the handler, must stay unset.
    fake = _Registry()
    _use(monkeypatch, fake)
    changes = winreg_assoc.register(make_default=False)
    assert not any("Wrote legacy default" in line for line in changes)
    for ext in winreg_assoc.EXTENSIONS:
        assert "" not in fake.tree.get(f"Software\\Classes\\{ext}", {})


# ------------------------------------------------- unregister


def test_unregister_removes_the_application_progid_and_capabilities_trees(
    win32: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = _Registry()
    _use(monkeypatch, fake)
    winreg_assoc.register(make_default=False)
    assert fake.tree, "sanity: register() must have written something"

    removed = winreg_assoc.unregister()

    assert not any(
        path.startswith(f"Software\\Classes\\{winreg_assoc.APP_KEY}")
        for path in fake.tree
    )
    assert not any(
        path.startswith(f"Software\\Classes\\{winreg_assoc.PROGID}")
        for path in fake.tree
    )
    assert not any(
        path.startswith(f"Software\\{winreg_assoc.APP_NAME}")
        for path in fake.tree
    )
    assert winreg_assoc.APP_NAME not in fake.tree.get(
        "Software\\RegisteredApplications", {}
    )
    for ext in winreg_assoc.EXTENSIONS:
        assert winreg_assoc.PROGID not in fake.tree.get(
            f"Software\\Classes\\{ext}\\OpenWithProgids", {}
        )
    assert any("Removed" in line for line in removed)


def test_unregister_is_a_quiet_no_op_when_nothing_was_ever_registered(
    win32: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The paired case: a machine that never ran --register must not
    # raise walking trees that do not exist, and must not claim it
    # removed anything.
    fake = _Registry()
    _use(monkeypatch, fake)
    assert winreg_assoc.unregister() == []


def test_unregister_removes_the_legacy_default_it_wrote(
    win32: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``unregister`` says it removes every key ``register`` wrote.

    It used to leave one behind. ``register(make_default=True)`` sets the
    "(Default)" value of ``Software\\Classes\\<ext>`` to ``PROGID``, and
    ``unregister`` walked only the ``APP_KEY`` / ``PROGID`` / ``APP_NAME``
    trees and the ``OpenWithProgids`` values -- never
    ``Software\\Classes\\<ext>`` itself. A machine that accepted "make
    default" and later uninstalled kept Explorer pointed at a ProgID that
    had been deleted everywhere else, so .md/.markdown/.qmd opened with an
    application that is gone.
    """
    fake = _Registry()
    _use(monkeypatch, fake)
    winreg_assoc.register(make_default=True)
    for ext in winreg_assoc.EXTENSIONS:
        assert (fake.tree[f"Software\\Classes\\{ext}"][""]
                == winreg_assoc.PROGID)

    winreg_assoc.unregister()

    for ext in winreg_assoc.EXTENSIONS:
        assert "" not in fake.tree.get(f"Software\\Classes\\{ext}", {}), (
            f"{ext} still names a default handler"
        )


def test_unregister_does_not_take_another_applications_default(
    win32: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The counter-example, and the reason the removal is conditional:
    another editor may have taken the default since. Removing someone
    else's association is a worse bug than leaving ours behind."""
    fake = _Registry()
    _use(monkeypatch, fake)
    winreg_assoc.register(make_default=True)
    ext = winreg_assoc.EXTENSIONS[0]
    fake.tree[f"Software\\Classes\\{ext}"][""] = "SomeOtherEditor.Markdown"

    winreg_assoc.unregister()

    assert (fake.tree[f"Software\\Classes\\{ext}"][""]
            == "SomeOtherEditor.Markdown")


# ------------------------------------------------- open_default_apps_settings


def test_open_default_apps_settings_refuses_off_windows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(winreg_assoc.sys, "platform", "linux")
    with pytest.raises(RuntimeError, match="only supported on Windows"):
        winreg_assoc.open_default_apps_settings()


def test_open_default_apps_settings_launches_the_settings_uri(
    win32: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    import subprocess

    calls: list[tuple[list[str], dict[str, object]]] = []
    monkeypatch.setattr(
        subprocess,
        "Popen",
        lambda cmd, **kwargs: calls.append((cmd, kwargs)),
    )
    winreg_assoc.open_default_apps_settings()
    assert calls
    cmd, _kwargs = calls[0]
    assert cmd == ["cmd", "/c", "start", "ms-settings:defaultapps"]
