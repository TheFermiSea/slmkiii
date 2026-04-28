"""Page/Binding data model for the live controller.

Each `Page` holds up to 8 knob bindings + 8 fader bindings + 16 pad bindings
plus an optional `focus_set` enabling per-page sub-instance specialization
(e.g. picking which Battalion drum the knobs/faders address).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable


@dataclass(frozen=True)
class Binding:
    """One knob/fader/pad → MIDI mapping."""
    label: str          # display label, max 9 chars (SL screen width)
    cc: int             # MIDI CC number 0..127 (or note number for pad)
    channel: int        # 1-indexed (1..16)
    param_path: str = ''
    min_val: int = 0
    max_val: int = 127


@dataclass
class Page:
    """A page of bindings selectable via the top-row soft buttons."""
    name: str
    label: str          # short display name (max 9 chars)
    color: int          # SL palette colour for the page-select LED
    knobs: list[Binding] = field(default_factory=list)
    faders: list[Binding] = field(default_factory=list)
    pads: list[Binding] = field(default_factory=list)
    focus_set: list[str] = field(default_factory=list)
    # When set, current_page is computed by calling specialize(focus_idx).
    specialize: Callable[[int], 'Page'] | None = None
