"""Tests for the YAML/JSON MappingSpec loader."""

import json
import tempfile
import unittest
from pathlib import Path

from controlmap.spec_loader import load_spec, spec_from_dict


class TestSpecFromDict(unittest.TestCase):

    def test_minimal(self):
        spec = spec_from_dict({
            'name': 'test',
            'controller': 'slmkiii',
            'plugin': 'animoog_z',
        })
        self.assertEqual(spec.name, 'test')
        self.assertEqual(spec.controller_id, 'slmkiii')
        self.assertEqual(spec.plugin_id, 'animoog_z')
        self.assertEqual(spec.target_id, 'aum')  # default
        self.assertEqual(spec.midi_channel_base, 1)
        self.assertEqual(spec.param_selections, [])
        self.assertEqual(spec.param_priorities, {})

    def test_full(self):
        spec = spec_from_dict({
            'name': 'animoog_perform',
            'controller': 'slmkiii',
            'plugin': 'animoog_z',
            'target': 'aum',
            'midi_channel_base': 3,
            'parameters': ['filter.*', 'envelope.attack'],
            'priorities': {'filter.cutoff': 100, 'filter.resonance': 90},
        })
        self.assertEqual(spec.midi_channel_base, 3)
        self.assertEqual(spec.param_selections, ['filter.*', 'envelope.attack'])
        self.assertEqual(spec.param_priorities,
                         {'filter.cutoff': 100, 'filter.resonance': 90})

    def test_priorities_coerced_to_int(self):
        spec = spec_from_dict({
            'name': 'x', 'controller': 'a', 'plugin': 'b',
            'priorities': {'p': '42'},
        })
        self.assertEqual(spec.param_priorities['p'], 42)

    def test_missing_required_key_raises(self):
        with self.assertRaises(KeyError):
            spec_from_dict({'controller': 'x', 'plugin': 'y'})  # missing name

    def test_non_dict_root_raises(self):
        with self.assertRaises(ValueError):
            spec_from_dict([])  # type: ignore[arg-type]

    def test_parameters_must_be_list(self):
        with self.assertRaises(ValueError):
            spec_from_dict({
                'name': 'x', 'controller': 'a', 'plugin': 'b',
                'parameters': 'not a list',
            })

    def test_priorities_must_be_dict(self):
        with self.assertRaises(ValueError):
            spec_from_dict({
                'name': 'x', 'controller': 'a', 'plugin': 'b',
                'priorities': ['list', 'not', 'dict'],
            })

    def test_routes_parsed(self):
        spec = spec_from_dict({
            'name': 'x', 'controller': 'a', 'plugin': 'b',
            'routes': [
                {'page': 0, 'in_ch': 1, 'in_cc': 20, 'out_ch': 2, 'out_cc': 40},
                {'page': 1, 'in_channel': 1, 'in_cc': 20,
                 'out_channel': 3, 'out_cc': 50},
            ],
        })
        self.assertEqual(len(spec.routes), 2)
        self.assertEqual(spec.routes[0].page, 0)
        self.assertEqual(spec.routes[0].in_channel, 1)
        self.assertEqual(spec.routes[0].out_cc, 40)
        self.assertEqual(spec.routes[1].out_channel, 3)

    def test_route_missing_field_raises(self):
        with self.assertRaises(ValueError):
            spec_from_dict({
                'name': 'x', 'controller': 'a', 'plugin': 'b',
                'routes': [{'page': 0, 'in_cc': 20}],  # missing most fields
            })

    def test_routes_must_be_list(self):
        with self.assertRaises(ValueError):
            spec_from_dict({
                'name': 'x', 'controller': 'a', 'plugin': 'b',
                'routes': 'not a list',
            })


class TestLoadSpecFromFile(unittest.TestCase):

    def test_load_json(self):
        with tempfile.NamedTemporaryFile('w', suffix='.json', delete=False) as f:
            json.dump({
                'name': 'json_test',
                'controller': 'slmkiii',
                'plugin': 'animoog_z',
                'parameters': ['filter.*'],
            }, f)
            path = f.name
        try:
            spec = load_spec(path)
            self.assertEqual(spec.name, 'json_test')
            self.assertEqual(spec.param_selections, ['filter.*'])
        finally:
            Path(path).unlink()

    def test_load_yaml(self):
        try:
            import yaml  # noqa: F401
        except ImportError:
            self.skipTest('PyYAML not available')
        body = (
            'name: yaml_test\n'
            'controller: slmkiii\n'
            'plugin: ua_battalion\n'
            'parameters:\n'
            '  - "drum1*"\n'
            '  - "drum2*"\n'
            'priorities:\n'
            '  drum1cutoff: 100\n'
        )
        with tempfile.NamedTemporaryFile('w', suffix='.yaml', delete=False) as f:
            f.write(body)
            path = f.name
        try:
            spec = load_spec(path)
            self.assertEqual(spec.name, 'yaml_test')
            self.assertEqual(spec.plugin_id, 'ua_battalion')
            self.assertEqual(spec.param_selections, ['drum1*', 'drum2*'])
            self.assertEqual(spec.param_priorities, {'drum1cutoff': 100})
        finally:
            Path(path).unlink()


if __name__ == '__main__':
    unittest.main()
