"""Wire protocol for the SL MkIII ↔ Mozaic bridge.

Mirrors slmk_bridge.moz (see controlmap/mozaic/slmk_bridge.moz).

Private manufacturer ID 0x7D (non-commercial / research), per the MIDI
specification. Payload bytes are always 0-127 so no 7-bit escaping is needed.

    F0 7D 01 F7                           HELLO           (both directions)
    F0 7D 02 ch cc [ch cc ...] F7         WATCH_SET       Mac -> iPad
    F0 7D 03 F7                           WATCH_CLEAR     Mac -> iPad
    F0 7D 04 ch cc val F7                 VALUE           iPad -> Mac
    F0 7D 05 page F7                      PAGE            both directions
"""

from __future__ import annotations

from typing import Iterable

import mido

SX_TAG = 0x7D
SX_HELLO = 0x01
SX_WATCH_SET = 0x02
SX_WATCH_CLEAR = 0x03
SX_VALUE = 0x04
SX_PAGE = 0x05

# A conservative chunk size for WATCH_SET. AUM / iOS CoreMIDI handle large
# sysex but staying well under 128 bytes per packet avoids edge cases.
WATCH_SET_MAX_PAIRS = 62


def hello() -> mido.Message:
    return mido.Message('sysex', data=[SX_TAG, SX_HELLO])


def watch_clear() -> mido.Message:
    return mido.Message('sysex', data=[SX_TAG, SX_WATCH_CLEAR])


def watch_set(pairs: Iterable[tuple[int, int]]) -> list[mido.Message]:
    """Chunk (channel, cc) pairs into one or more WATCH_SET sysex messages.

    Channels are 0-indexed (0..15).
    """
    pair_list = list(pairs)
    out: list[mido.Message] = []
    for i in range(0, len(pair_list), WATCH_SET_MAX_PAIRS):
        chunk = pair_list[i:i + WATCH_SET_MAX_PAIRS]
        payload = [SX_TAG, SX_WATCH_SET]
        for ch, cc in chunk:
            payload.extend([ch & 0x0F, cc & 0x7F])
        out.append(mido.Message('sysex', data=payload))
    return out


def page(page_index: int) -> mido.Message:
    return mido.Message('sysex', data=[SX_TAG, SX_PAGE, page_index & 0x7F])


def parse(msg: mido.Message) -> tuple[int, tuple[int, ...]] | None:
    """Parse an incoming sysex. Returns (command, payload) or None."""
    if msg.type != 'sysex':
        return None
    data = tuple(msg.data)
    if len(data) < 2 or data[0] != SX_TAG:
        return None
    return data[1], data[2:]
