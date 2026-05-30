import unittest

from api_launcher.models import ProviderCatalogEntry
from frontends.tk.provider_models import ProviderRow, provider_local_status_label, provider_update_status_label


class ProviderRowTests(unittest.TestCase):
    def test_provider_row_keeps_catalog_fields_and_download_label(self) -> None:
        # ProviderRow 只做 Tk 顯示模型轉換；catalog 欄位與下載資格仍由 core/shared policy 決定。
        row = ProviderRow(
            ProviderCatalogEntry(
                provider_id="example_provider",
                name="Example",
                owner="Example Org",
                categories=("science", "ocean"),
                geographic_scope="global",
                docs_url="https://example.test/docs",
                api_base_url="https://example.test/data.csv",
                signup_url="",
                auth_type="api_key",
                key_env_var="EXAMPLE_KEY",
                notes="demo",
                latest_status=None,
                latest_fetched_at="",
                latest_error="",
                remote_status="unchecked",
                local_status="not_imported",
                update_status="unknown",
                last_downloaded_at="",
                dataset_path="",
                install_id="",
                install_fingerprint="",
                is_starred=True,
            )
        )

        self.assertEqual("Example", row.name)
        self.assertEqual("science, ocean", row.category_label)
        self.assertEqual("★", row.star_label)
        self.assertEqual("未檢查", row.status_label)
        self.assertEqual("未納管", row.local_label)
        self.assertEqual("Direct+Key", row.download_label)
        self.assertEqual("example_provider", row.as_provider().provider_id)

    def test_provider_status_labels_hide_unknown_backend_tokens(self) -> None:
        self.assertEqual("有更新", provider_update_status_label("remote_updated"))
        self.assertEqual("更新狀態待確認", provider_update_status_label("new_backend_status"))
        self.assertEqual("未納管", provider_local_status_label("not_imported"))
        self.assertEqual("本地狀態待確認", provider_local_status_label("new_local_status"))

    def test_provider_row_status_fallbacks_hide_unknown_backend_tokens(self) -> None:
        row = ProviderRow(
            ProviderCatalogEntry(
                provider_id="example_provider",
                name="Example",
                owner="Example Org",
                categories=(),
                geographic_scope="global",
                docs_url="",
                api_base_url="",
                signup_url="",
                auth_type="none",
                key_env_var="",
                notes="",
                latest_status=None,
                latest_fetched_at="",
                latest_error="",
                remote_status="unchecked",
                local_status="new_local_status",
                update_status="new_backend_status",
                last_downloaded_at="",
                dataset_path="",
                install_id="",
                install_fingerprint="",
                is_starred=False,
            )
        )

        self.assertEqual("更新狀態待確認", row.update_label)
        self.assertEqual("本地狀態待確認", row.local_label)
