"""Does this bundle carry what the release promised?

``build.py`` refuses to build without a REQUIRED application and skips
an OPTIONAL one by name, printing a line. That is the right rule for a
build: an optional application is optional because its repository is
private, so a checkout that lacks it is a normal checkout, not a broken
one.

A RELEASE is the other question. Cutting an installer is exactly the
moment nobody re-reads the build log, and a bundle three applications
short looks identical from the outside to a complete one -- same
installer name, same launcher, same shortcut. So the promise is written
down in ``release.epyson`` and checked here, against the executables
that were actually produced.

Run from the repository root, after ``build.py``::

    python windows/build_support/verify_release.py
    python windows/build_support/verify_release.py --target <folder>

Exit status 1 names every promised application the bundle lacks.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "release.epyson"
CATALOG = ROOT / "src" / "epy_studio" / "_config" / "apps.epyson"
DEFAULT_TARGET = ROOT / "dist" / "epy_studio"


def promised(manifest: Path = MANIFEST) -> list[str]:
    """Return the application ids this release promises to carry.

    Args:
        manifest: The release manifest to read.

    Returns:
        The ids, in the order written.

    Raises:
        SystemExit: When the manifest is missing, or promises an
            application the catalog does not define. An id nobody
            recognises is a typo, and a typo here would quietly promise
            nothing at all.
    """
    if not manifest.is_file():
        raise SystemExit(f"no release manifest at {manifest}")
    ids = [str(item) for item in json.loads(
        manifest.read_text(encoding="utf-8")
    )["must_carry"]]
    known = {
        str(app["id"])
        for app in json.loads(CATALOG.read_text(encoding="utf-8"))["apps"]
    }
    unknown = [app_id for app_id in ids if app_id not in known]
    if unknown:
        raise SystemExit(
            f"{manifest.name} promises {', '.join(unknown)}, which the "
            f"catalog does not define"
        )
    return ids


def main(argv: list[str] | None = None) -> int:
    """Check the produced bundle against the promise; say what is short."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", type=Path, default=DEFAULT_TARGET)
    args = parser.parse_args(argv)
    target: Path = args.target
    if not target.is_dir():
        print(f"not built: {target}")
        return 1

    missing = [
        app_id
        for app_id in promised()
        if not (target / f"{app_id}.exe").is_file()
    ]
    if missing:
        print(f"this release promises {len(promised())} application(s) and")
        print(f"{target} is short of:")
        for app_id in missing:
            print(f"  - {app_id}.exe")
        print(
            "Either build with that sibling checkout present, or remove it "
            "from release.epyson because this release no longer carries it."
        )
        return 1
    names = ", ".join(promised())
    print(f"release promise kept: {names}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
