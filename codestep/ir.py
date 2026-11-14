"""A tiny language-neutral program representation.

Every non-Python lesson is written once in this IR and rendered into each
language by a renderer in ``codestep.languages``. That keeps the curriculum
identical across languages and lets the test suite compile/run every answer.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Union


# ---------------------------------------------------------------- expressions
@dataclass(frozen=True)
class Int:
    value: int


@dataclass(frozen=True)
class Str:
    value: str


@dataclass(frozen=True)
class Var:
    name: str


@dataclass(frozen=True)
class Bin:
    op: str  # + - * % > < >= <= ==
    left: "Expr"
    right: "Expr"


Expr = Union[Int, Str, Var, Bin]

COMPARISONS = {">", "<", ">=", "<=", "=="}


# ----------------------------------------------------------------- statements
@dataclass
class Print:
    args: list  # list[Expr]; several args are printed separated by one space


@dataclass
class Let:
    name: str
    value: Expr


@dataclass
class Set:
    name: str
    value: Expr


@dataclass
class Aug:
    name: str
    op: str  # + - *
    value: Expr


@dataclass
class If:
    branches: list  # list[tuple[Expr, list[Stmt]]]
    orelse: list = field(default_factory=list)


@dataclass
class For:
    var: str
    start: int
    stop: int  # exclusive, like Python's range()
    body: list
    step: int = 1


@dataclass
class While:
    cond: Expr
    body: list


@dataclass
class Def:
    name: str
    params: list  # list[tuple[str, str]]  -> (name, "int" | "str")
    body: list


@dataclass
class Call:
    name: str
    args: list


Stmt = Union[Print, Let, Set, Aug, If, For, While, Def, Call]


# ----------------------------------------------------------------- helpers
def S(v: str) -> Str:
    return Str(v)


def I(v: int) -> Int:
    return Int(v)


def V(n: str) -> Var:
    return Var(n)


def B(left, op, right) -> Bin:
    return Bin(op, _e(left), _e(right))


def _e(x):
    if isinstance(x, (Int, Str, Var, Bin)):
        return x
    if isinstance(x, bool):
        raise TypeError("booleans are not supported")
    if isinstance(x, int):
        return Int(x)
    if isinstance(x, str):
        return Var(x)
    raise TypeError(f"cannot convert {x!r} to an expression")


def P(*args) -> Print:
    """Print; bare str args are variable names, use S() for text."""
    return Print([_e(a) for a in args])


def L(name: str, value) -> Let:
    """Declare a variable; a bare str value is text (unlike P())."""
    return Let(name, Str(value) if isinstance(value, str) else _e(value))


# ----------------------------------------------------------------- analysis
def walk(stmts):
    for s in stmts:
        yield s
        if isinstance(s, If):
            for _, body in s.branches:
                yield from walk(body)
            yield from walk(s.orelse)
        elif isinstance(s, (For, While, Def)):
            yield from walk(s.body)


def walk_exprs(e):
    yield e
    if isinstance(e, Bin):
        yield from walk_exprs(e.left)
        yield from walk_exprs(e.right)


def stmt_exprs(s):
    if isinstance(s, Print):
        return list(s.args)
    if isinstance(s, (Let, Set, Aug)):
        return [s.value]
    if isinstance(s, If):
        return [c for c, _ in s.branches]
    if isinstance(s, While):
        return [s.cond]
    if isinstance(s, Call):
        return list(s.args)
    return []


def mutated_names(stmts) -> set:
    """Names that are assigned again after their first declaration."""
    return {s.name for s in walk(stmts) if isinstance(s, (Set, Aug))}


def uses_var(stmts, name: str) -> bool:
    for s in walk(stmts):
        for e in stmt_exprs(s):
            for sub in walk_exprs(e):
                if isinstance(sub, Var) and sub.name == name:
                    return True
        if isinstance(s, (Set, Aug)) and s.name == name:
            return True
    return False


def features(stmts) -> set:
    out = set()
    for s in walk(stmts):
        out.add(type(s).__name__)
        if isinstance(s, If) and (len(s.branches) > 1):
            out.add("Elif")
        if isinstance(s, If) and s.orelse:
            out.add("Else")
    return out
