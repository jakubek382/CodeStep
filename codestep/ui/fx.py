"""Animation + drawing toolkit on top of a plain Tk Canvas.

Tk has no alpha, no shadows and no animation system, so this module fakes
them: colours are blended against the background, glows are stacks of
blended outlines, and a single frame clock drives every tween/particle.
"""
from __future__ import annotations

import math
import random
import time


# ------------------------------------------------------------------ colour
def hex_to_rgb(h: str):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def rgb_to_hex(r, g, b) -> str:
    return "#%02x%02x%02x" % (max(0, min(255, int(r))), max(0, min(255, int(g))), max(0, min(255, int(b))))


def mix(a: str, b: str, t: float) -> str:
    """Blend colour a -> b by t (0 = a, 1 = b)."""
    ra, ga, ba = hex_to_rgb(a)
    rb, gb, bb = hex_to_rgb(b)
    return rgb_to_hex(ra + (rb - ra) * t, ga + (gb - ga) * t, ba + (bb - ba) * t)


def lighten(c: str, t: float) -> str:
    return mix(c, "#ffffff", t)


def darken(c: str, t: float) -> str:
    return mix(c, "#000000", t)


# ------------------------------------------------------------------ easing
def linear(t):
    return t


def ease_out_cubic(t):
    return 1 - (1 - t) ** 3


def ease_in_out_cubic(t):
    return 4 * t ** 3 if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2


def ease_out_back(t, s=1.70158):
    t -= 1
    return 1 + (s + 1) * t ** 3 + s * t ** 2


def ease_out_elastic(t):
    if t in (0, 1):
        return t
    return 2 ** (-10 * t) * math.sin((t * 10 - 0.75) * (2 * math.pi) / 3) + 1


def lerp(a, b, t):
    return a + (b - a) * t


# ------------------------------------------------------------------ clock
class Animator:
    """One `after` loop drives every tween and ticker (~60 fps)."""

    FRAME_MS = 16

    def __init__(self, widget):
        self.w = widget
        self.tweens = []      # [start, dur, fn, ease, done, key]
        self.tickers = {}     # key -> fn(dt, t) ; return False to stop
        self._job = None
        self._last = time.perf_counter()
        self.t = 0.0

    def tween(self, dur, fn, ease=ease_out_cubic, done=None, delay=0.0, key=None):
        now = time.perf_counter()
        if key is not None:
            self.cancel(key)
        self.tweens.append([now + delay, max(dur, 1e-6), fn, ease, done, key])
        if delay <= 0:
            fn(ease(0.0))
        self._kick()

    def ticker(self, key, fn):
        self.tickers[key] = fn
        self._kick()

    def cancel(self, key):
        self.tweens = [tw for tw in self.tweens if tw[5] != key]
        self.tickers.pop(key, None)

    def cancel_prefix(self, prefix):
        self.tweens = [tw for tw in self.tweens if not (isinstance(tw[5], str) and tw[5].startswith(prefix))]
        for k in [k for k in self.tickers if k.startswith(prefix)]:
            del self.tickers[k]

    def _kick(self):
        if self._job is None:
            self._last = time.perf_counter()
            self._job = self.w.after(self.FRAME_MS, self._frame)

    def _frame(self):
        self._job = None
        now = time.perf_counter()
        dt = min(now - self._last, 0.05)
        self._last = now
        self.t += dt
        finished = []
        for tw in list(self.tweens):
            start, dur, fn, ease, done, _ = tw
            if now < start:
                continue
            p = min(1.0, (now - start) / dur)
            try:
                fn(ease(p))
            except Exception:  # noqa: BLE001 - a dead canvas item must not kill the clock
                p = 1.0
                done = None
            if p >= 1.0:
                finished.append(tw)
                if done:
                    try:
                        done()
                    except Exception:  # noqa: BLE001
                        pass
        for tw in finished:
            if tw in self.tweens:
                self.tweens.remove(tw)
        for key, fn in list(self.tickers.items()):
            try:
                keep = fn(dt, self.t)
            except Exception:  # noqa: BLE001
                keep = False
            if keep is False:
                self.tickers.pop(key, None)
        if self.tweens or self.tickers:
            self._job = self.w.after(self.FRAME_MS, self._frame)


# ------------------------------------------------------------------ shapes
def round_rect_points(x1, y1, x2, y2, r):
    r = max(0, min(r, (x2 - x1) / 2, (y2 - y1) / 2))
    return [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
            x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]


def round_rect(cv, x1, y1, x2, y2, r, **kw):
    return cv.create_polygon(round_rect_points(x1, y1, x2, y2, r), smooth=True, **kw)


def set_round_rect(cv, item, x1, y1, x2, y2, r):
    cv.coords(item, *round_rect_points(x1, y1, x2, y2, r))


def glow(cv, x1, y1, x2, y2, r, color, bg, layers=4, spread=3, strength=0.55, tags=()):
    """Fake outer glow: blended outlines growing outwards."""
    items = []
    for i in range(layers, 0, -1):
        k = i / layers
        c = mix(color, bg, 1 - strength * (1 - k) ** 1.6 - 0.12)
        g = i * spread
        items.append(round_rect(cv, x1 - g, y1 - g, x2 + g, y2 + g, r + g, outline=c, fill="",
                                width=spread, tags=tags))
    return items


def gradient_round_rect(cv, x1, y1, x2, y2, r, c1, c2, tags=(), step=1):
    """Horizontal gradient inside a rounded rectangle (vertical strips)."""
    items = []
    w = x2 - x1
    h = y2 - y1
    r = min(r, w / 2, h / 2)
    x = x1
    while x < x2:
        dx = x + step / 2 - x1
        inset = 0.0
        if dx < r:
            inset = r - math.sqrt(max(0.0, r * r - (r - dx) ** 2))
        elif dx > w - r:
            d = dx - (w - r)
            inset = r - math.sqrt(max(0.0, r * r - d * d))
        col = mix(c1, c2, (x - x1) / max(1, w))
        items.append(cv.create_rectangle(x, y1 + inset, min(x + step, x2), y2 - inset,
                                         fill=col, outline="", tags=tags))
        x += step
    return items


def vertical_gradient(cv, x1, y1, x2, y2, c1, c2, tags=(), step=3):
    items = []
    h = max(1, y2 - y1)
    y = y1
    while y < y2:
        items.append(cv.create_rectangle(x1, y, x2, y + step, fill=mix(c1, c2, (y - y1) / h),
                                         outline="", tags=tags))
        y += step
    return items


# ------------------------------------------------------------------ particles
class Confetti:
    COLORS = ("#ff5c8a", "#ffd166", "#06d6a0", "#4cc9f0", "#b388ff", "#ff9f43", "#ffffff")

    def __init__(self, app, x, y, n=90, spread=math.pi * 0.9, power=(380, 820), colors=None,
                 rain=False, width=None):
        self.app = app
        self.cv = app.cv
        self.parts = []
        colors = colors or self.COLORS
        tag = f"confetti{id(self)}"
        self.tag = tag
        for _ in range(n):
            if rain:
                px, py = random.uniform(0, width), random.uniform(-300, -10)
                vx, vy = random.uniform(-60, 60), random.uniform(60, 220)
            else:
                a = -math.pi / 2 + random.uniform(-spread / 2, spread / 2)
                v = random.uniform(*power)
                px, py = x, y
                vx, vy = math.cos(a) * v, math.sin(a) * v
            size = random.uniform(5, 11)
            col = random.choice(colors)
            shape = random.random()
            if shape < 0.45:
                item = self.cv.create_polygon(0, 0, 0, 0, 0, 0, 0, 0, fill=col, outline="", tags=(tag, "fxtop"))
            elif shape < 0.8:
                item = self.cv.create_oval(0, 0, 0, 0, fill=col, outline="", tags=(tag, "fxtop"))
            else:
                item = self.cv.create_line(0, 0, 0, 0, fill=col, width=3, tags=(tag, "fxtop"),
                                           capstyle="round")
            self.parts.append({"i": item, "x": px, "y": py, "vx": vx, "vy": vy, "s": size,
                               "rot": random.uniform(0, math.tau), "vr": random.uniform(-9, 9),
                               "life": random.uniform(2.2, 3.4), "kind": shape})
        app.anim.ticker(tag, self._step)

    def _step(self, dt, _t):
        alive = 0
        H = self.cv.winfo_height() + 40
        for p in self.parts:
            if p["life"] <= 0:
                continue
            p["vy"] += 900 * dt
            p["vx"] *= (1 - 1.6 * dt)
            p["vy"] = min(p["vy"], 420)
            p["x"] += p["vx"] * dt + math.sin(p["rot"]) * 0.6
            p["y"] += p["vy"] * dt
            p["rot"] += p["vr"] * dt
            p["life"] -= dt
            if p["y"] > H or p["life"] <= 0:
                p["life"] = 0
                self.cv.delete(p["i"])
                continue
            alive += 1
            s = p["s"]
            flip = abs(math.cos(p["rot"])) * s
            x, y = p["x"], p["y"]
            if p["kind"] < 0.45:
                c, sn = math.cos(p["rot"]), math.sin(p["rot"])
                pts = []
                for dx, dy in ((-s, -flip / 2), (s, -flip / 2), (s, flip / 2), (-s, flip / 2)):
                    pts += [x + dx * c - dy * sn, y + dx * sn + dy * c]
                self.cv.coords(p["i"], *pts)
            elif p["kind"] < 0.8:
                self.cv.coords(p["i"], x - s / 2, y - flip / 2, x + s / 2, y + flip / 2)
            else:
                self.cv.coords(p["i"], x, y, x + math.cos(p["rot"]) * s, y + math.sin(p["rot"]) * s)
        self.cv.tag_raise(self.tag)
        return alive > 0


class Burst:
    """Ring shockwave + sparks (used for level up / node unlock)."""

    def __init__(self, app, x, y, color, radius=120, dur=0.8):
        cv = app.cv
        bg = app.t.bg
        rings = [cv.create_oval(x, y, x, y, outline=color, width=4, tags="fxtop") for _ in range(2)]
        sparks = []
        for i in range(14):
            a = i / 14 * math.tau
            sparks.append((cv.create_line(x, y, x, y, fill=color, width=3, capstyle="round", tags="fxtop"), a))

        def upd(p):
            for k, r in enumerate(rings):
                q = max(0.0, min(1.0, p * 1.25 - k * 0.25))
                rr = radius * ease_out_cubic(q)
                cv.coords(r, x - rr, y - rr, x + rr, y + rr)
                cv.itemconfigure(r, outline=mix(color, bg, q), width=max(1, 6 * (1 - q)))
            for item, a in sparks:
                r1 = radius * 0.3 + radius * 0.9 * ease_out_cubic(p)
                r2 = r1 - 18 * (1 - p)
                cv.coords(item, x + math.cos(a) * r2, y + math.sin(a) * r2, x + math.cos(a) * r1, y + math.sin(a) * r1)
                cv.itemconfigure(item, fill=mix(color, bg, p))

        def done():
            for r in rings:
                cv.delete(r)
            for item, _ in sparks:
                cv.delete(item)

        app.anim.tween(dur, upd, ease=linear, done=done)
