"""Developer CLI dialog for the Tk control panel.

This dialog is intentionally isolated from the general dialog module because it
owns subprocess execution, command parsing, and a single-flight background job.
The rest of the Tk dialog collection should not need to import subprocess
helpers just to expose ordinary settings or review windows.
"""

from __future__ import annotations

import shlex
import subprocess
from tkinter import BOTH, END, LEFT, RIGHT, WORD, X, StringVar, Text, Toplevel
from tkinter import ttk
from typing import Any

from api_launcher.paths import PROJECT_ROOT
from frontends.tk.background_jobs import single_flight_job_is_active, start_single_flight_thread
from frontends.tk.background_job_policies import MAX_TK_DEVELOPER_CLI_BACKGROUND_JOBS
from frontends.tk.ui_config import COLORS


class DeveloperCliDialog:
    def __init__(self, ui: Any):
        # CLI windows need the main UI's translation, status_var, and Tk after.
        # Keeping subprocess details here prevents launcher_ui/dialogs from
        # becoming another command-runner owner.
        self.ui = ui
        self.root = ui.root
        self.dialog = Toplevel(self.root)
        self.dialog.title(self.ui.tr("開發者 CLI", "Developer CLI"))
        self.dialog.configure(bg=COLORS["panel"])
        self.dialog.geometry("860x560")
        self.dialog.transient(self.root)

        self.command_var = StringVar(value="python APIkeys_collection.py --help")
        self._build()

    @staticmethod
    def split_command(command: str) -> list[str]:
        # shlex is the boundary between one UI string and argv. Keep it
        # testable so command quoting regressions do not require opening Tk.
        return shlex.split(command)

    def _build(self) -> None:
        ttk.Label(self.dialog, text=self.ui.tr("開發者 CLI", "Developer CLI"), style="DetailTitle.TLabel").pack(
            anchor="w", padx=24, pady=(22, 8)
        )
        ttk.Label(
            self.dialog,
            text=self.ui.tr(
                f"工作目錄：{PROJECT_ROOT}\n輸入單次命令後按執行，輸出會顯示在下方。",
                f"Working directory: {PROJECT_ROOT}\nEnter a one-shot command and run it; output appears below.",
            ),
            style="DetailMuted.TLabel",
        ).pack(anchor="w", fill=X, padx=24, pady=(0, 12))
        self.command_entry = ttk.Entry(self.dialog, textvariable=self.command_var, style="Search.TEntry")
        self.command_entry.pack(fill=X, padx=24, pady=(0, 12))
        self.output = Text(
            self.dialog,
            wrap=WORD,
            bg=COLORS["bg"],
            fg=COLORS["text"],
            relief="flat",
            padx=14,
            pady=12,
            font=("Consolas", 11),
        )
        self.output.pack(fill=BOTH, expand=True, padx=24, pady=(0, 12))
        self.output.insert("1.0", self.ui.tr("尚未執行命令。", "No command has been run yet."))
        self.output.configure(state="disabled")

        actions = ttk.Frame(self.dialog, style="Panel.TFrame")
        actions.pack(fill=X, padx=24, pady=(0, 18))
        self.command_entry.bind("<Return>", lambda _event: self.run_command())
        ttk.Button(actions, text=self.ui.tr("執行", "Run"), style="Action.TButton", command=self.run_command).pack(
            side=LEFT, padx=(0, 10)
        )
        ttk.Button(actions, text=self.ui.tr("清空", "Clear"), style="Action.TButton", command=lambda: self.set_output("")).pack(
            side=LEFT, padx=(0, 10)
        )
        ttk.Button(actions, text=self.ui.tr("關閉", "Close"), style="Action.TButton", command=self.dialog.destroy).pack(
            side=RIGHT
        )
        self.command_entry.focus_set()

    def append_output(self, text: str) -> None:
        self.output.configure(state="normal")
        self.output.insert(END, text)
        self.output.see(END)
        self.output.configure(state="disabled")

    def set_output(self, text: str) -> None:
        self.output.configure(state="normal")
        self.output.delete("1.0", END)
        self.output.insert("1.0", text)
        self.output.configure(state="disabled")

    def run_command(self) -> None:
        command = self.command_var.get().strip()
        if not command:
            return
        try:
            args = self.split_command(command)
        except ValueError as exc:
            self.set_output(self.ui.tr(f"命令解析失敗：{exc}", f"Command parse failed: {exc}"))
            return
        job_key = ("developer_cli", "command", "")
        if single_flight_job_is_active(
            self,
            job_key,
            active_jobs_attr="developer_cli_active_jobs",
            on_duplicate=lambda: self.ui.status_var.set(
                self.ui.tr("CLI 命令仍在執行中，請等待目前命令完成。", "CLI command is still running; wait for it to finish.")
            ),
        ):
            return
        self.set_output(f"$ {command}\n\n")
        self.ui.status_var.set(self.ui.tr(f"正在執行 CLI：{command}", f"Running CLI: {command}"))
        start_single_flight_thread(
            self,
            job_key,
            self._run_command_worker,
            (args,),
            active_jobs_attr="developer_cli_active_jobs",
            active_jobs_lock_attr="developer_cli_active_jobs_lock",
            max_active_jobs=MAX_TK_DEVELOPER_CLI_BACKGROUND_JOBS,
            on_duplicate=lambda: self.ui.status_var.set(
                self.ui.tr("CLI 命令仍在執行中，請等待目前命令完成。", "CLI command is still running; wait for it to finish.")
            ),
        )

    def _run_command_worker(self, args: list[str]) -> None:
        try:
            completed = subprocess.run(
                args,
                cwd=PROJECT_ROOT,
                text=True,
                capture_output=True,
                timeout=300,
                check=False,
            )
            text = ""
            if completed.stdout:
                text += completed.stdout
            if completed.stderr:
                text += ("\n[stderr]\n" if text else "[stderr]\n") + completed.stderr
            text += f"\n[exit code] {completed.returncode}\n"
            self.root.after(0, lambda: self.append_output(text))
            self.root.after(
                0,
                lambda: self.ui.status_var.set(
                    self.ui.tr(f"CLI 執行完成：exit {completed.returncode}", f"CLI finished: exit {completed.returncode}")
                ),
            )
        except Exception as exc:
            error = str(exc)
            self.root.after(0, lambda: self.append_output(f"\n[error] {error}\n"))
            self.root.after(0, lambda: self.ui.status_var.set(self.ui.tr(f"CLI 執行失敗：{error}", f"CLI failed: {error}")))
