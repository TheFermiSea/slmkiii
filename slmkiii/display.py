"""Frame-coherent screen renderer with per-cell dirty caching.

Mutate cells via set_text/set_color/set_value; flush() emits only the
SysEx for cells that actually changed since the last flush.

Geometry: 9 columns (0-7 knob screens, 8 = center) x 4 rows (text fields
0..3) x per-cell text/color/value. Layout (KNOB/BOX/EMPTY) tracked
separately; changing layout invalidates the entire frame (the device
clears its display when layout changes).
"""
from __future__ import annotations

from typing import Protocol


class _SysexSink(Protocol):
    def set_layout(self, layout: int) -> None: ...
    def set_text(self, column: int, field_index: int, text: str) -> None: ...
    def set_color(self, column: int, obj_index: int, color: int) -> None: ...
    def set_value(self, column: int, field_index: int, value: int) -> None: ...
    def set_screen_properties(self, column: int, properties: list) -> None: ...


_NUM_COLS = 9
_NUM_FIELDS = 4


class DisplayFrame:
    def __init__(self, sink: _SysexSink) -> None:
        self._sink = sink
        self._layout: int | None = None
        self._text: list[list[str | None]] = [
            [None] * _NUM_FIELDS for _ in range(_NUM_COLS)
        ]
        self._color: list[list[int | None]] = [
            [None] * _NUM_FIELDS for _ in range(_NUM_COLS)
        ]
        self._value: list[list[int | None]] = [
            [None] * _NUM_FIELDS for _ in range(_NUM_COLS)
        ]
        self._dirty_text: set[tuple[int, int]] = set()
        self._dirty_color: set[tuple[int, int]] = set()
        self._dirty_value: set[tuple[int, int]] = set()
        self._stats = {
            "text": 0,
            "color": 0,
            "value": 0,
            "skipped": 0,
            "flushes": 0,
        }

    @property
    def stats(self) -> dict[str, int]:
        return dict(self._stats)

    def reset_stats(self) -> None:
        for k in self._stats:
            self._stats[k] = 0

    def set_layout(self, layout: int) -> None:
        if layout == self._layout:
            return
        self._layout = layout
        self._sink.set_layout(layout)
        # device cleared on layout change; force re-flush of all cells
        self.invalidate()

    def invalidate(self) -> None:
        for col in range(_NUM_COLS):
            for f in range(_NUM_FIELDS):
                if self._text[col][f] is not None:
                    self._dirty_text.add((col, f))
                if self._color[col][f] is not None:
                    self._dirty_color.add((col, f))
                if self._value[col][f] is not None:
                    self._dirty_value.add((col, f))

    def set_text(self, col: int, field: int, text: str) -> None:
        # 9-char ascii limit per InControl wire format; truncate silently
        text = text[:9]
        if self._text[col][field] == text:
            self._stats["skipped"] += 1
            return
        self._text[col][field] = text
        self._dirty_text.add((col, field))

    def set_color(self, col: int, obj: int, color: int) -> None:
        if self._color[col][obj] == color:
            self._stats["skipped"] += 1
            return
        self._color[col][obj] = color
        self._dirty_color.add((col, obj))

    def set_value(self, col: int, field: int, value: int) -> None:
        if self._value[col][field] == value:
            self._stats["skipped"] += 1
            return
        self._value[col][field] = value
        self._dirty_value.add((col, field))

    def flush(self) -> dict[str, int]:
        """Emit dirty cells. Returns per-flush counts."""
        sent = {"text": 0, "color": 0, "value": 0}
        for (col, field) in sorted(self._dirty_text):
            self._sink.set_text(col, field, self._text[col][field])
            sent["text"] += 1
            self._stats["text"] += 1
        for (col, obj) in sorted(self._dirty_color):
            self._sink.set_color(col, obj, self._color[col][obj])
            sent["color"] += 1
            self._stats["color"] += 1
        for (col, field) in sorted(self._dirty_value):
            self._sink.set_value(col, field, self._value[col][field])
            sent["value"] += 1
            self._stats["value"] += 1
        self._dirty_text.clear()
        self._dirty_color.clear()
        self._dirty_value.clear()
        self._stats["flushes"] += 1
        return sent
