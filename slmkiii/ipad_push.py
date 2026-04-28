"""Push files to iPad apps via pymobiledevice3 HouseArrest.

Used to transfer:
  - .aum_midimap files into AUM/Documents/MIDI Mappings/
  - .mozaic files into AUM/Documents (then user "Open in Mozaic" to install)

Requires the app to declare UIFileSharingEnabled=YES (AUM does; Mozaic does
not — that's why we stage Mozaic files inside AUM's Documents).
"""

from __future__ import annotations

import asyncio
from pathlib import Path

DEFAULT_BUNDLE_ID = 'com.kymatica.AUM'


async def _push_async(local_paths: list[tuple[Path, str]],
                      bundle_id: str) -> list[str]:
    """Push (local_path, remote_path) pairs to the app's Documents folder.

    Returns the list of remote paths that were written.
    """
    from pymobiledevice3.lockdown import create_using_usbmux  # type: ignore
    from pymobiledevice3.services.house_arrest import HouseArrestService  # type: ignore

    lockdown = await create_using_usbmux()
    ha = await HouseArrestService.create(
        lockdown=lockdown, bundle_id=bundle_id, documents_only=True)
    written: list[str] = []
    try:
        for local, remote in local_paths:
            data = local.read_bytes()
            # ha.set_file_contents wants leading slash for documents_only mode
            remote_full = remote if remote.startswith('/') else f'/Documents/{remote}'
            await ha.set_file_contents(remote_full, data)
            written.append(remote_full)
    finally:
        await ha.close()
    return written


def push_files(local_paths: list[tuple[Path, str]],
               bundle_id: str = DEFAULT_BUNDLE_ID) -> list[str]:
    """Synchronous wrapper for pushing files to an iPad app.

    Args:
        local_paths: list of (local_path, remote_filename_or_path).
            Remote path may be bare (placed under /Documents) or absolute
            (e.g., '/Documents/MIDI Mappings/foo.aum_midimap').
        bundle_id: the iOS app to push to (default: AUM).

    Returns the list of absolute remote paths written.
    """
    return asyncio.run(_push_async(local_paths, bundle_id))


def push_to_aum(local_paths: list[Path]) -> list[str]:
    """Convenience: push files to AUM's Documents folder by basename."""
    pairs = [(p, p.name) for p in local_paths]
    return push_files(pairs, bundle_id='com.kymatica.AUM')
