"""Tests for spec migration + YAML-to-Pages compilation (c14, c15)."""

from __future__ import annotations

import importlib
import unittest
from pathlib import Path

from slmkiii.aum import generate_midimap_bytes
from slmkiii.spec.compile import _resolve_cc, _subst_str, compile_spec
from slmkiii.spec.loader import load_spec
from slmkiii.spec.migrate import (
    _bindings_to_aum_mappings,
    migrate_module,
    verify_round_trip,
)


_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_BATTALION_YAML = _PROJECT_ROOT / "slmkiii" / "data" / "specs" / "battalion.yaml"
_ANIMOOG_YAML = _PROJECT_ROOT / "slmkiii" / "data" / "specs" / "animoog.yaml"


class TestSubst(unittest.TestCase):
    def test_simple_subst(self):
        self.assertEqual(_subst_str("D$n Cut", {"n": 3}), "D3 Cut")

    def test_longest_prefix_wins(self):
        # `$nparams` should match `$n` (1) + literal "params"
        self.assertEqual(_subst_str("drum$nparams", {"n": 1}), "drum1params")

    def test_unknown_var_left_alone(self):
        self.assertEqual(_subst_str("$bogus", {"n": 1}), "$bogus")

    def test_no_dollar_unchanged(self):
        self.assertEqual(_subst_str("plain text", {"n": 1}), "plain text")


class TestResolveCC(unittest.TestCase):
    def test_int_passthrough(self):
        self.assertEqual(_resolve_cc(42, {}), 42)

    def test_arith_plus(self):
        self.assertEqual(_resolve_cc("$base+1", {"base": 28}), 29)

    def test_arith_minus(self):
        self.assertEqual(_resolve_cc("$base-2", {"base": 28}), 26)

    def test_bare_var(self):
        self.assertEqual(_resolve_cc("$x", {"x": 50}), 50)

    def test_unknown_var_raises(self):
        with self.assertRaises(KeyError):
            _resolve_cc("$missing+1", {})


class TestAnimoogMigration(unittest.TestCase):
    def test_yaml_validates(self):
        spec = load_spec(_ANIMOOG_YAML)
        self.assertEqual(spec.name, "animoog")
        self.assertEqual(len(spec.pages), 2)

    def test_round_trip_byte_equal(self):
        spec_dict = migrate_module("slmkiii.controller.pages.animoog")
        ok, msg = verify_round_trip("slmkiii.controller.pages.animoog", spec_dict)
        self.assertTrue(ok, msg)


class TestBattalionMigration(unittest.TestCase):
    def test_yaml_validates(self):
        spec = load_spec(_BATTALION_YAML)
        self.assertEqual(spec.name, "battalion")
        self.assertEqual(len(spec.pages), 2)
        # bat_drum has parametric mode + focus_set of 8
        bat_drum = next(p for p in spec.pages if p.name == "bat_drum")
        self.assertEqual(len(bat_drum.focus_set), 8)

    def test_compile_keeps_focus_meta_page(self):
        spec = load_spec(_BATTALION_YAML)
        pages = compile_spec(spec)
        # 2 PageModels -> 2 dataclass Pages (bat_global + bat_drum meta with specialize)
        self.assertEqual(len(pages), 2)
        names = [p.name for p in pages]
        self.assertEqual(names, ["bat_global", "bat_drum"])
        bat_drum = pages[1]
        self.assertEqual(len(bat_drum.focus_set), 8)
        self.assertIsNotNone(bat_drum.specialize)

    def test_specialize_resolves_focus_to_correct_bindings(self):
        spec = load_spec(_BATTALION_YAML)
        pages = compile_spec(spec)
        bat_drum = next(p for p in pages if p.name == "bat_drum")
        drum3 = bat_drum.specialize(2)   # focus idx 2 = drum 3
        self.assertEqual(drum3.knobs[0].label, "D3 Cut")
        self.assertEqual(drum3.knobs[0].cc, 44)
        self.assertEqual(drum3.knobs[0].param_path,
                         "drumProtoParams.drum3params.drum3cutoff")

    def test_battalion_round_trip_byte_equal(self):
        # The original Python module produces certain mapping bytes;
        # the YAML, when compiled, must match byte-for-byte
        mod = importlib.import_module("slmkiii.controller.pages.battalion")
        py_pages = list(mod.PAGES) + [
            mod.DRUM_FOCUS_PAGES[k] for k in sorted(mod.DRUM_FOCUS_PAGES.keys())
        ]
        spec = load_spec(_BATTALION_YAML)
        yml_pages = compile_spec(spec)

        py_maps = _bindings_to_aum_mappings(py_pages)
        yml_maps = _bindings_to_aum_mappings(yml_pages)

        py_b = generate_midimap_bytes("verify", py_maps)
        yml_b = generate_midimap_bytes("verify", yml_maps)
        self.assertEqual(py_b, yml_b,
                         f"battalion YAML doesn't round-trip byte-equal "
                         f"(py={len(py_maps)} maps, yml={len(yml_maps)} maps)")


class TestMigrateTool(unittest.TestCase):
    def test_animoog_migrate_produces_dict(self):
        spec_dict = migrate_module("slmkiii.controller.pages.animoog")
        self.assertEqual(spec_dict["name"], "animoog")
        self.assertEqual(spec_dict["spec_version"], 1)
        self.assertGreater(len(spec_dict["pages"]), 0)


if __name__ == "__main__":
    unittest.main()
