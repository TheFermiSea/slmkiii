"""IncDec — increment/decrement button pair. Targets page, focus, or a
Parameter value. on_change(new_value) fires after each press."""

from __future__ import annotations

from collections.abc import Callable

from slmkiii.params import Parameter
from slmkiii.widgets.base import Widget, WidgetEvent, WidgetRegion


class IncDec(Widget):
    def __init__(self,
                 *,
                 first_slot: int = 0,
                 wrap: bool = False,
                 lo: int = 0,
                 hi: int = 7,
                 step: int = 1,
                 binding: Parameter | None = None,
                 on_change: Callable[[int], None] | None = None):
        self.region = WidgetRegion(button_slots=range(first_slot, first_slot + 2))
        self._first_slot = first_slot
        self._wrap = wrap
        self._lo = lo
        self._hi = hi
        self._step = step
        self._binding = binding
        self._on_change = on_change
        self._value = lo if binding is None else binding.value

    @property
    def value(self) -> int:
        return self._binding.value if self._binding is not None else self._value

    def render(self, frame) -> None:
        # No on-screen rendering by default; can be extended
        pass

    def _set(self, new_value: int) -> None:
        if self._wrap:
            span = self._hi - self._lo + 1
            new_value = self._lo + ((new_value - self._lo) % span)
        else:
            new_value = max(self._lo, min(self._hi, new_value))
        if self._binding is not None:
            self._binding.value = new_value
        self._value = new_value
        if self._on_change is not None:
            self._on_change(new_value)

    def on_event(self, event: WidgetEvent) -> bool:
        if event.kind != "button" or not self.claims(event):
            return False
        if event.value != 127:
            return True
        widget_idx = event.index - self._first_slot
        cur = self.value
        if widget_idx == 0:
            self._set(cur - self._step)
        elif widget_idx == 1:
            self._set(cur + self._step)
        else:
            return False
        return True
