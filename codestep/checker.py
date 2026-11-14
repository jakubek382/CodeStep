"""Decide whether the learner's code solves a task."""
from __future__ import annotations

import re
from dataclasses import dataclass

from .runner import find_runner, normalize_output, run


@dataclass
class CheckResult:
    ok: bool
    message: str
    output: str = ""        # what to show in the console box
    xp: int = 0
    simulated: bool = False  # True when no toolchain was available


def _scan(code: str, lang, keep_strings=True, drop_ws=True):
    """Remove comments (and optionally strings / whitespace) outside of
    string literals. Returns the cleaned text."""
    out, i, n = [], 0, len(code)
    line_c = sorted(lang.line_comments, key=len, reverse=True)
    block_c = lang.block_comments
    while i < n:
        # block comments first so "--[[" wins over "--"
        hit = next(((a, b) for a, b in block_c if code.startswith(a, i)), None)
        if hit:
            j = code.find(hit[1], i + len(hit[0]))
            i = n if j < 0 else j + len(hit[1])
            out.append(" ")
            continue
        if any(code.startswith(c, i) for c in line_c):
            j = code.find("\n", i)
            i = n if j < 0 else j
            continue
        ch = code[i]
        if ch in lang.quotes:
            j = i + 1
            while j < n and code[j] != ch:
                j += 2 if code[j] == "\\" else 1
            lit = code[i:j + 1]
            if keep_strings:
                if lang.quotes_equivalent and ch in "'\"":
                    body = lit[1:-1].replace('\\"', '"').replace("\\'", "'")
                    lit = '"' + body + '"'
                out.append(lit)
            else:
                out.append(" ")
            i = j + 1
            continue
        if drop_ws and ch.isspace():
            i += 1
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def normalize_code(code: str, lang) -> str:
    """Comment/whitespace/quote-insensitive form of the code."""
    s = _scan(code, lang)
    if lang.optional_semicolons or lang.id == "python":
        s = s.replace(";", "")
    return s


def missing_words(code: str, required, lang) -> list:
    bare = _scan(code, lang, keep_strings=False, drop_ws=False)
    missing = []
    for w in required:
        pat = r"(?<!\w)" + r"\s+".join(map(re.escape, w.split())) + r"(?!\w)"
        if not re.search(pat, bare):
            missing.append(w)
    return missing


def check(lang, task, code: str) -> CheckResult:
    runner = find_runner(lang)
    expected = normalize_output(task.expected)

    if runner is None:
        if normalize_code(code, lang) == normalize_code(task.answer, lang):
            return CheckResult(True, f"Great job! Your code matches the solution! +{task.xp} XP",
                               expected + f"\n\n(simulated - install {lang.install_hint} to run real {lang.name} code)",
                               task.xp, simulated=True)
        return CheckResult(
            False,
            f"Not quite. No {lang.name} toolchain was found, so your code is compared with "
            f"the reference solution (spacing and comments don't matter).\n\n"
            f"Tip: install {lang.install_hint} so CodeStep can run any correct answer.\n"
            f"Use 'Show Solution' if you are stuck.",
            "(not run - no toolchain found)", simulated=True)

    res = run(runner, lang, code)
    got = normalize_output(res.stdout)
    if not res.ok:
        console = (got + "\n\n" if got else "") + "Error:\n" + res.error
        return CheckResult(False, "Your code didn't run:\n\n" + res.error[-800:], console)
    if got != expected:
        return CheckResult(False, f"Code runs but outputs '{got}' instead of '{expected}'", got)
    missing = missing_words(code, task.required, lang)
    if missing:
        return CheckResult(False, "The output is right, but this task wants you to use: "
                           + ", ".join(f"`{m}`" for m in missing), got)
    return CheckResult(True, f"Great job! Your code is correct and outputs '{got}'! +{task.xp} XP",
                       got, task.xp)
