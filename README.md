# 🚀 CodeStep

**CodeStep** is a gamified programming learning app — think *Duolingo*, but for coding.  
Made with love, creativity, and Python 🐍 by [Kuba].

## 🎯 What is CodeStep?

CodeStep helps you learn how to code step by step — from basics to more advanced topics — using:

- 📚 Lessons broken into small, digestible steps
- 🧠 Interactive quizzes and mini-projects
- 🔁 Progress tracking and XP system
- 👾 Challenges designed for fun, not boredom

It’s built to be **light**, **offline**, and **fast** — no bloated nonsense.

## 🧩 Features

- ✨ Fully animated UI: splash intro, swipe transitions, glowing gradient buttons, floating particles, a Duolingo-style lesson path, confetti, level-up and lesson-complete celebrations
- 🎨 Each language has its own colour theme that the whole app fades into
- 🖊️ Real code editor: line numbers, syntax highlighting, auto-indent, bracket pairing, `Ctrl+Enter` to run

- 🎓 Beginner-friendly interface
- 🎮 Feels like a game, not school
- 🔧 Built in Python (with 💡 passion)

## 🌍 Languages (v1.1.0)

13 languages, 5 lessons × 10 tasks each (650 tasks):

Python · JavaScript · TypeScript · Java · C · C++ · C# · Go · Rust · Kotlin · Ruby · PHP · Lua

Lessons: **Output → Variables & Math → Conditionals → Loops → Functions**.
Python keeps its original hand-written lessons (including the "fix the code" lesson).

### How your code is checked

- If the language's toolchain is installed (e.g. `node`, `gcc`, `go`, `rustc`, `java`, `dotnet`, `kotlinc`, `php`, `ruby`, `lua`), CodeStep **runs your code** and compares the output, so any correct solution passes. Tasks can also require certain keywords/names (e.g. "use a while loop").
- If not, it compares your code with the reference solution, ignoring spacing, comments and quote style.
- Python always runs: it's built in.

## 🛠️ Tech Stack

- Python 3.10+ and plain tkinter (no UI libraries): everything is drawn on one animated canvas
- `codestep/ui/` – the interface: animation engine (tweens, easing, confetti, glow, gradients), learning-path home screen, code editor with syntax highlighting / auto-indent / bracket pairing
- `codestep/` package:
  - `ir.py` – tiny language-neutral program format the shared lessons are written in
  - `languages.py` – one renderer per language (add a class to add a language)
  - `curriculum.py` – lessons
  - `checker.py` / `runner.py` – checking and running code
  - `progress.py` – save file (`~/Documents/CodeStep/progress_data.json`, v1 saves migrate automatically)

## 📦 Installation

```bash
pip install -r requirements.txt
python main.py
```

Build the Windows exe:

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --name CodeStep main.py
```

Run the tests (every answer in every language is compiled and run where the toolchain exists):

```bash
python -m pytest -q
```

## 📅 Roadmap

- [x] Core lesson system  
- [x] Basic XP and level-up logic  
- [x] Code editor integration  
- [ ] Leaderboards / community  
- [x] More languages (13 so far)

## 🧪 Beta Testers

Wanna help shape the future of CodeStep?  
DM me on Discord: `@kuba390` or just open an issue here.

## 📜 License

MIT License — feel free to contribute, fork, remix, whatever.

---

Made by Kuba with ❤️
