"""Tests for the c10 widget-based Controller runtime."""

from __future__ import annotations

import unittest
from dataclasses import dataclass, field

from slmkiii.controller.config import Binding, Page
from slmkiii.controller.runtime import (
    Controller,
    ControllerState,
    _LedRenderer,
    _MidoMidiSink,
    _detect_pad_kit,
    value_to_fader_color,
)
from slmkiii.params import Parameter
from slmkiii.sysex import Color


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------
@dataclass
class FakeConn:
    """Stand-in for InControlConnection — captures everything."""
    leds: list = field(default_factory=list)        # (led_idx, color)
    layouts: list = field(default_factory=list)
    text_calls: list = field(default_factory=list)
    color_calls: list = field(default_factory=list)
    value_calls: list = field(default_factory=list)
    notifications: list = field(default_factory=list)

    def set_led(self, led, color):
        self.leds.append((led, color))

    def set_layout(self, layout):
        self.layouts.append(layout)

    def set_text(self, col, field, text):
        self.text_calls.append((col, field, text))

    def set_color(self, col, obj, color):
        self.color_calls.append((col, obj, color))

    def set_value(self, col, field, value):
        self.value_calls.append((col, field, value))

    def set_screen_properties(self, col, props):  # unused by DisplayFrame
        pass

    def notify(self, line1, line2=""):
        self.notifications.append((line1, line2))

    def poll_input(self):
        return []

    def clear_all_leds(self):
        pass


class FakeMidoOutput:
    def __init__(self):
        self.sent: list = []

    def send(self, msg):
        self.sent.append(msg)

    def close(self):
        pass


def _knob_binding(label, cc, channel=1):
    return Binding(label=label, cc=cc, channel=channel,
                   param_path=f"path_{label}")


def _pad_bindings(base_note=36, channel=10, count=16):
    return [
        Binding(label=f"P{i}", cc=base_note + i, channel=channel,
                param_path=f"trig_{i}")
        for i in range(count)
    ]


# ---------------------------------------------------------------------------
class TestValueToFaderColor(unittest.TestCase):
    def test_thresholds(self):
        self.assertEqual(value_to_fader_color(0), int(Color.OFF))
        self.assertEqual(value_to_fader_color(15), int(Color.OFF))
        self.assertEqual(value_to_fader_color(16), int(Color.DIM_GREEN))
        self.assertEqual(value_to_fader_color(48), int(Color.GREEN))
        self.assertEqual(value_to_fader_color(96), int(Color.YELLOW))
        self.assertEqual(value_to_fader_color(127), int(Color.RED))


class TestDetectPadKit(unittest.TestCase):
    def test_consecutive_pads_detected(self):
        pads = _pad_bindings(base_note=36, channel=10, count=8)
        self.assertEqual(_detect_pad_kit(pads), (36, 10))

    def test_non_consecutive_returns_none(self):
        pads = [
            Binding("a", cc=36, channel=10),
            Binding("b", cc=40, channel=10),
        ]
        self.assertIsNone(_detect_pad_kit(pads))

    def test_mixed_channels_returns_none(self):
        pads = [
            Binding("a", cc=36, channel=10),
            Binding("b", cc=37, channel=11),
        ]
        self.assertIsNone(_detect_pad_kit(pads))

    def test_empty_returns_none(self):
        self.assertIsNone(_detect_pad_kit([]))


class TestControllerStateParameterCache(unittest.TestCase):
    def setUp(self):
        self.pages = [Page(name="p1", label="P1", color=int(Color.RED))]
        self.state = ControllerState(self.pages)

    def test_same_binding_returns_same_parameter(self):
        b = _knob_binding("Cutoff", 20)
        p1 = self.state.parameter_for(b)
        p2 = self.state.parameter_for(b)
        self.assertIs(p1, p2)

    def test_different_cc_returns_different_parameter(self):
        b1 = _knob_binding("Cutoff", 20)
        b2 = _knob_binding("Reso", 21)
        self.assertIsNot(self.state.parameter_for(b1),
                         self.state.parameter_for(b2))

    def test_value_persists_across_lookups(self):
        b = _knob_binding("Cutoff", 20)
        self.state.set_value(b, 99)
        self.assertEqual(self.state.get_value(b), 99)
        # Re-lookup yields same Parameter, value unchanged
        self.assertEqual(self.state.parameter_for(b).value, 99)

    def test_clamp_via_binding_range(self):
        b = Binding("Test", cc=50, channel=1, min_val=10, max_val=120)
        # First lookup creates Parameter with min/max from binding
        self.state.set_value(b, 200)
        self.assertEqual(self.state.get_value(b), 120)
        self.state.set_value(b, -5)
        self.assertEqual(self.state.get_value(b), 10)

    def test_label_refresh_on_relookup(self):
        # Same (channel, cc) but different binding label / range
        b1 = _knob_binding("Cutoff", 20)
        b2 = Binding("CutoffX", cc=20, channel=1, min_val=0, max_val=64)
        p1 = self.state.parameter_for(b1)
        p1.value = 100   # within b1's 0..127
        # Re-lookup with new binding clamps existing value? No — the value
        # is preserved; only label/range metadata refreshes.
        p2 = self.state.parameter_for(b2)
        self.assertIs(p1, p2)
        self.assertEqual(p2.name, "CutoffX")
        self.assertEqual(p2.max_value, 64)


class TestControllerWidgetBuilding(unittest.TestCase):
    def _make_controller(self, pages):
        return Controller(FakeConn(), FakeMidoOutput(), pages)

    def test_no_widgets_for_empty_page(self):
        page = Page(name="empty", label="Empty", color=int(Color.OFF))
        c = self._make_controller([page])
        self.assertEqual(len(c._widgets), 0)

    def test_knob_widget_built_when_page_has_knobs(self):
        page = Page(
            name="k", label="K", color=int(Color.RED),
            knobs=[_knob_binding("a", 20), _knob_binding("b", 21)],
        )
        c = self._make_controller([page])
        self.assertEqual(len(c._widgets), 1)
        # The widget should be a KnobBank (claims knob events)
        from slmkiii.widgets import KnobBank, WidgetEvent
        self.assertIsInstance(c._widgets[0], KnobBank)
        self.assertTrue(c._widgets[0].claims(
            WidgetEvent(kind="knob_delta", index=0, value=1)))

    def test_pad_kit_built_for_consecutive_pads(self):
        page = Page(
            name="p", label="P", color=int(Color.RED),
            pads=_pad_bindings(base_note=36, channel=10, count=16),
        )
        c = self._make_controller([page])
        # Just the pad widget
        self.assertEqual(len(c._widgets), 1)
        from slmkiii.widgets import PadDrumKit
        self.assertIsInstance(c._widgets[0], PadDrumKit)

    def test_pad_kit_not_built_for_non_consecutive_pads(self):
        page = Page(
            name="p", label="P", color=int(Color.RED),
            pads=[
                Binding("a", cc=36, channel=10),
                Binding("b", cc=42, channel=10),
            ],
        )
        c = self._make_controller([page])
        # Pads dropped silently because non-contiguous
        self.assertEqual(len(c._widgets), 0)

    def test_full_page_yields_three_widgets(self):
        page = Page(
            name="all", label="All", color=int(Color.RED),
            knobs=[_knob_binding("k", 20)],
            faders=[_knob_binding("f", 30)],
            pads=_pad_bindings(36, 10, 8),
        )
        c = self._make_controller([page])
        self.assertEqual(len(c._widgets), 3)


class TestPageSwitchRebuildsWidgets(unittest.TestCase):
    def test_switch_page_replaces_widgets(self):
        page1 = Page(name="p1", label="P1", color=int(Color.RED),
                     knobs=[_knob_binding("a", 20)])
        page2 = Page(name="p2", label="P2", color=int(Color.GREEN),
                     faders=[_knob_binding("b", 30)])
        c = Controller(FakeConn(), FakeMidoOutput(), [page1, page2])

        widgets_before = list(c._widgets)
        from slmkiii.widgets import KnobBank, FaderBank
        self.assertIsInstance(widgets_before[0], KnobBank)

        c._switch_page(1)
        self.assertEqual(c.state.current_page_idx, 1)
        self.assertEqual(len(c._widgets), 1)
        self.assertIsInstance(c._widgets[0], FaderBank)

    def test_switch_page_preserves_parameter_values(self):
        # Same CC on both pages — value must persist via the Parameter cache
        page1 = Page(name="p1", label="P1", color=int(Color.RED),
                     knobs=[_knob_binding("a", 20)])
        page2 = Page(name="p2", label="P2", color=int(Color.GREEN),
                     knobs=[_knob_binding("a", 20)])  # SAME CC
        c = Controller(FakeConn(), FakeMidoOutput(), [page1, page2])
        c.state.set_value(page1.knobs[0], 99)
        c._switch_page(1)
        self.assertEqual(c.state.get_value(page2.knobs[0]), 99)


class TestKnobEventEndToEnd(unittest.TestCase):
    def test_knob_event_sends_cc_via_widget(self):
        page = Page(name="p", label="P", color=int(Color.RED),
                    knobs=[_knob_binding("Cutoff", 20)])
        out = FakeMidoOutput()
        c = Controller(FakeConn(), out, [page])
        # Simulate a knob event from poll_input
        c._handle_event({
            "type": "knob",
            "knob": 1,           # SL knob 1 (1-indexed)
            "delta": 5,
            "value": 5,
        })
        self.assertEqual(len(out.sent), 1)
        msg = out.sent[0]
        self.assertEqual(msg.type, "control_change")
        self.assertEqual(msg.channel, 0)    # ch1 = 0-indexed
        self.assertEqual(msg.control, 20)
        self.assertEqual(msg.value, 64 + 5)


class TestNavButtons(unittest.TestCase):
    def _setup(self):
        pages = [
            Page(name="p1", label="P1", color=int(Color.RED)),
            Page(name="p2", label="P2", color=int(Color.GREEN)),
            Page(name="p3", label="P3", color=int(Color.BLUE)),
        ]
        return Controller(FakeConn(), FakeMidoOutput(), pages)

    def test_top_row_button_selects_page(self):
        c = self._setup()
        # CC SOFT_BUTTON_2 -> page 1
        from slmkiii.incontrol import Control
        c._handle_nav_button({
            "type": "button",
            "control": Control.SOFT_BUTTON_2.value,
            "value": 127,
            "pressed": True,
        })
        self.assertEqual(c.state.current_page_idx, 1)

    def test_track_right_cycles_page(self):
        c = self._setup()
        from slmkiii.incontrol import Control
        c._handle_nav_button({
            "type": "button",
            "control": Control.TRACK_RIGHT.value,
            "value": 127,
            "pressed": True,
        })
        self.assertEqual(c.state.current_page_idx, 1)
        c._handle_nav_button({
            "type": "button",
            "control": Control.TRACK_RIGHT.value,
            "value": 127,
            "pressed": True,
        })
        self.assertEqual(c.state.current_page_idx, 2)
        # Wraps
        c._handle_nav_button({
            "type": "button",
            "control": Control.TRACK_RIGHT.value,
            "value": 127,
            "pressed": True,
        })
        self.assertEqual(c.state.current_page_idx, 0)

    def test_button_release_ignored(self):
        c = self._setup()
        from slmkiii.incontrol import Control
        c._handle_nav_button({
            "type": "button",
            "control": Control.SOFT_BUTTON_2.value,
            "value": 0,
            "pressed": False,
        })
        self.assertEqual(c.state.current_page_idx, 0)


class TestLedRendererCache(unittest.TestCase):
    def test_skip_unchanged(self):
        conn = FakeConn()
        leds = _LedRenderer(conn)
        leds.set(0x04, int(Color.RED))
        leds.set(0x04, int(Color.RED))
        leds.set(0x04, int(Color.RED))
        self.assertEqual(len(conn.leds), 1)

    def test_emits_on_change(self):
        conn = FakeConn()
        leds = _LedRenderer(conn)
        leds.set(0x04, int(Color.RED))
        leds.set(0x04, int(Color.GREEN))
        self.assertEqual(len(conn.leds), 2)


class TestMidoSinkAdapter(unittest.TestCase):
    def test_send_cc_translates_channel(self):
        out = FakeMidoOutput()
        sink = _MidoMidiSink(out)
        sink.send_cc(channel=10, cc=20, value=50)
        self.assertEqual(len(out.sent), 1)
        self.assertEqual(out.sent[0].channel, 9)   # 1-indexed -> 0-indexed
        self.assertEqual(out.sent[0].control, 20)
        self.assertEqual(out.sent[0].value, 50)

    def test_send_note_on_off(self):
        out = FakeMidoOutput()
        sink = _MidoMidiSink(out)
        sink.send_note_on(channel=10, note=36, velocity=80)
        sink.send_note_off(channel=10, note=36)
        self.assertEqual(out.sent[0].type, "note_on")
        self.assertEqual(out.sent[1].type, "note_off")
        self.assertEqual(out.sent[1].velocity, 0)


if __name__ == "__main__":
    unittest.main()
