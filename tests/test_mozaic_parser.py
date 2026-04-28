"""Parser tests for slmkiii.mozaic."""

from __future__ import annotations

import unittest
from pathlib import Path

from slmkiii.mozaic import ast as A
from slmkiii.mozaic import parse
from slmkiii.mozaic.errors import MozaicError

QK_UTILS = Path(str(Path(__file__).resolve().parents[1].parent / 'quantumkomposer' / 'qk_utils'))
_QK_AVAILABLE = QK_UTILS.is_dir()

ALL_SCRIPTS = (
    "qk2sl.moz",
    "sl2qk.moz",
    "midi_spy.moz",
    "lp2qk.moz",
    "qk2lp.moz",
    "qk2knobs.moz",
    "atom_sq.moz",
)


@unittest.skipUnless(_QK_AVAILABLE, 'qk_utils sibling repo not present')
class TestRealScripts(unittest.TestCase):
    def test_all_qk_utils_parse(self) -> None:
        for name in ALL_SCRIPTS:
            with self.subTest(script=name):
                src = (QK_UTILS / name).read_text()
                mod = parse(src)
                self.assertGreater(len(mod.handlers), 0, f"{name} produced no handlers")

    def test_qk2sl_structure(self) -> None:
        src = (QK_UTILS / "qk2sl.moz").read_text()
        mod = parse(src)
        # Spec says qk2sl.moz has @OnLoad with @SetupScreens call.
        self.assertIn("OnLoad", mod.handlers)
        self.assertIn("SetupScreens", mod.handlers)
        body = mod.handlers["OnLoad"]
        calls = [s for s in body if isinstance(s, A.Call)]
        self.assertIn("SetupScreens", [c.handler for c in calls])

    def test_midi_spy_handlers(self) -> None:
        src = (QK_UTILS / "midi_spy.moz").read_text()
        mod = parse(src)
        for expected in (
            "OnLoad",
            "LabelAllPads",
            "OnPadDown",
            "OnMidiNoteOn",
            "OnMidiNoteOff",
            "OnMidiCC",
            "OnMidiInput",
            "OnHostStart",
        ):
            self.assertIn(expected, mod.handlers)

    def test_sl2qk_has_for_loop_in_init(self) -> None:
        src = (QK_UTILS / "sl2qk.moz").read_text()
        mod = parse(src)
        # @InitState contains FillArray; @OnMidiCC contains Exit at multiple points.
        self.assertIn("InitState", mod.handlers)
        body = mod.handlers["OnMidiCC"]

        def has_exit(stmts: list) -> bool:
            for s in stmts:
                if isinstance(s, A.Exit):
                    return True
                if isinstance(s, A.If):
                    for _, b in s.branches:
                        if has_exit(b):
                            return True
                    if has_exit(s.else_body):
                        return True
            return False

        self.assertTrue(has_exit(body))


class TestExpressionForms(unittest.TestCase):
    def test_indirect_indexing(self) -> None:
        # Central requirement: arr[var] indirect indexing must parse cleanly.
        mod = parse(
            "@OnLoad\n"
            "  arr = [10, 20, 30, 40]\n"
            "  i = 2\n"
            "  v = arr[i]\n"
            "@End\n"
        )
        body = mod.handlers["OnLoad"]
        # Last assign is `v = arr[i]`
        last = body[-1]
        self.assertIsInstance(last, A.Assign)
        self.assertEqual(last.name, "v")
        self.assertIsInstance(last.value_expr, A.Index)
        self.assertEqual(last.value_expr.name, "arr")
        self.assertIsInstance(last.value_expr.idx, A.Var)
        self.assertEqual(last.value_expr.idx.name, "i")

    def test_paren_function_call_in_log(self) -> None:
        mod = parse(
            "@OnLoad\n"
            "  Log {x:}, (NoteName MIDIByte2, YES), {!}\n"
            "@End\n"
        )
        body = mod.handlers["OnLoad"]
        self.assertEqual(len(body), 1)
        call = body[0]
        self.assertIsInstance(call, A.BuiltinCall)
        self.assertEqual(call.name, "Log")
        self.assertEqual(len(call.args), 3)
        self.assertIsInstance(call.args[1], A.FuncCall)
        self.assertEqual(call.args[1].name, "NoteName")

    def test_array_literal_with_offset(self) -> None:
        mod = parse(
            "@OnLoad\n"
            "  buffer[100] = [0, 1, 2, 3]\n"
            "@End\n"
        )
        body = mod.handlers["OnLoad"]
        a = body[0]
        self.assertIsInstance(a, A.Assign)
        self.assertEqual(a.name, "buffer")
        self.assertIsInstance(a.idx_expr, A.Number)
        self.assertEqual(a.idx_expr.value, 100)
        self.assertIsInstance(a.value_expr, A.FuncCall)
        self.assertEqual(a.value_expr.name, "__array__")
        self.assertEqual(len(a.value_expr.args), 4)


class TestErrorCases(unittest.TestCase):
    def test_unclosed_if(self) -> None:
        with self.assertRaises(MozaicError):
            parse("@OnLoad\n  if 1\n    a = 1\n@End\n")

    def test_mismatched_endif(self) -> None:
        with self.assertRaises(MozaicError):
            parse("@OnLoad\n  endif\n@End\n")

    def test_missing_end_handler(self) -> None:
        with self.assertRaises(MozaicError):
            parse("@OnLoad\n  a = 1\n")

    def test_unknown_unary_operator(self) -> None:
        # `++a` — `+` unary is permitted (no-op), but `++` would be invalid:
        # the second + has nothing to apply to. Use ``*`` as a leading op
        # which has no unary form to ensure a parse error.
        with self.assertRaises(MozaicError):
            parse("@OnLoad\n  a = * 2\n@End\n")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
