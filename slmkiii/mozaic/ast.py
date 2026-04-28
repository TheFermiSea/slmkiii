"""AST node definitions for the Mozaic interpreter."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Union

# ---- Expression nodes -----------------------------------------------------


@dataclass(frozen=True)
class Number:
    value: Union[int, float]


@dataclass(frozen=True)
class String:
    value: str


@dataclass(frozen=True)
class Var:
    name: str


@dataclass(frozen=True)
class Index:
    name: str
    idx: "Expr"


@dataclass(frozen=True)
class BinOp:
    op: str
    left: "Expr"
    right: "Expr"


@dataclass(frozen=True)
class UnaryOp:
    op: str
    operand: "Expr"


@dataclass(frozen=True)
class Unassigned:
    name: str


@dataclass(frozen=True)
class FuncCall:
    """Parenthesised builtin call used as an expression: ``(NoteName x, YES)``."""

    name: str
    args: list["Expr"]


Expr = Union[Number, String, Var, Index, BinOp, UnaryOp, Unassigned, FuncCall]


# ---- Statement nodes ------------------------------------------------------


@dataclass
class Assign:
    name: str
    idx_expr: Optional[Expr]
    value_expr: Expr


@dataclass
class If:
    branches: list[tuple[Expr, list["Stmt"]]]
    else_body: list["Stmt"]


@dataclass
class For:
    var: str
    lo: Expr
    hi: Expr
    body: list["Stmt"]


@dataclass
class While:
    cond: Expr
    body: list["Stmt"]


@dataclass
class Repeat:
    body: list["Stmt"]
    cond: Expr


@dataclass
class Call:
    handler: str


@dataclass
class Exit:
    pass


@dataclass
class BuiltinCall:
    name: str
    args: list[Expr]


Stmt = Union[Assign, If, For, While, Repeat, Call, Exit, BuiltinCall]


# ---- Module ---------------------------------------------------------------


@dataclass
class Module:
    handlers: dict[str, list[Stmt]] = field(default_factory=dict)
