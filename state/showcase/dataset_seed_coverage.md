# 資料集 seed 覆蓋展示報告

這份報告只檢查 catalog 裡的 dataset discovery source 設定，不執行網路爬取、不下載資料，適合展示目前入口爬蟲的 seed 覆蓋狀態。

## 摘要

- 展示狀態：`all_sources_have_complete_seed_attempt_path`
- 來源入口數：23
- 具備完整 seed 嘗試路徑：23
- 目前已是完整入口列表或分頁 catalog：1
- 需要展示模式忽略抽樣 `search_terms`：22
- 展示用 max-pages 安全上限：3

## 目前 seed 範圍

- `bounded_search_terms`：22
- `entry_listing`：1

## 下一步分組

- `run_dataset_discovery_complete_seed_to_ignore_sample_terms`：22
- `run_full_crawl_or_export_candidates`：1

## 建議展示命令

- `fast_seed_audit`：`--dataset-discovery-seed-coverage-json`
- `write_seed_audit`：`--write-dataset-seed-coverage state/showcase/dataset_seed_coverage.json`
- `complete_seed_attempt`：`--discover-dataset-candidates --dataset-discovery-complete-seed --dataset-discovery-max-pages 3`

## Source 明細

| Source | Provider | 類型 | 目前 seed 範圍 | 下一步 |
| --- | --- | --- | --- | --- |
| `noaa_ncei_dataset_search` | `noaa_ncei_access_data` | `ncei_search` | `bounded_search_terms` | `run_dataset_discovery_complete_seed_to_ignore_sample_terms` |
| `noaa_coastwatch_erddap_all_datasets` | `noaa_coastwatch_erddap` | `erddap_all_datasets` | `bounded_search_terms` | `run_dataset_discovery_complete_seed_to_ignore_sample_terms` |
| `marinecadastre_ais_daily_index_2025` | `noaa_marinecadastre_ais` | `html_file_index` | `entry_listing` | `run_full_crawl_or_export_candidates` |
| `nasa_earthdata_cmr_collections` | `nasa_earthdata` | `cmr_collections` | `bounded_search_terms` | `run_dataset_discovery_complete_seed_to_ignore_sample_terms` |
| `microsoft_planetary_computer_stac_collections` | `microsoft_planetary_computer` | `stac_collections` | `bounded_search_terms` | `run_dataset_discovery_complete_seed_to_ignore_sample_terms` |
| `earth_search_stac_collections` | `earth_search_stac` | `stac_collections` | `bounded_search_terms` | `run_dataset_discovery_complete_seed_to_ignore_sample_terms` |
| `gbif_dataset_search` | `gbif` | `gbif_dataset_search` | `bounded_search_terms` | `run_dataset_discovery_complete_seed_to_ignore_sample_terms` |
| `data_gov_package_search` | `data_gov` | `ckan_package_search` | `bounded_search_terms` | `run_dataset_discovery_complete_seed_to_ignore_sample_terms` |
| `nyc_open_data_socrata_catalog` | `nyc_open_data_socrata` | `socrata_catalog_search` | `bounded_search_terms` | `run_dataset_discovery_complete_seed_to_ignore_sample_terms` |
| `sf_open_data_socrata_catalog` | `sf_open_data_socrata` | `socrata_catalog_search` | `bounded_search_terms` | `run_dataset_discovery_complete_seed_to_ignore_sample_terms` |
| `chicago_data_portal_socrata_catalog` | `chicago_data_portal_socrata` | `socrata_catalog_search` | `bounded_search_terms` | `run_dataset_discovery_complete_seed_to_ignore_sample_terms` |
| `noaa_pmel_erddap_all_datasets` | `noaa_pmel_erddap` | `erddap_all_datasets` | `bounded_search_terms` | `run_dataset_discovery_complete_seed_to_ignore_sample_terms` |
| `ioos_erddap_all_datasets` | `ioos_erddap` | `erddap_all_datasets` | `bounded_search_terms` | `run_dataset_discovery_complete_seed_to_ignore_sample_terms` |
| `emodnet_erddap_all_datasets` | `emodnet_erddap` | `erddap_all_datasets` | `bounded_search_terms` | `run_dataset_discovery_complete_seed_to_ignore_sample_terms` |
| `harvard_dataverse_search` | `harvard_dataverse` | `dataverse_search` | `bounded_search_terms` | `run_dataset_discovery_complete_seed_to_ignore_sample_terms` |
| `zenodo_records_search` | `zenodo` | `zenodo_records_search` | `bounded_search_terms` | `run_dataset_discovery_complete_seed_to_ignore_sample_terms` |
| `datacite_dois_search` | `datacite` | `datacite_dois` | `bounded_search_terms` | `run_dataset_discovery_complete_seed_to_ignore_sample_terms` |
| `canada_open_data_package_search` | `canada_open_data` | `ckan_package_search` | `bounded_search_terms` | `run_dataset_discovery_complete_seed_to_ignore_sample_terms` |
| `uk_data_gov_package_search` | `uk_data_gov_ckan` | `ckan_package_search` | `bounded_search_terms` | `run_dataset_discovery_complete_seed_to_ignore_sample_terms` |
| `australia_data_gov_package_search` | `australia_data_gov_ckan` | `ckan_package_search` | `bounded_search_terms` | `run_dataset_discovery_complete_seed_to_ignore_sample_terms` |
| `hdx_package_search` | `hdx_ckan` | `ckan_package_search` | `bounded_search_terms` | `run_dataset_discovery_complete_seed_to_ignore_sample_terms` |
| `openalex_dataset_works_search` | `openalex` | `openalex_works_search` | `bounded_search_terms` | `run_dataset_discovery_complete_seed_to_ignore_sample_terms` |
| `wmo_wis2_gdc_records` | `wmo_wis2_gdc` | `ogc_api_records` | `bounded_search_terms` | `run_dataset_discovery_complete_seed_to_ignore_sample_terms` |
