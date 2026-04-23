"""QK-aware InControl surface for SL MkIII screen feedback.

Listens for CC feedback from QuantumKomposer on the iPad (forwarded by the
qk2sl.moz Mozaic script via iDAM) and updates the SL MkIII InControl
screens and LEDs accordingly.

Architecture::

    qk2sl.moz (iPad) → iDAM → Mac MIDI port "iPad" → QKSurface → SL MkIII InControl

Usage::

    python -m controlmap.qk_surface --input iPad

QK feedback CC protocol (received from iPad port):
  - CC 36-39 ch16 (mido ch15), val 0-127: KNTRL knob 1-4 → knob screens 0-3
  - CC 40-43 ch16 (mido ch15), val 0-127: MGEN knob 1-4 → knob screens 4-7
  - CC 24 ch16 (mido ch15), val 0-14: Selected instrument channel
  - CC 109-116 ch14 (mido ch13), val>0: Scene change (CC 109=scene 0, ..., 116=scene 7)
"""
from __future__ import annotations

import signal
import time

import mido

from slmkiii.incontrol import (
    InControlConnection,
    LAYOUT_KNOB,
)

# Rate limit for knob screen updates (~30 Hz)
_SCREEN_UPDATE_INTERVAL = 0.033

# MIDI channel indices (mido 0-indexed)
_CH_QK_MAIN = 15   # MIDI channel 16
_CH_QK_SCENE = 13  # MIDI channel 14

# CC ranges
_CC_KNTRL_FIRST = 36   # CC 36-39 → KNTRL knobs 1-4 → columns 0-3
_CC_KNTRL_LAST = 39
_CC_MGEN_FIRST = 40    # CC 40-43 → MGEN knobs 1-4 → columns 4-7
_CC_MGEN_LAST = 43
_CC_INSTRUMENT_CH = 24
_CC_SCENE_FIRST = 109  # CC 109-116 → scenes 0-7
_CC_SCENE_LAST = 116

# Column labels for knob screens (max 9 chars, SL MkIII display width)
_KNOB_LABELS = [
    'K-Knb1', 'K-Knb2', 'K-Knb3', 'K-Knb4',  # KNTRL knobs → cols 0-3
    'M-Knb1', 'M-Knb2', 'M-Knb3', 'M-Knb4',  # MGEN knobs → cols 4-7
]


class QKSurface:
    """Listens for QK feedback CC messages and updates SL MkIII InControl."""

    def __init__(self, midi_input: str, incontrol_port: str | None = None):
        """
        Args:
            midi_input: MIDI input port name to listen on (e.g. 'iPad').
            incontrol_port: SL MkIII InControl output port name.
                            Auto-detected if None.
        """
        self._midi_input_name = midi_input
        self._incontrol_port = incontrol_port

        # Current knob values (columns 0-7)
        self._knob_values: list[int] = [0] * 8

        # Rate-limit tracking per column
        self._last_screen_update: dict[int, float] = {}

    def _init_screens(self, ic: InControlConnection) -> None:
        """Set up all 8 knob screens on startup."""
        ic.set_layout(LAYOUT_KNOB)
        for col, label in enumerate(_KNOB_LABELS):
            ic.set_text(col, 0, label)
            ic.set_value(col, 0, 0)

    def _update_knob_screen(self, ic: InControlConnection,
                            col: int, value: int) -> None:
        """Update a knob screen, rate-limited to ~30 Hz."""
        now = time.monotonic()
        last = self._last_screen_update.get(col, 0.0)
        if now - last < _SCREEN_UPDATE_INTERVAL:
            return
        self._last_screen_update[col] = now
        ic.set_value(col, 0, value)

    def _handle_message(self, ic: InControlConnection,
                        msg: mido.Message) -> None:
        """Dispatch an incoming MIDI message to the appropriate screen update."""
        if msg.type != 'control_change':
            return

        ch = msg.channel
        cc = msg.control
        val = msg.value

        if ch == _CH_QK_MAIN:
            if _CC_KNTRL_FIRST <= cc <= _CC_KNTRL_LAST:
                col = cc - _CC_KNTRL_FIRST  # 0-3
                self._knob_values[col] = val
                self._update_knob_screen(ic, col, val)

            elif _CC_MGEN_FIRST <= cc <= _CC_MGEN_LAST:
                col = cc - _CC_MGEN_FIRST + 4  # 4-7
                self._knob_values[col] = val
                self._update_knob_screen(ic, col, val)

            elif cc == _CC_INSTRUMENT_CH:
                ic.notify('Channel', f'Ch: {val + 1}')

        elif ch == _CH_QK_SCENE:
            if _CC_SCENE_FIRST <= cc <= _CC_SCENE_LAST and val > 0:
                scene_num = cc - _CC_SCENE_FIRST  # 0-indexed scene number
                ic.notify('Scene', f'Scene: {scene_num + 1}')

    def run(self) -> None:
        """Block until Ctrl-C, updating SL MkIII screens from QK feedback."""
        running = True

        def stop(_sig, _frame) -> None:
            nonlocal running
            running = False

        signal.signal(signal.SIGINT, stop)
        signal.signal(signal.SIGTERM, stop)

        # Validate input port
        available_inputs = mido.get_input_names()
        if self._midi_input_name not in available_inputs:
            print(f'Error: MIDI input port "{self._midi_input_name}" not found.')
            print(f'Available input ports: {available_inputs}')
            return

        print(f'QK Surface starting...')
        print(f'MIDI input:     {self._midi_input_name}')
        print(f'InControl port: {self._incontrol_port or "(auto-detect)"}')
        print('Press Ctrl-C to stop.')

        try:
            with InControlConnection(output_port=self._incontrol_port) as ic:
                print('Connected to SL MkIII InControl.')
                self._init_screens(ic)
                print('Screens initialized. Listening for QK feedback...')

                with mido.open_input(self._midi_input_name) as midi_in:
                    while running:
                        for msg in midi_in.iter_pending():
                            self._handle_message(ic, msg)
                        time.sleep(0.005)

                # Clear screens on exit
                ic.set_layout(LAYOUT_KNOB)
                for col in range(8):
                    ic.set_text(col, 0, '')
                    ic.set_value(col, 0, 0)

        except Exception as exc:  # noqa: BLE001
            print(f'Error: {exc}')
            return

        print('QK Surface stopped.')


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(
        description='QK-aware InControl surface: mirrors QuantumKomposer '
                    'state to SL MkIII screens.',
    )
    parser.add_argument(
        '--input', '-i',
        default='iPad',
        metavar='PORT',
        help='MIDI input port name to listen on (default: "iPad")',
    )
    parser.add_argument(
        '--incontrol', '-c',
        default=None,
        metavar='PORT',
        help='SL MkIII InControl output port name (auto-detected if omitted)',
    )
    parser.add_argument(
        '--list-ports', '-l',
        action='store_true',
        help='List available MIDI ports and exit',
    )

    args = parser.parse_args()

    if args.list_ports:
        print('Input ports:')
        for name in mido.get_input_names():
            print(f'  {name}')
        print('Output ports:')
        for name in mido.get_output_names():
            print(f'  {name}')
    else:
        surface = QKSurface(
            midi_input=args.input,
            incontrol_port=args.incontrol,
        )
        surface.run()
