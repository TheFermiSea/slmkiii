"""Tests for slmkiii.display.DisplayFrame: per-cell dirty caching."""
from __future__ import annotations

import unittest

from slmkiii.display import DisplayFrame
from slmkiii.sysex import Color, Layout


class FakeSink:
    """Records every InControl-shaped sink method invocation."""

    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def set_layout(self, layout: int) -> None:
        self.calls.append(("layout", layout))

    def set_text(self, column: int, field_index: int, text: str) -> None:
        self.calls.append(("text", column, field_index, text))

    def set_color(self, column: int, obj_index: int, color: int) -> None:
        self.calls.append(("color", column, obj_index, color))

    def set_value(self, column: int, field_index: int, value: int) -> None:
        self.calls.append(("value", column, field_index, value))

    def set_screen_properties(self, column: int, properties: list) -> None:
        self.calls.append(("props", column, list(properties)))

    def kinds(self) -> list[str]:
        return [c[0] for c in self.calls]


class TestDisplayFrame(unittest.TestCase):
    def test_empty_flush_emits_nothing(self) -> None:
        sink = FakeSink()
        frame = DisplayFrame(sink)
        sent = frame.flush()
        self.assertEqual(sent, {"text": 0, "color": 0, "value": 0})
        self.assertEqual(sink.calls, [])
        self.assertEqual(frame.stats["flushes"], 1)

    def test_set_text_then_repeat_skips(self) -> None:
        sink = FakeSink()
        frame = DisplayFrame(sink)
        frame.set_text(0, 0, "Cutoff")
        sent = frame.flush()
        self.assertEqual(sent["text"], 1)
        self.assertEqual(sink.calls, [("text", 0, 0, "Cutoff")])

        # second identical write is a skip
        frame.set_text(0, 0, "Cutoff")
        self.assertEqual(frame.stats["skipped"], 1)
        sink.calls.clear()
        sent = frame.flush()
        self.assertEqual(sent, {"text": 0, "color": 0, "value": 0})
        self.assertEqual(sink.calls, [])

    def test_layout_change_invalidates_all_cells(self) -> None:
        sink = FakeSink()
        frame = DisplayFrame(sink)
        frame.set_layout(int(Layout.KNOB))
        frame.set_text(0, 0, "A")
        frame.set_text(1, 1, "B")
        frame.set_color(2, 0, int(Color.RED))
        frame.set_value(3, 2, 64)
        frame.flush()

        sink.calls.clear()
        # Switching layout -> device cleared; everything re-flushes
        frame.set_layout(int(Layout.BOX))
        sent = frame.flush()
        self.assertEqual(sent["text"], 2)
        self.assertEqual(sent["color"], 1)
        self.assertEqual(sent["value"], 1)

        # First call should be the layout change
        self.assertEqual(sink.calls[0], ("layout", int(Layout.BOX)))
        kinds = [c[0] for c in sink.calls[1:]]
        self.assertEqual(kinds.count("text"), 2)
        self.assertEqual(kinds.count("color"), 1)
        self.assertEqual(kinds.count("value"), 1)

    def test_layout_no_op_when_unchanged(self) -> None:
        sink = FakeSink()
        frame = DisplayFrame(sink)
        frame.set_layout(int(Layout.KNOB))
        sink.calls.clear()
        frame.set_layout(int(Layout.KNOB))  # same — no-op
        self.assertEqual(sink.calls, [])

    def test_flush_order_text_color_value_each_sorted(self) -> None:
        sink = FakeSink()
        frame = DisplayFrame(sink)
        # Mix in non-sorted insertion order
        frame.set_value(2, 1, 10)
        frame.set_color(0, 0, 5)
        frame.set_text(1, 2, "x")
        frame.set_text(0, 0, "a")
        frame.set_color(2, 1, 7)
        frame.set_value(0, 0, 1)
        frame.flush()

        kinds = sink.kinds()
        # All texts come before all colors come before all values
        first_color = kinds.index("color")
        first_value = kinds.index("value")
        self.assertTrue(all(k == "text" for k in kinds[:first_color]))
        self.assertTrue(
            all(k == "color" for k in kinds[first_color:first_value])
        )
        self.assertTrue(all(k == "value" for k in kinds[first_value:]))

        # Each group ordered by (col, field/obj)
        text_calls = [c for c in sink.calls if c[0] == "text"]
        self.assertEqual(
            text_calls, [("text", 0, 0, "a"), ("text", 1, 2, "x")]
        )
        color_calls = [c for c in sink.calls if c[0] == "color"]
        self.assertEqual(
            color_calls, [("color", 0, 0, 5), ("color", 2, 1, 7)]
        )
        value_calls = [c for c in sink.calls if c[0] == "value"]
        self.assertEqual(
            value_calls, [("value", 0, 0, 1), ("value", 2, 1, 10)]
        )

    def test_stats_track_across_flushes(self) -> None:
        sink = FakeSink()
        frame = DisplayFrame(sink)
        frame.set_text(0, 0, "a")
        frame.set_color(0, 0, 1)
        frame.set_value(0, 0, 2)
        frame.flush()

        # second flush — no changes
        frame.flush()

        # third flush — one new value, one repeat (skip)
        frame.set_value(0, 0, 2)  # skip
        frame.set_value(1, 0, 3)  # new
        frame.flush()

        s = frame.stats
        self.assertEqual(s["text"], 1)
        self.assertEqual(s["color"], 1)
        self.assertEqual(s["value"], 2)
        self.assertEqual(s["skipped"], 1)
        self.assertEqual(s["flushes"], 3)

        frame.reset_stats()
        self.assertEqual(
            frame.stats,
            {"text": 0, "color": 0, "value": 0, "skipped": 0, "flushes": 0},
        )

    def test_text_truncated_to_nine_chars(self) -> None:
        sink = FakeSink()
        frame = DisplayFrame(sink)
        frame.set_text(0, 0, "Cutoff_long_name")
        frame.flush()
        self.assertEqual(sink.calls, [("text", 0, 0, "Cutoff_lo")])
        self.assertEqual(len("Cutoff_lo"), 9)

        # subsequent write of the same truncated value is a skip
        sink.calls.clear()
        frame.set_text(0, 0, "Cutoff_long_name_extra")
        self.assertEqual(frame.stats["skipped"], 1)
        sent = frame.flush()
        self.assertEqual(sent["text"], 0)
        self.assertEqual(sink.calls, [])

    def test_eight_page_repaint_skips_text_when_labels_unchanged(self) -> None:
        """Two page changes with same labels but different values: no text resent."""
        sink = FakeSink()
        frame = DisplayFrame(sink)
        labels = [f"k{i}" for i in range(8)]

        # Page 1: paint labels + colors + values
        for col in range(8):
            frame.set_text(col, 0, labels[col])
            frame.set_color(col, 0, int(Color.GREEN))
            frame.set_value(col, 0, 10 * col)
        frame.flush()

        # Page 2: same labels (same names), different colors/values
        sink.calls.clear()
        for col in range(8):
            frame.set_text(col, 0, labels[col])  # unchanged -> skip
            frame.set_color(col, 0, int(Color.BLUE))
            frame.set_value(col, 0, 20 * col + 1)
        sent = frame.flush()

        self.assertEqual(sent["text"], 0)
        self.assertEqual(sent["color"], 8)
        self.assertEqual(sent["value"], 8)
        text_calls = [c for c in sink.calls if c[0] == "text"]
        self.assertEqual(text_calls, [])


if __name__ == "__main__":
    unittest.main()
