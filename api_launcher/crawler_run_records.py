from __future__ import annotations

import json
from hashlib import sha256
from typing import Mapping


def crawler_run_record(
    *,
    stage: str,
    asset_id: str,
    status: str,
    next_action: str = "",
    outcome_bucket: str = "",
    candidate_count: int = 0,
    direct_download_count: int = 0,
    review_required_count: int = 0,
    error_count: int = 0,
    warning_count: int = 0,
    duplicate_count: int = 0,
    source_signature: str = "",
    bounds_signature: str = "",
    candidate_snapshot_signature: str = "",
    candidate_snapshot_count: int = 0,
) -> dict[str, object]:
    """Build the compact crawler-run handoff payload shared by UI and agents.

    這不是永久 DB schema；目前先作為 structured event / JSON handoff
    的共用骨架。等 run registry 表定案後，這裡的欄位可以直接映射
    到 SQLite registry。
    """

    payload: dict[str, object] = {
        "record_key": "",
        "stage": stage,
        "asset_id": asset_id,
        "status": status,
        "outcome_bucket": outcome_bucket,
        "candidate_count": int(candidate_count),
        "direct_download_count": int(direct_download_count),
        "review_required_count": int(review_required_count),
        "error_count": int(error_count),
        "warning_count": int(warning_count),
        "duplicate_count": int(duplicate_count),
        "source_signature": source_signature,
        "bounds_signature": bounds_signature,
        "candidate_snapshot_signature": candidate_snapshot_signature,
        "candidate_snapshot_count": int(candidate_snapshot_count),
        "next_action": next_action,
        "storage_lane": "structured_event_log",
        "future_sqlite_table": "crawler_run_registry",
    }
    payload["record_key"] = crawler_run_record_key(payload)
    return payload


def crawler_run_record_key(payload: Mapping[str, object]) -> str:
    stable_payload = {key: value for key, value in payload.items() if key != "record_key"}
    raw = json.dumps(stable_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256(raw.encode("utf-8")).hexdigest()[:16]


def crawler_run_record_from_result(result: object) -> dict[str, object]:
    """Extract the compact run record from a result object when available.

    Tk/Web/Qt should not know how every crawler result calculates status.  They
    can call this helper and keep the event context bounded; objects without a
    ``to_dict().run_record`` contract simply return an empty payload.
    """

    to_dict = getattr(result, "to_dict", None)
    if not callable(to_dict):
        return {}
    try:
        payload = to_dict()
    except Exception:
        # 事件紀錄不能因單一 result 的序列化錯誤而拖垮 Tk/Web 回報路徑。
        return {}
    if not isinstance(payload, dict):
        return {}
    run_record = payload.get("run_record")
    return dict(run_record) if isinstance(run_record, dict) else {}


__all__ = [
    "crawler_run_record",
    "crawler_run_record_from_result",
    "crawler_run_record_key",
]
