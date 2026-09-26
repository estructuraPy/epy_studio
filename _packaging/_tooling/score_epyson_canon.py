"""Score every .epyson + its loader against the 5-rubric canon.

R1 per-file identity (id/version/desc/audit/json/english)
R2 cross-file conformance per <algo>_id family
R3 loader contract (public API, _validate_typed_id, no **kwargs, typed return, complement_with, audit_status check)
R4 loader runtime (cache, index, error message, thread-safety doc, alias support, public-only consumption)
R5 tests + housekeeper (mirror, parametrize, conformance loop, round-trip, negatives, hk rule)

raw_max = 5 * 6 * 5 = 150;  score_100 = raw / 1.5
"""
from __future__ import annotations

import ast
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

#: Suite root, derived from this file's own location rather than hardcoded
#: to one machine. The literal absolute path made the scorer unrunnable
#: anywhere else, and _tooling/README.md already listed it as the obvious
#: next cleanup.
ROOT = Path(__file__).resolve().parent.parent.parent

#: Libraries scored. Names are the ON-DISK directory names: ``ePy_plotter``
#: carries a capital P, and the old ``epy_plotter`` entry resolved only
#: because Windows ignores case -- on Linux it silently scored a missing
#: directory.
#:
#: ``epy_suite`` was removed on 2026-08-18. It was retired on 2026-08-08
#: (GitHub-archived, checkout deleted) and every run since had scored a
#: directory that does not exist. It did not crash -- every rubric degrades
#: to a floor -- it scored raw 34/150 = 22.7 and dragged the cross-suite
#: average down with a denominator of 150 x 17 counting a dead library.
LIBS = [
    "epy_analysis", "epy_bridges", "epy_buildings", "epy_compose",
    "epy_concrete", "epy_connections", "epy_geotechnical", "epy_houses",
    "epy_masonry", "ePy_plotter", "epy_steel", "epy_structure",
    "epy_tall", "epy_tanks", "epy_timber", "epy_towers",
]
VALID_AUDIT = {"verified", "partial", "needs_source_verification", "n_a"}
SEMVER = re.compile(r"^\d+\.\d+\.\d+([.\-+].*)?$")
# heuristic: common Spanish words / accented chars (excluding standard tech terms)
SPANISH_HINT = re.compile(r"[áéíóúñÁÉÍÓÚÑ]|\b(losa|techo|piso|viga|columna|muro|pared|conexión|cálculo|análisis|tipo|sin|para|por|que|las|los|del)\b", re.IGNORECASE)

# R1.6 measures UNTRANSLATED PROSE, not "any Spanish byte in the file". Three kinds
# of string legitimately keep the source language and must not be counted against a
# catalog that documents a Hispanic-American code:
#
#   1. Source identity — the official title of a standard, its issuing body, the
#      verbatim table caption a reader needs in order to find the page. A translated
#      title cannot be used to locate the document, so translating it destroys the
#      verifiability the citation exists to provide.
#   2. The source's own taxonomy and jurisdiction tables, which appear as KEYS:
#      Costa Rican canton names, or the CSCR system types (`marco a`, `muro a`)
#      that epy_analysis publishes as the suite-wide vocabulary.
#   3. Formulas. `2*Asd*fy*sin(alpha)` is not Spanish -- `sin`, `los` and `del` all
#      collide with Spanish stopwords, and no rewrite can remove a sine from a
#      shear-friction equation.
#
# So the rubric walks string VALUES and skips those three classes. Prose still gets
# checked, which is the thing the rule is actually about.
SOURCE_IDENTITY_KEYS = frozenset({
    "citation", "source", "source_pdf", "source_file", "filename", "url",
    "original_title", "issuing_body", "publisher", "organization",
    "reference", "normative_reference", "code_ref", "title",
})
# _filename: a file name on disk is pure source identity -- translating it
# breaks the only string that locates the document (the LDVCR PDF carries an
# enye in its real name on disk).
SOURCE_IDENTITY_SUFFIXES = ("_es", "_verbatim", "_filename")
FORMULA_KEYS = frozenset({"formula", "check", "equation", "expression"})


def lib_src(lib: str) -> Path:
    return ROOT / lib / "src" / lib.lower()


def lib_root(lib: str) -> Path:
    return ROOT / lib


# ---------- file collection ----------

def collect_epyson(lib: str) -> list[Path]:
    src = lib_src(lib)
    if not src.exists():
        return []
    return sorted(p for p in src.rglob("*.epyson"))


def safe_load_json(p: Path) -> tuple[dict | None, str | None, bytes | None]:
    try:
        raw = p.read_bytes()
        text = raw.decode("utf-8")
        return json.loads(text), text, raw
    except Exception as e:
        return None, None, None


def detect_id_field(data: dict) -> tuple[str | None, str | None]:
    """Return (id_field_name, id_value) for top-level *_id key, else (None, None)."""
    if not isinstance(data, dict):
        return None, None
    for k, v in data.items():
        if isinstance(k, str) and k.endswith("_id") and isinstance(v, str):
            return k, v
    return None, None


# ---------- scoring helpers ----------

def _is_exempt(path: str) -> bool:
    """True when the string at this dotted path legitimately keeps the source language."""
    last = path.rsplit(".", 1)[-1]
    if last in SOURCE_IDENTITY_KEYS or last.endswith(SOURCE_IDENTITY_SUFFIXES):
        return True
    if last in FORMULA_KEYS or last.endswith("_formula"):
        return True
    return ".branches." in f".{path}."


def prose_values(obj, path: str = ""):
    """Yield (path, text) for every string value a translator would translate."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from prose_values(v, f"{path}.{k}" if path else str(k))
    elif isinstance(obj, list):
        for v in obj:
            yield from prose_values(v, path)
    elif isinstance(obj, str) and path and not _is_exempt(path):
        yield path, obj


def pct_to_level(pct: float) -> int:
    if pct >= 1.0:
        return 5
    if pct >= 0.90:
        return 4
    if pct >= 0.70:
        return 3
    if pct >= 0.40:
        return 2
    return 1


def bool_to_level(ok: bool) -> int:
    return 5 if ok else 1


# ---------- R1 — per-file identity ----------

def score_r1(epyson_files: list[Path], notes: dict | None = None) -> dict[str, int]:
    n = len(epyson_files) or 1
    r11_ok = r12_ok = r13_ok = r14_ok = r15_ok = r16_ok = 0
    for p in epyson_files:
        data, text, raw = safe_load_json(p)
        if data is None:
            continue
        id_field, id_value = detect_id_field(data)
        if id_field and id_value == p.stem:
            r11_ok += 1
        v = data.get("version")
        if isinstance(v, str) and SEMVER.match(v):
            r12_ok += 1
        d = data.get("description")
        if isinstance(d, str) and len(d.strip()) >= 20:
            r13_ok += 1
        a = data.get("audit_status")
        if a in VALID_AUDIT:
            r14_ok += 1
        # R1.5 json well-formed + utf-8 + indent=2 + no BOM
        if raw is not None and not raw.startswith(b"\xef\xbb\xbf") and text and "\n  " in text:
            r15_ok += 1
        # R1.6 english-only prose (source identity, taxonomy keys and formulas exempt)
        untranslated = [k for k, v in prose_values(data) if SPANISH_HINT.search(v)]
        if untranslated:
            if notes is not None:
                notes.setdefault("R1.6", []).append((p.name, untranslated[:3]))
        else:
            r16_ok += 1
    return {
        "R1.1": pct_to_level(r11_ok / n),
        "R1.2": pct_to_level(r12_ok / n),
        "R1.3": pct_to_level(r13_ok / n),
        "R1.4": pct_to_level(r14_ok / n),
        "R1.5": pct_to_level(r15_ok / n),
        "R1.6": pct_to_level(r16_ok / n),
    }


# ---------- R2 — cross-file conformance per family ----------

def declared_keys(data: dict) -> frozenset:
    """Top-level keys the file actually declares something under.

    A key whose value is an empty object or array declares NOTHING. Counting it
    as present is what made padding pay: R2.1 compares key SETS, so adding the
    missing keys as ``{}`` was the cheapest way to match the family canon, and
    the suite dispatches on PRESENCE -- an absent modifier means the code has no
    such provision. A ``{}`` therefore makes a code claim a provision it does
    not publish, and scoring it rewarded exactly that.
    """
    return frozenset(k for k, v in data.items() if v not in ({}, []))


def score_r2(epyson_files: list[Path], lib: str) -> dict[str, int]:
    # bucket files per family
    fam: dict[str, list[tuple[Path, dict]]] = defaultdict(list)
    for p in epyson_files:
        data, _, _ = safe_load_json(p)
        if data is None:
            continue
        id_field, _ = detect_id_field(data)
        if id_field:
            fam[id_field].append((p, data))

    if not fam:
        return {f"R2.{i}": 1 for i in range(1, 7)}

    # R2.1 same top-level keyset per family (allow per-family stable set)
    r21_levels = []
    for fname, items in fam.items():
        if len(items) <= 1:
            r21_levels.append(5)
            continue
        sets = [declared_keys(d) for _, d in items]
        # canonical = most common
        canon = max(set(sets), key=sets.count)
        matches = sum(1 for s in sets if s == canon)
        r21_levels.append(pct_to_level(matches / len(items)))
    r21 = round(sum(r21_levels) / len(r21_levels)) if r21_levels else 1

    # R2.2 numeric fields with unit suffix or unit_system declared
    unit_suffix = re.compile(r"_(mpa|gpa|kpa|pa|kn|knm|n|nm|m|mm|cm|kg|kgm3|degc|c|s|hz|m2|m3)$", re.IGNORECASE)
    total_num = 0
    annotated = 0
    for _, items in fam.items():
        for _, d in items:
            has_unit_system = "unit_system" in d
            for k, v in _walk(d):
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    total_num += 1
                    if has_unit_system or unit_suffix.search(k):
                        annotated += 1
    r22 = pct_to_level(annotated / total_num) if total_num else 5

    # R2.3 Pydantic / JSON schema present in code.
    # Both placements are canonical: the material libraries keep per-family
    # schema packages under _core/_schemas, the thinner libraries keep a single
    # identity schema under _config/_schemas. Looking only in the latter scored
    # the five richest catalogs 1 and an identity-only stub 5 -- inverted.
    schema_dirs = (
        lib_src(lib) / "_core" / "_schemas",
        lib_src(lib) / "_config" / "_schemas",
    )
    r23 = 5 if any(d.exists() and any(d.glob("*.py")) for d in schema_dirs) else 1

    # R2.4 complement_with declared in local-scope codes
    local_hint = re.compile(r"(cscr|nec_se|nsr|nch|cirsoc|nbr|mopt|local)", re.IGNORECASE)
    local_files = []
    for p, d in [(p, d) for items in fam.values() for p, d in items]:
        if local_hint.search(p.stem):
            local_files.append(d)
    if not local_files:
        r24 = 5
    else:
        ok = sum(1 for d in local_files if "complement_with" in d)
        r24 = pct_to_level(ok / len(local_files))

    # R2.5 variations documented in _config/<algo>_variations.md
    variations_doc = lib_src(lib) / "_config" / "VARIATIONS.md"
    r25 = 5 if variations_doc.exists() else 1

    # R2.6 cross-lib parity — only computable globally, default 3 here, recomputed by main()
    r26 = 3

    return {"R2.1": r21, "R2.2": r22, "R2.3": r23, "R2.4": r24, "R2.5": r25, "R2.6": r26}


def _walk(obj, prefix=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            key = f"{prefix}.{k}" if prefix else k
            yield key, v
            yield from _walk(v, key)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _walk(v, f"{prefix}[{i}]")


# ---------- R3 / R4 — loader code introspection ----------

def _loader_path(lib: str) -> Path:
    return lib_src(lib) / "_config" / "_loader.py"


def _init_path(lib: str) -> Path:
    return lib_src(lib) / "__init__.py"


def _read_text(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8")
    except Exception:
        return ""


def score_r3(lib: str, families: list[str]) -> dict[str, int]:
    loader = _read_text(_loader_path(lib))
    init = _read_text(_init_path(lib))
    if not loader:
        return {f"R3.{i}": 1 for i in range(1, 7)}

    # R3.1 load_<algo>(id: str) exported from __init__
    ok_export = 0
    expected = [f"load_{fam.removesuffix('_id')}" for fam in families]
    for fn in expected:
        if fn in init and fn in loader:
            ok_export += 1
    r31 = pct_to_level(ok_export / len(expected)) if expected else 5

    # R3.2 _validate_typed_id present + called
    calls = loader.count("_validate_typed_id(")
    r32 = 5 if calls >= max(1, len(families)) else (3 if calls >= 1 else 1)

    # R3.3 no **kwargs
    r33 = 1 if re.search(r"\*\*kwargs|\*\*data", loader) else 5

    # R3.4 returns Pydantic model (heuristic: import pydantic or class definitions used)
    has_pyd = "pydantic" in loader.lower() or "BaseModel" in loader or "dataclass" in loader
    r34 = 5 if has_pyd else 2

    # R3.5 resolves complement_with
    r35 = 5 if "complement_with" in loader else 1

    # R3.6 validates audit_status
    r36 = 5 if "audit_status" in loader else 1

    return {"R3.1": r31, "R3.2": r32, "R3.3": r33, "R3.4": r34, "R3.5": r35, "R3.6": r36}


def score_r4(lib: str) -> dict[str, int]:
    loader = _read_text(_loader_path(lib))
    if not loader:
        return {f"R4.{i}": 1 for i in range(1, 7)}

    # R4.1 cache: lru_cache or singleton (_instance)
    r41 = 5 if ("lru_cache" in loader or "_instance" in loader) else 1
    # R4.2 pre-built index (dict assigned at init), no per-call rglob inside load_*
    per_call_rglob = bool(re.search(r"def\s+load_\w+\([^)]*\)[^:]*:\s*(?:.*\n)*?\s*[^#]*rglob\(", loader))
    has_dict_index = bool(re.search(r"self\._\w+\s*=\s*\{\}", loader)) or "load_all" in loader.lower()
    r42 = 5 if (has_dict_index and not per_call_rglob) else (3 if has_dict_index else 1)
    # R4.3 error message has "did you mean" or get_close_matches
    r43 = 5 if ("did you mean" in loader.lower() or "get_close_matches" in loader) else 1
    # R4.4 thread-safety doc (mention of thread-safe or lock)
    r44 = 5 if re.search(r"thread[\s-]?safe|threading\.Lock|RLock", loader, re.IGNORECASE) else 1
    # R4.5 alias support — the loader must RESOLVE aliases and at least one catalog
    # must DECLARE them. The previous rule was decided by a bare substring "alias"
    # anywhere in the loader, which a comment about Python variable aliasing already
    # satisfied; its other branch looked for `_config/_mappings`, a path that exists
    # in none of the libraries, so it never contributed.
    resolves = bool(re.search(r"def\s+\w*alias\w*|def\s+canonical_\w+", loader))
    declares = False
    for p in collect_epyson(lib):
        data, _, _ = safe_load_json(p)
        if isinstance(data, dict) and data.get("aliases"):
            declares = True
            break
    r45 = 5 if (resolves and declares) else (3 if (resolves or declares) else 1)
    # R4.6 public-only: no other src file imports _config._loader internals
    r46 = _check_public_only(lib)

    return {"R4.1": r41, "R4.2": r42, "R4.3": r43, "R4.4": r44, "R4.5": r45, "R4.6": r46}


def _check_public_only(lib: str) -> int:
    """Score 5 if no external module imports <lib>._config._loader._*, else 1."""
    bad = re.compile(rf"from\s+{re.escape(lib.lower())}\._config\._loader\s+import\s+_\w+")
    hits = 0
    for p in ROOT.rglob("*.py"):
        # only check OTHER libs' code consuming this lib's loader
        if lib.lower() in p.parts and "_config" in p.parts:
            continue
        try:
            if bad.search(p.read_text(encoding="utf-8", errors="ignore")):
                hits += 1
                if hits > 0:
                    return 1
        except Exception:
            pass
    return 5


# ---------- R5 — tests + housekeeper ----------

def score_r5(lib: str, families: list[str]) -> dict[str, int]:
    tests_loader = ROOT / lib / "tests" / "_config" / "test_loader.py"
    hk = ROOT / lib / "housekeeper.py"

    r51 = 5 if tests_loader.exists() else 1
    text = _read_text(tests_loader)

    # R5.2 parametrize with ≥3 ids per family
    if not families:
        r52 = 5
    else:
        param_ok = 0
        for fam in families:
            hits = re.findall(rf"parametrize\([^)]*{fam[:-3]}[^)]*\)", text)
            if hits:
                # crude — if at least one parametrize with that family's name
                param_ok += 1
        r52 = pct_to_level(param_ok / len(families))

    # R5.3 conformance loop
    r53 = 5 if re.search(r"for\s+\w+\s+in\s+.*\.glob\(['\"]\*\.epyson", text) or "rglob" in text and ".epyson" in text else 1
    # R5.4 round-trip / snapshot
    r54 = 5 if ("snapshot" in text.lower() or "round_trip" in text.lower() or "designer" in text.lower()) else 1
    # R5.5 negative tests — pytest.raises x ≥4
    raises = text.count("pytest.raises")
    r55 = 5 if raises >= 4 else (3 if raises >= 1 else 1)
    # R5.6 hk rule audit_epyson_canon
    hk_text = _read_text(hk)
    r56 = 5 if "audit_epyson_canon" in hk_text else 1

    return {"R5.1": r51, "R5.2": r52, "R5.3": r53, "R5.4": r54, "R5.5": r55, "R5.6": r56}


# ---------- orchestration ----------

def score_lib(lib: str) -> dict[str, Any]:
    files = collect_epyson(lib)
    families = sorted({detect_id_field(d)[0] for d in [safe_load_json(p)[0] for p in files] if d for f in [detect_id_field(d)[0]] if f})
    families = [f for f in families if f]
    notes: dict[str, list] = {}
    r1 = score_r1(files, notes)
    r2 = score_r2(files, lib)
    r3 = score_r3(lib, families)
    r4 = score_r4(lib)
    r5 = score_r5(lib, families)
    scores = {**r1, **r2, **r3, **r4, **r5}
    raw = sum(scores.values())
    return {"lib": lib, "n_epyson": len(files), "families": families, "scores": scores, "notes": notes, "raw": raw, "score_100": round(raw / 1.5, 1)}


def compute_r26_cross_lib(per_lib: list[dict]) -> None:
    """Compute R2.6 cross-lib parity: same <algo>_id appearing in 2+ libs must share schema."""
    # gather key-sets per family per lib
    fam_keys: dict[str, dict[str, set]] = defaultdict(dict)
    for entry in per_lib:
        lib = entry["lib"]
        for p in collect_epyson(lib):
            d, _, _ = safe_load_json(p)
            if not d:
                continue
            f, _ = detect_id_field(d)
            if f:
                fam_keys[f].setdefault(lib, set())
                fam_keys[f][lib].update(declared_keys(d))
    # for each family in ≥2 libs, compute jaccard
    per_lib_score: dict[str, list[float]] = defaultdict(list)
    for f, libs_map in fam_keys.items():
        if len(libs_map) < 2:
            continue
        union = set().union(*libs_map.values())
        for lib, keys in libs_map.items():
            jac = len(keys) / len(union) if union else 1.0
            per_lib_score[lib].append(jac)
    for entry in per_lib:
        lib = entry["lib"]
        if lib in per_lib_score:
            avg = sum(per_lib_score[lib]) / len(per_lib_score[lib])
            new = pct_to_level(avg)
            entry["scores"]["R2.6"] = new
            entry["raw"] = sum(entry["scores"].values())
            entry["score_100"] = round(entry["raw"] / 1.5, 1)


def render_markdown(per_lib: list[dict]) -> str:
    rubrics = ["R1.1", "R1.2", "R1.3", "R1.4", "R1.5", "R1.6",
               "R2.1", "R2.2", "R2.3", "R2.4", "R2.5", "R2.6",
               "R3.1", "R3.2", "R3.3", "R3.4", "R3.5", "R3.6",
               "R4.1", "R4.2", "R4.3", "R4.4", "R4.5", "R4.6",
               "R5.1", "R5.2", "R5.3", "R5.4", "R5.5", "R5.6"]
    lines = []
    lines.append("# epyson canonical audit — baseline\n")
    lines.append(f"Total libs: **{len(per_lib)}**  |  Total `.epyson`: **{sum(e['n_epyson'] for e in per_lib)}**\n")

    # rubric-totals per lib
    lines.append("## Score 100/100 per lib\n")
    lines.append("| Lib | N .epyson | Raw /150 | Score /100 | R1 /30 | R2 /30 | R3 /30 | R4 /30 | R5 /30 |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for e in per_lib:
        s = e["scores"]
        r1 = sum(s[f"R1.{i}"] for i in range(1, 7))
        r2 = sum(s[f"R2.{i}"] for i in range(1, 7))
        r3 = sum(s[f"R3.{i}"] for i in range(1, 7))
        r4 = sum(s[f"R4.{i}"] for i in range(1, 7))
        r5 = sum(s[f"R5.{i}"] for i in range(1, 7))
        lines.append(f"| {e['lib']} | {e['n_epyson']} | {e['raw']} | **{e['score_100']}** | {r1} | {r2} | {r3} | {r4} | {r5} |")

    # per-criterion grid
    lines.append("\n## Per-criterion grid (1=critical, 5=excellent)\n")
    header = "| Lib | " + " | ".join(rubrics) + " |"
    sep = "|---|" + "|".join(["---:"] * len(rubrics)) + "|"
    lines.append(header)
    lines.append(sep)
    for e in per_lib:
        row = "| " + e["lib"] + " | " + " | ".join(str(e["scores"][r]) for r in rubrics) + " |"
        lines.append(row)

    # cross-suite totals
    total_raw = sum(e["raw"] for e in per_lib)
    max_raw = 150 * len(per_lib)
    cross_100 = round(total_raw / (1.5 * len(per_lib)), 1)
    lines.append(f"\n## Cross-suite score: **{cross_100} / 100**  (raw {total_raw} / {max_raw})\n")

    return "\n".join(lines)


def main() -> int:
    per_lib = [score_lib(lib) for lib in LIBS]
    compute_r26_cross_lib(per_lib)
    md = render_markdown(per_lib)
    out_md = Path(__file__).parent / "epyson_canon_score.md"
    out_json = Path(__file__).parent / "epyson_canon_score.json"
    out_md.write_text(md, encoding="utf-8")
    out_json.write_text(json.dumps(per_lib, indent=2, default=str), encoding="utf-8")
    print(md)
    print(f"\nWritten: {out_md}\nWritten: {out_json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
