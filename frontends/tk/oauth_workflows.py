"""Tk OAuth/login workflows for RuRuKa Asset Launcher.

這個 mixin 集中 OAuth Client ID、Google 登入、device-code 與 API key session 流程，
讓主視窗避免繼續承擔長篇登入對話與本機 callback server 細節。
"""

from __future__ import annotations

import html
import os
import secrets
import threading
import time
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from tkinter import BOTH, END, LEFT, RIGHT, WORD, X, StringVar, TclError, Text, Tk, Toplevel, messagebox, simpledialog
from tkinter import ttk

import APIkeys_collection as core
from api_launcher.ai_api_keys import save_ai_api_key
from api_launcher.integrations import save_integration_config
from api_launcher.oauth_device import (
    activate_saved_oauth_token,
    build_oauth_device_login_request,
    exchange_oauth_authorization_code,
    looks_like_google_oauth_client_id,
    oauth_authorization_url,
    oauth_device_config_from_profile,
    pkce_code_challenge,
    poll_oauth_device_token,
    save_oauth_config_token,
    save_oauth_device_token,
)
from frontends.tk.ui_config import COLORS, PRODUCT_DISPLAY_NAME


class OAuthWorkflowMixin:
    """封裝 OAuth/login 對話流程；不改變目前的中期/開發者登入邊界。"""

    def configure_oauth_client_for_selected(self, table: ttk.Treeview, parent: Toplevel | None = None) -> None:
        selection = table.selection()
        if not selection:
            messagebox.showinfo(self.tr("尚未選取", "Nothing selected"), self.tr("請先選取一個 AI profile。", "Select an AI profile first."), parent=parent or self.root)
            return
        profile_id = str(selection[0])
        if self.configure_oauth_client_for_profile(profile_id, parent=parent, start_login=False):
            profile = next((candidate for candidate in core.ai_summary_profiles() if candidate.id == profile_id), None)
            if profile:
                values = list(table.item(profile_id, "values"))
                values[4] = self.ai_profile_login_status(profile)
                table.item(profile_id, values=values)

    def configure_oauth_client_for_profile(
        self,
        profile_id: str = "gemini_flash",
        parent: Toplevel | None = None,
        start_login: bool = False,
        continue_to_browser: bool = False,
    ) -> bool:
        profile = next((item for item in core.ai_summary_profiles() if item.id == profile_id), None)
        if profile is None:
            messagebox.showinfo(self.tr("尚未設定 AI profile", "No AI profile"), self.tr("找不到這個 AI profile。", "This AI profile was not found."), parent=parent or self.root)
            return False
        oauth_config = oauth_device_config_from_profile(profile)
        if oauth_config is None:
            messagebox.showinfo(
                self.tr("此 profile 沒有 QR 登入", "No QR login for this profile"),
                self.tr(f"{profile.label} 目前沒有 OAuth device-code 設定。", f"{profile.label} has no OAuth device-code settings."),
                parent=parent or self.root,
            )
            return False
        current_client_id = oauth_config.client_id or (os.environ.get(oauth_config.client_id_env, "").strip() if oauth_config.client_id_env else "")
        client_id = self.ask_oauth_client_id_with_guide(profile.label, current_client_id, provider=oauth_config.provider, parent=parent or self.root)
        if not client_id:
            return False
        if not self.save_oauth_client_id_for_profile(profile_id, oauth_config, client_id.strip(), parent=parent or self.root):
            return False
        self.status_var.set(self.tr(f"{profile.label} 已儲存 Google OAuth Client ID。", f"{profile.label} Google OAuth Client ID saved."))
        messagebox.showinfo(
            self.tr("Google 登入已設定", "Google login configured"),
            self.tr(
                "已儲存 Client ID。接下來可以開啟 Google 帳號登入。",
                "Client ID saved. You can now start Google account login.",
            ),
            parent=parent or self.root,
        )
        if start_login:
            self.open_ai_profile_login_dialog(profile_id, parent=parent)
        if continue_to_browser:
            self.open_ai_profile_browser_login_dialog(profile_id, parent=parent)
        return True

    def ask_oauth_client_id_with_guide(self, profile_label: str, current_client_id: str = "", provider: str = "", parent: Toplevel | Tk | None = None) -> str:
        owner = parent or self.root
        dialog = Toplevel(owner)
        dialog.title(self.tr("開發者 Google OAuth 設定", "Developer Google OAuth setup"))
        dialog.configure(bg=COLORS["panel"])
        dialog.geometry("720x520")
        dialog.transient(owner)
        dialog.grab_set()
        result: dict[str, str] = {"client_id": ""}

        ttk.Label(dialog, text=self.tr("開發者 Google OAuth 設定", "Developer Google OAuth setup"), style="DetailTitle.TLabel").pack(anchor="w", padx=24, pady=(22, 8))
        ttk.Label(
            dialog,
            text=self.tr(
                "這是開發者設定，不是一般使用者登入。它不是要你的 Gmail、密碼或 API key；它是在設定「這個 launcher 以什麼 App 身分向 Google 要授權」。",
                "This is developer setup, not normal user sign-in. It is not asking for your Gmail, password, or API key; it sets the app identity this launcher uses when asking Google for authorization.",
            ),
            style="DetailMuted.TLabel",
            wraplength=660,
        ).pack(anchor="w", fill=X, padx=24, pady=(0, 12))

        explanation = Text(dialog, height=11, wrap=WORD, bg=COLORS["bg"], fg=COLORS["text"], relief="flat", padx=16, pady=14, font=("Helvetica", 11))
        explanation.pack(fill=X, padx=24, pady=(0, 14))
        explanation.insert(
            "1.0",
            self.tr(
                "\n".join(
                    [
                        f"目前要設定：{profile_label}",
                        "",
                        "白話說，Google 登入分兩步：",
                        "1. App 身分：Google 先確認是哪個 App 要請你授權。這就是 OAuth Client ID，應由專案端準備好。",
                        "2. 使用者登入：App 身分存在後，launcher 才會打開 Google 網頁，讓你選帳號或使用 Google 提供的手機確認 / 掃碼登入。",
                        "",
                        "一般使用者不應該被要求貼這個值；這個入口只保留給正在替專案配置 OAuth 的開發者。",
                    ]
                ),
                "\n".join(
                    [
                        f"Current profile: {profile_label}",
                        "",
                        "Plainly, Google login has two steps:",
                        "1. App identity: Google first checks which app is asking for authorization. This is the OAuth Client ID, and the project should provide it.",
                        "2. User sign-in: after the app identity exists, the launcher opens Google's page so you can choose an account or use Google's phone/QR options.",
                        "",
                        "Normal users should not be asked to paste this value; this entry point is only for developers configuring OAuth for the project.",
                    ]
                ),
            ),
        )
        explanation.configure(state="disabled")

        form = ttk.Frame(dialog, style="Panel.TFrame")
        form.pack(fill=X, padx=24, pady=(0, 14))
        ttk.Label(form, text=self.tr("OAuth Client ID", "OAuth Client ID"), style="DetailSection.TLabel").pack(anchor="w")
        client_id_var = StringVar(value=current_client_id)
        client_entry = ttk.Entry(form, textvariable=client_id_var, font=("Helvetica", 12))
        client_entry.pack(fill=X, pady=(6, 0))
        client_entry.focus_set()

        actions = ttk.Frame(dialog, style="Panel.TFrame")
        actions.pack(fill=X, padx=24, pady=(0, 20))

        def save_and_close() -> None:
            candidate = client_id_var.get().strip()
            if provider == "google" and not looks_like_google_oauth_client_id(candidate):
                messagebox.showwarning(
                    self.tr("OAuth Client ID 格式不正確", "Invalid OAuth Client ID format"),
                    self.tr(
                        "這個值不會被保存，因為它不像 Google OAuth Client ID。\n\n如果你不是正在替專案配置 OAuth，請直接取消；一般使用者不需要處理這串值。\n\n合法格式通常是：\nxxxxx.apps.googleusercontent.com",
                        "This value will not be saved because it does not look like a Google OAuth Client ID.\n\nIf you are not configuring OAuth for the project, cancel this dialog; normal users do not need to handle this value.\n\nA valid value usually looks like:\nxxxxx.apps.googleusercontent.com",
                    ),
                    parent=dialog,
                )
                return
            result["client_id"] = candidate
            dialog.destroy()

        def cancel() -> None:
            result["client_id"] = ""
            dialog.destroy()

        ttk.Button(
            actions,
            text=self.tr("開啟 Google Cloud OAuth 設定頁", "Open Google Cloud OAuth setup"),
            style="Action.TButton",
            command=lambda: webbrowser.open("https://console.cloud.google.com/apis/credentials"),
        ).pack(side=LEFT, padx=(0, 10))
        ttk.Button(actions, text=self.tr("儲存後繼續登入", "Save and continue login"), style="Action.TButton", command=save_and_close).pack(side=RIGHT, padx=(10, 0))
        ttk.Button(actions, text=self.tr("取消", "Cancel"), style="Action.TButton", command=cancel).pack(side=RIGHT)
        dialog.protocol("WM_DELETE_WINDOW", cancel)
        owner.wait_window(dialog)
        return result["client_id"]

    def save_oauth_client_id_for_profile(self, profile_id: str, oauth_config: object, client_id: str, parent: Toplevel | Tk | None = None) -> bool:
        if not client_id:
            return False
        if oauth_config.provider == "google" and not looks_like_google_oauth_client_id(client_id):
            messagebox.showwarning(
                self.tr("OAuth Client ID 格式不正確", "Invalid OAuth Client ID format"),
                self.tr(
                    "這個 Client ID 看起來不是 Google OAuth Client ID，因此沒有保存。",
                    "This Client ID does not look like a Google OAuth Client ID, so it was not saved.",
                ),
                parent=parent or self.root,
            )
            return False
        config = core.ensure_local_integration_config()
        profiles = config.setdefault("ai_summary_profiles", [])
        target = next((item for item in profiles if str(item.get("id") or "").strip() == profile_id), None)
        if target is None:
            messagebox.showerror(
                self.tr("AI 設定失敗", "AI setup failed"),
                self.tr(f"本機設定檔中找不到 profile：{profile_id}", f"Profile not found in local config: {profile_id}"),
                parent=parent or self.root,
            )
            return False
        oauth_device = target.get("oauth_device") if isinstance(target.get("oauth_device"), dict) else {}
        oauth_device.update(
            {
                "enabled": True,
                "provider": oauth_config.provider,
                "client_id": client_id.strip(),
                "client_id_env": oauth_config.client_id_env,
                "client_secret_env": oauth_config.client_secret_env,
                "authorization_url": oauth_config.authorization_url,
                "device_code_url": oauth_config.device_code_url,
                "token_url": oauth_config.token_url,
                "verification_url": oauth_config.verification_url,
                "scopes": list(oauth_config.scopes),
                "token_env": oauth_config.token_env,
                "token_store": oauth_config.token_store,
            }
        )
        target["oauth_device"] = oauth_device
        save_integration_config(config)
        return True

    def configure_ai_api_key_session(self, profile_id: str | None = None, parent: Toplevel | Tk | None = None) -> bool:
        profiles = [profile for profile in core.ai_summary_profiles() if profile.kind != "ollama"]
        if not profiles:
            messagebox.showinfo(self.tr("沒有雲端 AI profile", "No cloud AI profile"), self.tr("目前沒有需要 API key 的 AI profile。", "There is no AI profile that needs an API key."), parent=parent or self.root)
            return False
        active = core.active_ai_profile()
        requested = next((profile for profile in profiles if profile.id == profile_id), None) if profile_id else None
        selected = requested or (active if active and active.kind != "ollama" else profiles[0])
        env_name = self.api_key_env_for_profile(selected)
        api_key = simpledialog.askstring(
            self.tr(f"{selected.label} API key", f"{selected.label} API key"),
            self.tr(
                f"貼上本次 launcher session 要使用的 API key。\n會寫入環境變數 {env_name}，只存在目前程式，不會寫進 Git 或設定檔。\n\n現階段這是 Gemini 描述生成的 MVP 路線，不需要 Google 帳號登入。",
                f"Paste an API key for this launcher session.\nIt will be placed in {env_name} only for this process and will not be written to Git or config.\n\nFor now this is the MVP path for Gemini description generation; Google account sign-in is not required.",
            ),
            parent=parent or self.root,
            show="*",
        )
        if not api_key:
            return False
        os.environ[env_name] = api_key.strip()
        try:
            key_path = save_ai_api_key(selected, api_key.strip())
        except Exception as exc:
            messagebox.showerror(self.tr("AI key 保存失敗", "AI key save failed"), str(exc), parent=parent or self.root)
            return False
        try:
            profile = core.set_active_ai_profile(selected.id)
        except Exception as exc:
            messagebox.showerror(self.tr("AI 設定失敗", "AI setup failed"), str(exc), parent=parent or self.root)
            return False
        self.selected_ai_profile_id = profile.id
        self.status_var.set(self.tr(f"AI 已在本次 session 啟用：{profile.label}", f"AI enabled for this session: {profile.label}"))
        messagebox.showinfo(
            self.tr("AI 已啟用", "AI enabled"),
            self.tr(
                f"{profile.label} 現在是 AI 摘要 profile。\nAPI key 已保存到本機 private state：{key_path}\n這個位置不會提交到 Git。",
                f"{profile.label} is now the active AI summary profile.\nThe API key was saved to local private state: {key_path}\nThis location is not committed to Git.",
            ),
            parent=parent or self.root,
        )
        return True

    def render_qr_photo(self, payload: str, size: int = 220) -> object | None:
        try:
            import qrcode
            from PIL import ImageTk
        except Exception:
            return None
        qr = qrcode.QRCode(border=2, box_size=8)
        qr.add_data(payload)
        qr.make(fit=True)
        image = qr.make_image(fill_color="black", back_color="white").convert("RGB")
        image = image.resize((size, size))
        return ImageTk.PhotoImage(image)

    def open_google_qr_login_dialog(self) -> None:
        self.open_ai_profile_login_dialog("gemini_flash")

    def open_google_browser_login_dialog(self) -> None:
        self.open_ai_profile_browser_login_dialog("gemini_flash")

    def open_google_oauth_developer_setup(self) -> None:
        self.configure_oauth_client_for_profile("gemini_flash", parent=self.root, start_login=False)

    def oauth_config_client_id(self, oauth_config: object | None) -> str:
        if oauth_config is None:
            return ""
        client_id = str(getattr(oauth_config, "client_id", "") or "").strip()
        if client_id:
            return client_id
        client_id_env = str(getattr(oauth_config, "client_id_env", "") or "").strip()
        return os.environ.get(client_id_env, "").strip() if client_id_env else ""

    def show_google_oauth_not_ready_dialog(
        self,
        profile: core.AiSummaryProfile,
        parent: Toplevel | None = None,
        reason: str = "missing",
    ) -> None:
        owner = parent or self.root
        dialog = Toplevel(owner)
        dialog.title(self.tr("Google 登入尚未開通", "Google login is not ready"))
        dialog.configure(bg=COLORS["panel"])
        dialog.geometry("760x520")
        dialog.transient(owner)
        dialog.grab_set()
        ttk.Label(dialog, text=self.tr("Google 登入尚未開通", "Google login is not ready"), style="DetailTitle.TLabel").pack(anchor="w", padx=24, pady=(22, 8))

        lead = self.tr(
            "這不是你的帳號問題，也不是你少貼了什麼。",
            "This is not an account problem, and you are not missing a value you were supposed to paste.",
        )
        ttk.Label(dialog, text=lead, style="DetailMuted.TLabel", wraplength=700).pack(anchor="w", fill=X, padx=24, pady=(0, 12))

        detail = Text(dialog, height=13, wrap=WORD, bg=COLORS["bg"], fg=COLORS["text"], relief="flat", padx=16, pady=14, font=("Helvetica", 11))
        detail.pack(fill=BOTH, expand=True, padx=24, pady=(0, 14))
        reason_text = (
            self.tr(
                "目前偵測到一個不像 Google OAuth Client ID 的值，所以 launcher 沒有把它送去 Google，避免重複出現 invalid_client。",
                "The launcher found a value that does not look like a Google OAuth Client ID, so it was not sent to Google again. This avoids repeated invalid_client errors.",
            )
            if reason == "invalid"
            else self.tr(
                "目前這個開發版沒有可用的專案官方 OAuth App 身分，所以還不能啟動 Google 帳號登入。",
                "This development build does not currently have a usable project-owned OAuth app identity, so Google account login cannot start yet.",
            )
        )
        detail.insert(
            "1.0",
            self.tr(
                "\n".join(
                    [
                        reason_text,
                        "",
                        "一般網路服務能讓你直接選 Google 帳號，是因為服務方已經先向 Google 註冊好 OAuth App；使用者通常看不到也不需要管理 Client ID。",
                        "這個專案也應該走同一條路：由專案端提供官方 OAuth 設定，或在未來透過後端代理完成登入。",
                        "",
                        "QR / 裝置碼登入也不是憑空產生的入口；它同樣需要官方 OAuth App 與 device-code 端點。",
                        "",
                        "目前你仍然可以在開發期用 Gemini API key 測試 AI 描述生成管線。這只是暫時讓功能能跑，不是把 API key 當成最終產品登入方案。",
                        "",
                        f"目前 profile：{profile.label}",
                    ]
                ),
                "\n".join(
                    [
                        reason_text,
                        "",
                        "Normal web services can let you choose a Google account because the service has already registered an OAuth app with Google; users usually never see or manage a Client ID.",
                        "This project should follow the same product shape: the project provides official OAuth settings, or a future backend broker completes sign-in.",
                        "",
                        "QR/device-code login is not an entry point that can be invented locally; it also needs an official OAuth app and device-code endpoint.",
                        "",
                        "For now, you can still use a Gemini API key during development to test AI description generation. That is a temporary runnable path, not the final product sign-in design.",
                        "",
                        f"Current profile: {profile.label}",
                    ]
                ),
            ),
        )
        detail.configure(state="disabled")

        actions = ttk.Frame(dialog, style="Panel.TFrame")
        actions.pack(fill=X, padx=24, pady=(0, 20))

        def open_developer_setup() -> None:
            self.configure_oauth_client_for_profile(profile.id, parent=dialog, start_login=False)

        ttk.Button(actions, text=self.tr("保存 Gemini API key", "Save Gemini API key"), style="Action.TButton", command=lambda: self.configure_ai_api_key_session(profile.id, parent=dialog)).pack(side=LEFT, padx=(0, 10))
        ttk.Button(actions, text=self.tr("開發者：設定 OAuth", "Developer: configure OAuth"), style="Action.TButton", command=open_developer_setup).pack(side=LEFT, padx=(0, 10))
        ttk.Button(actions, text=self.tr("顯示本機設定檔", "Reveal local config"), style="Action.TButton", command=self.open_integration_config_file).pack(side=LEFT, padx=(0, 10))
        ttk.Button(actions, text=self.tr("關閉", "Close"), style="Action.TButton", command=dialog.destroy).pack(side=RIGHT)

    def open_ai_profile_browser_login_dialog(self, profile_id: str | None = None, parent: Toplevel | None = None) -> None:
        profile = next((item for item in core.ai_summary_profiles() if item.id == profile_id), None) if profile_id else core.active_ai_profile()
        if profile is None:
            messagebox.showinfo(self.tr("尚未設定 AI profile", "No AI profile"), self.tr("請先到「整合 > AI 輔助模型選擇」選擇一個 AI profile。", "Choose an AI profile under Integrations > AI assistant model selection first."), parent=parent or self.root)
            return
        oauth_config = oauth_device_config_from_profile(profile)
        if oauth_config is None or not oauth_config.authorization_url or not oauth_config.token_url:
            messagebox.showinfo(
                self.tr("尚未支援瀏覽器登入", "Browser login is not configured"),
                self.tr(
                    f"{profile.label} 目前沒有瀏覽器 OAuth 登入端點。若此服務支援 device-code，會改開進階 QR / 裝置碼入口。",
                    f"{profile.label} has no browser OAuth endpoint. If this service supports device-code, the advanced QR/device-code dialog will open instead.",
                ),
                parent=parent or self.root,
            )
            self.open_ai_profile_login_dialog(profile.id, parent=parent)
            return
        client_id = self.oauth_config_client_id(oauth_config)
        if not client_id:
            self.show_google_oauth_not_ready_dialog(profile, parent=parent, reason="missing")
            return
        if oauth_config.provider == "google" and not looks_like_google_oauth_client_id(client_id):
            self.show_google_oauth_not_ready_dialog(profile, parent=parent, reason="invalid")
            return

        owner = parent or self.root
        dialog = Toplevel(owner)
        dialog.title(self.tr(f"{profile.label} Google 帳號登入", f"{profile.label} Google account login"))
        dialog.configure(bg=COLORS["panel"])
        dialog.geometry("760x500")
        dialog.transient(owner)
        dialog.grab_set()
        ttk.Label(dialog, text=self.tr("Google 帳號登入", "Google account login"), style="DetailTitle.TLabel").pack(anchor="w", padx=24, pady=(22, 8))
        ttk.Label(
            dialog,
            text=self.tr(
                "launcher 會打開你的系統瀏覽器。你會在 Google 頁面選帳號；如果 Google 當下提供手機確認或掃 QR，也會在那個頁面完成。",
                "The launcher will open your system browser. You choose the account on Google's page; if Google offers phone confirmation or QR there, it happens on that page.",
            ),
            style="DetailMuted.TLabel",
            wraplength=700,
        ).pack(anchor="w", fill=X, padx=24, pady=(0, 12))
        body = Text(dialog, height=9, wrap=WORD, bg=COLORS["bg"], fg=COLORS["text"], relief="flat", padx=16, pady=14, font=("Helvetica", 11))
        body.pack(fill=X, padx=24, pady=(0, 14))
        body.insert(
            "1.0",
            self.tr(
                "\n".join(
                    [
                        "白話說，這個流程分兩層：",
                        "1. Google 帳號登入：由 Google 網頁處理選帳號、密碼、手機確認或 QR。",
                        "2. App 授權：Google 需要知道是哪個程式要代表你呼叫 API；這個 App 身分應由專案端事先配置好。",
                        "",
                        "登入成功後，access token 會存在 state/private，不會提交到 Git。下次開啟 launcher 會優先嘗試讀取已保存 token。",
                    ]
                ),
                "\n".join(
                    [
                        "Plainly, this flow has two layers:",
                        "1. Google account login: Google's web page handles account choice, password, phone confirmation, or QR.",
                        "2. App authorization: Google must know which app is requesting API access; this app identity should be configured by the project first.",
                        "",
                        "After success, the access token is stored under state/private and is not committed to Git. The launcher will prefer saved tokens next time.",
                    ]
                ),
            ),
        )
        body.configure(state="disabled")
        status_var = StringVar(value=self.tr("準備開啟 Google 登入頁...", "Preparing to open Google's login page..."))
        ttk.Label(dialog, textvariable=status_var, style="DetailMuted.TLabel", wraplength=700).pack(anchor="w", fill=X, padx=24, pady=(0, 14))
        actions = ttk.Frame(dialog, style="Panel.TFrame")
        actions.pack(fill=X, padx=24, pady=(0, 20))
        cancel_event = threading.Event()
        auth_url_holder: dict[str, str] = {"value": ""}
        started: dict[str, bool] = {"value": False}

        def dialog_exists() -> bool:
            try:
                return bool(dialog.winfo_exists())
            except TclError:
                return False

        def set_status(message: str) -> None:
            def handle() -> None:
                if dialog_exists():
                    status_var.set(message)

            self.root.after(0, handle)

        def close_dialog() -> None:
            cancel_event.set()
            dialog.destroy()

        def open_current_auth_url() -> None:
            if auth_url_holder["value"]:
                webbrowser.open(auth_url_holder["value"])
            else:
                status_var.set(self.tr("Google 登入網址尚未產生，請稍候。", "The Google login URL is not ready yet."))

        def start_login() -> None:
            if started["value"]:
                open_current_auth_url()
                return
            started["value"] = True
            start_button.configure(state="disabled")

            def worker() -> None:
                result_box: dict[str, str] = {"code": "", "error": ""}
                state = secrets.token_urlsafe(24)
                code_verifier = secrets.token_urlsafe(48)
                code_challenge = pkce_code_challenge(code_verifier)

                class OAuthCallbackHandler(BaseHTTPRequestHandler):
                    def do_GET(self) -> None:
                        parsed = urllib.parse.urlparse(self.path)
                        params = urllib.parse.parse_qs(parsed.query)
                        returned_state = str((params.get("state") or [""])[0])
                        error_text = str((params.get("error") or [""])[0])
                        code = str((params.get("code") or [""])[0])
                        if parsed.path not in {"/", "/oauth/callback"}:
                            self._respond(404, self.server_message(False, "找不到這個本機登入回呼頁。"))
                            return
                        if returned_state != state:
                            result_box["error"] = "Google 回傳的 state 不符合，登入已停止。"
                            self._respond(400, self.server_message(False, result_box["error"]))
                            return
                        if error_text:
                            result_box["error"] = error_text
                            self._respond(400, self.server_message(False, f"Google 登入未完成：{error_text}"))
                            return
                        if not code:
                            result_box["error"] = "Google 沒有回傳授權碼。"
                            self._respond(400, self.server_message(False, result_box["error"]))
                            return
                        result_box["code"] = code
                        self._respond(200, self.server_message(True, f"登入完成，可以回到 {PRODUCT_DISPLAY_NAME}。"))

                    def _respond(self, status: int, content: str) -> None:
                        encoded = content.encode("utf-8")
                        self.send_response(status)
                        self.send_header("Content-Type", "text/html; charset=utf-8")
                        self.send_header("Content-Length", str(len(encoded)))
                        self.end_headers()
                        self.wfile.write(encoded)

                    def server_message(self, success: bool, message: str) -> str:
                        title = f"{PRODUCT_DISPLAY_NAME} Google 登入"
                        color = "#146c43" if success else "#9b1c1c"
                        return (
                            "<!doctype html><html><head><meta charset='utf-8'>"
                            f"<title>{html.escape(title)}</title>"
                            "<style>body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;"
                            "background:#111827;color:#f9fafb;margin:0;padding:48px;}"
                            "main{max-width:720px;margin:auto;}h1{font-size:28px;}p{font-size:18px;line-height:1.6;}"
                            f".badge{{display:inline-block;background:{color};padding:8px 12px;border-radius:6px;margin-bottom:16px;}}"
                            "</style></head><body><main>"
                            f"<div class='badge'>{'完成' if success else '未完成'}</div>"
                            f"<h1>{html.escape(title)}</h1><p>{html.escape(message)}</p>"
                            "<p>你可以關閉這個瀏覽器分頁，回到 launcher。</p>"
                            "</main></body></html>"
                        )

                    def log_message(self, _format: str, *_args: object) -> None:
                        return

                server = None
                try:
                    server = ThreadingHTTPServer(("127.0.0.1", 0), OAuthCallbackHandler)
                    server.timeout = 1
                    redirect_uri = f"http://127.0.0.1:{server.server_port}/"
                    auth_url = oauth_authorization_url(oauth_config, redirect_uri, state, code_challenge)
                    auth_url_holder["value"] = auth_url
                    set_status(self.tr("已打開 Google 登入頁；請在瀏覽器完成選帳號與授權。", "Google login page opened; finish account choice and consent in the browser."))
                    webbrowser.open(auth_url)
                    deadline = time.time() + 300
                    while time.time() < deadline and not cancel_event.is_set() and not result_box["code"] and not result_box["error"]:
                        server.handle_request()
                    if cancel_event.is_set():
                        set_status(self.tr("登入已取消。", "Login cancelled."))
                        return
                    if result_box["error"]:
                        set_status(self.tr(f"Google 登入未完成：{result_box['error']}", f"Google login was not completed: {result_box['error']}"))
                        return
                    if not result_box["code"]:
                        set_status(self.tr("等候逾時。請重新開啟 Google 登入。", "Timed out. Start Google login again."))
                        return
                    set_status(self.tr("已收到 Google 授權碼，正在換取 token...", "Authorization code received; exchanging it for a token..."))
                    result = exchange_oauth_authorization_code(oauth_config, result_box["code"], redirect_uri, code_verifier)
                    if result.status != "success":
                        set_status(result.message)
                        return
                    path = save_oauth_config_token(result, oauth_config)
                    activate_saved_oauth_token(oauth_config.token_store, oauth_config.token_env, label=profile.label)

                    def handle_success() -> None:
                        if not dialog_exists():
                            return
                        status_var.set(self.tr(f"登入成功，token 已儲存：{path}", f"Login succeeded; token saved: {path}"))
                        self.status_var.set(self.tr(f"{profile.label} Google 帳號登入完成；下次會優先使用已儲存 token。", f"{profile.label} Google account login completed; saved token will be reused next time."))

                    self.root.after(0, handle_success)
                except Exception as exc:
                    set_status(self.tr(f"Google 登入失敗：{exc}", f"Google login failed: {exc}"))
                finally:
                    if server is not None:
                        server.server_close()

            threading.Thread(target=worker, daemon=True).start()

        start_button = ttk.Button(actions, text=self.tr("開啟 Google 登入頁", "Open Google login page"), style="Action.TButton", command=start_login)
        start_button.pack(side=LEFT, padx=(0, 10))
        ttk.Button(actions, text=self.tr("重新開啟瀏覽器頁面", "Reopen browser page"), style="Action.TButton", command=open_current_auth_url).pack(side=LEFT, padx=(0, 10))
        ttk.Button(actions, text=self.tr("進階 QR / 裝置碼", "Advanced QR / device code"), style="Action.TButton", command=lambda: self.open_ai_profile_login_dialog(profile.id, parent=dialog)).pack(side=LEFT, padx=(0, 10))
        ttk.Button(actions, text=self.tr("顯示本機設定檔", "Reveal local config"), style="Action.TButton", command=self.open_integration_config_file).pack(side=LEFT, padx=(0, 10))
        ttk.Button(actions, text=self.tr("關閉", "Close"), style="Action.TButton", command=close_dialog).pack(side=RIGHT)
        dialog.protocol("WM_DELETE_WINDOW", close_dialog)
        dialog.after(250, start_login)

    def open_ai_profile_login_dialog(self, profile_id: str | None = None, parent: Toplevel | None = None) -> None:
        profile = next((item for item in core.ai_summary_profiles() if item.id == profile_id), None) if profile_id else core.active_ai_profile()
        if profile is None:
            messagebox.showinfo(self.tr("尚未設定 AI profile", "No AI profile"), self.tr("請先到「整合 > AI 輔助模型選擇」選擇一個 AI profile。", "Choose an AI profile under Integrations > AI assistant model selection first."), parent=parent or self.root)
            return
        oauth_config = oauth_device_config_from_profile(profile)
        if oauth_config is None:
            messagebox.showinfo(
                self.tr("此 profile 沒有 QR 登入", "No QR login for this profile"),
                self.tr(
                    f"{profile.label} 目前沒有 oauth_device 設定。若服務商支援 QR/device-code，請在本機整合設定檔替這個 profile 加上官方 OAuth 端點。",
                    f"{profile.label} has no oauth_device settings. If the provider supports QR/device-code, add its official OAuth endpoints in the local integration config.",
                ),
                parent=parent or self.root,
            )
            return
        request = build_oauth_device_login_request(oauth_config)
        owner = parent or self.root
        dialog = Toplevel(owner)
        dialog.title(self.tr(f"{profile.label} QR 登入", f"{profile.label} QR login"))
        dialog.configure(bg=COLORS["panel"])
        dialog.geometry("620x680")
        dialog.transient(owner)
        dialog.grab_set()
        ttk.Label(dialog, text=self.tr(f"{profile.label} QR / 裝置登入", f"{profile.label} QR / device login"), style="DetailTitle.TLabel").pack(anchor="w", padx=24, pady=(22, 8))
        status_var = StringVar(value=request.message)
        qr_frame = ttk.Frame(dialog, style="Panel.TFrame")
        qr_frame.pack(fill=X, padx=24, pady=(0, 14))
        qr_payload = request.verification_url_complete or request.verification_url
        qr_photo = self.render_qr_photo(qr_payload) if request.device_code else None
        if qr_photo is not None:
            qr_label = ttk.Label(qr_frame, image=qr_photo, style="DetailText.TLabel")
            qr_label.image = qr_photo
            qr_label.pack(anchor="center", pady=(8, 12))
        fallback = Text(dialog, height=8, wrap=WORD, bg=COLORS["bg"], fg=COLORS["text"], relief="flat", padx=16, pady=14, font=("Consolas", 11))
        fallback.pack(fill=X, padx=24, pady=(0, 14))
        if request.device_code:
            fallback_text = "\n".join(
                [
                    self.tr("這是進階 OAuth/device-code 授權，不是一般 Google 網頁服務的快速登入。", "This is advanced OAuth/device-code authorization, not the regular Google web-service quick login."),
                    self.tr("掃描 QR 或開啟裝置頁面後，輸入下列代碼完成授權。", "Scan the QR code or open the device page, then enter this code to finish authorization."),
                    "",
                    self.tr(f"頁面：{request.verification_url}", f"Page: {request.verification_url}"),
                    self.tr(f"代碼：{request.user_code}", f"Code: {request.user_code}"),
                    self.tr(f"有效時間：{request.expires_in} 秒", f"Expires in: {request.expires_in} seconds"),
                ]
            )
        else:
            fallback_text = "\n".join(
                [
                    self.tr("QR/OAuth 登入尚未設定。", "QR/OAuth login is not configured yet."),
                    "",
                    self.tr(
                        "一般 Google 服務那種選帳號或手機掃碼登入會放在中期 Google OAuth 入口；這個頁面是進階 device-code 流程，適合無鍵盤或跨裝置情境。",
                        "The normal Google account chooser or phone/QR login belongs in the mid-term Google OAuth entry; this page is the advanced device-code flow for limited-input or cross-device situations.",
                    ),
                    "",
                    request.message,
                ]
            )
        fallback.insert("1.0", fallback_text)
        fallback.configure(state="disabled")
        ttk.Label(dialog, textvariable=status_var, style="DetailMuted.TLabel").pack(anchor="w", fill=X, padx=24, pady=(0, 14))
        actions = ttk.Frame(dialog, style="Panel.TFrame")
        actions.pack(fill=X, padx=24, pady=(0, 20))
        poll_after_id: dict[str, str | None] = {"value": None}
        poll_interval_ms: dict[str, int] = {"value": max(request.interval, 1) * 1000}

        def cancel_polling() -> None:
            if poll_after_id["value"]:
                dialog.after_cancel(poll_after_id["value"])
                poll_after_id["value"] = None

        def close_dialog() -> None:
            cancel_polling()
            dialog.destroy()

        def schedule_poll(delay_ms: int | None = None) -> None:
            if not dialog.winfo_exists() or not request.device_code:
                return
            poll_after_id["value"] = dialog.after(delay_ms or poll_interval_ms["value"], poll_once)

        def poll_once() -> None:
            cancel_polling()
            status_var.set(self.tr("正在等待 AI 服務授權完成...", "Waiting for AI service authorization..."))

            def worker() -> None:
                result = poll_oauth_device_token(request)

                def handle() -> None:
                    if not dialog.winfo_exists():
                        return
                    if result.status == "success":
                        path = save_oauth_device_token(result, request)
                        activate_saved_oauth_token(request.token_store, request.token_env, label=profile.label)
                        status_var.set(self.tr(f"登入成功，token 已儲存：{path}", f"Login succeeded; token saved: {path}"))
                        self.status_var.set(self.tr(f"{profile.label} 登入完成；下次會優先使用已儲存 token。", f"{profile.label} login completed; saved token will be reused next time."))
                        return
                    if result.status in {"authorization_pending", "slow_down"}:
                        if result.slow_down:
                            poll_interval_ms["value"] += 5000
                        status_var.set(self.tr("尚未完成授權，請在手機或瀏覽器完成登入。", "Authorization is still pending; finish login on your phone or browser."))
                        schedule_poll()
                        return
                    status_var.set(result.message)
                    self.status_var.set(self.tr(f"{profile.label} 登入未完成：{result.status}", f"{profile.label} login not completed: {result.status}"))

                self.root.after(0, handle)

            threading.Thread(target=worker, daemon=True).start()

        if request.device_code:
            schedule_poll(500)
        dialog.protocol("WM_DELETE_WINDOW", close_dialog)

        if qr_payload:
            ttk.Button(actions, text=self.tr("開啟裝置頁面", "Open device page"), style="Action.TButton", command=lambda: webbrowser.open(qr_payload)).pack(side=LEFT, padx=(0, 10))
        if request.status in {"missing_client_id", "missing_client_id_env"}:
            def configure_and_restart() -> None:
                if self.configure_oauth_client_for_profile(profile.id, parent=dialog, start_login=False):
                    close_dialog()
                    self.open_ai_profile_login_dialog(profile.id, parent=owner)

            ttk.Button(actions, text=self.tr("開發者：設定 OAuth", "Developer: configure OAuth"), style="Action.TButton", command=configure_and_restart).pack(side=LEFT, padx=(0, 10))
        ttk.Button(actions, text=self.tr("用瀏覽器登入", "Browser login"), style="Action.TButton", command=lambda: self.open_ai_profile_browser_login_dialog(profile.id, parent=dialog)).pack(side=LEFT, padx=(0, 10))
        ttk.Button(actions, text=self.tr("保存 API key", "Save API key"), style="Action.TButton", command=lambda: self.configure_ai_api_key_session(profile.id, parent=dialog)).pack(side=LEFT, padx=(0, 10))
        ttk.Button(actions, text=self.tr("顯示本機設定檔", "Reveal local config"), style="Action.TButton", command=self.open_integration_config_file).pack(side=LEFT, padx=(0, 10))
        if request.device_code:
            ttk.Button(actions, text=self.tr("重新檢查登入", "Check login"), style="Action.TButton", command=poll_once).pack(side=LEFT, padx=(0, 10))
        ttk.Button(actions, text=self.tr("關閉", "Close"), style="Action.TButton", command=close_dialog).pack(side=RIGHT)
