"""Tk dynamic dataset-bound form dialog.

這個模組只負責把 `api_launcher.bound_form.BoundFormSpec` 畫成 Tk 表單。
界域推論、欄位角色判斷、URL 改寫都留在後端服務層，避免 Tk UI 再度長成巨型檔案。
"""

from __future__ import annotations

from tkinter import BOTH, RIGHT, WORD, X, BooleanVar, StringVar, Text, Tk, Toplevel, messagebox
from tkinter import ttk

from api_launcher.bound_form import BoundFormField, BoundFormSpec, source_download_bounds_from_form_values
from api_launcher.source_download import SourceDownloadBounds
from frontends.tk.ui_config import COLORS


class DatasetBoundFormDialog:
    """依 schema probe 結果動態產生界域輸入表單。

    呼叫端只需要把後端產出的 BoundFormSpec 傳進來，dialog 會回傳
    SourceDownloadBounds。這讓未來 Qt 版可以重用同一份 form spec，而不用重寫
    「哪些欄位可當時間/空間界域」的產品邏輯。
    """

    def __init__(self, parent: Tk, spec: BoundFormSpec, tr=lambda zh, _en: zh):
        self.parent = parent
        self.spec = spec
        self.tr = tr
        self.result: SourceDownloadBounds | None = None
        self.window = Toplevel(parent)
        self.window.title(self.tr("資料集界域設定", "Dataset bounds"))
        self.window.transient(parent)
        self.window.grab_set()
        self.window.configure(bg=COLORS["panel"])
        self.window.minsize(720, 640)
        self.vars: dict[str, StringVar] = {}
        self.multi_vars: dict[str, dict[str, BooleanVar]] = {}

        self._build()
        self.window.bind("<Escape>", lambda _event: self.cancel())
        self.window.protocol("WM_DELETE_WINDOW", self.cancel)
        self.window.wait_window()

    def _build(self) -> None:
        frame = ttk.Frame(self.window, style="Panel.TFrame")
        frame.pack(fill=BOTH, expand=True, padx=22, pady=22)

        ttk.Label(frame, text=self.tr("依資料欄位動態設定下載界域", "Define bounds from dataset columns"), style="DetailTitle.TLabel").pack(anchor="w")
        ttk.Label(
            frame,
            text=self.tr(
                f"已探測 {self.spec.row_count} 筆樣本、{len(self.spec.columns)} 個欄位。請選擇時間、空間與必要欄位後再建立 bounded 下載計畫。",
                f"Probed {self.spec.row_count} rows and {len(self.spec.columns)} columns. Choose time, spatial, and required-column bounds before building a bounded plan.",
            ),
            style="DetailMuted.TLabel",
        ).pack(anchor="w", fill=X, pady=(8, 12))

        field_frame = ttk.Frame(frame, style="Panel.TFrame")
        field_frame.pack(fill=BOTH, expand=True)
        for field in self.spec.fields:
            self._build_field(field_frame, field)

        if self.spec.columns:
            ttk.Label(frame, text=self.tr("欄位預覽", "Column preview"), style="DetailSection.TLabel").pack(anchor="w", pady=(12, 4))
            preview = Text(
                frame,
                height=5,
                wrap=WORD,
                bg=COLORS["bg"],
                fg=COLORS["text"],
                insertbackground=COLORS["text"],
                relief="flat",
                padx=10,
                pady=10,
                font=("Consolas", 10),
            )
            preview.pack(fill=X)
            preview.insert("1.0", "\n".join(f"{column.name}: {column.inferred_type} = {column.sample_value}" for column in self.spec.columns))
            preview.configure(state="disabled")

        buttons = ttk.Frame(frame, style="Panel.TFrame")
        buttons.pack(fill=X, pady=(16, 0))
        ttk.Button(buttons, text=self.tr("建立界域", "Apply bounds"), style="Action.TButton", command=self.save).pack(side=RIGHT, padx=(10, 0))
        ttk.Button(buttons, text=self.tr("取消", "Cancel"), style="Action.TButton", command=self.cancel).pack(side=RIGHT)

    def _build_field(self, parent: ttk.Frame, field: BoundFormField) -> None:
        ttk.Label(parent, text=self.tr(field.label_zh_TW, field.label_en), style="DetailSection.TLabel").pack(anchor="w", pady=(8, 2))
        if field.control == "select":
            values = [""] + [option.value for option in field.options]
            var = StringVar(value=str(field.default or ""))
            self.vars[field.field_id] = var
            ttk.Combobox(parent, values=values, textvariable=var, state="readonly", font=("Helvetica", 11)).pack(fill=X)
        elif field.control == "multiselect":
            checks = ttk.Frame(parent, style="Panel.TFrame")
            checks.pack(fill=X)
            self.multi_vars[field.field_id] = {}
            # 多選欄位可能很多，先限制顯示前 24 個；完整欄位仍在 preview 裡，避免 dialog 暴長。
            for index, option in enumerate(field.options[:24]):
                var = BooleanVar(value=False)
                self.multi_vars[field.field_id][option.value] = var
                ttk.Checkbutton(checks, text=option.value, variable=var).grid(row=index // 3, column=index % 3, sticky="w", padx=(0, 14), pady=2)
        else:
            var = StringVar(value=str(field.default or ""))
            self.vars[field.field_id] = var
            ttk.Entry(parent, textvariable=var, font=("Helvetica", 11)).pack(fill=X)
        help_text = self.tr(field.help_zh_TW, field.help_en)
        if help_text:
            ttk.Label(parent, text=help_text, style="DetailMuted.TLabel").pack(anchor="w", pady=(2, 0))

    def form_values(self) -> dict[str, object]:
        values: dict[str, object] = {field_id: var.get() for field_id, var in self.vars.items()}
        for field_id, options in self.multi_vars.items():
            values[field_id] = [name for name, var in options.items() if var.get()]
        return values

    def save(self) -> None:
        try:
            self.result = source_download_bounds_from_form_values(self.form_values())
        except Exception as exc:
            messagebox.showerror(self.tr("界域格式錯誤", "Invalid bounds"), str(exc), parent=self.window)
            return
        self.window.destroy()

    def cancel(self) -> None:
        self.result = None
        self.window.destroy()
