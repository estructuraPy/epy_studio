"""Cross-suite generalization of epy_concrete/_archive/migrate_epyson_canon.py.

Run on every .epyson under `src/<lib>/_config/` of each ePy lib:
  - ensure `<family>_id` top-level == filename stem (raises on mismatch)
  - add `version` (default "1.0.0") if missing
  - add `description` (inferred) if missing or < 20 chars
  - normalize `audit_status` to one of {verified, partial, needs_source_verification, n_a}
  - add `unit_system` top-level when numeric properties present
  - re-serialize indent=2, no BOM
  - for standards: backfill `country`, `edition_year`, `philosophy`, `complement_with`

Skips orphans (files without `<algo>_id`). Reports them so they can be fixed by
hand or by Phase B of the per-lib playbook.

Usage:
  python migrate_epyson_canon_xsuite.py            # dry-run, all 16 libs
  python migrate_epyson_canon_xsuite.py --apply    # actually write
  python migrate_epyson_canon_xsuite.py --apply --lib epy_steel
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import OrderedDict
from pathlib import Path
from typing import Any

ROOT = Path(r"C:\Users\ingah\estructuraPy")
LIBS = [
    "epy_analysis", "epy_bridges", "epy_buildings", "epy_compose",
    "epy_connections", "epy_geotechnical", "epy_houses",
    "epy_masonry", "epy_plotter", "epy_steel", "epy_structure",
    "epy_suite", "epy_tall", "epy_tanks", "epy_timber", "epy_towers",
]
# epy_concrete already at gold standard, skip by default

VALID_AUDIT = {"verified", "partial", "needs_source_verification", "n_a"}

CANONICAL_FIRST = (
    "standard_id", "material_id", "section_id", "layout_id",
    "constitutive_id", "config_id", "preset_id", "economics_id",
    "alignment_id", "fastener_id", "spectrum_id", "model_id",
    "typology_id", "catalog_id", "loads_id", "mapping_id",
    "version", "description", "audit_status", "audit_notes",
    "country", "edition_year", "philosophy", "complement_with",
    "language", "unit_system",
)

# Conservative Spanish→English dictionary — only unambiguous safe replacements
SPANISH_TO_ENGLISH = {
    "vivienda": "residential", "concreto": "concrete", "acero": "steel",
    "viga": "beam", "columna": "column", "muro": "wall", "losa": "slab",
    "cimentación": "foundation", "Análisis": "Analysis", "análisis": "analysis",
    "cálculo": "calculation", "Cálculo": "Calculation",
    "diseño": "design", "Diseño": "Design", "para": "for", "Para": "For",
    "por": "per", "Por": "Per", "que": "that", "los": "the", "las": "the",
    "del": "of the", "sin": "without", "Sin": "Without",
    "techo": "roof", "piso": "floor", "pared": "wall",
    "conexión": "connection", "Conexión": "Connection",
    "construcción": "construction", "Construcción": "Construction",
    "Hormigón": "Concrete", "hormigón": "concrete",
    "Armado": "Reinforced", "armado": "reinforced",
    "Norma": "Standard", "norma": "standard",
    "Estructuras": "Structures", "estructuras": "structures",
    "Estructura": "Structure", "estructura": "structure",
    "Codigo": "Code", "Código": "Code", "codigo": "code", "código": "code",
    "historico": "historical", "histórico": "historical",
    "evaluacion": "evaluation", "evaluación": "evaluation",
    "existentes": "existing", "construidas": "built", "construido": "built",
    "bajo": "under", "nuevo": "new", "nueva": "new", "apto": "suitable",
    "maximo": "maximum", "máximo": "maximum",
    "distincion": "distinction", "distinción": "distinction",
    "diametro": "diameter", "diámetro": "diameter",
    "barra": "bar", "barras": "bars",
    "deformacion": "strain", "deformación": "strain",
    "Deformacion": "Strain", "Deformación": "Strain",
    "unitaria": "unit", "ultima": "ultimate", "última": "ultimate",
    "Gancho": "Hook", "gancho": "hook",
    "sismico": "seismic", "sísmico": "seismic", "sísmica": "seismic", "sismica": "seismic",
    "estribos": "stirrups", "Estribos": "Stirrups",
    "porticos": "frames", "pórticos": "frames",
    "especiales": "special", "detallado": "detailing",
    "mejorado": "improved", "sobre": "over",
    "Título": "Title", "Titulo": "Title",
    "básico": "basic", "Básico": "Basic", "basico": "basic",
}


def detect_id_field(data: dict) -> tuple[str | None, str | None]:
    if not isinstance(data, dict):
        return None, None
    for k, v in data.items():
        if isinstance(k, str) and k.endswith("_id") and isinstance(v, str):
            return k, v
    return None, None


def infer_country(stem: str) -> str | None:
    s = stem.lower()
    if s.startswith(("aci_", "astm_", "aashto_", "aisc_", "asce_", "awc_", "nds_", "tms_")):
        return "USA"
    if s.startswith(("en_", "ec", "eurocode_")):
        return "EU"
    if s.startswith(("csa_", "can_")):
        return "CAN"
    if s.startswith(("cscr_", "nec_se", "cfia_", "mopt_", "cr_")):
        return "Costa Rica"
    if s.startswith(("nsr_", "nsr")):
        return "Colombia"
    if s.startswith("nch"):
        return "Chile"
    if s.startswith("nbr"):
        return "Brazil"
    if s.startswith("cirsoc"):
        return "Argentina"
    if s.startswith("din_") or s.startswith("din"):
        return "Germany"
    if s.startswith("jis_"):
        return "Japan"
    if s.startswith("gb_"):
        return "China"
    if s.startswith("is_"):
        return "India"
    return None


def infer_edition_year(stem: str) -> int | None:
    m = re.search(r"_(\d{4})(?:_|$)", stem)
    return int(m.group(1)) if m else None


def infer_philosophy(body_text: str) -> str:
    has_lrfd = "LRFD" in body_text or "phi_" in body_text or "phi factor" in body_text.lower()
    has_asd = "ASD" in body_text or "allowable_stress" in body_text.lower()
    if has_lrfd and has_asd:
        return "LRFD+ASD"
    if has_lrfd:
        return "LRFD"
    if has_asd:
        return "ASD"
    return "LRFD"


def is_local_code(stem: str) -> bool:
    return any(stem.lower().startswith(p) for p in ("cscr_", "nec_se", "cfia_", "mopt_", "cr_", "nsr_", "nch", "nbr_", "cirsoc"))


def primary_complement(lib: str) -> str:
    """Pick a sensible canonical international complement per lib."""
    m = {
        "epy_concrete": "aci_318_2025",
        "epy_steel": "aisc_360_2022",
        "epy_masonry": "tms_402_2013",
        # Renamed 2026-09-16: references.db holds NDS 2018 and no 2024 edition.
        "epy_timber": "nds_2018",
        "epy_compose": "aisc_360_2022",
        "epy_connections": "aisc_360_2022",
        "epy_bridges": "aashto_lrfd_2020",
        "epy_buildings": "asce_7_2022",
        "epy_houses": "asce_7_2022",
        "epy_tall": "asce_7_2022",
        "epy_tanks": "api_650_2020",
        "epy_towers": "asce_7_2022",
        "epy_structure": "asce_7_2022",
        "epy_analysis": "asce_7_2022",
        "epy_geotechnical": "asce_7_2022",
    }
    return m.get(lib, "asce_7_2022")


def infer_unit_system(data: dict) -> str:
    text = json.dumps(data)
    if re.search(r"_mpa\b", text, re.IGNORECASE) or "MPa" in text:
        return "MPa_m_kg"
    if re.search(r"_kpa\b|_pa\b", text, re.IGNORECASE):
        return "Pa_m_kg"
    return "SI_base"


def make_description(id_value: str, family: str, lib: str, data: dict) -> str:
    type_ = data.get("type", "")
    shape = data.get("shape", "")
    fam_clean = family.removesuffix("_id")
    if family == "standard_id":
        return f"Structural design code: {id_value.upper()} — full normative parameter set for design and verification in {lib}."
    if family == "material_id":
        ty = type_ or "material"
        return f"Material specification '{id_value}' ({ty}) — properties used by the {lib} design engine; cost and GWP via economics registry."
    if family == "section_id":
        sh = shape or "section"
        return f"Section geometry '{id_value}' ({sh}) — canonical dimensions used by section-property and design routines in {lib}."
    if family == "layout_id":
        return f"Plot styling preset '{id_value}' — font, palette, typography, figure size, and line styling for the {id_value} aesthetic ({lib})."
    if family == "constitutive_id":
        return f"Constitutive model '{id_value}' — stress-strain law and export configuration for non-linear solvers in {lib}."
    if family == "preset_id":
        return f"View preset '{id_value}' — camera, projection, filters, and overlay configuration for visualization in {lib}."
    if family == "economics_id":
        return f"Economics dataset '{id_value}' — cost or GWP values per material/region; consumed by the epy_suite economics registry."
    return f"Configuration entry '{id_value}' — canonical {fam_clean} record in {lib}."


def normalize_audit_status(value: Any) -> str:
    if isinstance(value, str):
        s = value.lower()
        if s.startswith("verified"):
            return "verified"
        if s.startswith("partial"):
            return "partial"
        if s.startswith("needs"):
            return "needs_source_verification"
        if s in {"n/a", "na", "n_a"}:
            return "n_a"
    return "needs_source_verification"


def fix_spanish_strings(obj: Any) -> tuple[Any, int]:
    fixes = 0
    if isinstance(obj, dict):
        new = {}
        for k, v in obj.items():
            new_v, f = fix_spanish_strings(v)
            fixes += f
            new[k] = new_v
        return new, fixes
    if isinstance(obj, list):
        out = []
        for v in obj:
            new_v, f = fix_spanish_strings(v)
            fixes += f
            out.append(new_v)
        return out, fixes
    if isinstance(obj, str):
        original = obj
        for es, en in SPANISH_TO_ENGLISH.items():
            obj = re.sub(rf"\b{re.escape(es)}\b", en, obj)
        if obj != original:
            fixes += 1
        return obj, fixes
    return obj, fixes


def canonical_order(data: dict) -> "OrderedDict[str, Any]":
    out: "OrderedDict[str, Any]" = OrderedDict()
    for k in CANONICAL_FIRST:
        if k in data:
            out[k] = data[k]
    for k in sorted(data.keys()):
        if k not in out:
            out[k] = data[k]
    return out


def migrate_file(path: Path, lib: str) -> tuple[dict | None, list[str]]:
    notes: list[str] = []
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        notes.append("strip BOM")
        raw = raw[3:]
    try:
        text = raw.decode("utf-8")
        data = json.loads(text)
    except Exception as e:
        return None, [f"JSON parse error: {e}"]
    if not isinstance(data, dict):
        return None, ["top-level not object"]

    family, id_value = detect_id_field(data)
    if family is None:
        return data, ["ORPHAN (no <algo>_id top-level)"]
    if id_value != path.stem:
        return data, [f"ID mismatch: '{id_value}' != stem '{path.stem}' — skipping"]

    if "version" not in data or not isinstance(data.get("version"), str):
        data["version"] = "1.0.0"
        notes.append("add version=1.0.0")

    desc = data.get("description")
    if not (isinstance(desc, str) and len(desc.strip()) >= 20):
        data["description"] = make_description(id_value, family, lib, data)
        notes.append("set canonical description")

    new_audit = normalize_audit_status(data.get("audit_status"))
    if data.get("audit_status") != new_audit:
        if "audit_status" in data:
            notes.append(f"normalize audit_status -> '{new_audit}'")
        else:
            notes.append("add audit_status=needs_source_verification")
        data["audit_status"] = new_audit

    if "unit_system" not in data:
        text_body = json.dumps(data)
        if re.search(r":\s*-?\d", text_body):
            data["unit_system"] = infer_unit_system(data)
            notes.append(f"add unit_system={data['unit_system']}")

    data, fixes = fix_spanish_strings(data)
    if fixes:
        notes.append(f"english strings fixed ({fixes})")

    if family == "standard_id":
        if "country" not in data:
            c = infer_country(path.stem)
            if c:
                data["country"] = c
                notes.append(f"add country={c}")
        if "edition_year" not in data:
            y = infer_edition_year(path.stem)
            if y:
                data["edition_year"] = y
                notes.append(f"add edition_year={y}")
        if "philosophy" not in data:
            data["philosophy"] = infer_philosophy(json.dumps(data))
            notes.append(f"add philosophy={data['philosophy']}")
        if is_local_code(path.stem) and "complement_with" not in data:
            data["complement_with"] = primary_complement(lib)
            notes.append(f"add complement_with={primary_complement(lib)}")

    return canonical_order(data), notes


def lib_config_dir(lib: str) -> Path:
    return ROOT / lib / "src" / lib.lower() / "_config"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--lib", help="run on a single lib (default: all 16 non-concrete)")
    args = ap.parse_args()

    libs = [args.lib] if args.lib else LIBS
    grand_changed = grand_skipped = grand_errors = grand_orphans = 0
    per_lib_summary: list[tuple[str, int, int, int, int]] = []
    for lib in libs:
        cfg = lib_config_dir(lib)
        if not cfg.exists():
            print(f"  [skip] {lib}: no _config/")
            continue
        files = sorted(cfg.rglob("*.epyson"))
        print(f"\n== {lib} ({len(files)} .epyson) ==")
        c = s = e = o = 0
        for p in files:
            try:
                new_data, notes = migrate_file(p, lib)
                if not notes:
                    s += 1
                    continue
                if any("ORPHAN" in n for n in notes):
                    print(f"  [orphan] {p.relative_to(cfg)}: {'; '.join(notes)}")
                    o += 1
                    continue
                if any("skipping" in n.lower() for n in notes):
                    print(f"  [skip] {p.relative_to(cfg)}: {'; '.join(notes)}")
                    s += 1
                    continue
                print(f"  [{'apply' if args.apply else 'dry'}] {p.relative_to(cfg)}: {'; '.join(notes)}")
                if args.apply and new_data is not None:
                    p.write_text(json.dumps(new_data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
                c += 1
            except Exception as exc:
                print(f"  [ERROR] {p.relative_to(cfg)}: {exc}", file=sys.stderr)
                e += 1
        per_lib_summary.append((lib, c, s, e, o))
        grand_changed += c
        grand_skipped += s
        grand_errors += e
        grand_orphans += o

    print("\n" + "=" * 70)
    print(f"{'lib':<22}{'changed':>10}{'skipped':>10}{'errors':>10}{'orphans':>10}")
    for lib, c, s, e, o in per_lib_summary:
        print(f"{lib:<22}{c:>10}{s:>10}{e:>10}{o:>10}")
    print(f"{'TOTAL':<22}{grand_changed:>10}{grand_skipped:>10}{grand_errors:>10}{grand_orphans:>10}")
    return 0 if grand_errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
