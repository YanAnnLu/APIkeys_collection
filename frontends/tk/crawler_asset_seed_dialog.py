from __future__ import annotations

from tkinter import BOTH, END, LEFT, RIGHT, X, Y, StringVar, Toplevel
from tkinter import ttk
from typing import Callable

from frontends.tk.ui_config import COLORS


def crawler_seed_dialog_rows(payload: object) -> list[dict[str, object]]:
    """Return the seed rows that the dialog can render.

    The paging contract is owned by `api_launcher.crawler_seed_registry`.
    This helper only normalizes the already-loaded page for Tk rendering.
    """

    if not isinstance(payload, dict):
        return []
    rows = payload.get("seeds")
    if not isinstance(rows, list):
        return []
    return [dict(row) for row in rows if isinstance(row, dict)]


def crawler_seed_dialog_import_label(row: dict[str, object]) -> str:
    """Return the backend-provided import lane label for a seed row.

    Tk deliberately does not infer CSV/ZIP/GeoTIFF behavior here. The row
    already comes from `api_launcher.crawler_seed_registry`, which attaches
    the UI-neutral content import profile used by Web and future Qt.
    """

    direct_label = str(row.get("content_display_label") or "").strip()
    if direct_label:
        return direct_label
    profile = row.get("content_import_profile")
    if isinstance(profile, dict):
        profile_label = str(profile.get("display_label") or "").strip()
        if profile_label:
            return profile_label
    return str(row.get("content_pipeline_lane") or "").strip()


def crawler_seed_dialog_row_values(row: dict[str, object]) -> tuple[str, str, str, str, str, str, str]:
    """Create stable table values for one seed row."""

    favorite = "★" if row.get("favorite") else ""
    title = str(row.get("title") or row.get("dataset_id") or row.get("dataset_uid") or "-").strip()
    native_format = str(row.get("native_format") or row.get("data_type") or "").strip()
    import_label = crawler_seed_dialog_import_label(row)
    version = str(row.get("version") or "").strip()
    dataset_uid = str(row.get("dataset_uid") or row.get("dataset_id") or "").strip()
    status = str(row.get("candidate_status") or row.get("source_type") or "").strip()
    return favorite, title, native_format, import_label, version, dataset_uid, status


class CrawlerAssetSeedDialog:
    """Seed row picker for crawler assets.

    The dialog does not write profiles, download files, or import data. It
    returns a small action payload to the workflow layer so Tk/Web/Qt can keep
    sharing the same backend services.
    """

    def __init__(
        self,
        parent: object,
        payload: object,
        tr: Callable[[str, str], str] = lambda zh, _en: zh,
    ) -> None:
        self.parent = parent
        self.payload = payload if isinstance(payload, dict) else {}
        self.tr = tr
        self.result: dict[str, object] | None = None
        self.rows = crawler_seed_dialog_rows(self.payload)
        self.row_by_iid: dict[str, dict[str, object]] = {}
        self.message_var = StringVar(value="")
        self.window = Toplevel(parent)
        self.window.title(self.tr("Seed 清單", "Seed list"))
        self.window.transient(parent)
        self.window.grab_set()
        self.window.configure(bg=COLORS["panel"])
        self.window.minsize(900, 560)

        self._build()
        self.window.bind("<Escape>", lambda _event: self.cancel())
        self.window.protocol("WM_DELETE_WINDOW", self.cancel)
        self.window.wait_window()

    def _build(self) -> None:
        frame = ttk.Frame(self.window, style="Panel.TFrame")
        frame.pack(fill=BOTH, expand=True, padx=22, pady=22)

        asset_id = str(self.payload.get("asset_id") or "").strip()
        page = int(self.payload.get("page") or 1)
        total = int(self.payload.get("total") or 0)
        ttk.Label(frame, text=self.tr("選擇入口內的 Seed", "Choose a source seed"), style="DetailTitle.TLabel").pack(anchor="w")
        ttk.Label(
            frame,
            text=self.tr(
                f"{asset_id or '-'} / 第 {page} 頁 / 本機 catalog 共 {total} 筆",
                f"{asset_id or '-'} / page {page} / {total} local catalog rows",
            ),
            style="DetailMuted.TLabel",
        ).pack(anchor="w", fill=X, pady=(4, 12))

        table_frame = ttk.Frame(frame, style="Panel.TFrame")
        table_frame.pack(fill=BOTH, expand=True)
        columns = ("favorite", "title", "format", "import_path", "version", "uid", "status")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="browse")
        headings = (
            ("favorite", self.tr("收藏", "Favorite"), 64, "center"),
            ("title", self.tr("Seed 名稱", "Seed title"), 300, "w"),
            ("format", self.tr("格式", "Format"), 120, "w"),
            ("import_path", self.tr("匯入路徑", "Import path"), 150, "w"),
            ("version", self.tr("版本", "Version"), 110, "w"),
            ("uid", self.tr("Seed ID", "Seed ID"), 260, "w"),
            ("status", self.tr("狀態", "Status"), 130, "w"),
        )
        for column, label, width, anchor in headings:
            self.tree.heading(column, text=label)
            self.tree.column(column, width=width, anchor=anchor, stretch=True)
        y_scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=y_scrollbar.set)
        self.tree.pack(side=LEFT, fill=BOTH, expand=True)
        y_scrollbar.pack(side=RIGHT, fill=Y)
        self.tree.bind("<Double-1>", lambda _event: self.download())

        for index, row in enumerate(self.rows):
            iid = str(index)
            self.row_by_iid[iid] = row
            self.tree.insert("", END, iid=iid, values=crawler_seed_dialog_row_values(row))
        if self.rows:
            self.tree.selection_set("0")
            self.tree.focus("0")
        else:
            self.message_var.set(
                self.tr(
                    "目前沒有可選 seed。請先執行清單擷取，或在右側使用「顯示更多 Seed」。",
                    "No selectable seeds. Run listing first, or use Show more seeds in the side panel.",
                )
            )

        ttk.Label(frame, textvariable=self.message_var, style="DetailMuted.TLabel").pack(anchor="w", pady=(10, 0))

        buttons = ttk.Frame(frame, style="Panel.TFrame")
        buttons.pack(fill=X, pady=(18, 0))
        ttk.Button(buttons, text=self.tr("下載此 Seed", "Download this seed"), style="Action.TButton", command=self.download).pack(side=RIGHT, padx=(10, 0))
        ttk.Button(buttons, text=self.tr("收藏 / 取消收藏", "Favorite / unfavorite"), style="Action.TButton", command=self.favorite).pack(side=RIGHT, padx=(10, 0))
        ttk.Button(buttons, text=self.tr("關閉", "Close"), style="Action.TButton", command=self.cancel).pack(side=RIGHT)

    def selected_row(self) -> dict[str, object] | None:
        selection = self.tree.selection()
        if not selection:
            return None
        return self.row_by_iid.get(str(selection[0]))

    def _selected_dataset_uid(self) -> str:
        row = self.selected_row()
        if not row:
            self.message_var.set(self.tr("請先選擇一筆 seed。", "Select one seed first."))
            return ""
        dataset_uid = str(row.get("dataset_uid") or row.get("dataset_id") or "").strip()
        if not dataset_uid:
            self.message_var.set(self.tr("這筆 seed 缺少可用 ID，無法操作。", "This seed has no usable ID."))
            return ""
        return dataset_uid

    def download(self) -> None:
        dataset_uid = self._selected_dataset_uid()
        if not dataset_uid:
            return
        self.result = {"action": "download", "dataset_uid": dataset_uid}
        self.window.destroy()

    def favorite(self) -> None:
        row = self.selected_row()
        dataset_uid = self._selected_dataset_uid()
        if not dataset_uid or row is None:
            return
        self.result = {
            "action": "favorite",
            "dataset_uid": dataset_uid,
            "favorite": not bool(row.get("favorite")),
        }
        self.window.destroy()

    def cancel(self) -> None:
        self.result = None
        self.window.destroy()


__all__ = [
    "CrawlerAssetSeedDialog",
    "crawler_seed_dialog_import_label",
    "crawler_seed_dialog_row_values",
    "crawler_seed_dialog_rows",
]
