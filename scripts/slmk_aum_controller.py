"""SL MkIII <-> AUM live controller — Mac runtime, eventual Mozaic transcription.

Listens to SL MkIII on the InControl USB port, translates input to MIDI CC and
notes on the iPad iDAM port, and paints SL MkIII screens / LEDs back in real
time. Provides a hybrid UX combining page selection (top row of soft buttons),
optional multi-instance focus (second row, e.g. Battalion drum 1-8), and
direct fixed bindings (knobs/faders/pads).

Page model:
    PAGES = [Page(name, label, color, knobs[8], faders[8], pads[16], focus_set?)]

Top row soft buttons (input CC 0x33..0x3A) select active page.
Second row (input CC 0x3B..0x42) selects focus instance, when the active page
has a focus_set defined (drum tracks, timbres, etc).
Pads (note 0x60..0x6F) always trigger Battalion drum notes on ch10.
Track L/R cycle pages. Pads Up/Down cycle focus instance.

Run:
    uv run python scripts/slmk_aum_controller.py
"""

from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass, field

import mido

from slmkiii.incontrol import (
    InControlConnection,
    LAYOUT_KNOB,
    LAYOUT_EMPTY,
)


# ---------------------------------------------------------------------------
# SL MkIII InControl input vocabulary (channel 16 = mido channel 15)
# ---------------------------------------------------------------------------
SL_CH = 15
SL_KNOB_BASE = 0x15        # CC 0x15..0x1C, twos-complement deltas
SL_FADER_BASE = 0x29       # CC 0x29..0x30, absolute 0..127
SL_SOFTBTN_BASE = 0x33     # CC 0x33..0x4A, 127=down 0=up, 24 buttons in 3 rows
SL_PAD_BASE = 0x60         # NoteOn 0x60..0x6F with velocity
SL_PADS_UP = 0x55
SL_PADS_DOWN = 0x56
SL_TRACK_LEFT = 0x66
SL_TRACK_RIGHT = 0x67
SL_RECORD = 0x4C
SL_PLAY = 0x4B
SL_STOP = 0x4D

# LED index bases (output to SL InControl as NoteOn ch16, value=color)
LED_TOP_ROW_BASE = 0x04        # SOFT_BUTTON_1..8 (under screens)
LED_2ND_ROW_BASE = 0x0C        # SOFT_BUTTON_9..16
LED_PAD_BASE = 0x26            # PAD_1..16
LED_FADER_BASE = 0x36          # FADER_1..8

# SL MkIII palette (subset of 128-colour table)
COL_OFF = 0
COL_DIM_WHITE = 1
COL_WHITE = 3
COL_DIM_RED = 7
COL_RED = 5
COL_ORANGE = 9
COL_YELLOW = 13
COL_GREEN = 21
COL_DIM_GREEN = 23
COL_CYAN = 33
COL_BLUE = 37
COL_PURPLE = 49
COL_MAGENTA = 53


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Binding:
    """A control-to-MIDI mapping for one knob/fader/pad."""
    label: str          # display label, max 9 chars
    cc: int             # MIDI CC number 0..127 (or note number for pad)
    channel: int        # 1..16, user-facing
    param_path: str = ""  # informational
    min_val: int = 0
    max_val: int = 127


@dataclass
class Page:
    """A page of bindings selectable via the top-row soft buttons."""
    name: str
    label: str          # short display name (max 9 chars)
    color: int          # SL palette colour for the page-select LED
    knobs: list[Binding] = field(default_factory=list)
    faders: list[Binding] = field(default_factory=list)
    pads: list[Binding] = field(default_factory=list)
    # focus_set: when present, second-row buttons pick which focus instance is
    # active and the bindings above are interpreted as templates with the
    # focus index substituted (e.g. 'drumNcutoff' where N is focus+1).
    focus_set: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Plugin / page config
# ---------------------------------------------------------------------------
def make_drum_page(drum_idx: int) -> Page:
    """Build a Battalion drum-N page (drum_idx 1..8)."""
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


# Battalion drum-trigger notes — standard GM drum range
BATTALION_DRUM_NOTE_BASE = 36  # C2 = drum 1
BATTALION_DRUM_CHANNEL = 10


def battalion_pads() -> list[Binding]:
    """Pads 1..16 -> notes 36..51 ch10 (Battalion drum triggers)."""
    return [
        Binding(f'Pad {i + 1}', BATTALION_DRUM_NOTE_BASE + i,
                BATTALION_DRUM_CHANNEL, f'drum_trigger_{i + 1}')
        for i in range(16)
    ]


PAGES: list[Page] = [
    # Page 0: Battalion global mix
    Page(
        name='bat_global',
        label='Bat Mix',
        color=COL_RED,
        knobs=[
            Binding('Master',  7,   1, 'Volume'),
            Binding('OutGain', 21,  1, 'drumProtoParams.effectParams.outGain'),
            Binding('Maximize', 22, 1, 'drumProtoParams.effectParams.maximize'),
            Binding('ModDepth', 23, 1, 'drumProtoParams.performParams.modulationDepth'),
        ],
        faders=[
            Binding('EQ Low',  24,  1, 'drumProtoParams.effectParams.eqlow'),
            Binding('EQ Mid',  25,  1, 'drumProtoParams.effectParams.eqmid'),
            Binding('EQ High', 26,  1, 'drumProtoParams.effectParams.eqhigh'),
            Binding('Random',  27,  1, 'drumProtoParams.performParams.performRandomDepth'),
        ],
        pads=battalion_pads(),
    ),
    # Page 1: Battalion per-drum focus (uses 2nd row buttons to pick drum)
    Page(
        name='bat_drum',
        label='Bat Drum',
        color=COL_ORANGE,
        knobs=[],   # populated dynamically from focus_set
        faders=[],
        pads=battalion_pads(),
        focus_set=[f'drum{i + 1}' for i in range(8)],
    ),
    # Page 2: Animoog Orb
    Page(
        name='animoog_orb',
        label='Anmg Orb',
        color=COL_GREEN,
        knobs=[
            Binding('Orb X',   20,  3, 'orb_x_k'),
            Binding('Orb Y',   21,  3, 'orb_y_k'),
            Binding('Orb Z',   22,  3, 'orb_z_k'),
            Binding('Orb Rt',  23,  3, 'orb_rate_k'),
        ],
        faders=[
            Binding('Origin X', 24, 3, 'origin_x_k'),
            Binding('Origin Y', 25, 3, 'origin_y_k'),
            Binding('Origin Z', 26, 3, 'origin_z_k'),
            Binding('Z Mult',  27,  3, 'z_mult_k'),
        ],
    ),
    # Page 3: Animoog Voice
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
    # Page 4: Drambo Macros (8 generic CCs)
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

# Build drum focus pages on demand (page 1 specialization)
DRUM_FOCUS_PAGES: dict[int, Page] = {
    i: make_drum_page(i + 1) for i in range(8)
}


# ---------------------------------------------------------------------------
# Runtime state
# ---------------------------------------------------------------------------
class ControllerState:
    def __init__(self) -> None:
        self.current_page_idx = 0
        self.focus_idx = 0  # index within current page's focus_set, if any
        # knob position memory keyed by (channel, cc) so values persist across pages
        self.value_cache: dict[tuple[int, int], int] = {}

    @property
    def current_page(self) -> Page:
        page = PAGES[self.current_page_idx]
        if page.focus_set and page.name == 'bat_drum':
            # Specialize: pick the per-drum page for current focus
            return DRUM_FOCUS_PAGES[self.focus_idx]
        return page

    @property
    def current_page_meta(self) -> Page:
        """The original page entry (for color, focus_set), not the specialized one."""
        return PAGES[self.current_page_idx]

    def get_value(self, b: Binding) -> int:
        return self.value_cache.get((b.channel, b.cc), 64)

    def set_value(self, b: Binding, value: int) -> None:
        self.value_cache[(b.channel, b.cc)] = max(b.min_val, min(b.max_val, value))


# ---------------------------------------------------------------------------
# Renderer — paints the SL MkIII for the current state
# ---------------------------------------------------------------------------
class Renderer:
    def __init__(self, conn: InControlConnection) -> None:
        self.conn = conn

    def repaint_all(self, state: ControllerState) -> None:
        page = state.current_page
        meta = state.current_page_meta

        # Set screen layout to KNOB
        self.conn.set_layout(LAYOUT_KNOB)

        # 8 columns: cols 0..3 = knobs, cols 4..7 = faders
        for col in range(8):
            if col < 4:
                bindings = page.knobs
                bcol = col
                color = meta.color
            else:
                bindings = page.faders
                bcol = col - 4
                color = self._dim(meta.color)

            if bcol < len(bindings):
                b = bindings[bcol]
                self.conn.set_text(col, 0, b.label[:9])
                self.conn.set_value(col, 0, state.get_value(b))
                self.conn.set_color(col, 0, color)
            else:
                self.conn.set_text(col, 0, '')
                self.conn.set_value(col, 0, 0)
                self.conn.set_color(col, 0, COL_OFF)

        self.repaint_page_leds(state)
        self.repaint_focus_leds(state)
        self.repaint_fader_leds(state)
        self.repaint_pad_leds(state)

    def repaint_page_leds(self, state: ControllerState) -> None:
        for i, page in enumerate(PAGES[:8]):
            led = LED_TOP_ROW_BASE + i
            if i == state.current_page_idx:
                self.conn.set_led(led, page.color)
            else:
                self.conn.set_led(led, self._dim(page.color))
        # Clear unused top-row buttons
        for i in range(len(PAGES), 8):
            self.conn.set_led(LED_TOP_ROW_BASE + i, COL_OFF)

    def repaint_focus_leds(self, state: ControllerState) -> None:
        meta = state.current_page_meta
        if not meta.focus_set:
            for i in range(8):
                self.conn.set_led(LED_2ND_ROW_BASE + i, COL_OFF)
            return
        for i in range(8):
            led = LED_2ND_ROW_BASE + i
            if i == state.focus_idx:
                self.conn.set_led(led, COL_WHITE)
            elif i < len(meta.focus_set):
                self.conn.set_led(led, COL_DIM_WHITE)
            else:
                self.conn.set_led(led, COL_OFF)

    def repaint_fader_leds(self, state: ControllerState) -> None:
        page = state.current_page
        for i in range(8):
            led = LED_FADER_BASE + i
            if i < len(page.faders):
                b = page.faders[i]
                self.conn.set_led(led, _value_to_color(state.get_value(b)))
            else:
                self.conn.set_led(led, COL_OFF)

    def repaint_pad_leds(self, state: ControllerState) -> None:
        page = state.current_page
        for i in range(16):
            led = LED_PAD_BASE + i
            if i < len(page.pads):
                self.conn.set_led(led, COL_BLUE)
            else:
                self.conn.set_led(led, COL_OFF)

    def update_value_screen(self, col: int, value: int) -> None:
        self.conn.set_value(col, 0, value)

    def flash(self, line1: str, line2: str = '') -> None:
        self.conn.notify(line1[:18], line2[:18])

    @staticmethod
    def _dim(color: int) -> int:
        # Crude "dim" by clamping to a known dim variant; real palette has
        # adjacent dim entries for each hue
        if color == COL_RED:
            return COL_DIM_RED
        if color == COL_GREEN:
            return COL_DIM_GREEN
        if color == COL_WHITE:
            return COL_DIM_WHITE
        return color  # leave others as-is for now


def _value_to_color(value: int) -> int:
    """Map 0..127 to a color gradient for fader LEDs."""
    if value < 16:
        return COL_OFF
    if value < 48:
        return COL_DIM_GREEN
    if value < 96:
        return COL_GREEN
    if value < 120:
        return COL_YELLOW
    return COL_RED


# ---------------------------------------------------------------------------
# Knob delta integration
# ---------------------------------------------------------------------------
def integrate_delta(current: int, raw: int) -> int:
    """SL MkIII InControl knobs send twos-complement deltas: 1..63 = +N,
    65..127 = -(128 - N). Returns new clamped 0..127."""
    delta = raw - 128 if raw > 63 else raw
    return max(0, min(127, current + delta))


# ---------------------------------------------------------------------------
# Main controller loop
# ---------------------------------------------------------------------------
class Controller:
    def __init__(self, conn: InControlConnection, ipad_out: mido.ports.BaseOutput) -> None:
        self.conn = conn
        self.ipad_out = ipad_out
        self.state = ControllerState()
        self.renderer = Renderer(conn)

    def run(self) -> None:
        self.renderer.repaint_all(self.state)
        self.renderer.flash('SL Controller', 'Page 0')
        print('Controller running. Ctrl-C to stop.')
        while True:
            for event in self.conn.poll_input():
                self.handle_event(event)
            time.sleep(0.001)

    def handle_event(self, event: dict) -> None:
        kind = event.get('type')
        if kind == 'knob':
            self._handle_knob(event)
        elif kind == 'fader':
            self._handle_fader(event)
        elif kind == 'button':
            self._handle_button(event)
        elif kind == 'pad':
            self._handle_pad(event)

    def _handle_knob(self, event: dict) -> None:
        idx = event['knob'] - 1  # 0..7
        delta_raw = event['value']
        page = self.state.current_page
        if idx >= len(page.knobs):
            return
        b = page.knobs[idx]
        new_val = integrate_delta(self.state.get_value(b), delta_raw)
        if new_val == self.state.get_value(b):
            return
        self.state.set_value(b, new_val)
        self._send_cc(b.channel, b.cc, new_val)
        self.renderer.update_value_screen(idx, new_val)

    def _handle_fader(self, event: dict) -> None:
        idx = event['fader'] - 1
        val = event['value']
        page = self.state.current_page
        if idx >= len(page.faders):
            return
        b = page.faders[idx]
        self.state.set_value(b, val)
        self._send_cc(b.channel, b.cc, val)
        self.renderer.update_value_screen(idx + 4, val)
        # Update fader LED brightness
        self.conn.set_led(LED_FADER_BASE + idx, _value_to_color(val))

    def _handle_pad(self, event: dict) -> None:
        idx = event['pad'] - 1
        velocity = event['velocity']
        page = self.state.current_page
        if idx >= len(page.pads):
            return
        b = page.pads[idx]
        if velocity > 0:
            self._send_note_on(b.channel, b.cc, velocity)
            self.conn.set_led(LED_PAD_BASE + idx, COL_WHITE)
        else:
            self._send_note_off(b.channel, b.cc)
            self.conn.set_led(LED_PAD_BASE + idx, COL_BLUE)

    def _handle_button(self, event: dict) -> None:
        cc = event['control']
        pressed = event['value'] == 127
        if not pressed:
            return  # only act on press

        # Top row (0x33..0x3A) -> page select
        if SL_SOFTBTN_BASE <= cc < SL_SOFTBTN_BASE + 8:
            page_idx = cc - SL_SOFTBTN_BASE
            if page_idx < len(PAGES):
                self._switch_page(page_idx)
                return

        # Second row (0x3B..0x42) -> focus select
        if SL_SOFTBTN_BASE + 8 <= cc < SL_SOFTBTN_BASE + 16:
            focus_idx = cc - (SL_SOFTBTN_BASE + 8)
            self._switch_focus(focus_idx)
            return

        # Track L/R cycle pages
        if cc == SL_TRACK_LEFT:
            self._switch_page((self.state.current_page_idx - 1) % len(PAGES))
            return
        if cc == SL_TRACK_RIGHT:
            self._switch_page((self.state.current_page_idx + 1) % len(PAGES))
            return

        # Pads up/down cycle focus
        if cc == SL_PADS_UP:
            self._switch_focus(max(0, self.state.focus_idx - 1))
            return
        if cc == SL_PADS_DOWN:
            self._switch_focus(min(7, self.state.focus_idx + 1))
            return

    def _switch_page(self, page_idx: int) -> None:
        if page_idx == self.state.current_page_idx:
            return
        self.state.current_page_idx = page_idx
        self.state.focus_idx = 0
        page = self.state.current_page
        meta = self.state.current_page_meta
        label = page.label
        sub = ''
        if meta.focus_set:
            sub = meta.focus_set[self.state.focus_idx]
        self.renderer.repaint_all(self.state)
        self.renderer.flash(label, sub)
        print(f'Page -> {meta.name} ({page.label})')

    def _switch_focus(self, focus_idx: int) -> None:
        meta = self.state.current_page_meta
        if not meta.focus_set:
            return
        if focus_idx >= len(meta.focus_set):
            return
        if focus_idx == self.state.focus_idx:
            return
        self.state.focus_idx = focus_idx
        self.renderer.repaint_all(self.state)
        page = self.state.current_page
        self.renderer.flash(meta.label, page.label)
        print(f'Focus -> {meta.focus_set[focus_idx]}')

    def _send_cc(self, channel_1based: int, cc: int, value: int) -> None:
        msg = mido.Message('control_change',
                           channel=channel_1based - 1,
                           control=cc, value=value)
        self.ipad_out.send(msg)

    def _send_note_on(self, channel_1based: int, note: int, velocity: int) -> None:
        msg = mido.Message('note_on',
                           channel=channel_1based - 1,
                           note=note, velocity=velocity)
        self.ipad_out.send(msg)

    def _send_note_off(self, channel_1based: int, note: int) -> None:
        msg = mido.Message('note_off',
                           channel=channel_1based - 1,
                           note=note, velocity=0)
        self.ipad_out.send(msg)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ipad-port', default='iPad',
                        help='mido output port name for iDAM')
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
