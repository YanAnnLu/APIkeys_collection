"""Tk dialogs for AI profile and Google/Gemini connection settings."""

from __future__ import annotations

import webbrowser
from tkinter import BOTH, END, LEFT, RIGHT, WORD, X, Text, Toplevel, messagebox
from tkinter import ttk
from typing import Any

import APIkeys_collection as core
from api_launcher.account_links import DEFAULT_ACCOUNT_PROVIDERS, account_auth_mode_label, account_status_label
from api_launcher.google_auth import google_oauth_token_status
from api_launcher.oauth_device import oauth_device_config_from_profile, oauth_token_status
from frontends.tk.ui_config import COLORS


class AiModelSettingsDialog:
    def __init__(self, ui: Any):
        # AI profile 選擇視窗只負責表格與按鈕調度；OAuth/API key 的實作仍留在
        # 主 UI 現有方法，避免一次搬動 credential 相關流程造成風險。
        self.ui = ui
        self.root = ui.root
        self.dialog = Toplevel(self.root)
        self.dialog.title(self.ui.tr("AI 輔助模型", "AI assistant model"))
        self.dialog.configure(bg=COLORS["panel"])
        self.dialog.geometry("760x460")
        self.dialog.transient(self.root)
        self._build()

    @staticmethod
    def profile_row_values(
        profile: Any,
        *,
        active_profile_id: str,
        login_status: str,
        enabled_label: str,
        disabled_label: str,
    ) -> tuple[str, object, object, object, str, str, object]:
        # Treeview 欄位順序固定在 helper，讓測試能保護 UI row contract。
        return (
            "✓" if active_profile_id and active_profile_id == profile.id else "",
            profile.label,
            profile.kind,
            profile.model,
            login_status,
            enabled_label if profile.enabled else disabled_label,
            profile.notes,
        )

    def _build(self) -> None:
        ttk.Label(self.dialog, text=self.ui.tr("AI 輔助模型", "AI assistant model"), style="DetailTitle.TLabel").pack(anchor="w", padx=24, pady=(22, 8))
        ttk.Label(
            self.dialog,
            text=self.ui.tr(
                "選擇產生資料源描述時要調用的 AI profile。登入或 API key 可以先存在各 profile 裡，但真正使用哪個模型由這裡決定。",
                "Choose which AI profile should be used for dataset descriptions. Login/API keys can be stored per profile, but this setting decides which one is called.",
            ),
            style="DetailMuted.TLabel",
        ).pack(anchor="w", fill=X, padx=24, pady=(0, 14))
        self.table = ttk.Treeview(
            self.dialog,
            columns=("use", "label", "kind", "model", "login", "status", "notes"),
            show="headings",
            height=9,
            selectmode="browse",
        )
        for name, label, width in [
            ("use", self.ui.tr("使用", "Use"), 58),
            ("label", self.ui.tr("AI profile", "AI profile"), 150),
            ("kind", self.ui.tr("服務", "Service"), 110),
            ("model", self.ui.tr("模型", "Model"), 150),
            ("login", self.ui.tr("登入", "Login"), 150),
            ("status", self.ui.tr("狀態", "Status"), 80),
            ("notes", self.ui.tr("備註", "Notes"), 220),
        ]:
            self.table.heading(name, text=label)
            self.table.column(name, width=width, anchor="w", stretch=True)
        active = core.active_ai_profile()
        active_profile_id = active.id if active else ""
        for profile in core.ai_summary_profiles():
            self.table.insert(
                "",
                END,
                iid=profile.id,
                values=self.profile_row_values(
                    profile,
                    active_profile_id=active_profile_id,
                    login_status=self.ui.ai_profile_login_status(profile),
                    enabled_label=self.ui.tr("啟用", "Enabled"),
                    disabled_label=self.ui.tr("停用", "Disabled"),
                ),
            )
        self.table.pack(fill=BOTH, expand=True, padx=24, pady=(0, 14))
        if active:
            self.table.selection_set(active.id)
            self.table.focus(active.id)

        actions = ttk.Frame(self.dialog, style="Panel.TFrame")
        actions.pack(fill=X, padx=24, pady=(0, 18))
        self.table.bind("<Double-1>", lambda _event: self.use_selected())
        ttk.Button(actions, text=self.ui.tr("使用選取模型", "Use selected model"), style="Action.TButton", command=self.use_selected).pack(side=LEFT, padx=(0, 10))
        ttk.Button(
            actions,
            text=self.ui.tr("開發者 OAuth 設定", "Developer OAuth setup"),
            style="Action.TButton",
            command=lambda: self.ui.configure_oauth_client_for_selected(self.table, parent=self.dialog),
        ).pack(side=LEFT, padx=(0, 10))
        ttk.Button(actions, text=self.ui.tr("未來：帳號登入", "Future: account sign-in"), style="Action.TButton", command=self.login_selected).pack(side=LEFT, padx=(0, 10))
        ttk.Button(actions, text=self.ui.tr("保存 API key", "Save API key"), style="Action.TButton", command=self.paste_key_for_selected).pack(side=LEFT, padx=(0, 10))
        ttk.Button(actions, text=self.ui.tr("顯示本機設定檔", "Reveal local config"), style="Action.TButton", command=self.ui.open_integration_config_file).pack(side=LEFT, padx=(0, 10))
        ttk.Button(actions, text=self.ui.tr("關閉", "Close"), style="Action.TButton", command=self.dialog.destroy).pack(side=RIGHT)

    def _selected_profile_id(self) -> str | None:
        selection = self.table.selection()
        if not selection:
            return None
        return str(selection[0])

    def _show_missing_selection(self) -> None:
        messagebox.showinfo(
            self.ui.tr("尚未選取", "Nothing selected"),
            self.ui.tr("請先選取一個 AI profile。", "Select an AI profile first."),
            parent=self.dialog,
        )

    def use_selected(self) -> None:
        selected_profile_id = self._selected_profile_id()
        if not selected_profile_id:
            self._show_missing_selection()
            return
        try:
            selected = core.set_active_ai_profile(selected_profile_id)
        except Exception as exc:
            messagebox.showerror(self.ui.tr("AI 模型設定失敗", "AI model setup failed"), str(exc), parent=self.dialog)
            return
        self.ui.selected_ai_profile_id = selected.id
        for item in self.table.get_children():
            values = list(self.table.item(item, "values"))
            values[0] = "✓" if item == selected.id else ""
            self.table.item(item, values=values)
        self.ui.status_var.set(self.ui.tr(f"AI 輔助模型已設定：{selected.label}", f"AI assistant model set: {selected.label}"))

    def login_selected(self) -> None:
        selected_profile_id = self._selected_profile_id()
        if not selected_profile_id:
            self._show_missing_selection()
            return
        self.ui.open_ai_profile_browser_login_dialog(selected_profile_id, parent=self.dialog)

    def paste_key_for_selected(self) -> None:
        selected_profile_id = self._selected_profile_id()
        self.ui.configure_ai_api_key_session(selected_profile_id)
        for item in self.table.get_children():
            profile = next((candidate for candidate in core.ai_summary_profiles() if candidate.id == item), None)
            if profile:
                values = list(self.table.item(item, "values"))
                values[4] = self.ui.ai_profile_login_status(profile)
                self.table.item(item, values=values)


class GoogleGeminiSettingsDialog:
    def __init__(self, ui: Any):
        # 這個 dialog 只負責 Google/Gemini 入口的說明與按鈕編排；credential 寫入、
        # OAuth browser flow 與 API key 儲存仍委派回主 UI，避免拆分時改到登入安全邊界。
        self.ui = ui
        self.root = ui.root
        self.dialog = Toplevel(self.root)
        self.dialog.title(self.ui.tr("Gemini / Google 連線", "Gemini / Google connection"))
        self.dialog.configure(bg=COLORS["panel"])
        self.dialog.geometry("840x560")
        self.dialog.transient(self.root)
        self.dialog.grab_set()
        self._build()

    @staticmethod
    def account_provider_row_values(provider: Any) -> tuple[object, object, object, str]:
        # 帳號支援表格的欄位順序固定在 helper，讓 headless 測試不用真的開 Tk 視窗。
        return (
            provider.label,
            account_auth_mode_label(str(provider.auth_mode or "")),
            account_status_label(str(provider.status or "")),
            ", ".join(provider.capability_targets),
        )

    def _profile_status_texts(self) -> tuple[str, str]:
        profile = core.active_ai_profile()
        profile_text = (
            self.ui.tr(
                f"目前 AI profile：{profile.label} ({profile.kind})",
                f"Current AI profile: {profile.label} ({profile.kind})",
            )
            if profile
            else self.ui.tr("目前沒有啟用 AI profile。", "No active AI profile.")
        )
        gemini_profile = next((item for item in core.ai_summary_profiles() if item.id == "gemini_flash"), None)
        gemini_oauth = oauth_device_config_from_profile(gemini_profile) if gemini_profile else None
        if gemini_oauth:
            token_status, token_message = oauth_token_status(gemini_oauth.token_store, label=gemini_profile.label)
        else:
            token_status, token_message = google_oauth_token_status()
        token_text = self.ui.tr(
            f"Gemini / Google token：{token_status} - {token_message}",
            f"Gemini / Google token: {token_status} - {token_message}",
        )
        return profile_text, token_text

    def _connection_message(self, profile_text: str, token_text: str) -> str:
        # 長說明文字留在 dialog class，主 UI 不需要知道這個產品教育文案如何排版。
        return self.ui.tr(
            "\n".join(
                [
                    "這裡是 Google / Gemini 連線入口。",
                    "白話說：它不是展示用空殼，但 Google 帳號登入還需要專案端把官方 OAuth App 配好。",
                    "一般網站能直接讓你選 Google 帳號，是因為網站已經替使用者處理好 OAuth App 身分；使用者不該被要求貼 Client ID。",
                    "這裡只負責登入、token 與 Google 相關設定；真正要調用哪個 AI，請到「整合 > AI 輔助模型選擇」選。",
                    "",
                    profile_text,
                    token_text,
                    "",
                    "目前支援：",
                    "1. Google 帳號瀏覽器登入：專案 OAuth App 配好後，才會打開 Google 授權頁並把 token 存在本機 private state。",
                    "2. Google QR/device-code：同樣需要官方 OAuth App 與 device-code 端點，不能在缺設定時硬造。",
                    "3. Gemini API key：作為目前 MVP 主路線，保存到本機 private state，下次啟動自動載入。",
                    "",
                    "目前開發版不會要求一般使用者貼 OAuth Client ID；那是專案/開發者要負責配置的事情。",
                ]
            ),
            "\n".join(
                [
                    "This panel is the Google/Gemini connection entry point.",
                    "Plainly: it is not a fake shell, but Google account login still needs the project to provide an official OAuth app.",
                    "Normal web services can let you choose a Google account because the service already owns the OAuth app identity; users should not be asked to paste a Client ID.",
                    "It handles login, tokens, and Google-related setup only. Choose the model under Integrations > AI assistant model selection.",
                    "",
                    profile_text,
                    token_text,
                    "",
                    "Currently supported:",
                    "1. Google browser account login: after the project OAuth app is configured, opens Google's authorization page and stores the token under local private state.",
                    "2. Google QR/device-code: also needs an official OAuth app and device-code endpoint; it cannot be invented when setup is missing.",
                    "3. Gemini API key: the current MVP path, saved under local private state and loaded automatically next launch.",
                    "",
                    "This development build will not ask normal users to paste an OAuth Client ID; that is a project/developer responsibility.",
                ]
            ),
        )

    def _build(self) -> None:
        ttk.Label(self.dialog, text=self.ui.tr("Gemini / Google 連線", "Gemini / Google connection"), style="DetailTitle.TLabel").pack(anchor="w", padx=24, pady=(22, 8))
        profile_text, token_text = self._profile_status_texts()
        readiness_text = self.ui.tr(
            "目前狀態：AI 生成管線已存在；Google 帳號登入需要專案端先配置官方 OAuth App，才會像一般網站一樣開瀏覽器選帳號或掃碼。",
            "Current status: AI generation exists; Google account login needs the project to provide an official OAuth app before it can open a normal browser account chooser or QR flow.",
        )
        ttk.Label(self.dialog, text=readiness_text, style="DetailMuted.TLabel", wraplength=760).pack(anchor="w", padx=24, pady=(0, 10))
        text = Text(self.dialog, height=12, wrap=WORD, bg=COLORS["bg"], fg=COLORS["text"], relief="flat", padx=16, pady=14, font=("Helvetica", 11))
        text.pack(fill=X, expand=False, padx=24, pady=(0, 14))
        text.insert("1.0", self._connection_message(profile_text, token_text))
        text.configure(state="disabled")

        providers = ttk.Treeview(self.dialog, columns=("provider", "mode", "status", "targets"), show="headings", height=3)
        for name, label, width in [
            ("provider", self.ui.tr("帳號", "Account"), 110),
            ("mode", self.ui.tr("登入模式", "Login mode"), 140),
            ("status", self.ui.tr("狀態", "Status"), 90),
            ("targets", self.ui.tr("能力目標", "Capability targets"), 230),
        ]:
            providers.heading(name, text=label)
            providers.column(name, width=width, anchor="w", stretch=True)
        for provider in DEFAULT_ACCOUNT_PROVIDERS:
            providers.insert("", END, values=self.account_provider_row_values(provider))
        providers.pack(fill=X, padx=24, pady=(0, 14))

        actions = ttk.Frame(self.dialog, style="Panel.TFrame")
        actions.pack(fill=X, padx=24, pady=(0, 20))
        primary_actions = ttk.Frame(actions, style="Panel.TFrame")
        primary_actions.pack(fill=X, pady=(0, 8))
        secondary_actions = ttk.Frame(actions, style="Panel.TFrame")
        secondary_actions.pack(fill=X)

        # 主要按鈕走 MVP API key 與模型設定；中期 OAuth 按鈕仍保留但交由既有安全流程處理。
        ttk.Button(primary_actions, text=self.ui.tr("保存 Gemini API key 並啟用", "Save Gemini API key and enable"), style="Action.TButton", command=lambda: self.ui.configure_ai_api_key_session("gemini_flash", parent=self.dialog)).pack(side=LEFT, padx=(0, 10))
        ttk.Button(primary_actions, text=self.ui.tr("AI 模型設定", "AI model settings"), style="Action.TButton", command=self.ui.open_ai_model_settings).pack(side=LEFT, padx=(0, 10))
        ttk.Button(primary_actions, text=self.ui.tr("產生目前資料源描述", "Generate selected source description"), style="Action.TButton", command=self.ui.generate_active_summary).pack(side=LEFT, padx=(0, 10))
        ttk.Button(primary_actions, text=self.ui.tr("關閉", "Close"), style="Action.TButton", command=self.dialog.destroy).pack(side=RIGHT)
        ttk.Button(secondary_actions, text=self.ui.tr("中期：Google 帳號登入", "Mid-term: Google account login"), style="Action.TButton", command=lambda: self.ui.open_ai_profile_browser_login_dialog("gemini_flash", parent=self.dialog)).pack(side=LEFT, padx=(0, 10))
        ttk.Button(secondary_actions, text=self.ui.tr("中期：QR / 裝置碼", "Mid-term: QR / device code"), style="Action.TButton", command=lambda: self.ui.open_ai_profile_login_dialog("gemini_flash", parent=self.dialog)).pack(side=LEFT, padx=(0, 10))
        ttk.Button(secondary_actions, text=self.ui.tr("開發期備用：Google AI Studio", "Development fallback: Google AI Studio"), style="Action.TButton", command=lambda: webbrowser.open("https://aistudio.google.com/app/apikey")).pack(side=LEFT, padx=(0, 10))
        ttk.Button(secondary_actions, text=self.ui.tr("顯示本機整合設定檔", "Reveal local integration config"), style="Action.TButton", command=self.ui.open_integration_config_file).pack(side=LEFT, padx=(0, 10))
