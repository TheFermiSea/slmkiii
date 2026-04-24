"""Unit tests for the SL MkIII <-> Mozaic sysex bridge protocol (v1.1)."""

import unittest

import mido

from controlmap import bridge_protocol as bp


class TestRequestEncoders(unittest.TestCase):

    def test_hello(self):
        msg = bp.hello()
        self.assertEqual(bp.parse(msg), (bp.CMD_HELLO, ()))

    def test_get_values(self):
        msg = bp.get_values()
        self.assertEqual(bp.parse(msg), (bp.CMD_GET_VALUES, ()))

    def test_clear_watches(self):
        msg = bp.clear_watches()
        self.assertEqual(bp.parse(msg), (bp.CMD_CLEAR_WATCHES, ()))

    def test_watch_cc_single_chunk(self):
        pairs = [(0, 20), (0, 21), (15, 119)]
        msgs = bp.watch_cc(pairs)
        self.assertEqual(len(msgs), 1)
        cmd, payload = bp.parse(msgs[0])  # type: ignore[misc]
        self.assertEqual(cmd, bp.CMD_WATCH_CC)
        self.assertEqual(payload, (0, 20, 0, 21, 15, 119))

    def test_watch_cc_chunks_when_large(self):
        pairs = [(ch, cc) for ch in range(4) for cc in range(20, 100)]
        msgs = bp.watch_cc(pairs)
        self.assertGreater(len(msgs), 1)
        recovered = []
        for m in msgs:
            cmd, payload = bp.parse(m)  # type: ignore[misc]
            self.assertEqual(cmd, bp.CMD_WATCH_CC)
            for i in range(0, len(payload), 2):
                recovered.append((payload[i], payload[i + 1]))
        self.assertEqual(recovered, pairs)

    def test_watch_notes(self):
        msg = bp.watch_notes([0, 5, 15])
        cmd, payload = bp.parse(msg)  # type: ignore[misc]
        self.assertEqual(cmd, bp.CMD_WATCH_NOTES)
        self.assertEqual(payload, (0, 5, 15))

    def test_page(self):
        msg = bp.page(7)
        self.assertEqual(bp.parse(msg), (bp.CMD_PAGE, (7,)))

    def test_channels_masked_to_4_bits(self):
        msgs = bp.watch_cc([(99, 20)])
        _cmd, payload = bp.parse(msgs[0])  # type: ignore[misc]
        self.assertEqual(payload[0], 99 & 0x0F)


class TestParser(unittest.TestCase):

    def test_foreign_sysex_ignored(self):
        # Novation SL MkIII InControl header
        foreign = mido.Message(
            'sysex', data=[0x00, 0x20, 0x29, 0x02, 0x0A, 0x01, 0x04])
        self.assertIsNone(bp.parse(foreign))
        self.assertIsNone(bp.parse_event(foreign))

    def test_non_sysex_ignored(self):
        msg = mido.Message('control_change', channel=0, control=20, value=64)
        self.assertIsNone(bp.parse(msg))
        self.assertIsNone(bp.parse_event(msg))

    def test_too_short_ignored(self):
        self.assertIsNone(bp.parse(mido.Message('sysex', data=[bp.SX_TAG])))


class TestEventDecoder(unittest.TestCase):

    def _bridge_msg(self, opcode: int, payload: list[int]) -> mido.Message:
        return mido.Message('sysex', data=[bp.SX_TAG, opcode] + payload)

    def test_cc_value(self):
        msg = self._bridge_msg(bp.RSP_CC_VALUE, [3, 22, 64])
        ev = bp.parse_event(msg)
        self.assertIsInstance(ev, bp.CCValue)
        assert isinstance(ev, bp.CCValue)
        self.assertEqual((ev.channel, ev.cc, ev.value), (3, 22, 64))

    def test_note_on(self):
        msg = self._bridge_msg(bp.RSP_NOTE_ON, [0, 60, 100])
        ev = bp.parse_event(msg)
        self.assertIsInstance(ev, bp.NoteEvent)
        assert isinstance(ev, bp.NoteEvent)
        self.assertTrue(ev.on)
        self.assertEqual((ev.channel, ev.note, ev.velocity), (0, 60, 100))

    def test_note_off(self):
        msg = self._bridge_msg(bp.RSP_NOTE_OFF, [0, 60])
        ev = bp.parse_event(msg)
        self.assertIsInstance(ev, bp.NoteEvent)
        assert isinstance(ev, bp.NoteEvent)
        self.assertFalse(ev.on)
        self.assertEqual(ev.velocity, 0)

    def test_hello_ack(self):
        msg = self._bridge_msg(bp.RSP_HELLO_ACK, [1, 1])
        ev = bp.parse_event(msg)
        self.assertIsInstance(ev, bp.HelloAck)
        assert isinstance(ev, bp.HelloAck)
        self.assertEqual((ev.major, ev.minor), (1, 1))

    def test_page_ack(self):
        msg = self._bridge_msg(bp.RSP_PAGE_ACK, [3])
        ev = bp.parse_event(msg)
        self.assertIsInstance(ev, bp.PageAck)
        assert isinstance(ev, bp.PageAck)
        self.assertEqual(ev.page, 3)

    def test_unknown_opcode(self):
        msg = self._bridge_msg(0x7F, [1, 2, 3])
        self.assertIsNone(bp.parse_event(msg))


class TestProtocolVersion(unittest.TestCase):

    def test_version_constant(self):
        self.assertEqual(bp.PROTOCOL_VERSION, (1, 1))


if __name__ == '__main__':
    unittest.main()
