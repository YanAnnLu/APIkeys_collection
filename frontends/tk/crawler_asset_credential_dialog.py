from __future__ import annotations

import webbrowser
from typing import Mapping
from tkinter import BOTH, LEFT, RIGHT, BooleanVar, StringVar, Toplevel, X
from tkinter import ttk

from api_launcher.crawler_assets import CrawlerAsset
from frontends.tk.ui_config import COLORS


def crawler_asset_credential_edit_payload(
    field_values: Mapping[str, object],
    clear_flags: Mapping[str, object],
    *,
    remember_local: object = True,
) -> dict[str, object]:
    """Build the backend credential update payload from UI field state.

    The dialog never pre-fills or returns saved secret values.  Non-empty entry
    text means "set/update this credential"; a clear checkbox means "remove the
    saved value" when no replacement value was entered.
    """

    values: dict[str, str] = {}
    clear: list[str] = []
    for raw_key, raw_value in field_values.items():
        key = str(raw_key or "").strip()
        value = str(raw_value or "").strip()
        if key and value:
            values[key] = value
    for raw_key, raw_flag in clear_flags.items():
        key = str(raw_key or "").strip()
        if key and bool(raw_flag) and key not in values:
            clear.append(key)
    return {
        "remember_local": bool(remember_local),
        "values": values,
        "clear": sorted(clear),
    }


def crawler_asset_credential_next_action_text(credential_status: Mapping[str, object]) -> str:
    """Return the user-facing next-action label for the credential dialog.

    Raw `next_action` ids are useful for logs and agent JSON, but they should
    not be shown as the primary instruction in a human login form.
    """

    display_profile = credential_status.get("display_profile")
    profile = display_profile if isinstance(display_profile, dict) else {}
    for candidate in (
        credential_status.get("next_action_label_zh_TW"),
        profile.get("next_action_label_zh_TW"),
        credential_status.get("next_action_label"),
        profile.get("next_action_label"),
        credential_status.get("next_action_label_en"),
        profile.get("next_action_label_en"),
    ):
        label = str(candidate or "").strip()
        if label:
            return label
    return ""


def crawler_asset_credential_subtitle(asset: CrawlerAsset, credential_status: Mapping[str, object]) -> str:
    """Return a UI-safe provenance line for the credential dialog header.

    Login settings need stable ids for support and debugging, but raw provider
    or asset ids should be labelled so they do not read like the main title.
    """

    provider_name = str(credential_status.get("provider_name") or "").strip() or "Provider 待確認"
    source_label = str(getattr(asset, "source_type_label", "") or "").strip() or "來源範式待確認"
    provider_id = str(getattr(asset, "provider_id", "") or "").strip() or "Provider ID 待確認"
    asset_id = str(getattr(asset, "asset_id", "") or "").strip() or "Asset ID 待確認"
    return f"Provider：{provider_name} / Source：{source_label} / Provider ID：{provider_id} / Asset ID：{asset_id}"


class CrawlerAssetCredentialDialog:
    """Tk login/settings dialog for crawler assets.

    This is intentionally a thin form.  It reads the UI-safe payload produced by
    ``api_launcher.local_credentials.crawler_asset_credential_status()`` and
    returns a structured update payload for
    ``update_crawler_asset_credentials()``.  It does not decide which source
    needs credentials and never logs or displays raw saved secrets.
    """

    def __init__(self, parent: object, asset: CrawlerAsset, credential_status: Mapping[str, object]):
        self.parent = parent
        self.asset = asset
        self.credential_status = dict(credential_status)
        self.result: dict[str, object] | None = None
        self.window = Toplevel(parent)
        self.window.title(f"登入設定 - {asset.display_name}")
        self.window.transient(parent)
        self.window.grab_set()
        self.window.configure(bg=COLORS["panel"])
        self.window.minsize(680, 520)

        fields = self.credential_status.get("fields") if isinstance(self.credential_status.get("fields"), list) else []
        self.fields = [field for field in fields if isinstance(field, dict)]
        self.value_vars = {
            str(field.get("env_var") or ""): StringVar(value="")
            for field in self.fields
            if str(field.get("env_var") or "").strip()
        }
        self.clear_vars = {
            str(field.get("env_var") or ""): BooleanVar(value=False)
            for field in self.fields
            if str(field.get("env_var") or "").strip()
        }
        self.remember_var = BooleanVar(value=bool(self.credential_status.get("remember_local_default", True)))

        self._build()
        self.window.bind("<Escape>", lambda _event: self.cancel())
        self.window.protocol("WM_DELETE_WINDOW", self.cancel)
        self.window.wait_window()

    def _build(self) -> None:
        frame = ttk.Frame(self.window, style="Panel.TFrame")
        frame.pack(fill=BOTH, expand=True, padx=22, pady=22)

        label = str(self.credential_status.get("display_label") or "登入設定").strip()
        ttk.Label(frame, text=f"{label} - {self.asset.display_name}", style="DetailTitle.TLabel").pack(anchor="w")
        ttk.Label(
            frame,
            text=crawler_asset_credential_subtitle(self.asset, self.credential_status),
            style="DetailMuted.TLabel",
        ).pack(anchor="w", fill=X, pady=(4, 12))
        ttk.Label(
            frame,
            text="像登入 email 一樣：先到官方入口申請或登入，拿到 API Key / Token 後貼在這裡。留空代表不變。",
            style="DetailText.TLabel",
            wraplength=620,
        ).pack(anchor="w", pady=(0, 12))
        next_action_label = crawler_asset_credential_next_action_text(self.credential_status)
        if next_action_label:
            ttk.Label(
                frame,
                text=f"下一步：{next_action_label}",
                style="DetailText.TLabel",
                wraplength=620,
            ).pack(anchor="w", pady=(0, 12))

        entry_url = str(self.credential_status.get("credential_entry_url") or "").strip()
        entry_label = str(self.credential_status.get("credential_entry_label") or "開啟官方登入 / 申請 API Key").strip()
        if entry_url:
            ttk.Button(
                frame,
                text=entry_label,
                style="Action.TButton",
                command=lambda: webbrowser.open(entry_url),
            ).pack(anchor="w", pady=(0, 12))

        if not self.fields:
            ttk.Label(
                frame,
                text="這個爬蟲尚未宣告可編輯的登入欄位。請先在爬蟲設定裡補上 API key 環境變數名，或更新 provider profile。",
                style="DetailText.TLabel",
                wraplength=620,
            ).pack(anchor="w", pady=(4, 12))
        for field in self.fields:
            self._build_field(frame, field)

        ttk.Checkbutton(frame, text="記住我的帳號", variable=self.remember_var).pack(anchor="w", pady=(12, 2))
        ttk.Label(
            frame,
            text="勾選後會保存到本機忽略檔；不勾選則只在目前程式執行期間使用。不要把金鑰提交到 Git。",
            style="DetailMuted.TLabel",
            wraplength=620,
        ).pack(anchor="w")

        buttons = ttk.Frame(frame, style="Panel.TFrame")
        buttons.pack(fill=X, pady=(18, 0))
        ttk.Button(buttons, text="儲存登入設定", style="Action.TButton", command=self.save).pack(side=RIGHT, padx=(10, 0))
        ttk.Button(buttons, text="取消", style="Action.TButton", command=self.cancel).pack(side=RIGHT)

    def _build_field(self, frame: ttk.Frame, field: Mapping[str, object]) -> None:
        env_var = str(field.get("env_var") or "").strip()
        if not env_var:
            return
        label = str(field.get("label") or env_var).strip()
        required = " *" if bool(field.get("required")) else ""
        configured = "已設定" if bool(field.get("configured")) else "尚未設定"
        preview = str(field.get("value_preview") or "").strip()
        ttk.Label(frame, text=f"{label}{required} ({env_var})", style="DetailSection.TLabel").pack(anchor="w", pady=(8, 2))
        row = ttk.Frame(frame, style="Panel.TFrame")
        row.pack(fill=X)
        entry = ttk.Entry(row, textvariable=self.value_vars[env_var], font=("Helvetica", 11), show="*")
        entry.pack(side=LEFT, fill=X, expand=True)
        ttk.Checkbutton(row, text="清除已保存", variable=self.clear_vars[env_var]).pack(side=RIGHT, padx=(8, 0))
        current_text = f"目前：{configured}"
        if preview:
            current_text = f"{current_text}（{preview}）"
        help_text = str(field.get("help_text") or "").strip()
        ttk.Label(frame, text=f"{current_text}。{help_text}", style="DetailMuted.TLabel", wraplength=620).pack(anchor="w", pady=(2, 0))

    def save(self) -> None:
        self.result = crawler_asset_credential_edit_payload(
            {key: var.get() for key, var in self.value_vars.items()},
            {key: var.get() for key, var in self.clear_vars.items()},
            remember_local=self.remember_var.get(),
        )
        self.window.destroy()

    def cancel(self) -> None:
        self.result = None
        self.window.destroy()


__all__ = [
    "CrawlerAssetCredentialDialog",
    "crawler_asset_credential_edit_payload",
    "crawler_asset_credential_next_action_text",
    "crawler_asset_credential_subtitle",
]
