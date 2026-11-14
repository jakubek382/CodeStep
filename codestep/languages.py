"""Renderers that turn the IR in ``codestep.ir`` into real source code.

Each language class knows its syntax, naming style, how to wrap a program,
and which keywords the checker should look for. Adding a language means
adding one class here and registering it in ``LANGUAGES``.
"""
from __future__ import annotations

from .ir import (
    Aug, Bin, COMPARISONS, Call, Def, For, If, Int, Let, Print, Set, Str, Var,
    While, mutated_names, uses_var,
)


def _snake_to_camel(name: str) -> str:
    head, *rest = name.split("_")
    return head + "".join(p.capitalize() for p in rest)


def _snake_to_pascal(name: str) -> str:
    return "".join(p.capitalize() for p in name.split("_"))


def _int_value(e):
    return e.value if isinstance(e, Int) else None


class Language:
    id = ""
    name = ""
    ext = ""
    indent = "    "
    end = ";"
    cond_parens = True
    fn_style = "snake"          # snake | camel | pascal
    eq = "=="
    line_comments = ("//",)
    block_comments = (("/*", "*/"),)
    quotes = ('"', "'")
    quotes_equivalent = False   # ' and " mean the same thing (normaliser)
    optional_semicolons = False
    increment = True            # supports x++ / x--
    placeholder = "// Write your code here"
    # keywords the checker requires when a task uses that construct
    kw_for = "for"
    kw_while = "while"
    kw_if = "if"
    kw_elif = "else if"
    kw_else = "else"
    kw_def = None               # e.g. "def", "function"; None = no keyword
    runners = ()                # see codestep.runner
    install_hint = ""

    # ------------------------------------------------------------ naming
    def fn(self, name: str) -> str:
        if self.fn_style == "camel":
            return _snake_to_camel(name)
        if self.fn_style == "pascal":
            return _snake_to_pascal(name)
        return name

    def var(self, name: str) -> str:
        return name

    # ------------------------------------------------------------ exprs
    def string(self, text: str) -> str:
        return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'

    def op(self, op: str) -> str:
        return self.eq if op == "==" else op

    def expr(self, e) -> str:
        if isinstance(e, Int):
            return str(e.value)
        if isinstance(e, Str):
            return self.string(e.value)
        if isinstance(e, Var):
            return self.var(e.name)
        if isinstance(e, Bin):
            return f"{self.expr(e.left)} {self.op(e.op)} {self.expr(e.right)}"
        raise TypeError(e)

    def wrapped(self, e) -> str:
        return f"({self.expr(e)})" if isinstance(e, Bin) else self.expr(e)

    def cond(self, e) -> str:
        c = self.expr(e)
        return f"({c})" if self.cond_parens else c

    @staticmethod
    def etype(e, env) -> str:
        if isinstance(e, Int):
            return "int"
        if isinstance(e, Str):
            return "str"
        if isinstance(e, Var):
            return env.get(e.name, "int")
        if isinstance(e, Bin):
            if e.op in COMPARISONS:
                return "bool"
            lt, rt = Language.etype(e.left, env), Language.etype(e.right, env)
            return "str" if "str" in (lt, rt) else "int"
        raise TypeError(e)

    @staticmethod
    def pieces(args, env):
        """Split print args into ("lit", text) / ("expr", e, type) pieces,
        inserting the single-space separator and merging adjacent text."""
        out = []
        for i, a in enumerate(args):
            if i:
                out.append(("lit", " "))
            if isinstance(a, Str):
                out.append(("lit", a.value))
            else:
                out.append(("expr", a, Language.etype(a, env)))
        merged = []
        for p in out:
            if p[0] == "lit" and merged and merged[-1][0] == "lit":
                merged[-1] = ("lit", merged[-1][1] + p[1])
            else:
                merged.append(p)
        return merged

    @staticmethod
    def inclusive_stop(stop):
        """range(a, b) -> b - 1, simplified when b is literal or `n + 1`."""
        if isinstance(stop, Int):
            return Int(stop.value - 1)
        if isinstance(stop, Bin) and stop.op == "+" and _int_value(stop.right) == 1:
            return stop.left
        return Bin("-", stop, Int(1))

    # ------------------------------------------------------------ statements
    def print_(self, args, env) -> str:
        raise NotImplementedError

    def type_name(self, t: str) -> str:
        return t

    def let(self, name, typ, value, mutable) -> str:
        return f"{self.var(name)} = {value}{self.end}"

    def assign(self, name, value) -> str:
        return f"{self.var(name)} = {value}{self.end}"

    def aug(self, name, op, value_e) -> str:
        v = self.var(name)
        if self.increment and op in "+-" and _int_value(value_e) == 1:
            return f"{v}{op}{op}{self.end}"
        return f"{v} {op}= {self.expr(value_e)}{self.end}"

    def call(self, name, args) -> str:
        return f"{self.fn(name)}({', '.join(self.expr(a) for a in args)}){self.end}"

    def block(self, lines):
        return [self.indent + ln if ln else ln for ln in lines]

    # C-family control flow (overridden where different)
    def if_(self, branches, orelse, env, mut):
        lines = []
        for i, (c, body) in enumerate(branches):
            head = "if" if i == 0 else "} else if"
            lines.append(f"{head} {self.cond(c)} {{")
            lines += self.block(self.body(body, env, mut))
        if orelse:
            lines.append("} else {")
            lines += self.block(self.body(orelse, env, mut))
        lines.append("}")
        return lines

    def for_head(self, var, start, stop, step, used) -> str:
        v = self.var(var)
        cmp = "<" if step > 0 else ">"
        if step == 1:
            inc = f"{v}++"
        elif step == -1:
            inc = f"{v}--"
        else:
            inc = f"{v} {'+' if step > 0 else '-'}= {abs(step)}"
        if step > 0 and isinstance(stop, Bin) and stop.op == "+" and _int_value(stop.right) == 1:
            cmp, stop = "<=", stop.left          # range(1, n + 1) -> i <= n
        decl = self.for_decl(var)
        return f"for ({decl}{v} = {self.expr(start)}; {v} {cmp} {self.expr(stop)}; {inc}) {{"

    def for_decl(self, var) -> str:
        return "int "

    def for_(self, s: For, env, mut):
        used = uses_var(s.body, s.var)
        head = self.for_head(s.var, _ex(s.start), _ex(s.stop), s.step, used)
        return [head] + self.block(self.body(s.body, env, mut)) + [self.close_block()]

    def while_(self, s: While, env, mut):
        return [f"while {self.cond(s.cond)} {{"] + self.block(self.body(s.body, env, mut)) + [self.close_block()]

    def close_block(self) -> str:
        return "}"

    def param(self, name, typ) -> str:
        return self.var(name)

    def def_head(self, name, params) -> str:
        raise NotImplementedError

    def render_def(self, d: Def):
        env = {n: t for n, t in d.params}
        mut = mutated_names(d.body)
        head = self.def_head(self.fn(d.name), [self.param(n, t) for n, t in d.params])
        return [head] + self.block(self.body(d.body, env, mut)) + [self.close_block()]

    def body(self, stmts, env, mut):
        lines = []
        for s in stmts:
            if isinstance(s, Print):
                lines.append(self.print_(s.args, env))
            elif isinstance(s, Let):
                typ = self.etype(s.value, env)
                env[s.name] = typ
                lines.append(self.let(s.name, typ, self.expr(s.value), s.name in mut))
            elif isinstance(s, Set):
                lines.append(self.assign(s.name, self.expr(s.value)))
            elif isinstance(s, Aug):
                lines.append(self.aug(s.name, s.op, s.value))
            elif isinstance(s, If):
                lines += self.if_(s.branches, s.orelse, env, mut)
            elif isinstance(s, For):
                env[s.var] = "int"
                lines += self.for_(s, env, mut)
            elif isinstance(s, While):
                lines += self.while_(s, env, mut)
            elif isinstance(s, Call):
                lines.append(self.call(s.name, s.args))
            else:
                raise TypeError(s)
        return lines

    # ------------------------------------------------------------ program
    def program(self, defs, main) -> str:
        """defs: list of line-lists, main: list of lines."""
        raise NotImplementedError

    def render(self, stmts) -> str:
        defs = [self.render_def(s) for s in stmts if isinstance(s, Def)]
        main = [s for s in stmts if not isinstance(s, Def)]
        return self.program(defs, self.body(main, {}, mutated_names(main))).rstrip() + "\n"

    def starter(self) -> str:
        """What the editor shows before the learner types anything."""
        return self.program([], [self.placeholder]).rstrip() + "\n"

    # ------------------------------------------------------------ checker
    def keywords_for(self, feats: set) -> list:
        kws = []
        if "For" in feats:
            kws.append(self.kw_for)
        if "While" in feats:
            kws.append(self.kw_while)
        if "If" in feats:
            kws.append(self.kw_if)
        if "Elif" in feats:
            kws.append(self.kw_elif)
        if "Else" in feats:
            kws.append(self.kw_else)
        if "Def" in feats and self.kw_def:
            kws.append(self.kw_def)
        return [k for k in kws if k]


def _ex(x):
    return Int(x) if isinstance(x, int) else x


def _flat(defs, sep_blank=True):
    out = []
    for d in defs:
        out += d
        if sep_blank:
            out.append("")
    return out


# ====================================================================== JS/TS
class JavaScript(Language):
    id, name, ext = "javascript", "JavaScript", ".js"
    fn_style = "camel"
    eq = "==="
    quotes = ('"', "'", "`")
    quotes_equivalent = True
    optional_semicolons = True
    kw_def = "function"
    runners = ("node", "bun", "deno")
    install_hint = "Node.js (nodejs.org)"

    def print_(self, args, env):
        return f"console.log({', '.join(self.expr(a) for a in args)});"

    def let(self, name, typ, value, mutable):
        return f"{'let' if mutable else 'const'} {name} = {value};"

    def for_decl(self, var):
        return "let "

    def def_head(self, name, params):
        return f"function {name}({', '.join(params)}) {{"

    def program(self, defs, main):
        return "\n".join(_flat(defs) + main)


class TypeScript(JavaScript):
    id, name, ext = "typescript", "TypeScript", ".ts"
    runners = ("bun", "deno", "tsx")
    install_hint = "Bun (bun.sh) or Deno (deno.com)"

    def param(self, name, typ):
        return f"{name}: {'number' if typ == 'int' else 'string'}"


# ======================================================================= Java
class Java(Language):
    id, name, ext = "java", "Java", ".java"
    fn_style = "camel"
    kw_def = "static void"
    runners = ("java",)
    install_hint = "a JDK 11+ (adoptium.net)"

    def type_name(self, t):
        return {"int": "int", "str": "String"}[t]

    def concat(self, args, env):
        ps = self.pieces(args, env)
        if len(ps) == 1 and ps[0][0] == "expr":
            return self.expr(ps[0][1])
        return " + ".join(self.string(p[1]) if p[0] == "lit" else self.wrapped(p[1]) for p in ps)

    def print_(self, args, env):
        return f"System.out.println({self.concat(args, env)});"

    def let(self, name, typ, value, mutable):
        return f"{self.type_name(typ)} {name} = {value};"

    def param(self, name, typ):
        return f"{self.type_name(typ)} {name}"

    def def_head(self, name, params):
        return f"static void {name}({', '.join(params)}) {{"

    def program(self, defs, main):
        inner = _flat(defs)
        inner += ["public static void main(String[] args) {"] + self.block(main) + ["}"]
        return "\n".join(["public class Main {"] + self.block(inner) + ["}"])


# ======================================================================== C#
class CSharp(Java):
    id, name, ext = "csharp", "C#", ".cs"
    fn_style = "pascal"
    kw_def = "void"
    runners = ("dotnet",)
    install_hint = "the .NET SDK 6+ (dot.net)"
    placeholder = "// Write your code here (top-level statements)"

    def type_name(self, t):
        return {"int": "int", "str": "string"}[t]

    def print_(self, args, env):
        return f"Console.WriteLine({self.concat(args, env)});"

    def def_head(self, name, params):
        return f"void {name}({', '.join(params)}) {{"

    def program(self, defs, main):
        # top-level statements; local functions follow the code that calls them
        return "\n".join(main + ([""] if defs else []) + _flat(defs))


# ========================================================================= C
class C(Language):
    id, name, ext = "c", "C", ".c"
    kw_def = "void"
    runners = ("gcc", "clang", "cc")
    install_hint = "GCC or Clang (MinGW-w64 / MSYS2 on Windows)"

    def type_name(self, t):
        return {"int": "int", "str": "const char *"}[t]

    def print_(self, args, env):
        fmt, vals = "", []
        for p in self.pieces(args, env):
            if p[0] == "lit":
                fmt += p[1].replace("%", "%%")
            else:
                fmt += "%s" if p[2] == "str" else "%d"
                vals.append(self.expr(p[1]))
        inner = self.string(fmt)[:-1] + '\\n"'
        return f"printf({', '.join([inner] + vals)});"

    def let(self, name, typ, value, mutable):
        t = self.type_name(typ)
        return f"{t}{'' if t.endswith('*') else ' '}{name} = {value};"

    def param(self, name, typ):
        t = self.type_name(typ)
        return f"{t}{'' if t.endswith('*') else ' '}{name}"

    def def_head(self, name, params):
        return f"void {name}({', '.join(params) or 'void'}) {{"

    def program(self, defs, main):
        return "\n".join(["#include <stdio.h>", ""] + _flat(defs)
                         + ["int main(void) {"] + self.block(main + ["return 0;"]) + ["}"])


class Cpp(C):
    id, name, ext = "cpp", "C++", ".cpp"
    runners = ("g++", "clang++")
    install_hint = "G++ or Clang (MinGW-w64 / MSYS2 on Windows)"

    def type_name(self, t):
        return {"int": "int", "str": "std::string"}[t]

    def print_(self, args, env):
        parts = [self.string(p[1]) if p[0] == "lit" else self.wrapped(p[1])
                 for p in self.pieces(args, env)]
        return "std::cout << " + " << ".join(parts) + " << std::endl;"

    def let(self, name, typ, value, mutable):
        return f"{self.type_name(typ)} {name} = {value};"

    def param(self, name, typ):
        return "int " + name if typ == "int" else f"const std::string& {name}"

    def def_head(self, name, params):
        return f"void {name}({', '.join(params)}) {{"

    def program(self, defs, main):
        return "\n".join(["#include <iostream>", "#include <string>", ""] + _flat(defs)
                         + ["int main() {"] + self.block(main + ["return 0;"]) + ["}"])


# ======================================================================== Go
class Go(Language):
    id, name, ext = "go", "Go", ".go"
    indent = "\t"
    end = ""
    cond_parens = False
    fn_style = "camel"
    optional_semicolons = True
    quotes = ('"', "`")
    kw_def = "func"
    kw_while = "for"   # Go spells while-loops as `for cond {}`
    runners = ("go",)
    install_hint = "Go (go.dev)"

    def print_(self, args, env):
        return f"fmt.Println({', '.join(self.expr(a) for a in args)})"

    def let(self, name, typ, value, mutable):
        return f"{name} := {value}"

    def for_head(self, var, start, stop, step, used):
        h = super().for_head(var, start, stop, step, used)
        # "for (int i = 0; i < 3; i++) {"  ->  "for i := 0; i < 3; i++ {"
        h = h.replace("for (int ", "for ", 1).replace(f"{var} = ", f"{var} := ", 1)
        return h[: -len(") {")] + " {"

    def while_(self, s, env, mut):
        return [f"for {self.cond(s.cond)} {{"] + self.block(self.body(s.body, env, mut)) + ["}"]

    def param(self, name, typ):
        return f"{name} {'int' if typ == 'int' else 'string'}"

    def def_head(self, name, params):
        return f"func {name}({', '.join(params)}) {{"

    def program(self, defs, main):
        out = ["package main", "", 'import "fmt"', ""]
        out += _flat(defs)
        out += ["func main() {"] + self.block(main) + ["}"]
        return "\n".join(out)


# ====================================================================== Rust
class Rust(Language):
    id, name, ext = "rust", "Rust", ".rs"
    cond_parens = False
    increment = False
    kw_def = "fn"
    quotes = ('"',)
    runners = ("rustc",)
    install_hint = "Rust (rustup.rs)"

    def print_(self, args, env):
        fmt, vals = "", []
        for p in self.pieces(args, env):
            if p[0] == "lit":
                fmt += p[1].replace("{", "{{").replace("}", "}}")
            else:
                fmt += "{}"
                vals.append(self.expr(p[1]))
        return f"println!({', '.join([self.string(fmt)] + vals)});"

    def let(self, name, typ, value, mutable):
        return f"let {'mut ' if mutable else ''}{name} = {value};"

    def for_(self, s, env, mut):
        if s.step <= 0:
            raise ValueError("Rust renderer only supports positive steps")
        v = s.var if uses_var(s.body, s.var) else "_"
        stop = _ex(s.stop)
        if isinstance(stop, Bin) and stop.op == "+" and _int_value(stop.right) == 1:
            rng = f"{self.expr(_ex(s.start))}..={self.expr(stop.left)}"
        else:
            rng = f"{self.expr(_ex(s.start))}..{self.expr(stop)}"
        it = rng if s.step == 1 else f"({rng}).step_by({s.step})"
        return [f"for {v} in {it} {{"] + self.block(self.body(s.body, env, mut)) + ["}"]

    def param(self, name, typ):
        return f"{name}: {'i32' if typ == 'int' else '&str'}"

    def def_head(self, name, params):
        return f"fn {name}({', '.join(params)}) {{"

    def program(self, defs, main):
        return "\n".join(_flat(defs) + ["fn main() {"] + self.block(main) + ["}"])


# ==================================================================== Kotlin
class Kotlin(Language):
    id, name, ext = "kotlin", "Kotlin", ".kt"
    end = ""
    fn_style = "camel"
    optional_semicolons = True
    quotes = ('"',)
    kw_def = "fun"
    runners = ("kotlinc",)
    install_hint = "the Kotlin compiler (kotlinlang.org) and a JDK"

    def template(self, args, env, dollar="$"):
        ps = self.pieces(args, env)
        out = ""
        for i, p in enumerate(ps):
            if p[0] == "lit":
                out += p[1].replace("\\", "\\\\").replace('"', '\\"').replace("$", "\\$")
            elif isinstance(p[1], Var):
                nxt = ps[i + 1][1][:1] if i + 1 < len(ps) and ps[i + 1][0] == "lit" else ""
                nm = self.var(p[1].name)
                out += f"{dollar}{{{nm}}}" if (nxt.isalnum() or nxt == "_") else f"{dollar}{nm}"
            else:
                out += f"{dollar}{{{self.expr(p[1])}}}"
        return '"' + out + '"'

    def print_(self, args, env):
        if len(args) == 1 and not isinstance(args[0], Str):
            return f"println({self.expr(args[0])})"
        return f"println({self.template(args, env)})"

    def let(self, name, typ, value, mutable):
        return f"{'var' if mutable else 'val'} {name} = {value}"

    def for_(self, s, env, mut):
        if s.step <= 0:
            raise ValueError("Kotlin renderer only supports positive steps")
        rng = f"{self.expr(_ex(s.start))}..{self.expr(self.inclusive_stop(_ex(s.stop)))}"
        if s.step != 1:
            rng += f" step {s.step}"
        return [f"for ({s.var} in {rng}) {{"] + self.block(self.body(s.body, env, mut)) + ["}"]

    def while_(self, s, env, mut):
        return [f"while {self.cond(s.cond)} {{"] + self.block(self.body(s.body, env, mut)) + ["}"]

    def param(self, name, typ):
        return f"{name}: {'Int' if typ == 'int' else 'String'}"

    def def_head(self, name, params):
        return f"fun {name}({', '.join(params)}) {{"

    def program(self, defs, main):
        return "\n".join(_flat(defs) + ["fun main() {"] + self.block(main) + ["}"])


# ====================================================================== Ruby
class Ruby(Language):
    id, name, ext = "ruby", "Ruby", ".rb"
    indent = "  "
    end = ""
    cond_parens = False
    increment = False
    line_comments = ("#",)
    block_comments = (("=begin", "=end"),)
    quotes_equivalent = True
    kw_elif = "elsif"
    kw_def = "def"
    kw_for = None   # .each / .times / .step are all fine
    placeholder = "# Write your code here"
    runners = ("ruby",)
    install_hint = "Ruby (ruby-lang.org)"

    def print_(self, args, env):
        if len(args) == 1:
            return f"puts {self.expr(args[0])}"
        out = ""
        for p in self.pieces(args, env):
            if p[0] == "lit":
                out += p[1].replace("\\", "\\\\").replace('"', '\\"').replace("#{", "\\#{")
            else:
                out += "#{" + self.expr(p[1]) + "}"
        return f'puts "{out}"'

    def if_(self, branches, orelse, env, mut):
        lines = []
        for i, (c, body) in enumerate(branches):
            lines.append(f"{'if' if i == 0 else 'elsif'} {self.cond(c)}")
            lines += self.block(self.body(body, env, mut))
        if orelse:
            lines.append("else")
            lines += self.block(self.body(orelse, env, mut))
        return lines + ["end"]

    def for_(self, s, env, mut):
        used = uses_var(s.body, s.var)
        start, stop = _ex(s.start), _ex(s.stop)
        bar = f" |{s.var}|" if used else ""
        if s.step == 1 and _int_value(start) == 0:
            head = f"{self.wrapped(stop)}.times do{bar}"
        else:
            rng = f"({self.expr(start)}..{self.expr(self.inclusive_stop(stop))})"
            head = f"{rng}.each do{bar}" if s.step == 1 else f"{rng}.step({s.step}) do{bar}"
        return [head] + self.block(self.body(s.body, env, mut)) + ["end"]

    def while_(self, s, env, mut):
        return [f"while {self.cond(s.cond)}"] + self.block(self.body(s.body, env, mut)) + ["end"]

    def call(self, name, args):
        return self.fn(name) + (f"({', '.join(self.expr(a) for a in args)})" if args else "")

    def def_head(self, name, params):
        return f"def {name}" + (f"({', '.join(params)})" if params else "")

    def close_block(self):
        return "end"

    def program(self, defs, main):
        return "\n".join(_flat(defs) + main)


# ======================================================================= PHP
class PHP(Language):
    id, name, ext = "php", "PHP", ".php"
    eq = "==="
    line_comments = ("//", "#")
    quotes_equivalent = True
    kw_def = "function"
    runners = ("php",)
    install_hint = "PHP 8 (php.net)"

    def var(self, name):
        return "$" + name

    def print_(self, args, env):
        segs, cur = [], ""
        for p in self.pieces(args, env):
            if p[0] == "lit":
                cur += p[1].replace("\\", "\\\\").replace('"', '\\"').replace("$", "\\$")
            elif isinstance(p[1], Var):
                cur += self.var(p[1].name)
            else:
                if cur:
                    segs.append(f'"{cur}"')
                    cur = ""
                segs.append(self.wrapped(p[1]))
        segs.append(f'"{cur}\\n"')
        return f"echo {' . '.join(segs)};"

    def for_decl(self, var):
        return ""

    def def_head(self, name, params):
        return f"function {name}({', '.join(params)}) {{"

    def program(self, defs, main):
        return "\n".join(["<?php", ""] + _flat(defs) + main)

    def starter(self):
        return "<?php\n\n" + self.placeholder + "\n"


# ======================================================================= Lua
class Lua(Language):
    id, name, ext = "lua", "Lua", ".lua"
    indent = "  "
    end = ""
    cond_parens = False
    increment = False
    line_comments = ("--",)
    block_comments = (("--[[", "]]"),)
    quotes_equivalent = True
    kw_elif = "elseif"
    kw_def = "function"
    placeholder = "-- Write your code here"
    runners = ("lua", "lua5.4", "lua54", "luajit")
    install_hint = "Lua 5.3+ (lua.org)"

    def print_(self, args, env):
        if len(args) == 1:
            return f"print({self.expr(args[0])})"
        parts = [self.string(p[1]) if p[0] == "lit" else self.wrapped(p[1])
                 for p in self.pieces(args, env)]
        return f"print({' .. '.join(parts)})"

    def let(self, name, typ, value, mutable):
        return f"local {name} = {value}"

    def aug(self, name, op, value_e):
        return f"{name} = {name} {op} {self.wrapped(value_e)}"

    def if_(self, branches, orelse, env, mut):
        lines = []
        for i, (c, body) in enumerate(branches):
            lines.append(f"{'if' if i == 0 else 'elseif'} {self.cond(c)} then")
            lines += self.block(self.body(body, env, mut))
        if orelse:
            lines.append("else")
            lines += self.block(self.body(orelse, env, mut))
        return lines + ["end"]

    def for_(self, s, env, mut):
        start, stop = _ex(s.start), _ex(s.stop)
        end_ = self.inclusive_stop(stop) if s.step > 0 else Bin("+", stop, Int(1))
        head = f"for {s.var} = {self.expr(start)}, {self.expr(end_)}"
        if s.step != 1:
            head += f", {s.step}"
        return [head + " do"] + self.block(self.body(s.body, env, mut)) + ["end"]

    def while_(self, s, env, mut):
        return [f"while {self.cond(s.cond)} do"] + self.block(self.body(s.body, env, mut)) + ["end"]

    def def_head(self, name, params):
        return f"local function {name}({', '.join(params)})"

    def close_block(self):
        return "end"

    def program(self, defs, main):
        return "\n".join(_flat(defs) + main)


# ===================================================================== Python
class Python(Language):
    """Only used for metadata / normalising; Python lessons are hand-written."""
    id, name, ext = "python", "Python", ".py"
    end = ""
    line_comments = ("#",)
    block_comments = ()
    quotes_equivalent = True
    placeholder = ""
    kw_elif = "elif"
    kw_def = "def"
    runners = ("python",)


LANGUAGES = {cls.id: cls() for cls in (
    Python, JavaScript, TypeScript, Java, C, Cpp, CSharp, Go, Rust, Kotlin,
    Ruby, PHP, Lua,
)}
