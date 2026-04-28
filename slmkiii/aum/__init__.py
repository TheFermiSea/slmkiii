"""AUM (Kymatica) file format tools — read/write .aum_midimap and .aumproj.

AUM stores its data as NSKeyedArchiver binary property lists. The submodules
here decode and encode them:

  - codec    : enums for AUM-specific values (MIDI message types, etc.)
  - archiver : low-level NSKeyedArchiver decoder/encoder
  - midimap  : .aum_midimap reader/writer + AumMidiMapping dataclass
  - session  : .aumproj reader + AumPlugin/AumChannel/AumSession dataclasses
  - cli      : `inspect-mapping` / `inspect-session` CLI

The most common imports are re-exported here.
"""
from slmkiii.aum.codec import (
    AumMsgType,
    MSG_TYPE_CC,
    MSG_TYPE_NOTE,
    MSG_TYPE_PROGRAM_CHANGE,
    MSG_TYPE_PITCH_BEND,
    MSG_TYPE_CHANNEL_PRESSURE,
)
from slmkiii.aum.archiver import (
    ArchiverBuilder,
    decode_keyed_archiver,
)
from slmkiii.aum.midimap import (
    AumMidiMapping,
    read_aum_midimap,
    write_aum_midimap,
    generate_midimap_bytes,
)
from slmkiii.aum.session import (
    AumChannel,
    AumPlugin,
    AumSession,
    read_aum_session,
)

__all__ = [
    # codec
    'AumMsgType',
    'MSG_TYPE_CC', 'MSG_TYPE_NOTE', 'MSG_TYPE_PROGRAM_CHANGE',
    'MSG_TYPE_PITCH_BEND', 'MSG_TYPE_CHANNEL_PRESSURE',
    # archiver
    'ArchiverBuilder', 'decode_keyed_archiver',
    # midimap
    'AumMidiMapping', 'read_aum_midimap', 'write_aum_midimap',
    'generate_midimap_bytes',
    # session
    'AumChannel', 'AumPlugin', 'AumSession', 'read_aum_session',
]
