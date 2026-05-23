#!/usr/bin/env python3
"""Tk 細節抽屜與 responsive layout 流程。"""

from __future__ import annotations

from tkinter import BOTH, LEFT, RIGHT, Y
from tkinter import ttk

from frontends.tk.startup_helpers import contextlib_suppress_tcl_error
from frontends.tk.ui_config import LAYOUT, TABLE_COLUMNS
from frontends.tk.ui_helpers import clamp


class ResponsiveLayoutWorkflowMixin:
    """封裝主視窗 resize、細節抽屜動畫，以及表格欄寬重新配置。"""

    def open_detail_drawer(self) -> None:
        if not self.active_provider_id and self.filtered_rows:
            self.active_provider_id = self.filtered_rows[0].provider_id
        self.update_detail_panel(self.row_by_provider_id(self.active_provider_id))
        if not self.detail_visible or self.detail_animating_close:
            self.detail_visible = True
            self.detail_animating_close = False
            self.animate_detail_drawer(opening=True)
        else:
            self.apply_detail_layout()
        self.root.after_idle(self.resize_table_columns)

    def close_detail_drawer(self) -> None:
        if self.detail_visible:
            self.animate_detail_drawer(opening=False)
            self.root.after_idle(self.resize_table_columns)

    def scaled_pad(self) -> int:
        return clamp(int(self.root.winfo_width() * LAYOUT["outer_pad_ratio"]), 18, 40)

    def detail_width(self) -> int:
        container_width = self.content_width()
        gap = LAYOUT["detail_gap"]
        table_min = LAYOUT["table_min_with_detail"]
        if container_width <= table_min + gap:
            return clamp(container_width // 2, 280, LAYOUT["detail_min"])
        max_width = max(280, min(LAYOUT["detail_max"], container_width - table_min - gap))
        min_width = min(LAYOUT["detail_min"], max_width)
        return clamp(int(container_width * LAYOUT["detail_ratio"]), min_width, max_width)

    def content_width(self) -> int:
        container_width = 0
        if hasattr(self, "content_frame"):
            container_width = self.content_frame.winfo_width()
        if container_width <= 1:
            sidebar_width = clamp(int(self.root.winfo_width() * LAYOUT["sidebar_ratio"]), LAYOUT["sidebar_min"], LAYOUT["sidebar_max"])
            container_width = max(self.root.winfo_width() - sidebar_width - (2 * self.scaled_pad()), 1)
        return max(container_width, 1)

    def detail_content_wraplength(self) -> int:
        return max(self.detail_width() - 64, 260)

    def apply_detail_wraplength(self) -> None:
        wraplength = self.detail_content_wraplength()
        for label in getattr(self, "detail_wrap_labels", []):
            label.configure(wraplength=wraplength)
        if hasattr(self, "detail_canvas"):
            canvas_width = max(self.detail_current_width - 18, 260)
            self.detail_canvas.itemconfigure(self.detail_canvas_window, width=canvas_width)

    def update_detail_scrollregion(self, _event: object | None = None) -> None:
        self.detail_canvas.configure(scrollregion=self.detail_canvas.bbox("all"))

    def on_detail_canvas_configure(self, event: object) -> None:
        width = max(getattr(event, "width", self.detail_width()) - 2, 260)
        self.detail_canvas.itemconfigure(self.detail_canvas_window, width=width)
        self.update_detail_scrollregion()

    def on_detail_mousewheel(self, event: object) -> str:
        delta = getattr(event, "delta", 0)
        if delta:
            self.detail_canvas.yview_scroll(int(-1 * (delta / 120)), "units")
        return "break"

    def apply_detail_layout(self) -> None:
        if not self.detail_visible:
            return
        if not self.detail_animation_after_id:
            self.detail_current_width = self.detail_width()
            self.detail.configure(width=self.detail_current_width)
        self.apply_detail_wraplength()

    def pack_content_area(self, detail_width: int | None = None) -> None:
        self.table_frame.pack_forget()
        self.detail.pack_forget()
        if self.detail_visible:
            if detail_width is None:
                self.apply_detail_layout()
            else:
                self.detail_current_width = max(detail_width, 1)
                self.detail.configure(width=self.detail_current_width)
                self.apply_detail_wraplength()
            self.detail.pack(side=RIGHT, fill=Y, padx=(LAYOUT["detail_gap"], 0))
        self.table_frame.pack(side=LEFT, fill=BOTH, expand=True)

    def cancel_detail_animation(self) -> None:
        if self.detail_animation_after_id:
            with contextlib_suppress_tcl_error():
                self.root.after_cancel(self.detail_animation_after_id)
            self.detail_animation_after_id = None

    def current_detail_width(self) -> int:
        if self.detail.winfo_ismapped():
            width = self.detail.winfo_width()
            if width > 1:
                return width
        if self.detail_current_width > 1:
            return self.detail_current_width
        return self.detail_width()

    def animate_detail_drawer(self, opening: bool) -> None:
        # 抽屜動畫只改寬度，不重建 widget，避免 Text/Treeview 狀態在開關時遺失。
        self.cancel_detail_animation()
        target_width = self.detail_width()
        start_width = self.current_detail_width() if self.detail.winfo_ismapped() else 1
        if opening:
            self.detail_visible = True
            self.detail_animating_close = False
            start_width = min(start_width, target_width)
            self.pack_content_area(detail_width=start_width)
        else:
            self.detail_animating_close = True
            start_width = max(start_width, 1)
            target_width = 1
        self.run_detail_animation(start_width, target_width, opening=opening, step=0)

    def run_detail_animation(self, start_width: int, target_width: int, opening: bool, step: int) -> None:
        steps = max(int(LAYOUT["detail_animation_steps"]), 1)
        progress = min(step / steps, 1.0)
        eased = 1 - ((1 - progress) ** 3)
        width = max(1, int(start_width + ((target_width - start_width) * eased)))
        self.detail_current_width = width
        self.detail.configure(width=width)
        self.apply_detail_wraplength()
        self.resize_table_columns()
        if step < steps:
            self.detail_animation_after_id = self.root.after(
                int(LAYOUT["detail_animation_delay_ms"]),
                lambda: self.run_detail_animation(start_width, target_width, opening=opening, step=step + 1),
            )
            return
        self.detail_animation_after_id = None
        if opening:
            self.detail_current_width = self.detail_width()
            self.apply_detail_layout()
        else:
            self.detail_visible = False
            self.detail_animating_close = False
            self.detail_current_width = 0
            self.pack_content_area()
        self.root.after_idle(self.resize_table_columns)

    def on_root_configure(self, event: object) -> None:
        if getattr(event, "widget", None) is not self.root:
            return
        if self.resize_after_id:
            self.root.after_cancel(self.resize_after_id)
        # resize event 很密集，用 after debounce 避免每個像素都重算欄寬。
        self.resize_after_id = self.root.after(80, self.apply_responsive_layout)

    def apply_responsive_layout(self) -> None:
        self.resize_after_id = None
        width = max(self.root.winfo_width(), 1)
        height = max(self.root.winfo_height(), 1)
        rowheight = clamp(int(height * LAYOUT["rowheight_ratio"]), 42, 62)
        ttk.Style(self.root).configure("Treeview", rowheight=rowheight)
        self.apply_detail_layout()
        self.resize_table_columns()

    def resize_table_columns(self) -> None:
        # 手動欄寬優先，剩餘空間再依比例分配給自動欄位。
        table_width = max(self.tree.winfo_width(), 1)
        reserved = 24
        manual_widths = {
            name: self.normalized_column_width(name, width)
            for name, width in self.column_width_overrides.items()
        }
        manual_total = sum(manual_widths.values())
        auto_columns = [column for column in TABLE_COLUMNS if column[0] not in manual_widths]
        available = max(table_width - reserved - manual_total, 1)
        ratio_base = 1.0 if not manual_widths else max(sum(column[2] for column in auto_columns), 0.01)
        for name, _label, ratio, min_width, max_width, _anchor, _stretch in TABLE_COLUMNS:
            if name in manual_widths:
                width = manual_widths[name]
            else:
                width = clamp(int(available * (ratio / ratio_base)), min_width, max_width)
            self.tree.column(name, width=width)
