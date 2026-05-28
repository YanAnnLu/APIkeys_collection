from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from api_launcher.crawlers.dataset_sources import SUPPORTED_DATASET_SOURCE_TYPES
from api_launcher.dataset_adapters import DATASET_ADAPTERS
from api_launcher.mvp_readiness import build_mvp_readiness_payload
from api_launcher.repository import ApiCatalogRepository
from api_launcher.simulation_bridge import DEFAULT_SIMULATION_BACKENDS


MATRIX_VERSION = "2026-05-28"


@dataclass(frozen=True)
class MaturityMatrixRow:
    area_id: str
    area_label: str
    maturity_level: str
    maturity_label_zh_TW: str
    deliverable_scope: str
    verified_behavior_source: tuple[str, ...]
    current_limitations: tuple[str, ...] = ()
    next_actions: tuple[str, ...] = ()
    metrics: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        display = maturity_display_profile(self.maturity_level)
        return {
            "area_id": self.area_id,
            "area_label": self.area_label,
            "maturity_level": self.maturity_level,
            "maturity_label_zh_TW": self.maturity_label_zh_TW,
            "status_icon": display["status_icon"],
            "display_tone": display["display_tone"],
            "display_label": display["display_label"],
            "display_profile": display,
            "deliverable_scope": self.deliverable_scope,
            "verified_behavior_source": list(self.verified_behavior_source),
            "current_limitations": list(self.current_limitations),
            "next_actions": list(self.next_actions),
            "metrics": self.metrics,
        }


def maturity_display_profile(maturity_level: str) -> dict[str, str]:
    """Return UI-neutral labels for maturity rows.

    Keep the icon/tone decision here so Tk, Web, and future Qt do not each
    re-interpret contract-only or planned work differently.
    """
    level = maturity_level.strip().lower()
    profiles = {
        "deliverable_100": {
            "status_icon": "✓",
            "display_tone": "success",
            "display_label": "可交付",
        },
        "implemented_bounded": {
            "status_icon": "✓",
            "display_tone": "success",
            "display_label": "已接通",
        },
        "partial_bounded": {
            "status_icon": "◐",
            "display_tone": "warning",
            "display_label": "部分接通",
        },
        "contract_only": {
            "status_icon": "🚧",
            "display_tone": "review",
            "display_label": "施工中 / 合約",
        },
        "planned_not_started": {
            "status_icon": "🚧",
            "display_tone": "neutral",
            "display_label": "規劃中",
        },
        "hardening_needed": {
            "status_icon": "!",
            "display_tone": "warning",
            "display_label": "需加固",
        },
    }
    return profiles.get(
        level,
        {
            "status_icon": "?",
            "display_tone": "neutral",
            "display_label": "未分類",
        },
    )


def build_project_maturity_payload(
    repository: ApiCatalogRepository,
    db_path: Path | str | None = None,
) -> dict[str, Any]:
    """Return the project maturity matrix used for progress reporting.

    This payload is deliberately not a single percentage. RRKAL mixes finished
    bounded loops, partially integrated live-source paths, and future contracts.
    A single number would hide which parts can actually be delivered.
    """
    mvp_readiness = build_mvp_readiness_payload(repository, db_path=db_path)
    rows = _matrix_rows(mvp_readiness)
    return {
        "matrix_version": MATRIX_VERSION,
        "reporting_rule": (
            "Do not report RRKAL progress as one percentage. Use this matrix and "
            "name the delivery scope being discussed."
        ),
        "why_no_single_percent": (
            "A single percentage would mix verified MVP closure, bounded source "
            "crawler contracts, partial importer/deep-adapter work, and renderer "
            "contracts. Those are different maturity levels."
        ),
        "canonical_delivery_scope": {
            "closure_id": mvp_readiness.get("closure_id"),
            "closure_percent": mvp_readiness.get("closure_percent"),
            "status": mvp_readiness.get("status"),
            "scope": mvp_readiness.get("scope"),
            "not_product_scope": mvp_readiness.get("not_product_scope"),
        },
        "maturity_levels": {
            "deliverable_100": "Bounded scope is implemented, tested, and can be shown as complete.",
            "implemented_bounded": "Implemented for a bounded path; use only within its stated limits.",
            "partial_bounded": "A real path exists, but not every provider/format/source is covered.",
            "contract_only": "Contracts or planned targets exist; real execution is not implemented.",
            "planned_not_started": "Roadmap or future UI/runtime surface; do not present as delivered.",
            "hardening_needed": "Usable path exists, but operational robustness still needs a design slice.",
        },
        "rows": [row.to_dict() for row in rows],
        "answer_template_zh_TW": (
            "目前不能用單一百分比回答。可交付小閉環是 100%；整體產品請看成熟度矩陣："
            "哪些是已驗證交付、哪些是 bounded、哪些是 partial、哪些仍是 contract-only。"
        ),
    }


def render_project_maturity_markdown(payload: dict[str, Any]) -> str:
    rows = payload.get("rows") if isinstance(payload.get("rows"), list) else []
    lines = [
        "# RRKAL Project Maturity Matrix",
        "",
        f"- matrix_version: {payload.get('matrix_version', '')}",
        f"- reporting_rule: {payload.get('reporting_rule', '')}",
        f"- why_no_single_percent: {payload.get('why_no_single_percent', '')}",
        "",
        "## Canonical Delivery Scope",
        "",
    ]
    closure = payload.get("canonical_delivery_scope") if isinstance(payload.get("canonical_delivery_scope"), dict) else {}
    lines.extend(
        [
            f"- closure_id: {closure.get('closure_id', '')}",
            f"- closure_percent: {closure.get('closure_percent', '')}",
            f"- status: {closure.get('status', '')}",
            f"- scope: {closure.get('scope', '')}",
            f"- not_product_scope: {closure.get('not_product_scope', '')}",
            "",
            "## Matrix",
            "",
            "| Area | Maturity | Deliverable Scope | Limits | Next Actions |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for row in rows:
        if not isinstance(row, dict):
            continue
        limits = "; ".join(str(item) for item in row.get("current_limitations", []) if item)
        actions = "; ".join(str(item) for item in row.get("next_actions", []) if item)
        display = maturity_display_profile(str(row.get("maturity_level") or ""))
        status_icon = str(row.get("status_icon") or display["status_icon"])
        maturity_label = f"{status_icon} {row.get('maturity_label_zh_TW', row.get('maturity_level', ''))}".strip()
        lines.append(
            "| "
            f"{_cell(row.get('area_label', ''))} | "
            f"{_cell(maturity_label)} | "
            f"{_cell(row.get('deliverable_scope', ''))} | "
            f"{_cell(limits)} | "
            f"{_cell(actions)} |"
        )
    lines.append("")
    return "\n".join(lines)


def write_project_maturity_payload(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _matrix_rows(mvp_readiness: dict[str, Any]) -> tuple[MaturityMatrixRow, ...]:
    return (
        MaturityMatrixRow(
            area_id="canonical_mvp_demo_closure",
            area_label="Canonical MVP demo closure",
            maturity_level="deliverable_100" if mvp_readiness.get("closure_percent") == 100 else "hardening_needed",
            maturity_label_zh_TW="可交付小閉環 100%" if mvp_readiness.get("closure_percent") == 100 else "小閉環需重跑或修復",
            deliverable_scope="Offline Socrata 311 fixture completes seed -> candidate -> plan -> download -> manifest -> SQLite import -> JSON handoff.",
            verified_behavior_source=("mvp_readiness_json", "mvp_demo_smoke", "pre_push_smoke", "github_actions"),
            metrics={"closure_percent": mvp_readiness.get("closure_percent", 0)},
        ),
        MaturityMatrixRow(
            area_id="source_pattern_and_crawler_handlers",
            area_label="Source pattern detection and crawler handlers",
            maturity_level="implemented_bounded",
            maturity_label_zh_TW="已實作 bounded source handler contract",
            deliverable_scope="Supported source types can be detected, drafted, crawled in bounded mode, and audited with warning/next_action payloads.",
            verified_behavior_source=("tests.test_dataset_discovery", "tests.test_source_patterns", "handler_smoke_contract"),
            current_limitations=("This is source discovery capability, not proof that every live provider has deep adapter/import/render support.",),
            next_actions=("Keep adding detectors/adapters by source interface type, not by institution special-case branches.",),
            metrics={"supported_source_type_count": len(SUPPORTED_DATASET_SOURCE_TYPES)},
        ),
        MaturityMatrixRow(
            area_id="crawler_asset_download_import",
            area_label="Crawler asset download/import path",
            maturity_level="partial_bounded",
            maturity_label_zh_TW="正式路徑已接通，但 provider 覆蓋仍是 partial",
            deliverable_scope="Web/Tk/CLI can build bounded plans and run formal crawler asset or seed-level download/import paths where provider/content capability permits.",
            verified_behavior_source=("tests.test_crawler_asset_download", "tests.test_web_preview", "mvp_demo_smoke"),
            current_limitations=("Many live sources still require credentials, adapter review, or content parser work before they are one-click importable.",),
            next_actions=("Prioritize provider-by-provider live closure only after profile, credential, bounds, and parser lanes are explicit.",),
        ),
        MaturityMatrixRow(
            area_id="content_parser_and_import",
            area_label="Content parser/import capability",
            maturity_level="partial_bounded",
            maturity_label_zh_TW="CSV/JSON/GeoJSON 可匯入；重型科學格式仍需 review",
            deliverable_scope="CSV, JSON, JSONL, GeoJSON, and selected archive-derived tabular payloads can enter manifest/import pipelines.",
            verified_behavior_source=("tests.test_ingestion_pipeline", "tests.test_csv_importer", "adapter_review_payload"),
            current_limitations=("NetCDF, HDF, GeoTIFF, Zarr, Parquet, and unknown payloads are not universally parsed into curated tables.",),
            next_actions=("Keep unsupported scientific/geospatial formats in manifest/adapter review until parser registry support is explicit.",),
        ),
        MaturityMatrixRow(
            area_id="provider_specific_deep_adapters",
            area_label="Provider-specific deep adapters",
            maturity_level="partial_bounded",
            maturity_label_zh_TW="少數 deep adapter 已落地",
            deliverable_scope="GEBCO, HYG, and yfinance have explicit dataset adapters in the current registry.",
            verified_behavior_source=("api_launcher.dataset_adapters.DATASET_ADAPTERS", "tests.test_adapter_plan_resolver"),
            current_limitations=("Supported source crawler types are broader than deep provider adapter coverage.",),
            next_actions=("Do not claim all supported source types have deep adapters; add adapters only where they close a real import/download path.",),
            metrics={"dataset_adapter_count": len(DATASET_ADAPTERS)},
        ),
        MaturityMatrixRow(
            area_id="tk_and_web_user_surfaces",
            area_label="Tk and Web user surfaces",
            maturity_level="implemented_bounded",
            maturity_label_zh_TW="Tk/Web 可操作但仍需 UX hardening",
            deliverable_scope="Tk is the stable desktop control panel; Web Preview is the UIUX/future Qt-QSS lead surface consuming backend contracts.",
            verified_behavior_source=("tests.test_tk_dialogs", "tests.test_launcher_ui", "tests.test_web_preview"),
            current_limitations=("Not every backend feature has a polished no-guess UI flow; complex live-source setup still needs more presets/dropdowns.",),
            next_actions=("Continue making UI consume backend display/form profiles instead of duplicating business rules.",),
        ),
        MaturityMatrixRow(
            area_id="credentials_and_local_security",
            area_label="Credential setup and local secret handling",
            maturity_level="implemented_bounded",
            maturity_label_zh_TW="本機登入設定已 bounded 實作",
            deliverable_scope="Credential status, local .env update, Tk/Web setup prompts, and remember-account language are available without exposing saved secrets in UI payloads.",
            verified_behavior_source=("tests.test_local_credentials", "tests.test_tk_dialogs", "tests.test_web_preview"),
            current_limitations=("Browser-based provider login/key acquisition is assisted by links, not fully automated account onboarding.",),
            next_actions=("Keep provider credential profiles explicit and avoid logging plaintext secrets.",),
        ),
        MaturityMatrixRow(
            area_id="renderer_unreal_simulation",
            area_label="Renderer, Unreal, and simulation bridge",
            maturity_level="contract_only",
            maturity_label_zh_TW="合約 / planned，不可當已交付執行功能",
            deliverable_scope="Renderer/simulation contracts describe future asset roles, targets, and bridge destinations.",
            verified_behavior_source=("api_launcher.unreal_bridge", "api_launcher.simulation_bridge", "tests.test_simulation_bridge"),
            current_limitations=("Unreal bridge plans target paths but does not copy/import assets; simulation backends are contract_only.",),
            next_actions=("Only present these as roadmap/contracts until real I/O or simulation execution is implemented and tested.",),
            metrics={"simulation_backend_contract_count": len(DEFAULT_SIMULATION_BACKENDS)},
        ),
        MaturityMatrixRow(
            area_id="qt_modern_ui",
            area_label="Qt modern UI",
            maturity_level="planned_not_started",
            maturity_label_zh_TW="尚未開始正式 Qt 實作",
            deliverable_scope="Qt is a future skin over the same backend contracts.",
            verified_behavior_source=("project_docs", "absence_of_qt_runtime_dependency"),
            current_limitations=("Current production UI surfaces are Tk and Web Preview, not Qt.",),
            next_actions=("Use Web Preview CSS/UX as design lead, then port stable contracts into Qt/QSS later.",),
        ),
        MaturityMatrixRow(
            area_id="background_jobs_and_scheduler",
            area_label="Background jobs and scheduler",
            maturity_level="hardening_needed",
            maturity_label_zh_TW="可用但需要 bounded scheduler hardening",
            deliverable_scope="Existing Tk/Web paths use background threads and queues to avoid immediate UI blocking.",
            verified_behavior_source=("tests.test_download_jobs", "tk_workflow_tests", "web_preview_tests"),
            current_limitations=("Threading is still ad hoc in multiple UI workflows; no unified bounded job scheduler/DB write gate yet.",),
            next_actions=("Design a bounded job scheduler before considering broad asyncio rewrites.",),
        ),
        MaturityMatrixRow(
            area_id="docs_and_governance",
            area_label="Docs, handoff, and governance",
            maturity_level="implemented_bounded",
            maturity_label_zh_TW="文檔治理已 bounded 實作",
            deliverable_scope="AGENT_START_HERE, handoff, GTD, docs drift guard, development log, pre-push smoke, and CI watch are part of the workflow.",
            verified_behavior_source=("docs_drift_audit", "pre_push_smoke", "github_actions"),
            current_limitations=("Docs can still drift if checkpoints skip GTD/handoff/log updates.",),
            next_actions=("Use this matrix for progress answers and update docs at each checkpoint.",),
        ),
    )


def _cell(value: object) -> str:
    text = str(value).replace("\n", " ").replace("|", "\\|")
    return text
