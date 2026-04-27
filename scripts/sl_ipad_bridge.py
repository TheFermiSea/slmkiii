"""Dev-only bridge: SL MkIII InControl <-> iPad (iDAM).

Mimics a direct SL-to-iPad USB connection while the SL is plugged into the
Mac for development. Two forwarders run in lockstep:

  SL MkIII InControl IN  ->  iPad OUT        (SL -> AUM)
  iPad IN                ->  SL MkIII InControl OUT   (AUM -> SL feedback)

Logs every message so we can see exactly what crossed the bridge.

Usage:
    uv run python scripts/sl_ipad_bridge.py [duration_sec]
"""

from __future__ import annotations

import sys
import time

import mido


SL_IN = "Novation SL MkIII SL MkIII InControl"
SL_OUT = "Novation SL MkIII SL MkIII InControl"
IPAD_IN = "iPad"
IPAD_OUT = "iPad"


def fmt(msg: mido.Message) -> str:
    if msg.type == "control_change":
        return f"CC ch{msg.channel + 1:>2} cc={msg.control:>3} val={msg.value:>3}"
    if msg.type == "note_on":
        return f"NoteOn ch{msg.channel + 1:>2} note={msg.note:>3} vel={msg.velocity:>3}"
    if msg.type == "note_off":
        return f"NoteOff ch{msg.channel + 1:>2} note={msg.note:>3} vel={msg.velocity:>3}"
    if msg.type == "sysex":
        body = " ".join(f"{b:02X}" for b in msg.data[:24])
        more = "..." if len(msg.data) > 24 else ""
        return f"SysEx [{len(msg.data)}B] {body}{more}"
    return msg.type


def main() -> None:
    duration = float(sys.argv[1]) if len(sys.argv) > 1 else 60.0

    sl_in = mido.open_input(SL_IN)
    sl_out = mido.open_output(SL_OUT)
    ipad_in = mido.open_input(IPAD_IN)
    ipad_out = mido.open_output(IPAD_OUT)

    print(f"Bridge running for {duration:.0f}s.")
    print("  SL InControl  -> iPad")
    print("  iPad          -> SL InControl")
    print("\n  T+sec  DIRECTION                    MESSAGE")
    print("  -----  --------------------------    -----------------------------")

    t0 = time.monotonic()
    end = t0 + duration

    while time.monotonic() < end:
        for msg in sl_in.iter_pending():
            ipad_out.send(msg)
            dt = time.monotonic() - t0
            print(f"  {dt:5.2f}  SL --> iPad                   {fmt(msg)}", flush=True)
        for msg in ipad_in.iter_pending():
            sl_out.send(msg)
            dt = time.monotonic() - t0
            print(f"  {dt:5.2f}  iPad --> SL                   {fmt(msg)}", flush=True)
        time.sleep(0.001)

    sl_in.close()
    sl_out.close()
    ipad_in.close()
    ipad_out.close()
    print("\nBridge stopped.")


if __name__ == "__main__":
    main()
