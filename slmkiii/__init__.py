"""slmkiii — Novation SL MkIII tooling: templates, live API, AUM bridge.

Subpackages:
    sysex       — every SL MkIII protocol byte (single source of truth)
    template    — binary template file format (.syx, .json)
    incontrol   — live LED/screen/input API over the InControl USB port
    midi        — MIDI port discovery + template push/pull
    aum         — read/write AUM .aum_midimap and .aumproj files
    controller  — live SL MkIII <-> AUM controller runtime + page configs
    harvest     — extract plugin parameters from harvested .aum_midimap files
    ipad_push   — pymobiledevice3 file-push helper
"""

from slmkiii.template import Template
from slmkiii import midi
from slmkiii import incontrol
from slmkiii import sysex

__all__ = ['Template', 'midi', 'incontrol', 'sysex']
