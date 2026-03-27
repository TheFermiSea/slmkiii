"""Tests for controlmap harvest and emitter modules."""
import tempfile
import unittest
from pathlib import Path

from controlmap.plugins.harvest import (
    _infer_param_type,
    _make_display_name,
    _infer_group,
    _walk_params,
    harvest_from_aum_midimap,
)
from controlmap.model import (
    Binding, ControlSlot, ControlType, MappingSpec, Page, PageSet,
    ParameterRef, ParamType, ResolvedMapping,
)
from controlmap.emitters.slmkiii_emitter import SlMkIIIEmitter
from controlmap.emitters.aum_emitter import AumEmitter
from controlmap import compile_mapping

import slmkiii
from aum_tools import _decode_keyed_archiver

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_BATTALION_MIDIMAP = _PROJECT_ROOT / 'aum_samples' / 'MIDI Mappings' / 'Channel' / 'Battalion.aum_midimap'


# -----------------------------------------------------------------------
# 1. Harvest helper tests
# -----------------------------------------------------------------------

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


# -----------------------------------------------------------------------
# 2. Harvest integration test (real Battalion file)
# -----------------------------------------------------------------------

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
        self.assertEqual(self.result['param_count'], 3230)

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

    def test_effects_group_exists(self):
        self.assertIn('effects', self.result['groups'])

    def test_each_param_has_required_keys(self):
        for group_name, group_data in self.result['groups'].items():
            for p in group_data['params']:
                self.assertIn('path', p, f'Missing path in group {group_name}')
                self.assertIn('display_name', p)
                self.assertIn('param_type', p)
                self.assertIn('group', p)


# -----------------------------------------------------------------------
# 3. SlMkIIIEmitter tests
# -----------------------------------------------------------------------

def _make_resolved_mapping(bindings_spec, metadata=None):
    """Build a ResolvedMapping from a list of (group, index, cc, channel, name, path) tuples."""
    pages = []
    page_bindings = []
    for group, index, cc, channel, name, path in bindings_spec:
        ct = {
            'knobs': ControlType.CONTINUOUS,
            'faders': ControlType.CONTINUOUS,
            'buttons': ControlType.MOMENTARY,
            'pads': ControlType.VELOCITY,
        }.get(group, ControlType.CONTINUOUS)
        slot = ControlSlot(group=group, index=index, control_type=ct)
        param = ParameterRef(plugin_id='test', param_path=path, display_name=name)
        page_bindings.append(Binding(
            slot=slot,
            param=param,
            midi_channel=channel,
            midi_cc=cc,
            msg_type='cc',
        ))

    pages.append(Page(name='Test P01', index=0, bindings=page_bindings))
    spec = MappingSpec(
        name='Test',
        controller_id='slmkiii',
        plugin_id='test',
        target_id='slmkiii',
    )
    return ResolvedMapping(
        spec=spec,
        page_set=PageSet(pages=pages),
        metadata=metadata or {},
    )


class TestSlMkIIIEmitter(unittest.TestCase):
    def test_emit_creates_syx_files(self):
        resolved = _make_resolved_mapping([
            ('knobs', 0, 20, 1, 'Cutoff', 'drum1.cutoff'),
            ('faders', 0, 21, 1, 'Volume', 'drum1.volume'),
            ('buttons', 0, 22, 1, 'Mute', 'drum1.mute'),
            ('pads', 0, 23, 1, 'Trigger', 'drum1.trigger'),
        ])

        emitter = SlMkIIIEmitter()
        with tempfile.TemporaryDirectory() as tmpdir:
            files = emitter.emit(resolved, tmpdir)
            self.assertEqual(len(files), 1)
            self.assertTrue(files[0].exists())
            self.assertTrue(files[0].name.endswith('.syx'))

    def test_emitted_syx_loadable(self):
        resolved = _make_resolved_mapping([
            ('knobs', 0, 20, 1, 'Cutoff', 'drum1.cutoff'),
            ('faders', 0, 21, 1, 'Volume', 'drum1.volume'),
        ])

        emitter = SlMkIIIEmitter()
        with tempfile.TemporaryDirectory() as tmpdir:
            files = emitter.emit(resolved, tmpdir)
            template = slmkiii.Template(str(files[0]))
            self.assertIsInstance(template, slmkiii.Template)

    def test_knob_mapping(self):
        resolved = _make_resolved_mapping([
            ('knobs', 0, 30, 2, 'Filter', 'filter.cutoff'),
        ])
        emitter = SlMkIIIEmitter()
        with tempfile.TemporaryDirectory() as tmpdir:
            files = emitter.emit(resolved, tmpdir)
            template = slmkiii.Template(str(files[0]))
            self.assertEqual(template.knobs[0].name, 'Filter')
            self.assertEqual(template.knobs[0].channel, 2)

    def test_fader_mapping(self):
        resolved = _make_resolved_mapping([
            ('faders', 2, 40, 3, 'Vol', 'mixer.vol'),
        ])
        emitter = SlMkIIIEmitter()
        with tempfile.TemporaryDirectory() as tmpdir:
            files = emitter.emit(resolved, tmpdir)
            template = slmkiii.Template(str(files[0]))
            self.assertEqual(template.faders[2].name, 'Vol')
            self.assertEqual(template.faders[2].channel, 3)

    def test_button_mapping(self):
        resolved = _make_resolved_mapping([
            ('buttons', 1, 50, 4, 'Mute', 'drum1.mute'),
        ])
        emitter = SlMkIIIEmitter()
        with tempfile.TemporaryDirectory() as tmpdir:
            files = emitter.emit(resolved, tmpdir)
            template = slmkiii.Template(str(files[0]))
            self.assertEqual(template.buttons[1].name, 'Mute')
            self.assertEqual(template.buttons[1].channel, 4)

    def test_pad_mapping(self):
        resolved = _make_resolved_mapping([
            ('pads', 3, 60, 5, 'Kick', 'drum1.kick'),
        ])
        emitter = SlMkIIIEmitter()
        with tempfile.TemporaryDirectory() as tmpdir:
            files = emitter.emit(resolved, tmpdir)
            template = slmkiii.Template(str(files[0]))
            self.assertEqual(template.pad_hits[3].name, 'Kick')
            self.assertEqual(template.pad_hits[3].channel, 5)

    def test_note_binding(self):
        pages = [Page(name='Note P01', index=0, bindings=[
            Binding(
                slot=ControlSlot(group='pads', index=0,
                                 control_type=ControlType.VELOCITY),
                param=ParameterRef(plugin_id='test',
                                   param_path='drum1.trigger',
                                   display_name='Trig'),
                midi_channel=10,
                midi_note=36,
                msg_type='note',
            ),
        ])]
        resolved = ResolvedMapping(
            spec=MappingSpec(name='NoteTest', controller_id='slmkiii',
                             plugin_id='test', target_id='slmkiii'),
            page_set=PageSet(pages=pages),
            metadata={},
        )
        emitter = SlMkIIIEmitter()
        with tempfile.TemporaryDirectory() as tmpdir:
            files = emitter.emit(resolved, tmpdir)
            template = slmkiii.Template(str(files[0]))
            self.assertEqual(template.pad_hits[0].name, 'Trig')
            self.assertEqual(template.pad_hits[0].channel, 10)

    def test_multiple_pages(self):
        pages = [
            Page(name='Multi P01', index=0, bindings=[
                Binding(
                    slot=ControlSlot(group='knobs', index=0,
                                     control_type=ControlType.CONTINUOUS),
                    param=ParameterRef(plugin_id='test',
                                       param_path='a', display_name='Knob A'),
                    midi_channel=1, midi_cc=20,
                ),
            ]),
            Page(name='Multi P02', index=1, bindings=[
                Binding(
                    slot=ControlSlot(group='knobs', index=0,
                                     control_type=ControlType.CONTINUOUS),
                    param=ParameterRef(plugin_id='test',
                                       param_path='b', display_name='Knob B'),
                    midi_channel=1, midi_cc=21,
                ),
            ]),
        ]
        resolved = ResolvedMapping(
            spec=MappingSpec(name='Multi', controller_id='slmkiii',
                             plugin_id='test', target_id='slmkiii'),
            page_set=PageSet(pages=pages),
            metadata={},
        )
        emitter = SlMkIIIEmitter()
        with tempfile.TemporaryDirectory() as tmpdir:
            files = emitter.emit(resolved, tmpdir)
            self.assertEqual(len(files), 2)
            for f in files:
                self.assertTrue(f.exists())
                slmkiii.Template(str(f))


# -----------------------------------------------------------------------
# 4. AumEmitter tests
# -----------------------------------------------------------------------

class TestAumEmitter(unittest.TestCase):
    def _make_aum_resolved(self, bindings_spec, au_identifier='Test.AU-1234'):
        pages = []
        page_bindings = []
        for group, index, cc, channel, name, path in bindings_spec:
            ct = ControlType.CONTINUOUS
            slot = ControlSlot(group=group, index=index, control_type=ct)
            param = ParameterRef(plugin_id='test', param_path=path,
                                 display_name=name)
            page_bindings.append(Binding(
                slot=slot,
                param=param,
                midi_channel=channel,
                midi_cc=cc,
                msg_type='cc',
            ))
        pages.append(Page(name='AumTest P01', index=0, bindings=page_bindings))
        spec = MappingSpec(
            name='AumTest',
            controller_id='slmkiii',
            plugin_id='test',
            target_id='aum',
        )
        return ResolvedMapping(
            spec=spec,
            page_set=PageSet(pages=pages),
            metadata={'au_identifier': au_identifier},
        )

    def test_emit_creates_midimap_file(self):
        resolved = self._make_aum_resolved([
            ('knobs', 0, 20, 1, 'Cutoff', 'drumProtoParams.drum1params.drum1cutoff'),
        ])
        emitter = AumEmitter()
        with tempfile.TemporaryDirectory() as tmpdir:
            files = emitter.emit(resolved, tmpdir)
            self.assertEqual(len(files), 1)
            self.assertTrue(files[0].exists())
            self.assertTrue(files[0].name.endswith('.aum_midimap'))

    def test_emitted_midimap_decodable(self):
        resolved = self._make_aum_resolved([
            ('knobs', 0, 20, 1, 'Cutoff', 'drumProtoParams.drum1params.drum1cutoff'),
            ('knobs', 1, 21, 1, 'Reso', 'drumProtoParams.drum1params.drum1resonance'),
        ])
        emitter = AumEmitter()
        with tempfile.TemporaryDirectory() as tmpdir:
            files = emitter.emit(resolved, tmpdir)
            with open(files[0], 'rb') as f:
                data = f.read()
            decoded = _decode_keyed_archiver(data)
            self.assertIsInstance(decoded, dict)

    def test_emitted_midimap_has_channel_root(self):
        resolved = self._make_aum_resolved([
            ('knobs', 0, 20, 1, 'Cutoff', 'drumProtoParams.drum1params.drum1cutoff'),
        ])
        emitter = AumEmitter()
        with tempfile.TemporaryDirectory() as tmpdir:
            files = emitter.emit(resolved, tmpdir)
            with open(files[0], 'rb') as f:
                decoded = _decode_keyed_archiver(f.read())
            self.assertEqual(decoded.get('_collection_map_name'), 'Channel')

    def test_emitted_midimap_has_slot_with_au_identifier(self):
        au_id = 'MyPlugin.AU-ABCD'
        resolved = self._make_aum_resolved(
            [('knobs', 0, 20, 1, 'Cut', 'drumProtoParams.drum1params.drum1cutoff')],
            au_identifier=au_id,
        )
        emitter = AumEmitter()
        with tempfile.TemporaryDirectory() as tmpdir:
            files = emitter.emit(resolved, tmpdir)
            with open(files[0], 'rb') as f:
                decoded = _decode_keyed_archiver(f.read())
            slot0 = decoded.get('slot0')
            self.assertIsNotNone(slot0)
            self.assertEqual(slot0.get('_collection_map_name'), au_id)

    def test_emitted_midimap_param_specstate(self):
        resolved = self._make_aum_resolved([
            ('knobs', 0, 42, 3, 'Cutoff', 'drumProtoParams.drum1params.drum1cutoff'),
        ])
        emitter = AumEmitter()
        with tempfile.TemporaryDirectory() as tmpdir:
            files = emitter.emit(resolved, tmpdir)
            with open(files[0], 'rb') as f:
                decoded = _decode_keyed_archiver(f.read())

            slot0 = decoded['slot0']
            # Navigate the nested path
            level1 = slot0.get('drumProtoParams')
            self.assertIsNotNone(level1, 'Missing drumProtoParams level')
            level2 = level1.get('drumProtoParams.drum1params')
            self.assertIsNotNone(level2, 'Missing drum1params level')
            entry = level2.get('drumProtoParams.drum1params.drum1cutoff')
            self.assertIsNotNone(entry, 'Missing drum1cutoff entry')
            self.assertEqual(entry['specState']['data1'], 42)
            # Channel should be 0-indexed: input 3 -> stored 2
            self.assertEqual(entry['channel'], 2)

    def test_emitted_note_binding(self):
        pages = [Page(name='NoteAum P01', index=0, bindings=[
            Binding(
                slot=ControlSlot(group='pads', index=0,
                                 control_type=ControlType.VELOCITY),
                param=ParameterRef(plugin_id='test',
                                   param_path='trigger',
                                   display_name='Trig'),
                midi_channel=10,
                midi_note=36,
                msg_type='note',
            ),
        ])]
        resolved = ResolvedMapping(
            spec=MappingSpec(name='NoteAum', controller_id='slmkiii',
                             plugin_id='test', target_id='aum'),
            page_set=PageSet(pages=pages),
            metadata={'au_identifier': 'Test.AU-1234'},
        )
        emitter = AumEmitter()
        with tempfile.TemporaryDirectory() as tmpdir:
            files = emitter.emit(resolved, tmpdir)
            with open(files[0], 'rb') as f:
                decoded = _decode_keyed_archiver(f.read())
            slot0 = decoded['slot0']
            entry = slot0.get('trigger')
            self.assertIsNotNone(entry)
            self.assertEqual(entry['specState']['data1'], 36)
            # MSG_TYPE_NOTE = 1
            self.assertEqual(entry['specState']['type'], 1)


# -----------------------------------------------------------------------
# 5. compile_mapping integration test
# -----------------------------------------------------------------------

_BATTALION_DB = _PROJECT_ROOT / 'controlmap' / 'plugins' / 'data' / 'ua_battalion.json'
_SLMKIII_PROFILE = _PROJECT_ROOT / 'controlmap' / 'controllers' / 'data' / 'slmkiii.json'


@unittest.skipUnless(
    _BATTALION_DB.exists() and _SLMKIII_PROFILE.exists(),
    'Plugin DB or controller profile not found',
)
class TestCompileMapping(unittest.TestCase):
    def test_compile_all_params(self):
        spec = MappingSpec(
            name='BatAll',
            controller_id='slmkiii',
            plugin_id='ua_battalion',
            target_id='slmkiii',
            param_selections=[],  # empty = all params
            midi_channel_base=1,
        )
        resolved = compile_mapping(spec)
        self.assertIsInstance(resolved, ResolvedMapping)
        self.assertGreater(len(resolved.page_set.pages), 0)
        self.assertGreater(resolved.page_set.total_bindings, 0)

    def test_compile_drum1_selection(self):
        spec = MappingSpec(
            name='BatDrum1',
            controller_id='slmkiii',
            plugin_id='ua_battalion',
            target_id='slmkiii',
            param_selections=['drumProtoParams.drum1params.*'],
            midi_channel_base=1,
        )
        resolved = compile_mapping(spec)
        self.assertIsInstance(resolved, ResolvedMapping)
        self.assertGreater(len(resolved.page_set.pages), 0)
        # All bindings should reference drum1 params
        for binding in resolved.page_set.all_bindings:
            self.assertIn('drum1', binding.param.param_path)

    def test_cc_assignments_unique_per_channel(self):
        spec = MappingSpec(
            name='BatUniq',
            controller_id='slmkiii',
            plugin_id='ua_battalion',
            target_id='slmkiii',
            param_selections=['drumProtoParams.drum1params.*'],
            midi_channel_base=1,
        )
        resolved = compile_mapping(spec)
        seen: set[tuple[int, int]] = set()
        for binding in resolved.page_set.all_bindings:
            if binding.msg_type == 'cc' and binding.midi_cc != 0:
                key = (binding.midi_channel, binding.midi_cc)
                self.assertNotIn(
                    key, seen,
                    f'Duplicate CC assignment: ch{binding.midi_channel} CC{binding.midi_cc}',
                )
                seen.add(key)

    def test_metadata_populated(self):
        spec = MappingSpec(
            name='BatMeta',
            controller_id='slmkiii',
            plugin_id='ua_battalion',
            target_id='slmkiii',
            param_selections=['drumProtoParams.drum1params.drum1cutoff'],
            midi_channel_base=1,
        )
        resolved = compile_mapping(spec)
        self.assertIn('controller', resolved.metadata)
        self.assertIn('plugin', resolved.metadata)
        self.assertIn('param_count', resolved.metadata)
        self.assertIn('page_count', resolved.metadata)
        self.assertEqual(resolved.metadata['controller'], 'Novation SL MkIII')
        self.assertEqual(resolved.metadata['plugin'], 'UA Battalion')

    def test_page_count_matches_metadata(self):
        spec = MappingSpec(
            name='BatPages',
            controller_id='slmkiii',
            plugin_id='ua_battalion',
            target_id='slmkiii',
            param_selections=['drumProtoParams.drum1params.*'],
            midi_channel_base=1,
        )
        resolved = compile_mapping(spec)
        self.assertEqual(
            len(resolved.page_set.pages),
            resolved.metadata['page_count'],
        )

    def test_midi_channels_in_range(self):
        spec = MappingSpec(
            name='BatCh',
            controller_id='slmkiii',
            plugin_id='ua_battalion',
            target_id='slmkiii',
            param_selections=['drumProtoParams.drum1params.*'],
            midi_channel_base=5,
        )
        resolved = compile_mapping(spec)
        for binding in resolved.page_set.all_bindings:
            self.assertGreaterEqual(binding.midi_channel, 1)
            self.assertLessEqual(binding.midi_channel, 16)


if __name__ == '__main__':
    unittest.main()
