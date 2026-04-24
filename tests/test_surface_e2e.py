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
    """Ensure the Mozaic script and Python protocol agree on opcodes."""

    def test_opcode_constants_match(self):
        from controlmap import bridge_protocol as bp

        bridge_src = (Path(__file__).parent.parent / 'controlmap' / 'mozaic'
                      / 'slmk_bridge.moz').read_text()

        # Map of (Python constant, expected Mozaic line fragment)
        cases = [
            (bp.CMD_HELLO,         'cmd_hello       = 0x00'),
            (bp.CMD_GET_VALUES,    'cmd_get_values  = 0x01'),
            (bp.CMD_WATCH_CC,      'cmd_watch_cc    = 0x02'),
            (bp.CMD_WATCH_NOTES,   'cmd_watch_notes = 0x03'),
            (bp.CMD_CLEAR_WATCHES, 'cmd_clear       = 0x04'),
            (bp.CMD_PAGE,          'cmd_page        = 0x05'),
            (bp.CMD_GET_HEALTH,    'cmd_get_health  = 0x06'),
            (bp.CMD_ROUTE_SET,     'cmd_route_set   = 0x07'),
            (bp.CMD_ROUTE_CLEAR,   'cmd_route_clear = 0x08'),
            (bp.CMD_SCENE_SAVE,    'cmd_scene_save  = 0x09'),
            (bp.CMD_SCENE_RECALL,  'cmd_scene_recall = 0x0A'),
            (bp.RSP_HELLO_ACK,     'rsp_hello_ack = 0x10'),
            (bp.RSP_CC_VALUE,      'rsp_cc_value  = 0x11'),
            (bp.RSP_NOTE_ON,       'rsp_note_on   = 0x12'),
            (bp.RSP_NOTE_OFF,      'rsp_note_off  = 0x13'),
            (bp.RSP_HEALTH,        'rsp_health    = 0x14'),
            (bp.RSP_PAGE_ACK,      'rsp_page_ack  = 0x15'),
        ]
        for _expected_value, fragment in cases:
            self.assertIn(fragment, bridge_src,
                          f'bridge script missing or has divergent line: {fragment!r}')


if __name__ == '__main__':
    unittest.main()
