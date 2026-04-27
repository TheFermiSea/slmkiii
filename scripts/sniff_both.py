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

import mido

from _midi_fmt import fmt


SL_INCONTROL_IN = "Novation SL MkIII SL MkIII InControl"
IPAD_PORT = "iPad"


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
