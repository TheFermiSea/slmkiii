"""StepGrid — rows × steps toggle matrix on pads. Tap toggles step on/off
(LED color swap). step(beat_idx) advances the cursor and fires NoteOn for
active steps per voice."""

from __future__ import annotations

from slmkiii.incontrol import LED
from slmkiii.params import Parameter
from slmkiii.sysex import Color
from slmkiii.widgets.base import Widget, WidgetEvent, WidgetRegion


class StepGrid(Widget):
    def __init__(self,
                 voices: list[Parameter],
                 *,
                 steps: int = 8,
                 active_color: int = int(Color.GREEN),
                 idle_color: int = int(Color.DIM_WHITE),
                 cursor_color: int = int(Color.YELLOW)):
        if not voices:
            raise ValueError("StepGrid needs at least one voice")
        if steps < 2 or steps > 16:
            raise ValueError(f"StepGrid steps must be 2-16, got {steps}")
        rows = len(voices)
        if rows < 1 or rows > 2:
            raise ValueError(f"StepGrid rows must be 1-2, got {rows}")
        self.region = WidgetRegion(pad_slots=range(0, rows * steps))
        self._voices = voices
        self._rows = rows
        self._steps = steps
        self._active_color = int(active_color)
        self._idle_color = int(idle_color)
        self._cursor_color = int(cursor_color)
        self._state: list[list[bool]] = [[False] * steps for _ in range(rows)]
        self._cursor: int = -1   # not-yet-stepped

    def _slot(self, row: int, step: int) -> int:
        # Bottom row of the SL MkIII pads is "row 0" (steps 0..7), top row is "row 1".
        # Pad indices 0..7 = bottom row, 8..15 = top row.
        return row * self._steps + step

    def _decode_slot(self, slot: int) -> tuple[int, int]:
        return (slot // self._steps, slot % self._steps)

    def render(self, frame) -> None:
        if self._led_set is None:
            return
        for row in range(self._rows):
            for step in range(self._steps):
                slot = self._slot(row, step)
                color = self._active_color if self._state[row][step] else self._idle_color
                if step == self._cursor:
                    color = self._cursor_color
                self._led_set(LED.PAD_1.value + slot, color)

    def step(self, beat_idx: int) -> None:
        """Advance the cursor and fire NoteOn for any active step."""
        self._cursor = beat_idx % self._steps
        if self._sink is not None:
            for row in range(self._rows):
                if self._state[row][self._cursor]:
                    p = self._voices[row]
                    self._sink.send_note_on(p.channel, p.cc, p.value or 100)
        if self._frame is not None:
            self.render(self._frame)

    def on_event(self, event: WidgetEvent) -> bool:
        if event.kind != "pad" or not self.claims(event):
            return False
        if event.value <= 0:
            return True   # consume release
        row, step = self._decode_slot(event.index)
        if row >= self._rows or step >= self._steps:
            return False
        self._state[row][step] = not self._state[row][step]
        if self._led_set is not None:
            color = self._active_color if self._state[row][step] else self._idle_color
            self._led_set(LED.PAD_1.value + event.index, color)
        return True

    @property
    def state(self) -> list[list[bool]]:
        return [row[:] for row in self._state]
