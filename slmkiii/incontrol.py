"""InControl API for real-time control of SL MkIII LEDs, screens, and input.

This module implements the documented InControl API from Novation's
Programmer's Reference Guide. It communicates over the InControl USB
MIDI port (separate from the template MIDI port used by midi.py).

The InControl API supports:
- LED control: solid, flash, pulse colors (palette or RGB)
- Screen layouts: Empty, Knob, Box
- Screen properties: text, colour, value, RGB
- Notification text on center screen
- Input from buttons, knobs, faders, pads
- Device inquiry (firmware version)
"""
from __future__ import annotations

import enum
import time

import mido

import slmkiii.errors

# ---------------------------------------------------------------------------
# InControl SysEx header: F0 00 20 29 02 0A 01
# Note: 0x01 (InControl) vs 0x03 (template protocol in midi.py)
# ---------------------------------------------------------------------------
INCONTROL_SYSEX_HEADER = bytes([0xF0, 0x00, 0x20, 0x29, 0x02, 0x0A, 0x01])

# InControl SysEx command IDs (byte following the header)
_CMD_SET_LAYOUT = 0x01
_CMD_SET_SCREEN_PROPERTY = 0x02
_CMD_SET_LED = 0x03
_CMD_SET_NOTIFICATION = 0x04

# Screen layout indices
LAYOUT_EMPTY = 0x00
LAYOUT_KNOB = 0x01
LAYOUT_BOX = 0x02

# Screen property types
PROP_TEXT = 0x01
PROP_COLOUR = 0x02
PROP_VALUE = 0x03
PROP_RGB = 0x04

# LED behaviors (for SysEx RGB mode)
LED_SOLID = 0x01
LED_FLASH = 0x02
LED_PULSE = 0x03

# MIDI channels for LED control via Note/CC messages (0-indexed for mido)
_LED_CH_SOLID = 15   # Channel 16
_LED_CH_FLASH = 1    # Channel 2
_LED_CH_PULSE = 2    # Channel 3

# Center screen column index
COLUMN_CENTER = 8

# Port name substrings for InControl detection
_INCONTROL_IDENTIFIERS = ('InControl', 'MIDIIN2', 'MIDIOUT2')

# Reuse device identifier from midi.py to avoid duplication
from slmkiii.midi import _SL_MKIII_IDENTIFIERS

# Device inquiry (standard MIDI)
_DEVICE_INQUIRY = bytes([0xF0, 0x7E, 0x0A, 0x06, 0x01, 0xF7])


# ---------------------------------------------------------------------------
# LED index constants — every addressable LED on the SL MkIII
# ---------------------------------------------------------------------------
class LED(enum.IntEnum):
    """LED indices for the SL MkIII InControl API.

    These are used as the CC/Note data byte 1 for LED messages,
    and as the LED index in SysEx RGB messages.
    """
    # Soft buttons (CC indices match the control indices table)
    SOFT_BUTTON_1 = 0x04
    SOFT_BUTTON_2 = 0x05
    SOFT_BUTTON_3 = 0x06
    SOFT_BUTTON_4 = 0x07
    SOFT_BUTTON_5 = 0x08
    SOFT_BUTTON_6 = 0x09
    SOFT_BUTTON_7 = 0x0A
    SOFT_BUTTON_8 = 0x0B
    SOFT_BUTTON_9 = 0x0C
    SOFT_BUTTON_10 = 0x0D
    SOFT_BUTTON_11 = 0x0E
    SOFT_BUTTON_12 = 0x0F
    SOFT_BUTTON_13 = 0x10
    SOFT_BUTTON_14 = 0x11
    SOFT_BUTTON_15 = 0x12
    SOFT_BUTTON_16 = 0x13
    SOFT_BUTTON_17 = 0x14
    SOFT_BUTTON_18 = 0x15
    SOFT_BUTTON_19 = 0x16
    SOFT_BUTTON_20 = 0x17
    SOFT_BUTTON_21 = 0x18
    SOFT_BUTTON_22 = 0x19
    SOFT_BUTTON_23 = 0x1A
    SOFT_BUTTON_24 = 0x1B

    # Right soft buttons
    RIGHT_SOFT_UP = 0x1C
    RIGHT_SOFT_DOWN = 0x1D

    # Transport
    RECORD = 0x20
    REWIND = 0x21
    FAST_FORWARD = 0x22
    STOP = 0x23
    PLAY = 0x24
    LOOP = 0x25

    # Pads
    PAD_1 = 0x26
    PAD_2 = 0x27
    PAD_3 = 0x28
    PAD_4 = 0x29
    PAD_5 = 0x2A
    PAD_6 = 0x2B
    PAD_7 = 0x2C
    PAD_8 = 0x2D
    PAD_9 = 0x2E
    PAD_10 = 0x2F
    PAD_11 = 0x30
    PAD_12 = 0x31
    PAD_13 = 0x32
    PAD_14 = 0x33
    PAD_15 = 0x34
    PAD_16 = 0x35

    # LEDs above faders
    FADER_1 = 0x36
    FADER_2 = 0x37
    FADER_3 = 0x38
    FADER_4 = 0x39
    FADER_5 = 0x3A
    FADER_6 = 0x3B
    FADER_7 = 0x3C
    FADER_8 = 0x3D

    # Navigation / mode
    SCREEN_UP = 0x3E
    SCREEN_DOWN = 0x3F
    GRID = 0x40
    OPTIONS = 0x41
    DUPLICATE = 0x42
    CLEAR = 0x43

    # Scene launch (SCENE_LAUNCH_BOTTOM aliases SOFT_BUTTON_1 — same
    # physical LED, same SysEx index per Novation's programmer's guide)
    SCENE_LAUNCH_TOP = 0x03
    SCENE_LAUNCH_BOTTOM = 0x04

    # Track left/right
    TRACK_LEFT = 0x1E
    TRACK_RIGHT = 0x1F

    # Pads up/down
    PADS_UP = 0x00
    PADS_DOWN = 0x01


# Control CC/Note indices for reading input messages
class Control(enum.IntEnum):
    """CC/Note indices for controls that send input messages."""
    # Rotary knobs (CC, two's complement delta)
    KNOB_1 = 0x15
    KNOB_2 = 0x16
    KNOB_3 = 0x17
    KNOB_4 = 0x18
    KNOB_5 = 0x19
    KNOB_6 = 0x1A
    KNOB_7 = 0x1B
    KNOB_8 = 0x1C

    # Faders (CC, absolute 0-127)
    FADER_1 = 0x29
    FADER_2 = 0x2A
    FADER_3 = 0x2B
    FADER_4 = 0x2C
    FADER_5 = 0x2D
    FADER_6 = 0x2E
    FADER_7 = 0x2F
    FADER_8 = 0x30

    # Soft buttons (CC, 127=press, 0=release)
    SOFT_BUTTON_1 = 0x33
    SOFT_BUTTON_2 = 0x34
    SOFT_BUTTON_3 = 0x35
    SOFT_BUTTON_4 = 0x36
    SOFT_BUTTON_5 = 0x37
    SOFT_BUTTON_6 = 0x38
    SOFT_BUTTON_7 = 0x39
    SOFT_BUTTON_8 = 0x3A
    SOFT_BUTTON_9 = 0x3B
    SOFT_BUTTON_10 = 0x3C
    SOFT_BUTTON_11 = 0x3D
    SOFT_BUTTON_12 = 0x3E
    SOFT_BUTTON_13 = 0x3F
    SOFT_BUTTON_14 = 0x40
    SOFT_BUTTON_15 = 0x41
    SOFT_BUTTON_16 = 0x42
    SOFT_BUTTON_17 = 0x43
    SOFT_BUTTON_18 = 0x44
    SOFT_BUTTON_19 = 0x45
    SOFT_BUTTON_20 = 0x46
    SOFT_BUTTON_21 = 0x47
    SOFT_BUTTON_22 = 0x48
    SOFT_BUTTON_23 = 0x49
    SOFT_BUTTON_24 = 0x4A

    # Screen navigation (CC)
    SCREEN_UP = 0x51
    SCREEN_DOWN = 0x52

    # Scene launch (CC)
    SCENE_LAUNCH_TOP = 0x53
    SCENE_LAUNCH_BOTTOM = 0x54

    # Pads up/down (CC)
    PADS_UP = 0x55
    PADS_DOWN = 0x56

    # Right soft buttons (CC)
    RIGHT_SOFT_UP = 0x57
    RIGHT_SOFT_DOWN = 0x58

    # Grid / Options / Shift / Duplicate / Clear (CC)
    GRID = 0x59
    OPTIONS = 0x5A
    SHIFT = 0x5B
    DUPLICATE = 0x5C
    CLEAR = 0x5D

    # Track left/right (CC)
    TRACK_LEFT = 0x66
    TRACK_RIGHT = 0x67

    # Transport (CC)
    REWIND = 0x70
    FAST_FORWARD = 0x71
    STOP = 0x72
    PLAY = 0x73
    LOOP = 0x74
    RECORD = 0x75


class PadNote(enum.IntEnum):
    """Note indices for pad input messages.

    Pads use Note On/Off (not CC), so their indices occupy a separate
    namespace from Control CC indices. Values 0x60-0x6F overlap with
    Control.TRACK_LEFT/RIGHT by design — they are distinguished by
    MIDI message type (Note vs CC).
    """
    PAD_1 = 0x60
    PAD_2 = 0x61
    PAD_3 = 0x62
    PAD_4 = 0x63
    PAD_5 = 0x64
    PAD_6 = 0x65
    PAD_7 = 0x66
    PAD_8 = 0x67
    PAD_9 = 0x68
    PAD_10 = 0x69
    PAD_11 = 0x6A
    PAD_12 = 0x6B
    PAD_13 = 0x6C
    PAD_14 = 0x6D
    PAD_15 = 0x6E
    PAD_16 = 0x6F


# Pad notes: 96-119 (0x60-0x77 in the indices table)
_PAD_NOTE_RANGE = range(0x60, 0x78)

# CC indices for knobs (two's complement delta encoding)
_KNOB_CC_RANGE = range(0x15, 0x1D)

# CC indices for faders (absolute 0-127)
_FADER_CC_RANGE = range(0x29, 0x31)


def decode_knob_delta(midi_value: int) -> int:
    """Decode a two's complement knob delta from a MIDI value (0-127).

    Returns:
        Signed integer: 0 = no change, 1-63 = clockwise, -64 to -1 = counter-clockwise.
    """
    if midi_value == 0:
        return 0
    elif midi_value <= 63:
        return midi_value  # +1 to +63
    else:
        return midi_value - 128  # -64 to -1


# ---------------------------------------------------------------------------
# InControl port discovery
# ---------------------------------------------------------------------------

def find_incontrol_ports() -> dict[str, str | None]:
    """Find the InControl MIDI ports for the SL MkIII.

    The SL MkIII exposes multiple USB MIDI ports:
    - Regular MIDI port (for template SysEx, used by midi.py)
    - InControl port (for LED/screen/input control)

    On macOS: "Novation SL MkIII SL MkIII InControl"
    On Windows: "MIDIIN2 (Novation SL MkIII)" / "MIDIOUT2 (Novation SL MkIII)"

    Returns:
        Dict with 'input' and 'output' keys, each a port name string or None.

    Raises:
        ErrorMidiDeviceNotFound: If no InControl ports are detected.
    """
    all_ports = {
        'input': mido.get_input_names(),
        'output': mido.get_output_names(),
    }
    result: dict[str, str | None] = {'input': None, 'output': None}
    for direction in ('input', 'output'):
        for name in all_ports[direction]:
            # Must be an SL MkIII port AND an InControl port
            is_slmkiii = any(ident in name for ident in _SL_MKIII_IDENTIFIERS)
            is_incontrol = any(ident in name for ident in _INCONTROL_IDENTIFIERS)
            if is_slmkiii and is_incontrol:
                result[direction] = name
                break
    if result['input'] is None and result['output'] is None:
        raise slmkiii.errors.ErrorMidiDeviceNotFound(
            'No SL MkIII InControl ports found')
    return result


# ---------------------------------------------------------------------------
# InControlConnection — context manager for bidirectional InControl I/O
# ---------------------------------------------------------------------------

class InControlConnection:
    """Context manager for an InControl MIDI connection to the SL MkIII.

    Provides methods for LED control, screen management, and input reading.
    All communication goes through the InControl USB port.

    Usage::

        with InControlConnection() as ic:
            ic.set_led(LED.PAD_1, 72)            # Red pad
            ic.set_layout(LAYOUT_KNOB)
            ic.set_text(0, 0, "Filter")
            ic.notify("Hello!", "World")

    Args:
        input_port: Specific InControl input port name. Auto-detected if None.
        output_port: Specific InControl output port name. Auto-detected if None.
    """

    def __init__(self, input_port: str | None = None,
                 output_port: str | None = None):
        self._input_port_name = input_port
        self._output_port_name = output_port
        self._input = None
        self._output = None

    def __enter__(self) -> InControlConnection:
        if self._input_port_name is None or self._output_port_name is None:
            detected = find_incontrol_ports()
            if self._input_port_name is None:
                if detected['input'] is None:
                    raise slmkiii.errors.ErrorMidiDeviceNotFound(
                        'No SL MkIII InControl input port found')
                self._input_port_name = detected['input']
            if self._output_port_name is None:
                if detected['output'] is None:
                    raise slmkiii.errors.ErrorMidiDeviceNotFound(
                        'No SL MkIII InControl output port found')
                self._output_port_name = detected['output']

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

    # -- Low-level send helpers ------------------------------------------

    def _send_sysex(self, data: bytes):
        """Send a raw SysEx message (with F0/F7 framing)."""
        if self._output is None:
            raise RuntimeError('InControl connection is not open')
        # mido strips F0/F7
        payload = data
        if payload[0] == 0xF0 and payload[-1] == 0xF7:
            payload = payload[1:-1]
        msg = mido.Message('sysex', data=list(payload))
        self._output.send(msg)

    def _send_note_on(self, channel: int, note: int, velocity: int):
        """Send a Note On message."""
        if self._output is None:
            raise RuntimeError('InControl connection is not open')
        msg = mido.Message('note_on', channel=channel,
                           note=note, velocity=velocity)
        self._output.send(msg)

    # -- LED control -----------------------------------------------------

    def _set_led_channel(self, channel: int, index: int, color: int):
        """Send an LED color message on the specified MIDI channel."""
        if not (0 <= color <= 127):
            raise ValueError(f'Color index must be 0-127, got {color}')
        self._send_note_on(channel, index, color)

    def set_led(self, index: int, color: int):
        """Set an LED to a solid color from the 128-color palette.

        Args:
            index: LED index (use LED enum values).
            color: Color index 0-127 from the colour table. 0 = off.
        """
        self._set_led_channel(_LED_CH_SOLID, index, color)

    def flash_led(self, index: int, color: int):
        """Set an LED to flash between its solid color and a second color.

        Args:
            index: LED index (use LED enum values).
            color: Flash color index 0-127 from the colour table.
        """
        self._set_led_channel(_LED_CH_FLASH, index, color)

    def pulse_led(self, index: int, color: int):
        """Set an LED to pulse (ramp up/down) a single color.

        Args:
            index: LED index (use LED enum values).
            color: Pulse color index 0-127 from the colour table.
        """
        self._set_led_channel(_LED_CH_PULSE, index, color)

    def set_led_rgb(self, index: int, r: int, g: int, b: int,
                    behavior: int = LED_SOLID):
        """Set an LED to an arbitrary RGB color via SysEx.

        Args:
            index: LED index (use LED enum values).
            r: Red component 0-127.
            g: Green component 0-127.
            b: Blue component 0-127.
            behavior: LED_SOLID (1), LED_FLASH (2), or LED_PULSE (3).
        """
        for name, val in [('r', r), ('g', g), ('b', b)]:
            if not (0 <= val <= 127):
                raise ValueError(f'{name} must be 0-127, got {val}')
        if behavior not in (LED_SOLID, LED_FLASH, LED_PULSE):
            raise ValueError(f'behavior must be 1-3, got {behavior}')
        self._send_sysex(INCONTROL_SYSEX_HEADER + bytes([
            _CMD_SET_LED, index, behavior, r, g, b, 0xF7,
        ]))

    def clear_led(self, index: int):
        """Turn off a single LED (set to color 0 = black)."""
        self.set_led(index, 0)

    def clear_all_leds(self):
        """Turn off all addressable LEDs."""
        for led in LED:
            self.set_led(led.value, 0)

    # -- Screen control --------------------------------------------------

    def set_layout(self, layout: int):
        """Set the screen layout for all 8 knob columns.

        Changing layout clears all previously set properties (except
        center screen). Send properties after changing layout.

        Args:
            layout: LAYOUT_EMPTY (0), LAYOUT_KNOB (1), or LAYOUT_BOX (2).
        """
        if layout not in (LAYOUT_EMPTY, LAYOUT_KNOB, LAYOUT_BOX):
            raise ValueError(f'Layout must be 0-2, got {layout}')
        self._send_sysex(INCONTROL_SYSEX_HEADER + bytes([
            _CMD_SET_LAYOUT, layout, 0xF7,
        ]))

    def set_text(self, column: int, field_index: int, text: str):
        """Set a text field on a screen column.

        Args:
            column: 0-7 for knob columns, 8 for center screen.
            field_index: Text field index (layout-dependent, see docs).
            text: ASCII string, max 9 chars (18 for notification).
        """
        if not (0 <= column <= 8):
            raise ValueError(f'Column must be 0-8, got {column}')
        text_bytes = text.encode('ascii', errors='replace')[:9]
        self._send_sysex(INCONTROL_SYSEX_HEADER + bytes([
            _CMD_SET_SCREEN_PROPERTY, column,
            PROP_TEXT, field_index,
        ]) + text_bytes + bytes([0x00, 0xF7]))

    def set_color(self, column: int, obj_index: int, color: int):
        """Set a colour object on a screen column (from palette).

        Args:
            column: 0-7 for knob columns, 8 for center screen.
            obj_index: Colour object index (layout-dependent).
            color: Color index 0-127 from the colour table.
        """
        if not (0 <= column <= 8):
            raise ValueError(f'Column must be 0-8, got {column}')
        if not (0 <= color <= 127):
            raise ValueError(f'Color must be 0-127, got {color}')
        self._send_sysex(INCONTROL_SYSEX_HEADER + bytes([
            _CMD_SET_SCREEN_PROPERTY, column,
            PROP_COLOUR, obj_index, color, 0xF7,
        ]))

    def set_color_rgb(self, column: int, obj_index: int,
                      r: int, g: int, b: int):
        """Set a colour object on a screen column using RGB values.

        Args:
            column: 0-7 for knob columns, 8 for center screen.
            obj_index: Colour object index (layout-dependent).
            r: Red 0-127.
            g: Green 0-127.
            b: Blue 0-127.
        """
        if not (0 <= column <= 8):
            raise ValueError(f'Column must be 0-8, got {column}')
        for name, val in [('r', r), ('g', g), ('b', b)]:
            if not (0 <= val <= 127):
                raise ValueError(f'{name} must be 0-127, got {val}')
        self._send_sysex(INCONTROL_SYSEX_HEADER + bytes([
            _CMD_SET_SCREEN_PROPERTY, column,
            PROP_RGB, obj_index, r, g, b, 0xF7,
        ]))

    def set_value(self, column: int, field_index: int, value: int):
        """Set a value field on a screen column.

        For Knob layout, field 0 controls the knob icon position (0-127).
        For Knob layout, field 1 controls lower text selection (0-1).

        Args:
            column: 0-7 for knob columns, 8 for center screen.
            field_index: Value field index (layout-dependent).
            value: 0-127.
        """
        if not (0 <= column <= 8):
            raise ValueError(f'Column must be 0-8, got {column}')
        if not (0 <= value <= 127):
            raise ValueError(f'Value must be 0-127, got {value}')
        self._send_sysex(INCONTROL_SYSEX_HEADER + bytes([
            _CMD_SET_SCREEN_PROPERTY, column,
            PROP_VALUE, field_index, value, 0xF7,
        ]))

    def set_screen_properties(self, column: int,
                              properties: list[tuple[int, int, bytes | int | tuple[int, ...]]]):
        """Set multiple properties on a screen column in a single SysEx message.

        This batches updates so they take effect simultaneously.

        Args:
            column: 0-7 for knob columns, 8 for center screen.
            properties: List of (property_type, object_index, data) tuples.
                        data is bytes for text, int for colour/value.
        """
        if not (0 <= column <= 8):
            raise ValueError(f'Column must be 0-8, got {column}')
        payload = bytearray(INCONTROL_SYSEX_HEADER)
        payload.append(_CMD_SET_SCREEN_PROPERTY)
        for prop_type, obj_index, data in properties:
            payload.append(column)
            payload.append(prop_type)
            payload.append(obj_index)
            if isinstance(data, (bytes, bytearray)):
                payload.extend(data)
                payload.append(0x00)  # null terminator for text
            elif isinstance(data, tuple):
                payload.extend(data)  # RGB tuple
            else:
                payload.append(data)
        payload.append(0xF7)
        self._send_sysex(bytes(payload))

    def notify(self, line1: str, line2: str = ''):
        """Display a temporary notification on the center screen.

        The notification appears briefly then auto-disappears.
        Will not display if both lines are empty.

        Args:
            line1: First line, up to 18 characters.
            line2: Second line, up to 18 characters.
        """
        line1_bytes = line1.encode('ascii', errors='replace')[:18]
        line2_bytes = line2.encode('ascii', errors='replace')[:18]
        self._send_sysex(INCONTROL_SYSEX_HEADER + bytes([
            _CMD_SET_NOTIFICATION,
        ]) + line1_bytes + bytes([0x00]) +
            line2_bytes + bytes([0x00, 0xF7]))

    # -- High-level screen helpers ---------------------------------------

    def label_knob(self, knob: int, name: str, value: int = 0,
                   color: int | None = None):
        """Set up a knob column with label and value in Knob layout.

        Args:
            knob: Knob number 1-8.
            name: Display name (max 9 chars).
            value: Knob position 0-127 (shown on knob icon).
            color: Optional top bar color index.
        """
        column = knob - 1
        if not (0 <= column <= 7):
            raise ValueError(f'Knob must be 1-8, got {knob}')
        self.set_text(column, 0, name)
        self.set_value(column, 0, value)
        if color is not None:
            self.set_color(column, 0, color)

    def label_fader(self, fader: int, name: str,
                    color: int | None = None):
        """Set up a knob column label for a fader (in Knob or Box layout).

        Args:
            fader: Fader number 1-8.
            name: Display name (max 9 chars).
            color: Optional bar color index.
        """
        column = fader - 1
        if not (0 <= column <= 7):
            raise ValueError(f'Fader must be 1-8, got {fader}')
        self.set_text(column, 2, name)
        if color is not None:
            self.set_color(column, 2, color)

    # -- Input handling --------------------------------------------------

    def receive(self, timeout: float | None = 5.0) -> mido.Message | None:
        """Receive a single MIDI message from the InControl port.

        Args:
            timeout: Seconds to wait. None for blocking.

        Returns:
            A mido Message, or None on timeout.
        """
        if self._input is None:
            raise RuntimeError('InControl connection is not open')
        for msg in self._input.iter_pending():
            return msg
        if timeout is not None:
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                msg = self._input.poll()
                if msg is not None:
                    return msg
                time.sleep(0.001)
            return None
        else:
            for msg in self._input:
                return msg
        return None

    def poll_input(self) -> list[dict]:
        """Poll for all pending input messages, decoded.

        Returns:
            List of dicts with keys: 'type' (button/knob/fader/pad),
            'control' (index), 'value' (raw MIDI value),
            and type-specific fields like 'delta' for knobs,
            'pressed' for buttons, 'velocity' for pads.
        """
        if self._input is None:
            raise RuntimeError('InControl connection is not open')
        events = []
        for msg in self._input.iter_pending():
            event = self._decode_input(msg)
            if event is not None:
                events.append(event)
        return events

    def _decode_input(self, msg: mido.Message) -> dict | None:
        """Decode a MIDI message into a structured input event."""
        if msg.type == 'control_change' and msg.channel == _LED_CH_SOLID:
            cc = msg.control
            val = msg.value
            if cc in _KNOB_CC_RANGE:
                knob_num = cc - 0x15 + 1
                return {
                    'type': 'knob',
                    'control': cc,
                    'knob': knob_num,
                    'value': val,
                    'delta': decode_knob_delta(val),
                }
            elif cc in _FADER_CC_RANGE:
                fader_num = cc - 0x29 + 1
                return {
                    'type': 'fader',
                    'control': cc,
                    'fader': fader_num,
                    'value': val,
                }
            else:
                return {
                    'type': 'button',
                    'control': cc,
                    'value': val,
                    'pressed': val == 127,
                }
        elif msg.type in ('note_on', 'note_off') and msg.channel == _LED_CH_SOLID:
            note = msg.note
            vel = msg.velocity if msg.type == 'note_on' else 0
            if note in _PAD_NOTE_RANGE:
                pad_num = note - 0x60 + 1
                return {
                    'type': 'pad',
                    'control': note,
                    'pad': pad_num,
                    'velocity': vel,
                    'pressed': vel > 0,
                }
        return None

    # -- Device inquiry --------------------------------------------------

    def device_inquiry(self, timeout: float = 5.0) -> dict | None:
        """Send a SysEx Device Inquiry and parse the response.

        Returns:
            Dict with 'family_code', 'member_code', 'firmware_version' keys,
            or None if no response.
        """
        self._send_sysex(_DEVICE_INQUIRY)
        start = time.monotonic()
        while time.monotonic() - start < timeout:
            msg = self.receive(timeout=timeout - (time.monotonic() - start))
            if msg is None:
                return None
            if msg.type == 'sysex':
                data = list(msg.data)
                # Expected: 7E ID 06 02 00 20 29 fc1 fc2 fm1 fm2 R1 R2 R3 R4
                if len(data) >= 14 and data[2] == 0x06 and data[3] == 0x02:
                    fc1, fc2 = data[7], data[8]
                    fm1, fm2 = data[9], data[10]
                    r1, r2, r3, r4 = data[11], data[12], data[13], data[14]
                    return {
                        'family_code': (fc1, fc2),
                        'member_code': (fm1, fm2),
                        'firmware_version': f'{r1}{r2}{r3}{r4}',
                    }
        return None
