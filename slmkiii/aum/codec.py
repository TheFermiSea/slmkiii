"""AUM-specific enums for binary file decoding."""

from __future__ import annotations

import enum


class AumMsgType(enum.IntEnum):
    """Value stored at `specState.type` inside an .aum_midimap binding.

    Identifies which kind of MIDI message AUM should react to / emit for the
    bound parameter.
    """
    CC = 0
    NOTE = 1
    PROGRAM_CHANGE = 2
    PITCH_BEND = 3
    CHANNEL_PRESSURE = 4


# Backwards-compatible module-level constants — many existing call sites
# (and external consumers) reference these names directly.
MSG_TYPE_CC = AumMsgType.CC
MSG_TYPE_NOTE = AumMsgType.NOTE
MSG_TYPE_PROGRAM_CHANGE = AumMsgType.PROGRAM_CHANGE
MSG_TYPE_PITCH_BEND = AumMsgType.PITCH_BEND
MSG_TYPE_CHANNEL_PRESSURE = AumMsgType.CHANNEL_PRESSURE
