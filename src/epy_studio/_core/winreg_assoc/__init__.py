r"""Windows file-association helpers for ePy Studio (HKCU only).

Registers the Studio launcher as a handler for ``.md`` / ``.markdown``
/ ``.qmd``: double-clicking a document opens the selector, which
forwards the file to whichever editor the user picks. Mirrors the key
layout of ``epy_reports._core.winreg_assoc`` with the Studio identity.

Since Windows 8 the actual default is gated by a per-user ``UserChoice``
key signed with a hash only Windows can produce — no installer can set
a default silently. ``register(make_default=True)`` writes the legacy
default handler and the Capabilities tree so ePy Studio appears in
*Settings > Default apps*; the user confirms it there (or via
*Open with > Always use this app*).
"""

from __future__ import annotations

import sys

PROGID = "epy_studio.Document.1"
APP_NAME = "epy_studio"
APP_DISPLAY = "ePy Studio"
APP_DESCRIPTION = (
    "Launcher for the ePy document editors (reports, slides, papers)."
)
APP_KEY = f"Applications\\{APP_NAME}.exe"
EXTENSIONS = (".md", ".markdown", ".qmd")
EXT_DESCRIPTION = "Markdown/Quarto Document"


def _require_windows() -> None:
    if sys.platform != "win32":
        raise RuntimeError("File association is only supported on Windows.")


def _open_command() -> str:
    """Shell ``open`` command: the frozen launcher plus the document."""
    return f'"{sys.executable}" "%1"'


def _icon_source() -> str:
    return f'"{sys.executable}",0'


def _set_value(key: object, name: str, value: str) -> None:
    """Write one string value under an already-open registry key.

    Args:
        key: The open key. Typed ``object`` because ``winreg.HKEYType``
            only exists on Windows, and this module is imported (never
            called) elsewhere; the calls below are what pin the shape.
        name: Value name. Empty means the key's default value.
        value: The string to store.
    """
    import winreg

    # The stub types the key as HKEYType, which exists only on Windows.
    # Naming it in the signature would make this module unimportable
    # everywhere else, and it is imported (never called) there.
    winreg.SetValueEx(key, name, 0, winreg.REG_SZ, value)  # pyright: ignore[reportArgumentType, reportCallIssue] - the key is Windows-only in the stub


def is_registered() -> bool:
    """Return whether this executable is the handler behind the ProgID.

    A missing key means nothing ever registered: every ``[Run]`` entry in
    the installer carries ``skipifsilent``, so a silent deployment leaves
    documents unhandled. A key naming a DIFFERENT executable means the
    bundle moved -- a reinstall into another folder leaves the old command
    behind, and a document opened from the shell then starts a program
    that is no longer there.

    Any other registry error answers ``True``. A machine whose policy
    blocks HKCU must never be asked the same question on every start.

    Returns:
        ``True`` when the stored open command is this executable, or when
        the registry could not be read at all.
    """
    if sys.platform != "win32":
        return True
    import winreg

    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            f"Software\\Classes\\{PROGID}\\shell\\open\\command",
        ) as key:
            stored, _ = winreg.QueryValueEx(key, "")
    except FileNotFoundError:
        return False
    except OSError:
        return True
    return str(stored).strip().lower() == _open_command().strip().lower()


def register(make_default: bool = False) -> list[str]:
    """Register ePy Studio for Markdown documents in HKCU.

    Args:
        make_default: Also write the legacy default handler (user still
            confirms in Settings — see module docstring).

    Returns:
        Human-readable lines describing what was changed.
    """
    _require_windows()
    import winreg

    cmd = _open_command()
    icon = _icon_source()
    changes: list[str] = []

    app_root = f"Software\\Classes\\{APP_KEY}"
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, app_root) as k:
        _set_value(k, "FriendlyAppName", APP_DISPLAY)
        _set_value(k, "ApplicationName", APP_DISPLAY)
        _set_value(k, "ApplicationDescription", APP_DESCRIPTION)
    with winreg.CreateKey(
        winreg.HKEY_CURRENT_USER, f"{app_root}\\DefaultIcon"
    ) as k:
        _set_value(k, "", icon)
    with winreg.CreateKey(
        winreg.HKEY_CURRENT_USER, f"{app_root}\\shell\\open\\command"
    ) as k:
        _set_value(k, "", cmd)
    with winreg.CreateKey(
        winreg.HKEY_CURRENT_USER, f"{app_root}\\SupportedTypes"
    ) as k:
        for ext in EXTENSIONS:
            _set_value(k, ext, "")
    changes.append(f"Registered application: {app_root}")

    progid_root = f"Software\\Classes\\{PROGID}"
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, progid_root) as k:
        _set_value(k, "", EXT_DESCRIPTION)
    with winreg.CreateKey(
        winreg.HKEY_CURRENT_USER, f"{progid_root}\\DefaultIcon"
    ) as k:
        _set_value(k, "", icon)
    with winreg.CreateKey(
        winreg.HKEY_CURRENT_USER, f"{progid_root}\\shell\\open\\command"
    ) as k:
        _set_value(k, "", cmd)
    changes.append(f"Registered ProgID: {progid_root}")

    caps_root = f"Software\\{APP_NAME}\\Capabilities"
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, caps_root) as k:
        _set_value(k, "ApplicationName", APP_DISPLAY)
        _set_value(k, "ApplicationDescription", APP_DESCRIPTION)
    with winreg.CreateKey(
        winreg.HKEY_CURRENT_USER, f"{caps_root}\\FileAssociations"
    ) as k:
        for ext in EXTENSIONS:
            _set_value(k, ext, PROGID)
    with winreg.CreateKey(
        winreg.HKEY_CURRENT_USER, "Software\\RegisteredApplications"
    ) as k:
        _set_value(k, APP_NAME, caps_root)
    changes.append(f"Registered application capabilities: {caps_root}")

    for ext in EXTENSIONS:
        ext_root = f"Software\\Classes\\{ext}\\OpenWithProgids"
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, ext_root) as k:
            winreg.SetValueEx(k, PROGID, 0, winreg.REG_NONE, b"")
        changes.append(f"Added {PROGID} to OpenWithProgids for {ext}")
        if make_default:
            with winreg.CreateKey(
                winreg.HKEY_CURRENT_USER, f"Software\\Classes\\{ext}"
            ) as k:
                _set_value(k, "", PROGID)
            changes.append(
                f"Wrote legacy default for {ext} -> {PROGID} "
                "(Windows may still require user confirmation)."
            )
    return changes


def unregister() -> list[str]:
    """Remove every key written by :func:`register`."""
    _require_windows()
    import winreg

    changes: list[str] = []

    def _delete_tree(root: int, path: str) -> None:
        try:
            with winreg.OpenKey(root, path) as k:
                while True:
                    try:
                        sub = winreg.EnumKey(k, 0)
                    except OSError:
                        break
                    _delete_tree(root, f"{path}\\{sub}")
            winreg.DeleteKey(root, path)
            changes.append(f"Removed {path}")
        except FileNotFoundError:
            pass

    _delete_tree(winreg.HKEY_CURRENT_USER, f"Software\\Classes\\{APP_KEY}")
    _delete_tree(winreg.HKEY_CURRENT_USER, f"Software\\Classes\\{PROGID}")
    _delete_tree(winreg.HKEY_CURRENT_USER, f"Software\\{APP_NAME}")
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            "Software\\RegisteredApplications",
            0,
            winreg.KEY_SET_VALUE,
        ) as k:
            winreg.DeleteValue(k, APP_NAME)
            changes.append("Removed RegisteredApplications entry")
    except FileNotFoundError:
        pass
    for ext in EXTENSIONS:
        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                f"Software\\Classes\\{ext}\\OpenWithProgids",
                0,
                winreg.KEY_SET_VALUE,
            ) as k:
                winreg.DeleteValue(k, PROGID)
                changes.append(f"Removed OpenWithProgids entry for {ext}")
        except FileNotFoundError:
            pass
    return changes


def open_default_apps_settings() -> None:
    """Open Windows Settings at the Default Apps page."""
    _require_windows()
    import subprocess

    subprocess.Popen(  # noqa: S603, S607 — fixed ms-settings URI
        ["cmd", "/c", "start", "ms-settings:defaultapps"],
        creationflags=0x08000000,  # CREATE_NO_WINDOW
    )
