"""DEPRECATED: page configs for Unfiltered Audio Battalion (8-track drum synth).

This Python-dataclass spec is superseded by slmkiii/data/specs/battalion.yaml,
which is auto-loaded by slmkiii.controller.pages and wins on name collision.
This file is preserved as a fallback for users who haven't migrated yet
and will be deleted in a future release. New page configs should be
authored as YAML.

CCs all on MIDI channel 1, allocated in 20..91 (avoiding the standard
reserved CCs 7, 64-69, 96-99). Drum trigger pads send notes 36-51 ch10.
"""
from __future__ import annotations

import warnings as _warnings

_warnings.warn(
    "slmkiii.controller.pages.battalion (Python spec) is deprecated; "
    "slmkiii/data/specs/battalion.yaml is the canonical source. "
    "This module will be removed in a future release.",
    DeprecationWarning,
    stacklevel=2,
)

from slmkiii.controller.config import Binding, Page
from slmkiii.sysex import Color


BATTALION_DRUM_NOTE_BASE = 36   # C2 = drum 1
BATTALION_DRUM_CHANNEL = 10


def _drum_pads() -> list[Binding]:
    return [
        Binding(f'Pad {i + 1}', BATTALION_DRUM_NOTE_BASE + i,
                BATTALION_DRUM_CHANNEL, f'drum_trigger_{i + 1}')
        for i in range(16)
    ]


def _make_drum_page(drum_idx: int) -> Page:
    n = drum_idx
    cc_start = 28 + (n - 1) * 8
    return Page(
        name=f'drum{n}',
        label=f'Drum {n}',
        color=Color.ORANGE,
        knobs=[
            Binding(f'D{n} Cut',  cc_start + 0, 1, f'drumProtoParams.drum{n}params.drum{n}cutoff'),
            Binding(f'D{n} Reso', cc_start + 1, 1, f'drumProtoParams.drum{n}params.drum{n}resonance'),
            Binding(f'D{n} Dist', cc_start + 2, 1, f'drumProtoParams.drum{n}params.drum{n}distort'),
            Binding(f'D{n} Mix',  cc_start + 3, 1, f'drumProtoParams.drum{n}params.drum{n}enginemix'),
        ],
        faders=[
            Binding(f'D{n} Lvl',  cc_start + 4, 1, f'drumProtoParams.drum{n}params.drum{n}outGain'),
            Binding(f'D{n} Pit',  cc_start + 5, 1, f'drumProtoParams.drum{n}params.drum{n}pitch'),
            Binding(f'D{n} Dec',  cc_start + 6, 1, f'drumProtoParams.drum{n}params.drum{n}env1decay'),
            Binding(f'D{n} Snd',  cc_start + 7, 1, f'drumProtoParams.drum{n}params.drum{n}sendA'),
        ],
    )


DRUM_FOCUS_PAGES: dict[int, Page] = {i: _make_drum_page(i + 1) for i in range(8)}


GLOBAL_PAGE = Page(
    name='bat_global',
    label='Bat Mix',
    color=Color.RED,
    knobs=[
        Binding('Master',   7,  1, 'Volume'),
        Binding('OutGain',  21, 1, 'drumProtoParams.effectParams.outGain'),
        Binding('Maximize', 22, 1, 'drumProtoParams.effectParams.maximize'),
        Binding('ModDepth', 23, 1, 'drumProtoParams.performParams.modulationDepth'),
    ],
    faders=[
        Binding('EQ Low',   24, 1, 'drumProtoParams.effectParams.eqlow'),
        Binding('EQ Mid',   25, 1, 'drumProtoParams.effectParams.eqmid'),
        Binding('EQ High',  26, 1, 'drumProtoParams.effectParams.eqhigh'),
        Binding('Random',   27, 1, 'drumProtoParams.performParams.performRandomDepth'),
    ],
    pads=_drum_pads(),
)


DRUM_FOCUS_PAGE = Page(
    name='bat_drum',
    label='Bat Drum',
    color=Color.ORANGE,
    pads=_drum_pads(),
    focus_set=[f'drum{i + 1}' for i in range(8)],
    specialize=lambda focus_idx: DRUM_FOCUS_PAGES[focus_idx],
)


PAGES: list[Page] = [GLOBAL_PAGE, DRUM_FOCUS_PAGE]


# AU identifier used by AUM to scope MIDI mappings to the Battalion plugin.
AU_IDENTIFIER = 'UA Battalion.AU-556E41757561424C61756D75'


def _aum_export():
    from slmkiii.controller.pages import AumExport
    return AumExport(
        pages=PAGES + list(DRUM_FOCUS_PAGES.values()),
        au_identifier=AU_IDENTIFIER,
        filename='SLMK Battalion.aum_midimap',
    )


AUM_EXPORT = _aum_export()
