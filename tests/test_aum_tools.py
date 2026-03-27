"""Tests for AUM file format tools."""
import tempfile
import unittest
from pathlib import Path

from aum_tools import (
    AumMidiMapping, AumSession, AumChannel, AumPlugin,
    MSG_TYPE_CC, MSG_TYPE_NOTE,
    read_aum_midimap, write_aum_midimap, generate_midimap_bytes,
    read_aum_session, _decode_keyed_archiver,
)

SAMPLES_DIR = Path(__file__).parent.parent / 'aum_samples'
TRANSPORT_MAP = SAMPLES_DIR / 'MIDI Mappings' / 'Transport' / 'New MIDI Mapping.aum_midimap'
RUISMAKER_MAP = SAMPLES_DIR / 'MIDI Mappings' / 'Ruismaker.AU-4272616D7275697361756D75' / 'New MIDI Mapping.aum_midimap'
SESSION_FILE = SAMPLES_DIR / 'Untitled 2026-02-24 22.53.54.aumproj'


class TestReadMidimap(unittest.TestCase):
    def test_read_transport(self):
        result = read_aum_midimap(TRANSPORT_MAP)
        self.assertEqual(result['collection_name'], 'Transport')
        self.assertGreater(len(result['mappings']), 0)

        # Find "Toggle Play" mapping
        toggle_play = next(
            m for m in result['mappings'] if m.parameter_name == 'Toggle Play')
        self.assertEqual(toggle_play.cc_number, 80)
        self.assertEqual(toggle_play.msg_type, MSG_TYPE_CC)
        self.assertFalse(toggle_play.enabled)

    def test_read_ruismaker(self):
        result = read_aum_midimap(RUISMAKER_MAP)
        self.assertIn('Ruismaker', result['collection_name'])
        self.assertGreater(len(result['mappings']), 70)

        # Check that instrument1-8 are enabled with CC mappings
        instruments = [m for m in result['mappings']
                       if m.parameter_name.startswith('instrument')]
        self.assertEqual(len(instruments), 8)
        for m in instruments:
            self.assertTrue(m.enabled)
            self.assertEqual(m.msg_type, MSG_TYPE_CC)

    def test_read_ruismaker_cc_numbers(self):
        result = read_aum_midimap(RUISMAKER_MAP)
        inst_map = {m.parameter_name: m.cc_number
                    for m in result['mappings']
                    if m.parameter_name.startswith('instrument')}
        self.assertEqual(inst_map['instrument1'], 36)
        self.assertEqual(inst_map['instrument8'], 43)

    def test_parameter_names_complete(self):
        result = read_aum_midimap(RUISMAKER_MAP)
        names = {m.parameter_name for m in result['mappings']}
        # Verify some expected Ruismaker parameters exist
        for expected in ['decay1', 'tune1', 'level1', 'pan1', 'drive1',
                         'reverb', 'volume', 'dynamics', 'delaytime']:
            self.assertIn(expected, names, f'{expected} not found in mapping')


class TestWriteMidimap(unittest.TestCase):
    def test_generate_and_read_back(self):
        mappings = [
            AumMidiMapping('volume', cc_number=7, channel=0, enabled=True),
            AumMidiMapping('pan', cc_number=10, channel=0, enabled=True),
            AumMidiMapping('cutoff', cc_number=74, channel=0, enabled=True,
                           min_value=0.0, max_value=0.5),
        ]
        data = generate_midimap_bytes('TestPlugin.AU-deadbeef', mappings)
        self.assertIsInstance(data, bytes)

        # Verify it's a valid plist
        decoded = _decode_keyed_archiver(data)
        self.assertEqual(decoded['_collection_map_name'], 'TestPlugin.AU-deadbeef')

    def test_round_trip_file(self):
        mappings = [
            AumMidiMapping('param_a', cc_number=20, channel=1, enabled=True),
            AumMidiMapping('param_b', cc_number=21, channel=1, enabled=False),
            AumMidiMapping('param_c', cc_number=22, channel=0, enabled=True,
                           auto_toggle=True, msg_type=MSG_TYPE_NOTE),
        ]
        with tempfile.NamedTemporaryFile(suffix='.aum_midimap', delete=False) as f:
            path = f.name

        write_aum_midimap('RoundTrip.AU-test', mappings, path)

        # Read back
        result = read_aum_midimap(path)
        self.assertEqual(result['collection_name'], 'RoundTrip.AU-test')
        self.assertEqual(len(result['mappings']), 3)

        read_map = {m.parameter_name: m for m in result['mappings']}
        self.assertEqual(read_map['param_a'].cc_number, 20)
        self.assertEqual(read_map['param_a'].channel, 1)
        self.assertTrue(read_map['param_a'].enabled)

        self.assertFalse(read_map['param_b'].enabled)

        self.assertTrue(read_map['param_c'].auto_toggle)
        self.assertEqual(read_map['param_c'].msg_type, MSG_TYPE_NOTE)

    def test_empty_mappings(self):
        data = generate_midimap_bytes('Empty', [])
        decoded = _decode_keyed_archiver(data)
        self.assertEqual(decoded['_collection_map_name'], 'Empty')


class TestReadSession(unittest.TestCase):
    def test_basic_session_info(self):
        session = read_aum_session(SESSION_FILE)
        self.assertIn('2026', session.title)
        self.assertEqual(session.version, 13)
        self.assertEqual(session.sample_rate, 96000)

    def test_channel_count(self):
        session = read_aum_session(SESSION_FILE)
        self.assertEqual(len(session.channels), 7)

    def test_channel_types(self):
        session = read_aum_session(SESSION_FILE)
        types = [ch.channel_type for ch in session.channels]
        self.assertIn('AUMAudioStrip', types)
        self.assertIn('AUMMIDIStrip', types)

    def test_fader_levels_vary(self):
        session = read_aum_session(SESSION_FILE)
        levels = [ch.fader_level for ch in session.channels
                  if ch.channel_type == 'AUMAudioStrip']
        # Levels should not all be the same (we set different levels)
        self.assertGreater(len(set(f'{l:.2f}' for l in levels)), 1)

    def test_plugins_identified(self):
        session = read_aum_session(SESSION_FILE)
        all_plugins = []
        for ch in session.channels:
            all_plugins.extend(ch.plugins)

        plugin_names = [p.component_name for p in all_plugins if p.component_name]
        self.assertIn('Unfiltered Audio: UA Battalion', plugin_names)
        self.assertIn('Moog: Animoog Z', plugin_names)
        self.assertIn('Apple: AUDelay', plugin_names)
        self.assertIn('Audulus: Audulus 4 FX', plugin_names)

    def test_plugin_au_types(self):
        session = read_aum_session(SESSION_FILE)
        all_plugins = [p for ch in session.channels for p in ch.plugins
                       if p.au_type]

        au_types = {p.component_name: p.au_type for p in all_plugins}
        # Battalion and Animoog are instruments
        self.assertEqual(au_types['Unfiltered Audio: UA Battalion'], 'aumu')
        self.assertEqual(au_types['Moog: Animoog Z'], 'aumu')
        # AUDelay is an effect
        self.assertEqual(au_types['Apple: AUDelay'], 'aufx')

    def test_plugin_manufacturers(self):
        session = read_aum_session(SESSION_FILE)
        all_plugins = [p for ch in session.channels for p in ch.plugins
                       if p.au_manufacturer]

        mfrs = {p.component_name: p.au_manufacturer for p in all_plugins}
        self.assertEqual(mfrs['Moog: Animoog Z'], 'Moog')
        self.assertEqual(mfrs['Apple: AUDelay'], 'appl')

    def test_channel_plugin_association(self):
        session = read_aum_session(SESSION_FILE)
        # Channel 1 should have Battalion
        ch1 = session.channels[1]
        self.assertTrue(any('Battalion' in p.component_name
                            for p in ch1.plugins))
        # Channel 2 should have Animoog + AUDelay
        ch2 = session.channels[2]
        self.assertTrue(any('Animoog' in p.component_name
                            for p in ch2.plugins))
        self.assertTrue(any('AUDelay' in p.component_name
                            for p in ch2.plugins))

    def test_tempo(self):
        session = read_aum_session(SESSION_FILE)
        self.assertEqual(session.tempo, 96.0)


if __name__ == '__main__':
    unittest.main()
