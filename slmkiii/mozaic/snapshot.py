"""Captured-event records for the Mozaic interpreter.

Phase 1 (c03): the basic ``MidiEvent`` and ``SysexEvent`` dataclasses used
by the interpreter to record outbound traffic.

Phase 2 (c04) extends this module with the :class:`Trace` aggregator and
deterministic JSON serialisation for golden snapshot tests.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class MidiEvent:
    """A single captured MIDI event (CC / NoteOn / NoteOff)."""

    tick: int
    status: int
    data1: int
    data2: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "tick": self.tick,
            "status": self.status,
            "data1": self.data1,
            "data2": self.data2,
        }


@dataclass(frozen=True)
class SysexEvent:
    """A single captured SysEx packet."""

    tick: int
    bytes_data: bytes

    def to_dict(self) -> dict[str, Any]:
        return {
            "tick": self.tick,
            "bytes": list(self.bytes_data),
        }
