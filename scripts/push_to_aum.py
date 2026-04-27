"""Push generated .aum_midimap files to AUM's Documents folder on iPad via USB.

Uses pymobiledevice3's HouseArrestService to write directly into the AUM
sandbox. After pushing, the files appear in AUM's MIDI Mappings browser
and can be loaded onto the matching plugin instance.

Requires:
    - iPad connected via USB and trusted
    - AUM installed (bundle id com.kymatica.AUM)
    - pymobiledevice3 (auto-installed by uv)

Usage:
    uv run --with pymobiledevice3 python scripts/push_to_aum.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from pymobiledevice3.lockdown import create_using_usbmux
from pymobiledevice3.services.house_arrest import HouseArrestService


AUM_BUNDLE_ID = 'com.kymatica.AUM'
LOCAL_FILES = [
    Path('output/SLMK Battalion.aum_midimap'),
    Path('output/SLMK Animoog.aum_midimap'),
]
REMOTE_DIR = '/Documents/MIDI Mappings/Channel'


async def main() -> int:
    missing = [p for p in LOCAL_FILES if not p.exists()]
    if missing:
        print('Missing local files (run generate_aum_mappings.py first):')
        for p in missing:
            print(f'  {p}')
        return 1

    print('Connecting to iPad ...')
    lockdown = await create_using_usbmux()
    print(f'  Device: {lockdown.product_type} / iOS {lockdown.product_version}')

    print(f'Opening AUM sandbox ({AUM_BUNDLE_ID}) ...')
    house = await HouseArrestService.create(
        lockdown=lockdown,
        bundle_id=AUM_BUNDLE_ID,
        documents_only=True,
    )

    # Make sure the destination dir exists
    try:
        await house.makedirs(REMOTE_DIR)
    except Exception:
        pass  # already exists or recurse-create issue, ignore

    for local in LOCAL_FILES:
        remote = f'{REMOTE_DIR}/{local.name}'
        print(f'  push {local} -> ipad:{remote}')
        with open(local, 'rb') as f:
            data = f.read()
        try:
            await house.set_file_contents(remote, data)
            stat = await house.stat(remote)
            size = stat.get('st_size', 0)
            print(f'    OK ({size} bytes on iPad)')
        except Exception as e:
            print(f'    FAIL: {e}')

    print('\nDone. In AUM, open MIDI Mapping browser on each plugin instance')
    print('and load "SLMK Battalion" or "SLMK Animoog".')
    return 0


if __name__ == '__main__':
    sys.exit(asyncio.run(main()))
