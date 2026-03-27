"""Comprehensive tests for the controlmap framework core modules."""
import unittest

from controlmap.model import (
    Binding, ControlSlot, ControlType, Page, PageSet, ParamType, ParameterRef,
)
from controlmap.controllers import ControlGroup, ControllerProfile, Feature
from controlmap.controllers.registry import load_controller, _CACHE as _CTRL_CACHE
from controlmap.plugins import PluginParam, PluginParamDB
from controlmap.plugins.registry import load_plugin, _CACHE as _PLUG_CACHE
from controlmap.strategy import AffinityMapper
from controlmap.paging import Paginator
from controlmap.cc_alloc import CCAllocator


# ---------------------------------------------------------------------------
# Helpers for building inline fixtures
# ---------------------------------------------------------------------------

def _make_slot(group='knobs', index=0, ctype=ControlType.CONTINUOUS,
               has_display=False, display_chars=0):
    return ControlSlot(group=group, index=index, control_type=ctype,
                       has_display=has_display, display_chars=display_chars)


def _make_param(path='p.cutoff', display_name='Cutoff',
                param_type=ParamType.CONTINUOUS, group='synth',
                priority=50, tags=None):
    return PluginParam(path=path, display_name=display_name,
                       param_type=param_type, group=group,
                       priority=priority, tags=tags or [])


def _make_binding(slot=None, param_ref=None, channel=1, cc=0, note=0,
                  msg_type='cc'):
    slot = slot or _make_slot()
    param_ref = param_ref or ParameterRef('test', 'p.x', 'X')
    return Binding(slot=slot, param=param_ref, midi_channel=channel,
                   midi_cc=cc, midi_note=note, msg_type=msg_type)


def _small_profile():
    """A minimal inline controller profile: 4 knobs + 2 buttons + 2 pads."""
    return ControllerProfile(
        id='test_ctrl',
        name='Test Controller',
        control_groups=[
            ControlGroup('knobs', 4, ControlType.CONTINUOUS,
                         has_display=True, display_chars=9),
            ControlGroup('buttons', 2, ControlType.MOMENTARY),
            ControlGroup('pads', 2, ControlType.VELOCITY),
        ],
    )


def _small_param_db():
    """A minimal inline plugin param database with mixed types."""
    params = {
        'synth.cutoff': PluginParam('synth.cutoff', 'Cutoff',
                                    ParamType.CONTINUOUS, 'synth', 90,
                                    ['filter']),
        'synth.resonance': PluginParam('synth.resonance', 'Reso',
                                       ParamType.CONTINUOUS, 'synth', 80,
                                       ['filter']),
        'synth.volume': PluginParam('synth.volume', 'Volume',
                                    ParamType.CONTINUOUS, 'mix', 70,
                                    ['level']),
        'synth.mute': PluginParam('synth.mute', 'Mute',
                                  ParamType.TOGGLE, 'mix', 60,
                                  ['switch']),
        'synth.trigger': PluginParam('synth.trigger', 'Trig',
                                     ParamType.TRIGGER, 'perf', 50,
                                     ['play']),
        'synth.waveform': PluginParam('synth.waveform', 'Waveform',
                                      ParamType.DISCRETE, 'synth', 40),
    }
    return PluginParamDB('test_plug', 'Test Plugin', 'au.test', params)


# ===================================================================
# 1. Model tests
# ===================================================================

class TestControlType(unittest.TestCase):
    def test_all_members(self):
        names = {m.name for m in ControlType}
        self.assertEqual(names, {'CONTINUOUS', 'MOMENTARY', 'VELOCITY', 'TOGGLE'})

    def test_distinct_values(self):
        values = [m.value for m in ControlType]
        self.assertEqual(len(values), len(set(values)))


class TestParamType(unittest.TestCase):
    def test_all_members(self):
        names = {m.name for m in ParamType}
        self.assertEqual(names, {'CONTINUOUS', 'DISCRETE', 'TOGGLE', 'TRIGGER'})

    def test_distinct_values(self):
        values = [m.value for m in ParamType]
        self.assertEqual(len(values), len(set(values)))


class TestPageSet(unittest.TestCase):
    def test_total_bindings_empty(self):
        ps = PageSet(pages=[])
        self.assertEqual(ps.total_bindings, 0)
        self.assertEqual(ps.all_bindings, [])

    def test_total_bindings_single_page(self):
        b1 = _make_binding(cc=20)
        b2 = _make_binding(cc=21)
        ps = PageSet(pages=[Page('P1', 0, [b1, b2])])
        self.assertEqual(ps.total_bindings, 2)
        self.assertEqual(ps.all_bindings, [b1, b2])

    def test_total_bindings_multiple_pages(self):
        b1 = _make_binding(cc=20)
        b2 = _make_binding(cc=21)
        b3 = _make_binding(cc=22)
        ps = PageSet(pages=[Page('P1', 0, [b1, b2]), Page('P2', 1, [b3])])
        self.assertEqual(ps.total_bindings, 3)
        self.assertEqual(ps.all_bindings, [b1, b2, b3])

    def test_all_bindings_preserves_order(self):
        bindings = [_make_binding(cc=i) for i in range(5)]
        p1 = Page('P1', 0, bindings[:3])
        p2 = Page('P2', 1, bindings[3:])
        ps = PageSet(pages=[p1, p2])
        self.assertEqual(ps.all_bindings, bindings)


class TestBindingDefaults(unittest.TestCase):
    def test_defaults(self):
        slot = _make_slot()
        ref = ParameterRef('plug', 'path', 'disp')
        b = Binding(slot=slot, param=ref, midi_channel=1)
        self.assertEqual(b.midi_cc, 0)
        self.assertEqual(b.midi_note, 0)
        self.assertEqual(b.msg_type, 'cc')
        self.assertEqual(b.min_value, 0.0)
        self.assertEqual(b.max_value, 1.0)


# ===================================================================
# 2. ControllerProfile tests (inline fixtures)
# ===================================================================

class TestControllerProfileInline(unittest.TestCase):
    def setUp(self):
        self.profile = _small_profile()

    def test_total_controls(self):
        self.assertEqual(self.profile.total_controls, 8)  # 4+2+2

    def test_slots_count(self):
        self.assertEqual(len(self.profile.slots()), 8)

    def test_slots_types(self):
        slots = self.profile.slots()
        knob_slots = [s for s in slots if s.group == 'knobs']
        btn_slots = [s for s in slots if s.group == 'buttons']
        pad_slots = [s for s in slots if s.group == 'pads']
        self.assertEqual(len(knob_slots), 4)
        self.assertEqual(len(btn_slots), 2)
        self.assertEqual(len(pad_slots), 2)

    def test_slots_by_type(self):
        cont = self.profile.slots_by_type(ControlType.CONTINUOUS)
        self.assertEqual(len(cont), 4)
        for s in cont:
            self.assertEqual(s.control_type, ControlType.CONTINUOUS)

        mom = self.profile.slots_by_type(ControlType.MOMENTARY)
        self.assertEqual(len(mom), 2)

        vel = self.profile.slots_by_type(ControlType.VELOCITY)
        self.assertEqual(len(vel), 2)

    def test_slots_by_group(self):
        knobs = self.profile.slots_by_group('knobs')
        self.assertEqual(len(knobs), 4)
        for s in knobs:
            self.assertEqual(s.group, 'knobs')

    def test_slots_by_group_nonexistent(self):
        self.assertEqual(self.profile.slots_by_group('encoders'), [])

    def test_group_lookup(self):
        g = self.profile.group('knobs')
        self.assertIsNotNone(g)
        self.assertEqual(g.name, 'knobs')
        self.assertEqual(g.count, 4)

    def test_group_none(self):
        self.assertIsNone(self.profile.group('encoders'))

    def test_slot_indices(self):
        knobs = self.profile.slots_by_group('knobs')
        indices = [s.index for s in knobs]
        self.assertEqual(indices, [0, 1, 2, 3])

    def test_slot_display_properties(self):
        knobs = self.profile.slots_by_group('knobs')
        for s in knobs:
            self.assertTrue(s.has_display)
            self.assertEqual(s.display_chars, 9)
        buttons = self.profile.slots_by_group('buttons')
        for s in buttons:
            self.assertFalse(s.has_display)


# ===================================================================
# 2b. ControllerProfile tests (real slmkiii.json)
# ===================================================================

class TestControllerProfileSLMkIII(unittest.TestCase):
    def setUp(self):
        # Clear cache to ensure fresh load each time
        _CTRL_CACHE.pop('slmkiii', None)
        self.profile = load_controller('slmkiii')

    def test_id_and_name(self):
        self.assertEqual(self.profile.id, 'slmkiii')
        self.assertEqual(self.profile.name, 'Novation SL MkIII')

    def test_total_controls(self):
        # 8 knobs + 8 faders + 16 buttons + 16 pads = 48
        self.assertEqual(self.profile.total_controls, 48)

    def test_groups(self):
        names = [g.name for g in self.profile.control_groups]
        self.assertEqual(names, ['knobs', 'faders', 'buttons', 'pads'])

    def test_knobs_have_display(self):
        kg = self.profile.group('knobs')
        self.assertTrue(kg.has_display)
        self.assertEqual(kg.display_chars, 9)

    def test_faders_no_display(self):
        fg = self.profile.group('faders')
        self.assertFalse(fg.has_display)

    def test_features(self):
        self.assertIn(Feature.SCREENS, self.profile.features)
        self.assertIn(Feature.RGB_LEDS, self.profile.features)
        self.assertIn(Feature.VELOCITY_PADS, self.profile.features)
        self.assertNotIn(Feature.MOTORIZED_FADERS, self.profile.features)

    def test_slots_by_type_continuous(self):
        # knobs (8) + faders (8) = 16
        cont = self.profile.slots_by_type(ControlType.CONTINUOUS)
        self.assertEqual(len(cont), 16)

    def test_slots_by_type_momentary(self):
        mom = self.profile.slots_by_type(ControlType.MOMENTARY)
        self.assertEqual(len(mom), 16)

    def test_slots_by_type_velocity(self):
        vel = self.profile.slots_by_type(ControlType.VELOCITY)
        self.assertEqual(len(vel), 16)

    def test_knob_pages_hardware(self):
        kg = self.profile.group('knobs')
        self.assertEqual(kg.pages_hardware, 2)


# ===================================================================
# 3. Controller registry tests
# ===================================================================

class TestControllerRegistry(unittest.TestCase):
    def setUp(self):
        _CTRL_CACHE.clear()

    def test_load_slmkiii(self):
        profile = load_controller('slmkiii')
        self.assertEqual(profile.id, 'slmkiii')
        self.assertIsInstance(profile, ControllerProfile)

    def test_caching(self):
        p1 = load_controller('slmkiii')
        p2 = load_controller('slmkiii')
        self.assertIs(p1, p2)

    def test_file_not_found(self):
        with self.assertRaises(FileNotFoundError):
            load_controller('nonexistent_controller_xyz')


# ===================================================================
# 4. PluginParamDB tests (inline fixtures)
# ===================================================================

class TestPluginParamDBSelect(unittest.TestCase):
    def setUp(self):
        self.db = _small_param_db()

    def test_select_empty_returns_all(self):
        result = self.db.select([])
        self.assertEqual(len(result), 6)

    def test_select_exact_path(self):
        result = self.db.select(['synth.cutoff'])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].path, 'synth.cutoff')

    def test_select_glob_star(self):
        result = self.db.select(['synth.*'])
        self.assertEqual(len(result), 6)

    def test_select_glob_partial(self):
        result = self.db.select(['synth.res*'])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].path, 'synth.resonance')

    def test_select_multiple_patterns(self):
        result = self.db.select(['synth.cutoff', 'synth.mute'])
        self.assertEqual(len(result), 2)
        paths = {p.path for p in result}
        self.assertEqual(paths, {'synth.cutoff', 'synth.mute'})

    def test_select_no_duplicates(self):
        result = self.db.select(['synth.cutoff', 'synth.*'])
        paths = [p.path for p in result]
        self.assertEqual(len(paths), len(set(paths)))

    def test_select_no_match(self):
        result = self.db.select(['nonexistent.*'])
        self.assertEqual(result, [])


class TestPluginParamDBGrouping(unittest.TestCase):
    def setUp(self):
        self.db = _small_param_db()

    def test_by_group(self):
        synth = self.db.by_group('synth')
        self.assertEqual(len(synth), 3)  # cutoff, resonance, waveform
        for p in synth:
            self.assertEqual(p.group, 'synth')

    def test_by_group_empty(self):
        self.assertEqual(self.db.by_group('nonexistent'), [])

    def test_by_priority(self):
        high = self.db.by_priority(min_priority=70)
        self.assertEqual(len(high), 3)  # cutoff=90, resonance=80, volume=70
        # Verify sorted by descending priority
        priorities = [p.priority for p in high]
        self.assertEqual(priorities, sorted(priorities, reverse=True))

    def test_by_priority_zero(self):
        result = self.db.by_priority(min_priority=0)
        self.assertEqual(len(result), 6)

    def test_by_priority_high_threshold(self):
        result = self.db.by_priority(min_priority=100)
        self.assertEqual(result, [])

    def test_by_tags_single(self):
        result = self.db.by_tags('filter')
        self.assertEqual(len(result), 2)
        for p in result:
            self.assertIn('filter', p.tags)

    def test_by_tags_multiple(self):
        result = self.db.by_tags('filter', 'level')
        self.assertEqual(len(result), 3)

    def test_by_tags_no_match(self):
        self.assertEqual(self.db.by_tags('xyz'), [])

    def test_groups(self):
        groups = self.db.groups()
        self.assertIn('synth', groups)
        self.assertIn('mix', groups)
        self.assertIn('perf', groups)
        self.assertEqual(len(groups['synth']), 3)
        self.assertEqual(len(groups['mix']), 2)
        self.assertEqual(len(groups['perf']), 1)


# ===================================================================
# 5. Plugin registry tests
# ===================================================================

class TestPluginRegistry(unittest.TestCase):
    def setUp(self):
        _PLUG_CACHE.clear()

    def test_load_ua_battalion(self):
        db = load_plugin('ua_battalion')
        self.assertEqual(db.plugin_id, 'ua_battalion')
        self.assertEqual(db.plugin_name, 'UA Battalion')
        self.assertIsInstance(db, PluginParamDB)
        self.assertGreater(len(db.params), 0)

    def test_ua_battalion_au_identifier(self):
        db = load_plugin('ua_battalion')
        self.assertTrue(db.au_identifier.startswith('UA Battalion'))

    def test_ua_battalion_param_count(self):
        db = load_plugin('ua_battalion')
        self.assertEqual(len(db.params), 3230)

    def test_caching(self):
        d1 = load_plugin('ua_battalion')
        d2 = load_plugin('ua_battalion')
        self.assertIs(d1, d2)

    def test_file_not_found(self):
        with self.assertRaises(FileNotFoundError):
            load_plugin('nonexistent_plugin_xyz')


# ===================================================================
# 6. AffinityMapper tests
# ===================================================================

class TestAffinityMapper(unittest.TestCase):
    def setUp(self):
        self.mapper = AffinityMapper()

    def test_continuous_to_continuous(self):
        params = [_make_param(param_type=ParamType.CONTINUOUS)]
        slots = [_make_slot(ctype=ControlType.CONTINUOUS)]
        result = self.mapper.assign(params, slots)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0][0].param_type, ParamType.CONTINUOUS)
        self.assertEqual(result[0][1].control_type, ControlType.CONTINUOUS)

    def test_toggle_to_momentary(self):
        params = [_make_param(path='p.mute', param_type=ParamType.TOGGLE)]
        slots = [_make_slot(group='buttons', ctype=ControlType.MOMENTARY)]
        result = self.mapper.assign(params, slots)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0][1].control_type, ControlType.MOMENTARY)

    def test_trigger_to_velocity(self):
        params = [_make_param(path='p.trig', param_type=ParamType.TRIGGER)]
        slots = [_make_slot(group='pads', ctype=ControlType.VELOCITY)]
        result = self.mapper.assign(params, slots)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0][1].control_type, ControlType.VELOCITY)

    def test_priority_ordering(self):
        p_high = _make_param(path='p.hi', priority=90)
        p_low = _make_param(path='p.lo', priority=10)
        slot = _make_slot()
        # Only one slot: highest priority param should win
        result = self.mapper.assign([p_low, p_high], [slot])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0][0].path, 'p.hi')

    def test_display_bonus(self):
        """Slot with display should be preferred over one without, all else equal."""
        p = _make_param(param_type=ParamType.CONTINUOUS)
        s_no_disp = _make_slot(group='faders', index=0,
                               ctype=ControlType.CONTINUOUS)
        s_disp = _make_slot(group='knobs', index=0,
                            ctype=ControlType.CONTINUOUS,
                            has_display=True, display_chars=9)
        result = self.mapper.assign([p], [s_no_disp, s_disp])
        self.assertEqual(len(result), 1)
        self.assertTrue(result[0][1].has_display)

    def test_more_params_than_slots(self):
        params = [_make_param(path=f'p.{i}', priority=50) for i in range(10)]
        slots = [_make_slot(index=i) for i in range(3)]
        result = self.mapper.assign(params, slots)
        self.assertEqual(len(result), 3)

    def test_empty_params(self):
        slots = [_make_slot()]
        result = self.mapper.assign([], slots)
        self.assertEqual(result, [])

    def test_empty_slots(self):
        params = [_make_param()]
        result = self.mapper.assign(params, [])
        self.assertEqual(result, [])

    def test_empty_both(self):
        self.assertEqual(self.mapper.assign([], []), [])

    def test_no_affinity_param_dropped(self):
        """A CONTINUOUS param has no affinity for TOGGLE slots -> score 0 -> skipped."""
        params = [_make_param(param_type=ParamType.CONTINUOUS)]
        slots = [_make_slot(group='toggles', ctype=ControlType.TOGGLE)]
        result = self.mapper.assign(params, slots)
        self.assertEqual(result, [])

    def test_discrete_prefers_continuous_over_momentary(self):
        """DISCRETE -> CONTINUOUS has 0.7 affinity, DISCRETE -> MOMENTARY has 0.4."""
        p = _make_param(param_type=ParamType.DISCRETE)
        s_cont = _make_slot(group='knobs', index=0,
                            ctype=ControlType.CONTINUOUS)
        s_mom = _make_slot(group='buttons', index=0,
                           ctype=ControlType.MOMENTARY)
        result = self.mapper.assign([p], [s_cont, s_mom])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0][1].control_type, ControlType.CONTINUOUS)

    def test_all_slots_consumed(self):
        """When each param perfectly matches each slot type, all should be assigned."""
        params = [
            _make_param(path='p.knob', param_type=ParamType.CONTINUOUS, priority=90),
            _make_param(path='p.btn', param_type=ParamType.TOGGLE, priority=80),
            _make_param(path='p.pad', param_type=ParamType.TRIGGER, priority=70),
        ]
        slots = [
            _make_slot(group='knobs', ctype=ControlType.CONTINUOUS),
            _make_slot(group='buttons', ctype=ControlType.MOMENTARY),
            _make_slot(group='pads', ctype=ControlType.VELOCITY),
        ]
        result = self.mapper.assign(params, slots)
        self.assertEqual(len(result), 3)


# ===================================================================
# 7. Paginator tests
# ===================================================================

class TestPaginator(unittest.TestCase):
    def setUp(self):
        self.paginator = Paginator()
        self.profile = _small_profile()
        self.all_slots = self.profile.slots()

    def test_single_page_fits_all(self):
        params = [_make_param(path=f'p.{i}') for i in range(3)]
        slots = self.all_slots[:3]
        assignments = list(zip(params, slots))
        ps = self.paginator.paginate(assignments, self.all_slots)
        self.assertEqual(len(ps.pages), 1)
        self.assertEqual(len(ps.pages[0].bindings), 3)

    def test_multiple_pages_slot_reuse(self):
        """Two params assigned to the same slot -> requires 2 pages."""
        slot = _make_slot(group='knobs', index=0)
        p1 = _make_param(path='p.a', priority=90)
        p2 = _make_param(path='p.b', priority=80)
        assignments = [(p1, slot), (p2, slot)]
        ps = self.paginator.paginate(assignments, self.all_slots)
        self.assertEqual(len(ps.pages), 2)
        self.assertEqual(len(ps.pages[0].bindings), 1)
        self.assertEqual(len(ps.pages[1].bindings), 1)

    def test_reserved_bindings_on_every_page(self):
        slot = _make_slot(group='knobs', index=0)
        p1 = _make_param(path='p.a', priority=90)
        p2 = _make_param(path='p.b', priority=80)
        assignments = [(p1, slot), (p2, slot)]
        reserved = [_make_binding(
            slot=_make_slot(group='buttons', index=0,
                            ctype=ControlType.MOMENTARY),
            channel=10, cc=99,
        )]
        ps = self.paginator.paginate(assignments, self.all_slots,
                                     reserved_bindings=reserved)
        self.assertEqual(len(ps.pages), 2)
        for page in ps.pages:
            # Each page has 1 assignment binding + 1 reserved binding
            self.assertEqual(len(page.bindings), 2)

    def test_empty_assignments(self):
        ps = self.paginator.paginate([], self.all_slots)
        self.assertEqual(len(ps.pages), 0)
        self.assertEqual(ps.total_bindings, 0)

    def test_page_naming(self):
        slot = _make_slot()
        p = _make_param()
        ps = self.paginator.paginate([(p, slot)], self.all_slots,
                                     mapping_name='MyMap')
        self.assertEqual(ps.pages[0].name, 'MyMap P01')

    def test_page_naming_multiple(self):
        slot = _make_slot(group='knobs', index=0)
        p1 = _make_param(path='p.a', priority=90)
        p2 = _make_param(path='p.b', priority=80)
        ps = self.paginator.paginate([(p1, slot), (p2, slot)], self.all_slots,
                                     mapping_name='Test')
        self.assertEqual(ps.pages[0].name, 'Test P01')
        self.assertEqual(ps.pages[1].name, 'Test P02')

    def test_page_indices(self):
        slot = _make_slot(group='knobs', index=0)
        params = [_make_param(path=f'p.{i}', priority=90 - i)
                  for i in range(3)]
        assignments = [(p, slot) for p in params]
        ps = self.paginator.paginate(assignments, self.all_slots)
        self.assertEqual(len(ps.pages), 3)
        for i, page in enumerate(ps.pages):
            self.assertEqual(page.index, i)

    def test_trigger_gets_note_msg_type(self):
        p = _make_param(param_type=ParamType.TRIGGER)
        slot = _make_slot(group='pads', ctype=ControlType.VELOCITY)
        ps = self.paginator.paginate([(p, slot)], self.all_slots)
        self.assertEqual(ps.pages[0].bindings[0].msg_type, 'note')

    def test_continuous_gets_cc_msg_type(self):
        p = _make_param(param_type=ParamType.CONTINUOUS)
        slot = _make_slot()
        ps = self.paginator.paginate([(p, slot)], self.all_slots)
        self.assertEqual(ps.pages[0].bindings[0].msg_type, 'cc')


# ===================================================================
# 8. CCAllocator tests
# ===================================================================

class TestCCAllocator(unittest.TestCase):
    def setUp(self):
        self.allocator = CCAllocator()

    def _make_page_set(self, bindings_per_page):
        """Build a PageSet from a list of binding lists."""
        pages = []
        for i, bindings in enumerate(bindings_per_page):
            pages.append(Page(f'P{i+1}', i, bindings))
        return PageSet(pages=pages)

    def test_sequential_cc_starting_at_20(self):
        bindings = [
            _make_binding(slot=_make_slot(index=i), channel=0, cc=0)
            for i in range(3)
        ]
        ps = self._make_page_set([bindings])
        self.allocator.allocate(ps, channel_base=1)
        self.assertEqual(bindings[0].midi_cc, 20)
        self.assertEqual(bindings[1].midi_cc, 21)
        self.assertEqual(bindings[2].midi_cc, 22)
        for b in bindings:
            self.assertEqual(b.midi_channel, 1)

    def test_skips_reserved_bindings(self):
        reserved = _make_binding(
            slot=_make_slot(group='buttons', index=0,
                            ctype=ControlType.MOMENTARY),
            channel=1, cc=20,
        )
        normal = _make_binding(slot=_make_slot(index=0), channel=0, cc=0)
        ps = self._make_page_set([[reserved, normal]])
        self.allocator.allocate(ps, channel_base=1)
        # Reserved keeps its original values
        self.assertEqual(reserved.midi_cc, 20)
        self.assertEqual(reserved.midi_channel, 1)
        # Normal skips CC20 (reserved) and gets CC21
        self.assertEqual(normal.midi_cc, 21)
        self.assertEqual(normal.midi_channel, 1)

    def test_note_type_gets_midi_note_not_cc(self):
        binding = _make_binding(
            slot=_make_slot(group='pads', index=3, ctype=ControlType.VELOCITY),
            channel=0, cc=0, msg_type='note',
        )
        ps = self._make_page_set([[binding]])
        self.allocator.allocate(ps, channel_base=5)
        self.assertEqual(binding.midi_channel, 5)
        self.assertEqual(binding.midi_note, 36 + 3)  # 39
        self.assertEqual(binding.midi_cc, 0)  # unchanged

    def test_cc_exhaustion_raises(self):
        # 100 CC bindings on one channel (only 100 CCs available: 20-119)
        bindings = [
            _make_binding(slot=_make_slot(index=i % 8), channel=0, cc=0)
            for i in range(100)
        ]
        ps = self._make_page_set([bindings])
        self.allocator.allocate(ps, channel_base=1)
        self.assertEqual(bindings[-1].midi_cc, 119)

        # 101 bindings should exhaust the range
        bindings_overflow = [
            _make_binding(slot=_make_slot(index=i % 8), channel=0, cc=0)
            for i in range(101)
        ]
        ps2 = self._make_page_set([bindings_overflow])
        with self.assertRaises(ValueError) as ctx:
            self.allocator.allocate(ps2, channel_base=1)
        self.assertIn('Exhausted CC range', str(ctx.exception))

    def test_channel_per_page_mode(self):
        b1 = _make_binding(slot=_make_slot(index=0), channel=0, cc=0)
        b2 = _make_binding(slot=_make_slot(index=0), channel=0, cc=0)
        ps = self._make_page_set([[b1], [b2]])
        self.allocator.allocate(ps, channel_base=3, channel_per_page=True)
        # Page 0 -> channel 3, Page 1 -> channel 4
        self.assertEqual(b1.midi_channel, 3)
        self.assertEqual(b2.midi_channel, 4)
        # Both start at CC20 since different channels
        self.assertEqual(b1.midi_cc, 20)
        self.assertEqual(b2.midi_cc, 20)

    def test_channel_per_page_shared_cc_range(self):
        """Each channel gets its own CC range starting at 20."""
        bindings_p1 = [
            _make_binding(slot=_make_slot(index=i), channel=0, cc=0)
            for i in range(5)
        ]
        bindings_p2 = [
            _make_binding(slot=_make_slot(index=i), channel=0, cc=0)
            for i in range(5)
        ]
        ps = self._make_page_set([bindings_p1, bindings_p2])
        self.allocator.allocate(ps, channel_base=1, channel_per_page=True)
        # Page 1 CCs
        ccs_p1 = [b.midi_cc for b in bindings_p1]
        self.assertEqual(ccs_p1, [20, 21, 22, 23, 24])
        # Page 2 reuses same CC range on a different channel
        ccs_p2 = [b.midi_cc for b in bindings_p2]
        self.assertEqual(ccs_p2, [20, 21, 22, 23, 24])

    def test_channel_per_page_wraps_past_16(self):
        """Channels wrap around when exceeding 16."""
        pages_bindings = []
        for _ in range(15):
            pages_bindings.append([
                _make_binding(slot=_make_slot(index=0), channel=0, cc=0)
            ])
        ps = self._make_page_set(pages_bindings)
        self.allocator.allocate(ps, channel_base=14, channel_per_page=True)
        # Page 0 -> ch14, Page 1 -> ch15, Page 2 -> ch16, Page 3 -> ch14 (wrap)
        self.assertEqual(ps.pages[0].bindings[0].midi_channel, 14)
        self.assertEqual(ps.pages[1].bindings[0].midi_channel, 15)
        self.assertEqual(ps.pages[2].bindings[0].midi_channel, 16)
        self.assertEqual(ps.pages[3].bindings[0].midi_channel, 14)  # wrap

    def test_shared_channel_unique_ccs_across_pages(self):
        """Without channel_per_page, CCs must be unique across all pages."""
        b1 = _make_binding(slot=_make_slot(index=0), channel=0, cc=0)
        b2 = _make_binding(slot=_make_slot(index=0), channel=0, cc=0)
        ps = self._make_page_set([[b1], [b2]])
        self.allocator.allocate(ps, channel_base=1, channel_per_page=False)
        self.assertEqual(b1.midi_channel, 1)
        self.assertEqual(b2.midi_channel, 1)
        self.assertEqual(b1.midi_cc, 20)
        self.assertEqual(b2.midi_cc, 21)  # must differ

    def test_empty_page_set(self):
        ps = self._make_page_set([])
        # Should not raise
        self.allocator.allocate(ps, channel_base=1)
        self.assertEqual(ps.total_bindings, 0)


if __name__ == '__main__':
    unittest.main()
