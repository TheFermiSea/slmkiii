"""Tests for slmkiii.mozaic.emit_data — single-instance MappingSpec → .moz emitter.

Verifies that the emitted single-instance .moz, when run under the Python
Mozaic interpreter, produces a runtime with correctly-populated dispatch
tables (no separate data .moz, no @OnSysex upload protocol)."""

from __future__ import annotations

import unittest
from pathlib import Path

from slmkiii.mozaic import MozaicInterp
from slmkiii.mozaic.emit_data import emit_runtime_moz
from slmkiii.spec.loader import load_spec


def _load_runtime(spec_path: Path) -> MozaicInterp:
    """Build runtime by emitting + interpreting the single-instance .moz."""
    spec = load_spec(spec_path)
    src = emit_runtime_moz(spec)
    rt = MozaicInterp()
    rt.load(src)
    return rt


class TestEmitDataAnimoog(unittest.TestCase):
    def setUp(self):
        path = (Path(__file__).resolve().parents[1]
                / "slmkiii" / "data" / "specs" / "animoog.yaml")
        self.rt = _load_runtime(path)

    def test_runtime_has_pages(self):
        n_pages = self.rt.vars.get("n_pages", [0])[0]
        self.assertGreaterEqual(n_pages, 1)

    def test_knob_emits_correct_cc(self):
        """Animoog page 0 knob 0 = orb_x_k on CC 20 ch3."""
        self.rt.midi_out.clear()
        self.rt.send_cc(channel=15, cc=0x15, val=1)   # knob 1 +1
        ccs = [m for m in self.rt.midi_out if 0xB0 <= m.status <= 0xBF]
        self.assertEqual(len(ccs), 1)
        self.assertEqual(ccs[0].data1, 20)
        self.assertEqual(ccs[0].status, 0xB2)         # ch3 = status 0xB0|2


class TestEmitDataBattalion(unittest.TestCase):
    def setUp(self):
        path = (Path(__file__).resolve().parents[1]
                / "slmkiii" / "data" / "specs" / "battalion.yaml")
        self.rt = _load_runtime(path)

    def test_runtime_has_two_pages(self):
        n_pages = self.rt.vars.get("n_pages", [0])[0]
        self.assertEqual(n_pages, 2)

    def test_focus_count_for_drum_page_is_eight(self):
        focus_count = self.rt.vars.get("focus_count", [0]*8)
        self.assertEqual(focus_count[1], 8)

    def test_drum1_cutoff_via_knob(self):
        # Switch to page 1 (bat_drum)
        self.rt.send_cc(channel=15, cc=0x34, val=127)
        self.assertEqual(self.rt.vars.get("active_page", [0])[0], 1)
        self.rt.midi_out.clear()
        self.rt.send_cc(channel=15, cc=0x15, val=1)
        ccs = [m for m in self.rt.midi_out if 0xB0 <= m.status <= 0xBF]
        self.assertEqual(len(ccs), 1)
        self.assertEqual(ccs[0].data1, 28)        # drum1cutoff
        self.assertEqual(ccs[0].status, 0xB0)     # ch1

    def test_focus_switch_changes_drum(self):
        self.rt.send_cc(channel=15, cc=0x34, val=127)     # page 1
        self.rt.send_cc(channel=15, cc=0x3D, val=127)     # focus to drum 3
        self.assertEqual(self.rt.vars.get("active_focus", [0])[0], 2)
        self.rt.midi_out.clear()
        self.rt.send_cc(channel=15, cc=0x15, val=1)
        ccs = [m for m in self.rt.midi_out if 0xB0 <= m.status <= 0xBF]
        self.assertEqual(ccs[0].data1, 44)        # drum3cutoff


class TestEmitDataDeterminism(unittest.TestCase):
    def test_emit_is_deterministic(self):
        path = (Path(__file__).resolve().parents[1]
                / "slmkiii" / "data" / "specs" / "battalion.yaml")
        spec = load_spec(path)
        a = emit_runtime_moz(spec)
        b = emit_runtime_moz(spec)
        self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main()
