"""Tests for slmkiii.widgets — RadioGroup, IncDec, StepGrid (c09)."""

from __future__ import annotations

import unittest

from slmkiii.params import Parameter
from slmkiii.sysex import Color
from slmkiii.widgets import IncDec, RadioGroup, StepGrid, WidgetEvent
from tests.fakes import FakeFrame, FakeSink


# ---------------------------------------------------------------------------
class TestRadioGroup(unittest.TestCase):
    def test_initial_render_lights_all(self):
        leds = []
        rg = RadioGroup(count=4)
        rg.bind(FakeSink(), FakeFrame(), led_set=lambda i, c: leds.append((i, c)))
        rg.render(FakeFrame())
        self.assertEqual(len(leds), 4)
        # First button is selected by default
        self.assertEqual(leds[0][1], int(Color.WHITE))
        self.assertEqual(leds[1][1], int(Color.DIM_WHITE))

    def test_press_changes_selection_and_fires_callback(self):
        seen = []
        rg = RadioGroup(count=4, on_select=lambda i: seen.append(i))
        rg.bind(FakeSink(), FakeFrame(), led_set=lambda *_: None)
        rg.on_event(WidgetEvent(kind="button", index=2, value=127))
        self.assertEqual(rg.selected, 2)
        self.assertEqual(seen, [2])

    def test_press_same_button_is_noop(self):
        seen = []
        rg = RadioGroup(count=4, on_select=lambda i: seen.append(i))
        rg.bind(FakeSink(), FakeFrame(), led_set=lambda *_: None)
        rg.on_event(WidgetEvent(kind="button", index=0, value=127))   # already selected
        self.assertEqual(seen, [])

    def test_release_consumed_but_no_action(self):
        rg = RadioGroup(count=4)
        rg.bind(FakeSink(), FakeFrame(), led_set=lambda *_: None)
        consumed = rg.on_event(WidgetEvent(kind="button", index=2, value=0))
        self.assertTrue(consumed)
        self.assertEqual(rg.selected, 0)

    def test_wrong_kind_passes_through(self):
        rg = RadioGroup(count=4)
        rg.bind(FakeSink(), FakeFrame(), led_set=lambda *_: None)
        self.assertFalse(rg.on_event(WidgetEvent(kind="knob_delta", index=0, value=1)))

    def test_count_validation(self):
        with self.assertRaises(ValueError):
            RadioGroup(count=1)
        with self.assertRaises(ValueError):
            RadioGroup(count=20)


# ---------------------------------------------------------------------------
class TestIncDec(unittest.TestCase):
    def test_default_target_no_wrap(self):
        seen = []
        w = IncDec(lo=0, hi=7, on_change=lambda v: seen.append(v))
        w.bind(FakeSink(), FakeFrame())
        # idx 1 = increment
        w.on_event(WidgetEvent(kind="button", index=1, value=127))
        self.assertEqual(seen, [1])
        w.on_event(WidgetEvent(kind="button", index=1, value=127))
        self.assertEqual(seen, [1, 2])
        # idx 0 = decrement
        w.on_event(WidgetEvent(kind="button", index=0, value=127))
        self.assertEqual(seen, [1, 2, 1])

    def test_clamps_to_range(self):
        seen = []
        w = IncDec(lo=0, hi=2, on_change=lambda v: seen.append(v))
        w.bind(FakeSink(), FakeFrame())
        # increment past hi clamps
        for _ in range(5):
            w.on_event(WidgetEvent(kind="button", index=1, value=127))
        self.assertEqual(seen[-1], 2)
        # decrement past lo clamps
        for _ in range(5):
            w.on_event(WidgetEvent(kind="button", index=0, value=127))
        self.assertEqual(seen[-1], 0)

    def test_wrap_mode(self):
        seen = []
        w = IncDec(lo=0, hi=2, wrap=True, on_change=lambda v: seen.append(v))
        w.bind(FakeSink(), FakeFrame())
        for _ in range(4):
            w.on_event(WidgetEvent(kind="button", index=1, value=127))
        self.assertEqual(seen, [1, 2, 0, 1])  # wrapped

    def test_value_target_mutates_parameter(self):
        param = Parameter(name="X", cc=20, channel=1, _value=10, min_value=0, max_value=20)
        w = IncDec(lo=0, hi=20, binding=param)
        w.bind(FakeSink(), FakeFrame())
        w.on_event(WidgetEvent(kind="button", index=1, value=127))
        self.assertEqual(param.value, 11)

    def test_release_consumed_no_action(self):
        seen = []
        w = IncDec(on_change=lambda v: seen.append(v))
        w.bind(FakeSink(), FakeFrame())
        w.on_event(WidgetEvent(kind="button", index=1, value=0))
        self.assertEqual(seen, [])


# ---------------------------------------------------------------------------
class TestStepGrid(unittest.TestCase):
    def _voices(self, n=2):
        return [Parameter(name=f"V{i}", cc=36 + i, channel=10, _value=100) for i in range(n)]

    def test_validation(self):
        with self.assertRaises(ValueError):
            StepGrid([], steps=8)
        with self.assertRaises(ValueError):
            StepGrid(self._voices(1), steps=1)
        with self.assertRaises(ValueError):
            StepGrid(self._voices(1) * 3, steps=8)  # 3 rows -> reject

    def test_tap_toggles_step(self):
        grid = StepGrid(self._voices(1), steps=8)
        leds = []
        grid.bind(FakeSink(), FakeFrame(), led_set=lambda i, c: leds.append((i, c)))
        # Tap pad 3
        grid.on_event(WidgetEvent(kind="pad", index=3, value=80))
        self.assertEqual(grid.state[0][3], True)
        grid.on_event(WidgetEvent(kind="pad", index=3, value=80))
        self.assertEqual(grid.state[0][3], False)

    def test_step_fires_active_voices(self):
        voices = self._voices(2)
        grid = StepGrid(voices, steps=8)
        sink = FakeSink()
        grid.bind(sink, FakeFrame(), led_set=lambda *_: None)
        # Activate row 0 step 0, row 1 step 1
        grid.on_event(WidgetEvent(kind="pad", index=0, value=80))     # row 0 step 0
        grid.on_event(WidgetEvent(kind="pad", index=8 + 1, value=80))  # row 1 step 1
        # Step at beat 0
        grid.step(0)
        self.assertEqual(sink.note_on, [(10, 36, 100)])
        # Step at beat 1
        sink.note_on.clear()
        grid.step(1)
        self.assertEqual(sink.note_on, [(10, 37, 100)])

    def test_release_consumed_but_no_toggle(self):
        grid = StepGrid(self._voices(1), steps=8)
        grid.bind(FakeSink(), FakeFrame(), led_set=lambda *_: None)
        consumed = grid.on_event(WidgetEvent(kind="pad", index=0, value=0))
        self.assertTrue(consumed)
        self.assertEqual(grid.state[0][0], False)

    def test_wrong_kind_passes_through(self):
        grid = StepGrid(self._voices(1), steps=8)
        grid.bind(FakeSink(), FakeFrame(), led_set=lambda *_: None)
        self.assertFalse(grid.on_event(WidgetEvent(kind="knob_delta", index=0, value=1)))


if __name__ == "__main__":
    unittest.main()
