"""Page configs for Drambo (modular host).

Drambo doesn't take .aum_midimap files; instead it learns CCs internally via
its MIDI-Learn UI. This page just declares 8 generic CC slots on channel 3
that you assign inside Drambo to whatever you want.
"""

from __future__ import annotations

from slmkiii.controller.config import Binding, Page
from slmkiii.sysex import Color


MACROS_PAGE = Page(
    name='drambo',
    label='Drambo',
    color=Color.PURPLE,
    knobs=[
        Binding(f'Macro{i + 1}', 102 + i, 3, f'unassigned{i + 1}')
        for i in range(4)
    ],
    faders=[
        Binding(f'Macro{i + 5}', 106 + i, 3, f'unassigned{i + 5}')
        for i in range(4)
    ],
)


PAGES: list[Page] = [MACROS_PAGE]
