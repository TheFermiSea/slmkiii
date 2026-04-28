"""Captured-event records and ``Trace`` aggregator for the Mozaic interpreter.

The interpreter writes every outbound MIDI / SysEx event into its own
``midi_out`` / ``sysex_out`` lists during ``fire(...)``. After a test run
those lists can be collected into a :class:`Trace`, which serialises to a
deterministic, sorted JSON document suitable for committing as a golden
snapshot.

The exact JSON shape is::

    {
      "log":   [<string>, ...],
      "midi":  [{"tick": int, "status": int, "data1": int, "data2": int}, ...],
      "sysex": [{"tick": int, "bytes": [int, ...]}, ...]
    }

Top-level keys are sorted; the inner ordering follows insertion order
(which is the only thing the interpreter guarantees about side-effect
ordering — the same script + same inputs always produces the same trace).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Iterable


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


@dataclass
class Trace:
    """Aggregated capture from a Mozaic test run.

    Constructed empty; populate via :meth:`add_midi`, :meth:`add_sysex`,
    :meth:`add_log`, or in bulk with :meth:`from_interp`.
    """

    midi: list[MidiEvent] = field(default_factory=list)
    sysex: list[SysexEvent] = field(default_factory=list)
    log: list[str] = field(default_factory=list)

    def add_midi(self, ev: MidiEvent) -> None:
        self.midi.append(ev)

    def add_sysex(self, ev: SysexEvent) -> None:
        self.sysex.append(ev)

    def add_log(self, line: str) -> None:
        self.log.append(line)

    @classmethod
    def from_interp(cls, interp: Any) -> "Trace":
        """Snapshot the current state of an interpreter into a fresh Trace."""
        return cls(
            midi=list(interp.midi_out),
            sysex=list(interp.sysex_out),
            log=list(interp.log),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "log": list(self.log),
            "midi": [m.to_dict() for m in self.midi],
            "sysex": [s.to_dict() for s in self.sysex],
        }

    def to_json(self) -> str:
        """Serialise to deterministic JSON (sorted keys, indent=2)."""
        return json.dumps(self.to_dict(), sort_keys=True, indent=2)

    @classmethod
    def from_json(cls, text: str) -> "Trace":
        d = json.loads(text)
        midi = [
            MidiEvent(tick=m["tick"], status=m["status"], data1=m["data1"], data2=m["data2"])
            for m in d.get("midi", [])
        ]
        sysex = [
            SysexEvent(tick=s["tick"], bytes_data=bytes(s["bytes"]))
            for s in d.get("sysex", [])
        ]
        return cls(midi=midi, sysex=sysex, log=list(d.get("log", [])))


def merge_traces(traces: Iterable[Trace]) -> Trace:
    """Concatenate multiple traces in order."""
    out = Trace()
    for t in traces:
        out.midi.extend(t.midi)
        out.sysex.extend(t.sysex)
        out.log.extend(t.log)
    return out
