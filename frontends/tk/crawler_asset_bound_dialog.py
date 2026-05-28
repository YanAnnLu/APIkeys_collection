from __future__ import annotations

from tkinter import BOTH, RIGHT, WORD, BooleanVar, StringVar, Text, Tk, Toplevel, messagebox
from tkinter import ttk
from typing import Mapping

from api_launcher.crawler_asset_bound_forms import (
    CrawlerAssetBoundFormField,
    CrawlerAssetBoundFormSpec,
    CrawlerAssetBoundPayload,
    crawler_asset_bound_payload_from_form_values,
)
from frontends.tk.ui_config import COLORS


class CrawlerAssetBoundDialog:
    """Tk 版 crawler asset 界域輸入視窗。

    Dialog 只把前端中立的 form spec 畫成 Tk 欄位，輸出仍是後端 payload。
    這樣未來 Qt 可以重用同一份 spec，而不用重寫界域推導規則。
    """

    def __init__(self, parent: Tk, spec: CrawlerAssetBoundFormSpec, tr=lambda zh, _en: zh):
        self.parent = parent
        self.spec = spec
        self.tr = tr
        self.result: CrawlerAssetBoundPayload | None = None
        self.vars: dict[str, StringVar] = {}
        self.multi_vars: dict[str, dict[str, BooleanVar]] = {}
        self.window = Toplevel(parent)
        self.window.title(self.tr("爬蟲界域設定", "Crawler bounds"))
        self.window.transient(parent)
        self.window.grab_set()
        self.window.configure(bg=COLORS["panel"])
        self.window.minsize(700, 620)

        self._build()
        self.window.bind("<Escape>", lambda _event: self.cancel())
        self.window.protocol("WM_DELETE_WINDOW", self.cancel)
        self.window.wait_window()

    def _build(self) -> None:
        frame = ttk.Frame(self.window, style="Panel.TFrame")
        frame.pack(fill=BOTH, expand=True, padx=22, pady=22)

        ttk.Label(frame, text=self.tr("定義這次要抓的界域", "Define crawler bounds"), style="DetailTitle.TLabel").pack(anchor="w")
        ttk.Label(
            frame,
            text=self.tr(
                "這裡只建立界域 payload，不直接下載。下一步會把 payload 交給爬蟲的 build_download_plan 能力。",
                "This only builds a bounds payload. The next step passes it to the crawler build_download_plan capability.",
            ),
            style="DetailMuted.TLabel",
        ).pack(anchor="w", pady=(8, 12))

        if self.spec.guidance_zh_TW or self.spec.guidance_en:
            ttk.Label(
                frame,
                text=self.tr(self.spec.guidance_zh_TW, self.spec.guidance_en),
                style="DetailMuted.TLabel",
            ).pack(anchor="w", pady=(0, 10))

        if self.spec.recommended_values or self.spec.presets:
            quick = ttk.Frame(frame, style="Panel.TFrame")
            quick.pack(fill="x", pady=(0, 12))
            ttk.Label(quick, text=self.tr("快速界域", "Quick bounds"), style="DetailSection.TLabel").pack(anchor="w", pady=(0, 6))
            actions = ttk.Frame(quick, style="Panel.TFrame")
            actions.pack(fill="x")
            if self.spec.recommended_values:
                ttk.Button(
                    actions,
                    text=self.tr("套用推薦值", "Apply recommended"),
                    style="Action.TButton",
                    command=self.apply_recommended_values,
                ).pack(side="left", padx=(0, 8), pady=2)
            for preset in self.spec.presets[:4]:
                ttk.Button(
                    actions,
                    text=self.tr(preset.label_zh_TW, preset.label_en),
                    style="Action.TButton",
                    command=lambda preset_id=preset.preset_id: self.apply_preset(preset_id),
                ).pack(side="left", padx=(0, 8), pady=2)

        for field in self.spec.fields:
            self._build_field(frame, field)

        if self.spec.warning_codes:
            preview = Text(
                frame,
                height=4,
                wrap=WORD,
                bg=COLORS["bg"],
                fg=COLORS["text"],
                insertbackground=COLORS["text"],
                relief="flat",
                padx=10,
                pady=10,
                font=("Consolas", 10),
            )
            preview.pack(fill="x", pady=(12, 0))
            preview.insert(
                "1.0",
                self.tr(
                    "注意：部分欄位建議先做 schema/head probe，再改成精準選單。\nwarning_codes: ",
                    "Note: some fields should be refined by schema/head probe before becoming precise selectors.\nwarning_codes: ",
                )
                + ", ".join(self.spec.warning_codes),
            )
            preview.configure(state="disabled")

        buttons = ttk.Frame(frame, style="Panel.TFrame")
        buttons.pack(fill="x", pady=(16, 0))
        ttk.Button(buttons, text=self.tr("套用界域", "Apply bounds"), style="Action.TButton", command=self.save).pack(side=RIGHT, padx=(10, 0))
        ttk.Button(buttons, text=self.tr("取消", "Cancel"), style="Action.TButton", command=self.cancel).pack(side=RIGHT)

    def _build_field(self, parent: ttk.Frame, field: CrawlerAssetBoundFormField) -> None:
        ttk.Label(parent, text=self.tr(field.label_zh_TW, field.label_en), style="DetailSection.TLabel").pack(anchor="w", pady=(8, 2))
        if field.control in {"select_or_text"} and field.options:
            var = StringVar(value=str(field.default or ""))
            self.vars[field.field_id] = var
            ttk.Combobox(parent, values=["", *field.options], textvariable=var, font=("Helvetica", 11)).pack(fill="x")
        elif field.control == "multiselect":
            checks = ttk.Frame(parent, style="Panel.TFrame")
            checks.pack(fill="x")
            self.multi_vars[field.field_id] = {}
            for index, option in enumerate(field.options[:24]):
                var = BooleanVar(value=False)
                self.multi_vars[field.field_id][option] = var
                ttk.Checkbutton(checks, text=option, variable=var).grid(row=index // 3, column=index % 3, sticky="w", padx=(0, 14), pady=2)
        else:
            var = StringVar(value=str(field.default or ""))
            self.vars[field.field_id] = var
            ttk.Entry(parent, textvariable=var, font=("Helvetica", 11)).pack(fill="x")
        help_text = self.tr(field.help_zh_TW, field.help_en)
        if help_text:
            ttk.Label(parent, text=help_text, style="DetailMuted.TLabel").pack(anchor="w", pady=(2, 0))

    def form_values(self) -> dict[str, object]:
        values: dict[str, object] = {field_id: var.get() for field_id, var in self.vars.items()}
        for field_id, options in self.multi_vars.items():
            values[field_id] = [name for name, var in options.items() if var.get()]
        return values

    def apply_recommended_values(self) -> None:
        self.apply_form_values(self.spec.recommended_values)

    def apply_preset(self, preset_id: str) -> bool:
        for preset in self.spec.presets:
            if preset.preset_id == preset_id:
                self.apply_form_values(preset.values)
                return True
        return False

    def apply_form_values(self, values: Mapping[str, object]) -> None:
        """Apply backend-provided UX helpers without changing the form contract.

        Presets and recommendations come from ``CrawlerAssetBoundFormSpec``.
        The dialog only copies those explicit values into visible variables; it
        does not infer bbox, time fields, versions, or dataset ids by itself.
        """

        for field_id, value in values.items():
            if field_id in self.vars:
                self.vars[field_id].set("" if value is None else str(value))
            if field_id in self.multi_vars:
                selected = {str(item) for item in value} if isinstance(value, (list, tuple, set)) else {str(value)}
                for option, var in self.multi_vars[field_id].items():
                    var.set(option in selected)

    def save(self) -> None:
        try:
            self.result = crawler_asset_bound_payload_from_form_values(self.spec, self.form_values())
        except Exception as exc:
            messagebox.showerror(self.tr("界域格式錯誤", "Invalid bounds"), str(exc), parent=self.window)
            return
        self.window.destroy()

    def cancel(self) -> None:
        self.result = None
        self.window.destroy()
