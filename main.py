"""CodeStep - learn to code step by step.

Rebuilt from the v1.0.2-alpha release and extended to 13 languages.
"""
import os
import sys
import threading
import tkinter as tk
from tkinter import messagebox

import customtkinter as ctk

from codestep import __version__ as CURRENT_VERSION
from codestep import progress as prog
from codestep.checker import CheckResult, check
from codestep.curriculum import format_task, lessons_for
from codestep.languages import LANGUAGES
from codestep.runner import find_runner

try:
    import requests
except ImportError:  # update check is optional
    requests = None

try:
    from PIL import Image
except ImportError:
    Image = None

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

RELEASES_API = "https://api.github.com/repos/jakubek382/CodeStep/releases/latest"


def resource(name: str) -> str:
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "assets", name)


def load_icon(name: str):
    if Image is None:
        return None
    try:
        return ctk.CTkImage(Image.open(resource(name)), size=(20, 20))
    except (OSError, ValueError):
        return None


def version_to_tuple(version: str):
    return tuple(int(p) for p in version.split("-")[0].split("."))


def check_for_updates():
    if requests is None:
        messagebox.showwarning("Update Check Failed", "The 'requests' package is not installed.")
        return
    try:
        r = requests.get(RELEASES_API, timeout=10)
        r.raise_for_status()
        latest = r.json()
        latest_version = latest.get("tag_name", "").lstrip("v")
        if version_to_tuple(latest_version) > version_to_tuple(CURRENT_VERSION):
            messagebox.showinfo(
                "Update Available",
                f"A new version ({latest_version}) is available!\n"
                f"Current version: {CURRENT_VERSION}\nDownload from: {latest.get('html_url')}")
        else:
            messagebox.showinfo("Up to Date", f"You are running the latest version ({CURRENT_VERSION})")
    except Exception as e:  # noqa: BLE001 - show any network/parse error
        messagebox.showwarning("Update Check Failed", f"Could not check for updates: {e}")


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.geometry("900x800")
        self.minsize(760, 640)
        try:
            self.iconbitmap(resource("codestep.ico"))
        except tk.TclError:
            pass

        try:
            self.progress = prog.load()
        except OSError as e:
            messagebox.showerror("Error", f"Cannot create CodeStep folder in Documents: {e}")
            sys.exit(1)

        lang_id = self.progress.get("language", "python")
        self.lang = LANGUAGES.get(lang_id, LANGUAGES["python"])
        self.lesson_no = 1
        self.task_no = 1
        self.lesson_buttons = []

        self._build_menu()
        self._build_lesson_view()
        self.show_menu()

    # ------------------------------------------------------------ properties
    @property
    def lessons(self):
        return lessons_for(self.lang.id)

    @property
    def task(self):
        return self.lessons[self.lesson_no - 1].tasks[self.task_no - 1]

    def save(self):
        try:
            prog.save(self.progress)
        except OSError as e:
            messagebox.showerror("Error", f"Cannot save progress: {e}")

    # ------------------------------------------------------------ menu
    def _build_menu(self):
        self.menu_frame = ctk.CTkFrame(self, fg_color="#2b2b2b")
        self.menu_label = ctk.CTkLabel(self.menu_frame, text="", font=("Arial", 20, "bold"),
                                       text_color="#ffffff")
        self.menu_label.pack(pady=(20, 10))

        row = ctk.CTkFrame(self.menu_frame, fg_color="transparent")
        row.pack(pady=5)
        ctk.CTkLabel(row, text="Language:", font=("Arial", 14), text_color="#ffffff").pack(side="left", padx=6)
        names = [l.name for l in LANGUAGES.values()]
        self.lang_menu = ctk.CTkOptionMenu(row, values=names, command=self.on_language,
                                           width=180, font=("Arial", 14))
        self.lang_menu.set(self.lang.name)
        self.lang_menu.pack(side="left", padx=6)

        self.streak_label = ctk.CTkLabel(self.menu_frame, text="", font=("Arial", 14), text_color="#aaaaaa")
        self.streak_label.pack(pady=(10, 2))
        self.runner_label = ctk.CTkLabel(self.menu_frame, text="", font=("Arial", 12),
                                         text_color="#888888", wraplength=600)
        self.runner_label.pack(pady=(0, 10))

        self.lessons_box = ctk.CTkFrame(self.menu_frame, fg_color="transparent")
        self.lessons_box.pack(pady=5)

        btn = dict(compound="left", font=("Arial", 14), width=280, height=40, corner_radius=10)
        ctk.CTkButton(self.menu_frame, text="Check for Updates", command=check_for_updates,
                      image=load_icon("update.png"), **btn).pack(pady=(15, 5))
        ctk.CTkButton(self.menu_frame, text="Exit", command=self.quit, image=load_icon("exit.png"),
                      fg_color="#bf3a3a", hover_color="#823232", **btn).pack(pady=5)
        ctk.CTkLabel(self.menu_frame, text=f"v{CURRENT_VERSION}", font=("Arial", 11),
                     text_color="#666666").pack(side="bottom", pady=8)

    def _rebuild_lesson_buttons(self):
        for b in self.lesson_buttons:
            b.destroy()
        self.lesson_buttons = []
        lp = prog.lang_progress(self.progress, self.lang.id)
        for i, lesson in enumerate(self.lessons, 1):
            done = lp["completed_tasks"].get(str(i), 0)
            total = len(lesson.tasks)
            mark = "  ✓" if done >= total else (f"  {done}/{total}" if done else "")
            b = ctk.CTkButton(
                self.lessons_box, text=f"{i}. {lesson.title}{mark}",
                command=lambda n=i: self.select_lesson(n), image=load_icon(f"lesson{i}.png"),
                compound="left", font=("Arial", 14), width=280, height=40, corner_radius=10,
                state="normal" if i in lp["unlocked"] else "disabled")
            b.pack(pady=5)
            self.lesson_buttons.append(b)

    def on_language(self, name):
        self.lang = next(l for l in LANGUAGES.values() if l.name == name)
        self.progress["language"] = self.lang.id
        prog.lang_progress(self.progress, self.lang.id)
        self.save()
        self.show_menu()

    def show_menu(self):
        self.lesson_frame.pack_forget()
        self.menu_frame.pack(fill="both", expand=True)
        self.lang_menu.set(self.lang.name)
        self.title(f"CodeStep: Learn {self.lang.name}")
        self.menu_label.configure(text=f"CodeStep: Learn {self.lang.name}\nWelcome! Choose a lesson:")
        runner = find_runner(self.lang)
        if runner:
            self.runner_label.configure(text=f"Your {self.lang.name} code runs with {runner.label}.")
        else:
            self.runner_label.configure(
                text=f"No {self.lang.name} toolchain found - answers are compared with the reference "
                     f"solution. Install {self.lang.install_hint} to run real code.")
        self._rebuild_lesson_buttons()
        self.update_ui()

    def select_lesson(self, lesson_no):
        if lesson_no in prog.lang_progress(self.progress, self.lang.id)["unlocked"]:
            self.show_lesson(lesson_no)
        else:
            messagebox.showwarning("Locked", "Complete the previous lesson first!")

    # ------------------------------------------------------------ lesson view
    def _build_lesson_view(self):
        f = self.lesson_frame = ctk.CTkFrame(self, fg_color="#1e1e1e")
        self.lesson_status_label = ctk.CTkLabel(f, text="", font=("Arial", 12), text_color="#aaaaaa")
        self.lesson_status_label.pack(pady=(10, 0), anchor="w", padx=20)
        self.progress_bar = ctk.CTkProgressBar(f, width=800, height=10, progress_color="#3a7ebf")
        self.progress_bar.pack(pady=(5, 10), padx=20, fill="x")
        self.progress_bar.set(0)
        self.lesson_label = ctk.CTkLabel(f, text="", font=("Consolas", 14), text_color="#ffffff",
                                         wraplength=820, justify="left")
        self.lesson_label.pack(pady=10, padx=20, anchor="w")

        ctk.CTkLabel(f, text="Enter your code below:", font=("Arial", 12),
                     text_color="#ffffff").pack(pady=(10, 5), padx=20, anchor="w")
        self.code_text = ctk.CTkTextbox(f, height=260, font=("Consolas", 14), fg_color="#252526",
                                        text_color="#ffffff", border_width=1, corner_radius=5, wrap="none")
        self.code_text.pack(pady=5, padx=20, fill="both", expand=True)
        self.code_text.bind("<Tab>", self._insert_tab)

        ctk.CTkLabel(f, text="Console Output:", font=("Arial", 12),
                     text_color="#ffffff").pack(pady=(10, 5), padx=20, anchor="w")
        self.console_output = ctk.CTkTextbox(f, height=110, font=("Consolas", 14), fg_color="#1e1e1e",
                                             text_color="#4ec9b0", border_width=1, corner_radius=5)
        self.console_output.pack(pady=5, padx=20, fill="x")
        self.console_output.configure(state="disabled")

        bf = ctk.CTkFrame(f, fg_color="transparent")
        bf.pack(pady=15)
        b = dict(font=("Arial", 14), width=150, height=40, corner_radius=10)
        self.check_button = ctk.CTkButton(bf, text="Check Code", command=self.check_code, **b)
        self.check_button.pack(side="left", padx=8)
        ctk.CTkButton(bf, text="Show Solution", command=self.show_solution, fg_color="#5a5a5a",
                      hover_color="#444444", **b).pack(side="left", padx=8)
        ctk.CTkButton(bf, text="Reset Code", command=self.reset_code, fg_color="#5a5a5a",
                      hover_color="#444444", **b).pack(side="left", padx=8)
        ctk.CTkButton(bf, text="Back to Menu", command=self.show_menu, fg_color="#bf3a3a",
                      hover_color="#823232", **b).pack(side="left", padx=8)

    def _insert_tab(self, _event):
        self.code_text.insert("insert", self.lang.indent)
        return "break"

    def set_console(self, text):
        self.console_output.configure(state="normal")
        self.console_output.delete("1.0", tk.END)
        self.console_output.insert(tk.END, text)
        self.console_output.configure(state="disabled")

    def reset_code(self):
        self.code_text.delete("1.0", tk.END)
        self.code_text.insert("1.0", self.task.starter)

    def show_lesson(self, lesson_no):
        lp = prog.lang_progress(self.progress, self.lang.id)
        done = lp["completed_tasks"].get(str(lesson_no), 0)
        total = len(self.lessons[lesson_no - 1].tasks)
        self.lesson_no = lesson_no
        self.task_no = 1 if done >= total else done + 1
        self.show_task()
        self.menu_frame.pack_forget()
        self.lesson_frame.pack(fill="both", expand=True)

    def show_task(self):
        self.lesson_label.configure(text=format_task(self.lessons, self.lesson_no, self.task_no))
        self.reset_code()
        self.check_button.configure(state="normal", text="Check Code")
        self.set_console("")
        self.update_ui()

    def show_solution(self):
        if messagebox.askyesno("Show Solution", "Put the reference solution in the editor?"):
            self.code_text.delete("1.0", tk.END)
            self.code_text.insert("1.0", self.task.answer)

    def check_code(self):
        code = self.code_text.get("1.0", tk.END).rstrip()
        if not code.strip():
            messagebox.showwarning("Empty Code", "Please enter code before checking!")
            return
        self.check_button.configure(state="disabled", text="Running...")
        self.set_console("Running...")
        lang, task = self.lang, self.task

        box = []

        def work():  # runs off the UI thread; never touch Tk here
            try:
                box.append(check(lang, task, code))
            except Exception as e:  # noqa: BLE001
                box.append(CheckResult(False, f"Internal error while checking: {e}"))

        worker = threading.Thread(target=work, daemon=True)
        worker.start()

        def poll():
            if box:
                self._on_checked(box[0])
            else:
                self.after(50, poll)

        self.after(50, poll)

    def _on_checked(self, res):
        self.check_button.configure(state="normal", text="Check Code")
        self.set_console(res.output)
        if not res.ok:
            messagebox.showerror("Error", res.message)
            return
        lesson = self.lessons[self.lesson_no - 1]
        accepted, leveled, why = prog.record_task(
            self.progress, self.lang.id, self.lesson_no, self.task_no, res.xp,
            len(lesson.tasks), len(self.lessons))
        if not accepted:
            messagebox.showwarning("Limit", why)
            return
        messagebox.showinfo("Success", res.message)
        if leveled:
            messagebox.showinfo("Congratulations", f"Level Up! You reached Level {self.progress['level']}!")
        self.update_ui()
        if self.task_no < len(lesson.tasks):
            self.task_no += 1
            self.show_task()
        else:
            messagebox.showinfo("Lesson Complete", "Congratulations! You completed the lesson!")
            self.show_menu()

    # ------------------------------------------------------------ status
    def update_ui(self):
        p = self.progress
        xp, level = p["xp"], prog.level_for(p["xp"])
        nxt = level * prog.XP_PER_LEVEL
        self.streak_label.configure(
            text=f"Streak: {p['streak']} days | Lessons today: {p['daily_lessons']}/{prog.DAILY_LESSON_LIMIT}"
                 f" | Level: {level} | XP: {xp}/{nxt}")
        self.lesson_status_label.configure(
            text=f"{self.lang.name} · Lesson {self.lesson_no} | Level: {level} | XP: {xp}/{nxt}")
        self.progress_bar.set((xp % prog.XP_PER_LEVEL) / prog.XP_PER_LEVEL)


if __name__ == "__main__":
    App().mainloop()
