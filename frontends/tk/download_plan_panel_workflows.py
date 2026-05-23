from __future__ import annotations

from tkinter import LEFT, RIGHT, X
from tkinter import ttk


class DownloadPlanPanelWorkflowMixin:
    """封裝下載計畫區塊的 Tk widget 建置與展開狀態。

    這個 mixin 只負責畫面結構，不處理實際下載、匯入或 retry 邏輯；按鈕仍委派
    給既有 workflow 方法，讓後續改版能單獨替換面板版面。
    """

    def _build_download_plan_panel(self, parent: ttk.Frame, outer_pad: int) -> None:
        # Download plan panel 同時顯示購物車與背景工作列，避免下載狀態只藏在 log。
        plan = ttk.Frame(parent, style="Panel.TFrame")
        plan.pack(fill=X, padx=outer_pad, pady=(0, max(14, outer_pad // 2)))
        self.download_plan_panel = plan

        header = ttk.Frame(plan, style="Panel.TFrame")
        header.pack(fill=X, padx=14, pady=(12, 8))
        ttk.Label(header, textvariable=self.plan_count_var, style="DetailSection.TLabel").pack(side=LEFT)
        ttk.Entry(header, textvariable=self.plan_name_var, font=("Helvetica", 12), width=34).pack(side=LEFT, padx=(14, 8))
        ttk.Button(header, textvariable=self.download_plan_toggle_var, style="Action.TButton", command=self.toggle_download_plan_panel).pack(side=RIGHT, padx=(8, 0))
        ttk.Button(header, text=self.tr("開始", "Start"), style="Action.TButton", command=self.start_download_plan).pack(side=RIGHT, padx=(8, 0))
        ttk.Button(header, text=self.tr("匯入", "Import"), style="Action.TButton", command=self.import_supported_plan_results_from_ui).pack(side=RIGHT, padx=(8, 0))
        ttk.Button(header, text=self.tr("暫停", "Pause"), style="Action.TButton", command=self.pause_active_download).pack(side=RIGHT, padx=(8, 0))
        ttk.Button(header, text=self.tr("繼續", "Resume"), style="Action.TButton", command=self.resume_active_download).pack(side=RIGHT, padx=(8, 0))
        ttk.Button(header, text=self.tr("取消", "Cancel"), style="Action.TButton", command=self.cancel_active_download).pack(side=RIGHT, padx=(8, 0))
        ttk.Button(header, text=self.tr("重試", "Retry"), style="Action.TButton", command=self.retry_active_download).pack(side=RIGHT, padx=(8, 0))
        ttk.Button(header, text=self.tr("移除", "Remove"), style="Action.TButton", command=self.remove_selected_from_plan).pack(side=RIGHT, padx=(8, 0))
        ttk.Button(header, text=self.tr("清空", "Clear"), style="Action.TButton", command=self.clear_download_plan).pack(side=RIGHT, padx=(8, 0))
        ttk.Button(header, text=self.tr("匯出計畫", "Export plan"), style="Action.TButton", command=self.export_download_plan).pack(side=RIGHT)
        body = ttk.Frame(plan, style="Panel.TFrame")
        body.pack(fill=X)
        self.download_plan_body = body
        ttk.Label(body, textvariable=self.plan_import_policy_var, style="DetailMuted.TLabel").pack(anchor="w", padx=14, pady=(0, 8))

        columns = ("name", "auth", "scope", "status", "import")
        self.cart_tree = ttk.Treeview(body, columns=columns, show="headings", height=4, selectmode="browse")
        for name, label, width, anchor in [
            ("name", self.tr("項目", "Item"), 260, "w"),
            ("auth", self.tr("認證", "Auth"), 150, "w"),
            ("scope", self.tr("範圍", "Scope"), 130, "w"),
            ("status", self.tr("下載狀態", "Download status"), 120, "center"),
            ("import", self.tr("匯入狀態", "Import status"), 210, "w"),
        ]:
            self.cart_tree.heading(name, text=label)
            self.cart_tree.column(name, width=width, anchor=anchor, stretch=True)
        self.cart_tree.pack(fill=X, padx=14, pady=(0, 12))
        self.cart_tree.bind("<<TreeviewSelect>>", self.on_cart_select)

        job_columns = ("name", "status", "progress", "import", "target")
        self.download_tree = ttk.Treeview(body, columns=job_columns, show="headings", height=4, selectmode="browse")
        for name, label, width, anchor in [
            ("name", self.tr("下載工作", "Download Job"), 240, "w"),
            ("status", self.tr("狀態", "Status"), 100, "center"),
            ("progress", self.tr("進度", "Progress"), 95, "center"),
            ("import", self.tr("匯入", "Import"), 190, "w"),
            ("target", self.tr("目標", "Target"), 360, "w"),
        ]:
            self.download_tree.heading(name, text=label)
            self.download_tree.column(name, width=width, anchor=anchor, stretch=True)
        self.download_tree.pack(fill=X, padx=14, pady=(0, 12))
        self.download_tree.bind("<<TreeviewSelect>>", self.on_download_select)
        self.apply_download_plan_visibility()

    def update_download_plan_toggle_label(self) -> None:
        # 收合時仍保留 header 與計數，讓使用者知道 plan 內還有幾個項目。
        label = self.tr("收合下載計畫", "Collapse plan") if self.download_plan_visible else self.tr("展開下載計畫", "Expand plan")
        self.download_plan_toggle_var.set(label)

    def apply_download_plan_visibility(self) -> None:
        # 只收合 plan body，不拆掉 header；下載工作仍在背景 queue 中持續更新。
        if not hasattr(self, "download_plan_body"):
            return
        if self.download_plan_visible:
            self.download_plan_body.pack(fill=X)
        else:
            self.download_plan_body.pack_forget()
        self.update_download_plan_toggle_label()

    def toggle_download_plan_panel(self) -> None:
        self.download_plan_visible = not self.download_plan_visible
        self.apply_download_plan_visibility()
        self.status_var.set(
            self.tr("已展開下載計畫。", "Download plan expanded.")
            if self.download_plan_visible
            else self.tr("已收合下載計畫。", "Download plan collapsed.")
        )
