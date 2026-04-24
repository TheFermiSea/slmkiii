"""Smoke tests for the `slmkiii surface ...` CLI subcommands.

These tests exercise the CLI handler functions directly with argparse
namespaces so we don't have to spawn subprocesses. The push/run subcommands
that touch real hardware are not exercised here — they're covered by manual
integration testing.
"""

import argparse
import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from slmkiii.cli import cmd_surface_compile, cmd_surface_inspect


def _write_spec(dir_: Path, name: str, plugin: str = 'animoog_z') -> Path:
    spec = dir_ / f'{name}.yaml'
    spec.write_text(
        f'name: {name}\n'
        f'controller: slmkiii\n'
        f'plugin: {plugin}\n'
        f'target: aum\n'
        f'midi_channel_base: 1\n'
        f'parameters:\n'
        f'  - "*"\n'
    )
    return spec


class TestSurfaceCompile(unittest.TestCase):

    def test_compile_produces_all_artifacts(self):
        with tempfile.TemporaryDirectory() as td:
            tdir = Path(td)
            spec = _write_spec(tdir, 'cli_compile_test')
            out = tdir / 'build'
            args = argparse.Namespace(spec=str(spec), out_dir=str(out))
            buf = io.StringIO()
            with redirect_stdout(buf):
                cmd_surface_compile(args)

            syx_files = list(out.glob('*.syx'))
            map_files = list(out.glob('*.aum_midimap'))
            mozaic_files = list(out.glob('SLMK-BRIDGE.mozaic'))

            self.assertGreater(len(syx_files), 0, 'no .syx generated')
            self.assertGreater(len(map_files), 0, 'no .aum_midimap generated')
            self.assertEqual(len(mozaic_files), 1, 'SLMK-BRIDGE.mozaic missing')

            for f in syx_files + map_files + mozaic_files:
                self.assertGreater(f.stat().st_size, 0, f'{f.name} is empty')


class TestSurfaceInspect(unittest.TestCase):

    def test_inspect_prints_summary(self):
        with tempfile.TemporaryDirectory() as td:
            spec = _write_spec(Path(td), 'cli_inspect_test')
            args = argparse.Namespace(spec=str(spec))
            buf = io.StringIO()
            with redirect_stdout(buf):
                cmd_surface_inspect(args)
            output = buf.getvalue()
            self.assertIn('cli_inspect_test', output)
            self.assertIn('controller:  slmkiii', output)
            self.assertIn('plugin:      animoog_z', output)
            self.assertIn('Page', output)


if __name__ == '__main__':
    unittest.main()
