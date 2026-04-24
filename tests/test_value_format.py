"""Tests for unit-aware value rendering."""

import unittest

from controlmap.model import ParameterRef
from controlmap.value_format import format_value, raw_to_real


def _ref(**kw) -> ParameterRef:
    base = dict(plugin_id='test', param_path='p', display_name='p')
    base.update(kw)
    return ParameterRef(**base)


class TestRawToReal(unittest.TestCase):

    def test_linear(self):
        ref = _ref(value_min=0.0, value_max=100.0, taper='lin')
        self.assertAlmostEqual(raw_to_real(0, ref), 0.0)
        self.assertAlmostEqual(raw_to_real(127, ref), 100.0)
        self.assertAlmostEqual(raw_to_real(64, ref), 64 / 127 * 100)

    def test_log(self):
        ref = _ref(value_min=20.0, value_max=20000.0, taper='log')
        self.assertAlmostEqual(raw_to_real(0, ref), 20.0)
        self.assertAlmostEqual(raw_to_real(127, ref), 20000.0)
        # Halfway should be ~ geometric mean (log midpoint)
        mid = raw_to_real(64, ref)
        # geometric midpoint of 20..20000 ≈ 632
        self.assertGreater(mid, 500)
        self.assertLess(mid, 800)

    def test_exp(self):
        ref = _ref(value_min=0.0, value_max=10.0, taper='exp')
        self.assertAlmostEqual(raw_to_real(0, ref), 0.0)
        self.assertAlmostEqual(raw_to_real(127, ref), 10.0)
        # Quarter point: norm=0.25, value = 10 * 0.25^2 = 0.625
        v = raw_to_real(32, ref)
        self.assertLess(v, raw_to_real(64, ref) / 2)


class TestFormatValue(unittest.TestCase):

    def test_discrete_labels(self):
        ref = _ref(discrete_labels=('Off', 'On'))
        self.assertEqual(format_value(0, ref), 'Off')
        self.assertEqual(format_value(127, ref), 'On')
        self.assertEqual(format_value(64, ref), 'On')

    def test_discrete_three_way(self):
        ref = _ref(discrete_labels=('Lo', 'Mid', 'Hi'))
        self.assertEqual(format_value(0, ref), 'Lo')
        self.assertEqual(format_value(60, ref), 'Mid')
        self.assertEqual(format_value(127, ref), 'Hi')

    def test_unit_hz_formatting(self):
        ref = _ref(unit='Hz', value_min=20.0, value_max=20000.0, taper='log')
        s = format_value(127, ref)
        self.assertIn('Hz', s)
        self.assertLessEqual(len(s), 9)

    def test_unit_db(self):
        ref = _ref(unit='dB', value_min=-60.0, value_max=6.0, taper='lin')
        self.assertIn('dB', format_value(64, ref))

    def test_percent_fallback(self):
        # No metadata, no labels: show percentage
        ref = _ref()
        self.assertEqual(format_value(0, ref), '0%')
        self.assertEqual(format_value(127, ref), '100%')
        self.assertEqual(format_value(64, ref), '50%')

    def test_max_chars_respected(self):
        ref = _ref(unit='Hz', value_min=20.0, value_max=20000.0, taper='log')
        for raw in range(0, 128, 10):
            self.assertLessEqual(len(format_value(raw, ref, max_chars=9)), 9)


if __name__ == '__main__':
    unittest.main()
