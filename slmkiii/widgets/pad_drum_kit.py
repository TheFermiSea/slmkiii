"""PadDrumKit — 16 pads triggering MIDI notes. Velocity-sensitive by default.
LEDs swap rest/active colors on press/release.
"""

from __future__ import annotations

from slmkiii.incontrol import LED
from slmkiii.sysex import Color
from slmkiii.widgets.base import Widget, WidgetEvent, WidgetRegion


class PadDrumKit(Widget):
    def __init__(self,
                 base_note: int = 36,
                 channel: int = 10,
                 *,
                 num_pads: int = 16,
                 fixed_velocity: int | None = None,
                 rest_color: int = int(Color.BLUE),
                 active_color: int = int(Color.WHITE)):
        self.region = WidgetRegion(pad_slots=range(0, num_pads))
        self._base_note = base_note
        self._channel = channel
        self._num_pads = num_pads
        self._fixed_velocity = fixed_velocity
        self._rest_color = int(rest_color)
        self._active_color = int(active_color)

    def render(self, frame) -> None:
        if self._led_set is None:
            return
        for i in range(self._num_pads):
            self._led_set(LED.PAD_1.value + i, self._rest_color)

    def on_event(self, event: WidgetEvent) -> bool:
        if event.kind != "pad" or not self.claims(event):
            return False
        if event.index >= self._num_pads:
            return False
        note = self._base_note + event.index
        velocity = (self._fixed_velocity
                    if self._fixed_velocity is not None
                    else event.value)
        if velocity > 0:
            if self._sink is not None:
                self._sink.send_note_on(self._channel, note, velocity)
            if self._led_set is not None:
                self._led_set(LED.PAD_1.value + event.index, self._active_color)
        else:
            if self._sink is not None:
                self._sink.send_note_off(self._channel, note)
            if self._led_set is not None:
                self._led_set(LED.PAD_1.value + event.index, self._rest_color)
        return True
