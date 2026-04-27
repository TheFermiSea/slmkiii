"""Two-port MIDI sniffer: SL MkIII InControl + iPad (iDAM).

Run while wiggling controls on the SL MkIII and observing AUM's MIDI Activity
indicators. Confirms ground truth for both:
  - What the SL MkIII actually emits on its InControl USB port
  - What is bidirectionally flowing on the iDAM (iPad) port

Usage:
    uv run python scripts/sniff_both.py [duration_sec]
"""

from __future__ import annotations

import sys
import time
from dataclasses import dataclass

import mido


SL_INCONTROL_IN = "Novation SL MkIII SL MkIII InControl"
IPAD_PORT = "iPad"


@dataclass
class Tagged:
    src: str
    msg: mido.Message
    t: float


def fmt(msg: mido.Message) -> str:
    if msg.type == "control_change":
        return f"CC ch{msg.channel + 1:>2} cc={msg.control:>3} val={msg.value:>3}"
    if msg.type == "note_on":
        return f"NoteOn ch{msg.channel + 1:>2} note={msg.note:>3} vel={msg.velocity:>3}"
    if msg.type == "note_off":
        return f"NoteOff ch{msg.channel + 1:>2} note={msg.note:>3} vel={msg.velocity:>3}"
    if msg.type == "sysex":
        body = " ".join(f"{b:02X}" for b in msg.data)
        return f"SysEx [{len(msg.data)}B] {body}"
    if msg.type == "pitchwheel":
        return f"PitchBend ch{msg.channel + 1:>2} val={msg.pitch}"
    return msg.type + " " + str(msg)


def main() -> None:
    duration = float(sys.argv[1]) if len(sys.argv) > 1 else 30.0

    print(f"Opening {SL_INCONTROL_IN!r} ...")
    sl_in = mido.open_input(SL_INCONTROL_IN)
    print(f"Opening {IPAD_PORT!r} (iDAM input) ...")
    ipad_in = mido.open_input(IPAD_PORT)

    print(f"\nSniffing for {duration:.0f}s. Wiggle knobs/faders/buttons/pads now.\n")
    print("  T+sec  SOURCE              MESSAGE")
    print("  -----  ------------------  -------------------------------------------")

    t0 = time.monotonic()
    end = t0 + duration

    while time.monotonic() < end:
        for msg in sl_in.iter_pending():
            dt = time.monotonic() - t0
            print(f"  {dt:5.2f}  SL_INCONTROL        {fmt(msg)}")
        for msg in ipad_in.iter_pending():
            dt = time.monotonic() - t0
            print(f"  {dt:5.2f}  iPad (iDAM)         {fmt(msg)}")
        time.sleep(0.001)

    sl_in.close()
    ipad_in.close()
    print("\nDone.")


if __name__ == "__main__":
    main()
