"""Tests for slmkiii/mozaic/runtime/slmk_runtime.moz — the hand-written
Mozaic runtime, exercised via the Python interpreter."""

from __future__ import annotations

import unittest
from pathlib import Path

from slmkiii.mozaic import MozaicInterp
from slmkiii.mozaic.protocol import (
    BeginUpload,
    Commit,
    DefineBinding,
    DefinePadBinding,
    DefinePage,
    MsgType,
    encode_inner,
)


_RUNTIME_SRC = (Path(__file__).resolve().parents[1]
                / "slmkiii" / "mozaic" / "runtime" / "slmk_runtime.moz"
                ).read_text()


def _runtime():
    rt = MozaicInterp()
    rt.load(_RUNTIME_SRC)
    return rt


def _push(rt, msg):
    rt.send_sysex(encode_inner(msg))


class TestParseAndLoad(unittest.TestCase):
    def test_runtime_parses(self):
        rt = _runtime()
        # All key handlers present
        for h in ("OnLoad", "OnMidiCC", "OnMidiNote", "OnSysex",
                  "HandleKnobDelta", "HandleFader", "HandleSoftButton",
                  "RenderActivePage"):
            self.assertIn(h, rt.handlers, f"missing handler {h}")

    def test_initial_state_is_empty(self):
        rt = _runtime()
        # No bindings before BEGIN_UPLOAD/COMMIT
        # Drive a knob and assert no MIDI out (knob_ch[idx] = 0 -> Exit)
        rt.midi_out.clear()
        rt.send_cc(channel=15, cc=0x15, val=1)
        self.assertEqual(len(rt.midi_out), 0)


class TestUploadFlow(unittest.TestCase):
    def setUp(self):
        self.rt = _runtime()

    def test_full_upload_commit_cycle(self):
        _push(self.rt, BeginUpload().encode())
        _push(self.rt, DefinePage(page_idx=0, color=5, name="Test").encode())
        _push(self.rt, DefineBinding(page_idx=0, focus_idx=0, slot=0,
                                     channel=1, cc=42, label="Cutoff").encode_as(
            MsgType.DEFINE_KNOB_BINDING))
        # Commit triggers RenderActivePage which emits page/focus/pad LEDs
        # plus the layout SysEx
        before_count = len(self.rt.sysex_out) + len(self.rt.midi_out)
        _push(self.rt, Commit().encode())
        after_count = len(self.rt.sysex_out) + len(self.rt.midi_out)
        self.assertGreater(after_count, before_count)

    def test_define_pad_binding(self):
        _push(self.rt, BeginUpload().encode())
        _push(self.rt, DefinePage(page_idx=0, color=5, name="Test").encode())
        _push(self.rt, DefinePadBinding(page_idx=0, focus_idx=0, slot=3,
                                        channel=10, note=39, color=37).encode())
        _push(self.rt, Commit().encode())

        # Tap pad index 3 (note 0x60+3 = 0x63)
        self.rt.midi_out.clear()
        self.rt.send_note_on(channel=15, note=0x63, vel=80)
        # Should emit ch10 note 39 vel 80 + LED highlight
        cc_or_note = [m for m in self.rt.midi_out
                      if 0x80 <= m.status <= 0x9F]
        self.assertTrue(any(m.data1 == 39 and m.data2 == 80 for m in cc_or_note),
                        f"expected note 39 vel 80, got {[(m.status, m.data1, m.data2) for m in cc_or_note]}")


class TestKnobDelta(unittest.TestCase):
    def setUp(self):
        self.rt = _runtime()
        _push(self.rt, BeginUpload().encode())
        _push(self.rt, DefinePage(page_idx=0, color=5, name="X").encode())
        _push(self.rt, DefineBinding(page_idx=0, focus_idx=0, slot=0,
                                     channel=1, cc=42, label="K1").encode_as(
            MsgType.DEFINE_KNOB_BINDING))
        _push(self.rt, Commit().encode())

    def test_positive_delta_emits_cc(self):
        self.rt.midi_out.clear()
        self.rt.send_cc(channel=15, cc=0x15, val=1)   # delta +1
        ccs = [m for m in self.rt.midi_out if 0xB0 <= m.status <= 0xBF]
        self.assertEqual(len(ccs), 1)
        self.assertEqual(ccs[0].data1, 42)
        self.assertEqual(ccs[0].data2, 65)   # 64 + 1

    def test_negative_delta_decreases(self):
        self.rt.midi_out.clear()
        self.rt.send_cc(channel=15, cc=0x15, val=127)  # delta -1
        ccs = [m for m in self.rt.midi_out if 0xB0 <= m.status <= 0xBF]
        self.assertEqual(len(ccs), 1)
        self.assertEqual(ccs[0].data2, 63)   # 64 - 1

    def test_clamp_at_127(self):
        # Drive +1 delta many times; should clamp at 127
        for _ in range(80):
            self.rt.send_cc(channel=15, cc=0x15, val=1)
        self.rt.midi_out.clear()
        self.rt.send_cc(channel=15, cc=0x15, val=1)
        # Already at 127; another +1 should produce no CC
        ccs = [m for m in self.rt.midi_out if 0xB0 <= m.status <= 0xBF]
        self.assertEqual(len(ccs), 0)


class TestPageNavigation(unittest.TestCase):
    def setUp(self):
        self.rt = _runtime()
        _push(self.rt, BeginUpload().encode())
        # 3 pages, each with one knob on different CCs
        for p in range(3):
            _push(self.rt, DefinePage(page_idx=p, color=5, name=f"P{p+1}").encode())
            _push(self.rt, DefineBinding(page_idx=p, focus_idx=0, slot=0,
                                         channel=1, cc=20+p, label=f"K{p+1}").encode_as(
                MsgType.DEFINE_KNOB_BINDING))
        _push(self.rt, Commit().encode())

    def test_page_select_via_top_row_button(self):
        # Page 0 active by default; knob 1 should go to CC 20
        self.rt.midi_out.clear()
        self.rt.send_cc(channel=15, cc=0x15, val=1)
        self.assertEqual(self.rt.midi_out[0].data1, 20)

        # Press SOFT_BUTTON_3 (CC 0x35) -> page 2
        self.rt.send_cc(channel=15, cc=0x35, val=127)

        # Same knob should now go to CC 22
        self.rt.midi_out.clear()
        self.rt.send_cc(channel=15, cc=0x15, val=1)
        self.assertEqual(self.rt.midi_out[0].data1, 22)


class TestVersionQuery(unittest.TestCase):
    def test_version_query_emits_reply(self):
        rt = _runtime()
        rt.sysex_out.clear()
        # Send VERSION_QUERY
        from slmkiii.mozaic.protocol import HEADER, MsgType
        rt.send_sysex(HEADER + bytes([int(MsgType.VERSION_QUERY)]))
        # Should get a VERSION_REPLY back
        replies = [s for s in rt.sysex_out if HEADER in s.bytes_data]
        self.assertEqual(len(replies), 1)
        body = replies[0].bytes_data
        # body shape: F0 7D 53 4C 4D 4B 02 <maj> <min> <patch> F7
        self.assertEqual(body[6], int(MsgType.VERSION_REPLY))


if __name__ == "__main__":
    unittest.main()
