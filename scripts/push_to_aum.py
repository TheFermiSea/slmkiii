"""Push generated .aum_midimap files to AUM's Documents folder on iPad over USB.

Thin wrapper around controlmap.ipad_push.push_files. After pushing, the files
appear in AUM's MIDI Mappings browser and can be loaded onto the matching
plugin instance.

Usage:
    uv run --with pymobiledevice3 python scripts/push_to_aum.py
"""

from __future__ import annotations

import sys
from pathlib import Path

from slmkiii.ipad_push import push_files


REMOTE_DIR = '/Documents/MIDI Mappings/Channel'
LOCAL_FILES = [
    Path('output/SLMK Battalion.aum_midimap'),
    Path('output/SLMK Animoog.aum_midimap'),
]


def main() -> int:
    missing = [p for p in LOCAL_FILES if not p.exists()]
    if missing:
        print('Missing local files (run generate_aum_mappings.py first):')
        for p in missing:
            print(f'  {p}')
        return 1

    pairs = [(p, f'{REMOTE_DIR}/{p.name}') for p in LOCAL_FILES]
    print('Pushing to iPad AUM ...')
    written = push_files(pairs)
    for path in written:
        print(f'  {path}')
    print('\nDone. In AUM, open MIDI Mapping browser on each plugin instance')
    print('and load "SLMK Battalion" or "SLMK Animoog".')
    return 0


if __name__ == '__main__':
    sys.exit(main())
