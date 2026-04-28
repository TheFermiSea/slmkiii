"""Tests for slmkiii.harvest (extracts plugin parameter dicts from .aum_midimap)."""

import unittest
from pathlib import Path

from slmkiii.harvest import (
    _infer_param_type,
    _make_display_name,
    _infer_group,
    _walk_params,
    harvest_from_aum_midimap,
)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_BATTALION_MIDIMAP = _PROJECT_ROOT / 'aum_samples' / 'MIDI Mappings' / 'Channel' / 'Battalion.aum_midimap'


class TestInferParamType(unittest.TestCase):
    def test_toggle_mute(self):
        self.assertEqual(_infer_param_type('drum1mute'), 'toggle')

    def test_toggle_solo(self):
        self.assertEqual(_infer_param_type('drum1solo'), 'toggle')

    def test_toggle_bypass(self):
        self.assertEqual(_infer_param_type('drum1bypass'), 'toggle')

    def test_trigger(self):
        self.assertEqual(_infer_param_type('drum1trigger'), 'trigger')

    def test_discrete_mode(self):
        self.assertEqual(_infer_param_type('drum1mode'), 'discrete')

    def test_continuous_cutoff(self):
        self.assertEqual(_infer_param_type('drum1cutoff'), 'continuous')


class TestMakeDisplayName(unittest.TestCase):
    def test_drum_prefix_replaced(self):
        self.assertEqual(_make_display_name('drum1cutoff'), 'D1 cutoff')

    def test_max_9_chars(self):
        result = _make_display_name('drum1cutoff')
        self.assertLessEqual(len(result), 9)

    def test_truncation(self):
        result = _make_display_name('drum1veryLongParameterName')
        self.assertLessEqual(len(result), 9)

    def test_no_drum_prefix(self):
        result = _make_display_name('volume')
        self.assertEqual(result, 'Volume')

    def test_custom_max_len(self):
        result = _make_display_name('drum1cutoff', max_len=5)
        self.assertLessEqual(len(result), 5)


class TestInferGroup(unittest.TestCase):
    def test_drum1(self):
        self.assertEqual(
            _infer_group('drumProtoParams.drum1params.drum1cutoff'),
            'drum1',
        )

    def test_drum1_mod(self):
        self.assertEqual(
            _infer_group('drumProtoParams.drum1params.drum1modparams.x'),
            'drum1.mod',
        )

    def test_effects(self):
        self.assertEqual(
            _infer_group('drumProtoParams.effectParams.x'),
            'effects',
        )

    def test_perform(self):
        self.assertEqual(
            _infer_group('drumProtoParams.performParams.x'),
            'perform',
        )

    def test_root_single_part(self):
        self.assertEqual(_infer_group('volume'), 'root')

    def test_sendA(self):
        self.assertEqual(
            _infer_group('drumProtoParams.sendAParams.reverbLevel'),
            'sendA',
        )

    def test_seqChan(self):
        self.assertEqual(
            _infer_group('drumProtoParams.seqChan1params.step1'),
            'seq1',
        )

    def test_sequencer(self):
        self.assertEqual(
            _infer_group('drumProtoParams.sequencerParams.tempo'),
            'sequencer',
        )


class TestWalkParams(unittest.TestCase):
    def test_finds_specState_entries(self):
        data = {
            'drumProtoParams.drum1params.drum1cutoff': {
                'specState': {'enabled': True, 'data1': 20, 'type': 0},
                'min': 0.0,
                'max': 1.0,
            },
            'drumProtoParams.drum1params.drum1mute': {
                'specState': {'enabled': True, 'data1': 21, 'type': 0},
                'min': 0.0,
                'max': 1.0,
            },
        }
        params = _walk_params(data)
        self.assertEqual(len(params), 2)
        paths = {p['path'] for p in params}
        self.assertIn('drumProtoParams.drum1params.drum1cutoff', paths)
        self.assertIn('drumProtoParams.drum1params.drum1mute', paths)

    def test_recurses_into_nested_dicts(self):
        data = {
            'level1': {
                'level1.level2': {
                    'level1.level2.param': {
                        'specState': {'enabled': True},
                    },
                },
            },
        }
        params = _walk_params(data)
        self.assertEqual(len(params), 1)
        self.assertEqual(params[0]['path'], 'level1.level2.param')

    def test_skips_underscore_keys(self):
        data = {
            '_collection_map_name': 'Something',
            'real.param': {
                'specState': {'enabled': True},
            },
        }
        params = _walk_params(data)
        self.assertEqual(len(params), 1)

    def test_empty_dict(self):
        self.assertEqual(_walk_params({}), [])

    def test_display_name_and_type_populated(self):
        data = {
            'drumProtoParams.drum1params.drum1solo': {
                'specState': {'enabled': True},
            },
        }
        params = _walk_params(data)
        self.assertEqual(len(params), 1)
        self.assertEqual(params[0]['display_name'], 'D1 solo')
        self.assertEqual(params[0]['param_type'], 'toggle')


@unittest.skipUnless(_BATTALION_MIDIMAP.exists(),
                     'Battalion.aum_midimap not found')
class TestHarvestBattalion(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = harvest_from_aum_midimap(
            _BATTALION_MIDIMAP,
            plugin_id='ua_battalion',
            plugin_name='UA Battalion',
        )

    def test_param_count(self):
        self.assertEqual(self.result['param_count'], 3225)

    def test_plugin_id(self):
        self.assertEqual(self.result['plugin_id'], 'ua_battalion')

    def test_plugin_name(self):
        self.assertEqual(self.result['plugin_name'], 'UA Battalion')

    def test_au_identifier_present(self):
        self.assertIn('.AU-', self.result['au_identifier'])

    def test_groups_not_empty(self):
        self.assertGreater(len(self.result['groups']), 0)

    def test_drum1_group_exists(self):
        self.assertIn('drum1', self.result['groups'])

    def test_each_param_has_required_keys(self):
        for group_name, group_data in self.result['groups'].items():
            for p in group_data['params']:
                self.assertIn('path', p, f'Missing path in group {group_name}')
                self.assertIn('display_name', p)
                self.assertIn('param_type', p)
                self.assertIn('group', p)


if __name__ == '__main__':
    unittest.main()
