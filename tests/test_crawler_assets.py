from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from api_launcher.crawler_asset_service import (
    CrawlerAssetDownloadPlanResult,
    CrawlerAssetListingResult,
    build_crawler_asset_download_plan,
    run_crawler_asset_listing,
)
from api_launcher.crawler_asset_listing_payloads import crawler_asset_listing_event_context, crawler_remote_pagination_payload
from api_launcher.crawler_asset_payloads import source_download_options_from_crawler_asset_payload
from api_launcher.crawler_asset_profiles import (
    CrawlerAssetProfile,
    compact_crawler_asset_plan_passport,
    crawler_asset_bounds_signature,
    crawler_asset_plan_passport_for_profile,
    crawler_asset_profile_for,
    crawler_asset_source_signature,
    load_crawler_asset_profiles,
    set_crawler_asset_archived,
    set_crawler_asset_seed_favorite,
    toggle_crawler_asset_archived,
    update_crawler_asset_plan_passport,
    update_crawler_asset_profile,
)
from api_launcher.crawler_asset_bound_forms import (
    apply_schema_probe_to_crawler_asset_bound_form_spec,
    build_crawler_asset_bound_form_spec,
    crawler_asset_bound_form_profile,
    crawler_asset_bound_payload_from_form_values,
)
from api_launcher.crawler_asset_bounds import SOURCE_BOUND_FACETS, bounds_facets_for_source, bounds_schema_for_source
from api_launcher.crawler_seed_display import seed_enumeration_display_payload
from api_launcher.crawler_assets import (
    BUILD_DOWNLOAD_PLAN,
    SOURCE_SURFACE_LABELS,
    crawler_asset_from_source,
    load_crawler_asset_source,
    load_crawler_assets,
    status_label,
)
from api_launcher.crawlers.source_type_registry import source_uses_file_index
from api_launcher.crawlers.orchestrator import DatasetCrawlOptions, DatasetCrawlResult, DatasetSourceCrawlResult
from api_launcher.crawlers.dataset_sources import SUPPORTED_DATASET_SOURCE_TYPES
from api_launcher.crawlers.types import DatasetCandidate, DatasetDiscoverySource
from api_launcher.db import connect_db
from api_launcher.models import Dataset, Provider
from api_launcher.repository import ApiCatalogRepository
from api_launcher.schema_probe import SchemaProbeColumn, SchemaProbeResult


class CrawlerAssetTest(unittest.TestCase):
    @staticmethod
    def _plan_build_stub(
        *,
        direct_download_count: int,
        candidate_count: int,
        review_required_count: int,
        payload_kind: str,
    ) -> SimpleNamespace:
        def to_dict() -> dict[str, object]:
            return {"kind": payload_kind}

        return SimpleNamespace(
            direct_download_count=direct_download_count,
            candidate_count=candidate_count,
            resolved_plan={"summary": {"review_required_count": review_required_count}},
            candidate_snapshot_signature="snapshot-a",
            candidate_snapshot_count=candidate_count,
            to_dict=to_dict,
        )

    def test_supported_source_exposes_three_capability_slots(self) -> None:
        source = DatasetDiscoverySource(
            source_id="demo_ckan",
            provider_id="demo_provider",
            name="Demo CKAN",
            source_type="ckan_package_search",
            endpoint_url="https://example.test/api/3/action/package_search",
            search_terms=("ocean",),
            categories=("catalog",),
        )

        asset = crawler_asset_from_source(source)

        self.assertEqual("demo_ckan", asset.asset_id)
        self.assertEqual("bounded", asset.maturity)
        self.assertEqual(("fetch_metadata", "list_datasets", BUILD_DOWNLOAD_PLAN), tuple(item.capability_id for item in asset.capabilities))
        self.assertEqual("ready", asset.capability_status("fetch_metadata"))
        self.assertEqual("bounded", asset.capability_status("list_datasets"))
        self.assertEqual("needs_bounds_or_adapter", asset.capability_status(BUILD_DOWNLOAD_PLAN))
        self.assertEqual("needs_bounds_or_adapter", asset.capability_status("download_selected"))
        self.assertEqual(("package", "resource", "format", "limit"), asset.capabilities[2].bounds_facets)
        self.assertEqual(("package", "resource", "format", "limit"), tuple(facet.facet_id for facet in asset.capabilities[2].bounds_schema))
        self.assertEqual("LimitBounds", asset.capabilities[2].bounds_schema[-1].group)
        self.assertEqual("public_or_review", asset.capabilities[2].credential_mode)
        self.assertIn("adapter_required", asset.capabilities[2].error_buckets)
        self.assertEqual(1, asset.seed_count)
        self.assertEqual("1 configured", asset.seed_summary)
        self.assertEqual("public_or_review", asset.access_requirement)
        self.assertGreaterEqual(asset.trust_score, 50)
        self.assertEqual("catalog_search", asset.capability_profile.source_family)
        self.assertEqual("json", asset.capability_profile.transport)
        self.assertEqual("dataset_list", asset.capability_profile.result_shape)
        self.assertEqual("paginated_catalog", asset.capability_profile.seed_scope)
        self.assertTrue(asset.capability_profile.supports_full_crawl)
        capability_code = asset.capability_profile.capability_code
        self.assertIsNotNone(capability_code)
        self.assertEqual(0b0000, capability_code.bits)
        self.assertEqual("0000", capability_code.binary)
        self.assertEqual("offset", asset.capability_profile.pagination_mode)
        self.assertEqual(("csv", "json", "zip", "excel", "pdf", "unknown"), asset.capability_profile.content_formats)
        self.assertEqual(("package", "resource", "format", "limit"), asset.capability_profile.bound_facets)
        self.assertIn("bounded_fetch", asset.capability_profile.middleware)
        self.assertIn("pagination_driver", asset.capability_profile.middleware)
        self.assertEqual("review_source_profile", asset.capability_profile.failure_policy["missing_credentials"])

        payload = asset.to_dict()["capability_profile"]
        self.assertEqual("ckan_package_search", payload["source_type"])
        self.assertEqual("catalog_search", payload["source_family"])
        self.assertEqual("json", payload["transport"])
        self.assertEqual("dataset_list", payload["result_shape"])
        self.assertEqual("paginated_catalog", payload["seed_scope"])
        self.assertTrue(payload["supports_full_crawl"])
        self.assertEqual({"bits": 0, "binary": "0000", "width": 4}, payload["capability_code"])
        self.assertEqual(0b0000, payload["capability_bits"])
        self.assertEqual("0000", payload["capability_binary"])
        self.assertEqual("offset", payload["pagination_mode"])
        self.assertEqual("public_or_review", payload["request_policy"]["credential_mode"])

    def test_file_index_source_can_offer_selectable_download(self) -> None:
        source = DatasetDiscoverySource(
            source_id="demo_index",
            provider_id="demo_provider",
            name="Demo Index",
            source_type="html_file_index",
            endpoint_url="https://example.test/files/index.html",
            file_url_regex=r"demo-(?P<version>\d{4})\.csv$",
        )

        asset = crawler_asset_from_source(source)

        self.assertEqual("selectable", asset.capability_status(BUILD_DOWNLOAD_PLAN))
        self.assertTrue(source_uses_file_index(source))
        self.assertIn("下載計畫:可選", asset.capability_summary)
        self.assertEqual(("version", "version_limit", "file_pattern", "limit"), asset.capabilities[2].bounds_facets)
        self.assertEqual("DatasetDiscoverySource.file_url_regex", asset.capabilities[2].bounds_schema[2].maps_to[0])
        self.assertEqual("full entry", asset.seed_summary)
        self.assertEqual("file_index", asset.source_surface)
        self.assertEqual("completed", asset.health.status_gate)

    def test_wms_source_surface_is_map_service_for_ui_cards(self) -> None:
        source = DatasetDiscoverySource(
            source_id="demo_wms",
            provider_id="demo_provider",
            name="Demo WMS",
            source_type="ogc_wms_capabilities",
            endpoint_url="https://example.test/wms?service=WMS&request=GetCapabilities",
        )

        asset = crawler_asset_from_source(source)

        self.assertEqual("map_service", asset.source_surface)

    def test_unsupported_source_is_visible_but_marked_as_handler_backlog(self) -> None:
        source = DatasetDiscoverySource(
            source_id="demo_unknown",
            provider_id="demo_provider",
            name="Demo Unknown",
            source_type="unknown_portal",
            endpoint_url="https://example.test/",
        )

        asset = crawler_asset_from_source(source)

        self.assertEqual("unbuilt", asset.maturity)
        self.assertEqual("needs_handler", asset.risk_tier)
        self.assertEqual("needs_handler", asset.capability_status("fetch_metadata"))
        self.assertEqual("adapter_review", asset.health.status_gate)
        self.assertEqual("待補", status_label("needs_handler"))
        self.assertIsNone(asset.capability_profile.capability_code)

        payload = asset.to_dict()["capability_profile"]
        self.assertEqual({}, payload["capability_code"])
        self.assertIsNone(payload["capability_bits"])
        self.assertEqual("", payload["capability_binary"])

    def test_account_requirement_is_assigned_to_crawler_asset(self) -> None:
        source = DatasetDiscoverySource(
            source_id="earthdata_guarded",
            provider_id="nasa_earthdata",
            name="Earthdata guarded source",
            source_type="cmr_collections",
            endpoint_url="https://cmr.earthdata.nasa.gov/search/collections.json",
            notes="Downloads may require Earthdata account login.",
        )

        asset = crawler_asset_from_source(source)

        self.assertEqual("crawler_managed_auth", asset.access_requirement)
        self.assertEqual("user_credential_required", asset.capabilities[0].credential_mode)
        self.assertEqual("auth_profile", asset.capabilities[2].bounds_schema[-1].facet_id)
        self.assertEqual("AuthBounds", asset.capabilities[2].bounds_schema[-1].group)
        self.assertEqual("user_credential_required", asset.capability_profile.auth_mode)
        self.assertIn("credential_guard", asset.capability_profile.middleware)
        self.assertEqual("open_credential_editor", asset.capability_profile.failure_policy["missing_credentials"])

    def test_source_profile_can_explicitly_declare_access_policy(self) -> None:
        source = DatasetDiscoverySource(
            source_id="guarded_source",
            provider_id="public_name_does_not_hint_auth",
            name="Guarded Source",
            source_type="ckan_package_search",
            endpoint_url="https://example.test/api/3/action/package_search",
            credential_mode="user_credential_required",
            terms_risk="terms_review_required",
        )

        asset = crawler_asset_from_source(source)

        self.assertEqual("crawler_managed_auth", asset.access_requirement)
        self.assertEqual("user_credential_required", asset.capabilities[0].credential_mode)
        self.assertEqual("terms_review_required", asset.capabilities[0].terms_risk)
        self.assertEqual("auth_profile", asset.capabilities[2].bounds_schema[-1].facet_id)

    def test_unknown_source_access_policy_values_do_not_leak_to_ui_contract(self) -> None:
        source = DatasetDiscoverySource(
            source_id="plain_public_source",
            provider_id="plain_provider",
            name="Plain Public Source",
            source_type="ckan_package_search",
            endpoint_url="https://example.test/api/3/action/package_search",
            credential_mode="raw-secret",
            terms_risk="maybe",
        )

        asset = crawler_asset_from_source(source)

        self.assertEqual("public_or_review", asset.capabilities[0].credential_mode)
        self.assertEqual("public_or_review", asset.capabilities[0].terms_risk)

    def test_source_type_drives_dynamic_bounds_facets(self) -> None:
        source = DatasetDiscoverySource(
            source_id="demo_stac",
            provider_id="demo_provider",
            name="Demo STAC",
            source_type="stac_collections",
            endpoint_url="https://example.test/stac",
        )

        self.assertEqual(("collection", "time", "bbox", "asset_role", "limit"), bounds_facets_for_source(source))
        schema = bounds_schema_for_source(source)
        self.assertEqual(("collection", "time", "bbox", "asset_role", "limit"), tuple(facet.facet_id for facet in schema))
        self.assertEqual(("SourceDownloadBounds.time_field", "SourceDownloadBounds.start_date", "SourceDownloadBounds.end_date"), schema[1].maps_to)
        self.assertEqual("SpatialBounds", schema[2].group)
        self.assertTrue(schema[2].requires_schema_probe)

    def test_source_bounds_facet_registry_tracks_supported_crawlers(self) -> None:
        self.assertEqual(set(SOURCE_BOUND_FACETS), set(SUPPORTED_DATASET_SOURCE_TYPES))
        self.assertIn("ogc_wms_capabilities", SOURCE_BOUND_FACETS)
        for source_type, facets in SOURCE_BOUND_FACETS.items():
            self.assertEqual(len(facets), len(set(facets)), source_type)

        source = DatasetDiscoverySource(
            source_id="demo_wms",
            provider_id="demo_provider",
            name="Demo WMS",
            source_type="ogc_wms_capabilities",
            endpoint_url="https://example.test/wms?service=WMS&request=GetCapabilities",
        )

        self.assertEqual(("collection", "bbox", "time", "format", "limit"), bounds_facets_for_source(source))

    def test_source_surface_registry_tracks_supported_crawlers(self) -> None:
        self.assertEqual(set(SOURCE_SURFACE_LABELS), set(SUPPORTED_DATASET_SOURCE_TYPES))

    def test_capability_to_dict_includes_bounds_schema_for_frontends(self) -> None:
        source = DatasetDiscoverySource(
            source_id="demo_erddap",
            provider_id="demo_provider",
            name="Demo ERDDAP",
            source_type="erddap_all_datasets",
            endpoint_url="https://example.test/erddap/info/index.json",
        )

        asset = crawler_asset_from_source(source)
        payload = asset.capabilities[2].to_dict()

        self.assertIn("bounds_schema", payload)
        self.assertEqual("columns", payload["bounds_schema"][1]["facet_id"])
        self.assertEqual("ColumnBounds", payload["bounds_schema"][1]["group"])

    def test_bounds_schema_builds_frontend_neutral_form_and_payload(self) -> None:
        source = DatasetDiscoverySource(
            source_id="demo_stac",
            provider_id="demo_provider",
            name="Demo STAC",
            source_type="stac_collections",
            endpoint_url="https://example.test/stac",
        )
        asset = crawler_asset_from_source(source)
        form_spec = build_crawler_asset_bound_form_spec(asset.asset_id, asset.capabilities[2].bounds_schema)

        self.assertEqual("ready", form_spec.status)
        self.assertIn("TimeBounds", form_spec.groups)
        self.assertIn("SpatialBounds", form_spec.groups)
        self.assertTrue(any(field.field_id == "start_date" for field in form_spec.fields))
        self.assertTrue(any(field.field_id == "bbox_west" for field in form_spec.fields))
        self.assertIn("schema_probe_recommended", form_spec.warning_codes)

        payload = crawler_asset_bound_payload_from_form_values(
            form_spec,
            {
                "collection": "landsat-c2",
                "time_field": "datetime",
                "start_date": "2026-01-01",
                "end_date": "2026-01-31",
                "bbox_west": "120",
                "bbox_south": "22",
                "bbox_east": "122",
                "bbox_north": "25",
                "asset_role": "data",
                "limit": "10",
            },
        )

        self.assertEqual("demo_stac", payload.asset_id)
        self.assertEqual((120.0, 22.0, 122.0, 25.0), payload.facet_values["bbox"])
        self.assertEqual("2026-01-01", payload.facet_values["time"]["start_date"])
        self.assertEqual(10, payload.facet_values["limit"])
        self.assertEqual((120.0, 22.0, 122.0, 25.0), payload.maps_to_values["SourceDownloadBounds.bbox"])

    def test_bounds_form_spec_exposes_safe_recommendations_and_region_presets(self) -> None:
        source = DatasetDiscoverySource(
            source_id="demo_stac",
            provider_id="demo_provider",
            name="Demo Taiwan STAC",
            source_type="stac_collections",
            endpoint_url="https://example.test/stac",
            search_terms=("landsat",),
            categories=("geospatial",),
            geographic_scope="taiwan",
            max_results=80,
        )
        asset = crawler_asset_from_source(source)
        form_spec = build_crawler_asset_bound_form_spec(
            asset.asset_id,
            asset.capabilities[2].bounds_schema,
            source=source,
        )

        self.assertEqual(25, form_spec.recommended_values["limit"])
        self.assertIn("preset_available", form_spec.warning_codes)
        preset_payloads = [preset.to_dict() for preset in form_spec.presets]
        preset_ids = [preset["preset_id"] for preset in preset_payloads]
        self.assertEqual("taiwan", preset_ids[0])
        taiwan = preset_payloads[0]
        self.assertEqual({"bbox_west": 119.0, "bbox_south": 21.5, "bbox_east": 123.5, "bbox_north": 25.5}, taiwan["values"])
        self.assertIn("預覽", form_spec.guidance_zh_TW)

    def test_bounds_form_profile_summarizes_dynamic_form_contract(self) -> None:
        source = DatasetDiscoverySource(
            source_id="demo_stac",
            provider_id="demo_provider",
            name="Demo Taiwan STAC",
            source_type="stac_collections",
            endpoint_url="https://example.test/stac",
            geographic_scope="taiwan",
            max_results=80,
        )
        asset = crawler_asset_from_source(source)
        form_spec = build_crawler_asset_bound_form_spec(
            asset.asset_id,
            asset.capabilities[2].bounds_schema,
            source=source,
        )

        profile = crawler_asset_bound_form_profile(form_spec)
        payload = form_spec.to_dict()["form_profile"]

        self.assertEqual("bounds_form_schema_probe_recommended", profile.profile_id)
        self.assertEqual("warning", profile.display_tone)
        self.assertEqual("apply_defaults_or_probe_schema", profile.next_action)
        self.assertEqual(len(form_spec.fields), profile.field_count)
        self.assertIn("time", profile.facet_ids)
        self.assertIn("bbox", profile.facet_ids)
        self.assertIn("TimeBounds", profile.groups)
        self.assertIn("SpatialBounds", profile.groups)
        self.assertIn("time_field", profile.schema_probe_field_ids)
        self.assertIn("taiwan", profile.preset_ids)
        self.assertIn("limit", profile.recommended_value_keys)
        self.assertEqual(profile.to_dict(), payload)

    def test_schema_probe_enriches_bounds_form_column_selectors(self) -> None:
        source = DatasetDiscoverySource(
            source_id="demo_socrata",
            provider_id="demo_provider",
            name="Demo Socrata",
            source_type="socrata_catalog_search",
            endpoint_url="https://data.example.test/api/views.json",
            max_results=40,
        )
        asset = crawler_asset_from_source(source)
        form_spec = build_crawler_asset_bound_form_spec(
            asset.asset_id,
            asset.capabilities[2].bounds_schema,
            source=source,
        )
        probe = SchemaProbeResult(
            status="ok",
            source_url="https://data.example.test/resource/abcd.json",
            columns=(
                SchemaProbeColumn("created_date", "2026-01-01T00:00:00", "datetime"),
                SchemaProbeColumn("borough", "Queens", "text"),
                SchemaProbeColumn("count", "3", "integer"),
            ),
        )

        enriched = apply_schema_probe_to_crawler_asset_bound_form_spec(form_spec, probe)
        fields = {field.field_id: field for field in enriched.fields}
        profile = crawler_asset_bound_form_profile(enriched)

        self.assertEqual("select_or_text", fields["time_field"].control)
        self.assertEqual(("created_date",), fields["time_field"].options)
        self.assertEqual("created_date", fields["time_field"].default)
        self.assertFalse(fields["time_field"].requires_schema_probe)
        self.assertEqual(("created_date", "borough", "count"), fields["columns"].options)
        self.assertFalse(fields["columns"].requires_schema_probe)
        self.assertEqual("created_date", enriched.recommended_values["time_field"])
        self.assertIn("schema_probe_applied", enriched.warning_codes)
        self.assertNotIn("schema_probe_recommended", enriched.warning_codes)
        self.assertEqual(0, enriched.schema_probe_required_count)
        self.assertEqual("bounds_form_ready_with_presets", profile.profile_id)

    def test_failed_schema_probe_keeps_bounds_form_in_review(self) -> None:
        source = DatasetDiscoverySource(
            source_id="demo_socrata",
            provider_id="demo_provider",
            name="Demo Socrata",
            source_type="socrata_catalog_search",
            endpoint_url="https://data.example.test/api/views.json",
        )
        asset = crawler_asset_from_source(source)
        form_spec = build_crawler_asset_bound_form_spec(
            asset.asset_id,
            asset.capabilities[2].bounds_schema,
            source=source,
        )
        probe = SchemaProbeResult(
            status="error",
            source_url="https://data.example.test/resource/abcd.json",
            error="timeout",
        )

        enriched = apply_schema_probe_to_crawler_asset_bound_form_spec(form_spec, probe)

        self.assertIn("schema_probe_failed", enriched.warning_codes)
        self.assertIn("schema_probe_recommended", enriched.warning_codes)
        self.assertEqual(form_spec.schema_probe_required_count, enriched.schema_probe_required_count)

    def test_empty_bounds_form_profile_allows_direct_plan_flow(self) -> None:
        form_spec = build_crawler_asset_bound_form_spec("demo_empty", ())

        profile = crawler_asset_bound_form_profile(form_spec)

        self.assertEqual("bounds_form_empty", profile.profile_id)
        self.assertEqual("empty", profile.status)
        self.assertEqual(0, profile.field_count)
        self.assertEqual("continue_to_download_plan", profile.next_action)
        self.assertEqual("不需界域", profile.display_label)

    def test_bounds_payload_converts_to_source_download_options(self) -> None:
        source = DatasetDiscoverySource(
            source_id="demo_stac",
            provider_id="demo_provider",
            name="Demo STAC",
            source_type="stac_collections",
            endpoint_url="https://example.test/stac",
        )
        asset = crawler_asset_from_source(source)
        form_spec = build_crawler_asset_bound_form_spec(asset.asset_id, asset.capabilities[2].bounds_schema)
        payload = crawler_asset_bound_payload_from_form_values(
            form_spec,
            {
                "collection": "landsat-c2",
                "time_field": "datetime",
                "start_date": "2026-01-01",
                "end_date": "2026-01-31",
                "bbox_west": "120",
                "bbox_south": "22",
                "bbox_east": "122",
                "bbox_north": "25",
                "limit": "10",
            },
        )

        options = source_download_options_from_crawler_asset_payload(payload, max_results=50, full_crawl=False)

        self.assertEqual(10, options.bounds.sample_limit)
        self.assertEqual("datetime", options.bounds.time_field)
        self.assertEqual("2026-01-31", options.bounds.end_date)
        self.assertEqual((120.0, 22.0, 122.0, 25.0), options.bounds.bbox)
        self.assertEqual(("landsat-c2",), options.search_terms_override)
        self.assertEqual(50, options.max_results_override)

    def test_blank_version_keeps_limit_without_selecting_fake_version(self) -> None:
        source = DatasetDiscoverySource(
            source_id="demo_index",
            provider_id="demo_provider",
            name="Demo Index",
            source_type="html_file_index",
            endpoint_url="https://example.test/files/index.html",
            file_url_regex=r"demo-(?P<version>\d{4})\.csv$",
        )
        asset = crawler_asset_from_source(source)
        form_spec = build_crawler_asset_bound_form_spec(asset.asset_id, asset.capabilities[2].bounds_schema)

        payload = crawler_asset_bound_payload_from_form_values(form_spec, {})
        options = source_download_options_from_crawler_asset_payload(payload)

        self.assertEqual(1, options.bounds.version_limit)
        self.assertEqual({}, options.selected_versions)
        self.assertNotIn("SourceDownloadOptions.selected_versions", payload.maps_to_values)

    def test_load_crawler_asset_source_finds_single_entry(self) -> None:
        with TemporaryDirectory() as tmp:
            source_path = Path(tmp) / "sources.json"
            source_path.write_text(
                """
{
  "schema_version": 1,
  "sources": [
    {
      "source_id": "demo_index",
      "provider_id": "demo_provider",
      "name": "Demo Index",
      "source_type": "html_file_index",
      "endpoint_url": "https://example.test/index.html"
    }
  ]
}
""".strip(),
                encoding="utf-8",
            )

            source = load_crawler_asset_source("demo_index", source_path, None)

        self.assertIsNotNone(source)
        assert source is not None
        self.assertEqual("html_file_index", source.source_type)

    def test_local_profile_can_archive_and_reenable_asset(self) -> None:
        with TemporaryDirectory() as tmp:
            profile_path = Path(tmp) / "crawler_asset_profiles.local.json"

            archived = set_crawler_asset_archived("demo_index", True, profile_path)
            profiles = load_crawler_asset_profiles(profile_path)
            current = crawler_asset_profile_for("demo_index", profiles)

            self.assertTrue(archived.archived)
            self.assertFalse(archived.enabled)
            self.assertEqual("archived", current.profile_state)

            enabled = toggle_crawler_asset_archived("demo_index", profile_path)

        self.assertFalse(enabled.archived)
        self.assertTrue(enabled.enabled)
        self.assertEqual("active", enabled.profile_state)

    def test_profile_update_keeps_credentials_as_references(self) -> None:
        with TemporaryDirectory() as tmp:
            profile_path = Path(tmp) / "crawler_asset_profiles.local.json"

            updated = update_crawler_asset_profile(
                "demo_index",
                profile_path,
                credential_profile_id="earthdata_default",
                api_key_env_var="NASA_EARTHDATA_TOKEN",
                account_hint="NASA Earthdata account",
                schedule_policy="manual",
                rate_limit_policy="polite_1rps",
                retry_policy="retry_3_with_backoff",
                seed_scope_policy="bounded",
                status_note="needs account review",
                local_logo_path="state/logos/demo.png",
                logo_source="custom",
                logo_license_note="local presentation asset",
            )
            profiles = load_crawler_asset_profiles(profile_path)

            self.assertEqual("NASA_EARTHDATA_TOKEN", updated.api_key_env_var)
            self.assertEqual("earthdata_default", profiles["demo_index"].credential_profile_id)
            self.assertEqual("polite_1rps", profiles["demo_index"].rate_limit_policy)
            self.assertEqual("bounded", profiles["demo_index"].seed_scope_policy)

            with self.assertRaises(ValueError):
                update_crawler_asset_profile("demo_index", profile_path, api_key_env_var="sk-secret")

    def test_profile_persists_seed_level_favorites(self) -> None:
        with TemporaryDirectory() as tmp:
            profile_path = Path(tmp) / "crawler_asset_profiles.local.json"

            favorited = set_crawler_asset_seed_favorite("demo_index", "seed-001", True, profile_path)
            set_crawler_asset_seed_favorite("demo_index", "seed-001", True, profile_path)
            set_crawler_asset_seed_favorite("demo_index", "seed-002", True, profile_path)
            unfavorited = set_crawler_asset_seed_favorite("demo_index", "seed-001", False, profile_path)
            profiles = load_crawler_asset_profiles(profile_path)

        self.assertEqual(("seed-001",), favorited.favorite_seed_uids)
        self.assertEqual(("seed-002",), unfavorited.favorite_seed_uids)
        self.assertEqual(("seed-002",), profiles["demo_index"].favorite_seed_uids)

    def test_profile_plan_passport_keeps_only_compact_status(self) -> None:
        with TemporaryDirectory() as tmp:
            profile_path = Path(tmp) / "crawler_asset_profiles.local.json"

            updated = update_crawler_asset_plan_passport(
                "demo_index",
                {
                    "asset_id": "demo_index",
                    "candidate_count": 5,
                    "candidate_snapshot_signature": "abcdef0123456789",
                    "candidate_snapshot_count": 5,
                    "candidate_snapshot_changed": True,
                    "direct_download_count": 2,
                    "adapter_review_count": 3,
                    "next_action": "open_downloader_and_start_or_pause_queue",
                    "bounds": {
                        "limit": 5,
                        "bbox": [120.0, 22.0, 122.0, 25.0],
                        "unsafe_nested": {"resolved_plan": True},
                    },
                    "providers": [{"provider_id": "too_large"}],
                    "resolved_plan": {"entries": [{"url": "https://example.test/file.csv"}]},
                },
                profile_path,
            )
            profiles = load_crawler_asset_profiles(profile_path)

        passport = updated.latest_plan_passport
        self.assertEqual(5, passport["candidate_count"])
        self.assertEqual("abcdef0123456789", passport["candidate_snapshot_signature"])
        self.assertEqual(5, passport["candidate_snapshot_count"])
        self.assertTrue(passport["candidate_snapshot_changed"])
        self.assertEqual(2, profiles["demo_index"].latest_plan_passport["direct_download_count"])
        self.assertEqual([120.0, 22.0, 122.0, 25.0], passport["bounds"]["bbox"])
        self.assertEqual("demo_index", passport["asset_id"])
        self.assertEqual("active", passport["profile_state"])
        self.assertFalse(passport["stale"])
        self.assertEqual("", passport["stale_reason"])
        self.assertRegex(str(passport["saved_at"]), r"^\d{4}-\d{2}-\d{2}T")
        self.assertNotIn("unsafe_nested", passport["bounds"])
        self.assertNotIn("providers", passport)
        self.assertNotIn("resolved_plan", passport)

    def test_compact_plan_passport_rejects_non_mapping(self) -> None:
        self.assertEqual({}, compact_crawler_asset_plan_passport(["not", "a", "mapping"]))

    def test_loaded_assets_mark_profile_plan_passport_stale_when_asset_disabled(self) -> None:
        with TemporaryDirectory() as tmp:
            source_path = Path(tmp) / "sources.json"
            profile_path = Path(tmp) / "crawler_asset_profiles.local.json"
            source_path.write_text(
                """
{
  "schema_version": 1,
  "sources": [
    {
      "source_id": "demo_index",
      "provider_id": "demo_provider",
      "name": "Demo Index",
      "source_type": "html_file_index",
      "endpoint_url": "https://example.test/index.html"
    }
  ]
}
""".strip(),
                encoding="utf-8",
            )
            update_crawler_asset_plan_passport(
                "demo_index",
                {
                    "asset_id": "demo_index",
                    "has_resolved_plan": True,
                    "candidate_count": 3,
                    "direct_download_count": 1,
                },
                profile_path,
            )
            update_crawler_asset_profile("demo_index", profile_path, enabled=False)

            assets = load_crawler_assets(source_path, None, profile_path)

        passport = assets[0].latest_plan_passport
        self.assertTrue(passport["stale"])
        self.assertEqual("asset_disabled", passport["stale_reason"])
        self.assertEqual("warning", passport["display_tone"])
        self.assertEqual(3, passport["candidate_count"])

    def test_loaded_assets_mark_profile_plan_passport_stale_when_source_changes(self) -> None:
        original_source = DatasetDiscoverySource(
            source_id="demo_index",
            provider_id="demo_provider",
            name="Demo Index",
            source_type="html_file_index",
            endpoint_url="https://example.test/index.html",
            file_url_regex=r"\.csv$",
        )
        with TemporaryDirectory() as tmp:
            source_path = Path(tmp) / "sources.json"
            profile_path = Path(tmp) / "crawler_asset_profiles.local.json"
            source_path.write_text(
                """
{
  "schema_version": 1,
  "sources": [
    {
      "source_id": "demo_index",
      "provider_id": "demo_provider",
      "name": "Demo Index",
      "source_type": "html_file_index",
      "endpoint_url": "https://example.test/files-v2/index.html",
      "file_url_regex": "\\\\.csv$"
    }
  ]
}
""".strip(),
                encoding="utf-8",
            )
            update_crawler_asset_plan_passport(
                "demo_index",
                {
                    "asset_id": "demo_index",
                    "candidate_count": 3,
                    "source_signature": crawler_asset_source_signature(original_source),
                    "bounds_signature": crawler_asset_bounds_signature(bounds_facets_for_source(original_source)),
                },
                profile_path,
            )

            assets = load_crawler_assets(source_path, None, profile_path)

        passport = assets[0].latest_plan_passport
        self.assertTrue(passport["stale"])
        self.assertEqual("source_changed", passport["stale_reason"])
        self.assertEqual("warning", passport["display_tone"])

    def test_profile_plan_passport_marks_stale_when_bounds_schema_changes(self) -> None:
        profile = CrawlerAssetProfile(
            asset_id="demo_index",
            latest_plan_passport={
                "asset_id": "demo_index",
                "candidate_count": 3,
                "source_signature": "same-source",
                "bounds_signature": crawler_asset_bounds_signature(("limit",)),
            },
        )

        passport = crawler_asset_plan_passport_for_profile(
            profile,
            source_signature="same-source",
            bounds_signature=crawler_asset_bounds_signature(("dataset", "limit")),
        )

        self.assertTrue(passport["stale"])
        self.assertEqual("bounds_schema_changed", passport["stale_reason"])
        self.assertEqual("warning", passport["display_tone"])

    def test_loaded_assets_apply_archived_profile_without_changing_source(self) -> None:
        with TemporaryDirectory() as tmp:
            source_path = Path(tmp) / "sources.json"
            profile_path = Path(tmp) / "crawler_asset_profiles.local.json"
            source_path.write_text(
                """
{
  "schema_version": 1,
  "sources": [
    {
      "source_id": "demo_index",
      "provider_id": "demo_provider",
      "name": "Demo Index",
      "source_type": "html_file_index",
      "endpoint_url": "https://example.test/index.html"
    }
  ]
}
""".strip(),
                encoding="utf-8",
            )
            set_crawler_asset_archived("demo_index", True, profile_path)

            assets = load_crawler_assets(source_path, None, profile_path)

        self.assertEqual(1, len(assets))
        self.assertTrue(assets[0].archived)
        self.assertEqual("archived", assets[0].risk_tier)
        self.assertEqual("unarchive_before_crawl", assets[0].next_action)
        self.assertEqual("archived", assets[0].health.status_code)
        self.assertEqual("restricted", assets[0].health.status_gate)
        self.assertEqual("unarchive_before_crawl", assets[0].health.next_action)

    def test_loaded_assets_expose_profile_and_health_for_ui_cards(self) -> None:
        with TemporaryDirectory() as tmp:
            source_path = Path(tmp) / "sources.json"
            profile_path = Path(tmp) / "crawler_asset_profiles.local.json"
            source_path.write_text(
                """
{
  "schema_version": 1,
  "sources": [
    {
      "source_id": "demo_stac",
      "provider_id": "demo_provider",
      "name": "Demo STAC",
      "source_type": "stac_collections",
      "endpoint_url": "https://example.test/stac"
    }
  ]
}
""".strip(),
                encoding="utf-8",
            )
            update_crawler_asset_profile(
                "demo_stac",
                profile_path,
                official_logo_url="https://example.test/logo.png",
                favicon_url="https://example.test/favicon.ico",
                schedule_policy="manual",
                rate_limit_policy="polite_1rps",
            )

            assets = load_crawler_assets(source_path, None, profile_path)

        self.assertEqual(1, len(assets))
        self.assertEqual("https://example.test/logo.png", assets[0].official_logo_url)
        self.assertEqual("manual", assets[0].schedule_policy)
        self.assertEqual("polite_1rps", assets[0].rate_limit_policy)
        self.assertEqual("needs_bounds", assets[0].health.status_code)
        self.assertEqual("review", assets[0].health.status_gate)
        self.assertEqual("probe_schema_then_define_bounds", assets[0].health.next_action)
        self.assertEqual("needs_bounds", assets[0].to_dict()["health"]["status_code"])
        self.assertEqual("review", assets[0].to_dict()["health"]["status_gate"])

    def test_service_blocks_archived_asset_before_crawl(self) -> None:
        with TemporaryDirectory() as tmp:
            source_path = Path(tmp) / "sources.json"
            local_path = Path(tmp) / "local_sources.json"
            profile_path = Path(tmp) / "crawler_asset_profiles.local.json"
            source_path.write_text(
                """
{
  "schema_version": 1,
  "sources": [
    {
      "source_id": "demo_index",
      "provider_id": "demo_provider",
      "name": "Demo Index",
      "source_type": "html_file_index",
      "endpoint_url": "https://example.test/index.html"
    }
  ]
}
""".strip(),
                encoding="utf-8",
            )
            set_crawler_asset_archived("demo_index", True, profile_path)
            conn = connect_db(Path(tmp) / "catalog.sqlite")
            try:
                called = False

                def fake_runner(_sources, _options):
                    nonlocal called
                    called = True
                    raise AssertionError("archived crawler asset should not crawl")

                result = run_crawler_asset_listing(
                    "demo_index",
                    conn,
                    primary_path=source_path,
                    local_path=local_path,
                    profile_path=profile_path,
                    crawl_runner=fake_runner,
                )
            finally:
                conn.close()

        self.assertFalse(called)
        self.assertTrue(result.blocked)
        self.assertEqual("archived", result.blocked_reason)
        self.assertEqual("unarchive_before_crawl", result.next_action)

    def test_service_upserts_candidates_for_single_asset(self) -> None:
        with TemporaryDirectory() as tmp:
            source_path = Path(tmp) / "sources.json"
            local_path = Path(tmp) / "local_sources.json"
            source_path.write_text(
                """
{
  "schema_version": 1,
  "sources": [
    {
      "source_id": "demo_index",
      "provider_id": "demo_provider",
      "name": "Demo Index",
      "source_type": "html_file_index",
      "endpoint_url": "https://example.test/index.html"
    }
  ]
}
""".strip(),
                encoding="utf-8",
            )
            conn = connect_db(Path(tmp) / "catalog.sqlite")
            try:
                repo = ApiCatalogRepository(conn)
                repo.init_schema()
                repo.upsert_provider(
                    Provider(
                        provider_id="demo_provider",
                        name="Demo Provider",
                        owner="Demo",
                        categories=("demo",),
                        geographic_scope="sample",
                        docs_url="https://example.test/docs",
                    )
                )
                candidate = DatasetCandidate(
                    dataset=Dataset(
                        dataset_uid="demo_provider:dataset_a",
                        provider_id="demo_provider",
                        dataset_id="dataset_a",
                        title="Dataset A",
                        categories=("demo",),
                        native_format="csv",
                    ),
                    source_id="demo_index",
                    source_type="html_file_index",
                    source_url="https://example.test/index.html",
                    confidence=0.9,
                    evidence=("unit-test",),
                )

                def fake_runner(sources, options):
                    self.assertEqual(["demo_index"], [source.source_id for source in sources])
                    self.assertIsInstance(options, DatasetCrawlOptions)
                    self.assertTrue(options.full_crawl)
                    self.assertEqual(1000, options.max_results_override)
                    self.assertEqual(("",), options.search_terms_override)
                    return DatasetCrawlResult(
                        candidates=(candidate,),
                        source_results=(
                            DatasetSourceCrawlResult(
                                source_id="demo_index",
                                provider_id="demo_provider",
                                source_type="html_file_index",
                                candidate_count=1,
                                candidates=(candidate,),
                            ),
                        ),
                    )

                result = run_crawler_asset_listing(
                    "demo_index",
                    conn,
                    primary_path=source_path,
                    local_path=local_path,
                    crawl_runner=fake_runner,
                )
                datasets = repo.list_datasets("demo_provider")
            finally:
                conn.close()

        self.assertFalse(result.blocked)
        self.assertEqual(1, result.candidate_count)
        self.assertEqual(1, result.upserted_count)
        self.assertEqual(0, result.skipped_provider_count)
        self.assertEqual("within_current_limits", result.to_dict()["seed_enumeration"]["status"])
        self.assertFalse(result.to_dict()["seed_enumeration"]["limited_by_max_results"])
        self.assertEqual("not_reported", result.to_dict()["seed_enumeration"]["remote_pagination"]["status"])
        self.assertEqual(1, len(datasets))
        self.assertEqual("Dataset A", datasets[0].title)
        self.assertEqual("demo_index", datasets[0].metadata["discovery_source_id"])

    def test_listing_result_marks_seed_enumeration_local_limit(self) -> None:
        result = CrawlerAssetListingResult(
            asset_id="demo_index",
            source_found=True,
            listing_mode="complete_seed",
            candidate_count=1000,
            upserted_count=1000,
            max_results=1000,
            complete_seed=True,
            next_action="review_or_upsert_dataset_candidates",
        )

        payload = result.to_dict()["seed_enumeration"]

        self.assertEqual("local_limit_reached", payload["status"])
        self.assertTrue(payload["limited_by_max_results"])
        self.assertEqual("narrow_bounds_or_raise_seed_limit", payload["next_action"])
        self.assertEqual("not_reported", payload["remote_pagination"]["status"])
        self.assertIsNone(payload["remote_pagination"]["exhausted"])
        self.assertFalse(payload["remote_pagination"]["next_page_token_present"])
        self.assertEqual("local_limit_only", payload["completion_confidence"])

    def test_seed_enumeration_display_payload_keeps_labels_out_of_service_logic(self) -> None:
        payload = seed_enumeration_display_payload(
            "local_limit_reached",
            candidate_count=50,
            max_results=50,
            remote_pagination={"status": "has_more", "exhausted": False},
        )

        self.assertEqual("local_limit_reached", payload["status"])
        self.assertEqual("warning", payload["display_tone"])
        self.assertEqual("已枚舉前 50 筆 seed", payload["label"])
        self.assertEqual("narrow_bounds_or_raise_seed_limit", payload["next_action"])
        self.assertTrue(payload["limited_by_max_results"])
        self.assertEqual("local_limit_only", payload["completion_confidence"])

    def test_service_carries_source_remote_pagination_into_listing_payload(self) -> None:
        with TemporaryDirectory() as tmp:
            source_path = Path(tmp) / "sources.json"
            local_path = Path(tmp) / "local_sources.json"
            source_path.write_text(
                """
{
  "schema_version": 1,
  "sources": [
    {
      "source_id": "demo_index",
      "provider_id": "demo_provider",
      "name": "Demo Index",
      "source_type": "html_file_index",
      "endpoint_url": "https://example.test/index.html"
    }
  ]
}
""".strip(),
                encoding="utf-8",
            )
            conn = connect_db(Path(tmp) / "catalog.sqlite")
            try:
                repo = ApiCatalogRepository(conn)
                repo.init_schema()
                repo.upsert_provider(
                    Provider(
                        provider_id="demo_provider",
                        name="Demo Provider",
                        owner="Demo",
                        categories=("demo",),
                        geographic_scope="sample",
                        docs_url="https://example.test/docs",
                    )
                )
                candidate = DatasetCandidate(
                    dataset=Dataset(
                        dataset_uid="demo_provider:dataset_a",
                        provider_id="demo_provider",
                        dataset_id="dataset_a",
                        title="Dataset A",
                        categories=("demo",),
                        native_format="csv",
                    ),
                    source_id="demo_index",
                    source_type="html_file_index",
                    source_url="https://example.test/index.html",
                    confidence=0.9,
                    evidence=("unit-test",),
                )

                def fake_runner(_sources, _options):
                    return DatasetCrawlResult(
                        candidates=(candidate,),
                        source_results=(
                            DatasetSourceCrawlResult(
                                source_id="demo_index",
                                provider_id="demo_provider",
                                source_type="html_file_index",
                                candidate_count=1,
                                candidates=(candidate,),
                                remote_pagination_status="has_more",
                                remote_exhausted=False,
                                remote_next_page_token="cursor-2",
                            ),
                        ),
                    )

                result = run_crawler_asset_listing(
                    "demo_index",
                    conn,
                    primary_path=source_path,
                    local_path=local_path,
                    crawl_runner=fake_runner,
                )
            finally:
                conn.close()

        payload = result.to_dict()["seed_enumeration"]

        self.assertEqual("has_more", payload["remote_pagination"]["status"])
        self.assertFalse(payload["remote_pagination"]["exhausted"])
        self.assertTrue(payload["remote_pagination"]["next_page_token_present"])
        self.assertEqual("remote_has_more", payload["completion_confidence"])
        self.assertNotIn("cursor-2", repr(payload))

    def test_listing_result_honors_remote_exhausted_status(self) -> None:
        result = CrawlerAssetListingResult(
            asset_id="demo_index",
            source_found=True,
            listing_mode="complete_seed",
            candidate_count=1000,
            upserted_count=1000,
            max_results=1000,
            complete_seed=True,
            remote_exhausted=True,
            next_action="review_or_upsert_dataset_candidates",
        )

        payload = result.to_dict()["seed_enumeration"]
        context = crawler_asset_listing_event_context(result)

        self.assertEqual("within_current_limits", payload["status"])
        self.assertFalse(payload["limited_by_max_results"])
        self.assertEqual("exhausted", payload["remote_pagination"]["status"])
        self.assertTrue(payload["remote_pagination"]["exhausted"])
        self.assertEqual("remote_reported_exhausted", payload["completion_confidence"])
        self.assertEqual("exhausted", context["remote_pagination"]["status"])

    def test_remote_pagination_payload_reports_token_presence_without_token(self) -> None:
        result = CrawlerAssetListingResult(
            asset_id="demo_index",
            source_found=True,
            remote_exhausted=False,
            remote_next_page_token="secret-token",
        )

        payload = crawler_remote_pagination_payload(result)

        self.assertEqual("has_more", payload["status"])
        self.assertFalse(payload["exhausted"])
        self.assertTrue(payload["next_page_token_present"])
        self.assertNotIn("secret-token", repr(payload))

    def test_download_plan_result_routes_review_required_bucket(self) -> None:
        plan_build = self._plan_build_stub(
            direct_download_count=0,
            candidate_count=2,
            review_required_count=2,
            payload_kind="review_plan",
        )
        result = CrawlerAssetDownloadPlanResult(
            asset_id="demo_index",
            source_found=True,
            plan_build=plan_build,
            next_action="adapter_review_required",
        )

        self.assertEqual("review_required", result.outcome_bucket)
        self.assertEqual("open_adapter_review_or_adjust_bounds", result.user_next_action)
        self.assertEqual("review_required", result.to_dict()["outcome_bucket"])

    def test_download_plan_result_routes_partial_review_bucket(self) -> None:
        plan_build = self._plan_build_stub(
            direct_download_count=1,
            candidate_count=3,
            review_required_count=2,
            payload_kind="mixed_plan",
        )
        result = CrawlerAssetDownloadPlanResult(
            asset_id="demo_index",
            source_found=True,
            plan_build=plan_build,
            next_action="adapter_review_required",
        )

        self.assertEqual("partial_review_required", result.outcome_bucket)
        self.assertEqual("open_downloader_and_start_or_pause_queue", result.user_next_action)
        payload = result.to_dict()
        self.assertEqual("partial_review_required", payload["outcome_bucket"])
        self.assertEqual("mixed_plan", payload["plan_build"]["kind"])

    def test_download_plan_result_routes_zero_candidates_bucket(self) -> None:
        plan_build = self._plan_build_stub(
            direct_download_count=0,
            candidate_count=0,
            review_required_count=0,
            payload_kind="empty_candidates",
        )
        result = CrawlerAssetDownloadPlanResult(
            asset_id="demo_index",
            source_found=True,
            plan_build=plan_build,
            next_action="inspect_crawler_audit",
        )

        self.assertEqual("zero_candidates", result.outcome_bucket)
        self.assertEqual("adjust_bounds_or_refresh_source_listing", result.user_next_action)
        payload = result.to_dict()
        self.assertEqual("zero_candidates", payload["outcome_bucket"])
        self.assertEqual("adjust_bounds_or_refresh_source_listing", payload["user_next_action"])
        self.assertEqual("download_plan_build", payload["run_record"]["stage"])
        self.assertEqual("review", payload["run_record"]["status"])
        self.assertEqual("zero_candidates", payload["run_record"]["outcome_bucket"])
        self.assertEqual("structured_event_log", payload["run_record"]["storage_lane"])
        self.assertEqual("crawler_run_registry", payload["run_record"]["future_sqlite_table"])
        self.assertRegex(str(payload["run_record"]["record_key"]), r"^[0-9a-f]{16}$")

    def test_download_plan_result_routes_blocked_bucket(self) -> None:
        result = CrawlerAssetDownloadPlanResult(
            asset_id="",
            source_found=False,
            blocked_reason="missing_asset_id",
            next_action="select_crawler_asset",
        )

        self.assertTrue(result.blocked)
        self.assertEqual("blocked", result.outcome_bucket)
        self.assertEqual("select_crawler_asset", result.user_next_action)
        payload = result.to_dict()
        self.assertTrue(payload["blocked"])
        self.assertEqual("missing_asset_id", payload["blocked_reason"])
        self.assertEqual({}, payload["plan_build"])
        self.assertEqual("download_plan_build", payload["run_record"]["stage"])
        self.assertEqual("blocked", payload["run_record"]["status"])

    def test_listing_result_includes_run_registry_handoff_payload(self) -> None:
        result = CrawlerAssetListingResult(
            asset_id="demo_index",
            source_found=True,
            candidate_count=3,
            upserted_count=2,
            duplicate_count=1,
            warning_count=1,
            next_action="review_candidates",
            audit_summary={"status": "warning"},
        )

        payload = result.to_dict()

        self.assertEqual("crawler_listing", payload["run_record"]["stage"])
        self.assertEqual("warning", payload["run_record"]["status"])
        self.assertEqual(3, payload["run_record"]["candidate_count"])
        self.assertEqual(1, payload["run_record"]["duplicate_count"])
        self.assertEqual("structured_event_log", payload["run_record"]["storage_lane"])
        self.assertEqual("crawler_run_registry", payload["run_record"]["future_sqlite_table"])
        self.assertRegex(str(payload["run_record"]["record_key"]), r"^[0-9a-f]{16}$")

    def test_service_builds_download_plan_from_asset_bounds(self) -> None:
        with TemporaryDirectory() as tmp:
            source_path = Path(tmp) / "sources.json"
            local_path = Path(tmp) / "local_sources.json"
            profile_path = Path(tmp) / "crawler_asset_profiles.local.json"
            source_path.write_text(
                """
{
  "schema_version": 1,
  "sources": [
    {
      "source_id": "demo_index",
      "provider_id": "demo_provider",
      "name": "Demo Index",
      "source_type": "html_file_index",
      "endpoint_url": "https://example.test/index.html"
    }
  ]
}
""".strip(),
                encoding="utf-8",
            )
            update_crawler_asset_plan_passport(
                "demo_index",
                {
                    "asset_id": "demo_index",
                    "candidate_snapshot_signature": "oldcandidate0001",
                    "candidate_snapshot_count": 1,
                },
                profile_path,
            )
            conn = connect_db(Path(tmp) / "catalog.sqlite")
            try:
                repo = ApiCatalogRepository(conn)
                repo.init_schema()
                repo.upsert_provider(
                    Provider(
                        provider_id="demo_provider",
                        name="Demo Provider",
                        owner="Demo",
                        categories=("demo",),
                        geographic_scope="sample",
                        docs_url="https://example.test/docs",
                        auth_type="none",
                    )
                )
                source = load_crawler_asset_source("demo_index", source_path, local_path)
                self.assertIsNotNone(source)
                assert source is not None
                asset = crawler_asset_from_source(source)
                spec = build_crawler_asset_bound_form_spec(asset.asset_id, asset.capabilities[2].bounds_schema)
                bounds_payload = crawler_asset_bound_payload_from_form_values(spec, {"limit": "7"})
                candidate = DatasetCandidate(
                    dataset=Dataset(
                        dataset_uid="demo_provider:dataset_a",
                        provider_id="demo_provider",
                        dataset_id="dataset_a",
                        title="Dataset A",
                        categories=("demo",),
                        native_format="csv",
                        api_url="https://example.test/data.csv",
                        metadata={"download_url": "https://example.test/data.csv"},
                    ),
                    source_id="demo_index",
                    source_type="html_file_index",
                    source_url="https://example.test/index.html",
                    confidence=0.9,
                    evidence=("unit-test",),
                )

                def fake_runner(_sources, _options):
                    return DatasetCrawlResult(
                        candidates=(candidate,),
                        source_results=(
                            DatasetSourceCrawlResult(
                                source_id="demo_index",
                                provider_id="demo_provider",
                                source_type="html_file_index",
                                candidate_count=1,
                                candidates=(candidate,),
                            ),
                        ),
                    )

                from unittest.mock import patch

                with patch("api_launcher.source_download.crawl_dataset_sources", fake_runner):
                    result = build_crawler_asset_download_plan(
                        "demo_index",
                        conn,
                        bounds_payload=bounds_payload,
                        downloads_root=Path(tmp) / "downloads",
                        primary_path=source_path,
                        local_path=local_path,
                        profile_path=profile_path,
                    )
            finally:
                conn.close()

        self.assertFalse(result.blocked)
        self.assertTrue(result.candidate_snapshot_changed)
        self.assertEqual("oldcandidate0001", result.previous_candidate_snapshot_signature)
        self.assertRegex(result.plan_build.candidate_snapshot_signature, r"^[0-9a-f]{16}$")
        self.assertTrue(result.to_dict()["candidate_snapshot_changed"])
        self.assertEqual("ready_to_download", result.outcome_bucket)
        self.assertEqual("open_downloader_and_start_or_pause_queue", result.user_next_action)
        self.assertEqual(1, result.direct_download_count)
        self.assertEqual(7, result.bounds.sample_limit)
        self.assertEqual("source_discovery_download_plan", result.original_plan["plan_name"])
        entry = result.resolved_plan["providers"][0]
        self.assertEqual("direct_download", entry["download_eligibility"]["status"])
        self.assertEqual(7, entry["download_bounds"]["sample_limit"])

    def test_service_does_not_mark_same_candidate_snapshot_as_changed(self) -> None:
        with TemporaryDirectory() as tmp:
            source_path = Path(tmp) / "sources.json"
            local_path = Path(tmp) / "local_sources.json"
            profile_path = Path(tmp) / "crawler_asset_profiles.local.json"
            source_path.write_text(
                """
{
  "schema_version": 1,
  "sources": [
    {
      "source_id": "demo_index",
      "provider_id": "demo_provider",
      "name": "Demo Index",
      "source_type": "html_file_index",
      "endpoint_url": "https://example.test/index.html"
    }
  ]
}
""".strip(),
                encoding="utf-8",
            )
            conn = connect_db(Path(tmp) / "catalog.sqlite")
            try:
                repo = ApiCatalogRepository(conn)
                repo.init_schema()
                repo.upsert_provider(
                    Provider(
                        provider_id="demo_provider",
                        name="Demo Provider",
                        owner="Demo",
                        categories=("demo",),
                        geographic_scope="sample",
                        docs_url="https://example.test/docs",
                        auth_type="none",
                    )
                )
                source = load_crawler_asset_source("demo_index", source_path, local_path)
                self.assertIsNotNone(source)
                assert source is not None
                asset = crawler_asset_from_source(source)
                spec = build_crawler_asset_bound_form_spec(asset.asset_id, asset.capabilities[2].bounds_schema)
                bounds_payload = crawler_asset_bound_payload_from_form_values(spec, {"limit": "7"})
                candidate = DatasetCandidate(
                    dataset=Dataset(
                        dataset_uid="demo_provider:dataset_a",
                        provider_id="demo_provider",
                        dataset_id="dataset_a",
                        title="Dataset A",
                        categories=("demo",),
                        native_format="csv",
                        api_url="https://example.test/data.csv",
                        metadata={"download_url": "https://example.test/data.csv"},
                    ),
                    source_id="demo_index",
                    source_type="html_file_index",
                    source_url="https://example.test/index.html",
                    confidence=0.9,
                    evidence=("unit-test",),
                )

                def fake_runner(_sources, _options):
                    return DatasetCrawlResult(
                        candidates=(candidate,),
                        source_results=(
                            DatasetSourceCrawlResult(
                                source_id="demo_index",
                                provider_id="demo_provider",
                                source_type="html_file_index",
                                candidate_count=1,
                                candidates=(candidate,),
                            ),
                        ),
                    )

                from unittest.mock import patch

                with patch("api_launcher.source_download.crawl_dataset_sources", fake_runner):
                    first_result = build_crawler_asset_download_plan(
                        "demo_index",
                        conn,
                        bounds_payload=bounds_payload,
                        downloads_root=Path(tmp) / "downloads",
                        primary_path=source_path,
                        local_path=local_path,
                        profile_path=profile_path,
                    )
                self.assertIsNotNone(first_result.plan_build)
                first_signature = first_result.plan_build.candidate_snapshot_signature
                update_crawler_asset_plan_passport(
                    "demo_index",
                    {
                        "asset_id": "demo_index",
                        "candidate_snapshot_signature": first_signature,
                        "candidate_snapshot_count": 1,
                    },
                    profile_path,
                )

                with patch("api_launcher.source_download.crawl_dataset_sources", fake_runner):
                    second_result = build_crawler_asset_download_plan(
                        "demo_index",
                        conn,
                        bounds_payload=bounds_payload,
                        downloads_root=Path(tmp) / "downloads",
                        primary_path=source_path,
                        local_path=local_path,
                        profile_path=profile_path,
                    )
            finally:
                conn.close()

        self.assertEqual(first_signature, second_result.previous_candidate_snapshot_signature)
        self.assertEqual(first_signature, second_result.plan_build.candidate_snapshot_signature)
        self.assertFalse(second_result.candidate_snapshot_changed)
        self.assertFalse(second_result.to_dict()["candidate_snapshot_changed"])

    def test_service_applies_source_level_version_selection_from_asset_bounds(self) -> None:
        with TemporaryDirectory() as tmp:
            source_path = Path(tmp) / "sources.json"
            local_path = Path(tmp) / "local_sources.json"
            source_path.write_text(
                """
{
  "schema_version": 1,
  "sources": [
    {
      "source_id": "versioned_index",
      "provider_id": "demo_provider",
      "name": "Versioned Index",
      "source_type": "html_file_index",
      "endpoint_url": "https://example.test/index.html"
    }
  ]
}
""".strip(),
                encoding="utf-8",
            )
            conn = connect_db(Path(tmp) / "catalog.sqlite")
            try:
                repo = ApiCatalogRepository(conn)
                repo.init_schema()
                repo.upsert_provider(
                    Provider(
                        provider_id="demo_provider",
                        name="Demo Provider",
                        owner="Demo",
                        categories=("demo",),
                        geographic_scope="sample",
                        docs_url="https://example.test/docs",
                        auth_type="none",
                    )
                )
                source = load_crawler_asset_source("versioned_index", source_path, local_path)
                self.assertIsNotNone(source)
                assert source is not None
                asset = crawler_asset_from_source(source)
                spec = build_crawler_asset_bound_form_spec(asset.asset_id, asset.capabilities[2].bounds_schema)
                bounds_payload = crawler_asset_bound_payload_from_form_values(
                    spec,
                    {"version": "2025-01-02", "limit": "5"},
                )
                candidate = DatasetCandidate(
                    dataset=Dataset(
                        dataset_uid="demo_provider:dataset_a",
                        provider_id="demo_provider",
                        dataset_id="dataset_a",
                        title="Dataset A",
                        categories=("demo",),
                        native_format="csv",
                        metadata={
                            "available_versions": [
                                {
                                    "label": "2025-01-01 shard",
                                    "version": "2025-01-01",
                                    "download_url": "https://example.test/data-2025-01-01.csv",
                                    "source_format": "csv",
                                },
                                {
                                    "label": "2025-01-02 shard",
                                    "version": "2025-01-02",
                                    "download_url": "https://example.test/data-2025-01-02.csv",
                                    "source_format": "csv",
                                },
                            ],
                        },
                    ),
                    source_id="versioned_index",
                    source_type="html_file_index",
                    source_url="https://example.test/index.html",
                    confidence=0.9,
                    evidence=("unit-test",),
                )

                def fake_runner(_sources, _options):
                    return DatasetCrawlResult(
                        candidates=(candidate,),
                        source_results=(
                            DatasetSourceCrawlResult(
                                source_id="versioned_index",
                                provider_id="demo_provider",
                                source_type="html_file_index",
                                candidate_count=1,
                                candidates=(candidate,),
                            ),
                        ),
                    )

                from unittest.mock import patch

                with patch("api_launcher.source_download.crawl_dataset_sources", fake_runner):
                    result = build_crawler_asset_download_plan(
                        "versioned_index",
                        conn,
                        bounds_payload=bounds_payload,
                        downloads_root=Path(tmp) / "downloads",
                        primary_path=source_path,
                        local_path=local_path,
                    )
            finally:
                conn.close()

        self.assertFalse(result.blocked)
        self.assertEqual(1, result.plan_build.selected_version_count)
        self.assertEqual(1, result.plan_build.filtered_version_count)
        entry = result.resolved_plan["providers"][0]
        version = entry["dataset_version"]
        self.assertEqual("2025-01-02", version["version"])
        self.assertEqual("https://example.test/data-2025-01-02.csv", entry["download_url"])
        self.assertFalse(result.candidate_snapshot_changed)


if __name__ == "__main__":
    unittest.main()
