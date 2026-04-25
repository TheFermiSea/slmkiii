"""Tests for the per-spec Mozaic generator (Mac-free runtime)."""

import unittest

from controlmap import compile_mapping
from controlmap.mozaic import generate, build_mozaic
from controlmap.mozaic import incontrol_codec as ic
from controlmap.spec_loader import spec_from_dict
from aum_tools import decode_keyed_archiver


def _resolved(params: list[str] | None = None):
    spec = spec_from_dict({
        'name': 'gen_test',
        'controller': 'slmkiii',
        'plugin': 'animoog_z',
        'parameters': params or ['*'],
    })
    return compile_mapping(spec)


class TestIncontrolCodec(unittest.TestCase):

    def test_set_layout_envelope(self):
        msg = ic.set_layout(ic.LAYOUT_KNOB)
        self.assertEqual(msg[0], 0xF0)
        self.assertEqual(msg[-1], 0xF7)
        self.assertEqual(msg[7], ic.CMD_SET_LAYOUT)
        self.assertEqual(msg[8], ic.LAYOUT_KNOB)

    def test_set_value_template_indices(self):
        msg, val_pos = ic.set_value_template(0, 0)
        # Filling val_pos with N then sending should produce a valid set_value(N).
        patched = list(msg)
        patched[val_pos] = 99
        full = ic.set_value(0, 0, 99)
        self.assertEqual(tuple(patched), full)

    def test_set_text_clamps_to_9(self):
        msg = ic.set_text(0, 0, 'a_very_long_label')
        # 7 header + 4 fixed + up to 9 text + 2 trailing = 22 max
        self.assertLessEqual(len(msg), 22)


class TestGenerate(unittest.TestCase):

    def test_generates_valid_moz_source(self):
        src = generate(_resolved())
        self.assertIn('@OnLoad', src)
        self.assertIn('@OnMidiCC', src)
        self.assertIn('SendMIDICC MIDIChannel, MIDIByte2, MIDIByte3', src)
        self.assertIn('cc_to_col', src)
        self.assertIn('Animoog Z', src)  # plugin name in header comment

    def test_generated_script_packs_into_mozaic(self):
        src = generate(_resolved())
        data = build_mozaic(src, 'GEN-TEST')
        decoded = decode_keyed_archiver(data)
        self.assertEqual(decoded['FILENAME'], 'GEN-TEST')
        code = decoded['CODE']['NS.data'].decode('utf-8')
        self.assertIn('@OnLoad', code)
        self.assertIn('cc_to_col', code)

    def test_generates_one_lookup_per_knob_binding(self):
        # animoog_z mapping puts continuous params on knobs/faders. The first
        # 8 knob slots get screen columns 0..7 if there are enough params.
        src = generate(_resolved())
        # Each knob_screen binding emits a `cc_to_col[N] = M` line
        lines = [ln for ln in src.splitlines()
                 if ln.strip().startswith('cc_to_col[')
                 and '= -1' not in ln]
        self.assertGreater(len(lines), 0)
        self.assertLessEqual(len(lines), 8)

    def test_emits_set_layout_knob(self):
        src = generate(_resolved())
        # CMD_SET_LAYOUT (0x01) followed by LAYOUT_KNOB (0x01) are emitted as
        # consecutive bytes 7 and 8 of the layout SysEx — which we render as
        # `buf[7] = 1` then `buf[8] = 1`.
        self.assertIn('buf[7] = 1\n    buf[8] = 1', src)

    def test_emits_emit_set_value_with_runtime_patch(self):
        src = generate(_resolved())
        self.assertIn('@EmitSetValue', src)
        self.assertIn('val_buf[8] = col', src)
        self.assertIn('val_buf[11] = MIDIByte3', src)

    def test_empty_mapping_raises(self):
        from controlmap.model import PageSet, ResolvedMapping
        from controlmap.spec_loader import spec_from_dict

        empty = ResolvedMapping(
            spec=spec_from_dict({'name': 'x', 'controller': 'slmkiii',
                                 'plugin': 'animoog_z'}),
            page_set=PageSet(pages=[]),
        )
        with self.assertRaises(ValueError):
            generate(empty)


if __name__ == '__main__':
    unittest.main()
