from __future__ import annotations

from pathlib import Path
from typing import Any

from api_launcher.handoff import build_handoff_snapshot, handoff_snapshot_to_dict
from api_launcher.repository import ApiCatalogRepository


MVP_CLOSURE_ID = "canonical_mvp_demo_closure"
MVP_CLOSURE_SCOPE = (
    "Canonical offline Socrata 311 fixture covering seed -> candidate -> plan -> "
    "download -> manifest -> SQLite import -> JSON handoff."
)
MVP_CLOSURE_STEPS = (
    "seed",
    "candidate",
    "plan",
    "download",
    "manifest",
    "import",
    "ui_json_handoff",
)


def build_mvp_readiness_payload(repository: ApiCatalogRepository, db_path: Path | str | None = None) -> dict[str, Any]:
    """Return a bounded, machine-readable readiness report for the canonical MVP loop."""
    snapshot = handoff_snapshot_to_dict(build_handoff_snapshot(repository))
    return mvp_readiness_payload_from_snapshot(snapshot, db_path=db_path)


def mvp_readiness_payload_from_snapshot(
    snapshot: dict[str, Any],
    db_path: Path | str | None = None,
) -> dict[str, Any]:
    """Convert the broader handoff snapshot into a scoped MVP closure artifact.

    This deliberately reports only the canonical demo closure. It must not be reused as
    an all-product maturity percentage.
    """
    readiness = _dict(snapshot.get("mvp_readiness"))
    verification = _dict(snapshot.get("verification_summary"))
    manifest_health = _dict(snapshot.get("manifest_health"))
    canonical_smoke = _dict(readiness.get("canonical_smoke"))
    blockers = _list(readiness.get("blockers"))
    warnings = _list(readiness.get("warnings"))
    ready = readiness.get("status") == "ready_for_mvp_demo" and not blockers
    db_arg = f"--db {db_path} " if db_path else ""

    return {
        "closure_id": MVP_CLOSURE_ID,
        "scope": MVP_CLOSURE_SCOPE,
        "not_product_scope": (
            "This is not the maturity percentage for every crawler, adapter, renderer, "
            "or future Qt/Web surface."
        ),
        "status": readiness.get("status", "needs_mvp_smoke"),
        "status_zh_TW": readiness.get("status_zh_TW", "MVP Demo 閉環仍需重跑或修復"),
        "closure_percent": 100 if ready else 0,
        "remaining_percent_estimate": readiness.get("remaining_percent_estimate", "unknown"),
        "verified_steps": [
            {
                "step": step,
                "status": "pass" if ready else "blocked",
                "evidence": _step_evidence(step, canonical_smoke, verification),
            }
            for step in MVP_CLOSURE_STEPS
        ],
        "canonical_smoke": canonical_smoke,
        "manifest_health": manifest_health,
        "blockers": blockers,
        "warnings": warnings,
        "verified_behavior_source": [
            "latest_mvp_demo_smoke_event",
            "manifest_health_summary",
            "handoff_snapshot",
        ],
        "rerun_commands": {
            "smoke_json": (
                f"py -3 -B APIkeys_collection.py {db_arg}"
                "--init-db --seed --run-mvp-demo-smoke-json state/mvp_demo/flow.json"
            ),
            "readiness_json": f"py -3 -B APIkeys_collection.py {db_arg}--mvp-readiness-json",
            "handoff_json": f"py -3 -B APIkeys_collection.py {db_arg}--handoff-report-json",
        },
    }


def _step_evidence(step: str, smoke: dict[str, Any], verification: dict[str, Any]) -> str:
    if step == "seed":
        return "Canonical smoke initializes and seeds the launcher registry before execution."
    if step == "candidate":
        return "Canonical Socrata 311 fixture is resolved through the adapter review flow."
    if step == "plan":
        return "Canonical review entry resolves into one bounded direct offline plan entry."
    if step == "download":
        return f"latest stage={smoke.get('stage', '')}; succeeded={smoke.get('succeeded', False)}"
    if step == "manifest":
        return "Offline plan writes and verifies sidecar manifest metadata during the smoke run."
    if step == "import":
        return (
            f"table={smoke.get('table_name', '')}; row_count={smoke.get('row_count', 0)}"
        )
    if step == "ui_json_handoff":
        return (
            "readiness_json and handoff_json expose machine-readable acceptance state; "
            f"event_at={verification.get('latest_mvp_demo_smoke_event_at', '')}"
        )
    return ""


def _dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: object) -> list[Any]:
    return value if isinstance(value, list) else []
