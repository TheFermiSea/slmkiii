"""Test that the ControlSurface pushes per-page routes to the bridge."""

import unittest
from unittest.mock import MagicMock

import mido

from controlmap import bridge_protocol as bp
from controlmap import compile_mapping
from controlmap.spec_loader import spec_from_dict
from controlmap.surface import ControlSurface


class TestRoutePush(unittest.TestCase):

    def _build_surface(self, routes_dict: list[dict]) -> ControlSurface:
        spec = spec_from_dict({
            'name': 'route_test',
            'controller': 'slmkiii',
            'plugin': 'animoog_z',
            'parameters': ['env_reset_t', 'orb_rate_k'],
            'routes': routes_dict,
        })
        resolved = compile_mapping(spec)
        return ControlSurface(resolved, midi_output=None, feedback_port=None)

    def _capture_pushed_messages(self, surface: ControlSurface) -> list[mido.Message]:
        sent: list[mido.Message] = []
        mock_out = MagicMock()
        mock_out.send.side_effect = lambda m: sent.append(m)
        surface._midi_out = mock_out
        surface._feedback_in = MagicMock()  # truthy so push runs
        surface._build_feedback_index()
        surface._push_watch_table()
        return sent

    def test_push_watch_table_emits_clear_then_routes(self):
        surface = self._build_surface([
            {'page': 0, 'in_ch': 1, 'in_cc': 20, 'out_ch': 2, 'out_cc': 40},
            {'page': 1, 'in_ch': 1, 'in_cc': 20, 'out_ch': 3, 'out_cc': 50},
        ])
        sent = self._capture_pushed_messages(surface)

        # CLEAR_WATCHES and ROUTE_CLEAR should both fire before any data
        opcodes = [bp.parse(m)[0] if bp.parse(m) else None for m in sent]
        self.assertIn(bp.CMD_CLEAR_WATCHES, opcodes)
        self.assertIn(bp.CMD_ROUTE_CLEAR, opcodes)
        self.assertIn(bp.CMD_WATCH_CC, opcodes)
        self.assertIn(bp.CMD_ROUTE_SET, opcodes)
        self.assertIn(bp.CMD_GET_VALUES, opcodes)

        # Verify CLEAR_WATCHES precedes WATCH_CC
        self.assertLess(opcodes.index(bp.CMD_CLEAR_WATCHES),
                        opcodes.index(bp.CMD_WATCH_CC))

        # Recover routes from the ROUTE_SET messages
        recovered: list[bp.Route] = []
        for m in sent:
            parsed = bp.parse(m)
            if parsed and parsed[0] == bp.CMD_ROUTE_SET:
                payload = parsed[1]
                for i in range(0, len(payload), 5):
                    recovered.append(bp.Route(*payload[i:i + 5]))
        self.assertEqual(len(recovered), 2)
        self.assertEqual(recovered[0].out_cc, 40)
        # Channels are 0-indexed in the wire payload
        self.assertEqual(recovered[0].in_ch, 0)
        self.assertEqual(recovered[1].out_ch, 2)

    def test_push_with_no_routes_still_works(self):
        surface = self._build_surface([])
        sent = self._capture_pushed_messages(surface)
        opcodes = [bp.parse(m)[0] if bp.parse(m) else None for m in sent]
        self.assertIn(bp.CMD_WATCH_CC, opcodes)
        self.assertNotIn(bp.CMD_ROUTE_SET, opcodes)


if __name__ == '__main__':
    unittest.main()
