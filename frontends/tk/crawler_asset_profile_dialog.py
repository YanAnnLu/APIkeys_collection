from __future__ import annotations

from tkinter import BOTH, LEFT, RIGHT, X, BooleanVar, StringVar, Toplevel, filedialog
from tkinter import ttk

from api_launcher.crawler_assets import CrawlerAsset
from frontends.tk.ui_config import COLORS


PROFILE_BOOLEAN_FIELDS: tuple[tuple[str, str, str], ...] = (
    ("enabled", "啟用這個爬蟲", "Enabled"),
    ("archived", "封存這個爬蟲", "Archived"),
)

PROFILE_TEXT_FIELDS: tuple[tuple[str, str, str, str], ...] = (
    ("credential_profile_id", "憑證設定檔 ID", "Credential profile ID", "例如 nasa_earthdata_personal；不填代表無憑證。"),
    ("api_key_env_var", "API key 環境變數名", "API key env var", "只填變數名，例如 FRED_API_KEY；不要填真實 token。"),
    ("account_hint", "帳號提示", "Account hint", "提醒使用者去哪裡申請帳號或 API key。"),
    ("schedule_policy", "自動化排程", "Schedule policy", "例如 manual、daily、weekly；目前只作為設定資料保存。"),
    ("rate_limit_policy", "限流策略", "Rate-limit policy", "例如 polite_1rps、provider_default。"),
    ("retry_policy", "重試策略", "Retry policy", "例如 retry_3_backoff；實際執行策略後續接線。"),
    ("seed_scope_policy", "Seed 範圍策略", "Seed scope policy", "bounded / complete / manual；預設 bounded。"),
    ("status_note", "狀態備註", "Status note", "給自己或其他 Agent 的維護備註。"),
    ("local_logo_path", "自訂 Logo 路徑", "Local logo path", "可留空；未來卡片 UI 會優先使用這個本機圖片。"),
    ("official_logo_url", "官方 Logo URL", "Official logo URL", "可留空；保存來源即可，不在這裡下載。"),
    ("favicon_url", "Favicon URL", "Favicon URL", "可留空；供未來快取器使用。"),
    ("logo_source", "Logo 來源", "Logo source", "例如 official_site、manual、generated。"),
    ("logo_license_note", "Logo 授權備註", "Logo license note", "記錄可否展示、是否只能本機使用。"),
)


class CrawlerAssetProfileDialog:
    """Tk 版 crawler asset profile 編輯器。

    Dialog 只收集 profile 表單值；實際驗證與保存交給
    api_launcher.crawler_asset_profiles.update_crawler_asset_profile()。
    這讓未來 Qt 介面可以重用同一份後端契約。
    """

    def __init__(self, parent: object, asset: CrawlerAsset):
        self.parent = parent
        self.asset = asset
        self.result: dict[str, object] | None = None
        self.window = Toplevel(parent)
        self.window.title(f"爬蟲設定 - {asset.display_name}")
        self.window.transient(parent)
        self.window.grab_set()
        self.window.configure(bg=COLORS["panel"])
        self.window.minsize(680, 760)

        self.bool_vars = {
            field_id: BooleanVar(value=bool(getattr(asset, field_id, False)))
            for field_id, _label_zh, _label_en in PROFILE_BOOLEAN_FIELDS
        }
        self.vars = {
            field_id: StringVar(value=str(getattr(asset, field_id, "") or ""))
            for field_id, _label_zh, _label_en, _help_text in PROFILE_TEXT_FIELDS
        }

        self._build()
        self.window.bind("<Escape>", lambda _event: self.cancel())
        self.window.protocol("WM_DELETE_WINDOW", self.cancel)
        self.window.wait_window()

    def _build(self) -> None:
        frame = ttk.Frame(self.window, style="Panel.TFrame")
        frame.pack(fill=BOTH, expand=True, padx=22, pady=22)

        ttk.Label(frame, text=self.asset.display_name, style="DetailTitle.TLabel").pack(anchor="w")
        ttk.Label(
            frame,
            text=f"{self.asset.provider_id} / {self.asset.source_type} / {self.asset.asset_id}",
            style="DetailMuted.TLabel",
        ).pack(anchor="w", fill=X, pady=(4, 12))

        toggles = ttk.Frame(frame, style="Panel.TFrame")
        toggles.pack(fill=X, pady=(0, 10))
        for field_id, label_zh, _label_en in PROFILE_BOOLEAN_FIELDS:
            ttk.Checkbutton(toggles, text=label_zh, variable=self.bool_vars[field_id]).pack(side=LEFT, padx=(0, 18))

        for field_id, label_zh, _label_en, help_text in PROFILE_TEXT_FIELDS:
            ttk.Label(frame, text=label_zh, style="DetailSection.TLabel").pack(anchor="w", pady=(8, 2))
            row = ttk.Frame(frame, style="Panel.TFrame")
            row.pack(fill=X)
            entry = ttk.Entry(row, textvariable=self.vars[field_id], font=("Helvetica", 11))
            entry.pack(side=LEFT, fill=X, expand=True)
            if field_id == "local_logo_path":
                ttk.Button(row, text="選擇", style="Action.TButton", command=self.choose_local_logo_path).pack(side=RIGHT, padx=(8, 0))
            ttk.Label(frame, text=help_text, style="DetailMuted.TLabel", wraplength=620).pack(anchor="w", pady=(2, 0))

        buttons = ttk.Frame(frame, style="Panel.TFrame")
        buttons.pack(fill=X, pady=(18, 0))
        ttk.Button(buttons, text="儲存", style="Action.TButton", command=self.save).pack(side=RIGHT, padx=(10, 0))
        ttk.Button(buttons, text="取消", style="Action.TButton", command=self.cancel).pack(side=RIGHT)

    def choose_local_logo_path(self) -> None:
        path = filedialog.askopenfilename(
            parent=self.window,
            title="選擇爬蟲 Logo",
            filetypes=(("Image files", "*.png *.jpg *.jpeg *.gif *.webp *.ico"), ("All files", "*.*")),
        )
        if path:
            self.vars["local_logo_path"].set(path)

    def form_values(self) -> dict[str, object]:
        values: dict[str, object] = {field_id: bool(var.get()) for field_id, var in self.bool_vars.items()}
        for field_id, var in self.vars.items():
            values[field_id] = str(var.get() or "").strip()
        return values

    def save(self) -> None:
        self.result = self.form_values()
        self.window.destroy()

    def cancel(self) -> None:
        self.result = None
        self.window.destroy()


__all__ = [
    "CrawlerAssetProfileDialog",
    "PROFILE_BOOLEAN_FIELDS",
    "PROFILE_TEXT_FIELDS",
]
