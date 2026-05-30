from __future__ import annotations

from tkinter import END, BooleanVar

import APIkeys_collection as core
from api_launcher.dataset_candidate_display import dataset_candidate_status_label
from frontends.tk.provider_models import ProviderRow


class TableDataWorkflowMixin:
    """封裝 provider/dataset 表格的資料生命週期。

    這裡保留 reload/filter/render 與 dataset row helper，讓主視窗只負責組裝 layout；
    右鍵選單、row action、細節面板仍留在主流程，避免一次搬太多有副作用的控制邏輯。
    """

    def reload_data(self) -> None:
        # reload 是 UI 的資料同步點：一次讀 provider、dataset，再重建篩選與下載計畫顯示。
        conn = self._connect()
        try:
            repository = core.ApiCatalogRepository(conn)
            entries = repository.list_provider_catalog_entries()
            datasets = repository.list_datasets()
        finally:
            conn.close()
        self.rows = [ProviderRow(entry) for entry in entries]
        self.datasets_by_provider = {}
        for dataset in datasets:
            self.datasets_by_provider.setdefault(dataset.provider_id, []).append(dataset)
        for provider_datasets in self.datasets_by_provider.values():
            provider_datasets.sort(key=lambda item: item.title.lower())
        for row in self.rows:
            self.selected.setdefault(row.provider_id, BooleanVar(value=False))
        known_ids = {row.provider_id for row in self.rows}
        for provider_id in list(self.selected):
            if provider_id not in known_ids:
                del self.selected[provider_id]
        self.apply_filter()
        if self.active_provider_id not in {row.provider_id for row in self.rows}:
            self.active_provider_id = self.rows[0].provider_id if self.rows else ""
        self.refresh_sidebar_filters()
        if self.detail_visible:
            self.update_detail_panel(self.row_by_provider_id(self.active_provider_id))
        self.update_download_plan_panel()
        self.status_var.set(f"已載入 {len(self.rows)} 個資料源。")

    def apply_filter(self) -> None:
        if not hasattr(self, "tree"):
            return
        # 搜尋會同時命中 provider 欄位與 crawler 發現的 dataset 欄位。
        query = "" if self.search_placeholder_active else self.search_var.get().strip().lower()
        category = self.category_var.get()
        self.current_filter_query = query
        self.current_filter_category = category
        filtered = []
        for row in self.rows:
            provider_datasets = self.datasets_by_provider.get(row.provider_id, [])
            if category == "starred" and not row.is_starred:
                continue
            if category == "noaa" and "noaa" not in row.provider_id.lower() and "noaa" not in row.owner.lower():
                continue
            if category == "requires_key" and not row.key_env_var:
                continue
            if category.startswith("provider:"):
                if row.owner != category.removeprefix("provider:"):
                    continue
            elif category not in ("all", "starred", "noaa", "requires_key"):
                if category not in row.categories and not any(category in dataset.categories for dataset in provider_datasets):
                    continue
            haystack = " ".join([row.provider_id, row.name, row.owner, row.category_label, row.auth_type, row.notes]).lower()
            dataset_haystack = " ".join(
                " ".join(
                    [
                        dataset.dataset_id,
                        dataset.title,
                        ", ".join(dataset.categories),
                        dataset.data_type,
                        dataset.native_format,
                        dataset.geographic_scope,
                        str(dataset.metadata.get("candidate_status") or ""),
                    ]
                )
                for dataset in provider_datasets
            ).lower()
            if query and query not in haystack:
                if query not in dataset_haystack:
                    continue
            filtered.append(row)
        self.filtered_rows = filtered
        self.render_table()

    def render_table(self) -> None:
        # Treeview 不是 virtual list；資料量變大前先用完整重繪保持狀態簡單可預期。
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.dataset_table_items = {}
        for row in self.filtered_rows:
            checked = "?" if self.selected[row.provider_id].get() else ""
            tags = []
            if row.is_starred:
                tags.append("starred")
            if row.action_label:
                tags.append("has_action")
            if row.update_status == "remote_updated":
                tags.append("remote_updated")
            provider_datasets = self.visible_datasets_for_provider(row.provider_id)
            row_name = row.name
            if provider_datasets:
                row_name = self.tr(f"{row.name}（{len(provider_datasets)} 筆資料集）", f"{row.name} ({len(provider_datasets)} datasets)")
            self.tree.insert(
                "",
                END,
                iid=row.provider_id,
                values=(
                    row.star_label,
                    checked,
                    row_name,
                    row.category_label,
                    row.local_label,
                    self.localized_download_label(row.download_eligibility),
                    row.action_label,
                ),
                tags=tuple(tags),
            )
            if self.show_dataset_rows_var.get():
                for dataset in provider_datasets:
                    item_id = self.dataset_tree_iid(dataset)
                    self.dataset_table_items[item_id] = dataset
                    self.tree.insert(
                        "",
                        END,
                        iid=item_id,
                        values=(
                            "",
                            "+",
                            f"  ↳ {dataset.title}",
                            self.dataset_category_label(dataset),
                            self.dataset_candidate_status_label(dataset),
                            self.dataset_download_label(dataset),
                            self.tr("加入", "Add"),
                        ),
                        tags=("dataset_row",),
                    )
        if self.active_provider_id in {row.provider_id for row in self.filtered_rows}:
            self.tree.selection_set(self.active_provider_id)
            self.tree.focus(self.active_provider_id)
        self.resize_table_columns()
        self.update_download_plan_panel()
        self.status_var.set(f"顯示 {len(self.filtered_rows)} / {len(self.rows)} 個資料源。")

    def dataset_tree_iid(self, dataset: core.Dataset) -> str:
        return f"dataset::{dataset.dataset_uid}"

    def dataset_for_table_item(self, item: object) -> core.Dataset | None:
        return self.dataset_table_items.get(str(item))

    def provider_id_for_table_item(self, item: object) -> str:
        dataset = self.dataset_for_table_item(item)
        if dataset is not None:
            return dataset.provider_id
        return str(item)

    def visible_datasets_for_provider(self, provider_id: str) -> list[core.Dataset]:
        # rejected 候選不顯示在主列表，但仍可在候選審核面板查到歷史狀態。
        datasets = self.datasets_by_provider.get(provider_id, [])
        query = self.current_filter_query
        category = self.current_filter_category
        visible = []
        for dataset in datasets:
            if self.dataset_candidate_status(dataset) == "rejected":
                continue
            if category not in ("all", "starred", "noaa", "requires_key") and not category.startswith("provider:"):
                if category not in dataset.categories:
                    continue
            if query and query not in self.dataset_search_text(dataset):
                continue
            visible.append(dataset)
        return visible

    def dataset_search_text(self, dataset: core.Dataset) -> str:
        metadata = dataset.metadata
        return " ".join(
            [
                dataset.dataset_uid,
                dataset.provider_id,
                dataset.dataset_id,
                dataset.title,
                ", ".join(dataset.categories),
                dataset.data_type,
                dataset.native_format,
                dataset.geographic_scope,
                dataset.temporal_coverage,
                str(metadata.get("candidate_status") or ""),
                str(metadata.get("source_url") or ""),
            ]
        ).lower()

    def dataset_candidate_status(self, dataset: core.Dataset) -> str:
        return str(dataset.metadata.get("candidate_status") or "").strip().lower()

    def dataset_candidate_status_label(self, dataset: core.Dataset) -> str:
        return dataset_candidate_status_label(self.dataset_candidate_status(dataset))

    def dataset_category_label(self, dataset: core.Dataset) -> str:
        values = [*dataset.categories]
        if dataset.data_type and dataset.data_type not in values:
            values.append(dataset.data_type)
        if dataset.native_format and dataset.native_format not in values:
            values.append(dataset.native_format)
        return ", ".join(values)

    def dataset_download_label(self, dataset: core.Dataset) -> str:
        options = core.version_options_for_dataset(dataset)
        option = options[0] if options else None
        if option and option.download_url and core.looks_like_direct_download(option.download_url):
            return self.tr("直接下載", "Direct")
        if option and option.download_url:
            return self.tr("需轉接器", "Needs adapter")
        return self.tr("metadata", "metadata")
