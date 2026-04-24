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
    """Reference to a plugin parameter.

    Optional metadata (unit, value range, taper, discrete labels) drives
    rich on-surface rendering — e.g., showing '437 Hz' instead of '65',
    or 'On'/'Off' instead of '127'/'0'. All metadata fields default to
    sensible empty values so older plugin JSONs keep working.
    """
    plugin_id: str          # e.g., "ua_battalion"
    param_path: str         # e.g., "drumProtoParams.drum1params.drum1cutoff"
    display_name: str = ""  # max 9 chars for SL MkIII screens
    unit: str = ""          # e.g., 'Hz', 'dB', '%', 'st', 'ms'
    value_min: float = 0.0  # real-world min (e.g., 20 for Hz)
    value_max: float = 1.0  # real-world max (e.g., 20000 for Hz)
    taper: str = "lin"      # 'lin' | 'log' | 'exp'
    # Discrete labels for stepped/toggle parameters: tuple of strings indexed
    # by raw 0-127 value bucketed into len(discrete_labels). Empty = continuous.
    discrete_labels: tuple[str, ...] = ()


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
    # Per-page CC routes: hardware (in_ch, in_cc) on a given page is rewritten
    # to (out_ch, out_cc) before hitting AUM's MIDI mapping / plugin chain.
    # Pushed to the Mozaic bridge as ROUTE_SET commands. Channels are
    # 1-indexed user-facing (matches midi_channel_base convention).
    routes: list['RouteSpec'] = field(default_factory=list)


@dataclass(frozen=True)
class RouteSpec:
    """A per-page CC route declaration in a MappingSpec."""
    page: int
    in_channel: int      # 1-indexed user-facing
    in_cc: int
    out_channel: int     # 1-indexed user-facing
    out_cc: int


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
