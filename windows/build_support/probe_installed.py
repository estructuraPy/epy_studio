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

CONVENTIONAL_TARGET = (
    Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "epy_studio"
)
"""Where a default install lands. A fallback, never the answer."""

_UNINSTALL = (
    r"HKCU\Software\Microsoft\Windows\CurrentVersion\Uninstall"
)


def installed_location() -> Path | None:
    """Return where the installer RECORDED that it wrote, or None.

    Not where an install conventionally goes. Inno remembers the
    directory, the setup type and the component list from whatever ran
    last, so a silent install can land somewhere nobody asked for --
    measured: one inherited a scratch directory from a subset proof,
    and a probe pointed at the usual path by hand then verified the
    PREVIOUS release and called the bundle sound.

    Returns:
        The recorded location, or ``None`` when nothing is registered.
    """
    listing = subprocess.run(
        ["reg", "query", _UNINSTALL],
        capture_output=True, text=True, check=False,
    ).stdout
    for key in listing.splitlines():
        key = key.strip()
        if not key.startswith("HKEY_"):
            continue
        values = subprocess.run(
            ["reg", "query", key],
            capture_output=True, text=True, check=False,
        ).stdout
        if "ePy Studio" not in values:
            continue
        for line in values.splitlines():
            if "InstallLocation" in line and "REG_SZ" in line:
                where = line.split("REG_SZ", 1)[1].strip()
                if where:
                    return Path(where)
    return None

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


def _optional_ids() -> frozenset[str]:
    """Return build.py's own notion of which applications may be absent."""
    import build  # noqa: PLC0415 - the repo root is on sys.path above

    return build._optional_ids()  # noqa: SLF001 - the same rule, one home


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
    parser.add_argument(
        "--target",
        type=Path,
        default=None,
        help=(
            "Where to probe. Defaults to the location the installer "
            "RECORDED, which is the only one it can be trusted to have "
            "written."
        ),
    )
    args = parser.parse_args(argv)
    recorded = installed_location()
    target: Path = args.target or recorded or CONVENTIONAL_TARGET
    if recorded is None:
        print("nothing registered as installed; probing " + str(target))
    elif args.target is not None and (
        Path(str(args.target).rstrip("\\/")).resolve()
        != Path(str(recorded).rstrip("\\/")).resolve()
    ):
        # The false green this exists to refuse: a directory that was
        # asked for is not a directory the installer wrote.
        print(
            f"refusing to probe {target}: the installer recorded "
            f"{recorded}. Probing a directory the installer did not "
            f"write is how a stale bundle passes every check."
        )
        return 1
    if not target.is_dir():
        print(f"not installed: {target}")
        return 1

    problems: list[str] = []
    skipped = 0
    optional = _optional_ids()
    rows = _shipped_fixes() + DRAWING_READER
    for stem, module, literal in rows:
        exe = target / f"{stem}.exe"
        if not exe.is_file():
            if stem in optional:
                # The owner hands this one out; a machine without it
                # is not a stale install.
                skipped += 1
                continue
            problems.append(f"{exe.name}: not installed")
            continue
        try:
            if not pyz_probe.carries(exe, module, literal):
                problems.append(f"{exe.name}: {module} lacks {literal!r}")
        except pyz_probe.BundleProbeError as exc:
            problems.append(f"{exe.name}: {exc}")
    present = len(rows) - len(problems) - skipped
    note = f"  ({skipped} skipped: optional, not installed)" if skipped else ""
    print(
        f"PYZ: {present}/{len(rows) - skipped} literal(s) present in {target}"
        f"{note}"
    )

    for extension, exe_name in REGISTERED:
        if not (target / exe_name).is_file():
            # The application that claims this type is not installed.
            # Only an OPTIONAL one can be legitimately absent, and the
            # loop above has already refused a required one by name, so
            # reaching here means the release does not carry it and the
            # type belongs to nobody.
            print(
                f"registry: {extension} -> skipped, "
                f"{exe_name} not installed"
            )
            continue
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
