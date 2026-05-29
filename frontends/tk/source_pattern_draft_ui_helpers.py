"""Tk display helpers for source pattern draft outcomes.

The source pattern draft workflow produces a backend summary dict.  Tk should
only translate that summary into a readable message; it must not decide whether
the source is promoted, audited, downloaded, or imported.
"""

from __future__ import annotations

from typing import Callable, Mapping

Translator = Callable[[str, str], str]


def source_pattern_draft_message(summary: object, translate: Translator) -> str:
    """Return the success message for a local source draft creation result."""

    data = summary if isinstance(summary, dict) else {}
    detection = _mapping_value(data, "source_pattern_detection")
    sources = data.get("sources") if isinstance(data.get("sources"), list) else []
    source = sources[0] if sources and isinstance(sources[0], dict) else {}
    evidence_preview = _evidence_preview(detection)
    confidence_text = _confidence_text(detection.get("confidence"))
    next_action_zh = _text(
        data.get("next_action_label_zh_TW")
        or data.get("next_action_label")
        or data.get("next_action")
        or "-"
    )
    next_action_en = _text(data.get("next_action_label_en") or data.get("next_action") or "-")
    audit_command = _text(data.get("audit_command") or "")
    return translate(
        (
            "已建立本機資料源草稿。\n\n"
            "這不是正式 catalog promotion，也不會下載或匯入資料；下一步必須執行本機 discovery audit。\n\n"
            f"Pattern：{detection.get('pattern_id') or '-'}\n"
            f"信心：{confidence_text}\n"
            f"Source type：{detection.get('source_type_hint') or source.get('source_type') or '-'}\n"
            f"Source ID：{source.get('source_id') or '-'}\n"
            f"Endpoint：{source.get('endpoint_url') or '-'}\n\n"
            f"證據：\n{evidence_preview}\n\n"
            f"Local draft：{data.get('dataset_source_path') or '-'}\n"
            f"下一步：{next_action_zh or '-'}"
            + (f"\n可重跑命令：{audit_command}" if audit_command else "")
        ),
        (
            "Local dataset source draft created.\n\n"
            "This is not catalog promotion and does not download or import data; run local discovery audit next.\n\n"
            f"Pattern: {detection.get('pattern_id') or '-'}\n"
            f"Confidence: {confidence_text}\n"
            f"Source type: {detection.get('source_type_hint') or source.get('source_type') or '-'}\n"
            f"Source ID: {source.get('source_id') or '-'}\n"
            f"Endpoint: {source.get('endpoint_url') or '-'}\n\n"
            f"Evidence:\n{evidence_preview}\n\n"
            f"Local draft: {data.get('dataset_source_path') or '-'}\n"
            f"Next: {next_action_en or '-'}"
            + (f"\nCommand: {audit_command}" if audit_command else "")
        ),
    )


def source_pattern_draft_review_message(summary: object, translate: Translator) -> str:
    """Return the review-needed message for a source draft result."""

    data = summary if isinstance(summary, dict) else {}
    detection = _mapping_value(data, "source_pattern_detection")
    evidence_preview = _evidence_preview(detection)
    confidence_text = _confidence_text(detection.get("confidence"))
    next_action_zh = _text(
        data.get("next_action_label_zh_TW")
        or data.get("next_action_label")
        or data.get("next_action")
        or "-"
    )
    next_action_en = _text(data.get("next_action_label_en") or data.get("next_action") or "-")
    return translate(
        (
            "來源草稿已保留在人工審核，沒有寫入本機 source draft。\n\n"
            f"審核原因：{data.get('review_reason') or '-'}\n"
            f"Pattern：{detection.get('pattern_id') or '-'}\n"
            f"信心分數：{confidence_text}\n"
            f"Source type hint：{detection.get('source_type_hint') or '-'}\n\n"
            f"證據：\n{evidence_preview}\n\n"
            f"下一步：{next_action_zh or '-'}"
        ),
        (
            "Source draft was kept in review; no local source draft was written.\n\n"
            f"Review reason: {data.get('review_reason') or '-'}\n"
            f"Pattern: {detection.get('pattern_id') or '-'}\n"
            f"Confidence: {confidence_text}\n"
            f"Source type hint: {detection.get('source_type_hint') or '-'}\n\n"
            f"Evidence:\n{evidence_preview}\n\n"
            f"Next: {next_action_en or '-'}"
        ),
    )


def _mapping_value(data: Mapping[str, object], key: str) -> Mapping[str, object]:
    value = data.get(key)
    return value if isinstance(value, dict) else {}


def _evidence_preview(detection: Mapping[str, object]) -> str:
    evidence = detection.get("evidence") if isinstance(detection.get("evidence"), list) else []
    return "\n".join(f"- {item}" for item in evidence[:5]) or "-"


def _confidence_text(value: object) -> str:
    try:
        return f"{float(value):.2f}"
    except (TypeError, ValueError):
        return "-"


def _text(value: object) -> str:
    return str(value).strip()
