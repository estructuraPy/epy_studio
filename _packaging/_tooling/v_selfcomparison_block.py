"""Canonical rule: a validation row must compare two numbers, not one twice.

WHY THIS EXISTS. Measured on 2026-08-27 across the suite: of 32,527 comparison
rows in the 711 ``V_*.md`` documents that no fixture certifies, **31,208
(96.0 %) carried the SAME number in the "Library" column and in the "Hand-calc"
column**, so every one of them read ``+0.00 % / PASS``. A value compared with
itself cannot fail. 570 documents were affected across 16 repositories, and 529
tables held nothing else -- those files reported thousands of passes while
verifying nothing at all.

It had been found twice before in miniature and fixed only where it was found:
2,298 rows in ``V_E01`` (2026-08-22, the "Library" column held the hand value)
and 71 rows across 13 documents (2026-08-19, an id truncated and compared with
itself). Nothing watched the shape, so the corpus kept it.

NO BASELINE, ON PURPOSE. The other suite-level rules froze what existed the day
they landed because twenty repos would have gone red before their migration
ran. This one lands the day AFTER the migration: the corpus is at zero, so the
rule is a hard failure from the start. A baseline here would be a place for the
defect to come back and live.

WHAT COUNTS AS A COMPARISON TABLE. The header must name both roles -- the
code's side (library, notebook, helper, PyNite, ...) and the person's side
(hand, manual, closed-form, ...). Two columns holding the same number under any
other header are not caught, and that is deliberate: a round-trip check
(``| Member count | 6 | 6 |``, original against re-imported) and an equilibrium
check (``| Base shear | 146.715 | 146.715 |``, applied against reaction) are
REAL verifications whose equality is the result. Five such rows in
``epy_analysis`` were inspected by hand before this rule was written.

CERTIFIED DOCUMENTS ARE EXEMPT, and the distinction is the point. In a document
backed by a fixture under ``tests/_benchmarks/`` the two numbers come from two
independent places -- the clause substituted inside the test and the library
called by the same test -- and the test goes red the moment they part. Equality
there is the RESULT. In the padded documents both cells came from one variable
and nothing would ever fail. Eight documents carry that backing today.

HOW TO SATISFY IT. Either the row compares two independently obtained numbers,
or it is not a comparison and does not belong in a comparison table. The
document may record a value elsewhere in prose; what it may not do is print a
``PASS`` for it.
"""

from __future__ import annotations

import re
from pathlib import Path

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

__all__ = [
    "audit_v_selfcomparison",
    "report_v_selfcomparison",
    "v_selfcomparison_measure",
]

_NUM = re.compile(r"^[-+]?[\d.,]+(?:[eE][-+]?\d+)?\s*%?$")
_LIBRARY_ROLE = re.compile(
    r"\b(library|notebook|lib|software|helper|pynite|opensees|nb|c[oó]digo|epy_\w+)\b", re.I
)
_HAND_ROLE = re.compile(
    r"\b(hand|manual|mano|te[oó]rico|analytic\w*|closed[- ]form|c[aá]lculo)\b", re.I
)
#: A document that names its own fixture DIRECTORY is verified elsewhere.
#: The named subdirectory is required, not the bare ``tests/_benchmarks/``: the
#: retirement note added to every swept document mentions the bare path while
#: explaining where real values come from, and a regex matching that turned all
#: 562 swept documents into exemptions -- the rule would have been silently
#: disabled across the whole corpus on the day it landed. Caught by following a
#: single escaped-pipe row that should have been flagged and was not.
_CERTIFIED = re.compile(r"tests/_benchmarks/[A-Za-z0-9_]+/")
_SKIP_PARTS = {"node_modules", "__pycache__", "_gallery", "testing", "docs_build"}


def _cells(line: str) -> list[str] | None:
    """Cells of a markdown table row, honouring escaped pipes.

    A cell may contain an escaped pipe -- ``| Peak \\|M\\| [kN*m] | 90.00 |
    90.00 |`` is a real row in this corpus. Splitting on every pipe shifted
    its columns, and that row survived the sweep which then reported zero
    residual; 46 rows across ten repositories carry the escape.
    """
    s = line.strip()
    if not (s.startswith("|") and s.endswith("|")):
        return None
    return [c.strip().replace("\\|", "|") for c in re.split(r"(?<!\\)\|", s[1:-1])]


def _is_separator(cells: list[str]) -> bool:
    return bool(cells) and all(c and set(c) <= set("-: ") for c in cells)


def _value_columns(header: list[str]) -> tuple[int, int] | None:
    cleaned = [c.strip().strip("`*") for c in header]
    lib = next((i for i, c in enumerate(cleaned) if _LIBRARY_ROLE.search(c)), None)
    hand = next((i for i, c in enumerate(cleaned) if _HAND_ROLE.search(c)), None)
    if lib is None or hand is None or lib == hand:
        return None
    return (lib, hand)


def _same_number(a: str, b: str) -> bool:
    a, b = a.strip().strip("`*"), b.strip().strip("`*")
    if not (_NUM.match(a) and _NUM.match(b)):
        return False
    return a.rstrip("%").replace(",", "").strip() == b.rstrip("%").replace(",", "").strip()


def v_selfcomparison_measure(lib_root: Path) -> list[tuple[str, int, str]]:
    """Every self-comparing row: ``(relative path, line number, the row)``."""
    found: list[tuple[str, int, str]] = []
    for doc in safe_rglob(lib_root, "V_*.md"):
        rel_parts = doc.relative_to(lib_root).parts
        if any(p.startswith(".") or p in _SKIP_PARTS for p in rel_parts):
            continue
        text = doc.read_text(encoding="utf-8", errors="replace")
        if _CERTIFIED.search(text):
            continue
        lines = text.splitlines()
        i = 0
        while i < len(lines):
            header = _cells(lines[i])
            cols = _value_columns(header) if header else None
            if not cols or i + 1 >= len(lines) or not _is_separator(_cells(lines[i + 1]) or []):
                i += 1
                continue
            a, b = cols
            j = i + 2
            while j < len(lines):
                row = _cells(lines[j])
                if not row or len(row) <= max(a, b):
                    break
                if _same_number(row[a], row[b]):
                    found.append((doc.relative_to(lib_root).as_posix(), j + 1, lines[j].strip()))
                j += 1
            i = j
    return found


def audit_v_selfcomparison(lib_root: Path) -> list[str]:
    """One message per row that compares a value with itself."""
    return [
        f"{path}:{line}: this row puts the same number in the library column and in "
        f"the hand-calc column, so it reads +0.00 % / PASS while comparing nothing -- "
        f"{row}"
        for path, line, row in v_selfcomparison_measure(lib_root)
    ]


def report_v_selfcomparison(violations: list[str]) -> None:
    print()
    print("=" * 70)
    print("  V_ VALIDATION ROWS (a comparison needs two numbers)")
    print("=" * 70)
    if not violations:
        print("  OK - no row compares a value with itself.")
        return
    print(f"  {len(violations)} SELF-COMPARING ROW(S):")
    for v in violations[:20]:
        print(f"    - {v}")
    if len(violations) > 20:
        print(f"    ... and {len(violations) - 20} more")
    print(
        "  A value compared with itself cannot fail. Either the row compares two\n"
        "  independently obtained numbers, or it is not a comparison: record the\n"
        "  value in prose instead of printing a PASS for it. A document certified\n"
        "  by a fixture under tests/_benchmarks/ is exempt, because there the two\n"
        "  numbers come from the clause and from the library inside one test."
    )
