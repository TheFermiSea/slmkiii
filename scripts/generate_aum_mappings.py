"""Generate AUM .aum_midimap files matching the slmk_aum_controller CC scheme.

Reads PAGES + DRUM_FOCUS_PAGES from slmk_aum_controller and writes one
.aum_midimap per plugin, producing files the user can drop into AUM's
Documents directory and load on the matching plugin.

Output files:
    output/SLMK Battalion.aum_midimap
    output/SLMK Animoog.aum_midimap

Drambo is intentionally skipped — those CCs are meant to be MIDI-learned
inside Drambo itself, not pre-mapped via .aum_midimap.

Usage:
    uv run python scripts/generate_aum_mappings.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from slmkiii.aum import AumMidiMapping, MSG_TYPE_CC, write_aum_midimap
from slmk_aum_controller import (
    PAGES,
    DRUM_FOCUS_PAGES,
    Page,
)


# AU identifiers (collection_name strings used by AUM to scope mappings)
BATTALION_COLLECTION = "UA Battalion.AU-556E41757561424C61756D75"
ANIMOOG_COLLECTION = "Animoog Z.AU-4D6F6F67616E696D61756D75"


def collect_bindings_for_plugin(page_names: list[str]) -> list[AumMidiMapping]:
    """Walk PAGES + DRUM_FOCUS_PAGES, collect bindings whose page name matches,
    convert to AumMidiMapping. Dedupes on (channel, cc, param_path)."""
    seen: set[tuple[int, int, str]] = set()
    out: list[AumMidiMapping] = []

    def add(b, source_page: str) -> None:
        if not b.param_path:
            return
        key = (b.channel - 1, b.cc, b.param_path)
        if key in seen:
            return
        seen.add(key)
        out.append(AumMidiMapping(
            parameter_name=b.param_path,
            cc_number=b.cc,
            channel=b.channel - 1,   # 0-indexed in AUM
            min_value=0.0,
            max_value=1.0,
            enabled=True,
            auto_toggle=False,
            msg_type=MSG_TYPE_CC,
        ))

    for p in PAGES:
        if p.name in page_names:
            for b in p.knobs + p.faders:
                add(b, p.name)

    # Drum focus pages: bat_drum specialization
    if 'bat_drum' in page_names:
        for p in DRUM_FOCUS_PAGES.values():
            for b in p.knobs + p.faders:
                add(b, p.name)

    return out


def main() -> int:
    out_dir = Path('output')
    out_dir.mkdir(exist_ok=True)

    # --- Battalion ---
    bat_mappings = collect_bindings_for_plugin(['bat_global', 'bat_drum'])
    bat_path = out_dir / 'SLMK Battalion.aum_midimap'
    write_aum_midimap(BATTALION_COLLECTION, bat_mappings, bat_path)
    print(f'  Battalion: {len(bat_mappings):3d} mappings -> {bat_path}')

    # --- Animoog ---
    anm_mappings = collect_bindings_for_plugin(['animoog_orb', 'animoog_voice'])
    anm_path = out_dir / 'SLMK Animoog.aum_midimap'
    write_aum_midimap(ANIMOOG_COLLECTION, anm_mappings, anm_path)
    print(f'  Animoog:   {len(anm_mappings):3d} mappings -> {anm_path}')

    # Brief CC-allocation summary
    print('\nCC allocation summary (CC, channel, parameter):')
    print('  Battalion (ch1):')
    for m in sorted(bat_mappings, key=lambda x: x.cc_number):
        print(f'    CC{m.cc_number:3d}  ch{m.channel + 1}  {m.parameter_name}')
    print('  Animoog (ch3):')
    for m in sorted(anm_mappings, key=lambda x: x.cc_number):
        print(f'    CC{m.cc_number:3d}  ch{m.channel + 1}  {m.parameter_name}')

    return 0


if __name__ == '__main__':
    sys.exit(main())
