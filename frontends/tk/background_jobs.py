"""Small single-flight helpers for Tk background work.

Tk workflows still own user-facing status text and service calls.  This module
only protects a shared invariant: one logical job key should not spawn multiple
daemon threads while it is already active.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any

TkJobKey = tuple[str, str, str]


def start_single_flight_thread(
    owner: object,
    job_key: TkJobKey,
    target: Callable[..., None],
    args: tuple[Any, ...],
    *,
    active_jobs_attr: str,
    active_jobs_lock_attr: str,
    on_duplicate: Callable[[], None],
) -> bool:
    """Start a daemon thread unless the key is already active on ``owner``."""

    active_jobs = _active_job_set(owner, active_jobs_attr)
    active_jobs_lock = _active_job_lock(owner, active_jobs_lock_attr)
    with active_jobs_lock:
        if job_key in active_jobs:
            on_duplicate()
            return False
        active_jobs.add(job_key)

    def runner(*worker_args: Any) -> None:
        try:
            target(*worker_args)
        finally:
            release_single_flight_job(
                owner,
                job_key,
                active_jobs_attr=active_jobs_attr,
                active_jobs_lock_attr=active_jobs_lock_attr,
            )

    threading.Thread(target=runner, args=args, daemon=True).start()
    return True


def single_flight_job_is_active(
    owner: object,
    job_key: TkJobKey,
    *,
    active_jobs_attr: str,
    on_duplicate: Callable[[], None] | None = None,
) -> bool:
    """Return whether a job key is active, optionally firing duplicate UI feedback."""

    active_jobs = getattr(owner, active_jobs_attr, None)
    if isinstance(active_jobs, set) and job_key in active_jobs:
        if on_duplicate is not None:
            on_duplicate()
        return True
    return False


def release_single_flight_job(
    owner: object,
    job_key: TkJobKey,
    *,
    active_jobs_attr: str,
    active_jobs_lock_attr: str,
) -> None:
    """Release a job key if the owner still has the matching active-job set."""

    active_jobs = getattr(owner, active_jobs_attr, None)
    if not isinstance(active_jobs, set):
        return
    active_jobs_lock = getattr(owner, active_jobs_lock_attr, None)
    if active_jobs_lock is None:
        active_jobs.discard(job_key)
        return
    with active_jobs_lock:
        active_jobs.discard(job_key)


def _active_job_set(owner: object, attr: str) -> set[TkJobKey]:
    active_jobs = getattr(owner, attr, None)
    if not isinstance(active_jobs, set):
        active_jobs = set()
        setattr(owner, attr, active_jobs)
    return active_jobs


def _active_job_lock(owner: object, attr: str) -> threading.Lock:
    active_jobs_lock = getattr(owner, attr, None)
    if active_jobs_lock is None:
        active_jobs_lock = threading.Lock()
        setattr(owner, attr, active_jobs_lock)
    return active_jobs_lock


__all__ = [
    "TkJobKey",
    "release_single_flight_job",
    "single_flight_job_is_active",
    "start_single_flight_thread",
]
