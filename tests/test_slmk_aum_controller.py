"""Unit tests for slmk_aum_controller config + pure logic (no hardware)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

# scripts/ is not a package; add it to path so we can import the controller
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'scripts'))

import slmk_aum_controller as C  # noqa: E402


class TestPageConfig(unittest.TestCase):
    def test_pages_have_unique_names(self):
        names = [p.name for p in C.PAGES]
        self.assertEqual(len(names), len(set(names)),
                         f'duplicate page names: {names}')

    def test_page_labels_within_screen_width(self):
        for p in C.PAGES:
            self.assertLessEqual(len(p.label), 9,
                                 f'page {p.name!r} label too long: {p.label!r}')
            for b in p.knobs + p.faders:
                self.assertLessEqual(len(b.label), 9,
                                     f'binding {b.label!r} too long')

    def test_no_cc_collisions_within_channel(self):
        seen: dict[tuple[int, int], str] = {}
        all_pages = list(C.PAGES) + list(C.DRUM_FOCUS_PAGES.values())
        for p in all_pages:
            for b in p.knobs + p.faders:
                key = (b.channel, b.cc)
                if key in seen and seen[key] != b.param_path:
                    self.fail(f'CC collision on ch{b.channel} CC{b.cc}: '
                              f'{seen[key]!r} vs {b.param_path!r}')
                seen[key] = b.param_path

    def test_drum_focus_pages_complete(self):
        self.assertEqual(len(C.DRUM_FOCUS_PAGES), 8)
        for i, page in C.DRUM_FOCUS_PAGES.items():
            self.assertEqual(len(page.knobs), 4)
            self.assertEqual(len(page.faders), 4)
            self.assertEqual(page.name, f'drum{i + 1}')

    def test_knobs_and_faders_size(self):
        for p in C.PAGES:
            self.assertLessEqual(len(p.knobs), 8, f'{p.name} too many knobs')
            self.assertLessEqual(len(p.faders), 8, f'{p.name} too many faders')


class TestValueToColor(unittest.TestCase):
    def test_thresholds(self):
        self.assertEqual(C._value_to_color(0), C.COL_OFF)
        self.assertEqual(C._value_to_color(15), C.COL_OFF)
        self.assertEqual(C._value_to_color(16), C.COL_DIM_GREEN)
        self.assertEqual(C._value_to_color(48), C.COL_GREEN)
        self.assertEqual(C._value_to_color(96), C.COL_YELLOW)
        self.assertEqual(C._value_to_color(127), C.COL_RED)


class TestControllerState(unittest.TestCase):
    def test_initial_page_is_first(self):
        state = C.ControllerState()
        self.assertEqual(state.current_page_idx, 0)
        self.assertEqual(state.current_page.name, C.PAGES[0].name)

    def test_focus_page_specialization(self):
        state = C.ControllerState()
        state.current_page_idx = 1  # bat_drum
        state.focus_idx = 2
        page = state.current_page
        self.assertEqual(page.name, 'drum3')
        self.assertEqual(page.knobs[0].label, 'D3 Cut')

    def test_value_cache_persists_across_page_change(self):
        state = C.ControllerState()
        binding = C.Binding('Test', 50, 1, 'test_path')
        state.set_value(binding, 99)
        self.assertEqual(state.get_value(binding), 99)
        # Same key on a different page recovers the value
        same_binding = C.Binding('Other', 50, 1, 'other_path')
        self.assertEqual(state.get_value(same_binding), 99)

    def test_value_cache_clamps(self):
        state = C.ControllerState()
        binding = C.Binding('Test', 50, 1, 'test_path', min_val=10, max_val=120)
        state.set_value(binding, 200)
        self.assertEqual(state.get_value(binding), 120)
        state.set_value(binding, -5)
        self.assertEqual(state.get_value(binding), 10)


if __name__ == '__main__':
    unittest.main()
