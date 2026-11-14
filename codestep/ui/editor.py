"""Code editor: line numbers, live highlighting, auto-indent, bracket pairs."""
from __future__ import annotations

import tkinter as tk

from . import syntax

PAIRS = {"(": ")", "[": "]", "{": "}", '"': '"', "'": "'"}
OPENERS_END = ("{", ":", "(", "[")
WORD_OPENERS = ("do", "then", "else")


class CodeEditor(tk.Frame):
    def __init__(self, master, theme, lang, on_submit=None):
        super().__init__(master, bg=theme.editor_bg, bd=0, highlightthickness=0)
        self.theme, self.lang, self.on_submit = theme, lang, on_submit
        f = theme.mono
        self.gutter = tk.Text(self, width=3, padx=10, pady=12, bd=0, highlightthickness=0, font=f,
                              bg=theme.editor_bg, fg=theme.muted, state="disabled", cursor="arrow",
                              takefocus=0)
        self.gutter.pack(side="left", fill="y")
        self.text = tk.Text(self, bd=0, highlightthickness=0, font=f, undo=True, wrap="none",
                            padx=8, pady=12, bg=theme.editor_bg, fg=syntax.COLORS["text"],
                            insertbackground=theme.accent, insertwidth=2, selectbackground="#3a4470",
                            selectforeground="#ffffff", spacing1=2, spacing3=2, tabs=(f.measure("    "),))
        self.text.pack(side="left", fill="both", expand=True)
        self.gutter.configure(spacing1=2, spacing3=2)
        for kind, col in syntax.COLORS.items():
            self.text.tag_configure(kind, foreground=col)
        self.text.tag_configure("comment", font=theme.mono_italic)
        self.text.tag_configure("curline", background=theme.editor_line)
        self.text.tag_lower("curline")
        self.gutter.tag_configure("right", justify="right")
        self.gutter.tag_configure("cur", foreground=theme.text)

        self.text.configure(yscrollcommand=self._sync)
        t = self.text
        t.bind("<KeyRelease>", lambda e: self.refresh())
        t.bind("<ButtonRelease-1>", lambda e: self.refresh(highlight=False))
        t.bind("<Tab>", self._tab)
        t.bind("<Return>", self._newline)
        t.bind("<BackSpace>", self._backspace)
        t.bind("<Control-Return>", self._submit)
        t.bind("<MouseWheel>", lambda e: self.after_idle(self._sync_now))
        for ch in PAIRS:
            t.bind(ch, lambda e, c=ch: self._open(c))
        for ch in (")", "]", "}"):
            t.bind(ch, lambda e, c=ch: self._close(c))
        self._hl_job = None

    # ------------------------------------------------------------ api
    def get(self) -> str:
        return self.text.get("1.0", "end-1c")

    def set(self, code: str):
        self.text.delete("1.0", "end")
        self.text.insert("1.0", code)
        self.text.edit_reset()
        self._place_cursor()
        self.refresh()

    def type_text(self, s: str):
        """Insert as if typed (used by the demo recorder)."""
        self.text.insert("insert", s)
        self.text.see("insert")
        self.refresh()

    def _place_cursor(self):
        """Put the cursor on the placeholder line if there is one."""
        idx = self.text.search(self.lang.placeholder or "\x00", "1.0", "end") if self.lang.placeholder else ""
        if idx:
            self.text.mark_set("insert", f"{idx} lineend")
        else:
            self.text.mark_set("insert", "end-1c")

    # ------------------------------------------------------------ painting
    def refresh(self, highlight=True):
        if highlight:
            self._highlight()
        n = int(self.text.index("end-1c").split(".")[0])
        cur = int(self.text.index("insert").split(".")[0])
        self.gutter.configure(state="normal")
        self.gutter.delete("1.0", "end")
        self.gutter.insert("1.0", "\n".join(str(i) for i in range(1, n + 1)), "right")
        self.gutter.tag_add("cur", f"{cur}.0", f"{cur}.end")
        self.gutter.configure(state="disabled")
        self.text.tag_remove("curline", "1.0", "end")
        self.text.tag_add("curline", "insert linestart", "insert lineend+1c")
        self._sync_now()

    def _highlight(self):
        code = self.get()
        for kind in syntax.COLORS:
            self.text.tag_remove(kind, "1.0", "end")
        for s, e, kind in syntax.tokens(code, self.lang.id):
            self.text.tag_add(kind, f"1.0+{s}c", f"1.0+{e}c")

    def _sync(self, first, last):
        self.gutter.yview_moveto(first)

    def _sync_now(self):
        self.gutter.yview_moveto(self.text.yview()[0])

    # ------------------------------------------------------------ editing
    def _indent_unit(self):
        return self.lang.indent

    def _tab(self, _e):
        if self.text.tag_ranges("sel"):
            first = int(self.text.index("sel.first").split(".")[0])
            last = int(self.text.index("sel.last").split(".")[0])
            for ln in range(first, last + 1):
                self.text.insert(f"{ln}.0", self._indent_unit())
        else:
            self.text.insert("insert", self._indent_unit())
        self.refresh()
        return "break"

    def _newline(self, _e):
        t = self.text
        line = t.get("insert linestart", "insert")
        after = t.get("insert", "insert lineend")
        indent = line[: len(line) - len(line.lstrip())]
        stripped = line.rstrip()
        words = stripped.split()
        opens = stripped.endswith(OPENERS_END) or bool(words and words[-1] in WORD_OPENERS)
        if not opens and words and self.lang.id in ("ruby", "lua") and not stripped.endswith("end"):
            opens = words[0] in ("def", "if", "elsif", "while", "unless", "function") \
                or stripped.startswith("local function")
        extra = self._indent_unit() if opens else ""
        if extra and after.strip()[:1] in (")", "]", "}"):
            t.insert("insert", "\n" + indent + extra)
            pos = t.index("insert")
            t.insert("insert", "\n" + indent)
            t.mark_set("insert", pos)
        else:
            t.insert("insert", "\n" + indent + extra)
        t.see("insert")
        self.refresh()
        return "break"

    def _backspace(self, _e):
        t = self.text
        if t.tag_ranges("sel"):
            return None
        before = t.get("insert-1c", "insert")
        after = t.get("insert", "insert+1c")
        if before in PAIRS and PAIRS[before] == after:
            t.delete("insert-1c", "insert+1c")
            self.refresh()
            return "break"
        line = t.get("insert linestart", "insert")
        unit = self._indent_unit()
        if line and line.endswith(unit) and not line.strip():
            t.delete(f"insert-{len(unit)}c", "insert")
            self.refresh()
            return "break"
        return None

    def _open(self, c):
        t = self.text
        nxt = t.get("insert", "insert+1c")
        if c in "\"'" and nxt == c:
            t.mark_set("insert", "insert+1c")
            return "break"
        if c in "\"'" and t.get("insert-1c", "insert").isalnum():
            return None  # don't pair inside words (e.g. "don't")
        if t.tag_ranges("sel"):
            sel = t.get("sel.first", "sel.last")
            t.delete("sel.first", "sel.last")
            t.insert("insert", c + sel + PAIRS[c])
        else:
            t.insert("insert", c + PAIRS[c])
            t.mark_set("insert", "insert-1c")
        self.refresh()
        return "break"

    def _close(self, c):
        t = self.text
        if t.get("insert", "insert+1c") == c:
            t.mark_set("insert", "insert+1c")
            self.refresh(highlight=False)
            return "break"
        line = t.get("insert linestart", "insert")
        if c == "}" and line and not line.strip() and line.endswith(self._indent_unit()):
            t.delete(f"insert-{len(self._indent_unit())}c", "insert")
        return None

    def _submit(self, _e):
        if self.on_submit:
            self.on_submit()
        return "break"
