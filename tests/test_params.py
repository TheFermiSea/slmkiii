"""Tests for slmkiii.params — Parameter / ParameterProvider observer pattern."""
from __future__ import annotations

import unittest

from slmkiii.params import (
    Parameter,
    SelectedFocusProvider,
    StaticParameterProvider,
)


def _mk(name: str = "p", cc: int = 20, channel: int = 1, **kwargs) -> Parameter:
    return Parameter(name=name, cc=cc, channel=channel, **kwargs)


class ParameterTests(unittest.TestCase):
    def test_value_clamps_high(self):
        p = _mk(max_value=100)
        p.value = 200
        self.assertEqual(p.value, 100)

    def test_value_clamps_low(self):
        p = _mk(min_value=10)
        p.value = -5
        self.assertEqual(p.value, 10)

    def test_value_clamps_default_range(self):
        p = _mk()
        p.value = 999
        self.assertEqual(p.value, 127)
        p.value = -999
        self.assertEqual(p.value, 0)

    def test_no_op_does_not_fire_observers(self):
        p = _mk()
        p.value = 42
        calls: list[int] = []
        p.add_observer(lambda _param, v: calls.append(v))
        p.value = 42  # same value, no-op
        self.assertEqual(calls, [])

    def test_change_fires_all_observers(self):
        p = _mk()
        a_calls: list[tuple[Parameter, int]] = []
        b_calls: list[tuple[Parameter, int]] = []
        p.add_observer(lambda param, v: a_calls.append((param, v)))
        p.add_observer(lambda param, v: b_calls.append((param, v)))
        p.value = 50
        self.assertEqual(a_calls, [(p, 50)])
        self.assertEqual(b_calls, [(p, 50)])

    def test_observers_fire_in_registration_order(self):
        p = _mk()
        order: list[str] = []
        p.add_observer(lambda _p, _v: order.append("first"))
        p.add_observer(lambda _p, _v: order.append("second"))
        p.add_observer(lambda _p, _v: order.append("third"))
        p.value = 7
        self.assertEqual(order, ["first", "second", "third"])

    def test_remove_observer_during_iteration_is_safe(self):
        """If observer #2 removes observer #3, observer #3 should still
        fire on the same change (snapshot semantics)."""
        p = _mk()
        order: list[str] = []

        def obs1(_p, _v):
            order.append("1")

        def obs3(_p, _v):
            order.append("3")

        def obs2(_p, _v):
            order.append("2")
            p.remove_observer(obs3)

        p.add_observer(obs1)
        p.add_observer(obs2)
        p.add_observer(obs3)
        p.value = 10
        self.assertEqual(order, ["1", "2", "3"])

        # Subsequent change should not fire obs3 (it was removed).
        order.clear()
        p.value = 20
        self.assertEqual(order, ["1", "2"])

    def test_add_observer_idempotent(self):
        p = _mk()
        calls: list[int] = []

        def obs(_p, v):
            calls.append(v)

        p.add_observer(obs)
        p.add_observer(obs)  # second registration is a no-op
        p.value = 5
        self.assertEqual(calls, [5])

    def test_remove_unknown_observer_silent(self):
        p = _mk()
        # Should not raise.
        p.remove_observer(lambda _p, _v: None)

    def test_reset_sets_midpoint(self):
        p = _mk(min_value=0, max_value=127)
        p.value = 100
        p.reset()
        self.assertEqual(p.value, 63)  # (0 + 127) // 2

        q = _mk(min_value=10, max_value=20)
        q.reset()
        self.assertEqual(q.value, 15)


class StaticParameterProviderTests(unittest.TestCase):
    def test_size_and_get(self):
        params = [_mk(name=f"p{i}", cc=20 + i) for i in range(4)]
        prov = StaticParameterProvider(params)
        self.assertEqual(prov.size(), 4)
        self.assertIs(prov.get(0), params[0])
        self.assertIs(prov.get(3), params[3])

    def test_observer_add_remove(self):
        prov = StaticParameterProvider([_mk()])
        calls: list[int] = []

        def cb():
            calls.append(1)

        prov.add_parameters_observer(cb)
        prov.add_parameters_observer(cb)  # idempotent
        prov._notify()
        self.assertEqual(calls, [1])
        prov.remove_parameters_observer(cb)
        prov._notify()
        self.assertEqual(calls, [1])
        # Removing again is silent.
        prov.remove_parameters_observer(cb)


class SelectedFocusProviderTests(unittest.TestCase):
    def test_rejects_empty_instances(self):
        with self.assertRaises(ValueError):
            SelectedFocusProvider([])

    def test_rejects_mismatched_sizes(self):
        a = [_mk(name="a0"), _mk(name="a1")]
        b = [_mk(name="b0")]
        with self.assertRaises(ValueError):
            SelectedFocusProvider([a, b])

    def test_set_focus_same_idx_is_noop(self):
        a = [_mk(name="a0")]
        b = [_mk(name="b0")]
        prov = SelectedFocusProvider([a, b])
        calls: list[int] = []
        prov.add_parameters_observer(lambda: calls.append(1))
        prov.set_focus(0)  # already 0
        self.assertEqual(calls, [])

    def test_set_focus_change_fires_observers(self):
        a = [_mk(name="a0")]
        b = [_mk(name="b0")]
        prov = SelectedFocusProvider([a, b])
        calls: list[int] = []
        prov.add_parameters_observer(lambda: calls.append(1))
        prov.set_focus(1)
        self.assertEqual(calls, [1])
        self.assertEqual(prov.focus, 1)

    def test_get_returns_focused_instance(self):
        a = [_mk(name="a0"), _mk(name="a1")]
        b = [_mk(name="b0"), _mk(name="b1")]
        prov = SelectedFocusProvider([a, b])
        self.assertEqual(prov.get(0).name, "a0")
        prov.set_focus(1)
        self.assertEqual(prov.get(0).name, "b0")
        self.assertEqual(prov.get(1).name, "b1")

    def test_out_of_range_focus_raises(self):
        a = [_mk()]
        prov = SelectedFocusProvider([a])
        with self.assertRaises(IndexError):
            prov.set_focus(5)
        with self.assertRaises(IndexError):
            prov.set_focus(-1)

    def test_size_and_num_instances(self):
        a = [_mk(name=f"a{i}") for i in range(4)]
        b = [_mk(name=f"b{i}") for i in range(4)]
        c = [_mk(name=f"c{i}") for i in range(4)]
        prov = SelectedFocusProvider([a, b, c])
        self.assertEqual(prov.size(), 4)
        self.assertEqual(prov.num_instances(), 3)

    def test_remove_observer(self):
        a = [_mk()]
        b = [_mk()]
        prov = SelectedFocusProvider([a, b])
        calls: list[int] = []

        def cb():
            calls.append(1)

        prov.add_parameters_observer(cb)
        prov.remove_parameters_observer(cb)
        prov.set_focus(1)
        self.assertEqual(calls, [])
        # Removing again is silent.
        prov.remove_parameters_observer(cb)

    def test_integration_two_instances_focus_switch(self):
        """SelectedFocusProvider with 2 instances of 4 params each.
        Observe parameters_adjusted, set_focus(1), assert observer fired
        once and provider.get(0).name is from instance 1."""
        inst0 = [_mk(name=f"i0_p{i}", cc=20 + i) for i in range(4)]
        inst1 = [_mk(name=f"i1_p{i}", cc=30 + i) for i in range(4)]
        prov = SelectedFocusProvider([inst0, inst1])

        fire_count: list[int] = []
        prov.add_parameters_observer(lambda: fire_count.append(1))

        # Initial state: focus 0
        self.assertEqual(prov.get(0).name, "i0_p0")

        prov.set_focus(1)
        self.assertEqual(len(fire_count), 1)
        self.assertEqual(prov.get(0).name, "i1_p0")
        self.assertEqual(prov.get(3).name, "i1_p3")


if __name__ == "__main__":
    unittest.main()
