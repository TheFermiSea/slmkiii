"""Test hot-reload behavior on the ControlSurface without real hardware."""

import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from controlmap import compile_mapping
from controlmap.spec_loader import load_spec
from controlmap.surface import ControlSurface


def _write_spec(path: Path, params: list[str]) -> None:
    path.write_text(
        'name: hot_reload_test\n'
        'controller: slmkiii\n'
        'plugin: animoog_z\n'
        'target: aum\n'
        'midi_channel_base: 1\n'
        'parameters:\n'
        + ''.join(f'  - "{p}"\n' for p in params)
    )


class TestHotReload(unittest.TestCase):

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix='hot_reload_'))
        self.spec_path = self.tmpdir / 'spec.yaml'
        _write_spec(self.spec_path, ['env_reset_t', 'orb_rate_k'])

    def test_detects_spec_change_and_recompiles(self):
        spec = load_spec(self.spec_path)
        resolved = compile_mapping(spec)
        initial_params = resolved.metadata['param_count']

        surface = ControlSurface(resolved, spec_path=str(self.spec_path))
        # Override the cached mtime to make the reload check cheap
        surface._last_reload_check = 0.0

        # Mock InControl - hot reload needs to call notify() and refresh_*().
        # Also need to set _midi_out / _feedback_in to bypass pushing
        ic = MagicMock()

        # Change the spec: add more params
        time.sleep(0.01)  # ensure mtime delta
        new_mtime = time.time()
        _write_spec(self.spec_path, ['*'])  # select ALL params
        os.utime(self.spec_path, (new_mtime, new_mtime))

        # Trigger hot reload
        surface._maybe_hot_reload(ic)

        # Verify surface state was updated
        new_params = surface._resolved.metadata['param_count']
        self.assertGreater(new_params, initial_params,
                           'reload should have loaded more params')
        ic.notify.assert_called()  # confirms the reload path ran

    def test_no_reload_when_mtime_unchanged(self):
        spec = load_spec(self.spec_path)
        resolved = compile_mapping(spec)
        surface = ControlSurface(resolved, spec_path=str(self.spec_path))
        surface._last_reload_check = 0.0
        ic = MagicMock()
        surface._maybe_hot_reload(ic)
        # Nothing should have happened (no reload)
        ic.notify.assert_not_called()

    def test_bad_spec_does_not_crash(self):
        spec = load_spec(self.spec_path)
        resolved = compile_mapping(spec)
        surface = ControlSurface(resolved, spec_path=str(self.spec_path))
        surface._last_reload_check = 0.0

        time.sleep(0.01)
        self.spec_path.write_text('!!! not valid yaml :::')
        os.utime(self.spec_path, (time.time(), time.time()))
        ic = MagicMock()

        # Should log and continue, not raise
        surface._maybe_hot_reload(ic)
        ic.notify.assert_not_called()

    def test_spec_path_none_never_reloads(self):
        spec = load_spec(self.spec_path)
        resolved = compile_mapping(spec)
        surface = ControlSurface(resolved, spec_path=None)
        ic = MagicMock()
        surface._maybe_hot_reload(ic)
        ic.notify.assert_not_called()


if __name__ == '__main__':
    unittest.main()
