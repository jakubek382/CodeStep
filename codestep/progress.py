"""Save file handling. Same location as v1.0.x: ~/Documents/CodeStep/progress_data.json

v1 files (Python-only) are migrated automatically. v1 also had two bugs that
are fixed here: lesson keys were saved as strings but looked up as ints (so
task progress reset on restart), and new players were shown as Level 0.
"""
from __future__ import annotations

import json
import os
from datetime import date, timedelta

XP_PER_LEVEL = 500
DAILY_LESSON_LIMIT = 3
SCHEMA_VERSION = 2


def progress_path() -> str:
    d = os.path.join(os.path.expanduser("~/Documents"), "CodeStep")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "progress_data.json")


def level_for(xp: int) -> int:
    return xp // XP_PER_LEVEL + 1


def _lang_default():
    return {"unlocked": [1], "completed_tasks": {}}


def default_progress():
    return {
        "version": SCHEMA_VERSION,
        "language": "python",
        "streak": 0,
        "last_date": "",
        "daily_lessons": 0,
        "xp": 0,
        "level": 1,
        "languages": {"python": _lang_default()},
    }


def _migrate(data: dict) -> dict:
    p = default_progress()
    for k in ("streak", "last_date", "daily_lessons", "xp", "language"):
        if k in data:
            p[k] = data[k]
    langs = data.get("languages") or {}
    if "unlocked" in data or "completed_tasks" in data:          # v1 layout
        langs = dict(langs)
        langs["python"] = {"unlocked": data.get("unlocked", [1]),
                           "completed_tasks": data.get("completed_tasks", {})}
    for lid, lp in langs.items():
        done = {}
        for k, v in (lp.get("completed_tasks") or {}).items():   # "1" and 1 -> "1"
            done[str(k)] = max(done.get(str(k), 0), int(v))
        unlocked = sorted({int(u) for u in lp.get("unlocked", [1])} | {1})
        p["languages"][lid] = {"unlocked": unlocked, "completed_tasks": done}
    p["level"] = level_for(p["xp"])
    return p


def load() -> dict:
    path = progress_path()
    try:
        with open(path, "r", encoding="utf-8") as f:
            return _migrate(json.load(f))
    except FileNotFoundError:
        p = default_progress()
        save(p)
        return p
    except (json.JSONDecodeError, ValueError, TypeError, AttributeError):
        # corrupt file: keep a copy and start fresh rather than crashing
        try:
            os.replace(path, path + ".broken")
        except OSError:
            pass
        p = default_progress()
        save(p)
        return p


def save(progress: dict) -> None:
    path = progress_path()
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(progress, f, indent=2)
    os.replace(tmp, path)


def lang_progress(progress: dict, lang_id: str) -> dict:
    return progress["languages"].setdefault(lang_id, _lang_default())


def roll_day(progress: dict, today: date | None = None) -> None:
    """Reset the daily counter and update the streak when the day changes."""
    today = today or date.today()
    t = today.isoformat()
    if progress["last_date"] == t:
        return
    yesterday = (today - timedelta(days=1)).isoformat()
    progress["streak"] = progress["streak"] + 1 if progress["last_date"] == yesterday else 1
    progress["daily_lessons"] = 0
    progress["last_date"] = t


def record_task(progress: dict, lang_id: str, lesson_no: int, task_no: int,
                xp_reward: int, task_count: int, lesson_count: int):
    """Returns (accepted, leveled_up, message_if_rejected)."""
    roll_day(progress)
    if progress["daily_lessons"] >= DAILY_LESSON_LIMIT:
        return False, False, (f"You've reached the daily limit of {DAILY_LESSON_LIMIT} lessons! "
                              "Come back tomorrow.")
    lp = lang_progress(progress, lang_id)
    old_level = level_for(progress["xp"])
    key = str(lesson_no)
    if task_no > lp["completed_tasks"].get(key, 0):
        lp["completed_tasks"][key] = task_no
        progress["xp"] += xp_reward
        if task_no == task_count:
            progress["daily_lessons"] += 1
            nxt = lesson_no + 1
            if nxt <= lesson_count and nxt not in lp["unlocked"]:
                lp["unlocked"].append(nxt)
    progress["level"] = level_for(progress["xp"])
    save(progress)
    return True, progress["level"] > old_level, ""
