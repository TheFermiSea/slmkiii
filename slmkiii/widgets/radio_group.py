"""RadioGroup — mutually-exclusive button bank. Used for focus/page
selection. Active button highlighted; press fires on_select(idx)."""

from __future__ import annotations

from collections.abc import Callable

from slmkiii.incontrol import LED
from slmkiii.sysex import Color
from slmkiii.widgets.base import Widget, WidgetEvent, WidgetRegion


class RadioGroup(Widget):
    def __init__(self,
                 count: int,
                 *,
                 first_slot: int = 0,
                 led_base: int = LED.SOFT_BUTTON_9.value,
                 selected_color: int = int(Color.WHITE),
                 idle_color: int = int(Color.DIM_WHITE),
                 on_select: Callable[[int], None] | None = None):
        if count < 2 or count > 16:
            raise ValueError(f"RadioGroup count must be 2-16, got {count}")
        self.region = WidgetRegion(button_slots=range(first_slot, first_slot + count))
        self._count = count
        self._first_slot = first_slot
        self._led_base = led_base
        self._selected_color = int(selected_color)
        self._idle_color = int(idle_color)
        self._on_select = on_select
        self._selected = 0

    @property
    def selected(self) -> int:
        return self._selected

    def set_selected(self, idx: int, *, fire: bool = False) -> None:
        if not (0 <= idx < self._count):
            raise IndexError(f"selected idx {idx} out of range 0..{self._count - 1}")
        if idx == self._selected:
            return
        self._selected = idx
        self._render_leds()
        if fire and self._on_select is not None:
            self._on_select(idx)

    def _render_leds(self) -> None:
        if self._led_set is None:
            return
        for i in range(self._count):
            color = self._selected_color if i == self._selected else self._idle_color
            self._led_set(self._led_base + i, color)

    def render(self, frame) -> None:
        self._render_leds()

    def on_event(self, event: WidgetEvent) -> bool:
        if event.kind != "button" or not self.claims(event):
            return False
        if event.value != 127:    # only on press
            return True
        widget_idx = event.index - self._first_slot
        if widget_idx >= self._count:
            return False
        if widget_idx != self._selected:
            self._selected = widget_idx
            self._render_leds()
            if self._on_select is not None:
                self._on_select(widget_idx)
        return True
