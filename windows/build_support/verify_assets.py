"""Verify that every app's build-time data tree reached the frozen bundle."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SUITE = ROOT.parent
CATALOG = ROOT / "src" / "epy_studio" / "_config" / "apps.epyson"
DEFAULT_TARGET = ROOT / "dist" / "epy_studio" / "_internal"
_SKIP = {"__pycache__", ".pytest_cache"}


def _files(root: Path) -> dict[str, int]:
    if not root.is_dir():
        return {}
    return {
        path.relative_to(root).as_posix(): path.stat().st_size
        for path in root.rglob("*")
        if path.is_file()
        and path.suffix != ".py"
        and not any(part in _SKIP for part in path.relative_to(root).parts)
    }


def _source_root(app_id: str) -> Path:
    for base in (SUITE / app_id, SUITE / "_deps" / app_id):
        candidate = base / "src" / app_id / "_config"
        if candidate.is_dir():
            return candidate
    return SUITE / app_id / "src" / app_id / "_config"


def main(argv: list[str] | None = None) -> int:
    """Exit non-zero when an app's `_config` data differs from the bundle."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", type=Path, default=DEFAULT_TARGET)
    args = parser.parse_args(argv)
    apps = json.loads(CATALOG.read_text(encoding="utf-8"))["apps"]
    problems: list[str] = []
    checked = 0
    for app in apps:
        app_id = str(app.get("id", ""))
        source = _source_root(app_id)
        if not source.is_dir():
            continue
        checked += 1
        expected = _files(source)
        actual = _files(args.target / app_id / "_config")
        missing = sorted(set(expected) - set(actual))
        extra = sorted(set(actual) - set(expected))
        changed = sorted(
            name for name in set(expected) & set(actual)
            if expected[name] != actual[name]
        )
        for name in missing:
            problems.append(f"{app_id}: missing {name}")
        for name in extra:
            problems.append(f"{app_id}: unexpected {name}")
        for name in changed:
            problems.append(f"{app_id}: changed size {name}")
    if problems:
        print("\n".join(problems))
        print(f"asset parity failed ({len(problems)} problem(s))")
        return 1
    print(f"asset parity kept: {checked} application(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
