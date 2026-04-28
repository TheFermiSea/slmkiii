"""Lexer tests for slmkiii.mozaic."""

from __future__ import annotations

import unittest
from pathlib import Path

from slmkiii.mozaic import lex
from slmkiii.mozaic.errors import MozaicError

QK_UTILS = Path("/Users/briansquires/code/quantumkomposer/qk_utils")


def _kinds(source: str) -> list[str]:
    return [t.kind for t in lex(source) if t.kind not in ("NEWLINE", "EOF")]


def _values(source: str) -> list[object]:
    return [t.value for t in lex(source) if t.kind not in ("NEWLINE", "EOF")]


class TestNumberLiterals(unittest.TestCase):
    def test_decimal_int(self) -> None:
        toks = lex("123")
        self.assertEqual(toks[0].kind, "NUMBER")
        self.assertEqual(toks[0].value, 123)

    def test_hex(self) -> None:
        toks = lex("0xFF 0x00 0x29")
        vals = [t.value for t in toks if t.kind == "NUMBER"]
        self.assertEqual(vals, [0xFF, 0x00, 0x29])

    def test_float(self) -> None:
        toks = lex("12.5")
        self.assertEqual(toks[0].value, 12.5)
        self.assertIsInstance(toks[0].value, float)


class TestStringAndComment(unittest.TestCase):
    def test_string(self) -> None:
        toks = lex("{Hello, world}")
        self.assertEqual(toks[0].kind, "STRING")
        self.assertEqual(toks[0].value, "Hello, world")

    def test_unterminated_string_raises(self) -> None:
        with self.assertRaises(MozaicError):
            lex("{not closed")

    def test_comment_to_eol(self) -> None:
        toks = lex("a = 1 // a comment\nb = 2")
        kinds = [t.kind for t in toks if t.kind not in ("NEWLINE", "EOF")]
        self.assertEqual(kinds, ["IDENT", "OP", "NUMBER", "IDENT", "OP", "NUMBER"])


class TestKeywordsAndConstants(unittest.TestCase):
    def test_yes_no_true_false_become_numbers(self) -> None:
        toks = [t for t in lex("YES NO TRUE FALSE") if t.kind != "EOF"]
        self.assertTrue(all(t.kind == "NUMBER" for t in toks))
        self.assertEqual([t.value for t in toks], [1, 0, 1, 0])

    def test_keywords_lowercased(self) -> None:
        toks = [t for t in lex("If ELSEIF Endif") if t.kind != "EOF"]
        self.assertEqual([t.kind for t in toks], ["KEYWORD", "KEYWORD", "KEYWORD"])
        self.assertEqual([t.value for t in toks], ["if", "elseif", "endif"])

    def test_handler_token(self) -> None:
        toks = lex("@OnLoad @OnMidiCC")
        h = [t for t in toks if t.kind == "HANDLER"]
        self.assertEqual([t.value for t in h], ["OnLoad", "OnMidiCC"])


class TestOperators(unittest.TestCase):
    def test_two_char_ops(self) -> None:
        toks = [t for t in lex("a == b <> c <= d >= e != f") if t.kind == "OP"]
        # == normalises to =, != normalises to <>
        self.assertEqual([t.value for t in toks], ["=", "<>", "<=", ">=", "<>"])

    def test_arithmetic(self) -> None:
        toks = [t for t in lex("a + b - c * d / e % f") if t.kind == "OP"]
        self.assertEqual([t.value for t in toks], ["+", "-", "*", "/", "%"])

    def test_bitwise(self) -> None:
        toks = [t for t in lex("a & b | c ^ d") if t.kind == "OP"]
        self.assertEqual([t.value for t in toks], ["&", "|", "^"])

    def test_brackets_parens_comma(self) -> None:
        toks = [t for t in lex("[](),") if t.kind != "EOF"]
        self.assertEqual([t.kind for t in toks], ["LBRACK", "RBRACK", "LPAREN", "RPAREN", "COMMA"])


class TestRepresentativeLines(unittest.TestCase):
    def test_assignment_with_array_literal(self) -> None:
        kinds = _kinds("kkntrl=[36,37,38,39]")
        self.assertEqual(
            kinds,
            ["IDENT", "OP", "LBRACK", "NUMBER", "COMMA", "NUMBER", "COMMA",
             "NUMBER", "COMMA", "NUMBER", "RBRACK"],
        )

    def test_indexed_assignment(self) -> None:
        kinds = _kinds("knob_pos[knob_idx]=new_pos")
        self.assertEqual(
            kinds,
            ["IDENT", "LBRACK", "IDENT", "RBRACK", "OP", "IDENT"],
        )

    def test_log_with_string_and_call(self) -> None:
        # `Log {NOTE: }, MIDIChannel+1, (NoteName MIDIByte2, YES)`
        src = "Log {NOTE: }, MIDIChannel+1, (NoteName MIDIByte2, YES)"
        kinds = _kinds(src)
        self.assertEqual(
            kinds,
            [
                "IDENT", "STRING", "COMMA",
                "IDENT", "OP", "NUMBER", "COMMA",
                "LPAREN", "IDENT", "IDENT", "COMMA", "NUMBER", "RPAREN",
            ],
        )


class TestRealScripts(unittest.TestCase):
    def test_qk2sl_lexes_clean(self) -> None:
        src = (QK_UTILS / "qk2sl.moz").read_text()
        toks = lex(src)
        # No exceptions; ends with EOF; has a healthy number of tokens.
        self.assertEqual(toks[-1].kind, "EOF")
        self.assertGreater(len(toks), 100)

    def test_all_qk_utils_lex(self) -> None:
        for name in (
            "qk2sl.moz",
            "sl2qk.moz",
            "midi_spy.moz",
            "lp2qk.moz",
            "qk2lp.moz",
            "qk2knobs.moz",
            "atom_sq.moz",
        ):
            with self.subTest(script=name):
                src = (QK_UTILS / name).read_text()
                toks = lex(src)
                self.assertEqual(toks[-1].kind, "EOF")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
