from __future__ import annotations

import argparse

from api_launcher.cli_dataset_discovery import dataset_discovery_command_active
from api_launcher.cli_discovery import discovery_command_active
from api_launcher.cli_portal_intake import portal_intake_command_active


def command_requested(args: argparse.Namespace) -> bool:
    # 用集中判斷避免 core.py 每次新增 CLI flag 都忘記是否該進入命令模式。
    command_flags = (
        # 這個 tuple 必須保持與 parser 新增的命令型 flag 同步；漏掉會導致意外開 UI。
        args.init_db,
        args.seed,
        bool(args.seed_json),
        args.seed_key_reference,
        args.generate_templates,
        args.crawl,
        args.list_providers,
        args.list_categories,
        args.self_check,
        args.verify_downloads,
        args.verify_downloads_json,
        bool(args.run_download_plan),
        bool(args.write_mvp_demo_flow),
        bool(args.write_yfinance_demo_plan),
        bool(args.write_yfinance_live_plan),
        bool(args.adapter_review_plan),
        args.adapter_review_json,
        bool(args.resolve_adapter_plan),
        bool(args.write_resolved_adapter_plan),
        args.keep_original_adapter_entries,
        args.import_supported_plan_results,
        bool(args.import_csv_manifest),
        args.import_verified_csv_manifests,
        bool(args.import_json_manifest),
        args.import_verified_json_manifests,
        args.manifest_health,
        args.list_manifests,
        args.show_logs > 0,
        bool(args.handoff_report),
        bool(args.heartbeat_report),
        args.heartbeat_plan_json,
        bool(args.write_heartbeat_plan_json),
        bool(args.heartbeat_agent_prompt),
        args.workspace_inventory,
        bool(args.write_workspace_inventory_json),
        args.unreal_bridge_plan,
        bool(args.show_render_profile),
        args.list_render_effects,
        args.list_simulation_contracts,
        bool(args.show_library_actions),
        args.library_actions_json,
        bool(args.library_repair_manifest),
        bool(args.test_data_store),
        args.self_check_databases,
        args.self_check_databases_json,
        bool(args.reimport_missing_sqlite_table),
        bool(args.unmanage_database_asset),
        bool(args.write_database_repair_sql),
        args.database_repair_json,
        bool(args.generate_ai_summary),
        bool(args.write_tile_manifest),
        bool(args.export_json),
        bool(args.export_csv),
        bool(args.export_markdown),
        bool(args.export_dataset_plan),
        bool(args.export_candidate_plan),
        bool(args.write_sample_registry),
        bool(args.write_sample_key_reference),
        args.write_credentials_template,
        args.discover_datasets,
        discovery_command_active(args),
        dataset_discovery_command_active(args),
        portal_intake_command_active(args),
        args.summary,
    )
    return any(command_flags)
