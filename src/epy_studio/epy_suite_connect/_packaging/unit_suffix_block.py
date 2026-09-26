"""A numeric key in a physical catalogue declares its unit in its name.

Owner directive (2026-09-23): "todo debe llevar las unidades con `_`".

WHAT IS CHECKED
---------------
A key whose WHOLE name is a dimensional word -- ``length``, ``area``,
``weight`` -- and which holds a number. That key says a magnitude and says
nothing about what it is measured in, so it is a violation. ``length_mm`` and
``length_threshold_in`` are outside the rule: their names are not dimensional
words.

The physical catalogues are told from the presentation ones by PATH. A font
``weight: 6.4`` and a rebar ``weight: 6.4`` kg/m are the same number, so the
split cannot be made by value; ``_PRESENTATION`` lists the directories whose
``.epyson`` files configure how something is drawn.

Two exclusions are made by CONTENT instead, because a path rule wide enough to
cover them would take real catalogues with it: a unit-conversion table keys by
unit NAME (epy_units publishes ``"span": 0.2286`` because a span IS 9 inches),
and a bibliographic record keys ``volume`` as a journal volume, recognisable
by its siblings ``journal`` and ``pages``.

Only ``src`` is scanned. Test fixtures spell a key bare on purpose, to
exercise a refusal.

THE SUITE DECLARES A UNIT THREE WAYS
------------------------------------
A key suffix (``fy_MPa``), a file-level ``"unit_system": "MPa_m_kg"``, and a
per-value ``{"value": 250.0, "unit": "MPa"}``. All three are legitimate; this
rule catches a key that uses none of them.

Author: Ing. Angel Navarro-Mora M.Sc.
"""

from __future__ import annotations

import json
from pathlib import Path

#: Path fragments whose ``.epyson`` files are presentation, not measurement.
_PRESENTATION = (
    "/layouts/", "/_layouts/", "/_assets/", "/assets/", "/themes/", "/_themes/",
    "/_style/", "/_styles/", "/styles/", "/_render/", "/viewer/", "/preview/",
    "/rubrics/", "/_settings/_ui", "/dist/", "/_internal/", "/_archive/",
    "/build/", "/.claude/",
    # A unit-conversion table's keys are unit NAMES, not magnitudes: epy_units
    # publishes "span": 0.2286 because a span IS 9 inches. The key is the unit.
    "/units/",
)

#: Sibling keys that mark a dict as a BIBLIOGRAPHIC record rather than a
#: measurement. `"volume": 89` in epy_compose is the journal volume of a 2026
#: Structures paper, sitting beside `journal` and `pages`.
_BIBLIOGRAPHIC = ("journal", "doi", "isbn", "issn", "pages", "publisher",
                  "authors", "year_published")

#: Bare key names that name a physical magnitude. A key here without a unit
#: suffix is the violation. A LIST OF NAMES rather than a pattern, so the
#: judgement is visible here and can be argued with.
_DIMENSIONAL = frozenset({
    "length", "width", "depth", "height", "thickness", "diameter", "radius",
    "perimeter", "spacing", "cover", "span", "gap", "offset", "area", "volume",
    "mass", "weight", "force", "moment", "stress", "pressure", "load",
    "yield_strength", "ultimate_strength", "modulus", "density", "velocity",
    "acceleration", "temperature", "energy", "torque", "stiffness",
})

#: The spelling the suite uses when a key carries a unit. The refusal message
#: quotes it so the author has the list in front of them.
_CANONICAL_SPELLING = (
    "_m", "_mm", "_cm", "_m2", "_cm2", "_m3", "_m4", "_in", "_ft",
    "_kg_m", "_kg_m3", "_kN", "_kN_m", "_kPa", "_MPa", "_GPa", "_ksi",
    "_deg", "_rad", "_pct", "_px", "_pt",
)


def _is_presentation(rel: str) -> bool:
    low = "/" + rel.replace("\\", "/").lower()
    return any(frag in low for frag in _PRESENTATION)


def _is_bare_magnitude(key: str) -> bool:
    """True when the key IS a dimensional word and nothing else.

    The whole name has to match. ``length`` is checked, ``length_mm`` and
    ``length_threshold_in`` are not, and neither is ``spacing_db_multiplier``.
    That narrowness is deliberate: a structural catalogue is full of
    single-letter subscripts (gamma_M2, phi_c, CM_wet_service_Ft) that a rule
    parsing endings would read as units.
    """
    return key in _DIMENSIONAL


def _bare_numeric_keys(node: object, out: list[str]) -> list[str]:
    """Every dimensional key holding a number and carrying no unit suffix."""
    if isinstance(node, dict):
        bibliographic = any(marker in node for marker in _BIBLIOGRAPHIC)
        for key, value in node.items():
            if (_is_bare_magnitude(key)
                    and not bibliographic
                    and isinstance(value, (int, float))
                    and not isinstance(value, bool)):
                out.append(key)
            _bare_numeric_keys(value, out)
    elif isinstance(node, list):
        for item in node:
            _bare_numeric_keys(item, out)
    return out


def audit_unit_suffixes(lib_root: Path) -> list[str]:
    """Physical-catalogue keys that hold a magnitude and do not name its unit.

    Scans ``src``. A test fixture spells a key bare on purpose, to exercise a
    refusal, so fixtures stay outside the rule.
    """
    src = lib_root / "src"
    if not src.is_dir():
        return []

    violations: list[str] = []
    for path in sorted(src.rglob("*.epyson")):
        rel = path.relative_to(lib_root).as_posix()
        if _is_presentation(rel):
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue  # a malformed catalogue is another rule's business
        bare = _bare_numeric_keys(data, [])
        if not bare:
            continue
        counted = sorted({k: bare.count(k) for k in bare}.items())
        listed = ", ".join(f"'{k}' x{n}" for k, n in counted)
        violations.append(
            f"{rel}: {listed} hold a number and do not say in what. A key that "
            f"carries a magnitude names its unit (owner directive 2026-09-23); "
            f"'length' meant millimetres in one catalogue and metres in another "
            f"in the same library until this was enforced. Spell it the way "
            f"the suite already does ({', '.join(_CANONICAL_SPELLING)}), "
            f"because a suffix is only a declaration if the reader recognises "
            f"it. The spelling is the author's to get right.")
    return violations


def report_unit_suffixes(violations: list[str]) -> None:
    """Print the unit-suffix audit."""
    print()
    print("=" * 70)
    print("  UNIT SUFFIXES (a magnitude names its unit)")
    print("=" * 70)
    if not violations:
        print("  OK - every physical catalogue key declares its unit.")
        return
    print(f"  BARE MAGNITUDES ({len(violations)} file(s)):")
    for violation in violations:
        print(f"    [!] {violation}")
