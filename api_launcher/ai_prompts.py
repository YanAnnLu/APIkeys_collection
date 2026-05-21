from __future__ import annotations

from dataclasses import dataclass

from api_launcher.models import Provider


@dataclass(frozen=True)
class PromptTemplate:
    # prompt template 集中管理，避免 UI/CLI 各自拼不同的 AI 描述提示詞。
    prompt_id: str
    purpose: str
    system_intent: str
    output_contract: tuple[str, ...]


DATASET_DESCRIPTION_PROMPT = PromptTemplate(
    prompt_id="dataset_launcher_description_v1",
    purpose="Generate a concise launcher-facing description for a data source or dataset.",
    system_intent=(
        "You are helping a Steam-like scientific dataset launcher explain data sources to users. "
        "Focus on what the source contains, why it matters, how it may be used, and any access caveats."
    ),
    output_contract=(
        "Write Traditional Chinese unless the source name must remain English.",
        "Use 3 to 5 short bullet points.",
        "Mention likely data type/domain.",
        "Mention possible big-data or virtual-twin use cases.",
        "Mention authentication/access caveats when provided.",
        "Do not invent API keys, credentials, exact pricing, or unsupported claims.",
    ),
)


def provider_description_prompt(provider: Provider) -> str:
    # prompt 只包含公開 metadata 與 env var 名稱，不把實際 API key/token 放進 AI 請求。
    categories = ", ".join(provider.categories) if provider.categories else "unknown"
    secret_fields = ", ".join(provider.secret_env_vars) if provider.secret_env_vars else "none"
    return "\n".join(
        [
            DATASET_DESCRIPTION_PROMPT.system_intent,
            "",
            "Task:",
            "Generate a launcher-facing description for this source. The user is deciding whether to add it to a download/install plan.",
            "",
            "Output contract:",
            *[f"- {rule}" for rule in DATASET_DESCRIPTION_PROMPT.output_contract],
            "",
            "Source metadata:",
            f"- name: {provider.name}",
            f"- owner: {provider.owner}",
            f"- categories: {categories}",
            f"- geographic_scope: {provider.geographic_scope}",
            f"- auth_type: {provider.auth_type}",
            f"- key_env_var: {provider.key_env_var or 'none'}",
            f"- secret_env_vars: {secret_fields}",
            f"- docs_url: {provider.docs_url or 'none'}",
            f"- api_base_url: {provider.api_base_url or 'none'}",
            f"- signup_url: {provider.signup_url or 'none'}",
            f"- license_url: {provider.license_url or 'none'}",
            f"- terms_url: {provider.terms_url or 'none'}",
            f"- existing_notes: {provider.notes or 'none'}",
        ]
    )
