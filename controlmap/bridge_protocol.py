"""Wire protocol for the SL MkIII <-> Mozaic bridge.

Mirrors slmk_bridge.moz (see controlmap/mozaic/slmk_bridge.moz).

Private manufacturer ID 0x7D (non-commercial / research), per the MIDI
specification. All payload bytes are 0-127 (standard MIDI data byte range)
so no 7-bit escaping is needed.

The protocol is asymmetric: opcodes 0x00-0x0F are Mac->bridge requests,
opcodes 0x10-0x1F are bridge->Mac responses/events.

    Mac -> bridge:
        F0 7D 00 F7                          HELLO
        F0 7D 01 F7                          GET_VALUES (request replay of cached state)
        F0 7D 02 ch cc [ch cc ...] F7        WATCH_CC
        F0 7D 03 ch [ch ...] F7              WATCH_NOTES (echo all notes on listed channels)
        F0 7D 04 F7                          CLEAR_WATCHES
        F0 7D 05 page F7                     PAGE

    bridge -> Mac:
        F0 7D 10 major minor F7              HELLO_ACK (also sent at @OnLoad)
        F0 7D 11 ch cc val F7                CC_VALUE
        F0 7D 12 ch note vel F7              NOTE_ON
        F0 7D 13 ch note F7                  NOTE_OFF
        F0 7D 15 page F7                     PAGE_ACK
"""

from __future__ import annotations

from typing import Iterable

import mido

PROTOCOL_VERSION = (1, 1)

SX_TAG = 0x7D

# Mac -> bridge opcodes
CMD_HELLO = 0x00
CMD_GET_VALUES = 0x01
CMD_WATCH_CC = 0x02
CMD_WATCH_NOTES = 0x03
CMD_CLEAR_WATCHES = 0x04
CMD_PAGE = 0x05

# bridge -> Mac opcodes
RSP_HELLO_ACK = 0x10
RSP_CC_VALUE = 0x11
RSP_NOTE_ON = 0x12
RSP_NOTE_OFF = 0x13
RSP_PAGE_ACK = 0x15

# A conservative chunk size for WATCH_CC. AUM/iOS CoreMIDI tolerate large
# sysex but staying well under 128 bytes per packet avoids edge cases.
WATCH_CC_MAX_PAIRS = 62


# ── Mac → bridge encoders ────────────────────────────────────────────────────


def hello() -> mido.Message:
    return mido.Message('sysex', data=[SX_TAG, CMD_HELLO])


def get_values() -> mido.Message:
    return mido.Message('sysex', data=[SX_TAG, CMD_GET_VALUES])


def clear_watches() -> mido.Message:
    return mido.Message('sysex', data=[SX_TAG, CMD_CLEAR_WATCHES])


def watch_cc(pairs: Iterable[tuple[int, int]]) -> list[mido.Message]:
    """Chunk (channel, cc) pairs into one or more WATCH_CC sysex messages.

    Channels are 0-indexed (0..15).
    """
    pair_list = list(pairs)
    out: list[mido.Message] = []
    for i in range(0, len(pair_list), WATCH_CC_MAX_PAIRS):
        chunk = pair_list[i:i + WATCH_CC_MAX_PAIRS]
        payload = [SX_TAG, CMD_WATCH_CC]
        for ch, cc in chunk:
            payload.extend([ch & 0x0F, cc & 0x7F])
        out.append(mido.Message('sysex', data=payload))
    return out


def watch_notes(channels: Iterable[int]) -> mido.Message:
    """Enable note echoing on the given 0-indexed channels."""
    payload = [SX_TAG, CMD_WATCH_NOTES]
    for ch in channels:
        payload.append(ch & 0x0F)
    return mido.Message('sysex', data=payload)


def page(page_index: int) -> mido.Message:
    return mido.Message('sysex', data=[SX_TAG, CMD_PAGE, page_index & 0x7F])


# ── Parser ──────────────────────────────────────────────────────────────────


def parse(msg: mido.Message) -> tuple[int, tuple[int, ...]] | None:
    """Parse an incoming sysex. Returns (opcode, payload) or None.

    Returns None for any sysex that isn't part of our private protocol.
    """
    if msg.type != 'sysex':
        return None
    data = tuple(msg.data)
    if len(data) < 2 or data[0] != SX_TAG:
        return None
    return data[1], data[2:]


# ── Convenience: typed event objects ─────────────────────────────────────────


from dataclasses import dataclass


@dataclass(frozen=True)
class CCValue:
    channel: int
    cc: int
    value: int


@dataclass(frozen=True)
class NoteEvent:
    channel: int
    note: int
    velocity: int  # 0 for NoteOff
    on: bool


@dataclass(frozen=True)
class HelloAck:
    major: int
    minor: int


@dataclass(frozen=True)
class PageAck:
    page: int


def parse_event(msg: mido.Message):
    """Parse a bridge -> Mac message into a typed event, or None."""
    parsed = parse(msg)
    if parsed is None:
        return None
    op, payload = parsed
    if op == RSP_CC_VALUE and len(payload) >= 3:
        return CCValue(payload[0], payload[1], payload[2])
    if op == RSP_NOTE_ON and len(payload) >= 3:
        return NoteEvent(payload[0], payload[1], payload[2], on=True)
    if op == RSP_NOTE_OFF and len(payload) >= 2:
        return NoteEvent(payload[0], payload[1], 0, on=False)
    if op == RSP_HELLO_ACK and len(payload) >= 2:
        return HelloAck(payload[0], payload[1])
    if op == RSP_PAGE_ACK and len(payload) >= 1:
        return PageAck(payload[0])
    return None
