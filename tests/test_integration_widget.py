"""End-to-end test: Page → Widget → DisplayFrame → MidiSink round trip.

Catches wiring regressions across the abstractions added in c06–c09:
Parameter observers, DisplayFrame dirty cache, KnobBank/FaderBank rendering,
PadDrumKit triggering. Cheap insurance against silent decoupling between
the layers.
"""

from __future__ import annotations

import unittest

from slmkiii.display import DisplayFrame
from slmkiii.params import Parameter, StaticParameterProvider
from slmkiii.sysex import Color
from slmkiii.widgets import FaderBank, KnobBank, PadDrumKit, WidgetEvent
from tests.fakes import FakeSink


class _RecordingFrame:
    """DisplayFrame stand-in that captures property changes for assertions."""

    def __init__(self) -> None:
        self.text: dict[tuple[int, int], str] = {}
        self.value: dict[tuple[int, int], int] = {}
        self.color: dict[tuple[int, int], int] = {}

    def set_text(self, col, field, text):
        self.text[(col, field)] = text

    def set_value(self, col, field, val):
        self.value[(col, field)] = val

    def set_color(self, col, obj, color):
        self.color[(col, obj)] = color


class TestRoundTrip(unittest.TestCase):
    def _build_provider(self):
        return StaticParameterProvider([
            Parameter(name="Cutoff", cc=20, channel=1, _value=64),
            Parameter(name="Reso",   cc=21, channel=1, _value=32),
            Parameter(name="Decay",  cc=22, channel=1, _value=0),
            Parameter(name="Mix",    cc=23, channel=1, _value=127),
        ])

    def test_knob_event_propagates_through_layers(self):
        provider = self._build_provider()
        kb = KnobBank(provider)
        sink = FakeSink()
        frame = _RecordingFrame()
        kb.bind(sink, frame)
        kb.render(frame)

        # Initial render painted text/color/value for all 4 knobs
        self.assertEqual(frame.text[(0, 0)], "Cutoff")
        self.assertEqual(frame.value[(0, 0)], 64)
        self.assertEqual(frame.color[(0, 0)], int(Color.CYAN))
        self.assertEqual(frame.value[(3, 0)], 127)

        # Knob delta event flows: Widget.on_event -> Parameter.value setter
        # -> observer fires -> frame.set_value invoked, AND sink.send_cc
        # invoked. The Parameter's clamping is exercised too.
        kb.on_event(WidgetEvent(kind="knob_delta", index=0, value=10))
        self.assertEqual(provider.get(0).value, 74)
        self.assertEqual(sink.cc[-1], (1, 20, 74))
        self.assertEqual(frame.value[(0, 0)], 74)

        # Negative delta past 0 clamps
        kb.on_event(WidgetEvent(kind="knob_delta", index=2, value=-100))
        self.assertEqual(provider.get(2).value, 0)
        self.assertEqual(sink.cc[-1], (1, 22, 0))

        # Identical value triggers Parameter setter no-op short-circuit
        # (no extra sink.cc call, no extra frame.set_value)
        cc_count = len(sink.cc)
        kb.on_event(WidgetEvent(kind="knob_delta", index=2, value=0))
        # KnobBank's on_event always sends CC even for unchanged values
        # because the wire might have been bumped; but the Parameter.value
        # setter short-circuits the observer, so frame.value is unchanged.
        # We assert sink picked up the no-op send (the wire is canonical).
        self.assertEqual(len(sink.cc), cc_count + 1)

    def test_fader_event_uses_absolute(self):
        provider = self._build_provider()
        fb = FaderBank(provider)
        sink = FakeSink()
        frame = _RecordingFrame()
        fb.bind(sink, frame)
        fb.render(frame)

        # Fader sends absolute, not delta
        fb.on_event(WidgetEvent(kind="fader", index=1, value=99))
        self.assertEqual(provider.get(1).value, 99)
        self.assertEqual(sink.cc[-1], (1, 21, 99))
        # Default fader column_offset = 4
        self.assertEqual(frame.value[(5, 0)], 99)

    def test_pad_event_emits_note_and_lights_led(self):
        led_calls: list[tuple[int, int]] = []

        def led_set(idx, color):
            led_calls.append((idx, color))

        kit = PadDrumKit(base_note=36, channel=10)
        sink = FakeSink()
        kit.bind(sink, _RecordingFrame(), led_set=led_set)
        kit.on_event(WidgetEvent(kind="pad", index=3, value=85))
        self.assertEqual(sink.note_on[-1], (10, 39, 85))
        # LED for that pad turned on with active color
        self.assertTrue(any(c == int(Color.WHITE) for _, c in led_calls))


class TestParameterObserverFanOut(unittest.TestCase):
    """Same Parameter shared between two widgets — both must update on
    a single value change. Catches forgotten observer subscriptions."""

    def test_two_banks_sharing_parameter_both_update(self):
        param = Parameter(name="Shared", cc=50, channel=1, _value=10)
        provider1 = StaticParameterProvider([param])
        provider2 = StaticParameterProvider([param])
        sink = FakeSink()
        f1 = _RecordingFrame()
        f2 = _RecordingFrame()
        kb1 = KnobBank(provider1)
        kb2 = KnobBank(provider2)
        kb1.bind(sink, f1)
        kb2.bind(sink, f2)
        kb1.render(f1)
        kb2.render(f2)

        # Mutate the parameter directly (simulating a remote-feedback path)
        param.value = 99

        # Both KnobBanks' observers should have updated their respective frames
        self.assertEqual(f1.value[(0, 0)], 99)
        self.assertEqual(f2.value[(0, 0)], 99)


class TestDisplayFrameWithProviderChange(unittest.TestCase):
    """SelectedFocusProvider focus change must rebind observers and
    re-render KnobBank against the new focus's parameters."""

    def test_focus_change_rerenders_with_new_params(self):
        from slmkiii.params import SelectedFocusProvider

        focus_a = [Parameter(name="A1", cc=20, channel=1, _value=10)]
        focus_b = [Parameter(name="B1", cc=20, channel=1, _value=20)]
        provider = SelectedFocusProvider([focus_a, focus_b])

        kb = KnobBank(provider)
        sink = FakeSink()
        frame = _RecordingFrame()
        kb.bind(sink, frame)
        kb.render(frame)

        self.assertEqual(frame.text[(0, 0)], "A1")
        self.assertEqual(frame.value[(0, 0)], 10)

        provider.set_focus(1)
        # After focus change, observer fired and rebound; frame reflects B-focus
        self.assertEqual(frame.text[(0, 0)], "B1")
        self.assertEqual(frame.value[(0, 0)], 20)

        # Original focus_a parameter mutation should NOT update the frame any more
        focus_a[0].value = 77
        self.assertEqual(frame.value[(0, 0)], 20)  # still B's

        # B's parameter mutation DOES update
        focus_b[0].value = 99
        self.assertEqual(frame.value[(0, 0)], 99)


class TestDisplayFrameDirtyCache(unittest.TestCase):
    """Ensures the dirty cache is wired into the render path (c06)."""

    def test_unchanged_value_no_sysex(self):
        emitted: list[tuple[str, tuple]] = []

        class StubConn:
            def set_text(self, col, field, text):
                emitted.append(("text", (col, field, text)))

            def set_color(self, col, obj, color):
                emitted.append(("color", (col, obj, color)))

            def set_value(self, col, field, val):
                emitted.append(("value", (col, field, val)))

            def set_layout(self, layout):
                emitted.append(("layout", (layout,)))

        # Use the real DisplayFrame
        frame = DisplayFrame(StubConn())
        frame.set_text(0, 0, "Cutoff")
        frame.set_value(0, 0, 64)
        frame.set_color(0, 0, int(Color.CYAN))
        frame.flush()
        first_count = len(emitted)
        self.assertGreater(first_count, 0)

        # Re-emit identical state — cache short-circuits
        frame.set_text(0, 0, "Cutoff")
        frame.set_value(0, 0, 64)
        frame.set_color(0, 0, int(Color.CYAN))
        frame.flush()
        self.assertEqual(len(emitted), first_count)

        # Change one cell — single emit
        frame.set_value(0, 0, 65)
        frame.flush()
        self.assertEqual(len(emitted), first_count + 1)


if __name__ == "__main__":
    unittest.main()
