from __future__ import annotations

from pathlib import Path
import csv
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .browser_operator import BrowserOperatorError, FlowBrowserOperator
from .models import Project
from .prompt_engine import build_initial_frames, build_next_prompt, update_continuity_memory
from .vision import VisionError, analyze_frame


class FlowAutopilotApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Flow Repair Autopilot")
        self.geometry("1180x780")
        self.minsize(980, 640)
        self.project: Project | None = None
        self.current_index = -1
        self._build_ui()

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        toolbar = ttk.Frame(self, padding=8)
        toolbar.grid(row=0, column=0, sticky="ew")
        ttk.Button(toolbar, text="Новый проект", command=self.new_project).pack(side="left")
        ttk.Button(toolbar, text="Открыть", command=self.open_project).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Сохранить", command=self.save_project).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Экспорт CSV", command=self.export_csv).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Настройки", command=self.open_settings).pack(side="right")

        main = ttk.PanedWindow(self, orient="horizontal")
        main.grid(row=1, column=0, sticky="nsew")

        left = ttk.Frame(main, padding=8)
        right = ttk.Frame(main, padding=8)
        main.add(left, weight=1)
        main.add(right, weight=2)

        left.columnconfigure(0, weight=1)
        right.columnconfigure(0, weight=1)
        right.rowconfigure(2, weight=1)

        self.meta_frame = ttk.LabelFrame(left, text="Проект", padding=8)
        self.meta_frame.grid(row=0, column=0, sticky="ew")
        self.title_var = tk.StringVar(value="Ремонт комнаты")
        self.aspect_var = tk.StringVar(value="16:9")
        self.count_var = tk.IntVar(value=8)
        self._entry(self.meta_frame, "Название", self.title_var, 0)
        self._entry(self.meta_frame, "Формат", self.aspect_var, 1)
        self._spin(self.meta_frame, "Кадров", self.count_var, 2)

        ttk.Label(left, text="Концепция").grid(row=1, column=0, sticky="w", pady=(10, 0))
        self.concept_text = tk.Text(left, height=5, wrap="word")
        self.concept_text.grid(row=2, column=0, sticky="ew")
        self.concept_text.insert("1.0", "Таймлапс ремонта одной комнаты от старого состояния до уютного финала.")

        ttk.Label(left, text="Стиль").grid(row=3, column=0, sticky="w", pady=(10, 0))
        self.style_text = tk.Text(left, height=4, wrap="word")
        self.style_text.grid(row=4, column=0, sticky="ew")
        self.style_text.insert("1.0", "реалистичный документальный ремонт, одна и та же камера, естественный свет, аккуратная кинематографичность")

        ttk.Label(left, text="Этапы, по одному в строке").grid(row=5, column=0, sticky="w", pady=(10, 0))
        self.stages_text = tk.Text(left, height=10, wrap="word")
        self.stages_text.grid(row=6, column=0, sticky="nsew")
        for line in [
            "исходное состояние комнаты до ремонта",
            "демонтаж старой отделки",
            "черновая подготовка стен и пола",
            "выравнивание и грунтовка",
            "укладка пола",
            "покраска стен",
            "установка мебели и света",
            "финальный чистый результат",
        ]:
            self.stages_text.insert("end", line + "\n")
        left.rowconfigure(6, weight=1)
        ttk.Button(left, text="Создать план кадров", command=self.create_frame_plan).grid(row=7, column=0, sticky="ew", pady=8)

        columns = ("index", "stage", "status")
        self.frame_table = ttk.Treeview(right, columns=columns, show="headings", height=10)
        self.frame_table.heading("index", text="#")
        self.frame_table.heading("stage", text="Этап")
        self.frame_table.heading("status", text="Статус")
        self.frame_table.column("index", width=50, anchor="center")
        self.frame_table.column("stage", width=440)
        self.frame_table.column("status", width=110)
        self.frame_table.grid(row=0, column=0, sticky="ew")
        self.frame_table.bind("<<TreeviewSelect>>", self.on_frame_select)

        actions = ttk.Frame(right)
        actions.grid(row=1, column=0, sticky="ew", pady=8)
        for label, command in [
            ("Отправить в Flow", self.send_to_flow),
            ("Сохранить скриншот Flow", self.capture_flow),
            ("Выбрать картинку", self.choose_image),
            ("Анализировать кадр", self.analyze_selected),
            ("Сделать следующий промпт", self.make_next_prompt),
        ]:
            ttk.Button(actions, text=label, command=command).pack(side="left", padx=3)

        editor = ttk.Notebook(right)
        editor.grid(row=2, column=0, sticky="nsew")
        self.prompt_text = self._tab_text(editor, "Промпт")
        self.eval_text = self._tab_text(editor, "Анализ")
        self.notes_text = self._tab_text(editor, "Заметки")
        self.memory_text = self._tab_text(editor, "Память постоянства")

        bottom = ttk.Frame(right)
        bottom.grid(row=3, column=0, sticky="ew", pady=(8, 0))
        ttk.Button(bottom, text="Применить правки к кадру", command=self.apply_frame_edits).pack(side="left")
        self.status_var = tk.StringVar(value="Готов.")
        ttk.Label(bottom, textvariable=self.status_var).pack(side="right")

    def _entry(self, parent: ttk.Frame, label: str, variable: tk.StringVar, row: int) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=2)
        ttk.Entry(parent, textvariable=variable).grid(row=row, column=1, sticky="ew", pady=2)
        parent.columnconfigure(1, weight=1)

    def _spin(self, parent: ttk.Frame, label: str, variable: tk.IntVar, row: int) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=2)
        ttk.Spinbox(parent, from_=2, to=30, textvariable=variable, width=8).grid(row=row, column=1, sticky="w", pady=2)

    def _tab_text(self, notebook: ttk.Notebook, label: str) -> tk.Text:
        frame = ttk.Frame(notebook)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)
        text = tk.Text(frame, wrap="word", undo=True)
        text.grid(row=0, column=0, sticky="nsew")
        notebook.add(frame, text=label)
        return text

    def _project_from_form(self, folder: str) -> Project:
        return Project(
            title=self.title_var.get().strip() or "Flow project",
            concept=self.concept_text.get("1.0", "end").strip(),
            style=self.style_text.get("1.0", "end").strip(),
            aspect_ratio=self.aspect_var.get().strip() or "16:9",
            frame_count=int(self.count_var.get()),
            stages_text=self.stages_text.get("1.0", "end").strip(),
            folder=folder,
        )

    def new_project(self) -> None:
        folder = filedialog.askdirectory(title="Папка проекта")
        if not folder:
            return
        self.project = self._project_from_form(folder)
        self.project.save()
        self.status("Проект создан.")
        self.refresh_table()

    def open_project(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("Flow project", "project.json"), ("JSON", "*.json")])
        if not path:
            return
        self.project = Project.load(path)
        self.load_project_into_form()
        self.refresh_table()
        self.status("Проект открыт.")

    def save_project(self) -> None:
        if not self.project:
            self.new_project()
            return
        self.apply_frame_edits(silent=True)
        self.project.title = self.title_var.get().strip()
        self.project.concept = self.concept_text.get("1.0", "end").strip()
        self.project.style = self.style_text.get("1.0", "end").strip()
        self.project.aspect_ratio = self.aspect_var.get().strip()
        self.project.frame_count = int(self.count_var.get())
        self.project.stages_text = self.stages_text.get("1.0", "end").strip()
        self.project.continuity_memory = self.memory_text.get("1.0", "end").strip()
        self.project.save()
        self.status("Сохранено.")

    def load_project_into_form(self) -> None:
        if not self.project:
            return
        self.title_var.set(self.project.title)
        self.aspect_var.set(self.project.aspect_ratio)
        self.count_var.set(self.project.frame_count)
        self._replace(self.concept_text, self.project.concept)
        self._replace(self.style_text, self.project.style)
        self._replace(self.stages_text, self.project.stages_text)
        self._replace(self.memory_text, self.project.continuity_memory)

    def create_frame_plan(self) -> None:
        if not self.project:
            folder = filedialog.askdirectory(title="Папка проекта")
            if not folder:
                return
            self.project = self._project_from_form(folder)
        else:
            self.project.title = self.title_var.get().strip()
            self.project.concept = self.concept_text.get("1.0", "end").strip()
            self.project.style = self.style_text.get("1.0", "end").strip()
            self.project.aspect_ratio = self.aspect_var.get().strip()
            self.project.frame_count = int(self.count_var.get())
            self.project.stages_text = self.stages_text.get("1.0", "end").strip()
        self.project.frames = build_initial_frames(self.project)
        self.project.save()
        self.refresh_table()
        self.status("План кадров создан.")

    def refresh_table(self) -> None:
        self.frame_table.delete(*self.frame_table.get_children())
        if not self.project:
            return
        for frame in self.project.frames:
            self.frame_table.insert("", "end", iid=str(frame.index - 1), values=(frame.index, frame.stage, frame.status))

    def on_frame_select(self, event=None) -> None:
        selected = self.frame_table.selection()
        if not selected or not self.project:
            return
        self.current_index = int(selected[0])
        frame = self.project.frames[self.current_index]
        self._replace(self.prompt_text, frame.prompt)
        self._replace(self.eval_text, frame.evaluation)
        self._replace(self.notes_text, frame.notes)
        self._replace(self.memory_text, self.project.continuity_memory)
        self.status(f"Выбран кадр {frame.index}.")

    def apply_frame_edits(self, silent: bool = False) -> None:
        if not self.project or self.current_index < 0:
            return
        frame = self.project.frames[self.current_index]
        frame.prompt = self.prompt_text.get("1.0", "end").strip()
        frame.evaluation = self.eval_text.get("1.0", "end").strip()
        frame.notes = self.notes_text.get("1.0", "end").strip()
        self.project.continuity_memory = self.memory_text.get("1.0", "end").strip()
        self.project.save()
        self.refresh_table()
        if not silent:
            self.status("Правки применены.")

    def send_to_flow(self) -> None:
        if not self._require_project_frame():
            return
        self.apply_frame_edits(silent=True)
        frame = self.project.frames[self.current_index]
        self._run_thread("Отправляю промпт во Flow...", lambda: self._send_to_flow(frame.prompt))

    def _send_to_flow(self, prompt: str) -> None:
        assert self.project
        operator = FlowBrowserOperator(self.project.settings, Path(self.project.folder))
        operator.send_prompt(prompt)
        self.after(0, lambda: self.status("Промпт отправлен во Flow."))

    def capture_flow(self) -> None:
        if not self._require_project_frame():
            return
        frame = self.project.frames[self.current_index]
        output = self.project.images_dir / f"frame_{frame.index:03d}.png"
        self._run_thread("Сохраняю скриншот Flow...", lambda: self._capture(output))

    def _capture(self, output: Path) -> None:
        assert self.project
        operator = FlowBrowserOperator(self.project.settings, Path(self.project.folder))
        path = operator.save_result_screenshot(output)
        frame = self.project.frames[self.current_index]
        frame.image_path = str(path)
        frame.status = "captured"
        self.project.save()
        self.after(0, self.refresh_table)
        self.after(0, lambda: self.status(f"Скриншот сохранен: {path.name}"))

    def choose_image(self) -> None:
        if not self._require_project_frame():
            return
        path = filedialog.askopenfilename(filetypes=[("Images", "*.png *.jpg *.jpeg *.webp"), ("All files", "*.*")])
        if not path:
            return
        frame = self.project.frames[self.current_index]
        frame.image_path = path
        frame.status = "captured"
        self.project.save()
        self.refresh_table()
        self.status("Картинка привязана к кадру.")

    def analyze_selected(self) -> None:
        if not self._require_project_frame():
            return
        self.apply_frame_edits(silent=True)
        self._run_thread("Локальная модель анализирует кадр...", self._analyze_current)

    def _analyze_current(self) -> None:
        assert self.project
        result = analyze_frame(self.project, self.current_index)
        frame = self.project.frames[self.current_index]
        frame.evaluation = result
        frame.status = "analyzed"
        update_continuity_memory(self.project, result)
        self.project.save()
        self.after(0, lambda: self._replace(self.eval_text, result))
        self.after(0, lambda: self._replace(self.memory_text, self.project.continuity_memory))
        self.after(0, self.refresh_table)
        self.after(0, lambda: self.status("Анализ готов."))

    def make_next_prompt(self) -> None:
        if not self._require_project_frame():
            return
        prompt = build_next_prompt(self.project, self.current_index)
        if not prompt:
            messagebox.showinfo("Готово", "Это последний кадр, следующего промпта нет.")
            return
        self.project.save()
        self.refresh_table()
        next_index = self.current_index + 1
        self.frame_table.selection_set(str(next_index))
        self.on_frame_select()
        self.status("Следующий промпт обновлен по фактическому кадру.")

    def export_csv(self) -> None:
        if not self.project:
            return
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")])
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8-sig") as file:
            writer = csv.writer(file)
            writer.writerow(["index", "stage", "goal", "prompt", "image_path", "evaluation", "notes", "next_step", "status"])
            for frame in self.project.frames:
                writer.writerow([
                    frame.index,
                    frame.stage,
                    frame.goal,
                    frame.prompt,
                    frame.image_path,
                    frame.evaluation,
                    frame.notes,
                    frame.next_step,
                    frame.status,
                ])
        self.status("CSV экспортирован.")

    def open_settings(self) -> None:
        if not self.project:
            folder = filedialog.askdirectory(title="Папка проекта")
            if not folder:
                return
            self.project = self._project_from_form(folder)
        SettingsDialog(self, self.project)

    def _run_thread(self, label: str, action) -> None:
        self.status(label)

        def runner():
            try:
                action()
            except (BrowserOperatorError, VisionError, Exception) as exc:
                error_text = str(exc)
                self.after(0, lambda: messagebox.showerror("Ошибка", error_text))
                self.after(0, lambda: self.status("Нужна ручная проверка."))

        threading.Thread(target=runner, daemon=True).start()

    def _require_project_frame(self) -> bool:
        if not self.project:
            messagebox.showinfo("Нет проекта", "Сначала создай или открой проект.")
            return False
        if self.current_index < 0:
            messagebox.showinfo("Нет кадра", "Выбери кадр в таблице.")
            return False
        return True

    def _replace(self, text: tk.Text, value: str) -> None:
        text.delete("1.0", "end")
        text.insert("1.0", value or "")

    def status(self, value: str) -> None:
        self.status_var.set(value)


class SettingsDialog(tk.Toplevel):
    def __init__(self, parent: FlowAutopilotApp, project: Project) -> None:
        super().__init__(parent)
        self.parent = parent
        self.project = project
        self.title("Настройки")
        self.geometry("760x520")
        self.vars: dict[str, tk.StringVar] = {}
        self._build()

    def _build(self) -> None:
        frame = ttk.Frame(self, padding=12)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(1, weight=1)
        fields = [
            ("vision_backend", "Vision backend: ollama или lm_studio"),
            ("ollama_url", "Ollama URL"),
            ("ollama_model", "Ollama model"),
            ("lm_studio_url", "LM Studio URL"),
            ("lm_studio_model", "LM Studio model"),
            ("flow_url", "Flow URL"),
            ("chrome_profile_dir", "Chrome profile folder"),
            ("prompt_field_selector", "Prompt field selector"),
            ("generate_button_selector", "Generate button selector"),
            ("result_selector", "Result selector"),
            ("generation_wait_seconds", "Wait seconds"),
        ]
        for row, (attr, label) in enumerate(fields):
            ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", pady=4)
            var = tk.StringVar(value=str(getattr(self.project.settings, attr)))
            self.vars[attr] = var
            ttk.Entry(frame, textvariable=var).grid(row=row, column=1, sticky="ew", pady=4)
        ttk.Button(frame, text="Сохранить настройки", command=self.save).grid(row=len(fields), column=1, sticky="e", pady=12)

    def save(self) -> None:
        for attr, var in self.vars.items():
            value = var.get().strip()
            if attr == "generation_wait_seconds":
                setattr(self.project.settings, attr, int(value or "90"))
            else:
                setattr(self.project.settings, attr, value)
        self.project.save()
        self.parent.status("Настройки сохранены.")
        self.destroy()


def main() -> None:
    app = FlowAutopilotApp()
    app.mainloop()


if __name__ == "__main__":
    main()
