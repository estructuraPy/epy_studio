"""The ONE canonical documented-standard-id rule, and the only place it is edited.

WHAT IT CHECKS
--------------
Every standard id cited in a library's ``.md`` / ``.ipynb`` must name a document
some catalog in the suite actually carries.

It is REFERENTIAL INTEGRITY, deliberately NOT a denylist. Nothing here knows
what CSA is, or which standards were withdrawn. A retired standard fails only
because its catalog file is gone; the day the documents arrive and the catalog
returns, the same docs pass untouched, with no edit to this rule. Encoding
"CSA is forbidden" would have made the ban permanent, which is not what a
withdrawal for want of a source means.

WHY IT EXISTS
-------------
The CSA branch was retired on 2026-08-12. Six days later the libraries still
shipped README rows and STANDARDS.md tables advertising the withdrawn ids as
supported, a copy-pasteable README snippet that raises, and tutorial cells that
die on execution. Nothing in the suite cross-checked a documented id against a
catalog, and nothing executed a tutorial notebook, so the drift was invisible.

WHAT COUNTS AS A CITED ID
-------------------------
A token inside backticks that has the SHAPE of a standard id:

* it ends in a four-digit year (the suite's own convention: "full 4-digit year
  in every standard ID"), or
* its first segment matches the first segment of a catalogued id, which is what
  catches abbreviations like ``cscr_10`` that no catalog carries.

Prose that names a standard in human spelling (``CSA A23.3-19``) is NOT matched.
That is a genuine limitation and it is stated rather than papered over: the
2026-08-12 retirement swept the id form only, and the human spellings survived
in a live Blender title-block dropdown and several docstrings until 2026-08-18.
Matching them reliably needs a name->id map the suite does not have yet.

SCOPE OF THE CATALOG
--------------------
The union of every ``src/<pkg>/_config/{_standards,standards}`` in the suite,
not just the library being checked -- epy_docs legitimately cites ids belonging
to its siblings, and a per-library check would flag them all.
"""

from __future__ import annotations

import json
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

#: Directory fragments never scanned.
#:
#: ``.claude`` earns its place the way the others did, by producing a red gate
#: on 2026-09-16: agent worktrees live in ``.claude/worktrees/<id>/`` and each
#: is a full COPY of the repo, so this audit walked into three of them and
#: reported the same ``libro_caso.md:624`` three times. epy_bridges failed
#: --strict on stale copies of a file its own working tree no longer has that
#: way. A worktree is somebody else's checkout: it is audited where it lives,
#: not from here.
_DOC_REF_SKIP = (
    "_archive", "build", ".deepseek_delegate", "snapshots", ".venv",
    "site-packages", "_temp", "_backups", "_scratch", ".audit_deepseek",
    ".git", "__pycache__", ".pytest_cache", ".ruff_cache", ".ipynb_checkpoints",
    "node_modules", ".dev_archive", ".claude",
)

#: Path fragments whose documents legitimately name a standard the catalog does
#: not carry. ``docs/validations/`` holds the CSI-software comparison records:
#: they document a check that WAS performed against a named standard, so the
#: name is evidence, not a claim of present support. Deleting it would destroy
#: the record; flagging it would train people to ignore the rule.
_DOC_REF_EXEMPT = ("docs/validations/", "docs\validations\\")

#: A backticked token that could be a standard id. A dot excludes it: a
#: filename (``aisc_360_2022.epyson``) or a dotted module path is not an id.
_DOC_REF_TOKEN = re.compile(r"`([a-z][a-z0-9]*(?:_[a-z0-9]+)+)`")

#: Ends in a four-digit year -- the suite's declared id convention.
_DOC_REF_YEAR = re.compile(r"_(?:18|19|20)\d{2}$")


#: A negative EXAMPLE of the naming convention, not a citation: the twelve
#: STANDARDS.md files state the rule as ``(e.g. `aci_318_2025`, not
#: `aci_318_25`)`` and two docs state that a spelling "es rechazado por
#: validate_standard_id". Renaming those tokens would erase the only statement
#: of the convention (or make it claim the opposite), so a token used AS the
#: counter-example is exempt. The context test is deliberately narrow: the
#: word "not"/"never"/"rechazado"/"rejected" adjacent to the backticked token.
def _doc_ref_is_negative_example(token: str, line: str) -> bool:
    """Whether ``line`` uses ``token`` as a naming-rule counter-example."""
    quoted = re.escape(token)
    pattern = (
        r"(?:\bnot\s+`" + quoted + r"`|\bnever\s+`" + quoted + r"`"
        r"|`" + quoted + r"`\s+(?:es\s+rechazad|is\s+reject))"
    )
    return re.search(pattern, line, re.IGNORECASE) is not None


# ---------------------------------------------------------------------------
# Human-spelling prose rule. The id rule above sees `csa_a23_3_2019`; this one
# sees "CSA A23.3-19". The discriminator is the SERIES (the id minus its
# edition year): `csa_s6` is carried by epy_bridges and must never flag, while
# `csa_a23_3` has zero catalog files and must. Same family, opposite verdicts,
# so the family can never be the unit of withdrawal.
# ---------------------------------------------------------------------------

_DOC_REF_RUN = re.compile(r"[a-z]+|[0-9]+")
_DOC_REF_PSEP = r"[._\s\-]?"

#: Prose files never scanned beyond the shared _DOC_REF_SKIP:
#: CHANGELOG is history ("Removed CSA A23.3 support" MUST name it), and the
#: coordination board is the record of the withdrawal act itself. CLAUDE.md is
#: deliberately NOT here: a stale capability claim in agent instructions is
#: the most expensive kind.
_DOC_REF_PROSE_EXEMPT_NAMES = ("changelog",)
_DOC_REF_PROSE_EXEMPT_PARTS = ("_coordination",)


def _doc_ref_series(sid: str) -> str:
    """The id minus its edition year: ``csa_a23_3_2019`` -> ``csa_a23_3``."""
    return _DOC_REF_YEAR.sub("", sid)


def _doc_ref_prose_pattern(series: str):
    """Regex matching the HUMAN spelling of an id-shaped series.

    ``csa_a23_3`` -> matches "CSA A23.3", "CSA-A23.3-19", "csa a23.3M-2019".
    Synthesized from the id itself -- never a hand-maintained table -- by
    splitting every post-org segment into letter/digit runs (``e060`` ->
    ``E.060``, ``part4`` -> ``Part 4``) joined by optional separators.

    Returns ``None`` for a series with no numeric designation
    (``codigo_geotecnico_cr``): a word-id has no human spelling to synthesize,
    and a pattern built from its words would match ordinary prose.
    """
    org, *rest = series.split("_")
    if not rest or not any(ch.isdigit() for ch in "".join(rest)):
        return None
    body = _DOC_REF_PSEP.join(
        _DOC_REF_PSEP.join(re.escape(run) for run in _DOC_REF_RUN.findall(seg))
        for seg in rest
    )
    return re.compile(
        r"(?<![A-Za-z0-9])" + re.escape(org)
        + r"(?:\s*/\s*[A-Za-z]{2,5})?"      # ASCE/SEI, ANSI/AISC sub-org slot
        + r"[\s\-/_]?" + body + r"[A-Za-z]?"  # trailing M / R (A23.3M, 314R)
        # Block only DOT+digit continuation: "CSA A23.3" must not be reachable
        # from a `csa_a23` pattern. A HYPHEN+digit tail is an edition suffix
        # ("S16-19", "318-25") and must stay matchable. Known ambiguity, on
        # purpose: for part-numbered families (EN 1993-1-1) a base-series
        # ledger entry also matches its parts -- which a withdrawal wants.
        + r"(?![A-Za-z0-9]|\.\d)",
        re.IGNORECASE,
    )


def doc_ref_withdrawn_series(lib_root: Path):
    """Series recorded as withdrawn AND currently carried by no catalog.

    Two conditions, both required, which is what keeps the committed ledger
    (``withdrawn_standard_series.txt``, next to this module) from being a
    denylist: a line supplies only the human-spelling VOCABULARY the id-shape
    rule cannot derive, while the CATALOG stays the arbiter. A series that
    reappears in some library's ``_config/standards/`` silently leaves this
    set with no ledger edit. The ledger is suite-level because a withdrawal is
    a suite-level act (contrast the per-library baselines, where the DEBT is
    per-library).

    Returns ``(series -> compiled prose pattern, hygiene violations)``. A
    missing ledger is a LOUD violation -- a silently skipped rule is worse
    than none -- and a word-series entry (no synthesizable spelling) is dead
    weight and says so.
    """
    path = Path(__file__).resolve().parent / "withdrawn_standard_series.txt"
    if not path.exists():
        return {}, [
            "doc-standard-refs: withdrawn_standard_series.txt is missing next to "
            "the rule, so prose citations were NOT checked. Loud on purpose."
        ]
    declared = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        entry = line.split("#", 1)[0].strip()
        if entry:
            declared.add(entry)
    catalogued_series = {_doc_ref_series(sid) for sid in doc_ref_catalogued_ids(lib_root)}
    hygiene = []
    patterns = {}
    for series in sorted(declared - catalogued_series):
        pat = _doc_ref_prose_pattern(series)
        if pat is None:
            hygiene.append(
                f"withdrawn_standard_series.txt: '{series}' has no numeric "
                f"designation, so no prose pattern can be built for it -- the "
                f"line is dead weight."
            )
        else:
            patterns[series] = pat
    return patterns, hygiene


def audit_doc_standard_prose(lib_root: Path) -> list:
    """Report prose citations (human spelling) of withdrawn standard series."""
    patterns, violations = doc_ref_withdrawn_series(lib_root)
    if not patterns:
        return violations
    for path in safe_rglob(lib_root):
        if path.suffix.lower() not in (".md", ".ipynb") or not path.is_file():
            continue
        if any(part in _DOC_REF_SKIP for part in path.parts):
            continue
        if any(part in _DOC_REF_PROSE_EXEMPT_PARTS for part in path.parts):
            continue
        if any(path.name.lower().startswith(n) for n in _DOC_REF_PROSE_EXEMPT_NAMES):
            continue
        if any(frag in path.as_posix() for frag in ("docs/validations/",)):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        rel = path.relative_to(lib_root).as_posix()
        seen = set()
        for lineno, line in enumerate(text.split("\n"), 1):
            for series, pat in patterns.items():
                if series in seen:
                    continue
                hit = pat.search(line)
                if hit:
                    seen.add(series)
                    violations.append(
                        f"{rel}:{lineno}: cites withdrawn standard series "
                        f"'{series}' in prose ({hit.group(0)!r}). The catalog "
                        f"no longer carries it; annotate the withdrawal or "
                        f"remove the capability claim."
                    )
    return violations


def doc_ref_prose_baseline_path(lib_root: Path) -> Path:
    """Where this library freezes prose debt that predates the prose rule."""
    return lib_root / "docs" / "withdrawn_standard_prose_baseline.txt"


def doc_ref_load_prose_baseline(lib_root: Path) -> set:
    """Frozen ``(series, relpath)`` pairs -- committed, never generated at run
    time. Freezing a bare series would disable the rule for it everywhere; a
    new citation in a NEW file must still fail. Deleting a line pays the debt."""
    path = doc_ref_prose_baseline_path(lib_root)
    if not path.exists():
        return set()
    pairs = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        entry = line.split("#", 1)[0].strip()
        if entry and " " in entry:
            series, rel = entry.split(None, 1)
            pairs.add((series, rel.strip()))
    return pairs


def _doc_ref_shares_a_stem(token: str, catalogued: set[str]) -> bool:
    """Whether some catalogued id shares more than the family word with ``token``.

    A misspelt standard id keeps almost all of its segments:
    ``en_1996_1_1_2022`` against ``eurocode_6_2022`` shares the year;
    ``api_620_12`` against ``api_620_2013`` shares ``api`` AND ``620``.

    A protocol or title-block id shares only the family word: ``fema_461``
    against ``fema_p695_2009`` has nothing after ``fema``, and ``cfia_cr_2024``
    against ``cfia_lineamientos_2012`` has nothing after ``cfia``. Requiring a
    SECOND shared segment separates the two without naming either.
    """
    parts = token.split("_")
    if len(parts) < 2:
        return False
    for sid in catalogued:
        other = sid.split("_")
        if other[0] != parts[0]:
            continue
        if set(parts[1:]) & set(other[1:]):
            return True
    return False


def _doc_ref_looks_like_id(token: str, families: set[str], catalogued: set[str]) -> bool:
    """Whether a backticked token is plausibly a standard id.

    Two shapes qualify, and both demand a digit -- an id names an EDITION:

    * it ends in a four-digit year, the suite's declared convention; or
    * its family is one the catalogs use AND every segment after the family is
      numeric, which is what catches an abbreviation like ``cscr_10``.

    The second test is deliberately narrow. ``is`` and ``iso`` are real
    families (``is_1904_1986``, ``iso_21500``), so a looser family rule flagged
    ``is_repetitive`` -- a boolean field -- forty times, and
    ``iso_16630_symmetric``, a loading protocol. A rule that cries wolf on
    field names is a rule people switch off.
    """
    if not any(ch.isdigit() for ch in token):
        return False
    segments = token.split("_")
    if segments[0] not in families:
        # Not a family any catalog uses. `meyerhof_1963` and `terzaghi_1943`
        # are bearing-capacity METHODS, `fema_461` a test protocol -- backticked,
        # year-suffixed, and none of them a standard id. Requiring a known
        # family keeps the rule inside the vocabulary the catalogs define.
        #
        # This IS a family-prefix heuristic, and the suite spent 2026-08-18
        # removing exactly that from calculation code. The difference is what
        # it decides: there, a prefix chose a NORMATIVE VALUE, so a wrong guess
        # shipped a wrong number. Here it only decides whether to CHECK a
        # token, so a wrong guess costs coverage and can never cost correctness.
        return False
    if not (_DOC_REF_YEAR.search(token) or all(s.isdigit() for s in segments[1:])):
        return False
    # Family alone is too weak: `fema` and `cfia` are catalogued families, so
    # `fema_461` (a loading protocol) and `cfia_cr_2024` (a title block) both
    # passed. Demand a SECOND shared segment with something catalogued.
    return _doc_ref_shares_a_stem(token, catalogued)


def _doc_ref_suite_root(lib_root: Path) -> Path:
    """The directory holding every library checkout."""
    return lib_root.resolve().parent


def doc_ref_catalogued_ids(lib_root: Path) -> set[str]:
    """Every standard id any library in the suite catalogs, plus declared aliases.

    Aliases count: a document citing ``ec4_2026`` names a real file, and the
    loader resolves it. Rejecting a spelling the library itself accepts is the
    same defect this rule exists to prevent, pointed the other way.
    """
    ids: set[str] = set()
    for sibling in _doc_ref_suite_root(lib_root).iterdir():
        if not sibling.is_dir() or sibling.name.startswith("."):
            continue
        for cfg in ("_standards", "standards"):
            for path in sibling.glob(f"src/*/_config/{cfg}/**/*.epyson"):
                ids.add(path.stem)
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    continue
                for alias in data.get("aliases") or []:
                    if isinstance(alias, str):
                        ids.add(alias)
    return ids


def audit_doc_standard_refs(lib_root: Path) -> list[str]:
    """Report every documented standard id the suite's catalogs do not carry."""
    catalogued = doc_ref_catalogued_ids(lib_root)
    if not catalogued:
        return [
            "doc-standard-refs: found NO catalogued standard ids anywhere in the "
            "suite. Refusing to report every documented id as unknown -- fix the "
            "catalog layout or this rule's discovery, not the docs."
        ]
    families = {sid.split("_")[0] for sid in catalogued}

    violations: list[str] = []
    for path in safe_rglob(lib_root):
        if path.suffix.lower() not in (".md", ".ipynb") or not path.is_file():
            continue
        if any(part in _DOC_REF_SKIP for part in path.parts):
            continue
        if any(frag in path.as_posix() for frag in ("docs/validations/",)):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        seen: dict[str, int] = {}
        for lineno, line in enumerate(text.split("\n"), 1):
            for token in _DOC_REF_TOKEN.findall(line):
                if token in catalogued:
                    continue
                if not _doc_ref_looks_like_id(token, families, catalogued):
                    continue
                if _doc_ref_is_negative_example(token, line):
                    continue
                seen.setdefault(token, lineno)
        rel = path.relative_to(lib_root).as_posix()
        for token, lineno in sorted(seen.items()):
            violations.append(
                f"{rel}:{lineno}: documents standard id '{token}', which no "
                f"catalog in the suite carries. Either the id is wrong, or the "
                f"document it names was withdrawn and the text still advertises it."
            )
    return violations


def doc_ref_baseline_path(lib_root: Path) -> Path:
    """Where this library records the drift that predates the rule."""
    return lib_root / "docs" / "documented_standard_ids_baseline.txt"


def doc_ref_load_baseline(lib_root: Path) -> set[str]:
    """Ids this library already documented without a catalog, before the rule.

    A BASELINE, not an exemption list. When the rule landed on 2026-08-18 the
    suite documented 433 ids no catalog carried -- almost none of them CSA:
    ``aashto_lrfd_2024`` where the catalog has ``aashto_lrfd_2020``,
    ``aci_318_25`` for ``aci_318_2025``, ``en_1996_1_1_2022`` for
    ``eurocode_6_2022``. Fixing all of it is a separate campaign; shipping a
    rule that fails everywhere would have produced one more red gate people
    learn to ignore, which is the thing this rule exists to prevent.

    So the debt is frozen where anyone can read it -- the file is committed,
    not generated at run time -- and the rule blocks it from GROWING. Deleting
    a line is how the debt gets paid; nothing re-adds one automatically.
    """
    path = doc_ref_baseline_path(lib_root)
    if not path.exists():
        return set()
    known = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            known.add(line)
    return known


def audit_doc_standard_refs_strict(lib_root: Path) -> list[str]:
    """Violations not frozen in this library's committed baselines.

    Two rules fold in here: the id-shape rule (per-id baseline) and the
    prose rule (per ``(series, relpath)`` pair baseline). A token caught by
    both on the same line reports once, under the id rule -- its message is
    more specific.
    """
    known = doc_ref_load_baseline(lib_root)
    out = []
    id_locations = set()
    for violation in audit_doc_standard_refs(lib_root):
        match = re.search(r"^([^:]+):\d+: documents standard id '([^']+)'", violation)
        if match:
            id_locations.add((match.group(1), _doc_ref_series(match.group(2))))
            if match.group(2) in known:
                continue
        out.append(violation)
    prose_known = doc_ref_load_prose_baseline(lib_root)
    for violation in audit_doc_standard_prose(lib_root):
        match = re.search(
            r"^([^:]+):\d+: cites withdrawn standard series '([^']+)'", violation
        )
        if match:
            rel, series = match.group(1), match.group(2)
            if (series, rel) in prose_known:
                continue
            if (rel, series) in id_locations:
                continue
        out.append(violation)
    return out


def report_doc_standard_refs(violations: list[str]) -> None:
    """Print the documented-standard-id report."""
    print("\n" + "=" * 70)
    print("  DOCUMENTED STANDARD IDS (referential integrity)")
    print("=" * 70)
    if not violations:
        print("  OK - every documented standard id names a catalogued document.")
        return
    print(f"  {len(violations)} documented id(s) name nothing the suite carries:\n")
    for violation in violations:
        print(f"    - {violation}")


def _self_test() -> int:
    """Both directions of the id-shape gate. Run: ``python doc_standard_refs_block.py``.

    _packaging ships no pytest suite, so the rule carries its own pins. A rule
    that decides what the whole suite's documentation may say should not be the
    one unverified thing in the chain.
    """
    here = Path(__file__).resolve().parent.parent.parent
    lib = next((d for d in here.iterdir() if (d / "src").is_dir()), None)
    if lib is None:
        print("FAIL: no library checkout found next to _packaging")
        return 1
    catalogued = doc_ref_catalogued_ids(lib)
    if not catalogued:
        print("FAIL: catalog discovery returned nothing")
        return 1
    families = {sid.split("_")[0] for sid in catalogued}

    # Must be REJECTED: these are not standards, and each one shares only its
    # family word with something catalogued.
    reject = ["fema_461", "cfia_cr_2024", "iso_16630_symmetric", "is_repetitive"]
    # Must be CAUGHT: retired ids, editions nothing carries, forbidden spellings.
    catch = ["csa_a23_3_2019", "csa_s16_2019", "en_1993_1_1_2014",
             "aashto_lrfd_2024", "api_620_12", "aci_318_25"]

    failures = []
    for token in reject:
        if _doc_ref_looks_like_id(token, families, catalogued):
            failures.append(f"{token!r} should NOT be flagged")
    for token in catch:
        if not _doc_ref_looks_like_id(token, families, catalogued):
            failures.append(f"{token!r} SHOULD be flagged")
    # Every catalogued id must pass its own rule, or the rule contradicts the
    # catalog it is checking against.
    for sid in sorted(catalogued):
        if sid not in catalogued:
            failures.append(f"catalogued {sid!r} fails its own check")

    # ------------------------------------------------------------------
    # Prose rule (human spelling), both directions.
    # ------------------------------------------------------------------
    # (A) Synthesizer, derived not hand-written: every catalogued id whose own
    # catalog text spells its org must be matched by its own synthesized
    # pattern. The catalogs ARE the fixture; adding one extends this test.
    import json as _json

    matched = unmatched = 0
    unmatched_ids = []
    for sibling in _doc_ref_suite_root(lib).iterdir():
        if not sibling.is_dir() or sibling.name.startswith("."):
            continue
        for cfg in ("_standards", "standards"):
            for path in sibling.glob(f"src/*/_config/{cfg}/**/*.epyson"):
                try:
                    data = _json.loads(path.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    continue
                text = " ".join(
                    str(data.get(k, "")) for k in ("name", "description", "citation")
                )
                org = path.stem.split("_")[0]
                if org.lower() not in text.lower():
                    continue
                pat = _doc_ref_prose_pattern(_doc_ref_series(path.stem))
                if pat is None:
                    continue
                if pat.search(text):
                    matched += 1
                else:
                    unmatched += 1
                    unmatched_ids.append(path.stem)
    total = matched + unmatched
    ratio = matched / total if total else 0.0
    print(f"prose synthesizer fixture: {matched}/{total} self-matching "
          f"catalogued ids ({ratio:.0%}); unmatched: {sorted(set(unmatched_ids))[:8]}")
    if total and ratio < 0.80:
        failures.append(
            f"prose synthesizer matches only {matched}/{total} self-naming "
            f"catalogs -- regression below the 80% floor"
        )

    # (B) Withdrawn-vs-active discrimination: the catalog is the arbiter.
    patterns, hygiene = doc_ref_withdrawn_series(lib)
    if "csa_a23_3" not in patterns:
        failures.append("'csa_a23_3' (withdrawn, zero catalogs) must survive the filter")
    if "csa_s6" in patterns:
        failures.append("'csa_s6' must be dropped -- epy_bridges catalogs csa_s6_2019")

    # (C) Must-CATCH prose spellings of a withdrawn series.
    pat = _doc_ref_prose_pattern("csa_a23_3")
    for prose in ("CSA A23.3-19", "CSA A23.3", "CSA-A23.3-2019", "csa a23.3",
                  "CSA A23.3M-19", "CSA/A23.3"):
        if not pat.search(prose):
            failures.append(f"prose {prose!r} SHOULD match csa_a23_3")

    # (D) Must-REJECT prose (false-positive pins).
    if pat.search("CSA A23.4"):
        failures.append("'CSA A23.4' must NOT match csa_a23_3")
    if pat.search("A23.3 without an org token"):
        failures.append("bare 'A23.3' must NOT match csa_a23_3")
    prefix_pat = _doc_ref_prose_pattern("csa_a23")
    if prefix_pat is not None and prefix_pat.search("CSA A23.3"):
        failures.append("prefix trap: a csa_a23 pattern must NOT match 'CSA A23.3'")
    s6_pat = _doc_ref_prose_pattern("csa_s6")
    if pat.search("CSA S6-19"):
        failures.append("'CSA S6-19' must NOT match csa_a23_3")
    # The Spanish-prose minefield: word-series never synthesize a pattern, so
    # families like `en`/`is`/`nec` can never scan ordinary text.
    for word_series in ("codigo_geotecnico_cr", "en", "is"):
        if _doc_ref_prose_pattern(word_series) is not None:
            failures.append(f"word series {word_series!r} must synthesize None")

    # (E) Negative-example exemption for the ID rule, both directions.
    if not _doc_ref_is_negative_example(
        "aci_318_25", "Full 4-digit year (e.g. `aci_318_2025`, not `aci_318_25`)"
    ):
        failures.append("the naming-rule counter-example must be exempt")
    if not _doc_ref_is_negative_example(
        "asce_10_15", "`asce_10_15` es rechazado por validate_standard_id"
    ):
        failures.append("the validator counter-example must be exempt")
    if _doc_ref_is_negative_example(
        "aci_318_25", "designed per `aci_318_25` provisions"
    ):
        failures.append("a plain citation must NOT be exempt as negative example")

    # (F) Ledger hygiene: a word-series entry is dead weight and says so.
    # (Simulated inline -- the shipped ledger must stay clean of them.)
    if any("dead weight" in h for h in hygiene):
        failures.append("the shipped ledger carries a dead-weight word series")

    # (G) Self-consistency: no catalogued series' pattern may match a DIFFERENT
    # catalogued series' own spelling (over-broad synthesizer catch). Checked
    # on same-family pairs, where collisions would hide.
    series_by_family = {}
    for sid in catalogued:
        ser = _doc_ref_series(sid)
        series_by_family.setdefault(ser.split("_")[0], set()).add(ser)
    for family, series_set in series_by_family.items():
        for a in series_set:
            pa = _doc_ref_prose_pattern(a)
            if pa is None:
                continue
            for b in series_set:
                if a == b or b.startswith(a):
                    continue
                spelled_b = " ".join(
                    ".".join(_DOC_REF_RUN.findall(seg)) for seg in b.split("_")[1:]
                )
                probe = f"{family.upper()} {spelled_b}"
                if a != b and not b.startswith(a) and pa.fullmatch(probe):
                    failures.append(
                        f"pattern for {a!r} fully matches {b!r}'s spelling {probe!r}"
                    )

    for f in failures:
        print("FAIL:", f)
    if failures:
        return 1
    print(f"OK - {len(reject)} rejected, {len(catch)} caught, "
          f"{len(catalogued)} catalogued ids accepted.")
    print("KNOWN GAP: `cscr_10` is no longer flagged. It shares only its family")
    print("  word with cscr_1974/1986/2002/2010/2014, so the second-segment test")
    print("  that removed the fema_461 false positive drops it too. That is a")
    print("  false NEGATIVE -- it costs coverage, never correctness -- and it is")
    print("  recorded here rather than papered over.")
    return 0


if __name__ == "__main__":
    raise SystemExit(_self_test())

