"""Shared MIDI message formatter used by sniff_both.py and sl_ipad_bridge.py."""

from __future__ import annotations

import mido


def fmt(msg: mido.Message) -> str:
    if msg.type == 'control_change':
        return f'CC ch{msg.channel + 1:>2} cc={msg.control:>3} val={msg.value:>3}'
    if msg.type == 'note_on':
        return f'NoteOn ch{msg.channel + 1:>2} note={msg.note:>3} vel={msg.velocity:>3}'
    if msg.type == 'note_off':
        return f'NoteOff ch{msg.channel + 1:>2} note={msg.note:>3} vel={msg.velocity:>3}'
    if msg.type == 'sysex':
        body = ' '.join(f'{b:02X}' for b in msg.data[:24])
        more = '...' if len(msg.data) > 24 else ''
        return f'SysEx [{len(msg.data)}B] {body}{more}'
    if msg.type == 'pitchwheel':
        return f'PitchBend ch{msg.channel + 1:>2} val={msg.pitch}'
    return msg.type
