"""KnobBank — N knobs each bound to a Parameter via a ParameterProvider.
Re-binds atomically when the provider fires parameters_adjusted (focus
change). Each parameter's value-changed observer keeps its screen cell live.
"""

from __future__ import annotations

from slmkiii.params import Parameter, ParameterProvider
from slmkiii.sysex import Color
from slmkiii.widgets.base import Widget, WidgetEvent, WidgetRegion


class KnobBank(Widget):
    def __init__(self,
                 provider: ParameterProvider,
                 first_slot: int = 0,
                 *,
                 label_color: int = int(Color.CYAN),
                 column_offset: int = 0):
        n = provider.size()
        self.region = WidgetRegion(knob_slots=range(first_slot, first_slot + n))
        self._provider = provider
        self._first_slot = first_slot
        self._label_color = int(label_color)
        self._column_offset = column_offset

        self._provider.add_parameters_observer(self._on_provider_changed)
        self._wire_param_observers()

    def _wire_param_observers(self) -> None:
        for i in range(self._provider.size()):
            self._provider.get(i).add_observer(self._on_param_value)

    def _unwire_param_observers(self) -> None:
        for i in range(self._provider.size()):
            try:
                self._provider.get(i).remove_observer(self._on_param_value)
            except Exception:
                pass

    def _on_provider_changed(self) -> None:
        self._unwire_param_observers()
        self._wire_param_observers()
        if self._frame is not None:
            self.render(self._frame)

    def _on_param_value(self, param: Parameter, new_value: int) -> None:
        if self._frame is None:
            return
        idx = self._index_for_param(param)
        if idx is None:
            return
        self._frame.set_value(self._column_offset + idx, 0, new_value)

    def _index_for_param(self, p: Parameter) -> int | None:
        for i in range(self._provider.size()):
            if self._provider.get(i) is p:
                return i
        return None

    def render(self, frame) -> None:
        for i in range(self._provider.size()):
            p = self._provider.get(i)
            col = self._column_offset + i
            frame.set_text(col, 0, p.name)
            frame.set_value(col, 0, p.value)
            frame.set_color(col, 0, self._label_color)

    def on_event(self, event: WidgetEvent) -> bool:
        if event.kind != "knob_delta" or not self.claims(event):
            return False
        widget_idx = event.index - self._first_slot
        if widget_idx >= self._provider.size():
            return False
        param = self._provider.get(widget_idx)
        new_val = max(param.min_value,
                      min(param.max_value, param.value + event.value))
        param.value = new_val
        if self._sink is not None:
            self._sink.send_cc(param.channel, param.cc, param.value)
        return True
