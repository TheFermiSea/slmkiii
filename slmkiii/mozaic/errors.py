"""Mozaic interpreter exceptions."""

from __future__ import annotations


class MozaicError(Exception):
    """Raised on lex / parse / eval errors in a Mozaic script."""

    def __init__(self, msg: str, line: int | None = None, col: int | None = None) -> None:
        if line is not None and col is not None:
            super().__init__(f"{line}:{col}: {msg}")
        else:
            super().__init__(msg)
        self.line = line
        self.col = col
        self.msg = msg
