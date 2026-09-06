"""Is the bundle that is INSTALLED the one that was built and tested?

``build.py`` probes the executables in ``dist/``. The installer then
copies them, and a probe of ``dist/`` says nothing about what a stale or
interrupted install left under ``%LOCALAPPDATA%``. This reads the
installed executables directly, with the same PYZ probe, and then asks
the registry whether the file types the bundle claims are pointed at
THOSE executables -- a silent install registers nothing (``skipifsilent``
on every ``[Run]`` entry), so ``epy_draft.exe --register`` has to have
been run, and this is how you know it was.

Usage, from the repository root::

    python windows/build_support/probe_installed.py
    python windows/build_support/probe_installed.py --target <folder>

Exit status 1 names what is missing or stale. Run against a previous
release it MUST fail -- that is the control that says it can.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1]))
import pyz_probe  # noqa: E402 - needs HERE on sys.path first

DEFAULT_TARGET = (
    Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "epy_studio"
)

DRAWING_READER: tuple[tuple[str, str, str], ...] = (
    # Our reader's own literal is already a build.py row; these are the
    # library it imports lazily, which no literal of ours can vouch for.
    ("epy_draft", "ezdxf", "readfile"),
    ("epy_draft", "ezdxf.entities", "MText"),
)

REGISTERED: tuple[tuple[str, str], ...] = (
    # (extension, the exe its open command must name)
    (".kepy", "epy_draft.exe"),
    (".zepy", "epy_draft.exe"),
)

_CLASSES = r"HKCU\Software\Classes"


def _shipped_fixes() -> tuple[tuple[str, str, str], ...]:
    """Return build.py's own probe rows, so the two lists cannot drift."""
    import build  # noqa: PLC0415 - the repo root is on sys.path above

    return tuple(build.SHIPPED_FIXES)


def _reg_default(key: str) -> str:
    """Return a registry key's default value, or "" when absent."""
    try:
        out = subprocess.run(
            ["reg", "query", key, "/ve"],
            capture_output=True, text=True, check=False,
        ).stdout
    except OSError:
        return ""
    value = ""
    for line in out.splitlines():
        if "REG_SZ" in line:
            value = line.split("REG_SZ", 1)[1].strip()
    return value


def _open_command(extension: str) -> str:
    """Return the registry's open command for ``extension``, or ""."""
    progid = _reg_default(rf"{_CLASSES}\{extension}")
    if not progid:
        return ""
    return _reg_default(rf"{_CLASSES}\{progid}\shell\open\command")


def main(argv: list[str] | None = None) -> int:
    """Probe the installed bundle and the registry; say what is wrong."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", type=Path, default=DEFAULT_TARGET)
    args = parser.parse_args(argv)
    target: Path = args.target
    if not target.is_dir():
        print(f"not installed: {target}")
        return 1

    problems: list[str] = []
    rows = _shipped_fixes() + DRAWING_READER
    for stem, module, literal in rows:
        exe = target / f"{stem}.exe"
        if not exe.is_file():
            problems.append(f"{exe.name}: not installed")
            continue
        try:
            if not pyz_probe.carries(exe, module, literal):
                problems.append(f"{exe.name}: {module} lacks {literal!r}")
        except pyz_probe.BundleProbeError as exc:
            problems.append(f"{exe.name}: {exc}")
    present = len(rows) - len(problems)
    print(f"PYZ: {present}/{len(rows)} literal(s) present in {target}")

    for extension, exe_name in REGISTERED:
        command = _open_command(extension)
        if not command:
            problems.append(
                f"{extension}: not registered (run epy_draft.exe --register)"
            )
        elif exe_name.lower() not in command.lower():
            problems.append(
                f"{extension}: opens with {command!r}, not {exe_name}"
            )
        elif str(target).lower() not in command.lower():
            problems.append(
                f"{extension}: opens {command!r}, outside {target}"
            )
        else:
            print(f"registry: {extension} -> {command}")

    if problems:
        print("the installed bundle is not the one that was built and tested:")
        for line in problems:
            print(f"  - {line}")
        return 1
    print("installed bundle verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
