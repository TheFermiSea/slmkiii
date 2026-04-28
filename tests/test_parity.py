"""Parity harness: Python live runtime ≡ Mozaic runtime+data.

Drives identical scripted MIDI input through:
  - slmkiii.controller.runtime.Controller   (Python live runtime)
  - slmk_runtime.moz + emit_data(spec).moz  (via Mozaic interpreter)

Asserts they produce the same outbound CC/note stream byte-for-byte.
This is the canonical guarantee that the iPad-deployed Mozaic compiler
produces semantically equivalent behavior to the Python reference impl.

Without this, refactors of either side could silently drift.
"""

from __future__ import annotations

import unittest
from dataclasses import dataclass, field
from pathlib import Path

from slmkiii.controller.runtime import Controller
from slmkiii.mozaic import MozaicInterp
from slmkiii.mozaic.emit_data import emit_data_moz
from slmkiii.spec.compile import compile_spec
from slmkiii.spec.loader import load_spec


_RUNTIME_SRC = (Path(__file__).resolve().parents[1]
                / "slmkiii" / "mozaic" / "runtime" / "slmk_runtime.moz"
                ).read_text()
_BATTALION_YAML = (Path(__file__).resolve().parents[1]
                   / "slmkiii" / "data" / "specs" / "battalion.yaml")
_ANIMOOG_YAML = (Path(__file__).resolve().parents[1]
                 / "slmkiii" / "data" / "specs" / "animoog.yaml")


@dataclass
class _FakeConn:
    leds: list = field(default_factory=list)

    def set_led(self, led, color): self.leds.append((led, color))
    def set_layout(self, layout): pass
    def set_text(self, col, field, text): pass
    def set_color(self, col, obj, color): pass
    def set_value(self, col, field, value): pass
    def set_screen_properties(self, col, props): pass
    def notify(self, line1, line2=""): pass
    def poll_input(self): return []
    def clear_all_leds(self): pass


class _CapturingMidoOut:
    def __init__(self): self.sent = []
    def send(self, msg): self.sent.append(msg)
    def close(self): pass


def _build_python_runtime(yaml_path: Path) -> tuple[Controller, _CapturingMidoOut]:
    pages = compile_spec(load_spec(yaml_path))
    out = _CapturingMidoOut()
    return Controller(_FakeConn(), out, pages), out


def _build_mozaic_runtime(yaml_path: Path) -> MozaicInterp:
    rt = MozaicInterp()
    rt.load(_RUNTIME_SRC)
    spec = load_spec(yaml_path)
    data = MozaicInterp()
    data.load(emit_data_moz(spec))
    for sx in data.sysex_out:
        rt.send_sysex(sx.bytes_data)
    return rt


def _python_cc_out(out: _CapturingMidoOut) -> list[tuple[int, int, int]]:
    """Extract (channel_0idx, cc, value) tuples in order."""
    return [(m.channel, m.control, m.value)
            for m in out.sent if m.type == "control_change"]


def _moz_cc_out(rt: MozaicInterp) -> list[tuple[int, int, int]]:
    """Extract (channel_0idx, cc, value) tuples from interpreter output."""
    out = []
    for m in rt.midi_out:
        if 0xB0 <= m.status <= 0xBF:
            out.append((m.status & 0x0F, m.data1, m.data2))
    return out


def _python_note_out(out: _CapturingMidoOut) -> list[tuple[int, int, int]]:
    return [(m.channel, m.note, m.velocity)
            for m in out.sent if m.type in ("note_on", "note_off")]


def _moz_note_out(rt: MozaicInterp) -> list[tuple[int, int, int]]:
    """Note-only events; filter out the LED NoteOn ch16 traffic."""
    out = []
    for m in rt.midi_out:
        if 0x80 <= m.status <= 0x9F:
            channel = m.status & 0x0F
            # SL InControl ch16 LEDs are sent on ch16 — skip those
            if channel == 15:
                continue
            out.append((channel, m.data1, m.data2))
    return out


# ---------------------------------------------------------------------------
class TestKnobParity(unittest.TestCase):
    def test_animoog_knob_delta_parity(self):
        py_c, py_out = _build_python_runtime(_ANIMOOG_YAML)
        moz = _build_mozaic_runtime(_ANIMOOG_YAML)

        # Drive 5 knob deltas of mixed sign
        deltas = [1, 1, 127, 1, 127]   # +1, +1, -1, +1, -1 (raw twos-complement)
        for d in deltas:
            py_c._handle_event({
                "type": "knob",
                "knob": 1,
                "delta": d - 128 if d > 63 else d,
                "value": d,
            })
            moz.send_cc(channel=15, cc=0x15, val=d)

        py_ccs = _python_cc_out(py_out)
        moz_ccs = _moz_cc_out(moz)
        self.assertEqual(py_ccs, moz_ccs,
                         f"knob CC streams diverged:\nPY: {py_ccs}\nMOZ: {moz_ccs}")

    def test_battalion_drum1_knob_parity(self):
        py_c, py_out = _build_python_runtime(_BATTALION_YAML)
        moz = _build_mozaic_runtime(_BATTALION_YAML)

        # Switch to bat_drum (page 1)
        py_c._handle_event({
            "type": "button",
            "control": 0x34,    # SOFT_BUTTON_2
            "value": 127,
            "pressed": True,
        })
        moz.send_cc(channel=15, cc=0x34, val=127)

        # Knob 1 -> drum1cutoff (CC 28 ch1)
        py_out.sent.clear()
        moz.midi_out.clear()
        py_c._handle_event({
            "type": "knob", "knob": 1, "delta": 5, "value": 5,
        })
        moz.send_cc(channel=15, cc=0x15, val=5)

        py_ccs = _python_cc_out(py_out)
        moz_ccs = _moz_cc_out(moz)
        self.assertEqual(py_ccs, moz_ccs,
                         f"battalion knob diverged:\nPY: {py_ccs}\nMOZ: {moz_ccs}")
        self.assertEqual(py_ccs[0][1], 28)   # drum1cutoff CC


class TestFaderParity(unittest.TestCase):
    def test_animoog_fader_parity(self):
        py_c, py_out = _build_python_runtime(_ANIMOOG_YAML)
        moz = _build_mozaic_runtime(_ANIMOOG_YAML)

        for val in (10, 50, 90, 127, 0):
            py_c._handle_event({
                "type": "fader", "fader": 1, "value": val,
            })
            moz.send_cc(channel=15, cc=0x29, val=val)

        py_ccs = _python_cc_out(py_out)
        moz_ccs = _moz_cc_out(moz)
        self.assertEqual(py_ccs, moz_ccs,
                         f"fader CC streams diverged:\nPY: {py_ccs}\nMOZ: {moz_ccs}")


class TestPadParity(unittest.TestCase):
    def test_battalion_pad_parity(self):
        py_c, py_out = _build_python_runtime(_BATTALION_YAML)
        moz = _build_mozaic_runtime(_BATTALION_YAML)

        # Pad 1 (slot 0) press + release on the bat_global page
        py_c._handle_event({
            "type": "pad", "pad": 1, "velocity": 80,
        })
        py_c._handle_event({
            "type": "pad", "pad": 1, "velocity": 0,
        })
        moz.send_note_on(channel=15, note=0x60, vel=80)
        moz.send_note_off(channel=15, note=0x60, vel=0)

        py_notes = _python_note_out(py_out)
        moz_notes = _moz_note_out(moz)
        self.assertEqual(py_notes, moz_notes,
                         f"pad note streams diverged:\nPY: {py_notes}\nMOZ: {moz_notes}")


class TestPageNavParity(unittest.TestCase):
    def test_track_right_cycles_pages_consistently(self):
        py_c, py_out = _build_python_runtime(_BATTALION_YAML)
        moz = _build_mozaic_runtime(_BATTALION_YAML)

        # Press track-right twice — should cycle page 0 -> 1 -> 0
        for _ in range(2):
            py_c._handle_event({
                "type": "button", "control": 0x67,
                "value": 127, "pressed": True,
            })
            moz.send_cc(channel=15, cc=0x67, val=127)

        # Both should be back on page 0
        self.assertEqual(py_c.state.current_page_idx, 0)
        self.assertEqual(moz.vars.get("active_page", [0])[0], 0)


if __name__ == "__main__":
    unittest.main()
