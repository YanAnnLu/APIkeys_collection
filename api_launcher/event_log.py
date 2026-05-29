from __future__ import annotations

import json
import os
import sys
import traceback
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from api_launcher.db import utc_now_iso
from api_launcher.paths import log_file


EVENT_LOG_NAME = "launcher_events.jsonl"
ERROR_LOG_NAME = "launcher_errors.log"
DEFAULT_EVENT_LOG_TAIL_BLOCK_BYTES = 8192


@dataclass(frozen=True)
class LauncherEvent:
    # 事件紀錄是給 UI、CLI、handoff 與 agent 共用的穩定格式，不只給人讀。
    level: str
    event: str
    message: str
    component: str = "launcher"
    context: dict[str, Any] = field(default_factory=dict)
    error_type: str = ""
    traceback: str = ""
    timestamp: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        # 每筆事件都帶平台資訊，方便跨 Windows/macOS/Linux 追查同一類錯誤。
        return {
            "timestamp": self.timestamp,
            "level": self.level,
            "event": self.event,
            "component": self.component,
            "message": self.message,
            "context": self.context,
            "error_type": self.error_type,
            "traceback": self.traceback,
            "platform": {
                # 避免在 Windows/雲端碟環境中呼叫可能卡住的 platform.* 探測。
                "system": os.name,
                "release": "",
                "python": sys.version.split()[0],
            },
        }


def log_event(
    event: str,
    message: str,
    *,
    level: str = "info",
    component: str = "launcher",
    context: dict[str, Any] | None = None,
    log_path: Path | None = None,
) -> LauncherEvent:
    # 一般事件只寫 JSONL；warning/error 另寫文字摘要，方便不用 JSON 工具也能快速看錯誤。
    # context 應放可序列化的小型摘要，不要塞完整 payload 或秘密資訊。
    record = LauncherEvent(
        level=level,
        event=event,
        component=component,
        message=message,
        context=context or {},
    )
    _append_jsonl(log_path or log_file(EVENT_LOG_NAME), record)
    if level in {"warning", "error", "critical"}:
        _append_text_summary(log_file(ERROR_LOG_NAME), record)
    return record


def log_exception(
    event: str,
    exc: BaseException,
    *,
    component: str = "launcher",
    context: dict[str, Any] | None = None,
    log_path: Path | None = None,
) -> LauncherEvent:
    # 例外事件保留完整 traceback，讓 handoff 不只看到錯誤訊息，也能回到發生位置。
    record = LauncherEvent(
        level="error",
        event=event,
        component=component,
        message=str(exc),
        context=context or {},
        error_type=type(exc).__name__,
        traceback="".join(traceback.format_exception(type(exc), exc, exc.__traceback__)),
    )
    _append_jsonl(log_path or log_file(EVENT_LOG_NAME), record)
    _append_text_summary(log_file(ERROR_LOG_NAME), record)
    return record


def latest_events(limit: int = 20, *, log_path: Path | None = None) -> list[dict[str, Any]]:
    # 只串流保留尾端 N 行，避免 UI 或 handoff 因長期累積的大型 log 變慢或耗盡記憶體。
    path = log_path or log_file(EVENT_LOG_NAME)
    if not path.exists():
        # 沒有 log 是乾淨新環境的正常狀態，呼叫端不需要另外處理例外。
        return []
    bounded_limit = max(0, int(limit))
    if bounded_limit == 0:
        return []
    lines = _tail_text_lines(path, bounded_limit)
    events: list[dict[str, Any]] = []
    for line in lines:
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            # JSONL 可能因中斷寫入留下壞行；略過壞行，保留其他可用事件。
            continue
    return events


def _tail_text_lines(path: Path, limit: int, block_size: int = DEFAULT_EVENT_LOG_TAIL_BLOCK_BYTES) -> list[str]:
    """Read the last N lines without loading or scanning the entire log file."""

    try:
        return _tail_text_lines_seek(path, limit, block_size=block_size)
    except OSError:
        # Some cloud-mounted Windows drives occasionally reject binary seek/read
        # near EOF.  Handoff should degrade to a bounded streaming tail rather
        # than failing the whole CLI JSON report.
        return _tail_text_lines_stream(path, limit)


def _tail_text_lines_seek(path: Path, limit: int, block_size: int = DEFAULT_EVENT_LOG_TAIL_BLOCK_BYTES) -> list[str]:
    chunks: list[bytes] = []
    newline_count = 0
    with path.open("rb") as handle:
        handle.seek(0, 2)
        position = handle.tell()
        while position > 0 and newline_count <= limit:
            read_size = min(block_size, position)
            position -= read_size
            handle.seek(position)
            chunk = handle.read(read_size)
            chunks.append(chunk)
            newline_count += chunk.count(b"\n")
    tail_bytes = b"".join(reversed(chunks))
    return [line.decode("utf-8", errors="replace") for line in tail_bytes.splitlines()[-limit:]]


def _tail_text_lines_stream(path: Path, limit: int) -> list[str]:
    tail: deque[str] = deque(maxlen=max(0, limit))
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            tail.append(line.rstrip("\r\n"))
    return list(tail)


def _append_jsonl(path: Path, record: LauncherEvent) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        # sort_keys 讓 diff/agent 讀取更穩定；ensure_ascii=False 保留中文訊息。
        # JSONL 每行一筆事件，方便 tail、grep 與之後的 agent parser 處理。
        handle.write(json.dumps(record.to_dict(), ensure_ascii=False, sort_keys=True) + "\n")


def _append_text_summary(path: Path, record: LauncherEvent) -> None:
    # 文字摘要是輔助檔；JSONL 仍是機器可讀的主要來源。
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(f"[{record.timestamp}] {record.level.upper()} {record.component}:{record.event} {record.message}\n")
        if record.context:
            handle.write(f"  context={json.dumps(record.context, ensure_ascii=False, sort_keys=True)}\n")
        if record.traceback:
            handle.write(record.traceback.rstrip() + "\n")
