"""A magnitude names its unit, and the rule that says so has to bite.

Mirrors unit_suffix_block.py.

The case this measures is dated and real. Until 2026-09-23 epy_timber shipped
``"length": 51.0`` for a 6d common nail (MILLIMETRES, in
``_sections/_fasteners/common_nails.epyson``) and ``"length": 0.836`` for a
stud wall (METRES, in ``_sections/_rectangular/muro_entramado_2x4.epyson``).
Same key, same library, two units, and the consumers guessed: ``_fibers.py``
read the bare key as metres and invented ``0.1`` when it was absent.

A rule installed into 31 housekeepers that reports OK on the day it lands
proves nothing by itself -- OK is also what a rule that never ran prints. So
every test here builds the violation for real and asserts it is CAUGHT, and
the exclusions are tested the same way, because a rule that fires on a font
weight would be reverted within a day and take the real one with it.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

_BLOCK = Path(__file__).resolve().parent / "unit_suffix_block.py"
_spec = importlib.util.spec_from_file_location("_unit_suffix_block_under_test", _BLOCK)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
audit_unit_suffixes = _mod.audit_unit_suffixes
report_unit_suffixes = _mod.report_unit_suffixes


def _catalogue(root: Path, rel: str, payload: dict) -> Path:
    """Write an .epyson at ``rel`` under a repo-shaped ``src`` tree."""
    path = root / "src" / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


class TestItCatchesTheBareMagnitude:
    def test_the_nail_that_started_this(self, tmp_path):
        """The real record: a 6d common at 51.0, and nothing saying of what."""
        _catalogue(tmp_path, "epy_timber/_config/_sections/_fasteners/common_nails.epyson",
                   {"nail_6d": {"length": 51.0, "diameter": 2.87}})
        violations = audit_unit_suffixes(tmp_path)
        assert len(violations) == 1
        assert "'length' x1" in violations[0]
        assert "'diameter' x1" in violations[0]

    def test_the_file_is_named_so_it_can_be_fixed(self, tmp_path):
        _catalogue(tmp_path, "epy_steel/_config/_sections/_bars/rebar.epyson",
                   {"n10": {"weight": 6.404}})
        assert "_sections/_bars/rebar.epyson" in audit_unit_suffixes(tmp_path)[0]

    def test_it_counts_repeats_rather_than_reporting_one(self, tmp_path):
        """One line per file, with the tally -- 84 keys in two epy_houses
        catalogues would otherwise be 84 lines of the same sentence."""
        _catalogue(tmp_path, "epy_houses/_config/typologies/walls.epyson",
                   {"a": {"width": 0.12}, "b": {"width": 0.15}, "c": {"width": 0.2}})
        assert "'width' x3" in audit_unit_suffixes(tmp_path)[0]

    def test_it_descends_into_lists(self, tmp_path):
        _catalogue(tmp_path, "epy_masonry/_config/_materials/clay.epyson",
                   {"units": [{"height": 71}, {"height": 52}]})
        assert "'height' x2" in audit_unit_suffixes(tmp_path)[0]

    @pytest.mark.parametrize("key", ["length", "area", "weight", "thickness",
                                     "yield_strength", "perimeter", "span"])
    def test_every_name_on_the_list_is_actually_checked(self, tmp_path, key):
        """The dimensional names are DATA; a name that silently fell out of the
        frozenset would leave its catalogues unguarded and look identical."""
        _catalogue(tmp_path, f"lib/_config/_sections/{key}.epyson", {"x": {key: 1.0}})
        assert audit_unit_suffixes(tmp_path), f"'{key}' is listed but never fires"


class TestItAcceptsWhatAlreadyDeclares:
    @pytest.mark.parametrize("key", ["length_mm", "width_m", "area_cm2",
                                     "weight_kg_m", "yield_strength_MPa",
                                     "perimeter_mm", "thickness_in",
                                     "pressure_kPa", "load_kN", "moment_kN_m"])
    def test_a_declared_unit_passes(self, tmp_path, key):
        _catalogue(tmp_path, "lib/_config/_sections/s.epyson", {"x": {key: 1.0}})
        assert audit_unit_suffixes(tmp_path) == []

    def test_a_text_value_is_not_a_magnitude(self, tmp_path):
        """``"length": "varies"`` has no unit to declare; only numbers do."""
        _catalogue(tmp_path, "lib/_config/_sections/s.epyson", {"x": {"length": "varies"}})
        assert audit_unit_suffixes(tmp_path) == []

    def test_a_boolean_is_not_a_magnitude(self, tmp_path):
        """bool is a subclass of int; without the explicit check, a flag named
        ``span`` would be reported as an undeclared length."""
        _catalogue(tmp_path, "lib/_config/_sections/s.epyson", {"x": {"span": True}})
        assert audit_unit_suffixes(tmp_path) == []

    def test_a_repo_without_src_is_not_an_error(self, tmp_path):
        assert audit_unit_suffixes(tmp_path) == []


class TestTheRuleIsNarrowOnPurpose:
    """Only a key whose WHOLE name is a dimensional word is checked.

    A broader rule -- parse the ending and demand a recognised unit -- was
    written, measured over 562581 numeric keys in the suite and thrown away:
    it flagged 78, of which one was a real misspelling and 77 were standards
    notation. These tests pin that decision so it is not quietly reopened.
    """

    @pytest.mark.parametrize("key", ["gamma_M2", "gamma_M3", "gamma_M4",
                                     "gust_factor_G", "mc_M_or_S", "alpha_S",
                                     "phi_c", "Omega_c", "phi_k", "D_f",
                                     "CM_wet_service_Ft", "top_n"])
    def test_a_standards_subscript_is_never_read_as_a_unit(self, tmp_path, key):
        """Every one of these lives in the suite today and none names a unit:
        gamma_M2 is the Eurocode partial factor, mc_M_or_S is Type M or S
        mortar, phi_k is the characteristic value, CM_wet_service_Ft is the NDS
        tension designation, top_n is a count. A rule that parsed endings read
        them as square metres, seconds, kelvin, feet and newtons."""
        _catalogue(tmp_path, "lib/_config/_standards/s.epyson", {"x": {key: 1.25}})
        assert audit_unit_suffixes(tmp_path) == [], f"'{key}' is notation, not a unit"

    @pytest.mark.parametrize("key", ["length_threshold_in", "spacing_max_m",
                                     "spacing_db_multiplier", "stress_trigger_ratio",
                                     "velocity_pressure_coefficient",
                                     "depth_min_fraction_of_beam_depth"])
    def test_a_qualified_name_is_not_a_bare_magnitude(self, tmp_path, key):
        """A qualifier after the dimensional word puts the key outside this
        rule, whether or not a unit follows. Reading those endings is what the
        rejected rule did."""
        _catalogue(tmp_path, "lib/_config/_standards/s.epyson", {"x": {key: 1.0}})
        assert audit_unit_suffixes(tmp_path) == []

    def test_the_other_two_ways_of_declaring_a_unit_are_left_alone(self, tmp_path):
        """The suite declares units three ways and all are legitimate: a key
        suffix, a file-level unit_system, and a per-value {value, unit}. Only a
        key that declares NOTHING is a violation."""
        _catalogue(tmp_path, "lib/_config/_materials/m.epyson",
                   {"unit_system": "MPa_m_kg",
                    "properties": {"Fy": {"value": 250.0, "unit": "MPa"}}})
        assert audit_unit_suffixes(tmp_path) == []

    def test_the_message_hands_the_author_the_spelling_list(self, tmp_path):
        """The refusal has to be actionable on its own: whoever hits it needs
        the spellings in front of them, not a pointer to this file."""
        _catalogue(tmp_path, "lib/_config/_sections/s.epyson", {"x": {"length": 51.0}})
        message = audit_unit_suffixes(tmp_path)[0]
        assert "_MPa" in message and "_mm" in message and "_kg_m" in message
        assert "the author's to get right" in message


class TestItLeavesPresentationAlone:
    @pytest.mark.parametrize("rel", [
        "epy_slides/_assets/themes/dark.epyson",
        "epy_docs/_config/layouts/report.epyson",
        "epy_reports/_config/_layouts/cover.epyson",
        "epy_compose/_styles/base.epyson",
        "epy_studio/viewer/panes.epyson",
    ])
    def test_a_font_weight_is_not_a_kilogram(self, tmp_path, rel):
        """The first draft of the census looked for ``/layouts/`` and missed
        ``/_layouts/``; it would have renamed font weights in two repos. The
        underscore variants are pinned here so that gap cannot reopen."""
        _catalogue(tmp_path, rel, {"title": {"weight": 700, "spacing": 1.4, "width": 12}})
        assert audit_unit_suffixes(tmp_path) == []

    def test_a_unit_conversion_table_keys_by_unit_name(self, tmp_path):
        """epy_units publishes ``"span": 0.2286`` because a span IS 9 inches.
        There the key is the unit, so it has nothing to declare."""
        _catalogue(tmp_path, "epy_units/_config/units/length.epyson", {"span": 0.2286})
        assert audit_unit_suffixes(tmp_path) == []

    def test_a_journal_volume_is_not_a_cubic_metre(self, tmp_path):
        """epy_compose cites Structures vol. 89. Widening the PATH list to
        silence that would have hidden any real catalogue living beside it, so
        the exclusion is made by SIBLING KEYS instead."""
        _catalogue(tmp_path, "epy_compose/_config/_refs/papers.epyson",
                   {"ref1": {"journal": "Structures", "volume": 89, "pages": "1-12"}})
        assert audit_unit_suffixes(tmp_path) == []

    def test_a_real_volume_beside_no_journal_is_still_caught(self, tmp_path):
        """The complement of the test above: the sibling rule must not become a
        blanket pass for the word ``volume``."""
        _catalogue(tmp_path, "epy_tanks/_config/_vessels/tank.epyson",
                   {"tank_a": {"volume": 45.0}})
        assert audit_unit_suffixes(tmp_path) != []

    def test_the_bibliographic_pass_does_not_leak_into_nested_catalogues(self, tmp_path):
        """A bare magnitude nested UNDER a citation is still a bare magnitude."""
        _catalogue(tmp_path, "lib/_config/_sections/s.epyson",
                   {"entry": {"journal": "X", "pages": "1", "section": {"depth": 0.4}}})
        assert audit_unit_suffixes(tmp_path) != []


class TestTheReportSaysWhatToDo:
    def test_a_clean_suite_says_so_explicitly(self, tmp_path, capsys):
        report_unit_suffixes([])
        out = capsys.readouterr().out
        assert "UNIT SUFFIXES" in out
        assert "OK" in out

    def test_a_violation_is_printed_with_its_file(self, tmp_path, capsys):
        _catalogue(tmp_path, "lib/_config/_sections/s.epyson", {"x": {"length": 51.0}})
        report_unit_suffixes(audit_unit_suffixes(tmp_path))
        out = capsys.readouterr().out
        assert "BARE MAGNITUDES (1 file(s))" in out
        assert "s.epyson" in out

    def test_the_message_names_the_directive_not_just_the_key(self, tmp_path):
        """Whoever hits this months from now reads the message, not this file."""
        _catalogue(tmp_path, "lib/_config/_sections/s.epyson", {"x": {"length": 51.0}})
        message = audit_unit_suffixes(tmp_path)[0]
        assert "names its unit" in message
        assert "2026-09-23" in message


class TestItSurvivesABadCatalogue:
    def test_malformed_json_is_another_rule_s_business(self, tmp_path):
        """The epyson-canon rule already reports unparseable files. Reporting it
        twice, from a rule about units, sends the reader to the wrong fix."""
        path = tmp_path / "src" / "lib" / "_config" / "broken.epyson"
        path.parent.mkdir(parents=True)
        path.write_text("{not json", encoding="utf-8")
        assert audit_unit_suffixes(tmp_path) == []

    def test_one_bad_file_does_not_hide_the_next(self, tmp_path):
        bad = tmp_path / "src" / "lib" / "_config" / "aaa_broken.epyson"
        bad.parent.mkdir(parents=True)
        bad.write_text("{not json", encoding="utf-8")
        _catalogue(tmp_path, "lib/_config/zzz_real.epyson", {"x": {"length": 51.0}})
        assert len(audit_unit_suffixes(tmp_path)) == 1
