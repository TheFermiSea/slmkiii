"""Live SL MkIII <-> AUM controller runtime (widget + observer architecture).

Pipeline:
    SL InControl IN  →  Controller  →  output port  (iPad iDAM)
    Controller       →  SL InControl OUT (screen text/value/colour, LEDs)

Architecture (c10):
    - Per-page Widgets (KnobBank/FaderBank/PadDrumKit) own slot regions and
      handle their own input + rendering. Built fresh on every page switch.
    - Parameters (slmkiii.params.Parameter) replace the flat value-cache
      dict. Same Parameter object is reused across pages keyed by
      (channel, cc), so values persist even when a page swap rewires which
      Widget owns it.
    - DisplayFrame absorbs all screen cell mutations into a per-cell dirty
      cache; flush() emits SysEx only for cells that actually changed.
    - LED rendering: Widgets paint their own LEDs via the led_set callback;
      page-select LEDs (top row) and focus-select LEDs (second row) are
      painted directly by the Controller (they belong to no widget).

The Controller still owns *navigation* (top-row buttons, second-row focus
buttons, track L/R, pads up/down). Widgets handle *content*.

Mode/View split is implicit: knob/fader widgets = "Mode" (what the knobs
do), pad widget + screen layout = "View" (what's painted). The two co-vary
per page so a separate `Mode` and `View` class doesn't pay for itself —
both live on the Page.
"""

from __future__ import annotations

import time
from typing import Iterable

import mido

from slmkiii.controller.config import Binding, Page
from slmkiii.display import DisplayFrame
from slmkiii.incontrol import (
    Control,
    InControlConnection,
    LED,
    PadNote,
)
from slmkiii.params import Parameter, StaticParameterProvider
from slmkiii.perf import timed
from slmkiii.sysex import (
    Color,
    Layout,
)
from slmkiii.widgets import (
    FaderBank,
    KnobBank,
    PadDrumKit,
    Widget,
    WidgetEvent,
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
# Helpers
# ---------------------------------------------------------------------------
def value_to_fader_color(value: int) -> int:
    """Map 0..127 to a colour for the fader-position indicator LED."""
    if value < 16:
        return int(Color.OFF)
    if value < 48:
        return int(Color.DIM_GREEN)
    if value < 96:
        return int(Color.GREEN)
    if value < 120:
        return int(Color.YELLOW)
    return int(Color.RED)


def _detect_pad_kit(pads: list[Binding]) -> tuple[int, int] | None:
    """If `pads` is a contiguous note sequence on a single channel, return
    (base_note, channel). Otherwise None — we currently don't support
    non-contiguous pad bindings (no test or page uses that pattern)."""
    if not pads:
        return None
    base = pads[0]
    for i, p in enumerate(pads):
        if p.channel != base.channel or p.cc != base.cc + i:
            return None
    return base.cc, base.channel


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------
class ControllerState:
    """Owns page index, focus index, and the global Parameter cache.

    Parameters are keyed by (channel, cc). The same Parameter is returned
    for any Binding sharing that key, so values persist across page switches
    even when a different Widget binds them on the new page.
    """

    def __init__(self, pages: list[Page]) -> None:
        self.pages = pages
        self.current_page_idx = 0
        self.focus_idx = 0
        self._params: dict[tuple[int, int], Parameter] = {}

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

    def parameter_for(self, b: Binding) -> Parameter:
        key = (b.channel, b.cc)
        p = self._params.get(key)
        if p is None:
            # Default value 64 matches legacy get_value default
            p = Parameter(
                name=b.label[:9],
                cc=b.cc,
                channel=b.channel,
                param_path=b.param_path,
                min_value=b.min_val,
                max_value=b.max_val,
                _value=64,
            )
            self._params[key] = p
        else:
            # Refresh display name + clamp range from latest binding (page swap
            # may rebind the same CC under a different label or range)
            p.name = b.label[:9]
            p.min_value = b.min_val
            p.max_value = b.max_val
        return p

    # -- back-compat shims for tests/test_controller.py ----------------------
    def get_value(self, b: Binding) -> int:
        return self.parameter_for(b).value

    def set_value(self, b: Binding, value: int) -> int:
        p = self.parameter_for(b)
        p.value = value
        return p.value


# ---------------------------------------------------------------------------
# MIDI sink + LED renderer adapters
# ---------------------------------------------------------------------------
class _MidoMidiSink:
    """Adapts a mido output port to slmkiii.widgets.MidiSink Protocol."""

    def __init__(self, output: mido.ports.BaseOutput) -> None:
        self._output = output

    def send_cc(self, channel: int, cc: int, value: int) -> None:
        self._output.send(mido.Message(
            'control_change', channel=channel - 1, control=cc, value=value))

    def send_note_on(self, channel: int, note: int, velocity: int) -> None:
        self._output.send(mido.Message(
            'note_on', channel=channel - 1, note=note, velocity=velocity))

    def send_note_off(self, channel: int, note: int) -> None:
        self._output.send(mido.Message(
            'note_off', channel=channel - 1, note=note, velocity=0))


class _LedRenderer:
    """LED diff cache. Widgets call it via led_set callback; the controller
    calls it directly for page-select / focus-select rows."""

    def __init__(self, conn: InControlConnection) -> None:
        self._conn = conn
        self._cache: dict[int, int] = {}

    def set(self, led: int, color: int) -> None:
        if self._cache.get(led) == color:
            return
        self._cache[led] = color
        self._conn.set_led(led, color)

    def invalidate(self) -> None:
        self._cache.clear()


# ---------------------------------------------------------------------------
# Renderer (kept for back-compat; thin shim over DisplayFrame + LedRenderer)
# ---------------------------------------------------------------------------
class Renderer:
    """Back-compat surface used by tests/external callers. Internally uses
    a DisplayFrame + LedRenderer instead of issuing SysEx directly."""

    def __init__(self, conn: InControlConnection) -> None:
        self.conn = conn
        self.frame = DisplayFrame(conn)
        self.leds = _LedRenderer(conn)

    def set_led(self, led: int, color: int) -> None:
        self.leds.set(led, color)

    def update_value_screen(self, col: int, value: int) -> None:
        self.frame.set_value(col, 0, value)
        self.frame.flush()

    def flash(self, line1: str, line2: str = '') -> None:
        self.conn.notify(line1[:18], line2[:18])


# ---------------------------------------------------------------------------
# Controller event loop
# ---------------------------------------------------------------------------
class Controller:
    """Wires SL MkIII input → Widgets → output port and renders feedback."""

    def __init__(self, conn: InControlConnection,
                 output: mido.ports.BaseOutput,
                 pages: list[Page]) -> None:
        self.conn = conn
        self.output = output
        self.state = ControllerState(pages)
        self.frame = DisplayFrame(conn)
        self.leds = _LedRenderer(conn)
        self.sink = _MidoMidiSink(output)
        self._widgets: list[Widget] = []
        self._build_widgets()

    # -- widget lifecycle ----------------------------------------------------
    def _tear_down_widgets(self) -> None:
        # Drop references; KnobBank/FaderBank unwire param observers in their
        # provider-changed callback by re-wiring on next render. Letting the
        # objects garbage-collect is sufficient here because each new page
        # builds fresh providers; old observers fire harmlessly until the GC
        # reaps them. For deterministic teardown we explicitly unwire.
        for w in self._widgets:
            unwire = getattr(w, "_unwire_param_observers", None)
            if unwire is not None:
                unwire()
        self._widgets = []

    def _build_widgets(self) -> None:
        self._tear_down_widgets()
        page = self.state.current_page
        meta = self.state.current_page_meta

        widgets: list[Widget] = []

        if page.knobs:
            knob_params = [self.state.parameter_for(b) for b in page.knobs]
            kb = KnobBank(StaticParameterProvider(knob_params),
                          label_color=meta.color)
            kb.bind(self.sink, self.frame, led_set=self.leds.set)
            widgets.append(kb)

        if page.faders:
            fader_params = [self.state.parameter_for(b) for b in page.faders]
            fb = FaderBank(StaticParameterProvider(fader_params))
            fb.bind(self.sink, self.frame, led_set=self.leds.set)
            widgets.append(fb)

        if page.pads:
            kit_geom = _detect_pad_kit(page.pads)
            if kit_geom is not None:
                base_note, chan = kit_geom
                kit = PadDrumKit(base_note=base_note, channel=chan,
                                 num_pads=len(page.pads))
                kit.bind(self.sink, self.frame, led_set=self.leds.set)
                widgets.append(kit)

        self._widgets = widgets

    def _repaint_all(self) -> None:
        self.frame.set_layout(Layout.KNOB)

        # Clear all 8 columns first; widgets will paint over the cells they own
        for col in range(8):
            self.frame.set_text(col, 0, "")
            self.frame.set_value(col, 0, 0)
            self.frame.set_color(col, 0, int(Color.OFF))

        for w in self._widgets:
            w.render(self.frame)

        self._paint_page_leds()
        self._paint_focus_leds()
        self._paint_fader_leds()

        self.frame.flush()

    def _paint_page_leds(self) -> None:
        for i in range(8):
            led = LED_TOP_ROW_BASE + i
            if i < len(self.state.pages):
                page = self.state.pages[i]
                color = (page.color if i == self.state.current_page_idx
                         else int(Color.DIM_WHITE))
                self.leds.set(led, color)
            else:
                self.leds.set(led, int(Color.OFF))

    def _paint_focus_leds(self) -> None:
        meta = self.state.current_page_meta
        for i in range(8):
            led = LED_2ND_ROW_BASE + i
            if not meta.focus_set:
                self.leds.set(led, int(Color.OFF))
            elif i == self.state.focus_idx:
                self.leds.set(led, int(Color.WHITE))
            elif i < len(meta.focus_set):
                self.leds.set(led, int(Color.DIM_WHITE))
            else:
                self.leds.set(led, int(Color.OFF))

    def _paint_fader_leds(self) -> None:
        page = self.state.current_page
        for i in range(8):
            led = LED_FADER_BASE + i
            if i < len(page.faders):
                p = self.state.parameter_for(page.faders[i])
                self.leds.set(led, value_to_fader_color(p.value))
            else:
                self.leds.set(led, int(Color.OFF))

    # -- main loop -----------------------------------------------------------
    def run(self) -> None:
        self._repaint_all()
        self.conn.notify("SL Controller"[:18],
                         self.state.pages[0].label[:18])
        print('Controller running. Ctrl-C to stop.')
        while True:
            for event in self.conn.poll_input():
                self._handle_event(event)
            self.frame.flush()
            time.sleep(0.005)

    # -- event dispatch ------------------------------------------------------
    def _handle_event(self, event: dict) -> None:
        with timed(f"event.{event['type']}"):
            wev = self._make_widget_event(event)
            if wev is not None:
                for w in self._widgets:
                    if w.on_event(wev):
                        if wev.kind == "fader":
                            page = self.state.current_page
                            if wev.index < len(page.faders):
                                p = self.state.parameter_for(page.faders[wev.index])
                                self.leds.set(LED_FADER_BASE + wev.index,
                                              value_to_fader_color(p.value))
                        return

            # Unconsumed: navigation / system buttons handled by Controller
            if event['type'] == 'button':
                self._handle_nav_button(event)

    def _make_widget_event(self, event: dict) -> WidgetEvent | None:
        kind = event['type']
        if kind == 'knob':
            idx = event['knob'] - 1
            return WidgetEvent(kind="knob_delta", index=idx,
                               value=event['delta'],
                               raw_channel=16,
                               raw_cc=SL_KNOB_BASE + idx)
        if kind == 'fader':
            idx = event['fader'] - 1
            return WidgetEvent(kind="fader", index=idx,
                               value=event['value'],
                               raw_channel=16,
                               raw_cc=SL_FADER_BASE + idx)
        if kind == 'pad':
            idx = event['pad'] - 1
            return WidgetEvent(kind="pad", index=idx,
                               value=event['velocity'],
                               raw_channel=16,
                               raw_cc=SL_PAD_BASE + idx)
        return None

    def _handle_nav_button(self, event: dict) -> None:
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
            meta = self.state.current_page_meta
            if meta.focus_set:
                self._switch_focus(min(len(meta.focus_set) - 1,
                                       self.state.focus_idx + 1))

    def _switch_page(self, page_idx: int) -> None:
        if page_idx == self.state.current_page_idx:
            return
        with timed("page_switch"):
            self.state.current_page_idx = page_idx
            self.state.focus_idx = 0
            self._build_widgets()
            self._repaint_all()
        meta = self.state.current_page_meta
        page = self.state.current_page
        self.conn.notify(meta.label[:18], self.state.focus_label()[:18])
        print(f'Page -> {meta.name} ({page.label})')

    def _switch_focus(self, focus_idx: int) -> None:
        meta = self.state.current_page_meta
        if not meta.focus_set or focus_idx >= len(meta.focus_set):
            return
        if focus_idx == self.state.focus_idx:
            return
        self.state.focus_idx = focus_idx
        self._build_widgets()
        self._repaint_all()
        page = self.state.current_page
        self.conn.notify(meta.label[:18], page.label[:18])
        print(f'Focus -> {meta.focus_set[focus_idx]}')


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def run(pages: Iterable[Page], output_port: str = 'iPad') -> int:
    """Open the InControl + output ports and run the event loop until Ctrl-C."""
    pages = list(pages)
    print('Opening SL MkIII InControl ...')
    with InControlConnection() as conn:
        print(f'Opening output port: {output_port!r} ...')
        try:
            output = mido.open_output(output_port)
        except Exception as e:
            print(f'ERROR opening output port: {e}')
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
            output.close()
    return 0
