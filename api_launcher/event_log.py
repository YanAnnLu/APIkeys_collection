from __future__ import annotations

import json
import platform
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from api_launcher.db import utc_now_iso
from api_launcher.paths import log_file


EVENT_LOG_NAME = "launcher_events.jsonl"
ERROR_LOG_NAME = "launcher_errors.log"


@dataclass(frozen=True)
class LauncherEvent:
    level: str
    event: str
    message: str
    component: str = "launcher"
    context: dict[str, Any] = field(default_factory=dict)
    error_type: str = ""
    traceback: str = ""
    timestamp: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
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
                "system": platform.system(),
                "release": platform.release(),
                "python": platform.python_version(),
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
    path = log_path or log_file(EVENT_LOG_NAME)
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    events: list[dict[str, Any]] = []
    for line in lines[-limit:]:
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events


def _append_jsonl(path: Path, record: LauncherEvent) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(record.to_dict(), ensure_ascii=False, sort_keys=True) + "\n")


def _append_text_summary(path: Path, record: LauncherEvent) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(f"[{record.timestamp}] {record.level.upper()} {record.component}:{record.event} {record.message}\n")
        if record.context:
            handle.write(f"  context={json.dumps(record.context, ensure_ascii=False, sort_keys=True)}\n")
        if record.traceback:
            handle.write(record.traceback.rstrip() + "\n")
