"""Tk download-plan composition workflows for RuRuKa Asset Launcher.

這個 mixin 管理 provider / dataset version 如何進入下載計畫，以及 Adapter plan
解析、plan JSON 匯入/匯出等 UI 調度。下載、匯入、repair 的實際執行仍留在各自 workflow。
"""

from __future__ import annotations

import json
import urllib.parse
from pathlib import Path
from tkinter import BooleanVar, messagebox

import APIkeys_collection as core
from api_launcher.adapter_review import adapter_review_items
from api_launcher.paths import DOWNLOADS_DIR, state_file
from frontends.tk.dialogs import AdapterReviewDialog
from frontends.tk.provider_models import ProviderRow
from frontends.tk.ui_config import DOWNLOAD_PLAN_NAME, RESOLVED_DOWNLOAD_PLAN_NAME


class PlanWorkflowMixin:
    """封裝下載計畫資料模型與 Adapter plan UI workflow。"""

    def add_dataset_to_plan(self, dataset: core.Dataset) -> None:
        options = core.version_options_for_dataset(dataset)
        if not options:
            self.status_var.set(self.tr(f"這筆資料集沒有版本資訊：{dataset.title}", f"No version metadata for dataset: {dataset.title}"))
            return
        self.add_provider_version_to_plan(dataset.provider_id, options[0])

    def toggle_provider(self, provider_id: str) -> None:
        var = self.selected[provider_id]
        var.set(not var.get())
        self.render_table()
        row = self.row_by_provider_id(provider_id)
        label = row.name if row else provider_id
        self.status_var.set(f"{'已加入下載計畫' if var.get() else '已移出下載計畫'}：{label}")

    def add_provider_to_plan(self, provider_id: str) -> None:
        row = self.row_by_provider_id(provider_id)
        if row is None:
            return
        self.remove_provider_version_plan_items(provider_id)
        var = self.selected.setdefault(provider_id, BooleanVar(value=False))
        already_selected = var.get()
        var.set(True)
        self.active_provider_id = provider_id
        self.render_table()
        self.status_var.set(
            f"{'已在下載計畫中' if already_selected else '已加入下載計畫'}：{row.name}"
        )

    def add_provider_version_to_plan(self, provider_id: str, option: core.DatasetVersionOption) -> None:
        # dataset/version plan 使用獨立 plan_key，保留 provider 一對多資料集的購物車語意。
        row = self.row_by_provider_id(provider_id)
        if row is None:
            return
        plan_key = self.plan_key_for_version(provider_id, option)
        self.plan_version_by_provider[plan_key] = option
        self.plan_provider_by_key[plan_key] = provider_id
        self.selected.setdefault(provider_id, BooleanVar(value=False)).set(True)
        self.active_provider_id = provider_id
        self.render_table()
        self.status_var.set(self.tr(f"已加入下載計畫：{row.name} {option.menu_label}", f"Added {row.name} {option.menu_label} to download plan"))

    def plan_key_for_version(self, provider_id: str, option: core.DatasetVersionOption) -> str:
        version = option.version or option.label or "unversioned"
        return f"{provider_id}::dataset::{option.dataset_uid}::{version}"

    def provider_id_for_plan_key(self, plan_key: str) -> str:
        if plan_key in self.plan_provider_by_key:
            return self.plan_provider_by_key[plan_key]
        if "::dataset::" in plan_key:
            return plan_key.split("::dataset::", 1)[0]
        return plan_key

    def version_plan_keys_for_provider(self, provider_id: str) -> list[str]:
        return [
            plan_key
            for plan_key in self.plan_version_by_provider
            if self.provider_id_for_plan_key(plan_key) == provider_id
        ]

    def remove_provider_version_plan_items(self, provider_id: str) -> None:
        for plan_key in self.version_plan_keys_for_provider(provider_id):
            self.plan_version_by_provider.pop(plan_key, None)
            self.plan_provider_by_key.pop(plan_key, None)

    def selected_plan_items(self) -> list[tuple[str, ProviderRow, core.DatasetVersionOption | None]]:
        # 先列具體 dataset/version，再補 provider-level 選取，避免同 provider 重複產生 plan entry。
        items: list[tuple[str, ProviderRow, core.DatasetVersionOption | None]] = []
        seen_keys: set[str] = set()
        for plan_key, option in self.plan_version_by_provider.items():
            provider_id = self.provider_id_for_plan_key(plan_key)
            row = self.row_by_provider_id(provider_id)
            if row is not None:
                items.append((plan_key, row, option))
                seen_keys.add(plan_key)
        for row in self.selected_rows():
            if self.version_plan_keys_for_provider(row.provider_id):
                continue
            if row.provider_id not in seen_keys:
                items.append((row.provider_id, row, None))
                seen_keys.add(row.provider_id)
        return items

    def selected_plan_keys(self) -> list[str]:
        return [plan_key for plan_key, _row, _option in self.selected_plan_items()]

    def plan_item_label(self, plan_key: str, row: ProviderRow | None = None, option: core.DatasetVersionOption | None = None) -> str:
        provider_id = self.provider_id_for_plan_key(plan_key)
        row = row or self.row_by_provider_id(provider_id)
        label = row.name if row else provider_id
        option = option or self.plan_version_by_provider.get(plan_key)
        if option:
            return f"{label} / {option.dataset_id} {option.version or option.label}"
        return label

    def plan_entry_for_item(
        self,
        row: ProviderRow,
        option: core.DatasetVersionOption | None = None,
        plan_key: str = "",
    ) -> tuple[dict[str, object] | None, str]:
        if plan_key and plan_key in self.download_plan_entries_by_provider:
            # 已排過下載的 entry 保留原 target/import_plan，避免 UI 重繪後改變下載目標。
            return dict(self.download_plan_entries_by_provider[plan_key]), ""
        if option:
            dataset = self.dataset_for_version_option(option)
            if dataset is None:
                return None, self.tr("找不到候選資料集 metadata", "Dataset metadata was not found")
            return (
                core.provider_dataset_version_plan_entry(
                    self.provider_from_row(row),
                    dataset,
                    option,
                    downloads_root=DOWNLOADS_DIR,
                ),
                "",
            )

        entry = core.provider_plan_entry(self.provider_from_row(row))
        eligibility = row.download_eligibility
        if eligibility.status == "direct_download" and eligibility.direct_url:
            target_path = self.download_target_for_row(row, eligibility.direct_url)
            entry["download_url"] = eligibility.direct_url
            entry["target_path"] = str(target_path)
            entry["use_staging"] = True
        return entry, ""

    def version_options_for_provider(self, provider_id: str) -> list[core.DatasetVersionOption]:
        # 若 catalog 尚未有 adapter dataset，右鍵開版本選單時做一次 bounded discovery。
        conn = self._connect()
        try:
            repository = core.ApiCatalogRepository(conn)
            datasets = repository.list_datasets(provider_id)
            if not datasets:
                providers = repository.load_providers([provider_id])
                for provider in providers:
                    for adapter in core.adapters_for_provider(provider):
                        for dataset in adapter.discover(provider):
                            repository.upsert_dataset(dataset)
                datasets = repository.list_datasets(provider_id)
            return core.version_options_for_datasets(datasets)
        finally:
            conn.close()

    def dataset_for_version_option(self, option: core.DatasetVersionOption) -> core.Dataset | None:
        conn = self._connect()
        try:
            return core.ApiCatalogRepository(conn).get_dataset(option.dataset_uid)
        finally:
            conn.close()

    def selected_provider_ids(self) -> list[str]:
        return [provider_id for provider_id, var in self.selected.items() if var.get()]

    def selected_rows(self) -> list[ProviderRow]:
        selected_ids = set(self.selected_provider_ids())
        return [row for row in self.rows if row.provider_id in selected_ids]

    def remove_selected_from_plan(self) -> None:
        selection = self.cart_tree.selection()
        if not selection:
            messagebox.showinfo("尚未選取", "請先在下載計畫中選取一個資料源。")
            return
        plan_key = str(selection[0])
        provider_id = self.provider_id_for_plan_key(plan_key)
        row = self.row_by_provider_id(provider_id)
        label = self.plan_item_label(plan_key, row)
        self.plan_version_by_provider.pop(plan_key, None)
        self.plan_provider_by_key.pop(plan_key, None)
        self.download_plan_entries_by_provider.pop(plan_key, None)
        self.import_status_by_plan_key.pop(plan_key, None)
        if plan_key == provider_id or not self.version_plan_keys_for_provider(provider_id):
            self.selected.setdefault(provider_id, BooleanVar(value=False)).set(False)
        self.render_table()
        self.status_var.set(f"已移出下載計畫：{label}")

    def clear_download_plan(self) -> None:
        if not self.selected_provider_ids():
            self.status_var.set("下載計畫已經是空的。")
            return
        for var in self.selected.values():
            var.set(False)
        self.plan_version_by_provider.clear()
        self.plan_provider_by_key.clear()
        self.download_plan_entries_by_provider.clear()
        self.import_status_by_plan_key.clear()
        self.render_table()
        self.status_var.set("已清空下載計畫。")

    def current_planned_entries(self) -> tuple[list[dict[str, object]], bool]:
        items = self.selected_plan_items()
        planned_entries: list[dict[str, object]] = []
        has_dataset_entries = False
        for plan_key, row, option in items:
            entry, build_error = self.plan_entry_for_item(row, option, plan_key=plan_key)
            if entry is None:
                entry = core.provider_plan_entry(self.provider_from_row(row))
                if option:
                    entry["dataset_version"] = option.to_plan_metadata()
                entry["plan_status"] = "metadata_missing"
                entry["plan_error"] = build_error
            if option:
                has_dataset_entries = True
            planned_entries.append(entry)
        return planned_entries, has_dataset_entries

    def current_download_plan_payload(self) -> tuple[dict[str, object], list[tuple[str, ProviderRow, core.DatasetVersionOption | None]]]:
        items = self.selected_plan_items()
        plan_name = self.plan_name_var.get().strip() or "Untitled download plan"
        planned_entries, has_dataset_entries = self.current_planned_entries()
        if has_dataset_entries:
            payload = core.build_dataset_download_plan(planned_entries, plan_name=plan_name)
        else:
            payload = core.build_download_plan([], plan_name=plan_name)
            payload["providers"] = planned_entries
            payload["summary"]["provider_count"] = len({str(entry.get("provider_id") or "") for entry in planned_entries if isinstance(entry, dict)})
        payload["summary"]["plan_item_count"] = len(planned_entries)
        return payload, items

    def resolve_adapter_plan_from_ui(self) -> None:
        if not self.selected_plan_items():
            messagebox.showinfo(self.tr("下載計畫是空的", "Download plan is empty"), self.tr("請先把資料集或資料源加入下載計畫。", "Add datasets or sources to the download plan first."))
            return
        payload, items = self.current_download_plan_payload()
        index_to_plan_key = {index: plan_key for index, (plan_key, _row, _option) in enumerate(items, start=1)}
        index_has_version = {index: option is not None for index, (_plan_key, _row, option) in enumerate(items, start=1)}
        resolved_payload, result = core.resolve_adapter_review_plan_payload(payload, downloads_root=DOWNLOADS_DIR)
        output_path = state_file(RESOLVED_DOWNLOAD_PLAN_NAME)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(resolved_payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

        resolved_entries = [
            entry
            for entry in resolved_payload.get("providers", [])
            if isinstance(entry, dict) and isinstance(entry.get("adapter_resolution"), dict)
        ]
        resolved_original_indices = {
            int((entry.get("adapter_resolution") or {}).get("original_plan_index"))
            for entry in resolved_entries
            if isinstance(entry.get("adapter_resolution"), dict) and str((entry.get("adapter_resolution") or {}).get("original_plan_index") or "").isdigit()
        }
        for original_index in resolved_original_indices:
            original_key = index_to_plan_key.get(original_index, "")
            if original_key and index_has_version.get(original_index):
                self.plan_version_by_provider.pop(original_key, None)
                self.plan_provider_by_key.pop(original_key, None)
                self.download_plan_entries_by_provider.pop(original_key, None)
                self.import_status_by_plan_key.pop(original_key, None)

        added = 0
        for entry in resolved_entries:
            provider_id = str(entry.get("provider_id") or "").strip()
            if not provider_id or self.row_by_provider_id(provider_id) is None:
                continue
            option = self.version_option_from_plan_entry(entry)
            if option is None:
                continue
            plan_key = self.plan_key_for_resolved_entry(entry)
            self.plan_version_by_provider[plan_key] = option
            self.plan_provider_by_key[plan_key] = provider_id
            self.download_plan_entries_by_provider[plan_key] = dict(entry)
            self.selected.setdefault(provider_id, BooleanVar(value=False)).set(True)
            added += 1

        self.render_table()
        summary = self.tr(
            f"Adapter 計畫解析完成：新增 {added} 個可下載項目；仍需 review {result.unresolved_review_entries} 個。",
            f"Adapter plan resolved: added {added} direct items; {result.unresolved_review_entries} still need review.",
        )
        self.status_var.set(summary)
        if added:
            messagebox.showinfo(
                self.tr("解析完成", "Resolve finished"),
                self.tr(
                    f"{summary}\n\n已同步到下方下載計畫，也已輸出：\n{output_path}\n\n接下來可以按「開始」下載新項目。",
                    f"{summary}\n\nThe download plan panel was updated and a resolved plan was written to:\n{output_path}\n\nYou can click Start to download the new items.",
                ),
            )
        else:
            detail = "\n".join(result.warnings[:5])
            message = self.tr(
                f"目前沒有找到可以自動轉成 direct download 的 resource。\n\n已輸出檢查結果：\n{output_path}",
                f"No resource could be safely promoted to direct download.\n\nA checked plan was written to:\n{output_path}",
            )
            if detail:
                message += f"\n\n{detail}"
            messagebox.showinfo(self.tr("沒有可自動解析項目", "No automatic resolution"), message)

    def add_download_plan_entries_from_file(self, plan_path: Path) -> int:
        # 將 adapter 產生的 JSON plan 接回現有下載計畫模型，避免 UI 和 CLI 各自維護一套 plan schema。
        payload = json.loads(Path(plan_path).read_text(encoding="utf-8"))
        added = self.add_download_plan_entries_from_payload(payload)
        self.render_table()
        self.update_download_plan_panel()
        return added

    def add_download_plan_entries_from_payload(self, payload: dict[str, object]) -> int:
        # 從既有 plan JSON 還原 UI 下載計畫時，只接受可對應到 catalog provider 的 direct entries。
        added = 0
        raw_entries = payload.get("providers") if isinstance(payload.get("providers"), list) else []
        for entry in raw_entries:
            if not isinstance(entry, dict):
                continue
            provider_id = str(entry.get("provider_id") or "").strip()
            if not provider_id or self.row_by_provider_id(provider_id) is None:
                continue
            option = self.version_option_from_plan_entry(entry)
            if option is None:
                continue
            plan_key = self.plan_key_for_resolved_entry(entry)
            self.plan_version_by_provider[plan_key] = option
            self.plan_provider_by_key[plan_key] = provider_id
            self.download_plan_entries_by_provider[plan_key] = dict(entry)
            self.import_status_by_plan_key.pop(plan_key, None)
            self.selected.setdefault(provider_id, BooleanVar(value=False)).set(True)
            self.active_provider_id = provider_id
            added += 1
        return added

    def version_option_from_plan_entry(self, entry: dict[str, object]) -> core.DatasetVersionOption | None:
        version_meta = entry.get("dataset_version") if isinstance(entry.get("dataset_version"), dict) else {}
        download_url = str(entry.get("download_url") or version_meta.get("download_url") or "").strip()
        if not download_url:
            return None
        metadata = version_meta.get("metadata") if isinstance(version_meta.get("metadata"), dict) else {}
        return core.DatasetVersionOption(
            dataset_uid=str(entry.get("dataset_uid") or version_meta.get("dataset_uid") or ""),
            dataset_id=str(entry.get("dataset_id") or version_meta.get("dataset_id") or ""),
            label=str(version_meta.get("label") or entry.get("dataset_title") or entry.get("name") or "resolved resource"),
            version=str(version_meta.get("version") or "resolved"),
            status=str(version_meta.get("version_status") or "resolved_resource"),
            download_url=download_url,
            landing_url=str(entry.get("landing_url") or version_meta.get("landing_url") or entry.get("docs_url") or ""),
            update_strategy=str(version_meta.get("update_strategy") or "full_replace_if_needed"),
            notes=str(version_meta.get("notes") or ""),
            metadata=dict(metadata),
        )

    def plan_key_for_resolved_entry(self, entry: dict[str, object]) -> str:
        version_meta = entry.get("dataset_version") if isinstance(entry.get("dataset_version"), dict) else {}
        provider_id = str(entry.get("provider_id") or "unknown_provider")
        dataset_uid = str(entry.get("dataset_uid") or version_meta.get("dataset_uid") or entry.get("dataset_id") or "dataset")
        version = str(version_meta.get("version") or "resolved")
        filename = Path(urllib.parse.unquote(urllib.parse.urlparse(str(entry.get("download_url") or "")).path)).name or "resource"
        base = f"{provider_id}::resolved::{dataset_uid}::{version}::{filename}"
        candidate = base
        suffix = 2
        while candidate in self.plan_version_by_provider or candidate in self.plan_provider_by_key:
            candidate = f"{base}::{suffix}"
            suffix += 1
        return candidate

    def open_adapter_review_panel(self) -> None:
        if not self.selected_plan_items():
            messagebox.showinfo(self.tr("下載計畫是空的", "Download plan is empty"), self.tr("請先把資料集或資料源加入下載計畫。", "Add datasets or sources to the download plan first."))
            return
        planned_entries, _has_dataset_entries = self.current_planned_entries()
        review_items = adapter_review_items({"providers": planned_entries})
        if not review_items:
            messagebox.showinfo(self.tr("沒有 Adapter 待辦", "No adapter review items"), self.tr("目前下載計畫沒有需要 adapter 接手的項目。", "The current plan has no adapter-required items."))
            return
        AdapterReviewDialog(self, review_items)

    def export_download_plan(self) -> None:
        items = self.selected_plan_items()
        if not items:
            messagebox.showinfo("下載計畫是空的", "請先把至少一個資料源加入下載計畫。")
            return
        plan_name = self.plan_name_var.get().strip() or "Untitled download plan"
        payload, _items = self.current_download_plan_payload()
        output_path = state_file(DOWNLOAD_PLAN_NAME)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        self.status_var.set(f"已匯出下載計畫：{plan_name} ({len(items)} 個項目)")
        messagebox.showinfo("匯出完成", f"已建立 {output_path}\n\nPlan: {plan_name}")
