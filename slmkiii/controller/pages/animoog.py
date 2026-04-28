"""Page configs for Moog Animoog Z (Orb-engine synth).

The harvested .aum_midimap exposes only the 21 Orb-engine root params — there
are no per-timbre level/pitch, no ADSR, no filter cutoff/resonance as
discrete MIDI-mappable params. The two pages below cover the full
MIDI-mappable surface: Orb position+rate+origin, voicing+path animator.
All on MIDI channel 3.
"""

from __future__ import annotations

from slmkiii.controller.config import Binding, Page
from slmkiii.sysex import Color


ORB_PAGE = Page(
    name='animoog_orb',
    label='Anmg Orb',
    color=Color.GREEN,
    knobs=[
        Binding('Orb X',    20, 3, 'orb_x_k'),
        Binding('Orb Y',    21, 3, 'orb_y_k'),
        Binding('Orb Z',    22, 3, 'orb_z_k'),
        Binding('Orb Rt',   23, 3, 'orb_rate_k'),
    ],
    faders=[
        Binding('Origin X', 24, 3, 'origin_x_k'),
        Binding('Origin Y', 25, 3, 'origin_y_k'),
        Binding('Origin Z', 26, 3, 'origin_z_k'),
        Binding('Z Mult',   27, 3, 'z_mult_k'),
    ],
)


VOICE_PAGE = Page(
    name='animoog_voice',
    label='Anmg Voc',
    color=Color.CYAN,
    knobs=[
        Binding('BaseFreq', 28, 3, 'base_freq_k'),
        Binding('Glide',    29, 3, 'syn_glide_k'),
        Binding('Voices',   30, 3, 'syn_voice_limit_k'),
        Binding('Volume',   31, 3, 'syn_volume_k'),
    ],
    faders=[
        Binding('PathRate', 33, 3, 'path_rate_k'),
        Binding('PathDir',  34, 3, 'path_dir_k'),
        Binding('PathSync', 35, 3, 'path_sync_t'),
        Binding('OrbSync',  36, 3, 'orb_sync_t'),
    ],
)


PAGES: list[Page] = [ORB_PAGE, VOICE_PAGE]

AU_IDENTIFIER = 'Animoog Z.AU-4D6F6F67616E696D61756D75'


def _aum_export():
    from slmkiii.controller.pages import AumExport
    return AumExport(
        pages=PAGES,
        au_identifier=AU_IDENTIFIER,
        filename='SLMK Animoog.aum_midimap',
    )


AUM_EXPORT = _aum_export()
