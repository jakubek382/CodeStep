import json
import os
import sys
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import codestep.checker as checker  # noqa: E402
from codestep import progress as prog  # noqa: E402
from codestep.curriculum import lessons_for  # noqa: E402
from codestep.languages import LANGUAGES  # noqa: E402


def test_fallback_matches_reformatted_answer(monkeypatch):
    """With no toolchain, spacing/comments/quote style must not matter."""
    monkeypatch.setattr(checker, "find_runner", lambda lang: None)
    for lid, lang in LANGUAGES.items():
        for lesson in lessons_for(lid):
            for task in lesson.tasks:
                c = lang.line_comments[0]
                messy = f"{c} my attempt\n" + task.answer.replace("    ", "  ") + f"\n{c} done\n"
                assert checker.check(lang, task, messy).ok, (lid, task.title)
                assert not checker.check(lang, task, task.starter).ok


def test_python_single_vs_double_quotes(monkeypatch):
    monkeypatch.setattr(checker, "find_runner", lambda lang: None)
    task = lessons_for("python")[0].tasks[0]
    assert checker.check(LANGUAGES["python"], task, 'print("Hello, World!")').ok


def test_required_words_ignore_strings_and_comments():
    lang = LANGUAGES["javascript"]
    assert checker.missing_words('console.log("for x")  // for x', ["for", "x"], lang) == ["for", "x"]
    assert checker.missing_words("const x = 1;", ["x"], lang) == []


def test_v1_save_is_migrated(tmp_path, monkeypatch):
    monkeypatch.setattr(prog, "progress_path", lambda: str(tmp_path / "p.json"))
    # what v1.0.2 actually wrote: int keys became strings, xp level 0
    v1 = {"unlocked": [1, 2], "streak": 3, "last_date": "2025-06-15", "daily_lessons": 1,
          "completed_tasks": {"1": 10, "2": 4}, "xp": 900, "level": 1}
    (tmp_path / "p.json").write_text(json.dumps(v1))
    p = prog.load()
    assert p["languages"]["python"] == {"unlocked": [1, 2], "completed_tasks": {"1": 10, "2": 4}}
    assert p["xp"] == 900 and p["level"] == 2 and p["streak"] == 3


def test_record_task_unlocks_and_limits(tmp_path, monkeypatch):
    monkeypatch.setattr(prog, "progress_path", lambda: str(tmp_path / "p.json"))
    p = prog.default_progress()
    for t in range(1, 11):
        ok, _, _ = prog.record_task(p, "rust", 1, t, 100, 10, 5)
        assert ok
    lp = p["languages"]["rust"]
    assert lp["unlocked"] == [1, 2] and lp["completed_tasks"]["1"] == 10
    assert p["xp"] == 1000 and p["level"] == 3 and p["daily_lessons"] == 1
    # replaying a finished task gives no XP
    prog.record_task(p, "rust", 1, 5, 100, 10, 5)
    assert p["xp"] == 1000
    p["daily_lessons"] = prog.DAILY_LESSON_LIMIT
    ok, _, msg = prog.record_task(p, "rust", 2, 1, 50, 10, 5)
    assert not ok and "limit" in msg


def test_streak():
    p = prog.default_progress()
    prog.roll_day(p, date(2026, 1, 1))
    prog.roll_day(p, date(2026, 1, 2))
    assert p["streak"] == 2
    prog.roll_day(p, date(2026, 1, 5))
    assert p["streak"] == 1
