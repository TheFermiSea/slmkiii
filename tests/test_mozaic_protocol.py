"""Tests for slmkiii.mozaic.protocol — SLMK-Bridge SysEx codec."""

from __future__ import annotations

import unittest

from slmkiii.mozaic.protocol import (
    HEADER,
    SYSEX_END,
    SYSEX_START,
    BeginUpload,
    Commit,
    DefineBinding,
    DefineButtonLed,
    DefineFocusSet,
    DefinePadBinding,
    DefinePage,
    ErrorCode,
    ErrorReport,
    Heartbeat,
    Message,
    MsgType,
    SubscribePluginEcho,
    crc14,
    decode_sysex,
    encode_inner,
    encode_sysex,
)


class TestHeader(unittest.TestCase):
    def test_header_is_slmk_magic(self):
        self.assertEqual(HEADER, bytes([0x7D, 0x53, 0x4C, 0x4D, 0x4B]))


class TestEncodeDecode(unittest.TestCase):
    def test_define_page_round_trip(self):
        m = DefinePage(page_idx=2, color=5, name="Bat Mix").encode()
        wire = encode_sysex(m)
        self.assertEqual(wire[0], SYSEX_START)
        self.assertEqual(wire[-1], SYSEX_END)
        decoded = decode_sysex(wire)
        self.assertIsNotNone(decoded)
        assert decoded is not None
        self.assertEqual(decoded.msg_type, MsgType.DEFINE_PAGE)
        # body: page_idx, color, name_len, name_bytes...
        self.assertEqual(decoded.body[0], 2)
        self.assertEqual(decoded.body[1], 5)
        self.assertEqual(decoded.body[2], 7)   # len("Bat Mix")
        self.assertEqual(decoded.body[3:].decode("ascii"), "Bat Mix")

    def test_focus_set_encode(self):
        m = DefineFocusSet(page_idx=1, names=("drum1", "drum2", "drum3")).encode()
        # body: page_idx, count, [len, bytes...] x N
        self.assertEqual(m.msg_type, MsgType.DEFINE_FOCUS_SET)
        self.assertEqual(m.body[0], 1)
        self.assertEqual(m.body[1], 3)

    def test_knob_binding_encode_as(self):
        b = DefineBinding(page_idx=1, focus_idx=2, slot=3, channel=1, cc=42, label="Cutoff")
        m = b.encode_as(MsgType.DEFINE_KNOB_BINDING)
        self.assertEqual(m.msg_type, MsgType.DEFINE_KNOB_BINDING)
        # body: page, focus, slot, channel, cc, label_len, label
        self.assertEqual(m.body[:5], bytes([1, 2, 3, 1, 42]))
        self.assertEqual(m.body[5], 6)   # len("Cutoff")
        self.assertEqual(m.body[6:].decode("ascii"), "Cutoff")

    def test_pad_binding_encode(self):
        m = DefinePadBinding(page_idx=0, focus_idx=0, slot=5, channel=10, note=41, color=37).encode()
        self.assertEqual(m.msg_type, MsgType.DEFINE_PAD_BINDING)
        self.assertEqual(m.body, bytes([0, 0, 5, 10, 41, 37]))

    def test_subscribe_encode(self):
        m = SubscribePluginEcho(channel=1, cc_lo=20, cc_hi=99).encode()
        self.assertEqual(m.msg_type, MsgType.SUBSCRIBE_PLUGIN_ECHO)
        self.assertEqual(m.body, bytes([1, 20, 99]))

    def test_begin_upload_encode(self):
        m = BeginUpload(data_major=2, data_minor=3, requires_rt_major=1).encode()
        self.assertEqual(m.body, bytes([2, 3, 1]))

    def test_commit_encode_decodes_crc(self):
        # 0x3FFF = 14 bits all set -> lo=0x7F, hi=0x7F
        m = Commit(crc14=0x3FFF).encode()
        self.assertEqual(m.msg_type, MsgType.COMMIT)
        self.assertEqual(m.body, bytes([0x7F, 0x7F]))
        # 0x1FFF (13 bits) -> lo=0x7F, hi=0x3F
        m2 = Commit(crc14=0x1FFF).encode()
        self.assertEqual(m2.body, bytes([0x7F, 0x3F]))

    def test_button_led_encode(self):
        m = DefineButtonLed(page_idx=1, button_idx=3, color=21).encode()
        self.assertEqual(m.body, bytes([1, 3, 21]))

    def test_error_report_encode(self):
        m = ErrorReport(last_msg_type=int(MsgType.DEFINE_PAGE),
                        code=ErrorCode.PAGE_OOR,
                        ctx_lo=42, ctx_hi=0).encode()
        self.assertEqual(m.body, bytes([
            int(MsgType.DEFINE_PAGE),
            int(ErrorCode.PAGE_OOR),
            42, 0,
        ]))

    def test_heartbeat_encode(self):
        m = Heartbeat(seq=7).encode()
        self.assertEqual(m.body, bytes([7]))


class TestDecode(unittest.TestCase):
    def test_decode_rejects_foreign_manufacturer(self):
        # Different manufacturer (Yamaha 0x43)
        wire = bytes([SYSEX_START, 0x43, 0x00, 0x01, SYSEX_END])
        self.assertIsNone(decode_sysex(wire))

    def test_decode_rejects_unknown_msg_type(self):
        wire = bytes([SYSEX_START]) + HEADER + bytes([0x7E, SYSEX_END])
        self.assertIsNone(decode_sysex(wire))

    def test_decode_inner_form(self):
        # interp.send_sysex strips F0/F7 — accept HEADER+payload directly
        m = DefinePage(page_idx=0, color=5, name="x").encode()
        inner = encode_inner(m)
        self.assertNotEqual(inner[0], SYSEX_START)
        decoded = decode_sysex(inner)
        self.assertIsNotNone(decoded)


class TestCrc(unittest.TestCase):
    def test_crc_excludes_envelope_messages(self):
        defines = [
            DefinePage(0, 5, "A").encode(),
            DefinePage(1, 9, "B").encode(),
        ]
        # Add envelope messages — they should not affect the CRC
        full = [BeginUpload().encode(), *defines, Commit(crc14=0).encode()]
        self.assertEqual(crc14(full), crc14(defines))

    def test_crc_changes_on_payload_change(self):
        a = [DefinePage(0, 5, "A").encode()]
        b = [DefinePage(0, 5, "B").encode()]
        self.assertNotEqual(crc14(a), crc14(b))

    def test_crc_within_14_bit_range(self):
        # Many large messages, verify result stays in 14 bits
        msgs = [DefinePage(i % 8, 100, "x" * 16).encode() for i in range(64)]
        c = crc14(msgs)
        self.assertGreaterEqual(c, 0)
        self.assertLessEqual(c, 0x3FFF)


if __name__ == "__main__":
    unittest.main()
