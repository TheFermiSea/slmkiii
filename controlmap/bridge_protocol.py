"""Wire protocol for the SL MkIII <-> Mozaic bridge.

Mirrors slmk_bridge.moz (see controlmap/mozaic/slmk_bridge.moz).

Private manufacturer ID 0x7D (non-commercial / research), per the MIDI
specification. All payload bytes are 0-127 so no 7-bit escaping is needed.
Opcodes 0x00-0x0F are Mac->bridge requests; 0x10-0x1F are bridge->Mac
responses/events.

    Mac -> bridge:
        F0 7D 00 F7                                         HELLO
        F0 7D 01 F7                                         GET_VALUES
        F0 7D 02 ch cc [ch cc ...] F7                       WATCH_CC
        F0 7D 03 ch [ch ...] F7                             WATCH_NOTES
        F0 7D 04 F7                                         CLEAR_WATCHES
        F0 7D 05 page F7                                    PAGE
        F0 7D 06 F7                                         GET_HEALTH
        F0 7D 07 page in_ch in_cc out_ch out_cc [...] F7    ROUTE_SET
        F0 7D 08 F7                                         ROUTE_CLEAR
        F0 7D 09 scene F7                                   SCENE_SAVE
        F0 7D 0A scene F7                                   SCENE_RECALL

    bridge -> Mac:
        F0 7D 10 major minor F7                             HELLO_ACK
        F0 7D 11 ch cc val F7                               CC_VALUE
        F0 7D 12 ch note vel F7                             NOTE_ON
        F0 7D 13 ch note F7                                 NOTE_OFF
        F0 7D 14 in_h in_l out_h out_l routes scenes F7     HEALTH
        F0 7D 15 page F7                                    PAGE_ACK
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import mido

PROTOCOL_VERSION = (1, 2)

SX_TAG = 0x7D

# Mac -> bridge opcodes
CMD_HELLO = 0x00
CMD_GET_VALUES = 0x01
CMD_WATCH_CC = 0x02
CMD_WATCH_NOTES = 0x03
CMD_CLEAR_WATCHES = 0x04
CMD_PAGE = 0x05
CMD_GET_HEALTH = 0x06
CMD_ROUTE_SET = 0x07
CMD_ROUTE_CLEAR = 0x08
CMD_SCENE_SAVE = 0x09
CMD_SCENE_RECALL = 0x0A

# bridge -> Mac opcodes
RSP_HELLO_ACK = 0x10
RSP_CC_VALUE = 0x11
RSP_NOTE_ON = 0x12
RSP_NOTE_OFF = 0x13
RSP_HEALTH = 0x14
RSP_PAGE_ACK = 0x15

WATCH_CC_MAX_PAIRS = 62
ROUTE_SET_MAX = 24   # 5 bytes each + overhead


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
    payload = [SX_TAG, CMD_WATCH_NOTES]
    for ch in channels:
        payload.append(ch & 0x0F)
    return mido.Message('sysex', data=payload)


def page(page_index: int) -> mido.Message:
    return mido.Message('sysex', data=[SX_TAG, CMD_PAGE, page_index & 0x7F])


def get_health() -> mido.Message:
    return mido.Message('sysex', data=[SX_TAG, CMD_GET_HEALTH])


@dataclass(frozen=True)
class Route:
    """A per-page CC route: when on `page`, input (in_ch, in_cc) becomes
    output (out_ch, out_cc). Channels are 0-indexed."""
    page: int
    in_ch: int
    in_cc: int
    out_ch: int
    out_cc: int


def route_set(routes: Iterable[Route]) -> list[mido.Message]:
    """Chunk routes into one or more ROUTE_SET sysex messages."""
    route_list = list(routes)
    out: list[mido.Message] = []
    for i in range(0, len(route_list), ROUTE_SET_MAX):
        chunk = route_list[i:i + ROUTE_SET_MAX]
        payload = [SX_TAG, CMD_ROUTE_SET]
        for r in chunk:
            payload.extend([r.page & 0x07, r.in_ch & 0x0F, r.in_cc & 0x7F,
                            r.out_ch & 0x0F, r.out_cc & 0x7F])
        out.append(mido.Message('sysex', data=payload))
    return out


def route_clear() -> mido.Message:
    return mido.Message('sysex', data=[SX_TAG, CMD_ROUTE_CLEAR])


def scene_save(scene: int) -> mido.Message:
    return mido.Message('sysex', data=[SX_TAG, CMD_SCENE_SAVE, scene & 0x07])


def scene_recall(scene: int) -> mido.Message:
    return mido.Message('sysex', data=[SX_TAG, CMD_SCENE_RECALL, scene & 0x07])


# ── Parser ──────────────────────────────────────────────────────────────────


def parse(msg: mido.Message) -> tuple[int, tuple[int, ...]] | None:
    """Parse an incoming sysex. Returns (opcode, payload) or None."""
    if msg.type != 'sysex':
        return None
    data = tuple(msg.data)
    if len(data) < 2 or data[0] != SX_TAG:
        return None
    return data[1], data[2:]


# ── Typed event objects (bridge -> Mac) ──────────────────────────────────────


@dataclass(frozen=True)
class CCValue:
    channel: int
    cc: int
    value: int


@dataclass(frozen=True)
class NoteEvent:
    channel: int
    note: int
    velocity: int
    on: bool


@dataclass(frozen=True)
class HelloAck:
    major: int
    minor: int


@dataclass(frozen=True)
class PageAck:
    page: int


@dataclass(frozen=True)
class Health:
    """Bridge health snapshot."""
    msgs_in: int      # total inbound MIDI event count (14-bit, may wrap)
    msgs_out: int     # total outbound MIDI event count (14-bit, may wrap)
    routes: int       # number of active per-page routes
    scene_mask: int   # bitmask of occupied scene slots (bit 0 = scene 0)

    def has_scene(self, scene: int) -> bool:
        return bool(self.scene_mask & (1 << scene))


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
    if op == RSP_HEALTH and len(payload) >= 6:
        msgs_in = (payload[0] << 7) | payload[1]
        msgs_out = (payload[2] << 7) | payload[3]
        return Health(msgs_in=msgs_in, msgs_out=msgs_out,
                      routes=payload[4], scene_mask=payload[5])
    return None
