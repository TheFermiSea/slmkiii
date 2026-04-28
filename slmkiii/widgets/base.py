"""Widget abstraction: a contiguous region of SL MkIII slots with its own
renderer and event handler. Composes knobs/faders/pads into self-contained
units (KnobBank, PadDrumKit, etc.) modeled on r_cycle's LP_GUI widgets and
DrivenByMoss View hierarchy.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal, Protocol


# Discriminator for WidgetEvent.kind. Centralises the spelling of every
# event class so subclasses can compare against this Literal alias instead
# of bare string literals.
EventKind = Literal["knob_delta", "fader", "pad", "button"]


@dataclass(frozen=True)
class WidgetEvent:
    """Input event delivered to widgets by the controller event router."""
    kind: EventKind     # "knob_delta" | "fader" | "pad" | "button"
    index: int          # slot index within the widget's region
    value: int          # delta for knob_delta, abs for fader, vel for pad, 127/0 for button
    raw_channel: int = 0    # 1-indexed MIDI channel of source event
    raw_cc: int = 0         # CC or note number


class MidiSink(Protocol):
    def send_cc(self, channel: int, cc: int, value: int) -> None: ...
    def send_note_on(self, channel: int, note: int, velocity: int) -> None: ...
    def send_note_off(self, channel: int, note: int) -> None: ...


LedSetter = Callable[[int, int], None]   # (led_index, color) -> None


@dataclass
class WidgetRegion:
    """The hardware slots a widget occupies. All ranges are inclusive starts,
    exclusive stops (Python range semantics)."""
    knob_slots: range = field(default_factory=lambda: range(0, 0))
    fader_slots: range = field(default_factory=lambda: range(0, 0))
    pad_slots: range = field(default_factory=lambda: range(0, 0))
    button_slots: range = field(default_factory=lambda: range(0, 0))


class Widget:
    """Base class. Concrete widgets implement render() + on_event()."""

    region: WidgetRegion = WidgetRegion()
    _sink: MidiSink | None = None
    _frame: object | None = None
    _led_set: LedSetter | None = None

    def bind(self, sink: MidiSink, frame, led_set: LedSetter | None = None) -> None:
        """Wire output sinks. Called once per page activation."""
        self._sink = sink
        self._frame = frame
        self._led_set = led_set

    def render(self, frame) -> None:
        raise NotImplementedError

    def on_event(self, event: WidgetEvent) -> bool:
        """Return True if the event was consumed (no further widgets see it)."""
        raise NotImplementedError

    def claims(self, event: WidgetEvent) -> bool:
        if event.kind == "knob_delta":
            return event.index in self.region.knob_slots
        if event.kind == "fader":
            return event.index in self.region.fader_slots
        if event.kind == "pad":
            return event.index in self.region.pad_slots
        if event.kind == "button":
            return event.index in self.region.button_slots
        return False
