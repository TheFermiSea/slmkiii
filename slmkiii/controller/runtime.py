"""Live SL MkIII <-> AUM controller runtime.

Listens to the SL MkIII InControl USB port, translates input to MIDI CC and
notes on a downstream output port (typically iPad iDAM), and paints SL MkIII
screens / LEDs back in real time.

Pipeline:
    SL InControl IN  →  Controller  →  output port  (iPad iDAM)
    Controller       →  SL InControl OUT (screen text/value/colour, LEDs)
"""

from __future__ import annotations

import time

import mido

from slmkiii.controller.config import Binding, Page
from slmkiii.incontrol import (
    Control,
    InControlConnection,
    LED,
    PadNote,
)
from slmkiii.sysex import (
    Color,
    Layout,
    ScreenProp,
)


# ---------------------------------------------------------------------------
# Input vocabulary on the SL MkIII (sourced from sysex enums)
# ---------------------------------------------------------------------------
SL_KNOB_BASE = Control.KNOB_1.value
SL_FADER_BASE = Control.FADER_1.value
SL_SOFTBTN_BASE = Control.SOFT_BUTTON_1.value
SL_PAD_BASE = PadNote.PAD_1.value
SL_PADS_UP = Control.PADS_UP.value
SL_PADS_DOWN = Control.PADS_DOWN.value
SL_TRACK_LEFT = Control.TRACK_LEFT.value
SL_TRACK_RIGHT = Control.TRACK_RIGHT.value

# LED index bases
LED_TOP_ROW_BASE = LED.SOFT_BUTTON_1.value
LED_2ND_ROW_BASE = LED.SOFT_BUTTON_9.value
LED_PAD_BASE = LED.PAD_1.value
LED_FADER_BASE = LED.FADER_1.value


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------
class ControllerState:
    """Mutable controller state: which page/focus is active, knob values."""

    def __init__(self, pages: list[Page]) -> None:
        self.pages = pages
        self.current_page_idx = 0
        self.focus_idx = 0
        self.value_cache: dict[tuple[int, int], int] = {}

    @property
    def current_page_meta(self) -> Page:
        return self.pages[self.current_page_idx]

    @property
    def current_page(self) -> Page:
        meta = self.current_page_meta
        if meta.specialize is not None:
            return meta.specialize(self.focus_idx)
        return meta

    def focus_label(self) -> str:
        meta = self.current_page_meta
        if meta.focus_set and self.focus_idx < len(meta.focus_set):
            return meta.focus_set[self.focus_idx]
        return ''

    def get_value(self, b: Binding) -> int:
        return self.value_cache.get((b.channel, b.cc), 64)

    def set_value(self, b: Binding, value: int) -> int:
        clamped = max(b.min_val, min(b.max_val, value))
        self.value_cache[(b.channel, b.cc)] = clamped
        return clamped


def value_to_fader_color(value: int) -> int:
    """Map 0..127 to a colour for the fader-position indicator LED."""
    if value < 16:
        return Color.OFF
    if value < 48:
        return Color.DIM_GREEN
    if value < 96:
        return Color.GREEN
    if value < 120:
        return Color.YELLOW
    return Color.RED


# ---------------------------------------------------------------------------
# Renderer
# ---------------------------------------------------------------------------
class Renderer:
    """Paints the SL MkIII screens + LEDs to reflect ControllerState."""

    def __init__(self, conn: InControlConnection) -> None:
        self.conn = conn
        self._led_cache: dict[int, int] = {}

    def set_led(self, led: int, color: int) -> None:
        if self._led_cache.get(led) == color:
            return
        self._led_cache[led] = color
        self.conn.set_led(led, color)

    def repaint_all(self, state: ControllerState) -> None:
        page = state.current_page
        meta = state.current_page_meta

        self.conn.set_layout(Layout.KNOB)

        for col in range(8):
            if col < 4:
                bindings, bcol, color = page.knobs, col, meta.color
            else:
                bindings, bcol, color = page.faders, col - 4, Color.DIM_WHITE

            if bcol < len(bindings):
                b = bindings[bcol]
                self.conn.set_screen_properties(col, [
                    (ScreenProp.TEXT, 0, b.label[:9].encode('ascii', errors='replace')),
                    (ScreenProp.VALUE, 0, state.get_value(b)),
                    (ScreenProp.COLOUR, 0, color),
                ])
            else:
                self.conn.set_screen_properties(col, [
                    (ScreenProp.TEXT, 0, b''),
                    (ScreenProp.VALUE, 0, 0),
                    (ScreenProp.COLOUR, 0, Color.OFF),
                ])

        self._repaint_page_leds(state)
        self._repaint_focus_leds(state)
        self._repaint_fader_leds(state)
        self._repaint_pad_leds(state)

    def _repaint_page_leds(self, state: ControllerState) -> None:
        for i in range(8):
            led = LED_TOP_ROW_BASE + i
            if i < len(state.pages):
                page = state.pages[i]
                color = page.color if i == state.current_page_idx else Color.DIM_WHITE
                self.set_led(led, color)
            else:
                self.set_led(led, Color.OFF)

    def _repaint_focus_leds(self, state: ControllerState) -> None:
        meta = state.current_page_meta
        for i in range(8):
            led = LED_2ND_ROW_BASE + i
            if not meta.focus_set:
                self.set_led(led, Color.OFF)
            elif i == state.focus_idx:
                self.set_led(led, Color.WHITE)
            elif i < len(meta.focus_set):
                self.set_led(led, Color.DIM_WHITE)
            else:
                self.set_led(led, Color.OFF)

    def _repaint_fader_leds(self, state: ControllerState) -> None:
        page = state.current_page
        for i in range(8):
            led = LED_FADER_BASE + i
            if i < len(page.faders):
                self.set_led(led, value_to_fader_color(state.get_value(page.faders[i])))
            else:
                self.set_led(led, Color.OFF)

    def _repaint_pad_leds(self, state: ControllerState) -> None:
        page = state.current_page
        for i in range(16):
            led = LED_PAD_BASE + i
            self.set_led(led, Color.BLUE if i < len(page.pads) else Color.OFF)

    def update_value_screen(self, col: int, value: int) -> None:
        self.conn.set_value(col, 0, value)

    def flash(self, line1: str, line2: str = '') -> None:
        self.conn.notify(line1[:18], line2[:18])


# ---------------------------------------------------------------------------
# Controller event loop
# ---------------------------------------------------------------------------
class Controller:
    """Wires SL MkIII input → output port and renders feedback to the SL."""

    def __init__(self, conn: InControlConnection,
                 output: mido.ports.BaseOutput,
                 pages: list[Page]) -> None:
        self.conn = conn
        self.output = output
        self.state = ControllerState(pages)
        self.renderer = Renderer(conn)

    def run(self) -> None:
        self.renderer.repaint_all(self.state)
        self.renderer.flash('SL Controller', self.state.pages[0].label)
        print('Controller running. Ctrl-C to stop.')
        while True:
            for event in self.conn.poll_input():
                self._handle_event(event)
            time.sleep(0.005)

    def _handle_event(self, event: dict) -> None:
        kind = event['type']
        if kind == 'knob':
            self._handle_knob(event)
        elif kind == 'fader':
            self._handle_fader(event)
        elif kind == 'button':
            self._handle_button(event)
        elif kind == 'pad':
            self._handle_pad(event)

    def _handle_knob(self, event: dict) -> None:
        idx = event['knob'] - 1
        page = self.state.current_page
        if idx >= len(page.knobs):
            return
        b = page.knobs[idx]
        prev = self.state.get_value(b)
        new_val = max(0, min(127, prev + event['delta']))
        if new_val == prev:
            return
        self.state.set_value(b, new_val)
        self._send(mido.Message('control_change',
                                channel=b.channel - 1, control=b.cc, value=new_val))
        self.renderer.update_value_screen(idx, new_val)

    def _handle_fader(self, event: dict) -> None:
        idx = event['fader'] - 1
        page = self.state.current_page
        if idx >= len(page.faders):
            return
        b = page.faders[idx]
        val = event['value']
        if val == self.state.get_value(b):
            return
        self.state.set_value(b, val)
        self._send(mido.Message('control_change',
                                channel=b.channel - 1, control=b.cc, value=val))
        self.renderer.update_value_screen(idx + 4, val)
        self.renderer.set_led(LED_FADER_BASE + idx, value_to_fader_color(val))

    def _handle_pad(self, event: dict) -> None:
        idx = event['pad'] - 1
        page = self.state.current_page
        if idx >= len(page.pads):
            return
        b = page.pads[idx]
        velocity = event['velocity']
        if velocity > 0:
            self._send(mido.Message('note_on',
                                    channel=b.channel - 1, note=b.cc, velocity=velocity))
            self.renderer.set_led(LED_PAD_BASE + idx, Color.WHITE)
        else:
            self._send(mido.Message('note_off',
                                    channel=b.channel - 1, note=b.cc, velocity=0))
            self.renderer.set_led(LED_PAD_BASE + idx, Color.BLUE)

    def _handle_button(self, event: dict) -> None:
        if not event.get('pressed'):
            return
        cc = event['control']
        n_pages = len(self.state.pages)

        if SL_SOFTBTN_BASE <= cc < SL_SOFTBTN_BASE + 8:
            page_idx = cc - SL_SOFTBTN_BASE
            if page_idx < n_pages:
                self._switch_page(page_idx)
            return

        if SL_SOFTBTN_BASE + 8 <= cc < SL_SOFTBTN_BASE + 16:
            self._switch_focus(cc - (SL_SOFTBTN_BASE + 8))
            return

        if cc == SL_TRACK_LEFT:
            self._switch_page((self.state.current_page_idx - 1) % n_pages)
        elif cc == SL_TRACK_RIGHT:
            self._switch_page((self.state.current_page_idx + 1) % n_pages)
        elif cc == SL_PADS_UP:
            self._switch_focus(max(0, self.state.focus_idx - 1))
        elif cc == SL_PADS_DOWN:
            self._switch_focus(min(7, self.state.focus_idx + 1))

    def _switch_page(self, page_idx: int) -> None:
        if page_idx == self.state.current_page_idx:
            return
        self.state.current_page_idx = page_idx
        self.state.focus_idx = 0
        page = self.state.current_page
        meta = self.state.current_page_meta
        self.renderer.repaint_all(self.state)
        self.renderer.flash(meta.label, self.state.focus_label())
        print(f'Page -> {meta.name} ({page.label})')

    def _switch_focus(self, focus_idx: int) -> None:
        meta = self.state.current_page_meta
        if not meta.focus_set or focus_idx >= len(meta.focus_set):
            return
        if focus_idx == self.state.focus_idx:
            return
        self.state.focus_idx = focus_idx
        self.renderer.repaint_all(self.state)
        page = self.state.current_page
        self.renderer.flash(meta.label, page.label)
        print(f'Focus -> {meta.focus_set[focus_idx]}')

    def _send(self, msg: mido.Message) -> None:
        self.output.send(msg)


def run(pages: list[Page], output_port: str = 'iPad') -> int:
    """Open the InControl + output ports and run the event loop until Ctrl-C."""
    print('Opening SL MkIII InControl ...')
    conn = InControlConnection()
    conn.__enter__()

    print(f'Opening output port: {output_port!r} ...')
    try:
        output = mido.open_output(output_port)
    except Exception as e:
        print(f'ERROR opening output port: {e}')
        conn.close()
        return 1

    controller = Controller(conn, output, pages)
    try:
        controller.run()
    except KeyboardInterrupt:
        print('\nStopping ...')
    finally:
        try:
            conn.clear_all_leds()
            conn.set_layout(Layout.EMPTY)
        except Exception:
            pass
        conn.close()
        output.close()
    return 0
