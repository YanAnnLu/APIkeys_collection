from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AccountProvider:
    # 這是帳號/身份入口的產品契約，不代表 OAuth 流程都已經實作完成。
    provider_id: str
    label: str
    auth_mode: str
    status: str
    capability_targets: tuple[str, ...]
    notes: str = ""


@dataclass(frozen=True)
class AccountCapabilityRoute:
    # capability route 用來說明某個功能偏好哪個身份/模型來源，避免 UI 硬寫判斷。
    capability: str
    preferred_provider: str
    fallback_providers: tuple[str, ...]
    target_profile: str
    notes: str = ""


DEFAULT_ACCOUNT_PROVIDERS = (
    # 目前只有 Google/Gemini 路徑接近 MVP；其他 provider 先保留為明確 roadmap 入口。
    AccountProvider(
        provider_id="google",
        label="Google",
        auth_mode="oauth_device_qr",
        status="skeleton",
        capability_targets=("gemini_summary", "google_drive_future", "google_cloud_future"),
        notes="Primary path for Gemini and future Google service integrations.",
    ),
    AccountProvider(
        provider_id="apple",
        label="Apple",
        auth_mode="sign_in_with_apple",
        status="reserved",
        capability_targets=("identity_only_future",),
        notes="Reserved for Apple identity linking. It does not directly provide Gemini access.",
    ),
    AccountProvider(
        provider_id="microsoft",
        label="Microsoft",
        auth_mode="oauth_device_qr",
        status="reserved",
        capability_targets=("identity_only_future", "azure_openai_future", "onedrive_future"),
        notes="Reserved for Microsoft/Azure integrations.",
    ),
    AccountProvider(
        provider_id="github",
        label="GitHub",
        auth_mode="oauth_device",
        status="reserved",
        capability_targets=("agent_handoff_future", "repo_sync_future"),
        notes="Reserved for development and agent handoff workflows.",
    ),
)


DEFAULT_CAPABILITY_ROUTES = (
    # 功能路由先保持小而明確；未來新增 Drive/Azure 等能力時再擴充這裡。
    AccountCapabilityRoute(
        capability="ai_dataset_summary",
        preferred_provider="google",
        fallback_providers=("local_ollama",),
        target_profile="gemini_flash",
        notes="Dataset descriptions can use Gemini through Google login/API key, or local Ollama as fallback.",
    ),
)


def account_provider(provider_id: str) -> AccountProvider | None:
    # 查詢時統一 lower，避免 UI 或設定檔大小寫差異造成找不到 provider。
    wanted = provider_id.strip().lower()
    return next((provider for provider in DEFAULT_ACCOUNT_PROVIDERS if provider.provider_id == wanted), None)


def capability_route(capability: str) -> AccountCapabilityRoute | None:
    # 回傳 None 代表該 capability 還沒有產品級路由，不應由 UI 自行猜測。
    wanted = capability.strip().lower()
    return next((route for route in DEFAULT_CAPABILITY_ROUTES if route.capability == wanted), None)
