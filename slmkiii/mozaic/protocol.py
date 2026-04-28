"""SLMK-Bridge custom SysEx protocol — encoder/decoder.

The runtime+data architecture uses a private SysEx vocabulary distinct from
the SL MkIII InControl protocol so the two can't collide:

    F0 7D 53 4C 4D 4B  <msg_type>  <payload...>  F7

7D = SysEx non-commercial / educational manufacturer ID; "SLMK" magic
follows the manufacturer prefix to distinguish our protocol from anything
else that happens to use 7D.

Two roles communicate over this:
  - DATA   side: emits BEGIN_UPLOAD + DEFINE_* + COMMIT on @OnLoad
  - RUNTIME side: receives those, fills its dispatch tables, lights up

7-bit safety: ALL payload bytes are 0..127. Multi-byte ints use
little-endian 7-bit packing (2 bytes => 14-bit range 0..16383).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Iterable


SYSEX_START = 0xF0
SYSEX_END = 0xF7
NON_COMMERCIAL_MFG = 0x7D
SLMK_MAGIC = (0x53, 0x4C, 0x4D, 0x4B)   # 'S', 'L', 'M', 'K'

#: Full 6-byte prefix every SLMK message starts with (after F0).
HEADER = bytes([NON_COMMERCIAL_MFG, *SLMK_MAGIC])

# Protocol version — increment major for breaking changes
RUNTIME_VERSION = (1, 0, 0)


class MsgType(IntEnum):
    VERSION_QUERY = 0x01
    VERSION_REPLY = 0x02
    BEGIN_UPLOAD = 0x03
    DEFINE_PAGE = 0x04
    DEFINE_FOCUS_SET = 0x05
    DEFINE_KNOB_BINDING = 0x06
    DEFINE_FADER_BINDING = 0x07
    DEFINE_PAD_BINDING = 0x08
    DEFINE_BUTTON_LED = 0x09
    DEFINE_SCREEN_LABEL = 0x0A
    SUBSCRIBE_PLUGIN_ECHO = 0x0B
    COMMIT = 0x0C
    COMMIT_ACK = 0x0D
    ERROR_REPORT = 0x0E
    HEARTBEAT = 0x0F
    RESET = 0x10


class ErrorCode(IntEnum):
    UNKNOWN_MSG = 0x01
    BAD_LENGTH = 0x02
    RT_TOO_OLD = 0x03
    PAGE_OOR = 0x04
    FOCUS_OOR = 0x05
    TABLE_FULL = 0x06
    CRC_MISMATCH = 0x07


# ---------------------------------------------------------------------------
# 7-bit ascii encoding (high bit zero so it doesn't collide with status bytes)
# ---------------------------------------------------------------------------
def _ascii7(s: str, max_len: int) -> bytes:
    """Latin-1 strip, mask high bit, truncate to max_len."""
    bs = s.encode("ascii", errors="replace")[:max_len]
    return bytes(b & 0x7F for b in bs)


def _u14(value: int) -> tuple[int, int]:
    """14-bit little-endian split into two 7-bit bytes."""
    if not 0 <= value <= 0x3FFF:
        raise ValueError(f"u14 out of range: {value}")
    return value & 0x7F, (value >> 7) & 0x7F


def _u14_decode(lo: int, hi: int) -> int:
    return (hi & 0x7F) << 7 | (lo & 0x7F)


# ---------------------------------------------------------------------------
# Message dataclasses
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Message:
    msg_type: MsgType
    body: bytes


@dataclass(frozen=True)
class DefinePage:
    page_idx: int
    color: int
    name: str

    def encode(self) -> Message:
        nb = _ascii7(self.name, 16)
        body = bytes([self.page_idx & 0x7F, self.color & 0x7F, len(nb)]) + nb
        return Message(MsgType.DEFINE_PAGE, body)


@dataclass(frozen=True)
class DefineFocusSet:
    page_idx: int
    names: tuple[str, ...]

    def encode(self) -> Message:
        body = bytearray([self.page_idx & 0x7F, len(self.names) & 0x7F])
        for name in self.names:
            nb = _ascii7(name, 9)
            body.append(len(nb))
            body.extend(nb)
        return Message(MsgType.DEFINE_FOCUS_SET, bytes(body))


@dataclass(frozen=True)
class DefineBinding:
    """Used for both knob and fader bindings (msg_type chosen by caller)."""
    page_idx: int
    focus_idx: int     # 0 if page has no focus_set
    slot: int          # 0..7 column within the bank
    channel: int       # 1-indexed
    cc: int
    label: str

    def encode_as(self, msg_type: MsgType) -> Message:
        lb = _ascii7(self.label, 9)
        body = bytes([
            self.page_idx & 0x7F,
            self.focus_idx & 0x7F,
            self.slot & 0x7F,
            self.channel & 0x7F,
            self.cc & 0x7F,
            len(lb),
        ]) + lb
        return Message(msg_type, body)


@dataclass(frozen=True)
class DefinePadBinding:
    page_idx: int
    focus_idx: int
    slot: int           # 0..15
    channel: int        # 1-indexed
    note: int
    color: int          # SL palette idx

    def encode(self) -> Message:
        body = bytes([
            self.page_idx & 0x7F,
            self.focus_idx & 0x7F,
            self.slot & 0x7F,
            self.channel & 0x7F,
            self.note & 0x7F,
            self.color & 0x7F,
        ])
        return Message(MsgType.DEFINE_PAD_BINDING, body)


@dataclass(frozen=True)
class DefineButtonLed:
    page_idx: int
    button_idx: int
    color: int

    def encode(self) -> Message:
        body = bytes([
            self.page_idx & 0x7F,
            self.button_idx & 0x7F,
            self.color & 0x7F,
        ])
        return Message(MsgType.DEFINE_BUTTON_LED, body)


@dataclass(frozen=True)
class SubscribePluginEcho:
    channel: int
    cc_lo: int
    cc_hi: int

    def encode(self) -> Message:
        body = bytes([
            self.channel & 0x7F,
            self.cc_lo & 0x7F,
            self.cc_hi & 0x7F,
        ])
        return Message(MsgType.SUBSCRIBE_PLUGIN_ECHO, body)


@dataclass(frozen=True)
class BeginUpload:
    data_major: int = 1
    data_minor: int = 0
    requires_rt_major: int = 1

    def encode(self) -> Message:
        body = bytes([
            self.data_major & 0x7F,
            self.data_minor & 0x7F,
            self.requires_rt_major & 0x7F,
        ])
        return Message(MsgType.BEGIN_UPLOAD, body)


@dataclass(frozen=True)
class Commit:
    crc14: int = 0

    def encode(self) -> Message:
        lo, hi = _u14(self.crc14)
        return Message(MsgType.COMMIT, bytes([lo, hi]))


@dataclass(frozen=True)
class ErrorReport:
    last_msg_type: int
    code: ErrorCode
    ctx_lo: int = 0
    ctx_hi: int = 0

    def encode(self) -> Message:
        body = bytes([
            self.last_msg_type & 0x7F,
            int(self.code) & 0x7F,
            self.ctx_lo & 0x7F,
            self.ctx_hi & 0x7F,
        ])
        return Message(MsgType.ERROR_REPORT, body)


@dataclass(frozen=True)
class Heartbeat:
    seq: int = 0

    def encode(self) -> Message:
        return Message(MsgType.HEARTBEAT, bytes([self.seq & 0x7F]))


# ---------------------------------------------------------------------------
# Wire encoding
# ---------------------------------------------------------------------------
def encode_sysex(msg: Message) -> bytes:
    """Wrap a Message into a complete F0..F7 SysEx byte string."""
    return bytes([SYSEX_START]) + HEADER + bytes([msg.msg_type]) + msg.body + bytes([SYSEX_END])


def encode_inner(msg: Message) -> bytes:
    """Inner SysEx body (without F0/F7) — what slmkiii.mozaic.interp.send_sysex
    expects (it strips F0/F7 before delivering to @OnSysex)."""
    return HEADER + bytes([msg.msg_type]) + msg.body


def decode_sysex(data: bytes) -> Message | None:
    """Parse a SLMK-Bridge SysEx packet. Returns None if the prefix doesn't
    match (foreign manufacturer or non-SLMK 7D usage)."""
    if len(data) < 8:
        return None
    if data[0] == SYSEX_START:
        if data[-1] != SYSEX_END:
            return None
        body = data[1:-1]
    else:
        body = data
    if not body.startswith(HEADER):
        return None
    if len(body) < len(HEADER) + 1:
        return None
    msg_type_byte = body[len(HEADER)]
    try:
        msg_type = MsgType(msg_type_byte)
    except ValueError:
        return None
    payload = body[len(HEADER) + 1:]
    return Message(msg_type, payload)


# ---------------------------------------------------------------------------
# CRC for COMMIT — simple 14-bit running sum of all bytes uploaded between
# BEGIN_UPLOAD and COMMIT
# ---------------------------------------------------------------------------
def crc14(messages: Iterable[Message]) -> int:
    s = 0
    for m in messages:
        if m.msg_type in (MsgType.BEGIN_UPLOAD, MsgType.COMMIT):
            continue
        s += int(m.msg_type)
        for b in m.body:
            s += b & 0x7F
    return s & 0x3FFF
