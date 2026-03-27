"""Core domain model for the control surface mapping framework."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from controlmap.plugins import PluginParam


class ControlType(Enum):
    """Physical control type on a hardware controller."""
    CONTINUOUS = auto()    # Knob, fader, encoder — sends CC range
    MOMENTARY = auto()     # Button — sends note on/off or CC toggle
    VELOCITY = auto()      # Pad — sends note with velocity
    TOGGLE = auto()        # Button with latch/toggle behavior


class ParamType(Enum):
    """Plugin parameter value type."""
    CONTINUOUS = auto()    # 0.0–1.0 float (filter cutoff, volume)
    DISCRETE = auto()      # Integer steps (waveform selector, mode)
    TOGGLE = auto()        # On/off boolean (mute, solo, bypass)
    TRIGGER = auto()       # Momentary fire-and-forget (note trigger)


class MsgType(str, Enum):
    """MIDI message type for a binding."""
    CC = "cc"
    NOTE = "note"


@dataclass(frozen=True)
class ControlSlot:
    """A specific physical control on a controller."""
    group: str              # "knobs", "faders", "buttons", "pads"
    index: int              # 0-based within group
    control_type: ControlType
    has_display: bool = False
    display_chars: int = 9


@dataclass(frozen=True)
class ParameterRef:
    """Reference to a plugin parameter."""
    plugin_id: str          # e.g., "ua_battalion"
    param_path: str         # e.g., "drumProtoParams.drum1params.drum1cutoff"
    display_name: str = ""  # max 9 chars for SL MkIII screens


@dataclass
class Binding:
    """A control-to-parameter assignment with MIDI details."""
    slot: ControlSlot
    param: ParameterRef
    midi_channel: int       # 1-16 (user-facing)
    midi_cc: int = 0        # 0-127
    midi_note: int = 0
    msg_type: MsgType = MsgType.CC
    min_value: float = 0.0
    max_value: float = 1.0


@dataclass
class Page:
    """One page/bank of control assignments."""
    name: str
    index: int
    bindings: list[Binding] = field(default_factory=list)


@dataclass
class PageSet:
    """Complete set of pages for a mapping."""
    pages: list[Page] = field(default_factory=list)

    @property
    def total_bindings(self) -> int:
        return sum(len(p.bindings) for p in self.pages)

    @property
    def all_bindings(self) -> list[Binding]:
        return [b for p in self.pages for b in p.bindings]


@dataclass
class MappingSpec:
    """Declarative specification of a mapping intent.

    This is the INPUT to compile_mapping(). It says WHAT should be
    mapped, not HOW — the strategy decides the details.
    """
    name: str
    controller_id: str
    plugin_id: str
    target_id: str
    param_selections: list[str] = field(default_factory=list)
    param_priorities: dict[str, int] = field(default_factory=dict)
    reserved_bindings: list[Binding] = field(default_factory=list)
    midi_channel_base: int = 1
    strategy: str = "affinity"


@dataclass
class ResolvedMapping:
    """Fully resolved output of the compilation pipeline."""
    spec: MappingSpec
    page_set: PageSet
    metadata: dict = field(default_factory=dict)


class MappingStrategy(Protocol):
    """Protocol for mapping intelligence."""

    def assign(
        self,
        params: list[PluginParam],
        slots: list[ControlSlot],
    ) -> list[tuple[PluginParam, ControlSlot]]:
        ...
