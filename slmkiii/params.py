"""Parameter / ParameterProvider observer pattern for reactive controller state.

Replaces the controller's value_cache dict with a model where:
  - Parameter holds a value plus a list of observers
  - Mutations fire observers regardless of source (local knob turn,
    remote MIDI echo via Mozaic feedback, programmatic preset load)
  - ParameterProvider is the swappable "what's bound to the knobs right now"
    set; emits parameters_adjusted when its set changes (page/focus switch)

Modeled on DrivenByMoss IParameter / IParameterProvider.
"""
from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class Parameter:
    """A single named MIDI value in the 0..127 range with observers."""
    name: str
    cc: int                     # MIDI CC number (or note number for trigger)
    channel: int                # 1-indexed
    param_path: str = ""        # informational
    min_value: int = 0
    max_value: int = 127
    units: str = ""
    _value: int = 0
    _observers: list[Callable[[Parameter, int], None]] = field(default_factory=list)

    @property
    def value(self) -> int:
        return self._value

    @value.setter
    def value(self, new_value: int) -> None:
        v = max(self.min_value, min(self.max_value, int(new_value)))
        if v == self._value:
            return
        self._value = v
        # Iterate over a snapshot so observers may mutate the list safely.
        for cb in list(self._observers):
            cb(self, v)

    def add_observer(self, cb: Callable[[Parameter, int], None]) -> None:
        if cb not in self._observers:
            self._observers.append(cb)

    def remove_observer(self, cb: Callable[[Parameter, int], None]) -> None:
        try:
            self._observers.remove(cb)
        except ValueError:
            pass

    def reset(self) -> None:
        """Set to default (midpoint between min and max)."""
        self.value = (self.min_value + self.max_value) // 2


class ParameterProvider(Protocol):
    """Returns the N parameters that should be bound to the controller's
    knobs/faders right now. Fires parameters_adjusted when its set changes."""
    def get(self, index: int) -> Parameter: ...
    def size(self) -> int: ...
    def add_parameters_observer(self, cb: Callable[[], None]) -> None: ...
    def remove_parameters_observer(self, cb: Callable[[], None]) -> None: ...


class StaticParameterProvider:
    """A provider that always returns the same fixed list."""
    def __init__(self, parameters: Iterable[Parameter]):
        self._params = list(parameters)
        self._observers: list[Callable[[], None]] = []

    def get(self, index: int) -> Parameter:
        return self._params[index]

    def size(self) -> int:
        return len(self._params)

    def add_parameters_observer(self, cb: Callable[[], None]) -> None:
        if cb not in self._observers:
            self._observers.append(cb)

    def remove_parameters_observer(self, cb: Callable[[], None]) -> None:
        try:
            self._observers.remove(cb)
        except ValueError:
            pass

    def _notify(self) -> None:
        for cb in list(self._observers):
            cb()


class SelectedFocusProvider:
    """Switches between several fixed parameter sets based on focus index.

    e.g. Battalion drum-focus page: 8 sets (drum1..drum8), each with 8
    knob+fader bindings. Switching focus_idx via set_focus(i) fires the
    parameters_adjusted observer chain so downstream consumers (renderer,
    MIDI dispatcher) rebind atomically."""
    def __init__(self, instance_params: list[list[Parameter]]):
        if not instance_params:
            raise ValueError("instance_params must be non-empty")
        sizes = {len(p) for p in instance_params}
        if len(sizes) != 1:
            raise ValueError(f"all instances must have same size; got {sizes}")
        self._instances = instance_params
        self._size = next(iter(sizes))
        self._focus = 0
        self._observers: list[Callable[[], None]] = []

    @property
    def focus(self) -> int:
        return self._focus

    def set_focus(self, idx: int) -> None:
        if not (0 <= idx < len(self._instances)):
            raise IndexError(f"focus idx {idx} out of range 0..{len(self._instances) - 1}")
        if idx == self._focus:
            return
        self._focus = idx
        for cb in list(self._observers):
            cb()

    def get(self, index: int) -> Parameter:
        return self._instances[self._focus][index]

    def size(self) -> int:
        return self._size

    def num_instances(self) -> int:
        return len(self._instances)

    def add_parameters_observer(self, cb: Callable[[], None]) -> None:
        if cb not in self._observers:
            self._observers.append(cb)

    def remove_parameters_observer(self, cb: Callable[[], None]) -> None:
        try:
            self._observers.remove(cb)
        except ValueError:
            pass
