"""Unit tests for slmkiii.controller config + pure logic (no hardware)."""

from __future__ import annotations

import unittest

from slmkiii.controller import Binding, ControllerState, value_to_fader_color
from slmkiii.controller.pages import DEFAULT_PAGES, PROJECTS, get_pages
from slmkiii.controller.pages.battalion import DRUM_FOCUS_PAGES
from slmkiii.sysex import Color


class TestPageConfig(unittest.TestCase):
    def test_pages_have_unique_names(self):
        names = [p.name for p in DEFAULT_PAGES]
        self.assertEqual(len(names), len(set(names)),
                         f'duplicate page names: {names}')

    def test_page_labels_within_screen_width(self):
        for p in DEFAULT_PAGES:
            self.assertLessEqual(len(p.label), 9,
                                 f'page {p.name!r} label too long: {p.label!r}')
            for b in p.knobs + p.faders:
                self.assertLessEqual(len(b.label), 9,
                                     f'binding {b.label!r} too long')

    def test_no_cc_collisions_within_channel(self):
        seen: dict[tuple[int, int], str] = {}
        all_pages = list(DEFAULT_PAGES) + list(DRUM_FOCUS_PAGES.values())
        for p in all_pages:
            for b in p.knobs + p.faders:
                key = (b.channel, b.cc)
                if key in seen and seen[key] != b.param_path:
                    self.fail(f'CC collision on ch{b.channel} CC{b.cc}: '
                              f'{seen[key]!r} vs {b.param_path!r}')
                seen[key] = b.param_path

    def test_drum_focus_pages_complete(self):
        self.assertEqual(len(DRUM_FOCUS_PAGES), 8)
        for i, page in DRUM_FOCUS_PAGES.items():
            self.assertEqual(len(page.knobs), 4)
            self.assertEqual(len(page.faders), 4)
            self.assertEqual(page.name, f'drum{i + 1}')

    def test_knobs_and_faders_size(self):
        for p in DEFAULT_PAGES:
            self.assertLessEqual(len(p.knobs), 8, f'{p.name} too many knobs')
            self.assertLessEqual(len(p.faders), 8, f'{p.name} too many faders')

    def test_get_pages_default_matches_default_pages(self):
        self.assertIs(get_pages('default'), DEFAULT_PAGES)

    def test_get_pages_unknown_project_raises(self):
        with self.assertRaises(KeyError):
            get_pages('does-not-exist')

    def test_known_projects(self):
        self.assertIn('battalion', PROJECTS)
        self.assertIn('animoog', PROJECTS)
        self.assertIn('drambo', PROJECTS)


class TestValueToFaderColor(unittest.TestCase):
    def test_thresholds(self):
        self.assertEqual(value_to_fader_color(0), Color.OFF)
        self.assertEqual(value_to_fader_color(15), Color.OFF)
        self.assertEqual(value_to_fader_color(16), Color.DIM_GREEN)
        self.assertEqual(value_to_fader_color(48), Color.GREEN)
        self.assertEqual(value_to_fader_color(96), Color.YELLOW)
        self.assertEqual(value_to_fader_color(127), Color.RED)


class TestControllerState(unittest.TestCase):
    def test_initial_page_is_first(self):
        state = ControllerState(DEFAULT_PAGES)
        self.assertEqual(state.current_page_idx, 0)
        self.assertEqual(state.current_page.name, DEFAULT_PAGES[0].name)

    def test_focus_page_specialization(self):
        state = ControllerState(DEFAULT_PAGES)
        # Page index 1 is bat_drum (the focused page)
        state.current_page_idx = 1
        state.focus_idx = 2
        page = state.current_page
        self.assertEqual(page.name, 'drum3')
        self.assertEqual(page.knobs[0].label, 'D3 Cut')

    def test_value_cache_persists_across_page_change(self):
        state = ControllerState(DEFAULT_PAGES)
        binding = Binding('Test', 50, 1, 'test_path')
        state.set_value(binding, 99)
        self.assertEqual(state.get_value(binding), 99)
        # Same key on a different binding instance recovers the value
        same_binding = Binding('Other', 50, 1, 'other_path')
        self.assertEqual(state.get_value(same_binding), 99)

    def test_value_cache_clamps(self):
        state = ControllerState(DEFAULT_PAGES)
        binding = Binding('Test', 50, 1, 'test_path', min_val=10, max_val=120)
        state.set_value(binding, 200)
        self.assertEqual(state.get_value(binding), 120)
        state.set_value(binding, -5)
        self.assertEqual(state.get_value(binding), 10)


if __name__ == '__main__':
    unittest.main()
