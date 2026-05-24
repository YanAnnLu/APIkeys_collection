from __future__ import annotations

from tkinter import BOTH, LEFT, RIGHT, X, StringVar, Toplevel, messagebox
from tkinter import ttk
from typing import Any, Callable

from frontends.tk.ui_config import COLORS


DraftTranslator = Callable[[str, str], str]


class SourcePatternDraftDialog:
    """Tk URL-to-source-draft input dialog.

    這個 dialog 只收集 detector 需要的最少參數；真正的 URL 範式辨識與
    local source draft 寫入仍由 api_launcher.source_pattern_drafts 負責。
    """

    def __init__(self, parent: object, tr: DraftTranslator = lambda zh, _en: zh):
        self.parent = parent
        self.tr = tr
        self.result: dict[str, object] | None = None
        self.window = Toplevel(parent)
        self.window.title(self.tr("從 URL 建立來源草稿", "Draft source from URL"))
        self.window.transient(parent)
        self.window.grab_set()
        self.window.configure(bg=COLORS["panel"])
        self.window.minsize(660, 560)

        self.vars = {
            "url": StringVar(value=""),
            "provider_id": StringVar(value=""),
            "name": StringVar(value=""),
            "source_id": StringVar(value=""),
            "categories": StringVar(value=""),
            "geographic_scope": StringVar(value="global"),
            "max_results": StringVar(value="10"),
            "min_expected_candidates": StringVar(value="1"),
            "timeout": StringVar(value="8.0"),
            "minimum_confidence": StringVar(value="0.35"),
        }

        self._build()
        self.window.bind("<Escape>", lambda _event: self.cancel())
        self.window.protocol("WM_DELETE_WINDOW", self.cancel)
        self.window.wait_window()

    def _build(self) -> None:
        frame = ttk.Frame(self.window, style="Panel.TFrame")
        frame.pack(fill=BOTH, expand=True, padx=22, pady=22)

        ttk.Label(frame, text=self.tr("從 URL 建立本機來源草稿", "Draft a local source from URL"), style="DetailTitle.TLabel").pack(anchor="w")
        ttk.Label(
            frame,
            text=self.tr(
                "這一步只會偵測來源介面類型並寫入 ignored local draft；不會提升 catalog、下載或匯入。",
                "This only detects the source interface and writes an ignored local draft; it will not promote catalog, download, or import.",
            ),
            style="DetailMuted.TLabel",
            wraplength=600,
        ).pack(anchor="w", fill=X, pady=(4, 14))

        self._entry(frame, "url", self.tr("來源 URL", "Source URL"), required=True)
        self._entry(frame, "provider_id", self.tr("Provider ID（可留空自動推導）", "Provider ID (optional)"))
        self._entry(frame, "name", self.tr("顯示名稱（可留空）", "Display name (optional)"))
        self._entry(frame, "source_id", self.tr("Source ID（可留空）", "Source ID (optional)"))
        self._entry(frame, "categories", self.tr("分類 / 關鍵字（逗號分隔，可留空）", "Categories / keywords (comma-separated, optional)"))

        numeric = ttk.Frame(frame, style="Panel.TFrame")
        numeric.pack(fill=X, pady=(8, 0))
        for field_id, label, width in (
            ("geographic_scope", self.tr("範圍", "Scope"), 16),
            ("max_results", self.tr("候選上限", "Max results"), 10),
            ("min_expected_candidates", self.tr("最低候選", "Min expected"), 10),
            ("timeout", self.tr("Timeout", "Timeout"), 10),
            ("minimum_confidence", self.tr("最低信心", "Min confidence"), 10),
        ):
            cell = ttk.Frame(numeric, style="Panel.TFrame")
            cell.pack(side=LEFT, padx=(0, 10))
            ttk.Label(cell, text=label, style="DetailSection.TLabel").pack(anchor="w")
            ttk.Entry(cell, textvariable=self.vars[field_id], width=width).pack(anchor="w")

        buttons = ttk.Frame(frame, style="Panel.TFrame")
        buttons.pack(fill=X, pady=(18, 0))
        ttk.Button(buttons, text=self.tr("建立草稿", "Create draft"), style="Action.TButton", command=self.save).pack(side=RIGHT, padx=(10, 0))
        ttk.Button(buttons, text=self.tr("取消", "Cancel"), style="Action.TButton", command=self.cancel).pack(side=RIGHT)

    def _entry(self, parent: ttk.Frame, field_id: str, label: str, *, required: bool = False) -> None:
        text = f"{label} *" if required else label
        ttk.Label(parent, text=text, style="DetailSection.TLabel").pack(anchor="w", pady=(8, 2))
        entry = ttk.Entry(parent, textvariable=self.vars[field_id], font=("Helvetica", 11))
        entry.pack(fill=X)
        if field_id == "url":
            entry.focus_set()

    def form_values(self) -> dict[str, object]:
        url = str(self.vars["url"].get() or "").strip()
        if not url:
            raise ValueError(self.tr("請輸入來源 URL。", "Source URL is required."))
        max_results = _positive_int(self.vars["max_results"].get(), "max_results")
        min_expected = _positive_int(self.vars["min_expected_candidates"].get(), "min_expected_candidates")
        timeout = _positive_float(self.vars["timeout"].get(), "timeout")
        minimum_confidence = _bounded_float(self.vars["minimum_confidence"].get(), "minimum_confidence", 0.0, 1.0)
        return {
            "url": url,
            "provider_id": str(self.vars["provider_id"].get() or "").strip(),
            "name": str(self.vars["name"].get() or "").strip(),
            "source_id": str(self.vars["source_id"].get() or "").strip(),
            "categories": _split_categories(str(self.vars["categories"].get() or "")),
            "geographic_scope": str(self.vars["geographic_scope"].get() or "").strip() or "global",
            "max_results": max_results,
            "min_expected_candidates": min_expected,
            "timeout": timeout,
            "minimum_confidence": minimum_confidence,
        }

    def save(self) -> None:
        try:
            self.result = self.form_values()
        except ValueError as exc:
            messagebox.showerror(self.tr("來源草稿參數錯誤", "Invalid source draft input"), str(exc), parent=self.window)
            return
        self.window.destroy()

    def cancel(self) -> None:
        self.result = None
        self.window.destroy()


def _split_categories(value: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in value.replace("\n", ",").split(",") if part.strip())


def _positive_int(value: Any, field_name: str) -> int:
    try:
        parsed = int(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be an integer") from exc
    if parsed < 1:
        raise ValueError(f"{field_name} must be greater than zero")
    return parsed


def _positive_float(value: Any, field_name: str) -> float:
    try:
        parsed = float(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be a number") from exc
    if parsed <= 0:
        raise ValueError(f"{field_name} must be greater than zero")
    return parsed


def _bounded_float(value: Any, field_name: str, lower: float, upper: float) -> float:
    parsed = _positive_float(value, field_name)
    if parsed < lower or parsed > upper:
        raise ValueError(f"{field_name} must be between {lower} and {upper}")
    return parsed


__all__ = ["SourcePatternDraftDialog"]
