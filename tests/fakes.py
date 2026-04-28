"""Shared test doubles for widget and runtime tests."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class FakeSink:
    """Captures CC and note events for assertions."""
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
    """Captures display set_text/set_color/set_value calls for assertions."""
    text_calls: list = field(default_factory=list)
    color_calls: list = field(default_factory=list)
    value_calls: list = field(default_factory=list)

    def set_text(self, col, field_idx, text):
        self.text_calls.append((col, field_idx, text))

    def set_color(self, col, obj_idx, color):
        self.color_calls.append((col, obj_idx, color))

    def set_value(self, col, field_idx, value):
        self.value_calls.append((col, field_idx, value))
