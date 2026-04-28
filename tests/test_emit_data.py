"""Tests for slmkiii.mozaic.emit_data — MappingSpec → data .moz emitter.

Verifies the emitted data .moz when fed through the Python interpreter
(loading both runtime + data) populates the runtime's tables to match
what the same spec produces via slmkiii.controller.runtime."""

from __future__ import annotations

import unittest
from pathlib import Path

from slmkiii.mozaic import MozaicInterp
from slmkiii.mozaic.emit_data import emit_data_moz
from slmkiii.spec.loader import load_spec


_RUNTIME_SRC = (Path(__file__).resolve().parents[1]
                / "slmkiii" / "mozaic" / "runtime" / "slmk_runtime.moz"
                ).read_text()


def _load_runtime_with_data(spec_path: Path) -> MozaicInterp:
    """Build runtime, then run data .moz which uploads spec into runtime."""
    rt = MozaicInterp()
    rt.load(_RUNTIME_SRC)

    spec = load_spec(spec_path)
    data_src = emit_data_moz(spec)

    # Run data .moz under a separate interpreter; its @OnLoad emits SysEx.
    # Cross-instance: whatever data emits gets fed into runtime.
    data = MozaicInterp()
    data.load(data_src)
    for sx in data.sysex_out:
        rt.send_sysex(sx.bytes_data)
    return rt


class TestEmitDataAnimoog(unittest.TestCase):
    def setUp(self):
        path = (Path(__file__).resolve().parents[1]
                / "slmkiii" / "data" / "specs" / "animoog.yaml")
        self.rt = _load_runtime_with_data(path)

    def test_runtime_has_pages(self):
        n_pages = self.rt.vars.get("n_pages", [0])[0]
        self.assertGreaterEqual(n_pages, 1)

    def test_knob_emits_correct_cc(self):
        """Animoog page 0 knob 0 = orb_x_k on CC 20 ch3."""
        # First page is auto-active
        self.rt.midi_out.clear()
        self.rt.send_cc(channel=15, cc=0x15, val=1)   # knob 1 +1
        ccs = [m for m in self.rt.midi_out if 0xB0 <= m.status <= 0xBF]
        self.assertEqual(len(ccs), 1)
        # CC number should be 20 (from animoog.yaml first knob)
        self.assertEqual(ccs[0].data1, 20)
        # Channel byte: 0xB2 = CC ch3 (status = 0xB0 | (3-1) = 0xB2)
        self.assertEqual(ccs[0].status, 0xB2)


class TestEmitDataBattalion(unittest.TestCase):
    def setUp(self):
        path = (Path(__file__).resolve().parents[1]
                / "slmkiii" / "data" / "specs" / "battalion.yaml")
        self.rt = _load_runtime_with_data(path)

    def test_runtime_has_two_pages(self):
        n_pages = self.rt.vars.get("n_pages", [0])[0]
        self.assertEqual(n_pages, 2)

    def test_focus_count_for_drum_page_is_eight(self):
        # bat_drum (idx 1) has focus_set of 8
        focus_count = self.rt.vars.get("focus_count", [0]*8)
        self.assertEqual(focus_count[1], 8)

    def test_drum1_cutoff_via_knob(self):
        """Page bat_drum focus 0 (drum1) knob 0 = drum1cutoff CC 28 ch1."""
        # Switch to page 1 (bat_drum)
        self.rt.send_cc(channel=15, cc=0x34, val=127)   # SOFT_BUTTON_2 = page 1
        # active_page should be 1, active_focus = 0 (drum1)
        active_page = self.rt.vars.get("active_page", [0])[0]
        self.assertEqual(active_page, 1)
        # Drive knob 1 +1
        self.rt.midi_out.clear()
        self.rt.send_cc(channel=15, cc=0x15, val=1)
        ccs = [m for m in self.rt.midi_out if 0xB0 <= m.status <= 0xBF]
        self.assertEqual(len(ccs), 1)
        self.assertEqual(ccs[0].data1, 28)   # drum1cutoff
        self.assertEqual(ccs[0].status, 0xB0)   # ch1

    def test_focus_switch_changes_drum(self):
        # Switch to bat_drum, then set focus to drum 3 (idx 2)
        self.rt.send_cc(channel=15, cc=0x34, val=127)   # page 1
        # Press 2nd-row button 3 (CC 0x3D = SOFT_BUTTON_11)
        self.rt.send_cc(channel=15, cc=0x3D, val=127)
        self.assertEqual(self.rt.vars.get("active_focus", [0])[0], 2)
        self.rt.midi_out.clear()
        self.rt.send_cc(channel=15, cc=0x15, val=1)   # knob 1 +1
        ccs = [m for m in self.rt.midi_out if 0xB0 <= m.status <= 0xBF]
        # drum3cutoff is at CC base+0 = 44 (28 + 2*8)
        self.assertEqual(ccs[0].data1, 44)


class TestEmitDataDeterminism(unittest.TestCase):
    def test_emit_is_deterministic(self):
        path = (Path(__file__).resolve().parents[1]
                / "slmkiii" / "data" / "specs" / "battalion.yaml")
        spec = load_spec(path)
        a = emit_data_moz(spec)
        b = emit_data_moz(spec)
        self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main()
