"""Evaluator tests for slmkiii.mozaic."""

from __future__ import annotations

import unittest
from pathlib import Path

from slmkiii.mozaic import MozaicInterp, parse
from slmkiii.mozaic.errors import MozaicError
from slmkiii.mozaic.snapshot import MidiEvent, SysexEvent, Trace

QK_UTILS = Path(str(Path(__file__).resolve().parents[1].parent / 'quantumkomposer' / 'qk_utils'))
_QK_AVAILABLE = QK_UTILS.is_dir()


def _run(src: str, handler: str = "OnLoad", **magic) -> MozaicInterp:
    interp = MozaicInterp()
    # We bypass auto-fire so the test can inspect state before/after explicitly.
    interp.handlers = parse(src).handlers
    if handler in interp.handlers:
        interp.fire(handler, **magic)
    return interp


class TestVariables(unittest.TestCase):
    def test_assign_read(self) -> None:
        interp = _run("@OnLoad\n  x = 42\n@End\n")
        self.assertEqual(interp._get_scalar("x"), 42)

    def test_unassigned_predicate(self) -> None:
        interp = MozaicInterp()
        interp.load(
            "@OnLoad\n"
            "  if Unassigned foo\n"
            "    a = 1\n"
            "  endif\n"
            "  bar = 99\n"
            "  if Unassigned bar\n"
            "    b = 1\n"
            "  endif\n"
            "@End\n"
        )
        self.assertEqual(interp._get_scalar("a"), 1)
        # bar IS assigned, so the second if-body shouldn't have set b.
        self.assertEqual(interp._get_scalar("b"), 0)

    def test_fill_array(self) -> None:
        interp = _run("@OnLoad\n  FillArray buf, 7, 5\n@End\n")
        self.assertEqual(interp.vars["buf"][:5], [7, 7, 7, 7, 7])

    def test_copy_array(self) -> None:
        src = (
            "@OnLoad\n"
            "  src = [1,2,3,4,5]\n"
            "  CopyArray src, dst, 3\n"
            "@End\n"
        )
        interp = _run(src)
        self.assertEqual(interp.vars["dst"][:3], [1, 2, 3])

    def test_copy_array_slice(self) -> None:
        src = (
            "@OnLoad\n"
            "  src = [10,20,30,40,50]\n"
            "  dst[5] = [0,0,0]\n"
            "  CopyArray src[1], dst[5], 3\n"
            "@End\n"
        )
        interp = _run(src)
        self.assertEqual(interp.vars["dst"][5:8], [20, 30, 40])


class TestIndirectIndexing(unittest.TestCase):
    def test_indirect_lookup(self) -> None:
        src = (
            "@OnLoad\n"
            "  arr = [10,20,30,40]\n"
            "  i = 2\n"
            "  v = arr[i]\n"
            "@End\n"
        )
        interp = _run(src)
        self.assertEqual(interp._get_scalar("v"), 30)

    def test_indirect_store(self) -> None:
        src = (
            "@OnLoad\n"
            "  i = 4\n"
            "  arr[i] = 99\n"
            "@End\n"
        )
        interp = _run(src)
        self.assertEqual(interp._get_cell("arr", 4), 99)


class TestControlFlow(unittest.TestCase):
    def test_if_elseif_else(self) -> None:
        src = (
            "@OnLoad\n"
            "  x = 5\n"
            "  if x = 1\n"
            "    r = 1\n"
            "  elseif x = 5\n"
            "    r = 2\n"
            "  else\n"
            "    r = 3\n"
            "  endif\n"
            "@End\n"
        )
        interp = _run(src)
        self.assertEqual(interp._get_scalar("r"), 2)

    def test_for_forward(self) -> None:
        src = (
            "@OnLoad\n"
            "  s = 0\n"
            "  for i = 1 to 5\n"
            "    s = s + i\n"
            "  endfor\n"
            "@End\n"
        )
        interp = _run(src)
        self.assertEqual(interp._get_scalar("s"), 15)

    def test_for_reverse(self) -> None:
        src = (
            "@OnLoad\n"
            "  s = 0\n"
            "  for i = 5 to 1\n"
            "    s = s + i\n"
            "  endfor\n"
            "@End\n"
        )
        interp = _run(src)
        self.assertEqual(interp._get_scalar("s"), 15)

    def test_while(self) -> None:
        src = (
            "@OnLoad\n"
            "  n = 10\n"
            "  c = 0\n"
            "  while n > 0\n"
            "    n = n - 1\n"
            "    c = c + 1\n"
            "  endwhile\n"
            "@End\n"
        )
        interp = _run(src)
        self.assertEqual(interp._get_scalar("c"), 10)

    def test_repeat_until(self) -> None:
        src = (
            "@OnLoad\n"
            "  c = 0\n"
            "  repeat\n"
            "    c = c + 1\n"
            "  until c >= 4\n"
            "@End\n"
        )
        interp = _run(src)
        self.assertEqual(interp._get_scalar("c"), 4)

    def test_exit_aborts(self) -> None:
        src = (
            "@OnLoad\n"
            "  a = 1\n"
            "  Exit\n"
            "  a = 2\n"
            "@End\n"
        )
        interp = _run(src)
        self.assertEqual(interp._get_scalar("a"), 1)


class TestArithmetic(unittest.TestCase):
    def test_division_by_zero(self) -> None:
        src = "@OnLoad\n  r = 5 / 0\n@End\n"
        interp = _run(src)
        self.assertEqual(interp._get_scalar("r"), 0)

    def test_modulus(self) -> None:
        src = "@OnLoad\n  r = 17 % 5\n@End\n"
        interp = _run(src)
        self.assertEqual(interp._get_scalar("r"), 2)

    def test_24bit_signed_wrap_on_assign(self) -> None:
        src = "@OnLoad\n  r = 0x7FFFFF + 1\n@End\n"  # +1 past max -> wraps to min
        interp = _run(src)
        self.assertEqual(interp._get_scalar("r"), -0x800000)

    def test_bitwise(self) -> None:
        src = "@OnLoad\n  r = (0xF0 & 0x0F) | (0xAA ^ 0x55)\n@End\n"
        interp = _run(src)
        # 0 | 0xFF == 0xFF
        self.assertEqual(interp._get_scalar("r"), 0xFF)


class TestBuiltins(unittest.TestCase):
    def test_send_sysex_captured(self) -> None:
        src = (
            "@OnLoad\n"
            "  buf = [0xF0, 0x01, 0x02, 0xF7]\n"
            "  SendSysex buf, 4\n"
            "@End\n"
        )
        interp = _run(src)
        self.assertEqual(len(interp.sysex_out), 1)
        self.assertEqual(interp.sysex_out[0].bytes_data, b"\xf0\x01\x02\xf7")

    def test_send_midi_cc_with_delay(self) -> None:
        src = "@OnLoad\n  SendMIDICC 0, 7, 64, 25\n@End\n"
        interp = _run(src)
        self.assertEqual(len(interp.midi_out), 1)
        ev = interp.midi_out[0]
        self.assertEqual(ev.status, 0xB0)
        self.assertEqual(ev.data1, 7)
        self.assertEqual(ev.data2, 64)
        # tick was 0 + 25
        self.assertEqual(ev.tick, 25)


class TestRecursionLimit(unittest.TestCase):
    def test_call_depth_limit(self) -> None:
        src = (
            "@OnLoad\n"
            "  Call @Recurse\n"
            "@End\n"
            "@Recurse\n"
            "  Call @Recurse\n"
            "@End\n"
        )
        interp = MozaicInterp()
        interp.handlers = parse(src).handlers
        with self.assertRaises(MozaicError):
            interp.fire("OnLoad")


class TestMagicVars(unittest.TestCase):
    def test_on_midi_cc_magic_vars(self) -> None:
        src = (
            "@OnMidiCC\n"
            "  Log {ch:}, MIDIChannel, { cc:}, MIDIByte2, { v:}, MIDIByte3\n"
            "@End\n"
        )
        interp = MozaicInterp()
        interp.load(src)
        interp.send_cc(7, 0x15, 100)
        self.assertEqual(interp.log, ["ch:7 cc:21 v:100"])

    def test_on_midi_note_on_magic_vars(self) -> None:
        src = (
            "@OnMidiNoteOn\n"
            "  Log {ch:}, MIDIChannel, { n:}, MIDIByte2, { v:}, MIDIByte3\n"
            "@End\n"
        )
        interp = MozaicInterp()
        interp.load(src)
        interp.send_note_on(2, 60, 64)
        self.assertEqual(interp.log, ["ch:2 n:60 v:64"])

    def test_on_sysex_receive_array_idiom(self) -> None:
        # Mozaic 1.x: ReceiveSysex copies payload into a user array; SysexSize
        # is the length. There is no per-byte SysexByteN magic var (reading
        # one crashes the AUv3 instance on script load).
        src = (
            "@OnSysex\n"
            "  ReceiveSysex sx\n"
            "  Log {n:}, SysexSize, { b0:}, sx[0], { b1:}, sx[1]\n"
            "@End\n"
        )
        interp = MozaicInterp()
        interp.load(src)
        interp.send_sysex(b"\xf0\x12\x34\xf7")
        self.assertEqual(interp.log, ["n:2 b0:18 b1:52"])


class TestTimers(unittest.TestCase):
    def test_timer_fires_on_advance(self) -> None:
        src = (
            "@OnLoad\n"
            "  SetTimerInterval 100\n"
            "  StartTimer\n"
            "@End\n"
            "@OnTimer\n"
            "  ticks = ticks + 1\n"
            "@End\n"
        )
        interp = MozaicInterp()
        interp.load(src)
        interp.advance_timer(50)
        self.assertEqual(interp._get_scalar("ticks"), 0)
        interp.advance_timer(60)
        self.assertEqual(interp._get_scalar("ticks"), 1)
        interp.advance_timer(250)
        self.assertEqual(interp._get_scalar("ticks"), 3)

    def test_stop_timer_halts(self) -> None:
        src = (
            "@OnLoad\n"
            "  SetTimerInterval 50\n"
            "  StartTimer\n"
            "@End\n"
            "@OnTimer\n"
            "  ticks = ticks + 1\n"
            "  StopTimer\n"
            "@End\n"
        )
        interp = MozaicInterp()
        interp.load(src)
        interp.advance_timer(500)
        self.assertEqual(interp._get_scalar("ticks"), 1)


class TestSysexReceive(unittest.TestCase):
    def test_receive_sysex_unpacks_payload(self) -> None:
        src = (
            "@OnSysex\n"
            "  ReceiveSysex msg\n"
            "  Log {b0:}, msg[0], { b1:}, msg[1], { b2:}, msg[2]\n"
            "@End\n"
        )
        interp = MozaicInterp()
        interp.load(src)
        interp.send_sysex(b"\xf0\x10\x20\x30\xf7")
        self.assertEqual(interp.log, ["b0:16 b1:32 b2:48"])
        # Array contents should also be populated.
        self.assertEqual(interp.vars["msg"][:3], [0x10, 0x20, 0x30])


class TestTraceSnapshot(unittest.TestCase):
    def test_trace_round_trip(self) -> None:
        src = (
            "@OnLoad\n"
            "  Log {hello}\n"
            "  SendMIDICC 0, 7, 64\n"
            "  buf = [0xF0, 0x12, 0xF7]\n"
            "  SendSysex buf, 3\n"
            "@End\n"
        )
        interp = MozaicInterp()
        interp.load(src)
        trace = Trace.from_interp(interp)
        text = trace.to_json()
        self.assertEqual(text, Trace.from_json(text).to_json())
        d = trace.to_dict()
        self.assertEqual(d["log"], ["hello"])
        self.assertEqual(len(d["midi"]), 1)
        self.assertEqual(d["sysex"][0]["bytes"], [0xF0, 0x12, 0xF7])


@unittest.skipUnless(_QK_AVAILABLE, 'qk_utils sibling repo not present')
class TestMidiSpyRoundtrip(unittest.TestCase):
    def test_note_on_logs_note_on(self) -> None:
        src = (QK_UTILS / "midi_spy.moz").read_text()
        interp = MozaicInterp()
        interp.load(src)
        interp.send_note_on(0, 60, 100)
        joined = "\n".join(interp.log)
        self.assertIn("NOTE ON", joined)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
