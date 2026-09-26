"""A cited ``references.db`` id must resolve to a document the file names.

The reference store was rebuilt and renumbered. Ids recorded before that point
still resolve -- to *different documents* -- so nothing ever failed: a census on
2026-08-29 found 41 citation sites across 20 ``SOURCE.md`` files pointing at the
wrong row, several of them under the words "confirmed by direct SQLite query".
An id that resolves to something is indistinguishable from an id that resolves
to the right thing unless something checks the two against each other.

The filename is the identity. This rule reads the filename a ``SOURCE.md``
names, resolves the id it cites, and fails when they disagree. It also fails
when a file cites an id and names no filename at all, because that is the state
in which the drift was invisible.

Loaded by path from each library's ``housekeeper.py``; edit it HERE.
"""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from typing import Any

# The ONE tree walk, live-loaded from the canonical file next door rather than
# copied: a walk that dies on a dangling junction takes the whole audit with it,
# and four call sites drifting apart is how the rule became four rules.
def _load_safe_rglob():
    """Bind ``safe_rglob`` from ``safe_walk_block.py``, or fall back to rglob."""
    import importlib.util as _ilu

    block = Path(__file__).resolve().parent / "safe_walk_block.py"
    if not block.exists():  # pragma: no cover - only when the tooling repo is partial
        return lambda root, pattern="*": sorted(Path(root).rglob(pattern))
    spec = _ilu.spec_from_file_location("_safe_walk_block", block)
    mod = _ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.safe_rglob


safe_rglob = _load_safe_rglob()

# a number sitting in the same clause as the word "id"/"ids"
_ID_PATTERN = re.compile(r"\bids?\b[^.\n]{0,80}?((?:\d{2,6})(?:\s*/\s*\d{2,6})*)", re.I)
_NUM_PATTERN = re.compile(r"\d{2,6}")
# Stored filenames carry accents (codigo_sismico, diseno) -- an ASCII-only class
# captures half of one and the rule then reports a document it did name. And
# most of them START with a year, so a filename inside an id clause offers a
# four-digit number that is not an id: both are why filenames are cut out of the
# text before ids are read from it.
_FILE_PATTERN = re.compile(
    r"([^\W_][\w\-\.]{4,}\.(?:pdf|zip|rar|djvu|jpg|png|docx|xlsx|txt|dwg))",
    re.UNICODE | re.I,
)


def _store_path(lib_root: Path) -> Path:
    return lib_root.parent / "references.db"


def audit_source_ids(lib_root: Path) -> dict[str, Any]:
    """Return the violations, plus whether the rule could run at all."""
    store = _store_path(lib_root)
    if not store.exists():
        return {"ran": False, "why": f"no reference store at {store}", "violations": []}

    with sqlite3.connect(f"file:{store}?mode=ro", uri=True) as db:
        rows = {
            int(i): (fn or "")
            for i, fn in db.execute("select id, filename from documents")
        }

    violations: list[tuple[str, str]] = []
    bench = lib_root / "tests" / "_benchmarks"
    for path in safe_rglob(bench, "SOURCE.md"):
        text = path.read_text(encoding="utf-8", errors="replace")
        named = {m.group(1).lower() for m in _FILE_PATTERN.finditer(text)}
        # read ids from the text with the filenames removed, so the year a
        # stored filename starts with is never mistaken for a catalogue id
        without_files = _FILE_PATTERN.sub(" ", text)
        cited: list[int] = []
        for match in _ID_PATTERN.finditer(without_files):
            cited.extend(int(n) for n in _NUM_PATTERN.findall(match.group(1)))
        if not cited:
            continue

        rel = path.relative_to(lib_root).as_posix()
        if not named:
            violations.append(
                (rel, f"cites ids {sorted(set(cited))} and names no document filename, "
                      f"so nothing can check them")
            )
            continue

        for doc_id in dict.fromkeys(cited):
            if doc_id not in rows:
                violations.append((rel, f"id {doc_id} is not a row in references.db"))
            elif rows[doc_id].lower() not in named:
                violations.append(
                    (rel, f"id {doc_id} resolves to {rows[doc_id]!r}, which this file "
                          f"does not name")
                )
    return {"ran": True, "why": None, "violations": violations}


def report_source_ids(result: dict[str, Any]) -> None:
    print()
    print("=" * 70)
    print("  SOURCE.md REFERENCE IDS (the filename is the identity)")
    print("=" * 70)
    if not result["ran"]:
        # a rule that cannot run must say so; silence reads as a pass
        print(f"  NOT RUN - {result['why']}")
        return
    if not result["violations"]:
        print("  OK - every cited id resolves to a document the file names.")
        return
    print(f"  {len(result['violations'])} citation(s) point at the wrong document:")
    for rel, why in result["violations"]:
        print(f"    [x] {rel}: {why}")
