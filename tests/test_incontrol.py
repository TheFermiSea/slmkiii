"""Tests for the InControl API module.

These tests verify protocol encoding without requiring a physical SL MkIII.
MIDI I/O is mocked to capture outgoing messages and inject incoming ones.
"""
import unittest
from unittest.mock import MagicMock, patch

import mido

import slmkiii.errors
from slmkiii.incontrol import (
    InControlConnection,
    LED, Control, PadNote,
    LAYOUT_EMPTY, LAYOUT_KNOB, LAYOUT_BOX,
    PROP_TEXT, PROP_COLOUR, PROP_VALUE, PROP_RGB,
    LED_SOLID, LED_FLASH, LED_PULSE,
    COLUMN_CENTER,
    decode_knob_delta,
    find_incontrol_ports,
)


class MockInControlConnection(InControlConnection):
    """InControlConnection with mocked MIDI ports for testing."""

    def __init__(self):
        super().__init__(input_port='mock_in', output_port='mock_out')
        self._sent_messages = []
        self._mock_input_messages = []

    def __enter__(self):
        self._output = MagicMock()
        self._input = MagicMock()

        def capture_send(msg):
            self._sent_messages.append(msg)
        self._output.send = capture_send

        def iter_pending():
            msgs = list(self._mock_input_messages)
            self._mock_input_messages.clear()
            return iter(msgs)
        self._input.iter_pending = iter_pending
        self._input.poll = MagicMock(return_value=None)
        return self

    def __exit__(self, *args):
        self._input = None
        self._output = None
        return False

    def inject_input(self, msg):
        """Queue a mock input message for reading."""
        self._mock_input_messages.append(msg)

    @property
    def sent(self):
        return self._sent_messages

    def last_sent(self):
        return self._sent_messages[-1] if self._sent_messages else None


class TestDecodeKnobDelta(unittest.TestCase):
    def test_zero(self):
        self.assertEqual(decode_knob_delta(0), 0)

    def test_clockwise(self):
        self.assertEqual(decode_knob_delta(1), 1)
        self.assertEqual(decode_knob_delta(63), 63)

    def test_counter_clockwise(self):
        self.assertEqual(decode_knob_delta(64), -64)
        self.assertEqual(decode_knob_delta(127), -1)

    def test_midpoint(self):
        self.assertEqual(decode_knob_delta(65), -63)


class TestLEDControl(unittest.TestCase):
    def test_set_led_solid(self):
        with MockInControlConnection() as ic:
            ic.set_led(LED.PAD_1, 72)
            msg = ic.last_sent()
            self.assertEqual(msg.type, 'note_on')
            self.assertEqual(msg.channel, 15)  # Channel 16
            self.assertEqual(msg.note, LED.PAD_1)
            self.assertEqual(msg.velocity, 72)

    def test_flash_led(self):
        with MockInControlConnection() as ic:
            ic.flash_led(LED.PLAY, 48)
            msg = ic.last_sent()
            self.assertEqual(msg.type, 'note_on')
            self.assertEqual(msg.channel, 1)  # Channel 2
            self.assertEqual(msg.note, LED.PLAY)
            self.assertEqual(msg.velocity, 48)

    def test_pulse_led(self):
        with MockInControlConnection() as ic:
            ic.pulse_led(LED.RECORD, 96)
            msg = ic.last_sent()
            self.assertEqual(msg.type, 'note_on')
            self.assertEqual(msg.channel, 2)  # Channel 3
            self.assertEqual(msg.note, LED.RECORD)
            self.assertEqual(msg.velocity, 96)

    def test_set_led_rgb(self):
        with MockInControlConnection() as ic:
            ic.set_led_rgb(LED.PAD_5, 100, 50, 25, LED_SOLID)
            msg = ic.last_sent()
            self.assertEqual(msg.type, 'sysex')
            # mido strips F0 but not F7
            data = list(msg.data)
            # Header: 00 20 29 02 0A 01
            self.assertEqual(data[:6], [0x00, 0x20, 0x29, 0x02, 0x0A, 0x01])
            # Command: 03 (set LED)
            self.assertEqual(data[6], 0x03)
            # LED index
            self.assertEqual(data[7], LED.PAD_5)
            # Behavior
            self.assertEqual(data[8], LED_SOLID)
            # RGB
            self.assertEqual(data[9:12], [100, 50, 25])

    def test_set_led_rgb_flash(self):
        with MockInControlConnection() as ic:
            ic.set_led_rgb(LED.FADER_1, 0, 127, 0, LED_FLASH)
            msg = ic.last_sent()
            data = list(msg.data)
            self.assertEqual(data[8], LED_FLASH)

    def test_set_led_rgb_pulse(self):
        with MockInControlConnection() as ic:
            ic.set_led_rgb(LED.STOP, 127, 0, 0, LED_PULSE)
            msg = ic.last_sent()
            data = list(msg.data)
            self.assertEqual(data[8], LED_PULSE)

    def test_clear_led(self):
        with MockInControlConnection() as ic:
            ic.clear_led(LED.PAD_1)
            msg = ic.last_sent()
            self.assertEqual(msg.velocity, 0)

    def test_invalid_color(self):
        with MockInControlConnection() as ic:
            with self.assertRaises(ValueError):
                ic.set_led(LED.PAD_1, 128)
            with self.assertRaises(ValueError):
                ic.set_led(LED.PAD_1, -1)

    def test_invalid_rgb(self):
        with MockInControlConnection() as ic:
            with self.assertRaises(ValueError):
                ic.set_led_rgb(LED.PAD_1, 128, 0, 0)
            with self.assertRaises(ValueError):
                ic.set_led_rgb(LED.PAD_1, 0, 128, 0)
            with self.assertRaises(ValueError):
                ic.set_led_rgb(LED.PAD_1, 0, 0, 128)

    def test_invalid_behavior(self):
        with MockInControlConnection() as ic:
            with self.assertRaises(ValueError):
                ic.set_led_rgb(LED.PAD_1, 0, 0, 0, behavior=0)
            with self.assertRaises(ValueError):
                ic.set_led_rgb(LED.PAD_1, 0, 0, 0, behavior=4)


class TestScreenControl(unittest.TestCase):
    def test_set_layout_knob(self):
        with MockInControlConnection() as ic:
            ic.set_layout(LAYOUT_KNOB)
            msg = ic.last_sent()
            data = list(msg.data)
            self.assertEqual(data[6], 0x01)  # Set Layout command
            self.assertEqual(data[7], LAYOUT_KNOB)

    def test_set_layout_box(self):
        with MockInControlConnection() as ic:
            ic.set_layout(LAYOUT_BOX)
            msg = ic.last_sent()
            data = list(msg.data)
            self.assertEqual(data[7], LAYOUT_BOX)

    def test_set_layout_empty(self):
        with MockInControlConnection() as ic:
            ic.set_layout(LAYOUT_EMPTY)
            msg = ic.last_sent()
            data = list(msg.data)
            self.assertEqual(data[7], LAYOUT_EMPTY)

    def test_invalid_layout(self):
        with MockInControlConnection() as ic:
            with self.assertRaises(ValueError):
                ic.set_layout(3)

    def test_set_text(self):
        with MockInControlConnection() as ic:
            ic.set_text(0, 0, 'Filter')
            msg = ic.last_sent()
            data = list(msg.data)
            # Header + cmd(0x02) + column(0) + prop_type(0x01) + obj_index(0)
            self.assertEqual(data[6], 0x02)  # Set Screen Properties
            self.assertEqual(data[7], 0)     # column 0
            self.assertEqual(data[8], PROP_TEXT)
            self.assertEqual(data[9], 0)     # field index
            # ASCII text
            text_bytes = bytes(data[10:-1])  # before null terminator
            self.assertEqual(text_bytes, b'Filter')
            # Null terminator
            self.assertEqual(data[-1], 0x00)

    def test_set_text_truncation(self):
        with MockInControlConnection() as ic:
            ic.set_text(0, 0, 'VeryLongName')
            msg = ic.last_sent()
            data = list(msg.data)
            # Text should be truncated to 9 chars
            text_bytes = bytes(data[10:-1])
            self.assertEqual(len(text_bytes), 9)
            self.assertEqual(text_bytes, b'VeryLongN')

    def test_set_text_center_screen(self):
        with MockInControlConnection() as ic:
            ic.set_text(COLUMN_CENTER, 0, 'Center')
            msg = ic.last_sent()
            data = list(msg.data)
            self.assertEqual(data[7], 8)  # column 8

    def test_set_color(self):
        with MockInControlConnection() as ic:
            ic.set_color(3, 0, 65)
            msg = ic.last_sent()
            data = list(msg.data)
            self.assertEqual(data[6], 0x02)
            self.assertEqual(data[7], 3)      # column
            self.assertEqual(data[8], PROP_COLOUR)
            self.assertEqual(data[9], 0)      # obj index
            self.assertEqual(data[10], 65)    # color

    def test_set_color_rgb(self):
        with MockInControlConnection() as ic:
            ic.set_color_rgb(5, 1, 100, 50, 25)
            msg = ic.last_sent()
            data = list(msg.data)
            self.assertEqual(data[8], PROP_RGB)
            self.assertEqual(data[9], 1)       # obj index
            self.assertEqual(data[10:13], [100, 50, 25])

    def test_set_value(self):
        with MockInControlConnection() as ic:
            ic.set_value(2, 0, 64)
            msg = ic.last_sent()
            data = list(msg.data)
            self.assertEqual(data[8], PROP_VALUE)
            self.assertEqual(data[9], 0)   # field index
            self.assertEqual(data[10], 64)

    def test_invalid_column(self):
        with MockInControlConnection() as ic:
            with self.assertRaises(ValueError):
                ic.set_text(9, 0, 'Bad')
            with self.assertRaises(ValueError):
                ic.set_text(-1, 0, 'Bad')

    def test_invalid_color_value(self):
        with MockInControlConnection() as ic:
            with self.assertRaises(ValueError):
                ic.set_color(0, 0, 128)

    def test_invalid_value(self):
        with MockInControlConnection() as ic:
            with self.assertRaises(ValueError):
                ic.set_value(0, 0, 128)


class TestNotification(unittest.TestCase):
    def test_notify_single_line(self):
        with MockInControlConnection() as ic:
            ic.notify('Hello!')
            msg = ic.last_sent()
            data = list(msg.data)
            self.assertEqual(data[6], 0x04)  # notification command
            # First line: "Hello!" + 0x00
            text_start = 7
            hello = bytes(data[text_start:text_start + 6])
            self.assertEqual(hello, b'Hello!')
            self.assertEqual(data[text_start + 6], 0x00)  # null terminator
            # Second line: "" + 0x00
            self.assertEqual(data[text_start + 7], 0x00)

    def test_notify_two_lines(self):
        with MockInControlConnection() as ic:
            ic.notify('Line 1', 'Line 2')
            msg = ic.last_sent()
            data = list(msg.data)
            # Find null terminators
            null_pos = data.index(0x00, 7)
            line1 = bytes(data[7:null_pos])
            line2 = bytes(data[null_pos + 1:data.index(0x00, null_pos + 1)])
            self.assertEqual(line1, b'Line 1')
            self.assertEqual(line2, b'Line 2')

    def test_notify_truncation(self):
        with MockInControlConnection() as ic:
            ic.notify('A' * 30, 'B' * 30)
            msg = ic.last_sent()
            data = list(msg.data)
            # Count chars before first null
            null_pos = data.index(0x00, 7)
            self.assertEqual(null_pos - 7, 18)  # max 18 chars


class TestInputDecoding(unittest.TestCase):
    def test_button_press(self):
        with MockInControlConnection() as ic:
            msg = mido.Message('control_change', channel=15,
                               control=Control.PLAY, value=127)
            ic.inject_input(msg)
            events = ic.poll_input()
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0]['type'], 'button')
            self.assertTrue(events[0]['pressed'])
            self.assertEqual(events[0]['control'], Control.PLAY)

    def test_button_release(self):
        with MockInControlConnection() as ic:
            msg = mido.Message('control_change', channel=15,
                               control=Control.STOP, value=0)
            ic.inject_input(msg)
            events = ic.poll_input()
            self.assertEqual(len(events), 1)
            self.assertFalse(events[0]['pressed'])

    def test_knob_clockwise(self):
        with MockInControlConnection() as ic:
            msg = mido.Message('control_change', channel=15,
                               control=Control.KNOB_1, value=3)
            ic.inject_input(msg)
            events = ic.poll_input()
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0]['type'], 'knob')
            self.assertEqual(events[0]['knob'], 1)
            self.assertEqual(events[0]['delta'], 3)

    def test_knob_counter_clockwise(self):
        with MockInControlConnection() as ic:
            msg = mido.Message('control_change', channel=15,
                               control=Control.KNOB_3, value=125)
            ic.inject_input(msg)
            events = ic.poll_input()
            self.assertEqual(events[0]['type'], 'knob')
            self.assertEqual(events[0]['knob'], 3)
            self.assertEqual(events[0]['delta'], -3)

    def test_fader(self):
        with MockInControlConnection() as ic:
            msg = mido.Message('control_change', channel=15,
                               control=Control.FADER_1, value=64)
            ic.inject_input(msg)
            events = ic.poll_input()
            self.assertEqual(events[0]['type'], 'fader')
            self.assertEqual(events[0]['fader'], 1)
            self.assertEqual(events[0]['value'], 64)

    def test_pad_hit(self):
        with MockInControlConnection() as ic:
            msg = mido.Message('note_on', channel=15,
                               note=PadNote.PAD_1, velocity=100)
            ic.inject_input(msg)
            events = ic.poll_input()
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0]['type'], 'pad')
            self.assertEqual(events[0]['pad'], 1)
            self.assertEqual(events[0]['velocity'], 100)
            self.assertTrue(events[0]['pressed'])

    def test_pad_release(self):
        with MockInControlConnection() as ic:
            msg = mido.Message('note_off', channel=15,
                               note=PadNote.PAD_1, velocity=0)
            ic.inject_input(msg)
            events = ic.poll_input()
            self.assertEqual(events[0]['velocity'], 0)
            self.assertFalse(events[0]['pressed'])

    def test_multiple_events(self):
        with MockInControlConnection() as ic:
            ic.inject_input(mido.Message('control_change', channel=15,
                                         control=Control.FADER_1, value=10))
            ic.inject_input(mido.Message('control_change', channel=15,
                                         control=Control.FADER_2, value=20))
            events = ic.poll_input()
            self.assertEqual(len(events), 2)
            self.assertEqual(events[0]['fader'], 1)
            self.assertEqual(events[1]['fader'], 2)

    def test_ignore_wrong_channel(self):
        with MockInControlConnection() as ic:
            msg = mido.Message('control_change', channel=0,
                               control=Control.FADER_1, value=64)
            ic.inject_input(msg)
            events = ic.poll_input()
            self.assertEqual(len(events), 0)


class TestHighLevelHelpers(unittest.TestCase):
    def test_label_knob(self):
        with MockInControlConnection() as ic:
            ic.label_knob(1, 'Filter', value=64, color=72)
            # Should send 3 messages: text, value, color
            self.assertEqual(len(ic.sent), 3)

    def test_label_knob_no_color(self):
        with MockInControlConnection() as ic:
            ic.label_knob(1, 'Filter', value=64)
            # Should send 2 messages: text, value
            self.assertEqual(len(ic.sent), 2)

    def test_label_knob_invalid(self):
        with MockInControlConnection() as ic:
            with self.assertRaises(ValueError):
                ic.label_knob(0, 'Bad')
            with self.assertRaises(ValueError):
                ic.label_knob(9, 'Bad')

    def test_label_fader(self):
        with MockInControlConnection() as ic:
            ic.label_fader(1, 'Volume', color=48)
            self.assertEqual(len(ic.sent), 2)

    def test_label_fader_invalid(self):
        with MockInControlConnection() as ic:
            with self.assertRaises(ValueError):
                ic.label_fader(0, 'Bad')


class TestLEDEnum(unittest.TestCase):
    def test_all_pads_sequential(self):
        pads = [LED.PAD_1, LED.PAD_2, LED.PAD_3, LED.PAD_4,
                LED.PAD_5, LED.PAD_6, LED.PAD_7, LED.PAD_8,
                LED.PAD_9, LED.PAD_10, LED.PAD_11, LED.PAD_12,
                LED.PAD_13, LED.PAD_14, LED.PAD_15, LED.PAD_16]
        for i, pad in enumerate(pads):
            self.assertEqual(pad, 0x26 + i)

    def test_all_faders_sequential(self):
        faders = [LED.FADER_1, LED.FADER_2, LED.FADER_3, LED.FADER_4,
                  LED.FADER_5, LED.FADER_6, LED.FADER_7, LED.FADER_8]
        for i, fader in enumerate(faders):
            self.assertEqual(fader, 0x36 + i)


class TestControlEnum(unittest.TestCase):
    def test_knobs_sequential(self):
        knobs = [Control.KNOB_1, Control.KNOB_2, Control.KNOB_3, Control.KNOB_4,
                 Control.KNOB_5, Control.KNOB_6, Control.KNOB_7, Control.KNOB_8]
        for i, knob in enumerate(knobs):
            self.assertEqual(knob, 0x15 + i)

    def test_faders_sequential(self):
        faders = [Control.FADER_1, Control.FADER_2, Control.FADER_3, Control.FADER_4,
                  Control.FADER_5, Control.FADER_6, Control.FADER_7, Control.FADER_8]
        for i, fader in enumerate(faders):
            self.assertEqual(fader, 0x29 + i)

    def test_pads_sequential(self):
        pads = [PadNote.PAD_1, PadNote.PAD_2, PadNote.PAD_3, PadNote.PAD_4,
                PadNote.PAD_5, PadNote.PAD_6, PadNote.PAD_7, PadNote.PAD_8,
                PadNote.PAD_9, PadNote.PAD_10, PadNote.PAD_11, PadNote.PAD_12,
                PadNote.PAD_13, PadNote.PAD_14, PadNote.PAD_15, PadNote.PAD_16]
        for i, pad in enumerate(pads):
            self.assertEqual(pad, 0x60 + i)


class TestPortDiscovery(unittest.TestCase):
    @patch('slmkiii.incontrol.mido')
    def test_finds_incontrol_ports(self, mock_mido):
        mock_mido.get_input_names.return_value = [
            'Novation SL MkIII SL MkIII MIDI',
            'Novation SL MkIII SL MkIII InControl',
        ]
        mock_mido.get_output_names.return_value = [
            'Novation SL MkIII SL MkIII MIDI',
            'Novation SL MkIII SL MkIII InControl',
        ]
        result = find_incontrol_ports()
        self.assertEqual(result['input'], 'Novation SL MkIII SL MkIII InControl')
        self.assertEqual(result['output'], 'Novation SL MkIII SL MkIII InControl')

    @patch('slmkiii.incontrol.mido')
    def test_no_incontrol_ports_raises(self, mock_mido):
        mock_mido.get_input_names.return_value = ['Some Other Device']
        mock_mido.get_output_names.return_value = ['Some Other Device']
        with self.assertRaises(slmkiii.errors.ErrorMidiDeviceNotFound):
            find_incontrol_ports()

    @patch('slmkiii.incontrol.mido')
    def test_windows_port_names(self, mock_mido):
        mock_mido.get_input_names.return_value = [
            'MIDIIN (SL MkIII)',
            'MIDIIN2 (SL MkIII)',
        ]
        mock_mido.get_output_names.return_value = [
            'MIDIOUT (SL MkIII)',
            'MIDIOUT2 (SL MkIII)',
        ]
        result = find_incontrol_ports()
        self.assertIn('MIDIIN2', result['input'])
        self.assertIn('MIDIOUT2', result['output'])


if __name__ == '__main__':
    unittest.main()
