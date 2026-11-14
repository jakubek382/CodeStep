"""Run learner code with whatever toolchain is installed on this machine.

If no toolchain for a language is found, the checker falls back to comparing
the code with the reference solution (see ``codestep.checker``).
"""
from __future__ import annotations

import contextlib
import io
import os
import shutil
import subprocess
import sys
import tempfile
import threading
from dataclasses import dataclass

IS_WINDOWS = os.name == "nt"
EXE = ".exe" if IS_WINDOWS else ""
FROZEN = getattr(sys, "frozen", False)   # running from the PyInstaller .exe


@dataclass
class RunResult:
    ok: bool             # program compiled and exited with status 0
    stdout: str
    error: str = ""


@dataclass
class Runner:
    tool: str            # e.g. "node"
    path: str            # resolved executable ("<in-process>" for Python)
    lang_id: str

    @property
    def label(self) -> str:
        return "built-in Python" if self.path == "<in-process>" else self.tool


def find_runner(lang) -> Runner | None:
    for tool in lang.runners:
        if tool == "python":
            if FROZEN:
                return Runner("python", "<in-process>", lang.id)
            return Runner("python", sys.executable, lang.id)
        path = shutil.which(tool)
        if path:
            if tool == "kotlinc" and not shutil.which("java"):
                continue
            return Runner(tool, path, lang.id)
    return None


# ------------------------------------------------------------------ helpers
def _popen_kwargs():
    kw = {}
    if IS_WINDOWS:
        kw["creationflags"] = 0x08000000  # CREATE_NO_WINDOW
    return kw


def _run(cmd, cwd, timeout, env=None) -> RunResult:
    try:
        p = subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout,
            stdin=subprocess.DEVNULL, env=env, encoding="utf-8", errors="replace",
            **_popen_kwargs(),
        )
    except subprocess.TimeoutExpired:
        return RunResult(False, "", f"Timed out after {timeout}s (infinite loop?)")
    except OSError as e:
        return RunResult(False, "", f"Could not start {cmd[0]}: {e}")
    if p.returncode != 0:
        return RunResult(False, p.stdout, (p.stderr or p.stdout).strip() or f"exit code {p.returncode}")
    return RunResult(True, p.stdout)


def _exec_in_process(code: str, timeout: float) -> RunResult:
    """Used inside the frozen .exe, where there is no python.exe to call."""
    out, box = io.StringIO(), {}

    def target():
        try:
            with contextlib.redirect_stdout(out):
                exec(compile(code, "<your code>", "exec"), {"__name__": "__main__"})
        except BaseException as e:  # noqa: BLE001 - report anything to the learner
            box["error"] = f"{type(e).__name__}: {e}"

    t = threading.Thread(target=target, daemon=True)
    t.start()
    t.join(timeout)
    if t.is_alive():
        return RunResult(False, out.getvalue(), f"Timed out after {timeout}s (infinite loop?)")
    if "error" in box:
        return RunResult(False, out.getvalue(), box["error"])
    return RunResult(True, out.getvalue())


def _dotnet_tfm(dotnet: str) -> str:
    try:
        v = subprocess.run([dotnet, "--version"], capture_output=True, text=True, timeout=30,
                           **_popen_kwargs()).stdout.strip()
        return f"net{int(v.split('.')[0])}.0"
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return "net8.0"


_CSPROJ = """<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <OutputType>Exe</OutputType>
    <TargetFramework>{tfm}</TargetFramework>
    <ImplicitUsings>enable</ImplicitUsings>
    <Nullable>disable</Nullable>
    <TreatWarningsAsErrors>false</TreatWarningsAsErrors>
  </PropertyGroup>
</Project>
"""


def run(runner: Runner, lang, code: str, timeout: float = 10.0) -> RunResult:
    if runner.path == "<in-process>":
        return _exec_in_process(code, timeout)

    with tempfile.TemporaryDirectory(prefix="codestep_") as d:
        src_name = "Main.java" if lang.id == "java" else "main" + lang.ext
        src = os.path.join(d, src_name)
        with open(src, "w", encoding="utf-8") as f:
            f.write(code)
        exe = os.path.join(d, "main" + EXE)
        t, p = runner.tool, runner.path
        slow = max(timeout, 120.0)  # first compile of JVM/.NET is slow

        if t == "python":
            return _run([p, "-I", src], d, timeout)
        if t in ("node", "bun", "tsx", "ruby", "php", "lua", "lua5.4", "lua54", "luajit"):
            return _run([p, src], d, timeout)
        if t == "deno":
            return _run([p, "run", "--quiet", src], d, timeout)
        if t == "java":
            return _run([p, src], d, max(timeout, 30.0))
        if t == "go":
            return _run([p, "run", src], d, max(timeout, 60.0))
        if t in ("gcc", "clang", "cc"):
            r = _run([p, src, "-o", exe], d, max(timeout, 30.0))
            return r if not r.ok else _run([exe], d, timeout)
        if t in ("g++", "clang++"):
            r = _run([p, "-std=c++17", src, "-o", exe], d, max(timeout, 30.0))
            return r if not r.ok else _run([exe], d, timeout)
        if t == "rustc":
            r = _run([p, "--edition", "2021", src, "-o", exe], d, max(timeout, 60.0))
            return r if not r.ok else _run([exe], d, timeout)
        if t == "kotlinc":
            jar = os.path.join(d, "main.jar")
            r = _run([p, src, "-include-runtime", "-d", jar], d, slow)
            return r if not r.ok else _run([shutil.which("java") or "java", "-jar", jar], d, timeout)
        if t == "dotnet":
            with open(os.path.join(d, "app.csproj"), "w", encoding="utf-8") as f:
                f.write(_CSPROJ.format(tfm=_dotnet_tfm(p)))
            env = dict(os.environ, DOTNET_NOLOGO="1", DOTNET_CLI_TELEMETRY_OPTOUT="1",
                       DOTNET_SKIP_FIRST_TIME_EXPERIENCE="1")
            r = _run([p, "build", "-nologo", "-v", "q", "-o", os.path.join(d, "out")], d, slow, env)
            if not r.ok:
                return r
            dll = os.path.join(d, "out", "app.dll")
            return _run([p, dll], d, timeout, env)
        return RunResult(False, "", f"Don't know how to run {t}")


def normalize_output(text: str) -> str:
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    return "\n".join(ln.rstrip() for ln in lines).strip()
