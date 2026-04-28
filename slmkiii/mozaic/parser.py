"""Recursive-descent parser for Mozaic Script.

The parser produces a :class:`~slmkiii.mozaic.ast.Module` (a dict from
handler name → list of statements). Top-level shape:

    @HandlerName
        ...statements...
    @End

Anything outside of an ``@Handler ... @End`` block is rejected. ``@End``
is treated as a terminator; an ``@End`` token is the only handler we don't
register as a real handler.

Operator precedence, low → high::

    or
    and
    not
    comparison ( = <> < > <= >= )
    bitwise or  ( | )
    bitwise xor ( ^ )
    bitwise and ( & )
    additive    ( + - )
    multiplicative ( * / % )
    unary -
    atom

Atoms are: number, string, variable, ``arr[expr]``, parenthesised
expression, parenthesised function call ``(FuncName arg, arg, ...)``,
``Unassigned <name>``, and the ``not`` unary operator.

The parser is liberal in what it accepts: unknown handler names are
preserved in the Module verbatim, and statements of the form
``IdentifierName arg, arg, ...`` are encoded as ``BuiltinCall``. The
interpreter is responsible for raising errors when a builtin is unknown.
"""

from __future__ import annotations

from slmkiii.mozaic import ast as A
from slmkiii.mozaic.errors import MozaicError
from slmkiii.mozaic.lexer import Token, lex

# Tokens that, when they follow ``(IDENT``, mean we're looking at a
# parenthesised expression rather than a function call. (Operators bind
# the leading IDENT into a binary expression; ``[`` continues the IDENT
# into an indexed access; ``,`` and ``)`` close the simple var.)
_AFTER_IDENT_IS_EXPR = {
    "OP",
    "LBRACK",
    "RBRACK",
    "RPAREN",
    "COMMA",
    "KEYWORD",  # 'and', 'or', 'not'
}


class _Parser:
    def __init__(self, tokens: list[Token]) -> None:
        self.toks = tokens
        self.pos = 0

    # ---- token helpers ----------------------------------------------------

    def peek(self, offset: int = 0) -> Token:
        return self.toks[self.pos + offset]

    def advance(self) -> Token:
        t = self.toks[self.pos]
        self.pos += 1
        return t

    def expect(self, kind: str, value: object = None) -> Token:
        t = self.peek()
        if t.kind != kind or (value is not None and t.value != value):
            raise MozaicError(
                f"expected {kind} {value!r}, got {t.kind} {t.value!r}",
                t.line,
                t.col,
            )
        return self.advance()

    def skip_newlines(self) -> None:
        while self.peek().kind == "NEWLINE":
            self.advance()

    def at_eof(self) -> bool:
        return self.peek().kind == "EOF"

    def end_of_stmt(self) -> None:
        # Statements terminate at NEWLINE, EOF, or before a HANDLER token.
        t = self.peek()
        if t.kind in ("NEWLINE", "EOF", "HANDLER"):
            if t.kind == "NEWLINE":
                self.advance()
            return
        raise MozaicError(
            f"expected end of statement, got {t.kind} {t.value!r}", t.line, t.col
        )

    # ---- top-level --------------------------------------------------------

    def parse_module(self) -> A.Module:
        mod = A.Module()
        self.skip_newlines()
        while not self.at_eof():
            t = self.peek()
            if t.kind != "HANDLER":
                raise MozaicError(
                    f"expected @Handler at top level, got {t.kind} {t.value!r}",
                    t.line,
                    t.col,
                )
            handler = self.advance()
            handler_name = handler.value
            self.skip_newlines()
            body: list[A.Stmt] = []
            while True:
                self.skip_newlines()
                if self.at_eof():
                    raise MozaicError(
                        f"@{handler_name}: missing @End", handler.line, handler.col
                    )
                t = self.peek()
                if t.kind == "HANDLER":
                    if t.value.lower() == "end":
                        self.advance()
                        self.skip_newlines()
                        break
                    # Next handler — implicit close (some scripts omit @End)
                    break
                stmt = self.parse_stmt()
                if stmt is not None:
                    body.append(stmt)
            if handler_name.lower() != "end":
                mod.handlers[handler_name] = body
        return mod

    # ---- statements -------------------------------------------------------

    def parse_stmt(self) -> A.Stmt | None:
        self.skip_newlines()
        t = self.peek()
        if t.kind == "KEYWORD":
            kw = t.value
            if kw == "if":
                return self.parse_if()
            if kw == "for":
                return self.parse_for()
            if kw == "while":
                return self.parse_while()
            if kw == "repeat":
                return self.parse_repeat()
            if kw == "call":
                return self.parse_call()
            if kw == "exit":
                self.advance()
                self.end_of_stmt()
                return A.Exit()
            raise MozaicError(
                f"unexpected keyword {kw!r}", t.line, t.col
            )
        if t.kind == "IDENT":
            return self.parse_ident_stmt()
        if t.kind == "NEWLINE":
            self.advance()
            return None
        raise MozaicError(
            f"unexpected token {t.kind} {t.value!r}", t.line, t.col
        )

    def parse_ident_stmt(self) -> A.Stmt:
        name_tok = self.expect("IDENT")
        name = name_tok.value

        # Indexed assignment: name[idx] = ...
        if self.peek().kind == "LBRACK":
            self.advance()
            idx_expr = self.parse_expr()
            self.expect("RBRACK")
            self.expect("OP", "=")
            value = self.parse_assign_rhs()
            self.end_of_stmt()
            return A.Assign(name, idx_expr, value)

        # Scalar assignment: name = ...
        if self.peek().kind == "OP" and self.peek().value == "=":
            self.advance()
            value = self.parse_assign_rhs()
            self.end_of_stmt()
            return A.Assign(name, None, value)

        # Otherwise builtin call: Name arg1, arg2, ...
        args: list[A.Expr] = []
        if self.peek().kind not in ("NEWLINE", "EOF", "HANDLER"):
            args.append(self.parse_expr())
            while self.peek().kind == "COMMA":
                self.advance()
                args.append(self.parse_expr())
        self.end_of_stmt()
        return A.BuiltinCall(name, args)

    def parse_assign_rhs(self) -> A.Expr:
        """Right-hand side of an assignment.

        Accepts a normal expression, or an array literal ``[1, 2, 3]`` which
        we encode as a synthetic ``FuncCall("__array__", [...])`` so the
        evaluator can blast it into the array starting at the index given
        on the LHS (or 0 for a scalar LHS).

        Also accepts a bare function-call form ``= Clip x, 0, 127``: if the
        parsed expression is a single ``Var`` and the next token starts a
        new argument (``,`` or expression start), we re-interpret the Var
        as a function name and read the remaining comma-separated args.
        """
        if self.peek().kind == "LBRACK":
            self.advance()
            elems: list[A.Expr] = []
            if self.peek().kind != "RBRACK":
                elems.append(self.parse_expr())
                while self.peek().kind == "COMMA":
                    self.advance()
                    elems.append(self.parse_expr())
            self.expect("RBRACK")
            return A.FuncCall("__array__", elems)
        expr = self.parse_expr()
        # Bare-call RHS: ``brightness = Clip (x+8), 0, 127``. The parser
        # consumed ``Clip`` as a Var; the following tokens start new args
        # without an enclosing paren. If we see another expression-starter
        # immediately, repackage as a function call.
        if isinstance(expr, A.Var):
            t = self.peek()
            if t.kind in ("LPAREN", "NUMBER", "STRING", "IDENT") or (
                t.kind == "OP" and t.value == "-"
            ):
                args: list[A.Expr] = [self.parse_expr()]
                while self.peek().kind == "COMMA":
                    self.advance()
                    args.append(self.parse_expr())
                return A.FuncCall(expr.name, args)
        return expr

    def parse_if(self) -> A.If:
        self.expect("KEYWORD", "if")
        cond = self.parse_expr()
        self.skip_newlines()
        body = self.parse_block(stop_keywords=("elseif", "else", "endif"))
        branches: list[tuple[A.Expr, list[A.Stmt]]] = [(cond, body)]
        else_body: list[A.Stmt] = []
        while True:
            t = self.peek()
            if t.kind == "KEYWORD" and t.value == "elseif":
                self.advance()
                c = self.parse_expr()
                self.skip_newlines()
                b = self.parse_block(stop_keywords=("elseif", "else", "endif"))
                branches.append((c, b))
                continue
            if t.kind == "KEYWORD" and t.value == "else":
                self.advance()
                self.skip_newlines()
                else_body = self.parse_block(stop_keywords=("endif",))
                continue
            if t.kind == "KEYWORD" and t.value == "endif":
                self.advance()
                # Allow trailing newline; do not require it (some scripts
                # have ``endif`` followed by another stmt on the next line)
                if self.peek().kind == "NEWLINE":
                    self.advance()
                return A.If(branches, else_body)
            raise MozaicError(
                f"unexpected token in if-block: {t.kind} {t.value!r}", t.line, t.col
            )

    def parse_for(self) -> A.For:
        self.expect("KEYWORD", "for")
        var_tok = self.expect("IDENT")
        self.expect("OP", "=")
        lo = self.parse_expr()
        self.expect("KEYWORD", "to")
        hi = self.parse_expr()
        self.skip_newlines()
        body = self.parse_block(stop_keywords=("endfor",))
        self.expect("KEYWORD", "endfor")
        if self.peek().kind == "NEWLINE":
            self.advance()
        return A.For(var_tok.value, lo, hi, body)

    def parse_while(self) -> A.While:
        self.expect("KEYWORD", "while")
        cond = self.parse_expr()
        self.skip_newlines()
        body = self.parse_block(stop_keywords=("endwhile",))
        self.expect("KEYWORD", "endwhile")
        if self.peek().kind == "NEWLINE":
            self.advance()
        return A.While(cond, body)

    def parse_repeat(self) -> A.Repeat:
        self.expect("KEYWORD", "repeat")
        self.skip_newlines()
        body = self.parse_block(stop_keywords=("until",))
        self.expect("KEYWORD", "until")
        cond = self.parse_expr()
        if self.peek().kind == "NEWLINE":
            self.advance()
        return A.Repeat(body, cond)

    def parse_call(self) -> A.Call:
        self.expect("KEYWORD", "call")
        t = self.peek()
        if t.kind != "HANDLER":
            raise MozaicError(
                f"Call expects @HandlerName, got {t.kind} {t.value!r}",
                t.line,
                t.col,
            )
        self.advance()
        self.end_of_stmt()
        return A.Call(t.value)

    def parse_block(self, stop_keywords: tuple[str, ...]) -> list[A.Stmt]:
        body: list[A.Stmt] = []
        while True:
            self.skip_newlines()
            t = self.peek()
            if t.kind == "KEYWORD" and t.value in stop_keywords:
                return body
            if t.kind == "HANDLER":
                # Defensive: bail out on @End / next @Handler
                return body
            if t.kind == "EOF":
                raise MozaicError(
                    f"unexpected EOF; expected one of {stop_keywords}", t.line, t.col
                )
            stmt = self.parse_stmt()
            if stmt is not None:
                body.append(stmt)

    # ---- expressions ------------------------------------------------------

    def parse_expr(self) -> A.Expr:
        return self.parse_or()

    def parse_or(self) -> A.Expr:
        left = self.parse_and()
        while self.peek().kind == "KEYWORD" and self.peek().value == "or":
            self.advance()
            right = self.parse_and()
            left = A.BinOp("or", left, right)
        return left

    def parse_and(self) -> A.Expr:
        left = self.parse_not()
        while self.peek().kind == "KEYWORD" and self.peek().value == "and":
            self.advance()
            right = self.parse_not()
            left = A.BinOp("and", left, right)
        return left

    def parse_not(self) -> A.Expr:
        if self.peek().kind == "KEYWORD" and self.peek().value == "not":
            self.advance()
            return A.UnaryOp("not", self.parse_not())
        return self.parse_cmp()

    def parse_cmp(self) -> A.Expr:
        left = self.parse_bitor()
        while True:
            t = self.peek()
            if t.kind == "OP" and t.value in ("=", "<>", "<", ">", "<=", ">="):
                self.advance()
                right = self.parse_bitor()
                left = A.BinOp(t.value, left, right)
            else:
                return left

    def parse_bitor(self) -> A.Expr:
        left = self.parse_bitxor()
        while self.peek().kind == "OP" and self.peek().value == "|":
            self.advance()
            right = self.parse_bitxor()
            left = A.BinOp("|", left, right)
        return left

    def parse_bitxor(self) -> A.Expr:
        left = self.parse_bitand()
        while self.peek().kind == "OP" and self.peek().value == "^":
            self.advance()
            right = self.parse_bitand()
            left = A.BinOp("^", left, right)
        return left

    def parse_bitand(self) -> A.Expr:
        left = self.parse_add()
        while self.peek().kind == "OP" and self.peek().value == "&":
            self.advance()
            right = self.parse_add()
            left = A.BinOp("&", left, right)
        return left

    def parse_add(self) -> A.Expr:
        left = self.parse_mul()
        while self.peek().kind == "OP" and self.peek().value in ("+", "-"):
            op = self.advance().value
            right = self.parse_mul()
            left = A.BinOp(op, left, right)
        return left

    def parse_mul(self) -> A.Expr:
        left = self.parse_unary()
        while self.peek().kind == "OP" and self.peek().value in ("*", "/", "%"):
            op = self.advance().value
            right = self.parse_unary()
            left = A.BinOp(op, left, right)
        return left

    def parse_unary(self) -> A.Expr:
        t = self.peek()
        if t.kind == "OP" and t.value == "-":
            self.advance()
            return A.UnaryOp("-", self.parse_unary())
        if t.kind == "OP" and t.value == "+":
            self.advance()
            return self.parse_unary()
        return self.parse_atom()

    def parse_atom(self) -> A.Expr:
        t = self.peek()
        if t.kind == "NUMBER":
            self.advance()
            return A.Number(t.value)
        if t.kind == "STRING":
            self.advance()
            return A.String(t.value)
        if t.kind == "KEYWORD" and t.value == "unassigned":
            self.advance()
            name_tok = self.peek()
            if name_tok.kind != "IDENT":
                raise MozaicError(
                    f"Unassigned expects an identifier, got {name_tok.kind}",
                    name_tok.line,
                    name_tok.col,
                )
            self.advance()
            return A.Unassigned(name_tok.value)
        if t.kind == "LPAREN":
            return self.parse_paren()
        if t.kind == "IDENT":
            self.advance()
            if self.peek().kind == "LBRACK":
                self.advance()
                idx = self.parse_expr()
                self.expect("RBRACK")
                return A.Index(t.value, idx)
            return A.Var(t.value)
        raise MozaicError(
            f"unexpected token in expression: {t.kind} {t.value!r}", t.line, t.col
        )

    def parse_paren(self) -> A.Expr:
        self.expect("LPAREN")
        # Disambiguate function-call form ``(Name arg, arg, ...)`` from a
        # plain parenthesised expression.
        first = self.peek()
        second = self.peek(1) if self.pos + 1 < len(self.toks) else None
        is_func = (
            first.kind == "IDENT"
            and second is not None
            and second.kind not in _AFTER_IDENT_IS_EXPR
        )
        if is_func:
            name = self.advance().value
            args: list[A.Expr] = []
            if self.peek().kind != "RPAREN":
                args.append(self.parse_expr())
                while self.peek().kind == "COMMA":
                    self.advance()
                    args.append(self.parse_expr())
            self.expect("RPAREN")
            return A.FuncCall(name, args)
        e = self.parse_expr()
        self.expect("RPAREN")
        return e


def parse(source: str) -> A.Module:
    """Parse Mozaic source into a :class:`Module`."""
    toks = lex(source)
    return _Parser(toks).parse_module()
