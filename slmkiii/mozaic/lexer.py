"""Mozaic lexer.

Tokenizes Mozaic Script source into a flat list of (kind, value, line, col)
tuples. Tokens:

    NUMBER, STRING, IDENT, HANDLER, KEYWORD, OP,
    LBRACK, RBRACK, LPAREN, RPAREN, COMMA, NEWLINE, EOF

Strings are written in curly braces: ``{Hello, world}`` (no escapes; the
braces themselves are not part of the value). Comments start with ``//`` and
run to end of line. Hex literals: ``0xFF``. Decimal/float: ``123``, ``12.5``.

Mozaic keywords are case-insensitive. ``YES``/``NO`` and ``TRUE``/``FALSE``
are emitted as NUMBER tokens (1/0) so the parser doesn't need to special-case
them.
"""

from __future__ import annotations

from dataclasses import dataclass

from slmkiii.mozaic.errors import MozaicError

# Reserved words. Stored lower-case; the lexer compares case-insensitively.
_KEYWORDS = frozenset(
    {
        "if",
        "elseif",
        "else",
        "endif",
        "for",
        "to",
        "endfor",
        "while",
        "endwhile",
        "repeat",
        "until",
        "and",
        "or",
        "not",
        "call",
        "exit",
        "unassigned",
    }
)
_BOOL_CONSTS = {"yes": 1, "no": 0, "true": 1, "false": 0}

# Two-character operators must be probed before the single-character ones.
_OP2 = ("==", "<=", ">=", "<>", "!=")
_OP1 = "=<>+-*/%&|^"


@dataclass(frozen=True)
class Token:
    kind: str
    value: object
    line: int
    col: int

    def __repr__(self) -> str:  # pragma: no cover - debugging aid only
        return f"Token({self.kind}, {self.value!r}, {self.line}:{self.col})"


def lex(source: str) -> list[Token]:
    """Tokenize ``source`` into a list of :class:`Token` ending with EOF."""
    tokens: list[Token] = []
    i = 0
    line = 1
    col = 1
    n = len(source)

    def err(msg: str) -> MozaicError:
        return MozaicError(msg, line, col)

    while i < n:
        c = source[i]

        # Whitespace (preserve newlines as tokens for statement separation)
        if c == "\n":
            tokens.append(Token("NEWLINE", "\n", line, col))
            i += 1
            line += 1
            col = 1
            continue
        if c in " \t\r":
            i += 1
            col += 1
            continue

        # Comments: // ... to EOL
        if c == "/" and i + 1 < n and source[i + 1] == "/":
            while i < n and source[i] != "\n":
                i += 1
                col += 1
            continue

        # Strings: {...}
        if c == "{":
            start_line, start_col = line, col
            j = i + 1
            buf = []
            while j < n and source[j] != "}":
                if source[j] == "\n":
                    line += 1
                    col = 1
                else:
                    col += 1
                buf.append(source[j])
                j += 1
            if j >= n:
                raise MozaicError("unterminated string literal", start_line, start_col)
            tokens.append(Token("STRING", "".join(buf), start_line, start_col))
            i = j + 1
            col += 1
            continue

        # Numbers: 0xFF, 123, 12.5
        if c.isdigit() or (c == "." and i + 1 < n and source[i + 1].isdigit()):
            start_col = col
            if c == "0" and i + 1 < n and source[i + 1] in "xX":
                j = i + 2
                while j < n and source[j] in "0123456789abcdefABCDEF":
                    j += 1
                tokens.append(Token("NUMBER", int(source[i:j], 16), line, start_col))
                col += j - i
                i = j
                continue
            j = i
            is_float = False
            while j < n and (source[j].isdigit() or source[j] == "."):
                if source[j] == ".":
                    if is_float:
                        break
                    is_float = True
                j += 1
            text = source[i:j]
            value: int | float = float(text) if is_float else int(text)
            tokens.append(Token("NUMBER", value, line, start_col))
            col += j - i
            i = j
            continue

        # Handler: @Identifier
        if c == "@":
            start_col = col
            j = i + 1
            while j < n and (source[j].isalnum() or source[j] == "_"):
                j += 1
            tokens.append(Token("HANDLER", source[i + 1 : j], line, start_col))
            col += j - i
            i = j
            continue

        # Identifier / keyword / boolean constant
        if c.isalpha() or c == "_":
            start_col = col
            j = i
            while j < n and (source[j].isalnum() or source[j] == "_"):
                j += 1
            word = source[i:j]
            lw = word.lower()
            if lw in _BOOL_CONSTS:
                tokens.append(Token("NUMBER", _BOOL_CONSTS[lw], line, start_col))
            elif lw in _KEYWORDS:
                tokens.append(Token("KEYWORD", lw, line, start_col))
            else:
                tokens.append(Token("IDENT", word, line, start_col))
            col += j - i
            i = j
            continue

        # Two-char operators
        if i + 1 < n and source[i : i + 2] in _OP2:
            op = source[i : i + 2]
            # Normalise: "==" -> "=", "!=" -> "<>"
            if op == "==":
                op = "="
            elif op == "!=":
                op = "<>"
            tokens.append(Token("OP", op, line, col))
            i += 2
            col += 2
            continue

        # Single-char operators / punctuation
        if c in _OP1:
            tokens.append(Token("OP", c, line, col))
            i += 1
            col += 1
            continue
        if c == "[":
            tokens.append(Token("LBRACK", c, line, col))
            i += 1
            col += 1
            continue
        if c == "]":
            tokens.append(Token("RBRACK", c, line, col))
            i += 1
            col += 1
            continue
        if c == "(":
            tokens.append(Token("LPAREN", c, line, col))
            i += 1
            col += 1
            continue
        if c == ")":
            tokens.append(Token("RPAREN", c, line, col))
            i += 1
            col += 1
            continue
        if c == ",":
            tokens.append(Token("COMMA", c, line, col))
            i += 1
            col += 1
            continue

        raise err(f"unexpected character {c!r}")

    tokens.append(Token("EOF", None, line, col))
    return tokens
