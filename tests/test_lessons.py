"""Every reference answer must run and print the expected output.

Languages whose toolchain isn't installed are skipped (and reported).
Run:  python -m pytest -q      or      python tests/test_lessons.py
"""
import os
import sys
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from codestep.checker import check, missing_words  # noqa: E402
from codestep.curriculum import lessons_for  # noqa: E402
from codestep.languages import LANGUAGES  # noqa: E402
from codestep.runner import find_runner  # noqa: E402

try:
    import pytest
except ImportError:  # allow running without pytest
    pytest = None


def all_tasks(lang_id):
    for li, lesson in enumerate(lessons_for(lang_id), 1):
        for ti, task in enumerate(lesson.tasks, 1):
            yield li, ti, task


def check_language(lang_id):
    lang = LANGUAGES[lang_id]
    failures = []
    for li, ti, task in all_tasks(lang_id):
        miss = missing_words(task.answer, task.required, lang)
        if miss:
            failures.append(f"{lang_id} L{li}T{ti}: answer lacks required {miss}")
        res = check(lang, task, task.answer)
        if not res.ok:
            failures.append(f"{lang_id} L{li}T{ti}: {res.message}\n{task.answer}")
    return failures


def test_structure():
    for lang_id in LANGUAGES:
        lessons = lessons_for(lang_id)
        assert len(lessons) == 5
        for lesson in lessons:
            assert len(lesson.tasks) == 10


def test_wrong_answer_rejected():
    lang = LANGUAGES["python"]
    task = lessons_for("python")[0].tasks[0]
    assert not check(lang, task, "print('nope')").ok
    # right output but required variable missing
    task = lessons_for("python")[0].tasks[3]
    assert not check(lang, task, "print(10)").ok


if pytest:
    @pytest.mark.parametrize("lang_id", list(LANGUAGES))
    def test_answers_run(lang_id):
        if find_runner(LANGUAGES[lang_id]) is None:
            pytest.skip(f"no toolchain for {lang_id}")
        failures = check_language(lang_id)
        assert not failures, "\n\n".join(failures)


if __name__ == "__main__":
    test_structure()
    test_wrong_answer_rejected()
    ids = list(LANGUAGES)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = dict(zip(ids, pool.map(
            lambda i: None if find_runner(LANGUAGES[i]) is None else check_language(i), ids)))
    bad = 0
    for i, fails in results.items():
        if fails is None:
            print(f"SKIP {i}: no toolchain")
        elif fails:
            bad += 1
            print(f"FAIL {i}:\n" + "\n\n".join(fails))
        else:
            print(f"ok   {i} (50 tasks)")
    sys.exit(1 if bad else 0)
