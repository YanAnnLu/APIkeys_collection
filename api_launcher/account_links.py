from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AccountProvider:
    provider_id: str
    label: str
    auth_mode: str
    status: str
    capability_targets: tuple[str, ...]
    notes: str = ""


@dataclass(frozen=True)
class AccountCapabilityRoute:
    capability: str
    preferred_provider: str
    fallback_providers: tuple[str, ...]
    target_profile: str
    notes: str = ""


DEFAULT_ACCOUNT_PROVIDERS = (
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
    AccountCapabilityRoute(
        capability="ai_dataset_summary",
        preferred_provider="google",
        fallback_providers=("local_ollama",),
        target_profile="gemini_flash",
        notes="Dataset descriptions can use Gemini through Google login/API key, or local Ollama as fallback.",
    ),
)


def account_provider(provider_id: str) -> AccountProvider | None:
    wanted = provider_id.strip().lower()
    return next((provider for provider in DEFAULT_ACCOUNT_PROVIDERS if provider.provider_id == wanted), None)


def capability_route(capability: str) -> AccountCapabilityRoute | None:
    wanted = capability.strip().lower()
    return next((route for route in DEFAULT_CAPABILITY_ROUTES if route.capability == wanted), None)
