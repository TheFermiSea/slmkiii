"""Tests for slmkiii.spec — pydantic v2 mapping spec models."""

from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

from slmkiii.spec import (
    MappingSpecModel,
    SpecError,
    load_spec,
    load_spec_dict,
)


SAMPLE = Path(__file__).parent / "data" / "sample_spec.yaml"


def _minimal_dict() -> dict:
    """Smallest valid spec, used as a base for negative tests."""
    return {
        "spec_version": 1,
        "name": "demo",
        "label": "Demo",
        "project_id": "demo",
        "plugin": {"name": "Demo Plug"},
        "modes": {
            "main": {
                "knobs": [
                    {"label": "K1", "cc": 20, "param_path": "p.a"},
                ],
                "faders": [],
            },
        },
        "pages": [
            {
                "name": "p1",
                "label": "P1",
                "color": "RED",
                "mode": "main",
            },
        ],
    }


class TestSampleLoad(unittest.TestCase):
    def test_sample_loads(self):
        spec = load_spec(SAMPLE)
        self.assertIsInstance(spec, MappingSpecModel)
        self.assertEqual(spec.name, "battalion_demo")
        self.assertEqual(len(spec.pages), 2)
        # Inline view on page 2
        page2 = spec.pages[1]
        self.assertIsNotNone(page2.view)
        # Focus set with parametric vars
        self.assertEqual(len(page2.focus_set), 2)
        self.assertEqual(page2.focus_set[0].vars["base"], 28)


class TestErrorReporting(unittest.TestCase):
    def test_malformed_yaml(self):
        with tempfile.NamedTemporaryFile(
            "w", suffix=".yaml", delete=False
        ) as f:
            f.write("this: is: not: valid: yaml: [unclosed\n")
            path = f.name
        try:
            with self.assertRaises(SpecError) as ctx:
                load_spec(path)
            self.assertIn(path, str(ctx.exception))
        finally:
            Path(path).unlink()

    def test_empty_file(self):
        with tempfile.NamedTemporaryFile(
            "w", suffix=".yaml", delete=False
        ) as f:
            path = f.name
        try:
            with self.assertRaises(SpecError):
                load_spec(path)
        finally:
            Path(path).unlink()

    def test_missing_file_raises(self):
        with self.assertRaises(FileNotFoundError):
            load_spec("/nonexistent/path/to/spec.yaml")


class TestValidation(unittest.TestCase):
    def test_cc_overrange(self):
        d = _minimal_dict()
        d["modes"]["main"]["knobs"][0]["cc"] = 200
        with self.assertRaises(SpecError) as ctx:
            load_spec_dict(d)
        msg = str(ctx.exception)
        # pydantic uses "less than or equal to 127" or our custom "0..127"
        self.assertTrue(
            "127" in msg or "out of range" in msg,
            f"expected range error, got: {msg}",
        )

    def test_cc_negative(self):
        d = _minimal_dict()
        d["modes"]["main"]["knobs"][0]["cc"] = -5
        with self.assertRaises(SpecError):
            load_spec_dict(d)

    def test_min_greater_than_max(self):
        d = _minimal_dict()
        d["modes"]["main"]["knobs"][0]["min"] = 100
        d["modes"]["main"]["knobs"][0]["max"] = 50
        with self.assertRaises(SpecError) as ctx:
            load_spec_dict(d)
        self.assertIn("min", str(ctx.exception).lower())

    def test_undefined_mode_ref(self):
        d = _minimal_dict()
        d["pages"][0]["mode"] = "ghost_mode"
        with self.assertRaises(SpecError) as ctx:
            load_spec_dict(d)
        msg = str(ctx.exception)
        self.assertIn("ghost_mode", msg)

    def test_undefined_view_ref(self):
        d = _minimal_dict()
        d["pages"][0]["view"] = "ghost_view"
        with self.assertRaises(SpecError) as ctx:
            load_spec_dict(d)
        self.assertIn("ghost_view", str(ctx.exception))

    def test_cc_collision_across_pages(self):
        d = _minimal_dict()
        # Add a second mode that re-uses the same (ch, cc) with a *different*
        # param_path; that must trip the collision detector.
        d["modes"]["other"] = {
            "knobs": [
                {
                    "label": "K1",
                    "cc": 20,
                    "channel": 1,
                    "param_path": "p.different",
                },
            ],
            "faders": [],
        }
        d["pages"].append(
            {
                "name": "p2",
                "label": "P2",
                "color": "BLUE",
                "mode": "other",
            }
        )
        with self.assertRaises(SpecError) as ctx:
            load_spec_dict(d)
        self.assertIn("collision", str(ctx.exception).lower())

    def test_widget_unknown_type(self):
        d = _minimal_dict()
        d["views"] = {
            "v": {
                "pads": {
                    "type": "NotARealWidget",
                    "base_note": 36,
                },
            },
        }
        d["pages"][0]["view"] = "v"
        with self.assertRaises(SpecError) as ctx:
            load_spec_dict(d)
        msg = str(ctx.exception)
        self.assertTrue(
            "NotARealWidget" in msg or "discriminator" in msg.lower(),
            f"expected discriminator error, got: {msg}",
        )

    def test_label_too_long(self):
        d = _minimal_dict()
        d["modes"]["main"]["knobs"][0]["label"] = "0123456789"  # 10 chars
        with self.assertRaises(SpecError) as ctx:
            load_spec_dict(d)
        msg = str(ctx.exception)
        # pydantic emits "String should have at most 9 characters"
        self.assertTrue(
            "9" in msg and ("at most" in msg or "max" in msg.lower()),
            f"expected length error, got: {msg}",
        )

    def test_label_exactly_9_chars_ok(self):
        d = _minimal_dict()
        d["modes"]["main"]["knobs"][0]["label"] = "012345678"  # 9 chars
        spec = load_spec_dict(d)
        self.assertEqual(spec.modes["main"].knobs[0].label, "012345678")

    def test_extra_fields_forbidden(self):
        d = _minimal_dict()
        d["modes"]["main"]["knobs"][0]["typo_field"] = "oops"
        with self.assertRaises(SpecError):
            load_spec_dict(d)

    def test_invalid_page_name_pattern(self):
        d = _minimal_dict()
        d["pages"][0]["name"] = "BadName"  # uppercase not allowed
        with self.assertRaises(SpecError):
            load_spec_dict(d)

    def test_unknown_color_rejected(self):
        d = _minimal_dict()
        d["pages"][0]["color"] = "MAUVE"
        with self.assertRaises(SpecError):
            load_spec_dict(d)

    def test_parametric_cc_skips_collision_check(self):
        d = _minimal_dict()
        d["modes"]["main"]["knobs"][0]["cc"] = "$base+0"
        # Parametric CC + parametric CC: must not collide.
        d["modes"]["other"] = {
            "knobs": [
                {
                    "label": "K2",
                    "cc": "$base+0",
                    "param_path": "p.b",
                },
            ],
        }
        d["pages"].append(
            {
                "name": "p2",
                "label": "P2",
                "color": "BLUE",
                "mode": "other",
            }
        )
        spec = load_spec_dict(d)
        self.assertEqual(len(spec.pages), 2)


class TestEchoSub(unittest.TestCase):
    def test_echo_requires_exactly_one_of_cc_or_range(self):
        d = _minimal_dict()
        d["plugin_echo"] = [{"channel": 1}]
        with self.assertRaises(SpecError):
            load_spec_dict(d)

        d["plugin_echo"] = [{"channel": 1, "cc": 20, "cc_range": [20, 30]}]
        with self.assertRaises(SpecError):
            load_spec_dict(d)

    def test_echo_cc_form(self):
        d = _minimal_dict()
        d["plugin_echo"] = [{"channel": 1, "cc": 20}]
        spec = load_spec_dict(d)
        self.assertEqual(spec.plugin_echo[0].cc, 20)

    def test_echo_cc_range_form(self):
        d = _minimal_dict()
        d["plugin_echo"] = [{"channel": 1, "cc_range": [20, 30]}]
        spec = load_spec_dict(d)
        self.assertEqual(spec.plugin_echo[0].cc_range, (20, 30))


class TestRoundTrip(unittest.TestCase):
    def test_yaml_roundtrip(self):
        spec1 = load_spec(SAMPLE)
        # model_dump -> yaml -> reload
        dumped = spec1.model_dump(mode="python")
        text = yaml.safe_dump(dumped, sort_keys=False)
        reparsed = yaml.safe_load(text)
        spec2 = load_spec_dict(reparsed)
        self.assertEqual(
            spec1.model_dump(mode="json"),
            spec2.model_dump(mode="json"),
        )


class TestSchemaCli(unittest.TestCase):
    def test_emit_schema_returns_valid_json(self):
        # Capture stdout via subprocess so we exercise the actual entry point.
        # Use module invocation to avoid console-script PATH dependence.
        result = subprocess.run(
            [sys.executable, "-m", "slmkiii.spec.cli", "emit-schema"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        schema = json.loads(result.stdout)
        self.assertEqual(schema.get("title"), "MappingSpecModel")
        # Sanity: schema has properties for top-level fields.
        self.assertIn("properties", schema)
        self.assertIn("pages", schema["properties"])

    def test_validate_cli_ok(self):
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "slmkiii.spec.cli",
                "validate",
                str(SAMPLE),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("OK", result.stdout)

    def test_validate_cli_failure(self):
        bad = copy.deepcopy(_minimal_dict())
        bad["pages"][0]["mode"] = "ghost"
        with tempfile.NamedTemporaryFile(
            "w", suffix=".yaml", delete=False
        ) as f:
            yaml.safe_dump(bad, f)
            path = f.name
        try:
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "slmkiii.spec.cli",
                    "validate",
                    path,
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 1)
            self.assertIn("ghost", result.stderr)
        finally:
            Path(path).unlink()


if __name__ == "__main__":
    unittest.main()
