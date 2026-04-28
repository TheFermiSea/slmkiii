"""Mozaic mini-interpreter.

Tree-walking lexer/parser/evaluator for Mozaic Script (the language used
by the iOS Mozaic AUv3 plugin). Used to test generated Mozaic scripts
byte-for-byte without an iPad.
"""

from slmkiii.mozaic.errors import MozaicError
from slmkiii.mozaic.lexer import lex
from slmkiii.mozaic.parser import parse


def __getattr__(name: str) -> object:
    # Lazy: avoids importing the evaluator when only the parser is needed.
    if name == "MozaicInterp":
        from slmkiii.mozaic.interp import MozaicInterp

        return MozaicInterp
    raise AttributeError(name)


__all__ = ["MozaicInterp", "MozaicError", "parse", "lex"]
