"""CodeStep's animated interface, drawn entirely on one Tk canvas."""
from __future__ import annotations

import itertools
from datetime import date
import math
import random
import sys
import threading
import tkinter as tk

from .. import __version__ as VERSION
from .. import progress as prog
from ..checker import CheckResult, check
from ..curriculum import lessons_for
from ..languages import LANGUAGES
from ..runner import find_runner
from . import syntax
from .editor import CodeEditor
from .fx import (Animator, Burst, Confetti, darken, ease_in_out_cubic, ease_out_back, ease_out_cubic,
                 ease_out_elastic, glow, gradient_round_rect, hex_to_rgb, lerp, lighten, linear, mix,
                 round_rect, vertical_gradient)
from .theme import LANG_STYLE, Theme

RELEASES_API = "https://api.github.com/repos/jakubek382/CodeStep/releases/latest"
PRAISE = ["Excellent!", "Nailed it!", "Awesome!", "Perfect!", "You're on fire!", "Brilliant!", "Great job!"]
_ids = itertools.count()


def _luma(c):
    r, g, b = hex_to_rgb(c)
    return (0.299 * r + 0.587 * g + 0.114 * b) / 255


def ink_on(c):
    """Readable text colour on top of colour c."""
    return "#0a0d1a" if _luma(c) > 0.58 else "#ffffff"


# ====================================================================== button
class Button:
    def __init__(self, app, x, y, w, h, text, command, kind="primary", font=None, tags=("screen",),
                 accent=None, accent2=None, name=None):
        self.app, self.cv, t = app, app.cv, app.t
        self.command, self.kind = command, kind
        self.tag = f"btn{next(_ids)}"
        tags = tuple(tags) + (self.tag,)
        self.box = (x, y, x + w, y + h)
        a = accent or t.accent
        b = accent2 or t.accent2
        r = h / 2
        cv = self.cv
        self.glow_items, self.body = [], None
        if kind == "primary":
            self.glow_items = glow(cv, x, y, x + w, y + h, r, a, t.bg, layers=4, spread=3, strength=0.45,
                                   tags=tags)
            gradient_round_rect(cv, x, y, x + w, y + h, r, a, b, tags=tags)
            ink = ink_on(mix(a, b, 0.5))
            self.colors = {"glow": a}
        else:
            fill = {"ghost": t.card2, "success": t.success, "danger": t.error}[kind]
            outline = t.border if kind == "ghost" else fill
            self.body = round_rect(cv, x, y, x + w, y + h, r, fill=fill, outline=outline, width=1.5, tags=tags)
            ink = t.text if kind == "ghost" else "#0a0d1a"
            self.colors = {"fill": fill, "outline": outline,
                           "hfill": mix(fill, a, 0.22) if kind == "ghost" else lighten(fill, 0.18),
                           "houtline": a if kind == "ghost" else lighten(fill, 0.3)}
        self.ink = ink
        self.label = cv.create_text(x + w / 2, y + h / 2, text=text, font=font or t.body_b, fill=ink, tags=tags)
        self.lift = 0.0
        self.busy = False
        self.spin_items = []
        self.hot = app.add_hot(*self.box, click=self._click, enter=self._enter, leave=self._leave,
                               press=self._press, release=self._release)
        if name:
            app.targets[name] = (x + w / 2, y + h / 2)

    def _set_hover(self, p):
        t = self.app.t
        if self.kind == "primary":
            n = len(self.glow_items)
            for i, it in enumerate(self.glow_items):
                k = (n - i) / n
                s = 0.45 + 0.4 * p
                self.cv.itemconfigure(it, outline=mix(self.colors["glow"], t.bg, 1 - s * (1 - k) ** 1.6 - 0.12))
        else:
            self.cv.itemconfigure(self.body, fill=mix(self.colors["fill"], self.colors["hfill"], p),
                                  outline=mix(self.colors["outline"], self.colors["houtline"], p))
        target = -2 * p
        self.cv.move(self.tag, 0, target - self.lift)
        self.lift = target

    def _enter(self):
        self.app.anim.tween(0.16, self._set_hover, key=self.tag + "h")

    def _leave(self):
        self.app.anim.tween(0.22, lambda p: self._set_hover(1 - p), key=self.tag + "h")

    def _press(self):
        self.cv.move(self.tag, 0, 2)

    def _release(self):
        self.cv.move(self.tag, 0, -2)

    def _click(self):
        if not self.busy and self.command:
            self.command()

    def set_text(self, s):
        self.cv.itemconfigure(self.label, text=s)

    def spinner(self, on, text=""):
        cv = self.cv
        for it in self.spin_items:
            cv.delete(it)
        self.spin_items = []
        self.app.anim.cancel(self.tag + "spin")
        self.busy = on
        if not on:
            cv.itemconfigure(self.label, text=text or cv.itemcget(self.label, "text"))
            return
        x1, y1, x2, y2 = self.box
        cx, cy = (x1 + x2) / 2 - 44, (y1 + y2) / 2 + self.lift
        rr = 9
        arc = cv.create_arc(cx - rr, cy - rr, cx + rr, cy + rr, start=0, extent=270, style="arc",
                            outline=self.ink, width=3, tags=("screen", self.tag))
        self.spin_items.append(arc)
        cv.itemconfigure(self.label, text="     " + text)

        def spin(dt, t):
            cv.itemconfigure(arc, start=(-t * 420) % 360, extent=200 + 80 * math.sin(t * 5))
        self.app.anim.ticker(self.tag + "spin", spin)


# ========================================================================= app
class App:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("CodeStep")
        self.root.geometry("1240x800")
        self.root.minsize(1100, 720)
        self.t = Theme(self.root)
        self.root.configure(bg=self.t.bg)
        self.cv = tk.Canvas(self.root, bg=self.t.bg, highlightthickness=0, bd=0)
        self.cv.pack(fill="both", expand=True)
        self.anim = Animator(self.root)
        self.targets = {}            # name -> (x, y)  (used by the demo recorder)
        self.hot_layers = [[]]
        self.hover = self.pressed = None
        self.windows = []
        self.screen = None
        self.size = (0, 0)
        self._resize_job = None
        self.in_transition = False
        self.pending_unlock = None
        self.banner_state = None

        try:
            self.progress = prog.load()
        except OSError as e:
            from tkinter import messagebox
            messagebox.showerror("Error", f"Cannot create CodeStep folder in Documents: {e}")
            sys.exit(1)
        self.lang = LANGUAGES.get(self.progress.get("language"), LANGUAGES["python"])
        self.t.set_lang(self.lang.id)
        self.lesson_no, self.task_no = 1, 1

        cv = self.cv
        cv.bind("<Motion>", self._motion)
        cv.bind("<Leave>", lambda e: self._set_hover(None))
        cv.bind("<ButtonPress-1>", self._mpress)
        cv.bind("<ButtonRelease-1>", self._mrelease)
        self.root.bind("<Configure>", self._on_configure)
        self.root.bind("<Escape>", lambda e: self.go_home() if self.screen == "lesson" else None)
        self.root.bind("<Return>", self._on_return)
        self.root.bind("<Control-Return>", lambda e: self.run_check() if self.screen == "lesson" else None)
        self.root.after(30, self._start)

    def mainloop(self):
        self.root.mainloop()

    # ---------------------------------------------------------------- basics
    @property
    def W(self):
        return max(self.cv.winfo_width(), 1100)

    @property
    def H(self):
        return max(self.cv.winfo_height(), 700)

    @property
    def lessons(self):
        return lessons_for(self.lang.id)

    @property
    def lp(self):
        return prog.lang_progress(self.progress, self.lang.id)

    @property
    def task(self):
        return self.lessons[self.lesson_no - 1].tasks[self.task_no - 1]

    def text(self, x, y, s, font, fill, anchor="nw", tags=("screen",), **kw):
        return self.cv.create_text(x, y, text=s, font=font, fill=fill, anchor=anchor, tags=tags, **kw)

    def save(self):
        try:
            prog.save(self.progress)
        except OSError as e:
            self.toast(f"Cannot save progress: {e}", "error")

    # ---------------------------------------------------------------- hotspots
    def add_hot(self, x1, y1, x2, y2, click=None, enter=None, leave=None, press=None, release=None,
                cursor="hand2", circle=False):
        h = dict(box=(x1, y1, x2, y2), click=click, enter=enter, leave=leave, press=press, release=release,
                 cursor=cursor, circle=circle)
        self.hot_layers[-1].append(h)
        return h

    def _hit(self, x, y):
        if self.in_transition:
            return None
        for h in reversed(self.hot_layers[-1]):
            x1, y1, x2, y2 = h["box"]
            if h["circle"]:
                cx, cy, r = (x1 + x2) / 2, (y1 + y2) / 2, (x2 - x1) / 2
                if (x - cx) ** 2 + (y - cy) ** 2 <= r * r:
                    return h
            elif x1 <= x <= x2 and y1 <= y <= y2:
                return h
        return None

    def _set_hover(self, h):
        if h is self.hover:
            return
        if self.hover and self.hover["leave"]:
            self.hover["leave"]()
        self.hover = h
        if h and h["enter"]:
            h["enter"]()
        self.cv.configure(cursor=h["cursor"] if h else "")

    def _motion(self, e):
        self._set_hover(self._hit(e.x, e.y))

    def _mpress(self, e):
        self.pressed = self._hit(e.x, e.y)
        if self.pressed and self.pressed["press"]:
            self.pressed["press"]()

    def _mrelease(self, e):
        p, self.pressed = self.pressed, None
        if p and p["release"]:
            p["release"]()
        h = self._hit(e.x, e.y)
        if p is not None and h is p and h["click"]:
            h["click"]()

    def push_layer(self):
        self._set_hover(None)
        self.hot_layers.append([])

    def pop_layer(self):
        self._set_hover(None)
        if len(self.hot_layers) > 1:
            self.hot_layers.pop()

    # ---------------------------------------------------------------- lifecycle
    def _start(self):
        self.size = (self.cv.winfo_width(), self.cv.winfo_height())
        self.draw_background()
        self.splash()

    def _on_configure(self, e):
        if e.widget is not self.root:
            return
        new = (self.cv.winfo_width(), self.cv.winfo_height())
        if self.screen is None or abs(new[0] - self.size[0]) + abs(new[1] - self.size[1]) < 4:
            return
        self.size = new
        if self._resize_job:
            self.root.after_cancel(self._resize_job)
        self._resize_job = self.root.after(160, self._relayout)

    def _relayout(self):
        self._resize_job = None
        if self.in_transition:
            return
        self.draw_background()
        code = self.editor.get() if self.screen == "lesson" and getattr(self, "editor", None) else None
        if self.screen == "home":
            self.build_home(animate=False)
        elif self.screen == "lesson":
            self.build_lesson(animate=False, code=code)
        elif self.screen == "complete":
            self.build_complete(animate=False)

    def clear_screen(self):
        self._set_hover(None)
        self.anim.cancel_prefix("scr:")
        self.cv.delete("screen")
        self.cv.delete("banner")
        for w in self.windows:
            w.destroy()
        self.windows = []
        self.hot_layers = [[]]
        self.targets = {k: v for k, v in self.targets.items() if k.startswith("sys:")}
        self.banner_state = None

    # ---------------------------------------------------------------- background
    def draw_background(self):
        cv, t = self.cv, self.t
        W, H = self.W, self.H
        cv.delete("bg")
        self.anim.cancel("amb")
        vertical_gradient(cv, 0, 0, W, H, t.bg, t.bg2, tags=("bg",), step=4)
        self.blobs = []
        specs = [(0.12, 0.08, 340, "a", 0.0), (0.92, 0.9, 380, "b", 2.1), (0.62, 0.42, 260, "a", 4.2)]
        for fx_, fy_, R, which, phase in specs:
            cx, cy = W * fx_, H * fy_
            rings = []
            steps = 16
            for i in range(steps):
                r = R * (1 - i / steps)
                k = (i / steps) ** 1.8
                rings.append((cv.create_oval(cx - r, cy - r, cx + r, cy + r, outline="", tags=("bg",)), k))
            self.blobs.append({"rings": rings, "which": which, "phase": phase, "dx": 0.0, "dy": 0.0,
                               "tag": None})
        self._paint_blobs(t.accent, t.accent2)
        self.particles = []
        for _ in range(42):
            x, y = random.uniform(0, W), random.uniform(0, H)
            r = random.uniform(0.8, 2.2)
            it = cv.create_oval(x - r, y - r, x + r, y + r, outline="", tags=("bg",))
            self.particles.append({"i": it, "x": x, "y": y, "r": r, "vx": random.uniform(-6, 6),
                                   "vy": random.uniform(-16, -4), "tw": random.uniform(0, 6)})
        cv.tag_lower("bg")
        self._frame_n = 0
        self.anim.ticker("amb", self._ambient)

    def _paint_blobs(self, a, b, strength=0.17):
        bg = self.t.bg
        for blob in self.blobs:
            col = a if blob["which"] == "a" else b
            for it, k in blob["rings"]:
                self.cv.itemconfigure(it, fill=mix(bg, col, strength * k))

    def _ambient(self, dt, t):
        cv = self.cv
        W, H = self.W, self.H
        self._frame_n += 1
        for p in self.particles:
            p["x"] += p["vx"] * dt
            p["y"] += p["vy"] * dt
            if p["y"] < -5:
                p["y"], p["x"] = H + 5, random.uniform(0, W)
            tw = (math.sin(t * 1.6 + p["tw"]) + 1) / 2
            r = p["r"]
            cv.coords(p["i"], p["x"] - r, p["y"] - r, p["x"] + r, p["y"] + r)
            if self._frame_n % 3 == 0:
                cv.itemconfigure(p["i"], fill=mix(self.t.bg, lighten(self.t.accent, 0.4), 0.25 + 0.5 * tw))
        if self._frame_n % 2 == 0:
            for blob in self.blobs:
                nx = math.sin(t * 0.23 + blob["phase"]) * 40
                ny = math.cos(t * 0.19 + blob["phase"]) * 30
                ddx, ddy = nx - blob["dx"], ny - blob["dy"]
                for it, _ in blob["rings"]:
                    cv.move(it, ddx, ddy)
                blob["dx"], blob["dy"] = nx, ny
        return True

    def recolor(self, new_lang_id, dur=0.7):
        oa, ob = self.t.accent, self.t.accent2
        na, nb, _ = LANG_STYLE[new_lang_id]
        self.t.set_lang(new_lang_id)
        self.anim.tween(dur, lambda p: self._paint_blobs(mix(oa, na, p), mix(ob, nb, p)),
                        ease=ease_in_out_cubic, key="recolor")

    # ---------------------------------------------------------------- effects
    def appear(self, items, delay=0.0, dy=22, dur=0.5, dx=0):
        """Slide + fade items in from (dx, dy)."""
        cv = self.cv
        bgc = self.t.bg
        rec = []
        for it in items:
            typ = cv.type(it)
            if typ is None:
                continue
            cols = {}
            if typ != "window":
                for opt in ("fill", "outline"):
                    try:
                        v = cv.itemcget(it, opt)
                    except tk.TclError:
                        continue
                    if v and v.startswith("#") and len(v) == 7:
                        cols[opt] = v
                for opt, v in cols.items():
                    cv.itemconfigure(it, **{opt: bgc})
            cv.move(it, dx, dy)
            rec.append((it, cols))
        state = {"p": 0.0}

        def upd(p):
            off = 1 - p
            prev = 1 - state["p"]
            for it, cols in rec:
                cv.move(it, dx * (off - prev), dy * (off - prev))
                if cols:
                    cv.itemconfigure(it, **{o: mix(bgc, v, min(1, p * 1.3)) for o, v in cols.items()})
            state["p"] = p

        self.anim.tween(dur, upd, ease=ease_out_cubic, delay=delay)

    def float_text(self, x, y, s, color, font=None):
        it = self.text(x, y, s, font or self.t.h3, color, anchor="center", tags=("screen", "fxtop"))

        def upd(p):
            self.cv.coords(it, x, y - 90 * p)
            self.cv.itemconfigure(it, fill=mix(color, self.t.bg, max(0, p * 1.4 - 0.4)))
        self.anim.tween(1.3, upd, ease=ease_out_cubic, done=lambda: self.cv.delete(it))

    def shake(self, tag, amp=14, dur=0.5):
        st = {"x": 0.0}

        def upd(p):
            x = amp * math.sin(p * math.pi * 7) * (1 - p)
            self.cv.move(tag, x - st["x"], 0)
            st["x"] = x
        self.anim.tween(dur, upd, ease=linear)

    def toast(self, msg, kind="info", dur=3.4):
        cv, t = self.cv, self.t
        cv.delete("toast")
        self.anim.cancel("toast")
        col = {"info": t.accent, "success": t.success, "error": t.error, "warn": t.warn}[kind]
        W = self.W
        tw = min(520, max(220, t.body.measure(msg) + 10))
        tmp = cv.create_text(0, 0, text=msg, font=t.body, width=tw, anchor="nw")
        x1_, y1_, x2_, y2_ = cv.bbox(tmp)
        cv.delete(tmp)
        w, h = (x2_ - x1_) + 88, max(56, (y2_ - y1_) + 30)
        x = (W - w) / 2
        tags = ("toast",)
        items = glow(cv, x, 0, x + w, h, 16, col, t.bg, layers=3, spread=3, strength=0.4, tags=tags)
        items.append(round_rect(cv, x, 0, x + w, h, 16, fill=t.card2, outline=mix(col, t.card2, 0.3), width=1.5,
                                tags=tags))
        items.append(cv.create_oval(x + 18, h / 2 - 14, x + 46, h / 2 + 14, fill=col, outline="", tags=tags))
        sym = {"info": "i", "success": "✓", "error": "!", "warn": "!"}[kind]
        items.append(cv.create_text(x + 32, h / 2, text=sym, font=t.body_b, fill=ink_on(col), tags=tags))
        items.append(cv.create_text(x + 60, h / 2, text=msg, font=t.body, fill=t.text, anchor="w", width=tw,
                                    tags=tags))
        st = {"y": 0.0}

        def place(p, y0=-h - 20, y1=18):
            y = lerp(y0, y1, p)
            cv.move("toast", 0, y - st["y"])
            st["y"] = y
            cv.tag_raise("toast")

        place(0)
        self.anim.tween(0.45, place, ease=ease_out_back, key="toast",
                        done=lambda: self.anim.tween(0.35, lambda p: place(p, 18, -h - 30), ease=ease_in_out_cubic,
                                                     delay=dur, key="toast", done=lambda: cv.delete("toast")))

    def curtain(self, midway):
        """Three coloured bands sweep across; screen is swapped underneath."""
        cv, t = self.cv, self.t
        W, H = self.W, self.H
        skew = 260
        self.in_transition = True
        self._set_hover(None)
        for w in self.windows:
            try:
                cv.itemconfigure(self._win_items[w], state="hidden")
            except (AttributeError, KeyError, tk.TclError):
                pass
        cols = [darken(t.accent, 0.55), t.accent, mix(t.accent, t.accent2, 0.6)]
        bands = []
        for c in cols:
            bands.append(cv.create_polygon(0, 0, 0, 0, 0, 0, 0, 0, fill=c, outline="", tags=("curtain",)))

        def shape(it, x):
            cv.coords(it, x, 0, x + W + skew, 0, x + W, H, x - skew, H)

        for b in bands:
            shape(b, -W - skew - 10)

        def phase_in(i):
            return lambda p: (shape(bands[i], lerp(-W - skew - 10, 0, p)), cv.tag_raise("curtain"))

        def phase_out(i):
            return lambda p: (shape(bands[i], lerp(0, W + skew + 10, p)), cv.tag_raise("curtain"))

        def swap():
            midway()
            for w in self.windows:
                cv.itemconfigure(self._win_items[w], state="hidden")
            cv.tag_raise("curtain")
            for i in range(3):
                self.anim.tween(0.42, phase_out(2 - i), ease=ease_in_out_cubic, delay=0.05 + i * 0.07,
                                done=finish if i == 2 else None)

        def finish():
            cv.delete("curtain")
            self.in_transition = False
            for w in self.windows:
                try:
                    cv.itemconfigure(self._win_items[w], state="normal")
                except tk.TclError:
                    pass
            if self.screen == "lesson":
                self.editor.text.focus_set()

        for i in range(3):
            self.anim.tween(0.4, phase_in(i), ease=ease_in_out_cubic, delay=i * 0.07,
                            done=swap if i == 2 else None)

    def embed(self, widget, x, y, w, h, tags=("screen",)):
        if not hasattr(self, "_win_items"):
            self._win_items = {}
        it = self.cv.create_window(x, y, window=widget, anchor="nw", width=w, height=h, tags=tags)
        self.windows.append(widget)
        self._win_items[widget] = it
        if self.in_transition:
            self.cv.itemconfigure(it, state="hidden")
        return it

    # ---------------------------------------------------------------- splash
    def splash(self):
        self.screen = "splash"
        cv, t = self.cv, self.t
        W, H = self.W, self.H
        cx, cy = W / 2, H / 2 - 30
        s = 84
        gradient_round_rect(cv, cx - s / 2, cy - s / 2 - 40, cx + s / 2, cy + s / 2 - 40, 24,
                                   t.accent, t.accent2, tags=("screen", "mark"))
        g = glow(cv, cx - s / 2, cy - s / 2 - 40, cx + s / 2, cy + s / 2 - 40, 24, t.accent, t.bg,
                 layers=5, spread=4, strength=0.5, tags=("screen", "mark"))
        cv.tag_lower(g[0])
        sym = self.text(cx, cy - 40, "</>", t.h2, ink_on(mix(t.accent, t.accent2, .5)), anchor="center",
                        tags=("screen", "mark"))
        st = {"s": 1.0}
        cv.scale("mark", cx, cy - 40, 0.01, 0.01)
        st["s"] = 0.01
        cv.itemconfigure(sym, state="hidden")

        def grow(p):
            sc = max(0.01, p)
            cv.scale("mark", cx, cy - 40, sc / st["s"], sc / st["s"])
            st["s"] = sc
        self.anim.tween(0.9, grow, ease=ease_out_elastic, done=lambda: cv.itemconfigure(sym, state="normal"))

        word = "CodeStep"
        total = sum(t.h1.measure(ch) for ch in word) * 1.25
        x = cx - total / 2
        for i, ch in enumerate(word):
            it = self.text(x, cy + 58, ch, ("" + t.h1.actual("family"), -44, "bold"),
                           mix(t.accent, t.accent2, i / 7), anchor="w")
            x += t.h1.measure(ch) * 1.25
            self.appear([it], delay=0.25 + i * 0.05, dy=-40, dur=0.6)
        tag = self.text(cx, cy + 110, "Learn to code, one step at a time", t.body, t.muted, anchor="center")
        self.appear([tag], delay=0.8, dy=10)
        self.root.after(1900, lambda: self.curtain(lambda: self.build_home()))

    # ================================================================== HOME
    def go_home(self):
        if self.in_transition:
            return
        self.curtain(lambda: self.build_home())

    def build_home(self, animate=True, only_path=False):
        self.clear_screen()
        self.screen = "home"
        self.root.title(f"CodeStep — Learn {self.lang.name}")
        cv, t = self.cv, self.t
        W, H = self.W, self.H
        d = 0.0 if not animate else 0.05

        # ---- header
        logo_items = []
        logo_items += gradient_round_rect(cv, 30, 24, 76, 70, 14, t.accent, t.accent2, tags=("screen",))
        logo_items.append(self.text(53, 47, "</>", t.small_b, ink_on(mix(t.accent, t.accent2, .5)), anchor="center"))
        letters = []
        x = 92
        for ch in "CodeStep":
            letters.append(self.text(x, 40, ch, t.logo, t.text, anchor="w"))
            x += t.logo.measure(ch)
        logo_items += letters
        logo_items.append(self.text(93, 64, "Learn to code, one step at a time", t.small, t.muted, anchor="w"))

        def shimmer(dt, tt):
            for i, it in enumerate(letters):
                k = (math.sin(tt * 1.8 - i * 0.45) + 1) / 2
                cv.itemconfigure(it, fill=mix(lighten(t.accent, 0.25), t.accent2, k))
        self.anim.ticker("scr:logo", shimmer)

        # ---- stat chips (right)
        p = self.progress
        level = prog.level_for(p["xp"])
        chip_items = []
        xr = W - 30
        for kind, value, label in (("level", f"Lv {level}", ""), ("xp", f"{p['xp']:,}", "XP"),
                                   ("streak", str(p["streak"]), "day streak" if p["streak"] == 1 else "day streak")):
            vw = t.body_b.measure(value)
            lw = t.small.measure(label) if label else 0
            w = 52 + vw + (lw + 8 if label else 0)
            x1 = xr - w
            chip_items.append(round_rect(cv, x1, 26, xr, 68, 21, fill=t.card, outline=t.border, width=1,
                                         tags=("screen",)))
            ix, iy = x1 + 24, 47
            chip_items += self.icon(kind, ix, iy, level_frac=(p["xp"] % prog.XP_PER_LEVEL) / prog.XP_PER_LEVEL)
            chip_items.append(self.text(x1 + 42, 47, value, t.body_b, t.text, anchor="w"))
            if label:
                chip_items.append(self.text(x1 + 48 + vw, 48, label, t.small, t.muted, anchor="w"))
            xr = x1 - 10

        # ---- language rail
        rail = self.build_rail(30, 108, 268, H - 24)

        # ---- right panel
        panel = self.build_panel(W - 300, 108, W - 30, H - 24)

        # ---- path
        path = self.build_path(300, 100, W - 330, H - 30)

        if animate:
            if not only_path:
                self.appear(logo_items, d, dy=-14)
                self.appear(chip_items, d + 0.1, dy=-14)
                for i, grp in enumerate(rail):
                    self.appear(grp, d + 0.1 + i * 0.025, dx=-26, dy=0, dur=0.45)
            for i, grp in enumerate(panel):
                self.appear(grp, d + 0.15 + i * 0.08, dx=26, dy=0)
            for i, grp in enumerate(path):
                self.appear(grp, d + 0.1 + i * 0.07, dy=26)

        if self.pending_unlock:
            n = self.pending_unlock
            self.pending_unlock = None
            if f"node:{n}" in self.targets:
                x_, y_ = self.targets[f"node:{n}"]
                self.root.after(900, lambda: (Burst(self, x_, y_, t.accent, radius=90),
                                              self.toast(f"Lesson {n} unlocked!", "success")))

    def icon(self, kind, x, y, level_frac=0.0, tags=("screen",)):
        cv, t = self.cv, self.t
        if kind == "streak":
            pts = [0, 11, -8, 3, -5, -6, 0, -13, 2, -4, 7, -8, 8, 3]
            outer = cv.create_polygon([v + (x if i % 2 == 0 else y) for i, v in enumerate(pts)], smooth=True,
                                      fill="#ff7a3d", outline="", tags=tags)
            inner = cv.create_oval(x - 4, y - 1, x + 4, y + 10, fill="#ffd166", outline="", tags=tags)
            return [outer, inner]
        if kind == "xp":
            pts = [2, -12, -7, 2, -1, 2, -3, 12, 7, -2, 1, -2]
            return [cv.create_polygon([v + (x if i % 2 == 0 else y) for i, v in enumerate(pts)],
                                      fill="#ffd166", outline="", tags=tags)]
        if kind == "level":
            r = 10
            a = cv.create_oval(x - r, y - r, x + r, y + r, outline=t.card2, width=4, tags=tags)
            b = cv.create_arc(x - r, y - r, x + r, y + r, start=90, extent=-max(1, 359.9 * level_frac),
                              style="arc", outline=t.accent2, width=4, tags=tags)
            return [a, b]
        if kind == "lock":
            a = cv.create_arc(x - 7, y - 14, x + 7, y + 2, start=0, extent=180, style="arc", outline=t.muted,
                              width=3, tags=tags)
            b = round_rect(cv, x - 10, y - 5, x + 10, y + 10, 4, fill=t.muted, outline="", tags=tags)
            return [a, b]
        return []

    # ---------------------------------------------------------------- rail
    def build_rail(self, x0, y0, x1, y1):
        cv, t = self.cv, self.t
        groups = [[self.text(x0 + 4, y0, "L A N G U A G E S", t.tiny, t.dim)]]
        n = len(LANGUAGES)
        top = y0 + 26
        ih = min(46, (y1 - top) / n - 6)
        for i, lang in enumerate(LANGUAGES.values()):
            y = top + i * (ih + 6)
            groups.append(self.rail_item(lang, x0, y, x1, y + ih))
        return groups

    def rail_item(self, lang, x0, y0, x1, y1):
        cv, t = self.cv, self.t
        a, b, badge = LANG_STYLE[lang.id]
        sel = lang.id == self.lang.id
        tag = f"rail_{lang.id}"
        tags = ("screen", tag)
        h = y1 - y0
        fill = mix(t.card, a, 0.16) if sel else t.card
        outline = mix(t.card, a, 0.7) if sel else mix(t.card, t.border, 0.5)
        items = []
        if sel:
            items += glow(cv, x0, y0, x1, y1, 12, a, t.bg, layers=3, spread=2, strength=0.35, tags=tags)
        body = round_rect(cv, x0, y0, x1, y1, 12, fill=fill, outline=outline, width=1.5, tags=tags)
        items.append(body)
        bs = h - 14
        items += gradient_round_rect(cv, x0 + 8, y0 + 7, x0 + 8 + bs, y0 + 7 + bs, 8, a, b, tags=tags, step=3)
        items.append(self.text(x0 + 8 + bs / 2, y0 + h / 2, badge, t.tiny, ink_on(mix(a, b, .5)),
                               anchor="center", tags=tags))
        items.append(self.text(x0 + 18 + bs, y0 + h / 2, lang.name, t.body_b if sel else t.body,
                               t.text if sel else mix(t.text, t.muted, 0.4), anchor="w", tags=tags))
        lp = prog.lang_progress(self.progress, lang.id) if lang.id in self.progress["languages"] else None
        done = sum(lp["completed_tasks"].values()) if lp else 0
        total = sum(len(l.tasks) for l in lessons_for(lang.id))
        if done:
            items.append(self.text(x1 - 12, y0 + h / 2, f"{done}/{total}", t.small, a, anchor="e", tags=tags))
        st = {"x": 0.0}

        def hov(p):
            x = 6 * p
            cv.move(tag, x - st["x"], 0)
            st["x"] = x
            if not sel:
                cv.itemconfigure(body, fill=mix(t.card, mix(t.card2, a, 0.12), p),
                                 outline=mix(outline, a, 0.6 * p))

        self.add_hot(x0, y0, x1, y1, click=lambda: self.select_language(lang.id),
                     enter=lambda: self.anim.tween(0.18, hov, key=tag),
                     leave=lambda: self.anim.tween(0.25, lambda p: hov(1 - p), key=tag))
        self.targets[f"lang:{lang.id}"] = ((x0 + x1) / 2, (y0 + y1) / 2)
        return items

    def select_language(self, lang_id):
        if lang_id == self.lang.id:
            return
        self.lang = LANGUAGES[lang_id]
        self.progress["language"] = lang_id
        prog.lang_progress(self.progress, lang_id)
        self.save()
        self.recolor(lang_id)
        self.build_home(animate=True, only_path=True)

    # ---------------------------------------------------------------- panel
    def card(self, x0, y0, x1, y1, title=None, tags=("screen",)):
        t = self.t
        items = [round_rect(self.cv, x0, y0, x1, y1, 18, fill=t.card, outline=mix(t.card, t.border, 0.7),
                            width=1, tags=tags)]
        if title:
            items.append(self.text(x0 + 20, y0 + 18, "  ".join(title.split(" ")).replace("", " ").strip(),
                                   t.tiny, t.dim, tags=tags))
        return items

    def build_panel(self, x0, y0, x1, y1):
        cv, t = self.cv, self.t
        p = self.progress
        groups = []
        # level ring
        level = prog.level_for(p["xp"])
        into = p["xp"] % prog.XP_PER_LEVEL
        frac = into / prog.XP_PER_LEVEL
        c1 = self.card(x0, y0, x1, y0 + 176, "LEVEL")
        cx, cy, r = x0 + 78, y0 + 100, 46
        c1.append(cv.create_oval(cx - r, cy - r, cx + r, cy + r, outline=t.card2, width=11, tags=("screen",)))
        segs = []
        n = 36
        for i in range(n):
            segs.append(cv.create_arc(cx - r, cy - r, cx + r, cy + r, start=90, extent=0, style="arc",
                                      outline=mix(t.accent, t.accent2, i / n), width=11, tags=("screen",)))
        c1 += segs

        def sweep(q):
            total = 360 * frac * q
            for i, it in enumerate(segs):
                s = 360 / n * i
                ext = max(0.0, min(360 / n + 0.8, total - s))
                cv.itemconfigure(it, start=90 - s, extent=-ext if ext > 0.01 else 0)
                cv.itemconfigure(it, state="normal" if ext > 0.01 else "hidden")
        sweep(0)
        self.anim.tween(1.4, sweep, ease=ease_out_cubic, delay=0.35, key="scr:ring")
        c1.append(self.text(cx, cy - 6, str(level), t.h1, t.text, anchor="center"))
        c1.append(self.text(cx, cy + 22, "LEVEL", t.tiny, t.muted, anchor="center"))
        c1.append(self.text(x0 + 146, y0 + 76, f"{p['xp']:,} XP", t.h3, t.text, anchor="w"))
        c1.append(self.text(x0 + 146, y0 + 102, f"{prog.XP_PER_LEVEL - into} XP to", t.small, t.muted, anchor="w"))
        c1.append(self.text(x0 + 146, y0 + 122, f"level {level + 1}", t.small, t.muted, anchor="w"))
        groups.append(c1)

        # daily goal
        y = y0 + 192
        c2 = self.card(x0, y, x1, y + 104, "DAILY GOAL")
        lim = prog.DAILY_LESSON_LIMIT
        today = p["daily_lessons"] if p["last_date"] == date.today().isoformat() else 0
        sw = (x1 - x0 - 40 - (lim - 1) * 8) / lim
        for i in range(lim):
            sx = x0 + 20 + i * (sw + 8)
            done = i < today
            if done:
                c2 += gradient_round_rect(cv, sx, y + 46, sx + sw, y + 60, 7, t.accent, t.accent2, tags=("screen",),
                                          step=3)
            else:
                c2.append(round_rect(cv, sx, y + 46, sx + sw, y + 60, 7, fill=t.card2, outline="", tags=("screen",)))
        c2.append(self.text(x0 + 20, y + 80, f"{today} of {lim} lessons today", t.small, t.muted, anchor="w"))
        groups.append(c2)

        # runner
        y += 120
        runner = find_runner(self.lang)
        c3 = self.card(x0, y, x1, y + 96, "CODE RUNNER")
        col = t.success if runner else t.warn
        dot = cv.create_oval(x0 + 20, y + 47, x0 + 32, y + 59, fill=col, outline="", tags=("screen",))
        ring = cv.create_oval(x0 + 26, y + 53, x0 + 26, y + 53, outline=col, width=2, tags=("screen",))
        c3 += [dot, ring]
        msg = (f"Runs real {self.lang.name} code with {runner.label}" if runner
               else f"Reference-match mode. Install {self.lang.install_hint} to run real code")
        c3.append(self.text(x0 + 42, y + 53, msg, t.small, t.text, anchor="w", width=x1 - x0 - 60))

        def pulse(dt, tt):
            q = (tt * 0.8) % 1.0
            rr = 6 + 12 * q
            cv.coords(ring, x0 + 26 - rr, y + 53 - rr, x0 + 26 + rr, y + 53 + rr)
            cv.itemconfigure(ring, outline=mix(col, t.card, q))
        self.anim.ticker("scr:runner", pulse)
        groups.append(c3)

        # buttons
        y += 116
        cur = self.current_lesson_no()
        b = Button(self, x0, y, x1 - x0, 54, f"Continue lesson {cur}  ▶", lambda: self.open_lesson(cur),
                   name="btn:continue_home")
        groups.append(list(cv.find_withtag(b.tag)))
        b2 = Button(self, x0, y + 68, x1 - x0, 42, "Check for updates", self.check_updates, kind="ghost",
                    font=t.small_b)
        groups.append(list(cv.find_withtag(b2.tag)))
        groups.append([self.text((x0 + x1) / 2, y1 - 6, f"CodeStep v{VERSION}", t.small, t.dim, anchor="s")])
        return groups

    def current_lesson_no(self):
        lp = self.lp
        for i, lesson in enumerate(self.lessons, 1):
            if i in lp["unlocked"] and lp["completed_tasks"].get(str(i), 0) < len(lesson.tasks):
                return i
        return max(lp["unlocked"])

    # ---------------------------------------------------------------- path
    def build_path(self, x0, y0, x1, y1):
        cv, t = self.cv, self.t
        lessons, lp = self.lessons, self.lp
        groups = []
        total = sum(len(l.tasks) for l in lessons)
        done_all = sum(min(lp["completed_tasks"].get(str(i), 0), len(l.tasks)) for i, l in enumerate(lessons, 1))
        head = [self.text(x0 + 30, y0 + 8, self.lang.name, t.h1, t.text),
                self.text(x0 + 32, y0 + 54, f"{len(lessons)} lessons  ·  {total} tasks  ·  "
                                            f"{round(100 * done_all / total)}% complete", t.small, t.muted)]
        bx0, bx1 = x0 + 32, x1 - 30
        head.append(round_rect(cv, bx0, y0 + 80, bx1, y0 + 88, 4, fill=t.card2, outline="", tags=("screen",)))
        if done_all:
            head += gradient_round_rect(cv, bx0, y0 + 80, bx0 + max(10, (bx1 - bx0) * done_all / total), y0 + 88, 4,
                                        t.accent, t.accent2, tags=("screen",), step=3)
        groups.append(head)

        n = len(lessons)
        top, bottom = y0 + 150, y1 - 50
        mid = (x0 + x1) / 2
        amp = max(30, min(90, (x1 - x0) / 2 - 240))
        pts = []
        for i in range(n):
            y = top + (bottom - top) * i / max(1, n - 1)
            x = mid + amp * (-1 if i % 2 == 0 else 1)
            pts.append((x, y))
        flat = [c for p in pts for c in p]
        cur = self.current_lesson_no()
        track = cv.create_line(*flat, smooth=True, splinesteps=30, width=14, fill=mix(t.card2, t.accent, 0.08),
                               capstyle="round", tags=("screen",))
        path_items = [track]
        reach = cur if lp["completed_tasks"].get(str(cur), 0) else cur - 1
        reach = max(reach, 0)
        if reach >= 1:
            sub = [c for p in pts[: reach + 1] for c in p] if reach < n else flat
            if len(sub) >= 4:
                path_items.append(cv.create_line(*sub, smooth=True, splinesteps=30, width=14, fill=t.accent,
                                                 capstyle="round", tags=("screen",)))
                ants = cv.create_line(*sub, smooth=True, splinesteps=30, width=3, dash=(2, 14),
                                      fill=lighten(t.accent, 0.6), capstyle="round", tags=("screen",))
                path_items.append(ants)
                self.anim.ticker("scr:ants", lambda dt, tt: cv.itemconfigure(ants, dashoffset=int(-tt * 40) % 16))
        groups.append(path_items)

        for i, (lesson, (x, y)) in enumerate(zip(lessons, pts), 1):
            groups.append(self.path_node(i, lesson, x, y, cur, left=(x < mid)))
        return groups

    def path_node(self, i, lesson, x, y, cur, left):
        cv, t = self.cv, self.t
        lp = self.lp
        done = lp["completed_tasks"].get(str(i), 0)
        total = len(lesson.tasks)
        unlocked = i in lp["unlocked"]
        complete = done >= total
        is_cur = unlocked and not complete and i == cur
        tag = f"node{i}"
        tags = ("screen", tag)
        r = 34
        items = [cv.create_oval(x - r, y - r + 7, x + r, y + r + 7, fill="#05070f", outline="", tags=tags)]
        if unlocked:
            base = darken(t.accent, 0.35)
            items.append(cv.create_oval(x - r, y - r + 5, x + r, y + r + 5, fill=base, outline="", tags=tags))
            items.append(cv.create_oval(x - r, y - r, x + r, y + r, fill=t.accent if (complete or is_cur) else
                                        mix(t.accent, t.card2, 0.45), outline="", tags=tags))
            items.append(cv.create_oval(x - r + 9, y - r + 6, x + 2, y - 8, fill=mix(t.accent, "#ffffff", 0.35),
                                        outline="", tags=tags))
            ink = ink_on(t.accent)
            if complete:
                items.append(cv.create_line(x - 12, y + 1, x - 3, y + 10, x + 14, y - 9, fill=ink, width=6,
                                            capstyle="round", joinstyle="round", tags=tags))
            else:
                items.append(self.text(x, y + 1, str(i), t.h2, ink, anchor="center", tags=tags))
            if is_cur:
                rr = r + 9
                items.append(cv.create_oval(x - rr, y - rr, x + rr, y + rr, outline=t.card2, width=5, tags=tags))
                if done:
                    items.append(cv.create_arc(x - rr, y - rr, x + rr, y + rr, start=90, extent=-360 * done / total,
                                               style="arc", outline=t.accent2, width=5, tags=tags))
                pulse = cv.create_oval(x, y, x, y, outline=t.accent, width=3, tags=("screen",))
                cv.tag_lower(pulse, items[0])

                def pul(dt, tt, pulse=pulse):
                    q = (tt * 0.7) % 1.0
                    pr = r + 10 + 34 * ease_out_cubic(q)
                    cv.coords(pulse, x - pr, y - pr, x + pr, y + pr)
                    cv.itemconfigure(pulse, outline=mix(t.accent, t.bg, q), width=max(1, 4 * (1 - q)))
                self.anim.ticker(f"scr:pulse{i}", pul)
                items.append(pulse)
        else:
            items.append(cv.create_oval(x - r, y - r + 5, x + r, y + r + 5, fill="#10142a", outline="", tags=tags))
            items.append(cv.create_oval(x - r, y - r, x + r, y + r, fill="#1a2040", outline=t.border, width=1.5,
                                        tags=tags))
            items += self.icon("lock", x, y + 2, tags=tags)

        # label
        lx = x - r - 22 if left else x + r + 22
        anchor = "e" if left else "w"
        title_col = t.text if unlocked else t.dim
        items.append(self.text(lx, y - 10, lesson.title, t.h3, title_col, anchor=anchor, tags=("screen",)))
        sub = "Completed" if complete else (f"{done}/{total} tasks" if unlocked else "Locked")
        items.append(self.text(lx, y + 14, f"Lesson {i}  ·  {sub}", t.small,
                               t.accent if complete else t.muted, anchor=anchor, tags=("screen",)))
        if is_cur:
            label = "CONTINUE" if done else "START"
            pw = t.tiny.measure(label) + 22
            px = lx - pw if left else lx
            py = y + 30
            items += gradient_round_rect(cv, px, py, px + pw, py + 20, 10, t.accent, t.accent2, tags=("screen",),
                                         step=3)
            items.append(self.text(px + pw / 2, py + 10, label, t.tiny, ink_on(mix(t.accent, t.accent2, .5)),
                                   anchor="center"))

        st = {"s": 1.0}

        def hov(p):
            s = 1 + 0.1 * p
            cv.scale(tag, x, y, s / st["s"], s / st["s"])
            st["s"] = s

        def click():
            if unlocked:
                self.open_lesson(i)
            else:
                self.shake(tag, amp=8, dur=0.4)
                self.toast(f"Finish lesson {i - 1} to unlock this one", "warn")

        self.add_hot(x - r - 6, y - r - 6, x + r + 6, y + r + 6, click=click, circle=True,
                     enter=lambda: self.anim.tween(0.25, hov, ease=ease_out_back, key=tag),
                     leave=lambda: self.anim.tween(0.2, lambda p: hov(1 - p), key=tag))
        self.targets[f"node:{i}"] = (x, y)
        return items

    # ---------------------------------------------------------------- updates
    def check_updates(self):
        self.toast("Checking for updates…", "info", dur=2)
        box = []

        def work():
            try:
                import requests
                r = requests.get(RELEASES_API, timeout=10)
                r.raise_for_status()
                box.append(r.json())
            except Exception as e:  # noqa: BLE001
                box.append(e)

        threading.Thread(target=work, daemon=True).start()

        def poll():
            if not box:
                self.root.after(100, poll)
                return
            res = box[0]
            if isinstance(res, Exception):
                self.toast(f"Could not check for updates: {res}", "error")
                return
            latest = res.get("tag_name", "").lstrip("v")
            try:
                newer = _vt(latest) > _vt(VERSION)
            except ValueError:
                newer = False
            if newer:
                self.toast(f"Version {latest} is available! {res.get('html_url', '')}", "success", dur=6)
            else:
                self.toast(f"You're on the latest version ({VERSION})", "success")
        poll()

    # ================================================================ LESSON
    def open_lesson(self, n):
        if self.in_transition:
            return
        if n not in self.lp["unlocked"]:
            self.toast("Complete the previous lesson first!", "warn")
            return
        done = self.lp["completed_tasks"].get(str(n), 0)
        total = len(self.lessons[n - 1].tasks)
        self.lesson_no = n
        self.task_no = 1 if done >= total else done + 1
        self.curtain(lambda: self.build_lesson())

    def build_lesson(self, animate=True, code=None, only_task=False):
        self.clear_screen()
        self.screen = "lesson"
        cv, t = self.cv, self.t
        W, H = self.W, self.H
        lesson = self.lessons[self.lesson_no - 1]
        task = self.task
        total = len(lesson.tasks)
        done = self.lp["completed_tasks"].get(str(self.lesson_no), 0)

        # ---- top bar
        top_items = []
        back = Button(self, 26, 22, 44, 44, "←", self.go_home, kind="ghost", font=t.h3, name="btn:back")
        top_items += list(cv.find_withtag(back.tag))
        a, b, badge = LANG_STYLE[self.lang.id]
        top_items += gradient_round_rect(cv, 84, 26, 120, 62, 9, a, b, tags=("screen",), step=3)
        top_items.append(self.text(102, 44, badge, t.tiny, ink_on(mix(a, b, .5)), anchor="center"))
        top_items.append(self.text(132, 34, f"{self.lang.name}  ·  Lesson {self.lesson_no}", t.small, t.muted,
                                   anchor="w"))
        top_items.append(self.text(132, 55, lesson.title, t.h3, t.text, anchor="w"))
        seg_w, gap = 30, 6
        sx0 = max(132 + max(t.h3.measure(lesson.title), 160) + 40, W / 2 - (total * (seg_w + gap)) / 2)
        self.segments = []
        for i in range(total):
            x = sx0 + i * (seg_w + gap)
            if i < done or (i + 1) < self.task_no:
                items = gradient_round_rect(cv, x, 38, x + seg_w, 50, 6, mix(t.accent, t.accent2, i / total),
                                            mix(t.accent, t.accent2, (i + 1) / total), tags=("screen",), step=3)
            else:
                items = [round_rect(cv, x, 38, x + seg_w, 50, 6, fill=t.card2, outline="", tags=("screen",))]
            self.segments.append((x, items))
            top_items += items
        cur_x = sx0 + (self.task_no - 1) * (seg_w + gap)
        cur_ring = round_rect(cv, cur_x - 3, 35, cur_x + seg_w + 3, 53, 8, fill="", outline=t.accent, width=2,
                              tags=("screen",))
        top_items.append(cur_ring)
        self.anim.ticker("scr:seg", lambda dt, tt: cv.itemconfigure(
            cur_ring, outline=mix(t.accent, t.bg, (math.sin(tt * 4) + 1) / 2 * 0.7)))
        # xp chip
        xp_val = f"{self.progress['xp']:,} XP"
        cw = 64 + t.body_b.measure("99,999 XP")
        top_items.append(round_rect(cv, W - 30 - cw, 24, W - 30, 64, 20, fill=t.card, outline=t.border, width=1,
                                    tags=("screen",)))
        top_items += self.icon("xp", W - 30 - cw + 24, 44)
        self.xp_label = self.text(W - 30 - cw + 42, 44, xp_val, t.body_b, t.text, anchor="w")
        top_items.append(self.xp_label)

        # ---- layout
        top, bottom = 88, H - 104
        lw = int(W * 0.36)
        task_items = self.build_task_card(28, top, lw, bottom, task, total)
        ex0, ex1 = lw + 18, W - 28
        eh = int((bottom - top) * 0.64)
        ed_items = self.build_editor_card(ex0, top, ex1, top + eh, code)
        con_items = self.build_console_card(ex0, top + eh + 14, ex1, bottom)

        # ---- bottom bar
        by = H - 80
        bb = []
        sol = Button(self, 28, by + 4, 168, 46, "Show solution", self.show_solution, kind="ghost", font=t.small_b,
                     name="btn:solution")
        rst = Button(self, 206, by + 4, 110, 46, "Reset", self.reset_code, kind="ghost", font=t.small_b)
        self.check_btn = Button(self, W - 28 - 210, by, 210, 54, "Check  ▶", self.run_check, name="btn:check")
        hint = self.text(W - 28 - 230, by + 27, "Ctrl + Enter", t.small, t.dim, anchor="e")
        for btn in (sol, rst, self.check_btn):
            bb += list(cv.find_withtag(btn.tag))
        bb.append(hint)

        if animate:
            if not only_task:
                self.appear(top_items, 0.05, dy=-12)
                self.appear(bb, 0.25, dy=16)
                self.appear(ed_items, 0.12, dx=30, dy=0)
                self.appear(con_items, 0.2, dx=30, dy=0)
            self.appear(task_items, 0.08, dx=-30, dy=0)
        self.typewriter()
        self.root.after(50, lambda: self.editor.text.focus_set())

    def build_task_card(self, x0, y0, x1, y1, task, total):
        cv, t = self.cv, self.t
        items = self.card(x0, y0, x1, y1)
        pad = 26
        cw = x1 - x0 - 2 * pad
        label = f"TASK {self.task_no} / {total}"
        pw = t.tiny.measure(label) + 24
        items.append(round_rect(cv, x0 + pad, y0 + 24, x0 + pad + pw, y0 + 48, 12, fill=mix(t.card, t.accent, 0.2),
                                outline="", tags=("screen",)))
        items.append(self.text(x0 + pad + pw / 2, y0 + 36, label, t.tiny, lighten(t.accent, 0.35), anchor="center"))
        title = self.text(x0 + pad, y0 + 64, task.title, t.h2, t.text, width=cw)
        items.append(title)
        ty = cv.bbox(title)[3] + 14
        prompt = self.text(x0 + pad, ty, task.prompt, t.body, mix(t.text, t.muted, 0.25), width=cw)
        items.append(prompt)
        py = cv.bbox(prompt)[3] + 22
        self._prompt = (prompt, task.prompt)
        cv.itemconfigure(prompt, text="")

        items.append(self.text(x0 + pad, py, "E X P E C T E D   O U T P U T", t.tiny, t.dim))
        lines = task.expected.split("\n")
        shown = lines[:8] + (["…"] if len(lines) > 8 else [])
        lh = t.mono_small.metrics("linespace") + 2
        bh = len(shown) * lh + 24
        items.append(round_rect(cv, x0 + pad, py + 22, x1 - pad, py + 22 + bh, 12, fill=t.editor_bg,
                                outline=mix(t.editor_bg, t.border, 0.6), tags=("screen",)))
        for k, ln in enumerate(shown):
            items.append(self.text(x0 + pad + 16, py + 34 + k * lh, ln, t.mono_small, "#7ee7b8"))
        ry = py + 22 + bh + 22
        xp_txt = f"+{task.xp} XP"
        rw = t.small_b.measure(xp_txt) + 46
        items.append(round_rect(cv, x0 + pad, ry, x0 + pad + rw, ry + 32, 16, fill=mix(t.card, "#ffd166", 0.12),
                                outline=mix(t.card, "#ffd166", 0.4), tags=("screen",)))
        items += self.icon("xp", x0 + pad + 18, ry + 16)
        items.append(self.text(x0 + pad + 32, ry + 16, xp_txt, t.small_b, "#ffd166", anchor="w"))
        if task.required:
            uses = "Use: " + ", ".join(task.required)
            items.append(self.text(x0 + pad + rw + 14, ry + 16, uses, t.small, t.muted, anchor="w",
                                   width=x1 - pad - (x0 + pad + rw + 14)))
        runner = find_runner(self.lang)
        foot = (f"▸ Your code is compiled & run with {runner.label}" if runner
                else f"▸ No {self.lang.name} toolchain: your code is compared with the solution")
        items.append(self.text(x0 + pad, y1 - 24, foot, t.small, t.dim, anchor="sw", width=cw))
        return items

    def typewriter(self):
        it, full = self._prompt
        n = len(full)
        self.anim.tween(min(1.2, 0.015 * n + 0.2), lambda p: self.cv.itemconfigure(it, text=full[: int(n * p)]),
                        ease=linear, key="scr:type", delay=0.25)

    def build_editor_card(self, x0, y0, x1, y1, code=None):
        cv, t = self.cv, self.t
        tags = ("screen", "edcard")
        items = [round_rect(cv, x0, y0, x1, y1, 16, fill=t.editor_bg, outline=mix(t.editor_bg, t.border, 0.8),
                            width=1, tags=tags)]
        for k, c in enumerate(("#ff5f57", "#febc2e", "#28c840")):
            items.append(cv.create_oval(x0 + 18 + k * 18, y0 + 15, x0 + 30 + k * 18, y0 + 27, fill=c, outline="",
                                        tags=tags))
        fname = ("Main.java" if self.lang.id == "java" else "main" + self.lang.ext)
        fx = x0 + 88
        items.append(self.text(fx, y0 + 21, fname, t.mono_small, t.text, anchor="w", tags=tags))
        items.append(cv.create_line(fx, y0 + 40, fx + t.mono_small.measure(fname), y0 + 40, fill=t.accent, width=2,
                                    tags=tags))
        items.append(self.text(x1 - 18, y0 + 21, self.lang.name.upper(), t.tiny, t.dim, anchor="e", tags=tags))
        items.append(cv.create_line(x0 + 1, y0 + 41, x1 - 1, y0 + 41, fill=mix(t.editor_bg, t.border, 0.5),
                                    tags=tags))
        self.editor = CodeEditor(self.root, t, self.lang, on_submit=self.run_check)
        self.editor.set(code if code is not None else self.task.starter)
        self.editor.text.bind("<Key>", lambda e: self.dismiss_banner(fail_only=True), add="+")
        self.ed_box = (x0 + 2, y0 + 43, x1 - x0 - 4, y1 - y0 - 52)
        items.append(self.embed(self.editor, *self.ed_box, tags=tags))
        return items

    def build_console_card(self, x0, y0, x1, y1):
        cv, t = self.cv, self.t
        tags = ("screen", "concard")
        items = [round_rect(cv, x0, y0, x1, y1, 16, fill=t.editor_bg, outline=mix(t.editor_bg, t.border, 0.8),
                            width=1, tags=tags)]
        items.append(self.text(x0 + 18, y0 + 20, "▸  O U T P U T", t.tiny, t.dim, anchor="w", tags=tags))
        self.status_dot = cv.create_oval(x1 - 98, y0 + 14, x1 - 86, y0 + 26, fill=t.dim, outline="", tags=tags)
        self.status_txt = self.text(x1 - 80, y0 + 20, "ready", t.small_b, t.muted, anchor="w", tags=tags)
        items += [self.status_dot, self.status_txt]
        con = tk.Text(self.root, bd=0, highlightthickness=0, font=t.mono_small, bg=t.editor_bg, fg="#b8ffd9",
                      padx=16, pady=6, wrap="word", state="disabled", cursor="arrow", spacing1=2)
        con.tag_configure("err", foreground=t.error)
        con.tag_configure("muted", foreground=t.muted)
        con.tag_configure("ok", foreground=t.success)
        self.console = con
        self.con_box = (x0 + 2, y0 + 38, x1 - x0 - 4, y1 - y0 - 46)
        items.append(self.embed(con, *self.con_box, tags=tags))
        self.set_console([("Press Check to run your code.", "muted")])
        return items

    def set_console(self, parts):
        c = self.console
        c.configure(state="normal")
        c.delete("1.0", "end")
        for s, tag in parts:
            c.insert("end", s, tag)
        c.configure(state="disabled")
        self._console_parts = parts

    def set_status(self, state):
        t = self.t
        col, label = {"ready": (t.dim, "ready"), "running": (t.warn, "running"), "passed": (t.success, "passed"),
                      "failed": (t.error, "failed")}[state]
        self.cv.itemconfigure(self.status_dot, fill=col)
        self.cv.itemconfigure(self.status_txt, text=label, fill=col)
        self.anim.cancel("scr:status")
        if state == "running":
            self.anim.ticker("scr:status", lambda dt, tt: self.cv.itemconfigure(
                self.status_dot, fill=mix(col, t.editor_bg, (math.sin(tt * 9) + 1) / 2 * 0.8)))

    def reset_code(self):
        self.editor.set(self.task.starter)
        self.dismiss_banner()
        self.editor.text.focus_set()

    def show_solution(self):
        self.dismiss_banner()
        self.editor.set(self.task.answer)
        self.toast("Solution loaded. Read it, then press Check.", "info")
        self.editor.text.focus_set()

    # ---------------------------------------------------------------- checking
    def run_check(self):
        if self.screen != "lesson" or self.check_btn.busy or self.in_transition or self.banner_state == "ok":
            return
        code = self.editor.get()
        if not code.strip() or code.strip() == self.task.starter.strip():
            self.toast("Write some code first!", "warn")
            self.shake("edcard", amp=8)
            return
        self.dismiss_banner()
        self.check_btn.spinner(True, "Running…")
        self.set_status("running")
        self.set_console([("Running…", "muted")])
        lang, task = self.lang, self.task
        box = []

        def work():
            try:
                box.append(check(lang, task, code))
            except Exception as e:  # noqa: BLE001
                box.append(CheckResult(False, f"Internal error while checking: {e}"))

        threading.Thread(target=work, daemon=True).start()

        def poll():
            if self.screen != "lesson":
                return
            if box:
                self.on_checked(box[0])
            else:
                self.root.after(40, poll)
        self.root.after(40, poll)

    def on_checked(self, res):
        self.check_btn.spinner(False, "Check  ▶")
        if not res.ok:
            self.set_status("failed")
            parts = []
            if res.output:
                out, _, err = res.output.partition("Error:\n")
                if out.strip():
                    parts.append((out.rstrip() + "\n", ""))
                if err:
                    parts.append(("Error:\n" + err, "err"))
            self.set_console(parts or [("(no output)", "muted")])
            self.shake("edcard")
            msg = res.message
            if msg.startswith("Your code didn't run"):
                lines = [ln.strip() for ln in msg.splitlines() if ln.strip()]
                msg = "Your code didn't run: " + (lines[-1] if len(lines) > 1 else "") + "  (details in Output)"
            self.banner(False, msg)
            return
        lesson = self.lessons[self.lesson_no - 1]
        old_xp = self.progress["xp"]
        accepted, leveled, why = prog.record_task(self.progress, self.lang.id, self.lesson_no, self.task_no, res.xp,
                                                  len(lesson.tasks), len(self.lessons))
        self.set_status("passed")
        self.set_console([(res.output, "ok" if not res.simulated else "")])
        if not accepted:
            self.toast(why, "warn", dur=5)
            return
        gained = self.progress["xp"] - old_xp
        # celebrate
        self.freeze_editor()
        bx, by = self.targets["btn:check"]
        Confetti(self, bx, by - 20, n=110)
        Confetti(self, self.W * 0.2, self.H - 110, n=50, spread=math.pi * 0.6, power=(400, 760))
        if gained:
            self.float_text(bx, by - 40, f"+{gained} XP", "#ffd166", self.t.h2)
            new = self.progress["xp"]
            self.anim.tween(0.9, lambda p: self.cv.itemconfigure(self.xp_label, text=f"{int(lerp(old_xp, new, p)):,} XP"),
                            key="scr:xpcount")
        x, items = self.segments[self.task_no - 1]
        for it in items:
            self.cv.itemconfigure(it, fill=self.t.accent)
        Burst(self, x + 15, 44, self.t.accent, radius=40, dur=0.6)
        msg = random.choice(PRAISE)
        self.banner(True, f"Output: {res.output.splitlines()[0][:60] if res.output else ''}"
                    + (" …" if res.output.count("\n") else ""), title=msg)
        if leveled:
            self.root.after(700, lambda: self.level_up(self.progress["level"]))

    def freeze_editor(self):
        """Replace the Text widgets with a canvas drawing so effects can fly over them."""
        cv, t = self.cv, self.t
        x, y, w, h = self.ed_box
        cv.itemconfigure(self._win_items[self.editor], state="hidden")
        code = self.editor.get()
        lh = t.mono.metrics("linespace") + 4
        cw = t.mono.measure("0")
        for i, line in enumerate(syntax.colored_lines(code, self.lang.id)):
            yy = y + 14 + i * lh
            if yy > y + h - lh:
                break
            self.text(x + 10 + cw * (3 - len(str(i + 1))), yy, str(i + 1), t.mono, t.muted,
                      tags=("screen", "frozen", "edcard"))
            col = 0
            for s, c in line:
                self.text(x + 28 + 3 * cw + col * cw, yy, s, t.mono, c, tags=("screen", "frozen", "edcard"))
                col += len(s)
        cx, cy, cw_, ch_ = self.con_box
        cv.itemconfigure(self._win_items[self.console], state="hidden")
        out = "".join(s for s, _ in self._console_parts)
        self.text(cx + 16, cy + 8, out, t.mono_small, "#b8ffd9", width=cw_ - 30, tags=("screen", "frozen"))

    # ---------------------------------------------------------------- banner
    def banner(self, ok, message, title=None):
        cv, t = self.cv, self.t
        self.dismiss_banner(instant=True)
        W, H = self.W, self.H
        bh = 104
        col = t.success if ok else t.error
        tags = ("screen", "banner")
        y0 = H - bh
        cv.create_rectangle(0, y0, W, H, fill=mix(t.bg, col, 0.13), outline="", tags=tags)
        cv.create_line(0, y0, W, y0, fill=mix(t.bg, col, 0.6), width=2, tags=tags)
        cv.create_oval(32, y0 + 24, 88, y0 + 80, fill=col, outline="", tags=tags)
        if ok:
            cv.create_line(47, y0 + 52, 56, y0 + 61, 74, y0 + 42, fill="#0a0d1a", width=6, capstyle="round",
                           joinstyle="round", tags=tags)
        else:
            cv.create_line(49, y0 + 41, 71, y0 + 63, fill="#0a0d1a", width=6, capstyle="round", tags=tags)
            cv.create_line(71, y0 + 41, 49, y0 + 63, fill="#0a0d1a", width=6, capstyle="round", tags=tags)
        self.text(108, y0 + 22, title or ("Not quite…" if not ok else "Correct!"), t.h2, col, tags=tags)
        msg = message.replace("\n\n", "  ").replace("\n", " ")
        if len(msg) > 260:
            msg = msg[:257] + "…"
        self.text(108, y0 + 56, msg, t.small, mix(t.text, col, 0.25), width=W - 108 - 330, tags=tags)
        layer = self.hot_layers[-1]
        first_hot = len(layer)
        self.add_hot(0, y0, W, H, cursor="")
        if ok:
            last = self.task_no >= len(self.lessons[self.lesson_no - 1].tasks)
            b = Button(self, W - 28 - 210, y0 + 25, 210, 54, "Finish lesson  ▶" if last else "Continue  ▶",
                       self.next_task, kind="success", tags=tags, name="btn:next")
        else:
            b = Button(self, W - 28 - 170, y0 + 25, 170, 54, "Try again", lambda: self.dismiss_banner(),
                       kind="danger", tags=tags, name="btn:retry")
            Button(self, W - 28 - 170 - 186, y0 + 25, 170, 54, "Show solution", self.show_solution, kind="ghost",
                   font=t.small_b, tags=tags, name="btn:solution2")
        self.banner_state = "ok" if ok else "fail"
        self._banner_hot = layer[first_hot:]
        st = {"y": bh}
        cv.move("banner", 0, bh)

        def slide(p):
            y = bh * (1 - p)
            cv.move("banner", 0, y - st["y"])
            st["y"] = y
            cv.tag_raise("banner")
            cv.tag_raise("fxtop")
        self.anim.tween(0.45, slide, ease=ease_out_back, key="scr:banner")

    def dismiss_banner(self, instant=False, fail_only=False):
        if not self.banner_state or (fail_only and self.banner_state != "fail"):
            return
        self.banner_state = None
        layer = self.hot_layers[-1]
        for h in getattr(self, "_banner_hot", []):
            if h in layer:
                layer.remove(h)
        self._set_hover(None)
        if instant:
            self.cv.delete("banner")
            return
        st = {"y": 0.0}
        self.cv.addtag_withtag("banner_leaving", "banner")
        self.cv.dtag("banner_leaving", "banner")

        def slide2(p):
            y = 110 * p
            self.cv.move("banner_leaving", 0, y - st["y"])
            st["y"] = y
        self.anim.tween(0.25, slide2, ease=ease_in_out_cubic, done=lambda: self.cv.delete("banner_leaving"))

    def next_task(self):
        lesson = self.lessons[self.lesson_no - 1]
        if self.task_no < len(lesson.tasks):
            self.task_no += 1
            self.build_lesson(animate=True, only_task=True)
        else:
            self.curtain(lambda: self.build_complete())

    def _on_return(self, e):
        if self.screen == "lesson" and self.banner_state == "ok":
            self.next_task()
            return "break"
        if self.screen == "complete":
            self.finish_complete()
        return None

    # ---------------------------------------------------------------- level up
    def level_up(self, level):
        if self.screen != "lesson":
            return
        cv, t = self.cv, self.t
        W, H = self.W, self.H
        self.push_layer()
        tags = ("screen", "lvl")
        cx, cy = W / 2, H / 2 - 30
        w, h = 420, 250
        glow(cv, cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2, 26, t.accent2, t.bg, layers=6, spread=4,
             strength=0.6, tags=tags)
        round_rect(cv, cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2, 26, fill=t.card, outline=t.accent2, width=2,
                   tags=tags)
        self.text(cx, cy - 78, "L E V E L   U P !", t.h3, t.accent2, anchor="center", tags=tags)
        num = self.text(cx, cy + 4, str(level), (t.h1.actual("family"), -10, "bold"), t.text, anchor="center",
                        tags=tags)
        self.text(cx, cy + 84, "Keep going — you're getting good at this.", t.small, t.muted, anchor="center",
                  tags=tags)
        fam = t.h1.actual("family")
        self.anim.tween(1.0, lambda p: cv.itemconfigure(num, font=(fam, -max(8, int(96 * p)), "bold")),
                        ease=ease_out_elastic)
        Burst(self, cx, cy + 4, t.accent2, radius=170, dur=1.0)
        Confetti(self, cx, cy + 40, n=90, spread=math.pi * 1.6, power=(300, 700))

        def close():
            if not cv.find_withtag("lvl"):
                return
            cv.delete("lvl")
            self.pop_layer()
        self.add_hot(0, 0, W, H, click=close, cursor="hand2")
        self.root.after(2600, close)

    # ---------------------------------------------------------------- complete
    def build_complete(self, animate=True):
        self.clear_screen()
        self.screen = "complete"
        cv, t = self.cv, self.t
        W, H = self.W, self.H
        lesson = self.lessons[self.lesson_no - 1]
        cx = W / 2
        cy = H / 2 - 130
        trophy = []
        gold, gold2 = "#ffd166", "#ff9f1c"
        tags = ("screen", "trophy")
        trophy += glow(cv, cx - 70, cy - 70, cx + 70, cy + 70, 70, gold, t.bg, layers=6, spread=6, strength=0.35,
                       tags=tags)
        trophy.append(cv.create_arc(cx - 78, cy - 52, cx - 22, cy + 8, start=90, extent=180, style="arc",
                                    outline=gold2, width=9, tags=tags))
        trophy.append(cv.create_arc(cx + 22, cy - 52, cx + 78, cy + 8, start=270, extent=180, style="arc",
                                    outline=gold2, width=9, tags=tags))
        trophy.append(cv.create_polygon(cx - 52, cy - 60, cx + 52, cy - 60, cx + 46, cy - 6, cx + 20, cy + 26,
                                        cx - 20, cy + 26, cx - 46, cy - 6, smooth=True, fill=gold, outline="",
                                        tags=tags))
        trophy.append(cv.create_polygon(cx - 30, cy - 52, cx - 8, cy - 52, cx - 16, cy - 4, cx - 32, cy - 14,
                                        smooth=True, fill=lighten(gold, 0.5), outline="", tags=tags))
        trophy.append(cv.create_rectangle(cx - 9, cy + 24, cx + 9, cy + 46, fill=gold2, outline="", tags=tags))
        trophy.append(round_rect(cv, cx - 42, cy + 44, cx + 42, cy + 62, 6, fill=gold2, outline="", tags=tags))
        trophy.append(self.text(cx, cy - 24, "★", t.h2, "#ffffff", anchor="center", tags=tags))
        stars = []
        for i in range(9):
            a = i / 9 * math.tau
            rx, ry = cx + math.cos(a) * 130, cy + math.sin(a) * 95
            stars.append((self.text(rx, ry, "✦", t.h3, gold, anchor="center"), random.uniform(0, 6)))

        st = {"y": 0.0}

        def bob(dt, tt):
            y = math.sin(tt * 2.2) * 6
            cv.move("trophy", 0, y - st["y"])
            st["y"] = y
            for it, ph in stars:
                k = (math.sin(tt * 3 + ph) + 1) / 2
                cv.itemconfigure(it, fill=mix(t.bg, gold, k))
        self.anim.ticker("scr:trophy", bob)

        txt = [self.text(cx, cy + 112, "Lesson complete!", t.h1, t.text, anchor="center"),
               self.text(cx, cy + 152, f"{self.lang.name}  ·  {lesson.title}", t.body, t.muted, anchor="center")]
        xp = sum(tk_.xp for tk_ in lesson.tasks)
        tiles = []
        tw_, th_ = 180, 104
        stats = [("XP EARNED", xp, "#ffd166"), ("TASKS", f"{len(lesson.tasks)}/{len(lesson.tasks)}", t.success),
                 ("STREAK", f"{self.progress['streak']} days", "#ff7a3d")]
        x = cx - (3 * tw_ + 2 * 18) / 2
        for label, val, col in stats:
            g = self.card(x, cy + 190, x + tw_, cy + 190 + th_)
            g.append(self.text(x + tw_ / 2, cy + 216, "  ".join(label.split()).replace("", " ").strip(), t.tiny,
                               t.dim, anchor="center"))
            num = self.text(x + tw_ / 2, cy + 256, str(val), t.h2, col, anchor="center")
            g.append(num)
            if isinstance(val, int):
                self.anim.tween(1.2, lambda p, num=num, val=val: cv.itemconfigure(num, text=f"+{int(val * p)}"),
                                delay=0.5, key=f"scr:count{label}")
            tiles.append(g)
            x += tw_ + 18
        btn = Button(self, cx - 130, cy + 330, 260, 58, "Continue  ▶", self.finish_complete, name="btn:finish")
        if animate:
            self.appear(trophy, 0.1, dy=-40, dur=0.7)
            self.appear(txt, 0.3, dy=20)
            for i, g in enumerate(tiles):
                self.appear(g, 0.45 + i * 0.1, dy=30)
            self.appear(list(cv.find_withtag(btn.tag)), 0.8, dy=20)
            self.root.after(500, lambda: Confetti(self, 0, 0, n=160, rain=True, width=W))
            self.root.after(1700, lambda: self.screen == "complete" and Confetti(self, 0, 0, n=100, rain=True,
                                                                                     width=W))
        nxt = self.lesson_no + 1
        if nxt <= len(self.lessons):
            self.pending_unlock = nxt

    def finish_complete(self):
        if self.in_transition:
            return
        self.curtain(lambda: self.build_home())


def _vt(v):
    return tuple(int(p) for p in v.split("-")[0].split("."))
