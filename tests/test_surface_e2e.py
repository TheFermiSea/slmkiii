"""End-to-end test: YAML spec -> compile -> emit -> verify artifacts."""

import tempfile
import unittest
from pathlib import Path

from controlmap import compile_mapping
from controlmap.emitters.aum_emitter import AumEmitter
from controlmap.emitters.slmkiii_emitter import SlMkIIIEmitter
from controlmap.mozaic import pack_moz_file
from controlmap.spec_loader import load_spec
from slmkiii import Template
from aum_tools import read_aum_midimap, decode_keyed_archiver


class TestE2EPipeline(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.tmpdir = Path(tempfile.mkdtemp(prefix='slmkiii_e2e_'))
        cls.spec_path = cls.tmpdir / 'spec.yaml'
        cls.spec_path.write_text(
            'name: e2e_test\n'
            'controller: slmkiii\n'
            'plugin: animoog_z\n'
            'target: aum\n'
            'midi_channel_base: 1\n'
            'parameters:\n'
            '  - "*"\n'
        )

    def test_load_compile_emit(self):
        spec = load_spec(self.spec_path)
        self.assertEqual(spec.name, 'e2e_test')

        resolved = compile_mapping(spec)
        self.assertGreater(resolved.metadata['param_count'], 0)
        self.assertGreater(len(resolved.page_set.all_bindings), 0)

        # SL MkIII emitter
        out = Path(tempfile.mkdtemp(prefix='e2e_emit_'))
        syx_paths = SlMkIIIEmitter().emit(resolved, out)
        self.assertGreater(len(syx_paths), 0)
        for p in syx_paths:
            self.assertTrue(p.exists())
            # Round-trip: load it back as a Template
            t = Template(str(p))
            self.assertIsNotNone(t.name)

        # AUM emitter
        map_paths = AumEmitter().emit(resolved, out)
        self.assertGreater(len(map_paths), 0)
        for p in map_paths:
            self.assertTrue(p.exists())
            mapping = read_aum_midimap(p)
            self.assertIn('collection_name', mapping)
            self.assertGreater(len(mapping['mappings']), 0)

    def test_mozaic_bridge_packs(self):
        bridge_src = (Path(__file__).parent.parent / 'controlmap' / 'mozaic'
                      / 'slmk_bridge.moz')
        self.assertTrue(bridge_src.exists())
        out = self.tmpdir / 'BRIDGE.mozaic'
        pack_moz_file(bridge_src, out, 'SLMK-BRIDGE')
        # Decode and verify CODE was preserved
        obj = decode_keyed_archiver(out.read_bytes())
        self.assertEqual(obj['FILENAME'], 'SLMK-BRIDGE')
        code = obj['CODE']['NS.data']
        self.assertIn(b'SLMK-BRIDGE', code)
        # All v1.1 protocol opcodes must appear in the script
        for opcode_name in [b'cmd_hello', b'cmd_get_values', b'cmd_watch_cc',
                             b'cmd_watch_notes', b'cmd_clear', b'cmd_page',
                             b'rsp_hello_ack', b'rsp_cc_value',
                             b'rsp_note_on', b'rsp_note_off']:
            self.assertIn(opcode_name, code,
                          f'bridge script missing constant {opcode_name!r}')


class TestProtocolBridgeAlignment(unittest.TestCase):
    """Ensure the Mozaic script and Python protocol agree on opcodes.

    Parses the .moz source for `name = 0xNN` assignments and verifies the
    extracted values match the Python constants by name. Whitespace-insensitive
    so formatting edits to the Mozaic file don't break CI.
    """

    def test_opcode_constants_match(self):
        import re
        from controlmap import bridge_protocol as bp

        bridge_src = (Path(__file__).parent.parent / 'controlmap' / 'mozaic'
                      / 'slmk_bridge.moz').read_text()

        moz_constants: dict[str, int] = {}
        for name, hex_val in re.findall(
                r'^\s*(cmd_\w+|rsp_\w+)\s*=\s*0x([0-9A-Fa-f]+)',
                bridge_src, re.MULTILINE):
            moz_constants[name.lower()] = int(hex_val, 16)

        # Map Python constant names (CMD_FOO / RSP_FOO) to expected Mozaic keys.
        expected = {name.lower(): getattr(bp, name)
                    for name in dir(bp)
                    if name.startswith(('CMD_', 'RSP_'))}
        # Mozaic uses cmd_scene_save / cmd_scene_recall exactly like Python
        # (with underscore between SCENE and SAVE/RECALL).

        missing = set(expected) - set(moz_constants)
        self.assertFalse(missing,
                         f'Mozaic script missing constants: {sorted(missing)}')

        mismatched = [
            (k, expected[k], moz_constants[k])
            for k in expected if expected[k] != moz_constants[k]
        ]
        self.assertFalse(mismatched,
                         f'opcode value mismatches: {mismatched}')


if __name__ == '__main__':
    unittest.main()
