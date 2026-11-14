"""Small regex syntax highlighter shared by the editor and canvas renderer."""
from __future__ import annotations

import re

KEYWORDS = {
    "python": "def return if elif else for while in range and or not True False None import from class pass break continue print",
    "javascript": "function return if else for while let const var new class true false null undefined of in break continue console",
    "typescript": "function return if else for while let const var new class true false null undefined of in break continue console number string boolean interface type",
    "java": "public private static void class int String return if else for while new true false null boolean double System",
    "c": "include int void char const return if else for while break continue printf",
    "cpp": "include int void char const return if else for while break continue std string cout endl auto",
    "csharp": "using void int string var return if else for while new class true false null Console",
    "go": "package import func return if else for range var const true false nil int string fmt",
    "rust": "fn let mut return if else for while in loop match true false i32 str println",
    "kotlin": "fun val var return if else for while in until step true false null Int String println",
    "ruby": "def end if elsif else unless while do each times step puts return true false nil",
    "php": "php function return if else elseif for while foreach echo true false null",
    "lua": "local function return if then elseif else end for do while in and or not true false nil print",
}

COMMENTS = {
    "python": r"#[^\n]*", "ruby": r"#[^\n]*", "lua": r"--[^\n]*",
    "php": r"//[^\n]*|#(?!\{)[^\n]*|/\*[\s\S]*?\*/",
}
DEFAULT_COMMENT = r"//[^\n]*|/\*[\s\S]*?\*/"

COLORS = {
    "comment": "#6b7394",
    "string": "#a5e075",
    "number": "#ffb86c",
    "keyword": "#c792ea",
    "func": "#82aaff",
    "type": "#ffcb6b",
    "var": "#f07178",
    "punct": "#89ddff",
    "text": "#e6e9f5",
}

_cache = {}


def _pattern(lang_id):
    if lang_id not in _cache:
        kws = sorted(KEYWORDS.get(lang_id, "").split(), key=len, reverse=True)
        parts = [
            ("comment", COMMENTS.get(lang_id, DEFAULT_COMMENT)),
            ("string", r'"(?:\\.|[^"\\\n])*"?|\'(?:\\.|[^\'\\\n])*\'?|`[^`]*`?'),
            ("number", r"\b\d+(?:\.\d+)?\b"),
            ("var", r"\$\w+" if lang_id == "php" else r"(?!x)x"),
            ("keyword", r"(?<![\w$])(?:" + "|".join(map(re.escape, kws)) + r")(?!\w)" if kws else r"(?!x)x"),
            ("func", r"\b[A-Za-z_]\w*(?=\s*!?\()"),
            ("type", r"\b[A-Z]\w*\b"),
            ("punct", r"[{}()\[\];:.,<>=+\-*/%!&|]+"),
        ]
        _cache[lang_id] = re.compile("|".join(f"(?P<{k}>{p})" for k, p in parts))
    return _cache[lang_id]


def tokens(code: str, lang_id: str):
    """Yield (start, end, kind) spans."""
    for m in _pattern(lang_id).finditer(code):
        yield m.start(), m.end(), m.lastgroup


def colored_lines(code: str, lang_id: str):
    """[[(text, color), ...] per line] - used to draw code onto the canvas."""
    spans = []
    pos = 0
    for s, e, kind in tokens(code, lang_id):
        if s > pos:
            spans.append((code[pos:s], COLORS["text"]))
        spans.append((code[s:e], COLORS[kind]))
        pos = e
    if pos < len(code):
        spans.append((code[pos:], COLORS["text"]))
    lines = [[]]
    for text, col in spans:
        parts = text.split("\n")
        for i, part in enumerate(parts):
            if i:
                lines.append([])
            if part:
                lines[-1].append((part.replace("\t", "    "), col))
    return lines
