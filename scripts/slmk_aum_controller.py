"""SL MkIII <-> AUM live controller — Mac runtime, eventual Mozaic transcription.

Listens to SL MkIII on the InControl USB port, translates input to MIDI CC and
notes on the iPad iDAM port, and paints SL MkIII screens / LEDs back in real
time. Hybrid UX: page selection (top row), optional multi-instance focus
(second row), and direct fixed bindings on knobs/faders/pads.

Run:
    uv run python scripts/slmk_aum_controller.py
"""

from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass, field
from typing import Callable

import mido

from slmkiii.incontrol import (
    Control,
    InControlConnection,
    LAYOUT_EMPTY,
    LAYOUT_KNOB,
    LED,
    PadNote,
    PROP_COLOUR,
    PROP_TEXT,
    PROP_VALUE,
)


SL_KNOB_BASE = Control.KNOB_1.value
SL_FADER_BASE = Control.FADER_1.value
SL_SOFTBTN_BASE = Control.SOFT_BUTTON_1.value
SL_PAD_BASE = PadNote.PAD_1.value
SL_PADS_UP = Control.PADS_UP.value
SL_PADS_DOWN = Control.PADS_DOWN.value
SL_TRACK_LEFT = Control.TRACK_LEFT.value
SL_TRACK_RIGHT = Control.TRACK_RIGHT.value

LED_TOP_ROW_BASE = LED.SOFT_BUTTON_1.value
LED_2ND_ROW_BASE = LED.SOFT_BUTTON_9.value
LED_PAD_BASE = LED.PAD_1.value
LED_FADER_BASE = LED.FADER_1.value

COL_OFF = 0
COL_DIM_WHITE = 1
COL_WHITE = 3
COL_RED = 5
COL_ORANGE = 9
COL_YELLOW = 13
COL_GREEN = 21
COL_DIM_GREEN = 23
COL_CYAN = 33
COL_BLUE = 37
COL_PURPLE = 49


@dataclass(frozen=True)
class Binding:
    label: str
    cc: int
    channel: int
    param_path: str = ''
    min_val: int = 0
    max_val: int = 127


@dataclass
class Page:
    name: str
    label: str
    color: int
    knobs: list[Binding] = field(default_factory=list)
    faders: list[Binding] = field(default_factory=list)
    pads: list[Binding] = field(default_factory=list)
    focus_set: list[str] = field(default_factory=list)
    # When set, current_page is computed by calling specialize(focus_idx).
    specialize: Callable[[int], 'Page'] | None = None


def _make_drum_page(drum_idx: int) -> Page:
    n = drum_idx
    cc_start = 28 + (n - 1) * 8
    return Page(
        name=f'drum{n}',
        label=f'Drum {n}',
        color=COL_ORANGE,
        knobs=[
            Binding(f'D{n} Cut',  cc_start + 0, 1, f'drumProtoParams.drum{n}params.drum{n}cutoff'),
            Binding(f'D{n} Reso', cc_start + 1, 1, f'drumProtoParams.drum{n}params.drum{n}resonance'),
            Binding(f'D{n} Dist', cc_start + 2, 1, f'drumProtoParams.drum{n}params.drum{n}distort'),
            Binding(f'D{n} Mix',  cc_start + 3, 1, f'drumProtoParams.drum{n}params.drum{n}enginemix'),
        ],
        faders=[
            Binding(f'D{n} Lvl',  cc_start + 4, 1, f'drumProtoParams.drum{n}params.drum{n}outGain'),
            Binding(f'D{n} Pit',  cc_start + 5, 1, f'drumProtoParams.drum{n}params.drum{n}pitch'),
            Binding(f'D{n} Dec',  cc_start + 6, 1, f'drumProtoParams.drum{n}params.drum{n}env1decay'),
            Binding(f'D{n} Snd',  cc_start + 7, 1, f'drumProtoParams.drum{n}params.drum{n}sendA'),
        ],
    )


DRUM_FOCUS_PAGES: dict[int, Page] = {i: _make_drum_page(i + 1) for i in range(8)}

BATTALION_DRUM_NOTE_BASE = 36
BATTALION_DRUM_CHANNEL = 10


def _battalion_pads() -> list[Binding]:
    return [
        Binding(f'Pad {i + 1}', BATTALION_DRUM_NOTE_BASE + i,
                BATTALION_DRUM_CHANNEL, f'drum_trigger_{i + 1}')
        for i in range(16)
    ]


PAGES: list[Page] = [
    Page(
        name='bat_global',
        label='Bat Mix',
        color=COL_RED,
        knobs=[
            Binding('Master',   7,  1, 'Volume'),
            Binding('OutGain',  21, 1, 'drumProtoParams.effectParams.outGain'),
            Binding('Maximize', 22, 1, 'drumProtoParams.effectParams.maximize'),
            Binding('ModDepth', 23, 1, 'drumProtoParams.performParams.modulationDepth'),
        ],
        faders=[
            Binding('EQ Low',   24, 1, 'drumProtoParams.effectParams.eqlow'),
            Binding('EQ Mid',   25, 1, 'drumProtoParams.effectParams.eqmid'),
            Binding('EQ High',  26, 1, 'drumProtoParams.effectParams.eqhigh'),
            Binding('Random',   27, 1, 'drumProtoParams.performParams.performRandomDepth'),
        ],
        pads=_battalion_pads(),
    ),
    Page(
        name='bat_drum',
        label='Bat Drum',
        color=COL_ORANGE,
        pads=_battalion_pads(),
        focus_set=[f'drum{i + 1}' for i in range(8)],
        specialize=lambda focus_idx: DRUM_FOCUS_PAGES[focus_idx],
    ),
    Page(
        name='animoog_orb',
        label='Anmg Orb',
        color=COL_GREEN,
        knobs=[
            Binding('Orb X',    20, 3, 'orb_x_k'),
            Binding('Orb Y',    21, 3, 'orb_y_k'),
            Binding('Orb Z',    22, 3, 'orb_z_k'),
            Binding('Orb Rt',   23, 3, 'orb_rate_k'),
        ],
        faders=[
            Binding('Origin X', 24, 3, 'origin_x_k'),
            Binding('Origin Y', 25, 3, 'origin_y_k'),
            Binding('Origin Z', 26, 3, 'origin_z_k'),
            Binding('Z Mult',   27, 3, 'z_mult_k'),
        ],
    ),
    Page(
        name='animoog_voice',
        label='Anmg Voc',
        color=COL_CYAN,
        knobs=[
            Binding('BaseFreq', 28, 3, 'base_freq_k'),
            Binding('Glide',    29, 3, 'syn_glide_k'),
            Binding('Voices',   30, 3, 'syn_voice_limit_k'),
            Binding('Volume',   31, 3, 'syn_volume_k'),
        ],
        faders=[
            Binding('PathRate', 33, 3, 'path_rate_k'),
            Binding('PathDir',  34, 3, 'path_dir_k'),
            Binding('PathSync', 35, 3, 'path_sync_t'),
            Binding('OrbSync',  36, 3, 'orb_sync_t'),
        ],
    ),
    Page(
        name='drambo',
        label='Drambo',
        color=COL_PURPLE,
        knobs=[
            Binding(f'Macro{i + 1}', 102 + i, 3, f'unassigned{i + 1}')
            for i in range(4)
        ],
        faders=[
            Binding(f'Macro{i + 5}', 106 + i, 3, f'unassigned{i + 5}')
            for i in range(4)
        ],
    ),
]


class ControllerState:
    def __init__(self) -> None:
        self.current_page_idx = 0
        self.focus_idx = 0
        self.value_cache: dict[tuple[int, int], int] = {}

    @property
    def current_page_meta(self) -> Page:
        return PAGES[self.current_page_idx]

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


def _value_to_color(value: int) -> int:
    if value < 16:
        return COL_OFF
    if value < 48:
        return COL_DIM_GREEN
    if value < 96:
        return COL_GREEN
    if value < 120:
        return COL_YELLOW
    return COL_RED


class Renderer:
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

        self.conn.set_layout(LAYOUT_KNOB)

        for col in range(8):
            if col < 4:
                bindings, bcol, color = page.knobs, col, meta.color
            else:
                bindings, bcol, color = page.faders, col - 4, COL_DIM_WHITE

            if bcol < len(bindings):
                b = bindings[bcol]
                self.conn.set_screen_properties(col, [
                    (PROP_TEXT, 0, b.label[:9].encode('ascii', errors='replace')),
                    (PROP_VALUE, 0, state.get_value(b)),
                    (PROP_COLOUR, 0, color),
                ])
            else:
                self.conn.set_screen_properties(col, [
                    (PROP_TEXT, 0, b''),
                    (PROP_VALUE, 0, 0),
                    (PROP_COLOUR, 0, COL_OFF),
                ])

        self._repaint_page_leds(state)
        self._repaint_focus_leds(state)
        self._repaint_fader_leds(state)
        self._repaint_pad_leds(state)

    def _repaint_page_leds(self, state: ControllerState) -> None:
        for i in range(8):
            led = LED_TOP_ROW_BASE + i
            if i < len(PAGES):
                page = PAGES[i]
                color = page.color if i == state.current_page_idx else COL_DIM_WHITE
                self.set_led(led, color)
            else:
                self.set_led(led, COL_OFF)

    def _repaint_focus_leds(self, state: ControllerState) -> None:
        meta = state.current_page_meta
        for i in range(8):
            led = LED_2ND_ROW_BASE + i
            if not meta.focus_set:
                self.set_led(led, COL_OFF)
            elif i == state.focus_idx:
                self.set_led(led, COL_WHITE)
            elif i < len(meta.focus_set):
                self.set_led(led, COL_DIM_WHITE)
            else:
                self.set_led(led, COL_OFF)

    def _repaint_fader_leds(self, state: ControllerState) -> None:
        page = state.current_page
        for i in range(8):
            led = LED_FADER_BASE + i
            if i < len(page.faders):
                self.set_led(led, _value_to_color(state.get_value(page.faders[i])))
            else:
                self.set_led(led, COL_OFF)

    def _repaint_pad_leds(self, state: ControllerState) -> None:
        page = state.current_page
        for i in range(16):
            led = LED_PAD_BASE + i
            self.set_led(led, COL_BLUE if i < len(page.pads) else COL_OFF)

    def update_value_screen(self, col: int, value: int) -> None:
        self.conn.set_value(col, 0, value)

    def flash(self, line1: str, line2: str = '') -> None:
        self.conn.notify(line1[:18], line2[:18])


class Controller:
    def __init__(self, conn: InControlConnection, ipad_out: mido.ports.BaseOutput) -> None:
        self.conn = conn
        self.ipad_out = ipad_out
        self.state = ControllerState()
        self.renderer = Renderer(conn)

    def run(self) -> None:
        self.renderer.repaint_all(self.state)
        self.renderer.flash('SL Controller', PAGES[0].label)
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
        self.renderer.set_led(LED_FADER_BASE + idx, _value_to_color(val))

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
            self.renderer.set_led(LED_PAD_BASE + idx, COL_WHITE)
        else:
            self._send(mido.Message('note_off',
                                    channel=b.channel - 1, note=b.cc, velocity=0))
            self.renderer.set_led(LED_PAD_BASE + idx, COL_BLUE)

    def _handle_button(self, event: dict) -> None:
        if not event.get('pressed'):
            return
        cc = event['control']

        if SL_SOFTBTN_BASE <= cc < SL_SOFTBTN_BASE + 8:
            page_idx = cc - SL_SOFTBTN_BASE
            if page_idx < len(PAGES):
                self._switch_page(page_idx)
            return

        if SL_SOFTBTN_BASE + 8 <= cc < SL_SOFTBTN_BASE + 16:
            self._switch_focus(cc - (SL_SOFTBTN_BASE + 8))
            return

        if cc == SL_TRACK_LEFT:
            self._switch_page((self.state.current_page_idx - 1) % len(PAGES))
        elif cc == SL_TRACK_RIGHT:
            self._switch_page((self.state.current_page_idx + 1) % len(PAGES))
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
        self.ipad_out.send(msg)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ipad-port', default='iPad')
    args = parser.parse_args()

    print('Opening SL MkIII InControl ...')
    conn = InControlConnection()
    conn.__enter__()

    print(f'Opening iPad output: {args.ipad_port!r} ...')
    try:
        ipad_out = mido.open_output(args.ipad_port)
    except Exception as e:
        print(f'ERROR opening iPad port: {e}')
        conn.close()
        return 1

    controller = Controller(conn, ipad_out)
    try:
        controller.run()
    except KeyboardInterrupt:
        print('\nStopping ...')
    finally:
        try:
            conn.clear_all_leds()
            conn.set_layout(LAYOUT_EMPTY)
        except Exception:
            pass
        conn.close()
        ipad_out.close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
