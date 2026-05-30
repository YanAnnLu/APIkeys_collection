from __future__ import annotations

import os
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SQLiteWriteGateProfile:
    """Small process-local writer gate for one SQLite database path."""

    gate_id: str
    scope: str
    max_active_writers_per_database: int
    protects: tuple[str, ...]
    limitation: str

    def to_dict(self) -> dict[str, object]:
        return {
            "gate_id": self.gate_id,
            "scope": self.scope,
            "max_active_writers_per_database": self.max_active_writers_per_database,
            "protects": list(self.protects),
            "limitation": self.limitation,
        }


SQLITE_WRITE_GATE_PROFILE = SQLiteWriteGateProfile(
    gate_id="sqlite_write_gate",
    scope="process_per_sqlite_path",
    max_active_writers_per_database=1,
    protects=("csv_to_sqlite", "json_to_sqlite", "download_plan_import"),
    limitation="Process-local guard only; it does not coordinate writers across separate Python processes.",
)

_LOCKS_GUARD = threading.Lock()
_LOCKS_BY_PATH: dict[str, threading.RLock] = {}


def sqlite_write_gate_key(sqlite_path: str | Path) -> str:
    """Return a stable process-local key for a SQLite path."""

    path = Path(sqlite_path).expanduser().resolve(strict=False)
    return os.path.normcase(str(path))


def sqlite_write_gate_profile() -> SQLiteWriteGateProfile:
    return SQLITE_WRITE_GATE_PROFILE


@contextmanager
def sqlite_write_gate(sqlite_path: str | Path) -> Iterator[None]:
    """Serialize SQLite writes for one database path inside this process.

    The gate is intentionally small: it protects importer write critical
    sections without pretending to be a cross-process lock or full scheduler.
    """

    lock = _lock_for_sqlite_path(sqlite_path)
    with lock:
        yield


def _lock_for_sqlite_path(sqlite_path: str | Path) -> threading.RLock:
    key = sqlite_write_gate_key(sqlite_path)
    with _LOCKS_GUARD:
        lock = _LOCKS_BY_PATH.get(key)
        if lock is None:
            lock = threading.RLock()
            _LOCKS_BY_PATH[key] = lock
        return lock


__all__ = [
    "SQLITE_WRITE_GATE_PROFILE",
    "SQLiteWriteGateProfile",
    "sqlite_write_gate",
    "sqlite_write_gate_key",
    "sqlite_write_gate_profile",
]
