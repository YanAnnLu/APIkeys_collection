#!/usr/bin/env python3
"""Tk 表格欄寬、游標與搜尋分類事件流程。"""

from __future__ import annotations

from tkinter import TclError

from frontends.tk.ui_config import TABLE_COLUMNS


class TableInteractionWorkflowMixin:
    """封裝不改變資料內容的 Treeview / search UI 事件。"""

    def table_column_name_from_event(self, event: object) -> str:
        column_id = self.tree.identify_column(getattr(event, "x", 0))
        if not column_id.startswith("#"):
            return ""
        try:
            index = int(column_id[1:]) - 1
        except ValueError:
            return ""
        if index < 0 or index >= len(TABLE_COLUMNS):
            return ""
        return TABLE_COLUMNS[index][0]

    def on_tree_button_press(self, event: object) -> None:
        region = self.tree.identify("region", getattr(event, "x", 0), getattr(event, "y", 0))
        self.resizing_column_name = self.table_column_name_from_event(event) if region == "separator" else None
        if self.resizing_column_name:
            self.set_tree_cursor(self.table_resize_cursor)

    def on_tree_button_release(self, event: object) -> None:
        if not self.resizing_column_name:
            return
        name = self.resizing_column_name
        self.resizing_column_name = None
        self.on_tree_motion(event)
        self.root.after_idle(lambda column_name=name: self.finish_tree_column_resize(column_name))

    def finish_tree_column_resize(self, name: str) -> None:
        width = self.normalized_column_width(name, int(self.tree.column(name, "width")))
        self.column_width_overrides[name] = width
        self.save_column_width_overrides()
        self.resize_table_columns()
        label = next((column[1] for column in TABLE_COLUMNS if column[0] == name), name)
        self.status_var.set(self.tr(f"已調整欄寬：{label}", f"Column width updated: {label}"))

    def reset_table_column_widths(self) -> None:
        self.column_width_overrides.clear()
        self.save_column_width_overrides()
        self.resize_table_columns()
        self.status_var.set(self.tr("已重設表格欄寬。", "Table column widths reset."))

    def on_tree_motion(self, event: object) -> None:
        if self.resizing_column_name:
            self.set_tree_cursor(self.table_resize_cursor)
            return
        region = self.tree.identify("region", getattr(event, "x", 0), getattr(event, "y", 0))
        cursor = self.table_resize_cursor if region == "separator" else self.tree_default_cursor
        self.set_tree_cursor(cursor)

    def on_tree_leave(self, _event: object) -> None:
        if not self.resizing_column_name:
            self.set_tree_cursor(self.tree_default_cursor)

    def set_tree_cursor(self, cursor: str) -> None:
        if str(self.tree.cget("cursor") or "") == cursor:
            return
        try:
            self.tree.configure(cursor=cursor)
        except TclError:
            self.tree.configure(cursor=self.tree_default_cursor)

    def set_search_placeholder(self) -> None:
        if self.search_var.get():
            return
        self.search_placeholder_active = True
        self.search_var.set(self.search_placeholder_text)
        self.search_entry.configure(style="SearchPlaceholder.TEntry")

    def on_search_focus_in(self, _event: object) -> None:
        if self.search_placeholder_active:
            self.search_placeholder_active = False
            self.search_var.set("")
            self.search_entry.configure(style="Search.TEntry")

    def on_search_focus_out(self, _event: object) -> None:
        if not self.search_var.get().strip():
            self.set_search_placeholder()

    def set_category(self, category: str) -> None:
        self.category_var.set(category)
        self.apply_filter()
