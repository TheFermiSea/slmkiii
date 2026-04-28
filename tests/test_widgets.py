"""Tests for slmkiii.widgets — KnobBank, FaderBank, PadDrumKit (c08)."""

from __future__ import annotations

import unittest
from dataclasses import dataclass, field

from slmkiii.params import Parameter, SelectedFocusProvider, StaticParameterProvider
from slmkiii.sysex import Color
from slmkiii.widgets import (
    FaderBank,
    KnobBank,
    PadDrumKit,
    WidgetEvent,
)


# ---------------------------------------------------------------------------
# Test fakes
# ---------------------------------------------------------------------------
@dataclass
class FakeSink:
    cc: list = field(default_factory=list)
    note_on: list = field(default_factory=list)
    note_off: list = field(default_factory=list)

    def send_cc(self, channel, cc, value):
        self.cc.append((channel, cc, value))

    def send_note_on(self, channel, note, velocity):
        self.note_on.append((channel, note, velocity))

    def send_note_off(self, channel, note):
        self.note_off.append((channel, note))


@dataclass
class FakeFrame:
    text_calls: list = field(default_factory=list)
    color_calls: list = field(default_factory=list)
    value_calls: list = field(default_factory=list)

    def set_text(self, col, field_idx, text):
        self.text_calls.append((col, field_idx, text))

    def set_color(self, col, obj_idx, color):
        self.color_calls.append((col, obj_idx, color))

    def set_value(self, col, field_idx, value):
        self.value_calls.append((col, field_idx, value))


def _params(*names_with_cc):
    return [Parameter(name=n, cc=cc, channel=1) for n, cc in names_with_cc]


# ---------------------------------------------------------------------------
# KnobBank
# ---------------------------------------------------------------------------
class TestKnobBank(unittest.TestCase):
    def test_render_emits_cells_per_param(self):
        params = _params(("Cutoff", 20), ("Reso", 21), ("Decay", 22), ("Mix", 23))
        provider = StaticParameterProvider(params)
        kb = KnobBank(provider)
        sink, frame = FakeSink(), FakeFrame()
        kb.bind(sink, frame)
        kb.render(frame)
        self.assertEqual(len(frame.text_calls), 4)
        self.assertEqual(frame.text_calls[0], (0, 0, "Cutoff"))
        self.assertEqual(frame.text_calls[3], (3, 0, "Mix"))
        self.assertEqual(len(frame.color_calls), 4)
        self.assertEqual(frame.color_calls[0], (0, 0, int(Color.CYAN)))

    def test_knob_event_sends_cc_and_updates_value(self):
        params = _params(("A", 20))
        provider = StaticParameterProvider(params)
        kb = KnobBank(provider)
        sink, frame = FakeSink(), FakeFrame()
        kb.bind(sink, frame)
        params[0].value = 64

        # Pre-render so the param observer is wired
        kb.render(frame)
        frame.value_calls.clear()

        ev = WidgetEvent(kind="knob_delta", index=0, value=3, raw_channel=16, raw_cc=0x15)
        consumed = kb.on_event(ev)
        self.assertTrue(consumed)
        self.assertEqual(params[0].value, 67)
        self.assertEqual(sink.cc, [(1, 20, 67)])
        # Per-cell observer fired
        self.assertEqual(frame.value_calls, [(0, 0, 67)])

    def test_event_outside_region_passes_through(self):
        provider = StaticParameterProvider(_params(("A", 20)))
        kb = KnobBank(provider)
        kb.bind(FakeSink(), FakeFrame())
        ev = WidgetEvent(kind="knob_delta", index=5, value=1)
        self.assertFalse(kb.on_event(ev))

    def test_wrong_kind_passes_through(self):
        provider = StaticParameterProvider(_params(("A", 20)))
        kb = KnobBank(provider)
        kb.bind(FakeSink(), FakeFrame())
        self.assertFalse(kb.on_event(WidgetEvent(kind="fader", index=0, value=64)))
        self.assertFalse(kb.on_event(WidgetEvent(kind="pad", index=0, value=80)))

    def test_clamps_to_param_range(self):
        params = [Parameter(name="X", cc=20, channel=1, min_value=10, max_value=20)]
        provider = StaticParameterProvider(params)
        kb = KnobBank(provider)
        kb.bind(FakeSink(), FakeFrame())
        params[0].value = 18
        kb.on_event(WidgetEvent(kind="knob_delta", index=0, value=10))
        self.assertEqual(params[0].value, 20)
        kb.on_event(WidgetEvent(kind="knob_delta", index=0, value=-100))
        self.assertEqual(params[0].value, 10)

    def test_provider_change_rerenders(self):
        a = _params(("AlphaA", 20), ("AlphaB", 21), ("AlphaC", 22), ("AlphaD", 23))
        b = _params(("BetaA", 30), ("BetaB", 31), ("BetaC", 32), ("BetaD", 33))
        provider = SelectedFocusProvider([a, b])
        kb = KnobBank(provider)
        sink, frame = FakeSink(), FakeFrame()
        kb.bind(sink, frame)
        kb.render(frame)
        frame.text_calls.clear()
        provider.set_focus(1)
        # provider observer fired and re-rendered with beta names
        names = [t[2] for t in frame.text_calls]
        self.assertEqual(names, ["BetaA", "BetaB", "BetaC", "BetaD"])


# ---------------------------------------------------------------------------
# FaderBank
# ---------------------------------------------------------------------------
class TestFaderBank(unittest.TestCase):
    def test_fader_sends_absolute(self):
        provider = StaticParameterProvider(_params(("Vol", 7)))
        fb = FaderBank(provider)
        sink, frame = FakeSink(), FakeFrame()
        fb.bind(sink, frame)
        fb.on_event(WidgetEvent(kind="fader", index=0, value=100))
        self.assertEqual(sink.cc, [(1, 7, 100)])
        self.assertEqual(provider.get(0).value, 100)

    def test_default_column_offset_is_4(self):
        provider = StaticParameterProvider(_params(("Vol", 7)))
        fb = FaderBank(provider)
        frame = FakeFrame()
        fb.bind(FakeSink(), frame)
        fb.render(frame)
        # text/value/color all at column 4
        self.assertEqual(frame.text_calls[0][0], 4)
        self.assertEqual(frame.value_calls[0][0], 4)

    def test_wrong_kind_passes_through(self):
        provider = StaticParameterProvider(_params(("Vol", 7)))
        fb = FaderBank(provider)
        fb.bind(FakeSink(), FakeFrame())
        self.assertFalse(fb.on_event(WidgetEvent(kind="knob_delta", index=0, value=1)))


# ---------------------------------------------------------------------------
# PadDrumKit
# ---------------------------------------------------------------------------
class TestPadDrumKit(unittest.TestCase):
    def _build(self, **kw):
        led_calls = []

        def led_set(idx, color):
            led_calls.append((idx, color))

        kit = PadDrumKit(**kw)
        sink = FakeSink()
        kit.bind(sink, FakeFrame(), led_set=led_set)
        return kit, sink, led_calls

    def test_press_sends_note_on_and_lights_active(self):
        kit, sink, leds = self._build()
        kit.on_event(WidgetEvent(kind="pad", index=3, value=85))
        self.assertEqual(sink.note_on, [(10, 39, 85)])  # base 36 + 3
        # Last LED call for the pressed pad is the active color
        self.assertTrue(any(c == int(Color.WHITE) for _, c in leds))

    def test_release_sends_note_off_and_returns_to_rest(self):
        kit, sink, leds = self._build()
        kit.on_event(WidgetEvent(kind="pad", index=0, value=0))
        self.assertEqual(sink.note_off, [(10, 36)])

    def test_fixed_velocity_overrides_input(self):
        kit, sink, _ = self._build(fixed_velocity=100)
        kit.on_event(WidgetEvent(kind="pad", index=0, value=42))
        self.assertEqual(sink.note_on, [(10, 36, 100)])

    def test_render_paints_all_pads_rest_color(self):
        kit, _, leds = self._build(num_pads=8)
        kit.render(FakeFrame())
        self.assertEqual(len(leds), 8)
        self.assertTrue(all(c == int(Color.BLUE) for _, c in leds))

    def test_pad_outside_range_passes_through(self):
        kit, _, _ = self._build(num_pads=8)
        ev = WidgetEvent(kind="pad", index=10, value=80)
        self.assertFalse(kit.on_event(ev))

    def test_wrong_kind_passes_through(self):
        kit, _, _ = self._build()
        self.assertFalse(kit.on_event(WidgetEvent(kind="knob_delta", index=0, value=1)))


if __name__ == "__main__":
    unittest.main()
