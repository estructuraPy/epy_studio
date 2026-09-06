"""Does the built ePy Draft actually carry its drawing reader?

``ezdxf`` is an optional extra with no PyInstaller hook, and it ships
compiled accelerators (``ezdxf/acc/*.pyd``) beside pure Python. The
literal probe in ``build.py`` proves OUR module is in the PYZ; it cannot
prove the library it imports lazily came along. A bundle missing it
would not fail to build and would not fail to start -- the ``.dxf``
suffix would refuse by name on the first drawing, on the user's machine,
which is the wrong place to learn it.

Run from the repository root after ``build.py``::

    python windows/build_support/probe_dxf_reader.py

Exit status 1 names what is missing.
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import pyz_probe  # noqa: E402 - needs HERE on sys.path first

ROOT = HERE.parents[1]
TARGET = ROOT / "dist" / "epy_studio"
EXE = TARGET / "epy_draft.exe"

REQUIRED: tuple[tuple[str, str], ...] = (
    # Our reader, and the two ezdxf entry points it calls.
    ("epy_draft._core._index.extract", "_DXF_SUFFIX"),
    ("ezdxf", "readfile"),
    ("ezdxf.entities", "MText"),
)


def main() -> int:
    """Probe the bundle and say what it lacks."""
    if not EXE.is_file():
        print(f"not produced: {EXE}")
        return 1
    missing: list[str] = []
    for dotted, literal in REQUIRED:
        try:
            if not pyz_probe.carries(EXE, dotted, literal):
                missing.append(f"{dotted} lacks {literal!r}")
        except pyz_probe.BundleProbeError as exc:
            missing.append(f"{dotted}: {exc}")
    # The accelerators are OPTIONAL to ezdxf -- it falls back to pure
    # Python when they are absent -- so their absence is reported, not
    # failed. A drawing still reads; it reads slower.
    acc = sorted((TARGET / "_internal" / "ezdxf" / "acc").glob("*.pyd"))
    print(
        f"ezdxf accelerators on disk: {len(acc)}"
        + ("" if acc else "  (pure-Python fallback; drawings read slower)")
    )
    if missing:
        print("the built epy_draft.exe cannot read drawings:")
        for line in missing:
            print(f"  - {line}")
        return 1
    print(
        f"drawing reader verified: {len(REQUIRED)} literal(s) present in "
        f"{EXE.name}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
