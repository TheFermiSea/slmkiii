"""Controller profile definitions."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto

from controlmap.model import ControlSlot, ControlType


class Feature(Enum):
    SCREENS = auto()
    RGB_LEDS = auto()
    VELOCITY_PADS = auto()
    AFTERTOUCH = auto()
    SEQUENCER = auto()
    MOTORIZED_FADERS = auto()


@dataclass(frozen=True)
class ControlGroup:
    """A group of physical controls of the same type."""
    name: str
    count: int
    control_type: ControlType
    pages_hardware: int = 1
    has_display: bool = False
    display_chars: int = 0


@dataclass
class ControllerProfile:
    """Complete description of a MIDI controller's capabilities."""
    id: str
    name: str
    control_groups: list[ControlGroup]
    features: set[Feature] = field(default_factory=set)

    def slots(self) -> list[ControlSlot]:
        """Enumerate all available control slots."""
        result = []
        for group in self.control_groups:
            for i in range(group.count):
                result.append(ControlSlot(
                    group=group.name,
                    index=i,
                    control_type=group.control_type,
                    has_display=group.has_display,
                    display_chars=group.display_chars,
                ))
        return result

    def slots_by_type(self, control_type: ControlType) -> list[ControlSlot]:
        return [s for s in self.slots() if s.control_type == control_type]

    def slots_by_group(self, group_name: str) -> list[ControlSlot]:
        return [s for s in self.slots() if s.group == group_name]

    def group(self, name: str) -> ControlGroup | None:
        for g in self.control_groups:
            if g.name == name:
                return g
        return None

    @property
    def total_controls(self) -> int:
        return sum(g.count for g in self.control_groups)
