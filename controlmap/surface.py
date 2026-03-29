"""Control surface daemon — bridges controlmap mappings to SL MkIII hardware.

Manages real-time screen labels, LED states, value tracking, and page
switching via the InControl API. Runs as a persistent process on the Mac.

Usage::

    from controlmap.surface import ControlSurface
    from controlmap import compile_mapping
    from controlmap.model import MappingSpec

    spec = MappingSpec(...)
    resolved = compile_mapping(spec)
    surface = ControlSurface(resolved, midi_output='iPad')
    surface.run()  # blocks, Ctrl-C to stop
"""
from __future__ import annotations

import signal
import time

import mido

from slmkiii.incontrol import (
    InControlConnection, LED, Control,
    LAYOUT_KNOB, COLUMN_CENTER,
    PROP_TEXT, PROP_COLOUR, PROP_VALUE,
)
from controlmap.model import MsgType, ResolvedMapping, Binding

# Derive LED groups from sequential enum values
_BUTTON_LEDS = [LED(LED.SOFT_BUTTON_1 + i) for i in range(16)]
_PAD_LEDS = [LED(LED.PAD_1 + i) for i in range(16)]
_FADER_LEDS = [LED(LED.FADER_1 + i) for i in range(8)]

# SL MkIII 128-color palette indices
COLOR_OFF = 0
COLOR_WHITE = 3
COLOR_RED = 5
COLOR_ORANGE = 9
COLOR_YELLOW = 13
COLOR_GREEN = 21
COLOR_CYAN = 33
COLOR_BLUE = 37
COLOR_PURPLE = 49

# Rate limit for knob screen updates (seconds)
_SCREEN_UPDATE_INTERVAL = 0.03  # ~33 Hz


class ControlSurface:
    """Real-time control surface manager for the SL MkIII.

    Connects to the InControl port and manages:
    - Screen labels showing parameter names
    - Knob value display tracking
    - LED feedback for button/pad states
    - Page switching via Screen Up/Down buttons
    - MIDI forwarding to DAW (replaces template-mode MIDI output)
    """

    def __init__(self, resolved: ResolvedMapping, midi_output: str | None = None):
        """Initialize the control surface.

        Args:
            resolved: Compiled mapping with pages and bindings.
            midi_output: MIDI output port name for forwarding CC/Note
                         to the DAW (e.g., 'iPad' for AUM via iDAM).
                         If None, no MIDI is forwarded.
        """
        self._resolved = resolved
        self._pages = resolved.page_set.pages
        self._current_page = 0
        self._ic: InControlConnection | None = None
        self._midi_output_name = midi_output
        self._midi_out = None

        # Track current values per binding (for screen display)
        self._values: dict[tuple[str, int], int] = {}

        # Track button toggle states
        self._button_states: dict[tuple[str, int], bool] = {}

        # Cached bindings dict, invalidated on page switch
        self._cached_bindings: dict[tuple[str, int], Binding] | None = None

        # Rate limiting for knob screen updates
        self._last_screen_update: dict[int, float] = {}

    @property
    def current_page(self):
        return self._pages[self._current_page] if self._pages else None

    @property
    def page_count(self):
        return len(self._pages)

    def _send_midi(self, binding: Binding, value: int):
        """Forward a CC or Note message to the MIDI output port."""
        if self._midi_out is None:
            return
        channel = binding.midi_channel - 1  # mido uses 0-indexed
        if binding.msg_type == MsgType.CC:
            msg = mido.Message('control_change', channel=channel,
                               control=binding.midi_cc, value=value)
        else:
            if value > 0:
                msg = mido.Message('note_on', channel=channel,
                                   note=binding.midi_note, velocity=value)
            else:
                msg = mido.Message('note_off', channel=channel,
                                   note=binding.midi_note, velocity=0)
        self._midi_out.send(msg)

    def _bindings_by_slot(self) -> dict[tuple[str, int], Binding]:
        """Get current page's bindings indexed by (group, index). Cached."""
        if self._cached_bindings is not None:
            return self._cached_bindings
        page = self.current_page
        if not page:
            self._cached_bindings = {}
        else:
            self._cached_bindings = {
                (b.slot.group, b.slot.index): b for b in page.bindings
            }
        return self._cached_bindings

    def _invalidate_cache(self):
        """Invalidate cached bindings (call on page switch)."""
        self._cached_bindings = None

    def _refresh_screens(self, ic: InControlConnection):
        """Update all screens for the current page using batched SysEx."""
        ic.set_layout(LAYOUT_KNOB)

        bindings = self._bindings_by_slot()

        for i in range(8):
            binding = bindings.get(('knobs', i))
            if binding:
                name = binding.param.display_name or binding.param.param_path.split('.')[-1][:9]
                val = self._values.get(('knobs', i), 0)
                pct = round(val / 127 * 100)
                # Batch: text + value + color in one SysEx per column
                ic.set_screen_properties(i, [
                    (PROP_TEXT, 0, name[:9].encode('ascii', errors='replace') + b'\x00'),
                    (PROP_TEXT, 2, f'{pct}%'.encode('ascii') + b'\x00'),
                    (PROP_VALUE, 0, val),
                    (PROP_COLOUR, 0, COLOR_CYAN),
                ])
            else:
                ic.set_screen_properties(i, [
                    (PROP_TEXT, 0, b'\x00'),
                    (PROP_TEXT, 2, b'\x00'),
                    (PROP_VALUE, 0, 0),
                    (PROP_COLOUR, 0, COLOR_OFF),
                ])

        # Center screen
        page = self.current_page
        if page:
            ic.set_text(COLUMN_CENTER, 0, page.name[:9])
            ic.set_text(COLUMN_CENTER, 1, f'Pg {self._current_page + 1}/{self.page_count}')

    def _refresh_leds(self, ic: InControlConnection):
        """Update LED states for current page."""
        bindings = self._bindings_by_slot()

        for i, led in enumerate(_BUTTON_LEDS):
            binding = bindings.get(('buttons', i))
            if binding:
                toggled = self._button_states.get(('buttons', i), False)
                ic.set_led(led, COLOR_GREEN if toggled else COLOR_RED)
            else:
                ic.set_led(led, COLOR_OFF)

        for i, led in enumerate(_FADER_LEDS):
            binding = bindings.get(('faders', i))
            ic.set_led(led, COLOR_CYAN if binding else COLOR_OFF)

        for i, led in enumerate(_PAD_LEDS):
            binding = bindings.get(('pads', i))
            ic.set_led(led, COLOR_PURPLE if binding else COLOR_OFF)

    def _update_knob_screen(self, ic: InControlConnection, knob_index: int, value: int):
        """Update a knob's screen display, rate-limited to avoid SysEx flooding."""
        now = time.monotonic()
        last = self._last_screen_update.get(knob_index, 0.0)
        if now - last < _SCREEN_UPDATE_INTERVAL:
            return
        self._last_screen_update[knob_index] = now
        pct = round(value / 127 * 100)
        ic.set_text(knob_index, 2, f'{pct}%')
        ic.set_value(knob_index, 0, value)

    def _switch_page(self, ic: InControlConnection, direction: int):
        """Switch to next/previous page and refresh display."""
        new_page = self._current_page + direction
        if 0 <= new_page < self.page_count:
            self._current_page = new_page
            self._invalidate_cache()
            self._refresh_screens(ic)
            self._refresh_leds(ic)
            ic.notify(
                self.current_page.name[:18] if self.current_page else '',
                f'Page {self._current_page + 1} of {self.page_count}',
            )

    def _handle_input(self, ic: InControlConnection):
        """Poll InControl port for input and update state."""
        events = ic.poll_input()
        if not events:
            return
        bindings = self._bindings_by_slot()

        for event in events:
            if event['type'] == 'knob':
                idx = event['knob'] - 1
                binding = bindings.get(('knobs', idx))
                if binding:
                    delta = event['delta']
                    current = self._values.get(('knobs', idx), 0)
                    new_val = max(0, min(127, current + delta))
                    self._values[('knobs', idx)] = new_val
                    self._update_knob_screen(ic, idx, new_val)
                    self._send_midi(binding, new_val)

            elif event['type'] == 'fader':
                idx = event['fader'] - 1
                binding = bindings.get(('faders', idx))
                if binding:
                    self._values[('faders', idx)] = event['value']
                    self._send_midi(binding, event['value'])

            elif event['type'] == 'button':
                cc = event['control']
                if event['pressed']:
                    if cc == Control.SCREEN_UP:
                        self._switch_page(ic, -1)
                    elif cc == Control.SCREEN_DOWN:
                        self._switch_page(ic, 1)
                    else:
                        btn_idx = cc - Control.SOFT_BUTTON_1
                        if 0 <= btn_idx < 16:
                            binding = bindings.get(('buttons', btn_idx))
                            if binding:
                                key = ('buttons', btn_idx)
                                self._button_states[key] = not self._button_states.get(key, False)
                                if btn_idx < len(_BUTTON_LEDS):
                                    ic.set_led(_BUTTON_LEDS[btn_idx],
                                               COLOR_GREEN if self._button_states[key] else COLOR_RED)
                                self._send_midi(binding, 127 if self._button_states[key] else 0)

            elif event['type'] == 'pad':
                idx = event['pad'] - 1
                if idx < len(_PAD_LEDS):
                    if event['pressed']:
                        ic.set_led(_PAD_LEDS[idx], COLOR_WHITE)
                        binding = bindings.get(('pads', idx))
                        if binding:
                            self._send_midi(binding, event.get('velocity', 127))
                    else:
                        binding = bindings.get(('pads', idx))
                        ic.set_led(_PAD_LEDS[idx],
                                   COLOR_PURPLE if binding else COLOR_OFF)
                        if binding:
                            self._send_midi(binding, 0)

    def run(self):
        """Run the control surface daemon. Blocks until Ctrl-C."""
        running = True

        def stop(_sig, _frame):
            nonlocal running
            running = False

        signal.signal(signal.SIGINT, stop)
        signal.signal(signal.SIGTERM, stop)

        print(f'Control Surface: {self._resolved.metadata.get("plugin", "?")}')
        print(f'Pages: {self.page_count}')
        print(f'Connecting to SL MkIII InControl...')

        if self._midi_output_name:
            self._midi_out = mido.open_output(self._midi_output_name)
            print(f'MIDI output: {self._midi_output_name}')

        with InControlConnection() as ic:
            self._ic = ic
            print(f'Connected. Screen Up/Down to switch pages. Ctrl-C to stop.')

            self._refresh_screens(ic)
            self._refresh_leds(ic)

            while running:
                self._handle_input(ic)
                time.sleep(0.005)

            # Clean up
            ic.set_layout(LAYOUT_KNOB)
            for i in range(8):
                ic.set_text(i, 0, '')
                ic.set_text(i, 2, '')
                ic.set_value(i, 0, 0)
            ic.clear_all_leds()

        self._ic = None
        if self._midi_out:
            self._midi_out.close()
            self._midi_out = None
        print('Control Surface stopped.')

    def run_once(self, ic: InControlConnection):
        """Set up screens/LEDs without entering the event loop."""
        self._ic = ic
        self._refresh_screens(ic)
        self._refresh_leds(ic)
