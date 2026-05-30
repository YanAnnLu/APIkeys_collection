"""Declarative Tk background-job capacity policies.

The current Tk frontend still uses small worker threads for blocking work.
This module keeps the first hardening layer explicit: every bounded workflow
has a named policy, a capacity, and the owner attributes used by the shared
single-flight helper.  It is not a full scheduler; it is the table that keeps
workflow-level limits from drifting apart.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class TkBackgroundJobPolicy:
    """One bounded Tk worker lane.

    ``policy_id`` is stable diagnostic vocabulary.  ``max_active_jobs`` is the
    current safety cap for one UI instance, not a promise of backend throughput.
    """

    policy_id: str
    max_active_jobs: int
    active_jobs_attr: str
    active_jobs_lock_attr: str
    description: str


TK_BACKGROUND_JOB_POLICIES: dict[str, TkBackgroundJobPolicy] = {
    "ai_summary": TkBackgroundJobPolicy(
        policy_id="ai_summary",
        max_active_jobs=2,
        active_jobs_attr="ai_summary_active_jobs",
        active_jobs_lock_attr="ai_summary_active_jobs_lock",
        description="Provider AI summary generation.",
    ),
    "crawler_asset": TkBackgroundJobPolicy(
        policy_id="crawler_asset",
        max_active_jobs=4,
        active_jobs_attr="crawler_asset_active_jobs",
        active_jobs_lock_attr="crawler_asset_active_jobs_lock",
        description="Crawler asset listing, schema probe, plan build, and seed download/import handoff.",
    ),
    "discovery": TkBackgroundJobPolicy(
        policy_id="discovery",
        max_active_jobs=2,
        active_jobs_attr="discovery_active_jobs",
        active_jobs_lock_attr="discovery_active_jobs_lock",
        description="Provider discovery, dataset discovery, and crawler audit actions.",
    ),
    "oauth": TkBackgroundJobPolicy(
        policy_id="oauth",
        max_active_jobs=2,
        active_jobs_attr="oauth_active_jobs",
        active_jobs_lock_attr="oauth_active_jobs_lock",
        description="OAuth browser login and device-code polling.",
    ),
    "plan_bounds_probe": TkBackgroundJobPolicy(
        policy_id="plan_bounds_probe",
        max_active_jobs=2,
        active_jobs_attr="plan_bounds_active_jobs",
        active_jobs_lock_attr="plan_bounds_active_jobs_lock",
        description="Download-plan bounds/schema probing.",
    ),
    "sidebar_favicon": TkBackgroundJobPolicy(
        policy_id="sidebar_favicon",
        max_active_jobs=4,
        active_jobs_attr="sidebar_active_jobs",
        active_jobs_lock_attr="sidebar_active_jobs_lock",
        description="Provider favicon fetch/cache jobs.",
    ),
    "source_action": TkBackgroundJobPolicy(
        policy_id="source_action",
        max_active_jobs=2,
        active_jobs_attr="source_action_active_jobs",
        active_jobs_lock_attr="source_action_active_jobs_lock",
        description="Metadata crawl and row-level source actions.",
    ),
    "sqlite_import": TkBackgroundJobPolicy(
        policy_id="sqlite_import",
        max_active_jobs=1,
        active_jobs_attr="import_active_jobs",
        active_jobs_lock_attr="import_active_jobs_lock",
        description="SQLite import/write lane.",
    ),
}


MAX_TK_AI_SUMMARY_BACKGROUND_JOBS = TK_BACKGROUND_JOB_POLICIES["ai_summary"].max_active_jobs
MAX_CRAWLER_ASSET_BACKGROUND_JOBS = TK_BACKGROUND_JOB_POLICIES["crawler_asset"].max_active_jobs
MAX_TK_DISCOVERY_BACKGROUND_JOBS = TK_BACKGROUND_JOB_POLICIES["discovery"].max_active_jobs
MAX_TK_OAUTH_BACKGROUND_JOBS = TK_BACKGROUND_JOB_POLICIES["oauth"].max_active_jobs
MAX_TK_PLAN_BOUNDS_PROBE_JOBS = TK_BACKGROUND_JOB_POLICIES["plan_bounds_probe"].max_active_jobs
MAX_TK_SIDEBAR_FAVICON_JOBS = TK_BACKGROUND_JOB_POLICIES["sidebar_favicon"].max_active_jobs
MAX_TK_SOURCE_ACTION_BACKGROUND_JOBS = TK_BACKGROUND_JOB_POLICIES["source_action"].max_active_jobs
MAX_TK_SQLITE_IMPORT_JOBS = TK_BACKGROUND_JOB_POLICIES["sqlite_import"].max_active_jobs


def tk_background_job_policy(policy_id: str) -> TkBackgroundJobPolicy:
    """Return one policy by id, failing fast on unknown diagnostic vocabulary."""

    try:
        return TK_BACKGROUND_JOB_POLICIES[policy_id]
    except KeyError as exc:
        raise ValueError(f"Unknown Tk background job policy: {policy_id}") from exc


def iter_tk_background_job_policies() -> Iterable[TkBackgroundJobPolicy]:
    """Iterate policies in stable id order for diagnostics and tests."""

    for policy_id in sorted(TK_BACKGROUND_JOB_POLICIES):
        yield TK_BACKGROUND_JOB_POLICIES[policy_id]


__all__ = [
    "MAX_CRAWLER_ASSET_BACKGROUND_JOBS",
    "MAX_TK_AI_SUMMARY_BACKGROUND_JOBS",
    "MAX_TK_DISCOVERY_BACKGROUND_JOBS",
    "MAX_TK_OAUTH_BACKGROUND_JOBS",
    "MAX_TK_PLAN_BOUNDS_PROBE_JOBS",
    "MAX_TK_SIDEBAR_FAVICON_JOBS",
    "MAX_TK_SOURCE_ACTION_BACKGROUND_JOBS",
    "MAX_TK_SQLITE_IMPORT_JOBS",
    "TK_BACKGROUND_JOB_POLICIES",
    "TkBackgroundJobPolicy",
    "iter_tk_background_job_policies",
    "tk_background_job_policy",
]
