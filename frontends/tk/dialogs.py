"""Compatibility exports for Tk dialog classes.

Dialog implementations live in focused owner modules.  This facade keeps the
historic `frontends.tk.dialogs` import path stable while preventing new dialog
logic from accumulating in one large file.
"""

from __future__ import annotations

from frontends.tk.adapter_review_dialog import AdapterReviewDialog
from frontends.tk.ai_settings_dialogs import AiModelSettingsDialog, GoogleGeminiSettingsDialog
from frontends.tk.data_store_connection_settings_dialog import DataStoreConnectionSettingsDialog
from frontends.tk.database_client_settings_dialog import DatabaseClientSettingsDialog
from frontends.tk.dataset_candidate_review_dialog import DatasetCandidateReviewDialog
from frontends.tk.developer_cli_dialog import DeveloperCliDialog
from frontends.tk.import_policy_dialog import ImportExistingTablePolicyDialog
from frontends.tk.language_settings_dialog import UiLanguageSettingsDialog
from frontends.tk.provider_candidate_review_dialog import ProviderCandidateReviewDialog
from frontends.tk.provider_editor_dialog import ProviderEditorDialog
from frontends.tk.recent_event_logs_dialog import RecentEventLogsDialog
from frontends.tk.startup_environment_checks_dialog import StartupEnvironmentChecksDialog

__all__ = [
    "AdapterReviewDialog",
    "AiModelSettingsDialog",
    "DataStoreConnectionSettingsDialog",
    "DatabaseClientSettingsDialog",
    "DatasetCandidateReviewDialog",
    "DeveloperCliDialog",
    "GoogleGeminiSettingsDialog",
    "ImportExistingTablePolicyDialog",
    "ProviderCandidateReviewDialog",
    "ProviderEditorDialog",
    "RecentEventLogsDialog",
    "StartupEnvironmentChecksDialog",
    "UiLanguageSettingsDialog",
]
