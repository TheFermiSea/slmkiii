"""Golden / snapshot tests for production Mozaic scripts.

Each test loads one of the qk_utils Mozaic scripts, replays a fixed
scripted MIDI input sequence against it, and compares the captured
:class:`~slmkiii.mozaic.snapshot.Trace` (serialised to JSON) against a
committed golden file under ``tests/golden/<name>.json``.

To regenerate the goldens after intentional behavioural changes::

    MOZAIC_UPDATE_GOLDEN=1 uv run python -m unittest tests.test_mozaic_golden

The harness only writes goldens when that environment variable is set
(or when the file does not yet exist), and otherwise asserts byte-for-byte
equality.
"""

from __future__ import annotations

import os
import unittest
from pathlib import Path
from typing import Callable

from slmkiii.mozaic import MozaicInterp
from slmkiii.mozaic.snapshot import Trace

QK_UTILS = Path("/Users/briansquires/code/quantumkomposer/qk_utils")
GOLDEN_DIR = Path(__file__).parent / "golden"
UPDATE_GOLDEN = os.environ.get("MOZAIC_UPDATE_GOLDEN", "") not in ("", "0", "false")


# ---- replay sequences -----------------------------------------------------


def _replay_sl2qk(interp: MozaicInterp) -> None:
    """Drive sl2qk: simulate knob 1 increasing, fader 1 sweep, button presses."""
    # Knob 1 (CC 0x15 ch16) — 10 small positive deltas.
    for _ in range(10):
        interp.send_cc(15, 0x15, 1)
    # Fader 3 absolute (CC 0x2B ch16) sweep 0..127 in 16 steps.
    for v in (0, 16, 32, 48, 64, 80, 96, 112, 127):
        interp.send_cc(15, 0x2B, v)
    # Soft button 5 press (CC 0x37 val=127), then release (val=0).
    interp.send_cc(15, 0x37, 127)
    interp.send_cc(15, 0x37, 0)
    # Pads up / down to cycle MGEN.
    interp.send_cc(15, 0x55, 127)
    interp.send_cc(15, 0x56, 127)
    # Pad 0 NoteOn / NoteOff (note 0x60 ch16).
    interp.send_note_on(15, 0x60, 96)
    interp.send_note_off(15, 0x60, 0)


def _replay_qk2sl(interp: MozaicInterp) -> None:
    """Drive qk2sl: knob feedback + channel-select feedback."""
    # KNTRL knob 0 value 64 then 100 (CC 36 ch15).
    interp.send_cc(15, 36, 64)
    interp.send_cc(15, 36, 100)
    # MGEN knob 1 value 50 (CC 41 ch15).
    interp.send_cc(15, 41, 50)
    # Channel select sweep 0..3 (CC 24 ch15).
    for v in (0, 1, 2, 3):
        interp.send_cc(15, 24, v)
    # MGEN device select to 4 (CC 90 ch15).
    interp.send_cc(15, 90, 4)
    # Pad-color feedback: NoteOn ch15 note 5 with QK color 3.
    interp.send_note_on(15, 5, 3)


def _replay_midi_spy(interp: MozaicInterp) -> None:
    """Drive midi_spy: a representative slice of MIDI traffic."""
    interp.send_note_on(0, 60, 100)
    interp.send_note_off(0, 60, 0)
    interp.send_cc(0, 7, 64)
    interp.send_cc(0, 1, 0)
    # Toggle PadDown 2 (turns CC logging off), then send another CC.
    if "OnPadDown" in interp.handlers:
        interp.fire("OnPadDown", LastPad=2)
    interp.send_cc(0, 1, 127)


_SCRIPTS: dict[str, Callable[[MozaicInterp], None]] = {
    "sl2qk": _replay_sl2qk,
    "qk2sl": _replay_qk2sl,
    "midi_spy": _replay_midi_spy,
}


def _run_script(name: str) -> Trace:
    src = (QK_UTILS / f"{name}.moz").read_text()
    interp = MozaicInterp()
    interp.load(src)
    _SCRIPTS[name](interp)
    return Trace.from_interp(interp)


# ---- test driver ----------------------------------------------------------


class GoldenTests(unittest.TestCase):
    """One subTest per script in :data:`_SCRIPTS`."""

    def _check(self, name: str) -> None:
        trace = _run_script(name)
        actual = trace.to_json() + "\n"
        golden = GOLDEN_DIR / f"{name}.json"
        if UPDATE_GOLDEN or not golden.exists():
            golden.parent.mkdir(parents=True, exist_ok=True)
            golden.write_text(actual)
            return
        expected = golden.read_text()
        self.assertEqual(
            expected,
            actual,
            f"Trace for {name} differs from {golden}; "
            f"set MOZAIC_UPDATE_GOLDEN=1 to regenerate.",
        )

    def test_sl2qk(self) -> None:
        self._check("sl2qk")

    def test_qk2sl(self) -> None:
        self._check("qk2sl")

    def test_midi_spy(self) -> None:
        self._check("midi_spy")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
