"""SL MkIII SysEx protocol — single source of truth for all magic bytes.

The SL MkIII speaks two related but distinct SysEx dialects on its two USB
ports, both rooted in Novation's standard manufacturer header:

    F0 00 20 29 02 0A <port_kind> <command> <payload...> F7

  port_kind = 0x01  ->  InControl live API   (LEDs, screens, notifications)
  port_kind = 0x03  ->  Template push/pull   (binary template blocks)

This module exposes typed `IntEnum`s for every byte that has meaning, plus
pre-built header byte sequences. Anything elsewhere in the codebase that
uses a raw hex literal for SL MkIII protocol bytes should import from here.
"""

from __future__ import annotations

import enum

# ---------------------------------------------------------------------------
# Universal SysEx framing
# ---------------------------------------------------------------------------
SYSEX_START = 0xF0
SYSEX_END = 0xF7

# Universal MIDI Device Inquiry — F0 7E <id> 06 01 F7
DEVICE_INQUIRY = bytes([0xF0, 0x7E, 0x0A, 0x06, 0x01, 0xF7])


# ---------------------------------------------------------------------------
# Novation SL MkIII manufacturer / product identifier
# ---------------------------------------------------------------------------
class NovationHeader(enum.IntEnum):
    """The first 6 SysEx bytes (after F0) identifying a Novation SL MkIII msg."""
    MFG_0 = 0x00
    MFG_1 = 0x20
    MFG_2 = 0x29
    DEVICE_FAMILY = 0x02
    DEVICE_MODEL = 0x0A


class PortKind(enum.IntEnum):
    """The 7th SysEx byte selecting which dialect (InControl vs template)."""
    INCONTROL = 0x01
    TEMPLATE = 0x03


_NOVATION_PREFIX = bytes([
    SYSEX_START,
    NovationHeader.MFG_0,
    NovationHeader.MFG_1,
    NovationHeader.MFG_2,
    NovationHeader.DEVICE_FAMILY,
    NovationHeader.DEVICE_MODEL,
])

#: Header for InControl LED/screen/notification SysEx (F0 00 20 29 02 0A 01).
INCONTROL_HEADER = _NOVATION_PREFIX + bytes([PortKind.INCONTROL])

#: Header for template push/pull / dump SysEx (F0 00 20 29 02 0A 03).
TEMPLATE_HEADER = _NOVATION_PREFIX + bytes([PortKind.TEMPLATE])


# ---------------------------------------------------------------------------
# InControl protocol (port_kind = 0x01)
# ---------------------------------------------------------------------------
class InControlCmd(enum.IntEnum):
    """The 8th SysEx byte selecting the InControl command."""
    SET_LAYOUT = 0x01
    SET_SCREEN_PROPERTY = 0x02
    SET_LED = 0x03
    SET_NOTIFICATION = 0x04


class Layout(enum.IntEnum):
    """Top-row screen layouts. Set with InControlCmd.SET_LAYOUT."""
    EMPTY = 0x00
    KNOB = 0x01
    BOX = 0x02


class ScreenProp(enum.IntEnum):
    """Per-column screen property kinds. Used in SET_SCREEN_PROPERTY payload."""
    TEXT = 0x01
    COLOUR = 0x02
    VALUE = 0x03
    RGB = 0x04


# Center column index for screen commands (0..7 = knob columns, 8 = center).
COLUMN_CENTER = 8


class LedBehavior(enum.IntEnum):
    """LED animation behaviour, only used for the SET_LED RGB SysEx form."""
    SOLID = 0x01
    FLASH = 0x02
    PULSE = 0x03


class LedChannel(enum.IntEnum):
    """0-indexed MIDI channel that selects LED behaviour for the simple
    Note/CC LED-set form (see Programmer's Reference Guide p.3-4)."""
    SOLID = 15   # MIDI channel 16
    FLASH = 1    # MIDI channel 2
    PULSE = 2    # MIDI channel 3


# ---------------------------------------------------------------------------
# Template protocol (port_kind = 0x03)
# ---------------------------------------------------------------------------
class TemplateBlock(enum.IntEnum):
    """Block kind in the SL MkIII template wire format."""
    INIT = 0x01
    DATA = 0x02
    CRC = 0x03


# ---------------------------------------------------------------------------
# Color palette (subset of the 128-entry SL MkIII palette)
#
# Provided as named constants for ergonomics. The full palette is documented
# in the Programmer's Reference Guide; these are the entries used by the
# live controller and diagnostics.
# ---------------------------------------------------------------------------
class Color(enum.IntEnum):
    OFF = 0
    DIM_WHITE = 1
    WHITE = 3
    DIM_RED = 7
    RED = 5
    ORANGE = 9
    YELLOW = 13
    GREEN = 21
    DIM_GREEN = 23
    CYAN = 33
    BLUE = 37
    PURPLE = 49
    MAGENTA = 53
