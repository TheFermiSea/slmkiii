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
        self.assertIn('ccmap', src)
        self.assertIn('Animoog Z', src)  # plugin name in header comment

    def test_generated_script_packs_into_mozaic(self):
        src = generate(_resolved())
        data = build_mozaic(src, 'GEN-TEST')
        decoded = decode_keyed_archiver(data)
        self.assertEqual(decoded['FILENAME'], 'GEN-TEST')
        code = decoded['CODE']['NS.data'].decode('utf-8')
        self.assertIn('@OnLoad', code)
        self.assertIn('ccmap', code)

    def test_generates_one_lookup_per_knob_binding(self):
        # animoog_z mapping puts continuous params on knobs/faders. The first
        # 8 knob slots get screen columns 0..7 if there are enough params.
        src = generate(_resolved())
        # Each knob_screen binding emits a `ccmap[N] = M` line
        lines = [ln for ln in src.splitlines()
                 if ln.strip().startswith('ccmap[')
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


class TestPhase2Features(unittest.TestCase):

    def test_page_navigation_handlers_present(self):
        src = generate(_resolved())
        self.assertIn('@PageUp', src)
        self.assertIn('@PageDown', src)
        # Page nav is gated on InControl channel (15) and the screen-up/down CCs
        self.assertIn(f'MIDIChannel = {ic.INCONTROL_CHANNEL_0IDX}', src)
        self.assertIn(f'MIDIByte2 = {ic.CC_SCREEN_UP}', src)
        self.assertIn(f'MIDIByte2 = {ic.CC_SCREEN_DOWN}', src)

    def test_apply_page_rebuilds_lookup(self):
        src = generate(_resolved())
        self.assertIn('@ApplyPage', src)
        # Lookup table is wiped and per-page entries rewritten
        self.assertIn('FillArray ccmap, -1, 2048', src)

    def test_render_page_for_each_page(self):
        # Construct a multi-page mapping by hand since the paginator currently
        # packs everything into one page. Validates that the generator emits
        # one @RenderPageN per page and the dispatch chain handles multiple.
        from controlmap.model import (
            Binding, ControlSlot, ControlType, Page, PageSet,
            ParameterRef, ResolvedMapping)
        from controlmap.spec_loader import spec_from_dict

        spec = spec_from_dict({'name': 'multi', 'controller': 'slmkiii',
                               'plugin': 'animoog_z'})

        def _page(i: int) -> Page:
            slot = ControlSlot(group='knobs', index=0,
                               control_type=ControlType.CONTINUOUS)
            ref = ParameterRef(plugin_id='animoog_z', param_path=f'p{i}',
                               display_name=f'P{i}')
            return Page(name=f'page-{i}', index=i,
                        bindings=[Binding(slot=slot, param=ref,
                                          midi_channel=1, midi_cc=20 + i)])

        resolved = ResolvedMapping(
            spec=spec,
            page_set=PageSet(pages=[_page(i) for i in range(3)]),
            metadata={'plugin': 'animoog_z', 'page_count': 3,
                      'param_count': 3},
        )
        src = generate(resolved)
        for i in range(3):
            self.assertIn(f'@RenderPage{i}', src, f'missing @RenderPage{i}')
        # Dispatch chain should reference all three
        self.assertIn('if active_page = 0', src)
        self.assertIn('elseif active_page = 1', src)
        self.assertIn('elseif active_page = 2', src)

    def test_button_leds_initialised_for_bound_slots(self):
        src = generate(_resolved())
        # At least one SOFT_BUTTON LED (index 4..19) gets a non-zero color
        # from the per-page render. We check the line shape.
        import re
        m = re.findall(r'SendMIDICC 15, (\d+), (\d+)', src)
        # SOFT_BUTTON_1 through 16 are LED indices 4..19.
        button_leds = [(int(led), int(color))
                       for led, color in m if 4 <= int(led) <= 19]
        self.assertGreater(len(button_leds), 0,
                           'should set at least one button LED')
        self.assertTrue(any(color != 0 for _led, color in button_leds),
                        'at least one button slot should be lit')

    def test_pad_leds_initialised(self):
        # Force a mapping with pad bindings (use a plugin that has triggers)
        # Animoog doesn't have triggers; test with a contrived spec by
        # confirming the code structure is present even with empty pads.
        src = generate(_resolved())
        # Pad LED indices are 0x26..0x35 = 38..53
        self.assertIn('SendMIDICC 15, 38, ', src)
        self.assertIn('SendMIDICC 15, 53, ', src)

    def test_pad_note_handler_present(self):
        src = generate(_resolved())
        self.assertIn('@OnMidiNote', src)
        # Note pass-through to plugin is unconditional
        self.assertIn('SendMIDINoteOn MIDIChannel, MIDIByte2, MIDIByte3', src)
        self.assertIn('SendMIDINoteOff MIDIChannel, MIDIByte2, MIDIByte3', src)

    def test_center_screen_indicator(self):
        src = generate(_resolved())
        # Page indicator goes to column 8 (CENTER) — set_text builds
        # column byte at index 8 of the SysEx envelope. Easier to check by
        # seeing that buf[8] = 8 appears (column = CENTER_COLUMN = 8).
        self.assertIn('buf[8] = 8', src)

    def test_emit_set_value_unchanged(self):
        # The runtime set_value patch from Phase 1 must still be present.
        src = generate(_resolved())
        self.assertIn('@EmitSetValue', src)
        self.assertIn('val_buf[8] = col', src)
        self.assertIn('val_buf[11] = MIDIByte3', src)


if __name__ == '__main__':
    unittest.main()
