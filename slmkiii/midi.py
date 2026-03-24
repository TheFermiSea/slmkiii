"""MIDI device discovery and connection management for SL MkIII."""
from __future__ import annotations

import mido

import slmkiii.errors

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
            import time
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
