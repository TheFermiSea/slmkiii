"""Direct InControl screen smoke test — bypasses Mozaic entirely.

Drives the SL MkIII top-row screens, button LEDs, fader LEDs, and a
center-screen notification straight from the Mac via the SL MkIII InControl
USB port. Proves the InControl SysEx in slmkiii.incontrol is correct.

Usage:
    uv run python scripts/screen_smoke.py
"""

from __future__ import annotations

import time

from slmkiii.incontrol import (
    InControlConnection,
    LAYOUT_KNOB,
    LAYOUT_EMPTY,
    LED,
)


# SL MkIII palette indices (subset of the 128-colour table)
COLORS = [5, 9, 13, 21, 33, 37, 49, 3]  # red, orange, yellow, green, cyan, blue, purple, white
LABELS = ["Cutoff", "Reso", "Attack", "Decay", "Volume", "Pan", "Send", "Mix"]


def main() -> None:
    print("Opening SL MkIII InControl ...")
    with InControlConnection() as conn:
        in_name = conn.input_port_name
        out_name = conn.output_port_name
        print(f"  IN : {in_name}")
        print(f"  OUT: {out_name}")
        if not out_name:
            print("ERROR: no InControl output port found.")
            return

        print("\n[1/5] Setting top-row layout to KNOB ...")
        conn.set_layout(LAYOUT_KNOB)
        time.sleep(0.05)

        print("[2/5] Labeling 8 knob columns with names + values + colors ...")
        for col in range(8):
            conn.set_text(col, 0, LABELS[col])
            conn.set_value(col, 0, min(127, (col + 1) * 16))
            conn.set_color(col, 0, COLORS[col])
            time.sleep(0.02)

        print("[3/5] Lighting 8 button LEDs in matching colors ...")
        for i in range(8):
            conn.set_led(LED.SOFT_BUTTON_1.value + i, COLORS[i])
            time.sleep(0.02)

        print("[4/5] Lighting 8 fader LEDs in matching colors ...")
        for i in range(8):
            conn.set_led(LED.FADER_1.value + i, COLORS[i])
            time.sleep(0.02)

        print("[5/5] Showing center-screen notification ...")
        conn.notify("HELLO FROM MAC", "InControl OK")

        print("\nLook at the SL MkIII NOW. You should see:")
        print("  - 8 top-row screens labeled Cutoff/Reso/Attack/Decay/Volume/Pan/Send/Mix")
        print("  - Each screen with a colored top bar and knob icon at varying positions")
        print("  - 8 soft buttons (top row) lit in matching colors")
        print("  - 8 fader LEDs lit in matching colors")
        print("  - Center screen: 'HELLO FROM MAC / InControl OK'")
        print("\nHolding state for 30 seconds ... Ctrl-C to stop early.")

        try:
            time.sleep(30)
        except KeyboardInterrupt:
            print("Interrupted.")

        print("\nClearing all LEDs and resetting layout ...")
        conn.clear_all_leds()
        conn.set_layout(LAYOUT_EMPTY)


if __name__ == "__main__":
    main()
