"""Colours, fonts and per-language accents."""
from __future__ import annotations

import tkinter.font as tkfont

# (accent, gradient end, badge text)
LANG_STYLE = {
    "python": ("#4b8bbe", "#ffd43b", "Py"),
    "javascript": ("#f7df1e", "#ff9f1c", "JS"),
    "typescript": ("#3178c6", "#5ec8ff", "TS"),
    "java": ("#f89820", "#ff4f5e", "Jv"),
    "c": ("#7d8fff", "#a8b9cc", "C"),
    "cpp": ("#f34b7d", "#9b5cff", "C++"),
    "csharp": ("#2fbf71", "#9be15d", "C#"),
    "go": ("#00add8", "#5ef2ff", "Go"),
    "rust": ("#ff7a45", "#ffb86c", "Rs"),
    "kotlin": ("#a97bff", "#ff6bd6", "Kt"),
    "ruby": ("#e5484d", "#ff8a8a", "Rb"),
    "php": ("#8892bf", "#c3b6ff", "PHP"),
    "lua": ("#5b6cff", "#9ec5ff", "Lua"),
}


def _pick(families, *names):
    for n in names:
        if n in families:
            return n
    return names[-1]


class Theme:
    bg = "#0a0d1a"
    bg2 = "#11162b"
    card = "#151a31"
    card2 = "#1b2140"
    border = "#2a3157"
    text = "#eef0ff"
    muted = "#8d95bd"
    dim = "#5b6390"
    success = "#2ee59d"
    error = "#ff5c7a"
    warn = "#ffb648"
    editor_bg = "#0f1326"
    editor_line = "#161c36"

    def __init__(self, root):
        fam = set(tkfont.families(root))
        ui = _pick(fam, "Inter", "Segoe UI Variable Display", "Segoe UI", "SF Pro Display",
                   "Helvetica Neue", "DejaVu Sans", "Helvetica")
        mono = _pick(fam, "JetBrains Mono", "Cascadia Code", "Fira Code", "Consolas", "Menlo",
                     "DejaVu Sans Mono", "Courier")
        F = lambda size, weight="normal", fam_=ui, slant="roman": tkfont.Font(  # noqa: E731
            root=root, family=fam_, size=-size, weight=weight, slant=slant)
        self.logo = F(30, "bold")
        self.h1 = F(34, "bold")
        self.h2 = F(24, "bold")
        self.h3 = F(17, "bold")
        self.body = F(15)
        self.body_b = F(15, "bold")
        self.small = F(13)
        self.small_b = F(13, "bold")
        self.tiny = F(11, "bold")
        self.big_num = F(44, "bold")
        self.mono = F(14, fam_=mono)
        self.mono_italic = F(14, fam_=mono, slant="italic")
        self.mono_small = F(13, fam_=mono)
        self.accent = "#4b8bbe"
        self.accent2 = "#ffd43b"

    def set_lang(self, lang_id):
        self.accent, self.accent2, _ = LANG_STYLE.get(lang_id, LANG_STYLE["python"])
