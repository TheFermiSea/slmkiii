"""Unit tests for the SL MkIII <-> Mozaic sysex bridge protocol."""

import unittest

import mido

from controlmap import bridge_protocol as bp


class TestBridgeProtocol(unittest.TestCase):

    def test_hello_round_trip(self):
        msg = bp.hello()
        parsed = bp.parse(msg)
        self.assertEqual(parsed, (bp.SX_HELLO, ()))

    def test_watch_clear_round_trip(self):
        msg = bp.watch_clear()
        parsed = bp.parse(msg)
        self.assertEqual(parsed, (bp.SX_WATCH_CLEAR, ()))

    def test_watch_set_single_chunk(self):
        pairs = [(0, 20), (0, 21), (15, 119)]
        msgs = bp.watch_set(pairs)
        self.assertEqual(len(msgs), 1)
        parsed = bp.parse(msgs[0])
        self.assertIsNotNone(parsed)
        cmd, payload = parsed
        self.assertEqual(cmd, bp.SX_WATCH_SET)
        self.assertEqual(payload, (0, 20, 0, 21, 15, 119))

    def test_watch_set_chunks_when_large(self):
        pairs = [(ch, cc) for ch in range(4) for cc in range(20, 100)]
        msgs = bp.watch_set(pairs)
        self.assertGreater(len(msgs), 1, 'large pair list should chunk')
        # Reassemble payload and verify every pair round-trips
        recovered = []
        for m in msgs:
            parsed = bp.parse(m)
            self.assertIsNotNone(parsed)
            _cmd, payload = parsed
            for i in range(0, len(payload), 2):
                recovered.append((payload[i], payload[i + 1]))
        self.assertEqual(recovered, pairs)

    def test_page_round_trip(self):
        msg = bp.page(7)
        parsed = bp.parse(msg)
        self.assertEqual(parsed, (bp.SX_PAGE, (7,)))

    def test_channels_masked_to_4_bits(self):
        msgs = bp.watch_set([(99, 20)])  # invalid channel
        parsed = bp.parse(msgs[0])
        self.assertIsNotNone(parsed)
        _cmd, payload = parsed
        self.assertEqual(payload[0], 99 & 0x0F)

    def test_foreign_sysex_ignored(self):
        # Novation SL MkIII InControl header - must not be parsed as ours.
        foreign = mido.Message('sysex',
                               data=[0x00, 0x20, 0x29, 0x02, 0x0A, 0x01, 0x04])
        self.assertIsNone(bp.parse(foreign))

    def test_non_sysex_ignored(self):
        self.assertIsNone(bp.parse(mido.Message('control_change',
                                                channel=0, control=20, value=64)))

    def test_empty_sysex_ignored(self):
        self.assertIsNone(bp.parse(mido.Message('sysex', data=[bp.SX_TAG])))


if __name__ == '__main__':
    unittest.main()
