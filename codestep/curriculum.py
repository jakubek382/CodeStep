"""Lesson content.

* Python keeps the original five hand-written lessons recovered from
  CodeStep v1.0.2-alpha (main.py).
* Every other language gets the same five lessons, written once in the IR
  (``codestep.ir``) and rendered per language, so all answers are real,
  runnable programs (the test suite compiles and runs every one).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from . import ir
from .ir import B, Call, Def, For, I, If, L, P, S, Set, Aug, V, While
from .languages import LANGUAGES


@dataclass
class Task:
    title: str
    prompt: str
    answer: str            # canonical solution
    expected: str          # expected stdout (stripped)
    xp: int
    required: list = field(default_factory=list)   # words that must appear
    starter: str = ""      # editor contents when the task opens


@dataclass
class Lesson:
    title: str
    tasks: list


# ============================================================== Python (v1.0.2)
# (answer, expected output, xp) -- verbatim from the original check_answer()
_PY_ANSWERS = {
    1: [
        ("print('Hello, World!')", "Hello, World!", 50),
        ("print('Python is awesome!')", "Python is awesome!", 50),
        ("print(42)", "42", 50),
        ("x = 10\nprint(x)", "10", 75),
        ("name = 'CodeStep'\nprint(name)", "CodeStep", 75),
        ("a = 5\nb = 3\nprint(a + b)", "8", 100),
        ("greeting = 'Hello'\nprint(greeting)", "Hello", 75),
        ("a = 'Hi'\nb = 'World'\nprint(a, b)", "Hi World", 100),
        ("word = 'Score'\npoints = 100\nprint(word, points)", "Score 100", 100),
        ("a = 'Hello, World!'\nb = 'Hi'\nprint(a, b)", "Hello, World! Hi", 150),
    ],
    2: [
        ("name = 'CodeStep'\nprint(name)", "CodeStep", 50),
        ("x = 5\nprint(x)", "5", 50),
        ("x = 10\nprint(x + 1)", "11", 75),
        ("y = 42\nprint(y)", "42", 50),
        ("text = 'Hello'\nnumber = 5\nprint(text, number)", "Hello 5", 100),
        ("a = 3\nb = 7\nprint(a + b)", "10", 100),
        ("value = 100\nprint(value)", "100", 50),
        ("x = 'Test'\nx = 10\nprint(x)", "10", 75),
        ("a = 'Hi'\nb = 'World'\nprint(a, b)", "Hi World", 100),
        ("score = 50\nprint('Your score is', score)", "Your score is 50", 150),
    ],
    3: [
        ("x = 10\nif x > 5:\n    print('Big')", "Big", 50),
        ("x = 3\nif x < 5:\n    print('Small')", "Small", 50),
        ("x = 7\nif x >= 7:\n    print('Enough')", "Enough", 75),
        ("x = 0\nif x == 0:\n    print('Zero')", "Zero", 75),
        ("x = 15\nif x > 10:\n    print('Large')\nelse:\n    print('Small')", "Large", 100),
        ("x = 4\nif x > 5:\n    print('Big')\nelse:\n    print('Small')", "Small", 100),
        ("x = 50\nif x > 100:\n    print('Huge')\nelif x > 10:\n    print('Medium')\nelse:\n    print('Tiny')", "Medium", 125),
        ("x = 5\ny = 10\nif x + y > 12:\n    print('Pass')", "Pass", 125),
        ("age = 18\nif age >= 18:\n    print('Adult')\nelse:\n    print('Minor')", "Adult", 150),
        ("score = 85\nif score >= 90:\n    print('A')\nelif score >= 80:\n    print('B')\nelif score >= 70:\n    print('C')\nelse:\n    print('D')", "B", 200),
    ],
    4: [
        ("for i in range(3):\n    print('Loop')", "Loop\nLoop\nLoop", 50),
        ("for i in range(1, 4):\n    print(i)", "1\n2\n3", 50),
        ("for i in range(2, 7, 2):\n    print(i)", "2\n4\n6", 75),
        ("x = 0\nwhile x < 3:\n    print(x)\n    x += 1", "0\n1\n2", 75),
        ("for i in range(5):\n    print(i * 2)", "0\n2\n4\n6\n8", 100),
        ("x = 5\nwhile x > 0:\n    print(x)\n    x -= 1", "5\n4\n3\n2\n1", 100),
        ("total = 0\nfor i in range(1, 5):\n    total += i\nprint(total)", "10", 125),
        ("count = 0\nwhile count < 4:\n    print('Hi')\n    count += 1", "Hi\nHi\nHi\nHi", 125),
        ("for i in range(1, 6):\n    if i % 2 == 0:\n        print(i)", "2\n4", 150),
        ("total = 0\nfor i in range(1, 11):\n    if i % 2 == 0:\n        total += i\nprint(total)", "30", 200),
    ],
    5: [
        ("def say_hello():\n    print('Hello')\nsay_hello()", "Hello", 50),
        ("def print_num():\n    print(42)\nprint_num()", "42", 50),
        ("def add_five(x):\n    print(x + 5)\nadd_five(10)", "15", 75),
        ("def greet(name):\n    print('Hi', name)\ngreet('CodeStep')", "Hi CodeStep", 75),
        ("def double(x):\n    print(x * 2)\ndouble(5)", "10", 100),
        ("def is_positive(x):\n    if x > 0:\n        print('Positive')\n    else:\n        print('Non-positive')\nis_positive(3)", "Positive", 100),
        ("def count_to_three():\n    for i in range(1, 4):\n        print(i)\ncount_to_three()", "1\n2\n3", 125),
        ("def print_sum(a, b):\n    print(a + b)\nprint_sum(4, 6)", "10", 125),
        ("def check_even(x):\n    if x % 2 == 0:\n        print('Even')\n    else:\n        print('Odd')\ncheck_even(4)", "Even", 150),
        ("def factorial(n):\n    result = 1\n    for i in range(1, n + 1):\n        result *= i\n    print(result)\nfactorial(4)", "24", 200),
    ],
}

# (title, body) -- verbatim task text from the original show_task()
_PY_PROMPTS = {
    1: [
        ("Print text", "Use the `print()` function to display 'Hello, World!'.\nExample: 'Text'"),
        ("Print another text", "Use `print()` to display 'Python is awesome!'."),
        ("Print number", "Use `print()` to display 42."),
        ("Variable", "Create variable `x = 10` and print it."),
        ("Text variable", "Create variable `name = 'CodeStep'` and print it."),
        ("Sum", "Create `a = 5`, `b = 3`, print their sum."),
        ("Greeting", "Create `greeting = 'Hello'` and print it."),
        ("Two variables", "Create `a = 'Hi'`, `b = 'World'`, print them."),
        ("Mixed types", "Create `word = 'Score'`, `points = 100`, print them."),
        ("Advanced", "Create `a = 'Hello, World!'`, `b = 'Hi'`, print them."),
    ],
    2: [
        ("Fix code", "Code: `name = CodeStep; print(name)`\nFix to print 'CodeStep'."),
        ("Fix code", "Code: `x = 5; Print(x)`\nFix to print 5."),
        ("Fix code", "Code: `x = '10'; print(x + 1)`\nFix to print 11."),
        ("Fix code", "Code: `y = 42; print(Y)`\nFix to print 42."),
        ("Fix code", "Code: `text = 'Hello'; print(text + 5)`\nFix to print 'Hello 5'."),
        ("Fix code", "Code: `a = 3; b = 7; print(a - b)`\nFix to print 10."),
        ("Fix code", "Code: `value = 100; print('value')`\nFix to print 100."),
        ("Fix code", "Code: `x = 'Test'; x = 10; print(X)`\nFix to print 10."),
        ("Fix code", "Code: `a = 'Hi'; b = 'World'; print(a + b)`\nFix to print 'Hi World'."),
        ("Fix code", "Code: `score = 50; print('Your score is ' + score)`\nFix to print 'Your score is 50'."),
    ],
    3: [
        ("Condition", "Check if `x = 10` > 5, print 'Big'."),
        ("Condition", "Check if `x = 3` < 5, print 'Small'."),
        ("Condition", "Check if `x = 7` >= 7, print 'Enough'."),
        ("Condition", "Check if `x = 0` == 0, print 'Zero'."),
        ("If-else", "Check if `x = 15` > 10, print 'Large' or 'Small'."),
        ("If-else", "Check if `x = 4` > 5, print 'Big' or 'Small'."),
        ("Elif", "Check `x = 50`: >100 'Huge', >10 'Medium', else 'Tiny'."),
        ("Sum", "Check if `x = 5`, `y = 10` sum > 12, print 'Pass'."),
        ("Age", "Check if `age = 18` >= 18, print 'Adult' or 'Minor'."),
        ("Grades", "Check `score = 85`: >=90 'A', >=80 'B', >=70 'C', else 'D'."),
    ],
    4: [
        ("Loop", "Print 'Loop' 3 times with for loop."),
        ("Loop", "Print 1 to 3 with for loop."),
        ("Loop", "Print 2, 4, 6 with for loop."),
        ("While", "Print 0 to 2 with while loop."),
        ("Loop", "Print 0, 2, 4, 6, 8 with for loop."),
        ("While", "Print 5 to 1 with while loop."),
        ("Sum", "Sum 1 to 4, print 10."),
        ("While", "Print 'Hi' 4 times with while loop."),
        ("Loop", "Print even numbers 2, 4 from 1 to 5."),
        ("Sum", "Sum even numbers 1 to 10, print 30."),
    ],
    5: [
        ("Function", "Define `say_hello` to print 'Hello'."),
        ("Function", "Define `print_num` to print 42."),
        ("Function", "Define `add_five(x)` to print x+5, call with 10."),
        ("Function", "Define `greet(name)` to print 'Hi name', call with 'CodeStep'."),
        ("Function", "Define `double(x)` to print x*2, call with 5."),
        ("Function", "Define `is_positive(x)` to print 'Positive' or 'Non-positive', call with 3."),
        ("Function", "Define `count_to_three` to print 1 to 3."),
        ("Function", "Define `print_sum(a, b)` to print a+b, call with 4, 6."),
        ("Function", "Define `check_even(x)` to print 'Even' or 'Odd', call with 4."),
        ("Function", "Define `factorial(n)` to print 4! (24)."),
    ],
}

_PY_TITLES = ["Introduction to print()", "Variables", "Conditionals", "Loops", "Functions"]

_PY_KEYWORDS = ("for", "while", "if", "elif", "else", "def")


def _python_required(answer: str) -> list:
    """Names/keywords from the solution that the learner must also use."""
    req = []
    for kw in _PY_KEYWORDS:
        if re.search(rf"\b{kw}\b", answer):
            req.append(kw)
    req += re.findall(r"^def (\w+)", answer, re.M)
    req += [n for n in re.findall(r"^\s*(\w+)\s*[-+*]?=(?!=)", answer, re.M) if n not in req]
    return req


def _python_lessons():
    lessons = []
    for lid in range(1, 6):
        tasks = []
        for (title, body), (ans, out, xp) in zip(_PY_PROMPTS[lid], _PY_ANSWERS[lid]):
            tasks.append(Task(title, body, ans, out, xp, _python_required(ans)))
        lessons.append(Lesson(_PY_TITLES[lid - 1], tasks))
    return lessons


# ============================================================== shared lessons
# Each spec: (title, prompt, program, expected, xp)
# Prompts use {name} placeholders for function names, which are rendered in
# the target language's naming style (say_hello / sayHello / SayHello).
# {lang} is the language name.
def _shared_specs(lang_name: str):
    return [
        ("Output", [
            ("Print text", "Print the text 'Hello, World!'.",
             [P(S("Hello, World!"))], "Hello, World!", 50),
            ("Print another text", f"Print the text '{lang_name} is awesome!'.",
             [P(S(f"{lang_name} is awesome!"))], f"{lang_name} is awesome!", 50),
            ("Print number", "Print the number 42.",
             [P(I(42))], "42", 50),
            ("Variable", "Create a variable `x` with the value 10 and print it.",
             [L("x", I(10)), P("x")], "10", 75),
            ("Text variable", "Create a variable `name` with the text 'CodeStep' and print it.",
             [L("name", "CodeStep"), P("name")], "CodeStep", 75),
            ("Sum", "Create `a = 5` and `b = 3`, then print their sum.",
             [L("a", I(5)), L("b", I(3)), P(B("a", "+", "b"))], "8", 100),
            ("Greeting", "Create `greeting` with the text 'Hello' and print it.",
             [L("greeting", "Hello"), P("greeting")], "Hello", 75),
            ("Two variables", "Create `a = 'Hi'` and `b = 'World'`, print them on one line separated by a space.",
             [L("a", "Hi"), L("b", "World"), P("a", "b")], "Hi World", 100),
            ("Mixed types", "Create `word = 'Score'` and `points = 100`, print them on one line: 'Score 100'.",
             [L("word", "Score"), L("points", I(100)), P("word", "points")], "Score 100", 100),
            ("Advanced", "Create `a = 'Hello, World!'` and `b = 'Hi'`, print them on one line separated by a space.",
             [L("a", "Hello, World!"), L("b", "Hi"), P("a", "b")], "Hello, World! Hi", 150),
        ]),
        ("Variables & Math", [
            ("Store a number", "Create `x = 7` and print it.",
             [L("x", I(7)), P("x")], "7", 50),
            ("Subtract", "Create `a = 10` and `b = 4`, print `a - b`.",
             [L("a", I(10)), L("b", I(4)), P(B("a", "-", "b"))], "6", 50),
            ("Multiply", "Create `a = 6` and `b = 7`, print `a * b`.",
             [L("a", I(6)), L("b", I(7)), P(B("a", "*", "b"))], "42", 75),
            ("Remainder", "Create `x = 17`, print the remainder of `x` divided by 5.",
             [L("x", I(17)), P(B("x", "%", 5))], "2", 75),
            ("Add to a variable", "Create `score = 10`, add 5 to it with a compound assignment, print it.",
             [L("score", I(10)), Aug("score", "+", I(5)), P("score")], "15", 100),
            ("Lose a life", "Create `lives = 3`, subtract 1 from it, print it.",
             [L("lives", I(3)), Aug("lives", "-", I(1)), P("lives")], "2", 100),
            ("Total price", "Create `price = 20` and `qty = 3`, store `price * qty` in `total`, print `total`.",
             [L("price", I(20)), L("qty", I(3)), L("total", B("price", "*", "qty")), P("total")], "60", 100),
            ("Reassign", "Create `x = 5`, then set `x` to `x * 2`, print it.",
             [L("x", I(5)), Set("x", B("x", "*", 2)), P("x")], "10", 75),
            ("Sentence", "Create `name = 'Player'` and `level = 7`, print 'Player is level 7'.",
             [L("name", "Player"), L("level", I(7)), P("name", S("is level"), "level")], "Player is level 7", 125),
            ("Calculator", "Create `a = 8` and `b = 3`, print `a + b`, `a - b` and `a * b` on separate lines.",
             [L("a", I(8)), L("b", I(3)), P(B("a", "+", "b")), P(B("a", "-", "b")), P(B("a", "*", "b"))],
             "11\n5\n24", 150),
        ]),
        ("Conditionals", [
            ("Condition", "Create `x = 10`. If `x` > 5, print 'Big'.",
             [L("x", I(10)), If([(B("x", ">", 5), [P(S("Big"))])])], "Big", 50),
            ("Condition", "Create `x = 3`. If `x` < 5, print 'Small'.",
             [L("x", I(3)), If([(B("x", "<", 5), [P(S("Small"))])])], "Small", 50),
            ("Condition", "Create `x = 7`. If `x` >= 7, print 'Enough'.",
             [L("x", I(7)), If([(B("x", ">=", 7), [P(S("Enough"))])])], "Enough", 75),
            ("Condition", "Create `x = 0`. If `x` equals 0, print 'Zero'.",
             [L("x", I(0)), If([(B("x", "==", 0), [P(S("Zero"))])])], "Zero", 75),
            ("If-else", "Create `x = 15`. If `x` > 10 print 'Large', otherwise print 'Small'.",
             [L("x", I(15)), If([(B("x", ">", 10), [P(S("Large"))])], [P(S("Small"))])], "Large", 100),
            ("If-else", "Create `x = 4`. If `x` > 5 print 'Big', otherwise print 'Small'.",
             [L("x", I(4)), If([(B("x", ">", 5), [P(S("Big"))])], [P(S("Small"))])], "Small", 100),
            ("Else-if", "Create `x = 50`: > 100 print 'Huge', > 10 print 'Medium', otherwise 'Tiny'.",
             [L("x", I(50)), If([(B("x", ">", 100), [P(S("Huge"))]), (B("x", ">", 10), [P(S("Medium"))])],
                                [P(S("Tiny"))])], "Medium", 125),
            ("Sum", "Create `x = 5` and `y = 10`. If `x + y` > 12, print 'Pass'.",
             [L("x", I(5)), L("y", I(10)), If([(B(B("x", "+", "y"), ">", 12), [P(S("Pass"))])])], "Pass", 125),
            ("Age", "Create `age = 18`. If `age` >= 18 print 'Adult', otherwise 'Minor'.",
             [L("age", I(18)), If([(B("age", ">=", 18), [P(S("Adult"))])], [P(S("Minor"))])], "Adult", 150),
            ("Grades", "Create `score = 85`: >= 90 'A', >= 80 'B', >= 70 'C', otherwise 'D'.",
             [L("score", I(85)), If([(B("score", ">=", 90), [P(S("A"))]), (B("score", ">=", 80), [P(S("B"))]),
                                     (B("score", ">=", 70), [P(S("C"))])], [P(S("D"))])], "B", 200),
        ]),
        ("Loops", [
            ("Loop", "Print 'Loop' 3 times using a for loop.",
             [For("i", 0, 3, [P(S("Loop"))])], "Loop\nLoop\nLoop", 50),
            ("Loop", "Print 1 to 3 using a for loop.",
             [For("i", 1, 4, [P("i")])], "1\n2\n3", 50),
            ("Loop", "Print 2, 4, 6 using a for loop with a step of 2.",
             [For("i", 2, 7, [P("i")], step=2)], "2\n4\n6", 75),
            ("While", "Create `x = 0` and print 0 to 2 using a while loop.",
             [L("x", I(0)), While(B("x", "<", 3), [P("x"), Aug("x", "+", I(1))])], "0\n1\n2", 75),
            ("Loop", "Print 0, 2, 4, 6, 8 by printing `i * 2` in a for loop.",
             [For("i", 0, 5, [P(B("i", "*", 2))])], "0\n2\n4\n6\n8", 100),
            ("While", "Create `x = 5` and count down from 5 to 1 using a while loop.",
             [L("x", I(5)), While(B("x", ">", 0), [P("x"), Aug("x", "-", I(1))])], "5\n4\n3\n2\n1", 100),
            ("Sum", "Create `total = 0`, add 1 to 4 to it with a for loop, print `total` (10).",
             [L("total", I(0)), For("i", 1, 5, [Aug("total", "+", V("i"))]), P("total")], "10", 125),
            ("While", "Create `count = 0` and print 'Hi' 4 times using a while loop.",
             [L("count", I(0)), While(B("count", "<", 4), [P(S("Hi")), Aug("count", "+", I(1))])],
             "Hi\nHi\nHi\nHi", 125),
            ("Loop", "Loop from 1 to 5 and print only the even numbers.",
             [For("i", 1, 6, [If([(B(B("i", "%", 2), "==", 0), [P("i")])])])], "2\n4", 150),
            ("Sum", "Create `total = 0`, add the even numbers from 1 to 10, print `total` (30).",
             [L("total", I(0)),
              For("i", 1, 11, [If([(B(B("i", "%", 2), "==", 0), [Aug("total", "+", V("i"))])])]),
              P("total")], "30", 200),
        ]),
        ("Functions", [
            ("Function", "Define `{say_hello}` that prints 'Hello', then call it.",
             [Def("say_hello", [], [P(S("Hello"))]), Call("say_hello", [])], "Hello", 50),
            ("Function", "Define `{print_num}` that prints 42, then call it.",
             [Def("print_num", [], [P(I(42))]), Call("print_num", [])], "42", 50),
            ("Parameter", "Define `{add_five}(x)` that prints `x + 5`, call it with 10.",
             [Def("add_five", [("x", "int")], [P(B("x", "+", 5))]), Call("add_five", [I(10)])], "15", 75),
            ("Text parameter", "Define `{greet}(name)` that prints 'Hi' and the name, call it with 'CodeStep'.",
             [Def("greet", [("name", "str")], [P(S("Hi"), "name")]), Call("greet", [S("CodeStep")])],
             "Hi CodeStep", 75),
            ("Function", "Define `{double_it}(x)` that prints `x * 2`, call it with 5.",
             [Def("double_it", [("x", "int")], [P(B("x", "*", 2))]), Call("double_it", [I(5)])], "10", 100),
            ("Decision", "Define `{is_positive}(x)` that prints 'Positive' or 'Non-positive', call it with 3.",
             [Def("is_positive", [("x", "int")],
                  [If([(B("x", ">", 0), [P(S("Positive"))])], [P(S("Non-positive"))])]),
              Call("is_positive", [I(3)])], "Positive", 100),
            ("Loop inside", "Define `{count_to_three}` that prints 1 to 3 with a for loop, then call it.",
             [Def("count_to_three", [], [For("i", 1, 4, [P("i")])]), Call("count_to_three", [])],
             "1\n2\n3", 125),
            ("Two parameters", "Define `{print_sum}(a, b)` that prints `a + b`, call it with 4 and 6.",
             [Def("print_sum", [("a", "int"), ("b", "int")], [P(B("a", "+", "b"))]),
              Call("print_sum", [I(4), I(6)])], "10", 125),
            ("Even or odd", "Define `{check_even}(x)` that prints 'Even' or 'Odd', call it with 4.",
             [Def("check_even", [("x", "int")],
                  [If([(B(B("x", "%", 2), "==", 0), [P(S("Even"))])], [P(S("Odd"))])]),
              Call("check_even", [I(4)])], "Even", 150),
            ("Factorial", "Define `{factorial}(n)` that multiplies `result` by 1..n in a loop and prints it; call it with 4 (24).",
             [Def("factorial", [("n", "int")],
                  [L("result", I(1)), For("i", 1, B("n", "+", 1), [Aug("result", "*", V("i"))]), P("result")]),
              Call("factorial", [I(4)])], "24", 200),
        ]),
    ]


def _required_names(lang, program) -> list:
    names = []
    for s in ir.walk(program):
        if isinstance(s, ir.Let) and s.name not in names:
            names.append(s.name)
        elif isinstance(s, ir.Def):
            names.append(lang.fn(s.name))
    return names


def _shared_lessons(lang):
    out = []
    fn_names = {}
    for title, specs in _shared_specs(lang.name):
        tasks = []
        for t_title, prompt, program, expected, xp in specs:
            for s in ir.walk(program):
                if isinstance(s, ir.Def):
                    fn_names[s.name] = lang.fn(s.name)
            required = lang.keywords_for(ir.features(program)) + _required_names(lang, program)
            tasks.append(Task(
                title=t_title,
                prompt=prompt.format(**fn_names),
                answer=lang.render(program),
                expected=expected,
                xp=xp,
                required=required,
                starter=lang.starter(),
            ))
        out.append(Lesson(title, tasks))
    return out


_cache: dict = {}


def lessons_for(lang_id: str) -> list:
    if lang_id not in _cache:
        lang = LANGUAGES[lang_id]
        _cache[lang_id] = _python_lessons() if lang_id == "python" else _shared_lessons(lang)
    return _cache[lang_id]


def format_task(lessons, lesson_no: int, task_no: int) -> str:
    """Task text in the same layout the original app used."""
    t = lessons[lesson_no - 1].tasks[task_no - 1]
    total = len(lessons[lesson_no - 1].tasks)
    return f"Task {task_no}/{total}: {t.title}\n\n{t.prompt}\n\n[{t.xp} XP]"
