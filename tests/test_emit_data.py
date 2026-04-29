"""Tests for slmkiii.mozaic.emit_data — QK-pattern .moz emitter.

Architecture: SL MkIII is in TEMPLATE mode and sends plugin CCs directly.
The Mozaic AUv3:
  - Forwards every CC/Note unchanged.
  - Updates the SL MkIII screens via InControl SysEx.
  - Handles SL InControl ch16 nav buttons (page/focus/track/pads).

These tests run the emitted .moz under our Python Mozaic interpreter and
verify the pass-through + dispatch semantics."""

from __future__ import annotations

import unittest
from pathlib import Path

from slmkiii.mozaic import MozaicInterp
from slmkiii.mozaic.emit_data import emit_runtime_moz
from slmkiii.spec.loader import load_spec


def _load_runtime(spec_path: Path) -> MozaicInterp:
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

    def test_initial_state(self):
        self.assertEqual(self.rt.vars["active_page"][0], 0)
        self.assertEqual(self.rt.vars["active_focus"][0], 0)

    def test_passthrough_orb_x_cc(self):
        """CC20 ch3 (orb_x_k) flows through unchanged + screen updates."""
        self.rt.midi_out.clear()
        self.rt.sysex_out.clear()
        self.rt.send_cc(channel=2, cc=20, val=77)
        ccs = [m for m in self.rt.midi_out if 0xB0 <= m.status <= 0xBF]
        self.assertEqual(len(ccs), 1)
        self.assertEqual(ccs[0].status, 0xB2)
        self.assertEqual(ccs[0].data1, 20)
        self.assertEqual(ccs[0].data2, 77)
        # Plus a SysEx for the screen value update on column 0.
        self.assertEqual(len(self.rt.sysex_out), 1)

    def test_unbound_cc_passes_through_no_screen(self):
        """CC that isn't in the spec passes through but produces no SysEx."""
        self.rt.midi_out.clear()
        self.rt.sysex_out.clear()
        self.rt.send_cc(channel=0, cc=99, val=33)
        ccs = [m for m in self.rt.midi_out if 0xB0 <= m.status <= 0xBF]
        self.assertEqual(len(ccs), 1)
        self.assertEqual(self.rt.sysex_out, [])

    def test_page_switch_via_softbtn(self):
        """Soft button 2 (CC 0x34 ch16, val 127) selects page 1."""
        self.rt.send_cc(channel=15, cc=0x34, val=127)
        self.assertEqual(self.rt.vars["active_page"][0], 1)

    def test_track_right_cycles(self):
        """Animoog has 2 pages; 2x track-right returns to page 0."""
        self.rt.send_cc(channel=15, cc=0x67, val=127)
        self.assertEqual(self.rt.vars["active_page"][0], 1)
        self.rt.send_cc(channel=15, cc=0x67, val=127)
        self.assertEqual(self.rt.vars["active_page"][0], 0)

    def test_voice_page_cc(self):
        """On animoog_voice (page 1), CC28 ch3 = base_freq_k -> col 0 update."""
        self.rt.send_cc(channel=15, cc=0x34, val=127)
        self.rt.midi_out.clear()
        self.rt.sysex_out.clear()
        self.rt.send_cc(channel=2, cc=28, val=42)
        ccs = [m for m in self.rt.midi_out if 0xB0 <= m.status <= 0xBF]
        self.assertEqual(ccs[0].data1, 28)
        self.assertEqual(len(self.rt.sysex_out), 1)


class TestEmitDataBattalion(unittest.TestCase):
    def setUp(self):
        path = (Path(__file__).resolve().parents[1]
                / "slmkiii" / "data" / "specs" / "battalion.yaml")
        self.rt = _load_runtime(path)

    def test_drum_focus_via_2nd_row_button(self):
        """Soft btn 2 selects bat_drum (page 1); 2nd-row btn 3 selects focus 2."""
        self.rt.send_cc(channel=15, cc=0x34, val=127)
        self.rt.send_cc(channel=15, cc=0x3D, val=127)
        self.assertEqual(self.rt.vars["active_page"][0], 1)
        self.assertEqual(self.rt.vars["active_focus"][0], 2)

    def test_focus_changes_dispatch_target(self):
        """On (page 1, focus 2) drum3cutoff (CC44 ch1) updates a screen col."""
        self.rt.send_cc(channel=15, cc=0x34, val=127)  # page 1
        self.rt.send_cc(channel=15, cc=0x3D, val=127)  # focus 2 (drum3)
        self.rt.midi_out.clear()
        self.rt.sysex_out.clear()
        self.rt.send_cc(channel=0, cc=44, val=99)      # drum3cutoff
        ccs = [m for m in self.rt.midi_out if 0xB0 <= m.status <= 0xBF]
        self.assertEqual(len(ccs), 1)
        self.assertEqual(ccs[0].data1, 44)
        self.assertEqual(len(self.rt.sysex_out), 1)

    def test_focus_isolation(self):
        """drum1cutoff CC (CC28 ch1) shouldn't update screen when on focus 2."""
        self.rt.send_cc(channel=15, cc=0x34, val=127)  # page 1
        self.rt.send_cc(channel=15, cc=0x3D, val=127)  # focus 2
        self.rt.midi_out.clear()
        self.rt.sysex_out.clear()
        self.rt.send_cc(channel=0, cc=28, val=50)      # drum1cutoff
        # Pass-through happens regardless
        ccs = [m for m in self.rt.midi_out if 0xB0 <= m.status <= 0xBF]
        self.assertEqual(len(ccs), 1)
        # But no screen-value SysEx because col is owned by another focus.
        self.assertEqual(self.rt.sysex_out, [])

    def test_pad_note_passes_through(self):
        """Pad note-on flows unchanged through @OnMidiNote."""
        self.rt.midi_out.clear()
        self.rt.send_note_on(channel=9, note=36, vel=80)
        notes = [m for m in self.rt.midi_out if 0x80 <= m.status <= 0x9F]
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0].status, 0x99)
        self.assertEqual(notes[0].data1, 36)
        self.assertEqual(notes[0].data2, 80)


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
