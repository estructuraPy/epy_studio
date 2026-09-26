"""Regenerate the vendored `standards_helpers_block` in every lib's `_config/_loader.py`.

Background
----------
12 ePy Suite libs each carry a copy-pasted block of 6 functions
(`_walk_diff_sh`, `_standards_dir_sh`, `_resolve_complement_value_sh`,
`list_supported_standards`, `diff_standards`, `compare_standards`) between
`# === BEGIN standards_helpers_block ===` / `# === END standards_helpers_block ===`
markers in `src/<lib>/_config/_loader.py`. The logic is identical everywhere;
the only real per-lib variance is:

1. The standards catalog directory name (`"standards"` vs. `"_standards"`) —
   load-bearing: the wrong literal makes `list_supported_standards()` and
   `diff_standards()` silently return empty results.
2. A documentation-only "References" comment listing the standards actually
   present in that catalog directory.

Everything else had drifted only cosmetically (docstring wording, stray
formatting) from repeated manual copy/paste passes. This module makes the
template shipped next to it (`standards_helpers_block.py.tmpl`) the single
source of truth and regenerates the marked span in each lib from it.

Usage
-----
    # from a shell, run against the current working directory:
    python _packaging/_tooling/_standards_helpers_sync.py --check
    python _packaging/_tooling/_standards_helpers_sync.py --write --root <suite-root>

    # or as a library:
    import sys; sys.path.insert(0, "_packaging/_tooling")
    from _standards_helpers_sync import sync_standards_helpers
    sync_standards_helpers("C:/path/to/suite/root", check=True)

Hard rules
----------
- Only the text between the BEGIN/END markers is ever regenerated. Everything
  before the first marker and after the last marker is left byte-identical.
- `.epyson` catalog files are only ever READ, never rewritten.
- References are derived strictly from real `standard_id` / `description` /
  `audit_status` fields on disk — nothing here invents normative content.
"""

from __future__ import annotations

import argparse
import difflib
import json
import sys
from pathlib import Path

TEMPLATE_PATH = Path(__file__).resolve().parent / "standards_helpers_block.py.tmpl"

BEGIN_MARKER = "# === BEGIN standards_helpers_block ==="
END_MARKER = "# === END standards_helpers_block ==="

MAX_DESCRIPTION_CHARS = 100


class SyncError(RuntimeError):
    """Raised for conditions that must hard-fail the sync (never silently guessed)."""


def discover_target_libs(suite_root: Path) -> list[Path]:
    """Find every `src/<lib>/_config/_loader.py` that carries the marker block.

    Marker presence is the authoritative scope filter: libs with a related but
    unmarked helper implementation (epy_concrete, epy_compose, epy_analysis)
    are intentionally excluded, matching them never having the markers.
    """
    loaders: list[Path] = []
    for loader_path in sorted(suite_root.glob("epy_*/src/*/_config/_loader.py")):
        text = loader_path.read_text(encoding="utf-8")
        if BEGIN_MARKER in text and END_MARKER in text:
            loaders.append(loader_path)
    return loaders


def resolve_standards_dir(loader_path: Path) -> Path:
    """Resolve the on-disk standards catalog directory for one lib's loader.

    Checks which of `_config/standards/` or `_config/_standards/` actually
    exists. Hard-fails if neither or both exist — the dir-name literal is
    load-bearing and must never be guessed.
    """
    config_dir = loader_path.parent
    candidates = [config_dir / "standards", config_dir / "_standards"]
    existing = [c for c in candidates if c.is_dir()]
    if len(existing) == 0:
        raise SyncError(
            f"{loader_path}: neither 'standards/' nor '_standards/' exists under "
            f"{config_dir} — cannot resolve STANDARDS_DIR_NAME."
        )
    if len(existing) == 2:
        raise SyncError(
            f"{loader_path}: both 'standards/' and '_standards/' exist under "
            f"{config_dir} — ambiguous STANDARDS_DIR_NAME, resolve manually."
        )
    return existing[0]


def load_catalog_entries(standards_dir: Path) -> list[tuple[str, str, str]]:
    """Read every `*.epyson` file in the catalog dir and extract reference fields.

    Returns a sorted list of (standard_id, description, audit_status) for
    every file that parses as JSON and carries a `standard_id`. Files that
    fail to parse are skipped (never invented) and reported to stderr.
    """
    entries: list[tuple[str, str, str]] = []
    for epyson_path in sorted(standards_dir.glob("*.epyson")):
        try:
            data = json.loads(epyson_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"  WARNING: could not parse {epyson_path}: {exc}", file=sys.stderr)
            continue
        standard_id = str(data.get("standard_id", epyson_path.stem))
        description = str(data.get("description", "")).strip()
        audit_status = str(data.get("audit_status", "unknown"))
        entries.append((standard_id, description, audit_status))
    entries.sort(key=lambda e: e[0])
    return entries


def render_references_block(entries: list[tuple[str, str, str]]) -> str:
    """Render the References comment block from real catalog entries.

    Never fabricates citations: with zero parseable entries, emits a single
    honest line pointing at the catalog directory instead of inventing text.
    """
    if not entries:
        return (
            "# (no parseable .epyson entries found in this catalog directory — consult it directly)"
        )
    lines = []
    for standard_id, description, audit_status in entries:
        short = description
        if len(short) > MAX_DESCRIPTION_CHARS:
            short = short[: MAX_DESCRIPTION_CHARS - 3].rstrip() + "..."
        if short:
            lines.append(f"# - {standard_id}: {short} [{audit_status}]")
        else:
            lines.append(f"# - {standard_id} [{audit_status}]")
    return "\n".join(lines)


def render_span(standards_dir: Path) -> str:
    """Render the full BEGIN..END span for one lib from the template."""
    template_raw = TEMPLATE_PATH.read_text(encoding="utf-8")
    t_begin = template_raw.index(BEGIN_MARKER)
    t_end = template_raw.index(END_MARKER) + len(END_MARKER)
    template_span = template_raw[t_begin:t_end]

    entries = load_catalog_entries(standards_dir)
    references_block = render_references_block(entries)

    rendered = template_span.replace("{{STANDARDS_DIR_NAME}}", standards_dir.name)
    rendered = rendered.replace("{{REFERENCES_COUNT}}", str(len(entries)))
    rendered = rendered.replace("{{REFERENCES_BLOCK}}", references_block)
    if "{{" in rendered:
        raise SyncError(f"Unresolved placeholder(s) left in rendered span:\n{rendered}")
    return rendered


def splice(loader_path: Path, new_span: str) -> tuple[str, str]:
    """Return (old_full_text, new_full_text) with only the marker span swapped in.

    Everything before BEGIN and after END is preserved byte-for-byte.
    """
    old_text = loader_path.read_text(encoding="utf-8")
    begin_idx = old_text.index(BEGIN_MARKER)
    end_idx = old_text.index(END_MARKER) + len(END_MARKER)

    prefix = old_text[:begin_idx]
    suffix = old_text[end_idx:]
    new_text = prefix + new_span + suffix

    # Defensive self-check: never write outside the markers.
    if new_text[:begin_idx] != prefix or new_text[len(prefix) + len(new_span) :] != suffix:
        raise SyncError(f"{loader_path}: splice invariant violated — refusing to write.")
    return old_text, new_text


def summarize_diff(loader_path: Path, old_text: str, new_text: str) -> str:
    """Compact unified-diff summary for one out-of-sync loader file."""
    diff = difflib.unified_diff(
        old_text.splitlines(keepends=True),
        new_text.splitlines(keepends=True),
        fromfile=str(loader_path) + " (current)",
        tofile=str(loader_path) + " (generated)",
        n=1,
    )
    lines = list(diff)
    changed = sum(
        1 for line in lines if line.startswith(("+", "-")) and not line.startswith(("+++", "---"))
    )
    preview = "".join(lines[:40])
    more = "" if len(lines) <= 40 else f"\n  ... ({len(lines) - 40} more diff lines)"
    return f"  {changed} changed line(s):\n{preview}{more}"


def sync_standards_helpers(
    suite_root: str | Path | None = None,
    *,
    check: bool = True,
    libs: list[str] | None = None,
) -> int:
    """Check or regenerate the vendored standards-helpers block suite-wide.

    Parameters
    ----------
    suite_root : str | Path, optional
        Directory containing the sibling lib repos (default: current working
        directory).
    check : bool, default True
        ``True`` reports drift and writes nothing (exit code 1 when out of
        sync); ``False`` regenerates the marker span in place.
    libs : list[str], optional
        Limit the run to these lib names (default: every lib discovered by
        marker presence).

    Returns
    -------
    int
        Process-style exit code: 0 in sync / written, 1 drift found in check
        mode, 2 hard failure (missing template, ambiguous catalog dir, no
        targets found).
    """
    root = Path(suite_root).resolve() if suite_root is not None else Path.cwd()

    if not TEMPLATE_PATH.is_file():
        print(f"ERROR: template not found at {TEMPLATE_PATH}", file=sys.stderr)
        return 2

    loaders = discover_target_libs(root)
    if libs:
        wanted = set(libs)
        loaders = [p for p in loaders if p.parents[3].name in wanted]

    if not loaders:
        print(
            f"ERROR: no loader files with standards_helpers_block markers found under {root}.",
            file=sys.stderr,
        )
        return 2

    out_of_sync: list[str] = []
    errors: list[str] = []

    for loader_path in loaders:
        lib_name = loader_path.parents[3].name
        try:
            standards_dir = resolve_standards_dir(loader_path)
            new_span = render_span(standards_dir)
            old_text, new_text = splice(loader_path, new_span)
        except SyncError as exc:
            print(f"[{lib_name}] HARD FAIL: {exc}", file=sys.stderr)
            errors.append(lib_name)
            continue

        entries_count = len(load_catalog_entries(standards_dir))
        if old_text == new_text:
            print(f"[{lib_name}] in sync (dir={standards_dir.name}, references={entries_count})")
            continue

        out_of_sync.append(lib_name)
        if not check:
            loader_path.write_text(new_text, encoding="utf-8")
            print(f"[{lib_name}] WRITTEN (dir={standards_dir.name}, references={entries_count})")
        else:
            print(
                f"[{lib_name}] OUT OF SYNC (dir={standards_dir.name}, references={entries_count})"
            )
            print(summarize_diff(loader_path, old_text, new_text))

    if errors:
        print(f"\n{len(errors)} lib(s) hard-failed: {', '.join(errors)}", file=sys.stderr)
        return 2

    if check:
        if out_of_sync:
            print(
                f"\n{len(out_of_sync)} lib(s) out of sync: {', '.join(out_of_sync)}",
                file=sys.stderr,
            )
            return 1
        print(f"\nAll {len(loaders)} lib(s) in sync.")
        return 0

    print(
        f"\n{len(out_of_sync)} lib(s) updated, {len(loaders) - len(out_of_sync)} already in sync."
    )
    return 0


def main() -> int:
    """Argparse CLI wrapper around :func:`sync_standards_helpers`."""
    # The console codepage on Windows (cp1252) can't encode em-dashes and other
    # characters that show up verbatim in .epyson descriptions. Widen stdout/
    # stderr to UTF-8 so --check/--write diff output never crashes on Windows;
    # file I/O elsewhere already pins encoding="utf-8" explicitly.
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="backslashreplace")

    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--check", action="store_true", help="Report drift, write nothing, exit 1 if out of sync."
    )
    mode.add_argument("--write", action="store_true", help="Regenerate the marker span in place.")
    parser.add_argument(
        "--root",
        default=None,
        help="Suite root containing the lib repos (default: current working directory).",
    )
    parser.add_argument(
        "--lib",
        action="append",
        default=None,
        help="Limit to lib name(s) (e.g. --lib epy_steel). May be repeated. Default: all discovered libs.",
    )
    args = parser.parse_args()
    return sync_standards_helpers(args.root, check=args.check, libs=args.lib)


if __name__ == "__main__":
    raise SystemExit(main())
