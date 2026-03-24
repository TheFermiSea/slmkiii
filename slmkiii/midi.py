"""MIDI device discovery and connection management for SL MkIII."""
from __future__ import annotations

import struct
import time

import mido

import slmkiii.errors
from slmkiii.template import (
    SYSEX_HEADER, SYSEX_END, SYSEX_BLOCK_INIT, SYSEX_TEMPLATE_SIZE,
)

# Port name substrings that identify the SL MkIII.
# The device typically appears as "Novation SL MkIII" or "Novation SL MkIII SL MkIII MIDI".
_SL_MKIII_IDENTIFIERS = ('SL MkIII',)


def list_midi_ports() -> dict[str, list[str]]:
    """List all available MIDI input and output port names.

    Returns:
        Dict with keys 'input' and 'output', each a list of port name strings.
    """
    return {
        'input': mido.get_input_names(),
        'output': mido.get_output_names(),
    }


def find_slmkiii() -> dict[str, list[str]]:
    """Scan MIDI ports for the Novation SL MkIII.

    Returns:
        Dict with keys 'input' and 'output', each a list of matching port names.

    Raises:
        ErrorMidiDeviceNotFound: If no SL MkIII ports are detected.
    """
    ports = list_midi_ports()
    result = {'input': [], 'output': []}
    for direction in ('input', 'output'):
        for name in ports[direction]:
            if any(ident in name for ident in _SL_MKIII_IDENTIFIERS):
                result[direction].append(name)
    if not result['input'] and not result['output']:
        raise slmkiii.errors.ErrorMidiDeviceNotFound()
    return result


class MidiConnection:
    """Context manager for an open MIDI connection to the SL MkIII.

    Usage::

        with MidiConnection() as conn:
            conn.send(sysex_bytes)
            response = conn.receive(timeout=5.0)

    Args:
        input_port: Specific input port name. Auto-detected if None.
        output_port: Specific output port name. Auto-detected if None.
    """

    def __init__(self, input_port: str | None = None,
                 output_port: str | None = None):
        self._input_port_name = input_port
        self._output_port_name = output_port
        self._input = None
        self._output = None

    def __enter__(self) -> MidiConnection:
        if self._input_port_name is None or self._output_port_name is None:
            detected = find_slmkiii()
            if self._input_port_name is None:
                if not detected['input']:
                    raise slmkiii.errors.ErrorMidiDeviceNotFound(
                        'No SL MkIII input ports found')
                self._input_port_name = detected['input'][0]
            if self._output_port_name is None:
                if not detected['output']:
                    raise slmkiii.errors.ErrorMidiDeviceNotFound(
                        'No SL MkIII output ports found')
                self._output_port_name = detected['output'][0]

        self._input = mido.open_input(self._input_port_name)
        self._output = mido.open_output(self._output_port_name)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

    def close(self):
        """Close both input and output ports."""
        if self._input is not None:
            self._input.close()
            self._input = None
        if self._output is not None:
            self._output.close()
            self._output = None

    @property
    def input_port_name(self) -> str | None:
        return self._input_port_name

    @property
    def output_port_name(self) -> str | None:
        return self._output_port_name

    def send(self, data: bytes):
        """Send a SysEx message to the SL MkIII.

        Args:
            data: Raw SysEx bytes (must start with 0xF0 and end with 0xF7).
        """
        if self._output is None:
            raise RuntimeError('MIDI connection is not open')
        # mido SysEx messages exclude the 0xF0/0xF7 framing bytes
        if data[0] == 0xF0 and data[-1] == 0xF7:
            data = data[1:-1]
        msg = mido.Message('sysex', data=list(data))
        self._output.send(msg)

    def receive(self, timeout: float | None = 5.0) -> bytes | None:
        """Receive a SysEx message from the SL MkIII.

        Args:
            timeout: Seconds to wait for a message. None for blocking.

        Returns:
            Raw SysEx bytes (including 0xF0/0xF7 framing), or None on timeout.
        """
        if self._input is None:
            raise RuntimeError('MIDI connection is not open')
        for msg in self._input.iter_pending():
            if msg.type == 'sysex':
                return bytes([0xF0] + list(msg.data) + [0xF7])
        # iter_pending exhausted; block with poll
        if timeout is not None:
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                msg = self._input.poll()
                if msg is not None and msg.type == 'sysex':
                    return bytes([0xF0] + list(msg.data) + [0xF7])
                time.sleep(0.01)
            return None
        else:
            # Blocking receive
            for msg in self._input:
                if msg.type == 'sysex':
                    return bytes([0xF0] + list(msg.data) + [0xF7])
        return None

    def receive_all(self, timeout: float = 5.0) -> bytes:
        """Receive multiple SysEx messages and concatenate them.

        Collects messages until no new message arrives within *timeout*
        seconds of the last received message. This is used for template
        dumps which arrive as multiple SysEx blocks.

        Returns:
            Concatenated raw SysEx bytes.
        """
        chunks = []
        while True:
            msg = self.receive(timeout=timeout)
            if msg is None:
                break
            chunks.append(msg)
        return b''.join(chunks)


# SL MkIII SysEx protocol constants
# SYSEX_HEADER includes the F0 start byte as byte 0 (240).
# _SYSEX_HEADER_BYTES packs the full header for building complete SysEx messages.
_SYSEX_HEADER_BYTES = struct.pack('>7B', *SYSEX_HEADER)


def _patch_sysex_slot(sysex_data: bytes, device_slot: int) -> bytes:
    """Patch the slot byte (byte 17) in all SysEx blocks.

    The SL MkIII requires each SysEx block to carry the target slot
    address at byte offset 17. export_sysex() leaves this as 0x00
    since it's not needed for file export — this function patches
    it for device communication.
    """
    blocks = _split_sysex_blocks(sysex_data)
    patched = []
    for block in blocks:
        if len(block) >= 18:
            block = bytearray(block)
            block[17] = device_slot
            block = bytes(block)
        patched.append(block)
    return patched


def push_template(template, slot: int = 0,
                  connection: MidiConnection | None = None) -> None:
    """Send a template to the SL MkIII over MIDI.

    Args:
        template: A slmkiii.Template instance.
        slot: Template slot on the device (0-7).
        connection: An open MidiConnection. If None, auto-discovers the
                    SL MkIII and opens a temporary connection.

    Raises:
        ValueError: If slot is out of range.
        ErrorMidiDeviceNotFound: If no SL MkIII is detected.
    """
    if not (0 <= slot <= 7):
        raise ValueError(f'Template slot must be 0-7, got {slot}')

    sysex_data = template.export_sysex()
    device_slot = _TEMPLATE_SLOT_OFFSET + slot
    blocks = _patch_sysex_slot(sysex_data, device_slot)

    def _do_push(conn):
        for block in blocks:
            conn.send(block)
            time.sleep(0.02)  # 20ms inter-block delay

    if connection is not None:
        _do_push(connection)
    else:
        with MidiConnection() as conn:
            _do_push(conn)


def _build_dump_request(group: int, slot: int) -> bytes:
    """Build a SysEx dump request message.

    The SL MkIII dump request format (reverse-engineered from Novation Components):
        F0 00 20 29 02 0A 03 01 00 00 00 00 00 00 00 00 [group] [slot] 02 F7

    The trailing 0x02 means "read/request" (vs 0x01 for write/data).

    Groups:
        0x01: Sessions (slots 0x00-0x3F = 64 sessions)
        0x02: Templates (slots 0x00-0x3F = up to 64 templates)
    """
    return _SYSEX_HEADER_BYTES + bytes([
        SYSEX_BLOCK_INIT,
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,  # 8 zero bytes
        group, slot,
        0x02,  # read request
        SYSEX_END,
    ])


# Template slots in the SL MkIII are in group 0x02.
# The device has 8 template slots mapped to group-2 slot indices.
# From sniffed traffic, templates appear at slots 0x38-0x3F in group 0x02.
_TEMPLATE_GROUP = 0x02
_TEMPLATE_SLOT_OFFSET = 0x38  # Template 0 = group 2, slot 0x38


def pull_template(slot: int = 0,
                  connection: MidiConnection | None = None,
                  timeout: float = 10.0):
    """Request and receive a template dump from the SL MkIII.

    Sends a SysEx dump request and collects the multi-block response,
    returning a Template object.

    Args:
        slot: Template slot to pull (0-7).
        connection: An open MidiConnection. If None, auto-discovers.
        timeout: Seconds to wait for the dump response.

    Returns:
        A slmkiii.Template instance parsed from the device response.

    Raises:
        ValueError: If slot is out of range.
        ErrorMidiDeviceNotFound: If no SL MkIII is detected.
        TimeoutError: If no response is received within timeout.
    """
    if not (0 <= slot <= 7):
        raise ValueError(f'Template slot must be 0-7, got {slot}')

    request = _build_dump_request(_TEMPLATE_GROUP,
                                  _TEMPLATE_SLOT_OFFSET + slot)

    def _do_pull(conn):
        # Flush any pending messages
        while conn.receive(timeout=0.1) is not None:
            pass
        conn.send(request)
        response = conn.receive_all(timeout=timeout)
        if not response:
            raise TimeoutError(
                f'No template dump received within {timeout}s')
        # Import here to avoid circular import at module level
        from slmkiii.template import Template
        return Template(response)

    if connection is not None:
        return _do_pull(connection)
    else:
        with MidiConnection() as conn:
            return _do_pull(conn)


def _split_sysex_blocks(data: bytes) -> list[bytes]:
    """Split concatenated SysEx data into individual F0...F7 messages."""
    blocks = []
    i = 0
    while i < len(data):
        if data[i] == 0xF0:
            end = data.index(0xF7, i)
            blocks.append(data[i:end + 1])
            i = end + 1
        else:
            i += 1
    return blocks
