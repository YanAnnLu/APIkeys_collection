# APIkeys_collection Project State

Last local review: 2026-05-20

## Product Intent

`APIkeys_collection` is a Steam-like launcher for big-data sources. The current UI should help browse official data providers, check remote metadata, select datasets, and eventually download/import source data into local assets that downstream renderers can launch quickly.

Current pipeline target:

```text
provider registry -> source catalog -> metadata checks -> download plan
-> dataset adapters -> raw/curated local data -> render bridge assets
-> taichi_global_bathymetry.py
```

The project is not a secret harvester. Credential files are templates for user-owned accounts and API tokens.

## Current Implementation

- `APIkeys_collection.py` is now a thin compatibility wrapper that re-exports `api_launcher.core`.
- Built-in providers are now loaded from `catalog/APIkeys_collection_catalog.json` with a small Python overlay for fields that should not clutter the catalog, such as extra credential env vars. The current built-in catalog has 54 providers, including newer seeds for NOAA GOES-R on AWS, NOAA NOMADS, Marine Regions, GADM, OpenStreetMap Overpass, U.S. Census TIGERweb, EMODnet ERDDAP, Harvard Dataverse, Zenodo, DataCite, OpenAlex, WMO WIS2 Global Discovery Catalogue, Canada/UK/Australia/HDX CKAN portals, and NYC/DataSF/Chicago Socrata portals.
- `APIkeys_collection_ui.py` is now a compatibility wrapper for the Tk launcher implementation in
  `frontends/tk/launcher_ui.py`.
- `APIkeys_collection.sqlite` currently contains provider-level catalog state.
- Dataset-level adapter interfaces now exist. Concrete provider-specific adapters include `HYGStarCatalogAdapter` for
  the HYG v3.8 star catalog and `GEBCOTopographyAdapter` for the GEBCO 2025 global elevation grid.
- Dataset candidate discovery is now crawler-first. `catalog/dataset_discovery_sources.json` has 23 metadata-only
  sources, and `api_launcher/crawlers/` provides a concurrent orchestrator plus source-type crawlers for NOAA/NCEI
  search, ERDDAP `allDatasets`, HTML file indexes, NASA CMR collections, STAC collections, GBIF dataset search,
  Dataverse search, Zenodo records search, DataCite DOI search, OGC API Records, Socrata catalog search, and CKAN `package_search`, producing reviewable dataset candidates without bulk downloads. The orchestrator now reports
  audit warnings for suspicious "successful" crawls, such as zero candidates, low candidate counts, or malformed
  candidate metadata.
- HTTP downloads now use staging, sidecar manifests, and SQLite manifest registration so downloaded files can be
  verified later instead of being treated as anonymous blobs. If the target file and sidecar manifest already verify
  and match the requested provider/dataset/version/source/path, the HTTP adapter reuses the file instead of downloading again.
- Healthy download manifests can now be promoted into the install registry as managed filesystem `file` assets. This
  closes the first MVP loop from direct download to manifest verification to local asset ownership.
- Adapter-discovered dataset plans can now be safely executed from CLI with `--run-download-plan`; only direct entries
  are submitted, `adapter_required` entries are skipped, and completed payloads are manifest-verified before registry
  asset ownership is updated.
- Crawler-discovered dataset candidates can now be exported with `--export-candidate-plan`; this uses the same
  dataset-version plan schema as adapters and adds candidate review metadata plus conservative import hints.
- `--run-download-plan` can optionally add `--import-supported-plan-results`, which imports supported CSV/JSON plan
  results into curated SQLite after manifest verification while tracking import skipped/failed counts separately. If the
  same plan is run again and the target table already exists, the runner records `skipped_existing_table` instead of
  treating the item as a failed import.
- Verified CSV/CSV.GZ manifests can now be imported into curated SQLite tables through `--import-csv-manifest`; columns
  are normalized as safe SQL identifiers, table schema fingerprints are recorded, and the result is registered as a
  managed curated table asset.
- Registry CSV imports can now run in batch through `--import-verified-csv-manifests`; the batch path skips non-CSV,
  unhealthy, and already-imported tables by default so it can be safely re-run during MVP smoke checks.
- Verified JSON/JSONL/GeoJSON manifests can now be imported into curated SQLite tables through
  `--import-json-manifest`; object arrays, JSON Lines, wrapped records/items/results/data arrays, and basic GeoJSON
  FeatureCollections are normalized to safe text columns and registered as managed curated table assets.
- Registry JSON imports can now run in batch through `--import-verified-json-manifests`; the batch path skips non-JSON,
  unhealthy, and already-imported tables by default.
- Dataset update planning now separates static versioned datasets from append-only, revisable, and realtime
  time-series data. Same-version financial/live sources can produce `append_incremental` or
  `maintain_realtime_stream` decisions instead of being skipped.
- CLI handoff and observability commands now exist: `--verify-downloads`, `--verify-downloads-json`,
  `--manifest-health`, `--show-logs`, and `--handoff-report`.
- Data-store checks now use `api_launcher/data_store_connections.py` as the single profile contract. CLI
  `--test-data-store PROFILE_ID|all` can test configured profiles without storing secrets.
- Data-store profiles now support an `env_var_map` for connection roles such as host, database, user, password, port,
  or SQLite path. This lets a custom profile use its own environment variable names without writing secrets into config.
- Database self-check now verifies managed SQLite database and table assets from the install registry. Whole-database
  assets use read-only schema fingerprints; table assets use `source_uri` as the SQLite path and `asset_name` as the
  table name, preserving missing/error details for repair work. The database verifier is scoped to database/table assets
  so downloaded file assets are not marked as database failures.
- Database/table asset records can now store `data_store_profile_id` and explicit `schema_name`. The self-check verifier
  uses configured profiles from local integration config, so future UI settings can choose a profile per asset instead
  of relying only on one hard-coded MySQL/PostgreSQL default.
- MySQL/PostgreSQL connection probes now have reusable `information_schema` helpers for table counts, table names,
  table existence, column signatures, and schema fingerprints. Database assets with registered fingerprints can request
  deep schema summaries when the optional DB driver and env vars are available.
- MySQL/PostgreSQL table assets now carry install ownership through `AssetRecord.install_location`; self-check can parse
  the target database, check table existence, and compare table-level fingerprints when drivers/env vars are available.
- Database self-check failures now map to stable repair suggestions and can be emitted as pure JSON through
  `--self-check-databases-json` for UI or agent handoff workflows.
- Download manifest verification can now emit agent-readable JSON through `--verify-downloads-json`, including
  summary counts, issues, repair suggestions, and safe requeue plan entries for HTTP(S) manifests.
- Tk Repair / verify assets now has a Databases tab that surfaces those suggestions in Traditional Chinese. It can also
  update a selected database/table asset's `data_store_profile_id` and `schema_name`, stop tracking a selected
  database/table asset by marking only that registry asset `unmanaged`, or reimport a manifest-backed missing SQLite
  table from its recorded healthy CSV/JSON sidecar manifest. Registry edits do not execute SQL; reimport only creates a
  missing table and refuses to DROP or replace an existing table. UI language is configurable through `ui_language` in
  local integration config.
- Tk source browsing now supports category/provider sidebar modes. Provider mode can show cached website favicons from
  `state/favicons/`. The main table can optionally show crawler-imported dataset rows under each provider, so dataset
  discovery results are visible without opening the review dialog first.
- AI-generated provider descriptions now use explicit AI profile selection under `整合 > AI 輔助模型選擇`. For the
  current MVP loop, Gemini API keys can be saved under ignored `state/private/ai_api_keys.private.json` and loaded at
  startup. Startup should not activate Google/OAuth tokens or open browser/config windows. Google browser account login and QR/device-code are still desired mid-term product goals, but they should wait
  until the backend MVP loop is closed and the project can provide an official OAuth app or broker; normal users should
  not be asked to paste OAuth Client IDs.
- Unreal Engine 5 is now treated as the future interactive frontend. Local UE 5.7 is detected on this Windows machine,
  and the launcher has an Unreal bridge profile/check/plan skeleton.
- Maritime jurisdiction overlays should be modeled as GIS polygon layers with legal/administrative attributes
  (territorial sea, EEZ, disputed zone, high seas). MySQL spatial tables are acceptable for MVP storage and
  point-in-polygon checks, but PostGIS is the preferred backend for heavier spatial analysis and tiling.
- Financial market data should be modeled as time-series ingest, not static file versions. Store `event_time`,
  `received_at`, and `ingest_run_id`; keep revisions/backfills explicit; use MySQL only for MVP-scale storage and
  prefer TimescaleDB/ClickHouse/Parquet-DuckDB style backends for larger tick or intraday history. TradingView-like
  charting is the UX/rendering benchmark for time-series analysis, separate from Taichi/Unreal globe rendering.
- Collider and large-instrument data should be modeled as scientific event/array data. SQL should hold metadata,
  file indexes, run IDs, calibration versions, provenance, and manifests; raw payloads should usually remain in
  ROOT/HDF5/Parquet/Zarr/FITS/NetCDF/object storage and be analyzed with ROOT/uproot, DuckDB/Parquet, Dask/Spark,
  ClickHouse, or domain-specific tooling.
- Cultural heritage, multimedia, and 3D collections should be modeled as asset bundles. SQL should index metadata,
  location, period, licenses, thumbnails, versions, and provenance; raw photos/video/audio/meshes/point clouds/BIM
  files/textures should remain in filesystem or object storage with manifests and viewer hints for Three.js, Cesium,
  Unreal, Blender, or GLTF pipelines.
- Hadoop/HDFS/Hive/Spark integration is a mid-term handoff point for another team, not a current MVP dependency. The
  launcher should keep manifests, dataset IDs, checksums, provenance, partitions, and job/output metadata as the stable
  contract. `hadoop_default` is reserved in data-store profiles so future adapters have a named integration point.
- Kubernetes/K8S integration is a mid-term orchestration handoff point for containerized workers and services, not a
  database. The launcher should keep job specs, dataset manifest inputs, output manifests, status, retries, and namespace
  metadata as the contract. Runtime orchestration profiles are reserved in integration config for Docker Compose and K8S.

Current SQLite counts observed on this machine:

- `providers`: 35 after current built-in seed
- `template_keys`: 21 after current built-in seed
- `provider_download_state`: follows `providers`
- `crawl_results`: 4
- `datasets`: depends on adapter/crawler discovery; HYG and GEBCO can be inserted by `--discover-datasets`, and crawler candidates can be inserted by `--discover-dataset-candidates --upsert-dataset-candidates`
- `dataset_sync_state`: follows `datasets`
- `render_bridge_assets`: populated when renderer bridge assets are registered
- `dataset_asset_manifests`: populated by completed downloads or `--verify-downloads`

## Structural Progress

The root `APIkeys_collection.py` is now a thin compatibility entry point. The old core has moved into the
`api_launcher` package, and the first stable modules have been split out:

- `api_launcher/models.py`: dataclasses such as `Provider` and `ProviderCatalogEntry`.
- `api_launcher/registry.py`: provider catalog JSON loading and provider overlays.
- `api_launcher/db.py`: project paths, SQLite connection, timestamps, and schema setup.
- `api_launcher/repository.py`: provider seeding, provider queries, UI catalog entries, and starred preferences.
- `api_launcher/plans.py`: shared Download Plan JSON schema builder used by the UI and future workers. It now covers
  provider plans, adapter-discovered dataset-version plans, and crawler-candidate plans with direct/review eligibility
  plus conservative `import_plan` hints for SQLite MVP importers.
- `api_launcher/adapter_review.py` and `adapter_plan_resolver.py`: adapter handoff queues plus a bounded resolver that
  turns CKAN-like direct file resources into executable plan entries, can do one bounded CKAN `package_show`
  metadata lookup when the plan only has a package API URL, can turn ERDDAP/STAC/Socrata API entries into small
  sample download plans, and can do one DataCite DOI metadata lookup for DataCite/OpenAlex DOI entries that have no
  resources yet but may expose explicit `contentUrl` files.
- `api_launcher/renderer_contracts.py`: shared renderer IDs and bridge-asset contracts for `taichi_global_bathymetry.py`.
- `api_launcher/adapters/`: dataset adapter interface and stable dataset UID helper.
- `api_launcher/asset_verifier.py`, `asset_roles.py`, and `provenance.py`: local asset verification and provenance helpers for SQL/API/CSV/JSON/manual imports.
- `api_launcher/importers/curation.py`: first data-cleaning primitives for field mapping, type casting, required checks, and deduplication.
- `api_launcher/discovery.py`: seed-driven official source-site metadata discovery for reviewable provider candidates.
- `api_launcher/manifests.py`, `api_launcher/downloads/staging.py`, and `api_launcher/downloads/repair.py`: staged downloads, sidecar manifest creation, and manifest verification.
- `api_launcher/data_store_connections.py` and `database_self_check.py`: configured data-store probes, SQL
  `information_schema` helpers, plus registry-backed database/table asset self-checks.
- `api_launcher/event_log.py` and `handoff.py`: structured logs and agent/human handoff report generation.
- `api_launcher/unreal_bridge.py`: maps registered renderer bridge assets to future Unreal Content targets.
- `scripts/export_unreal_preview.py`: creates lightweight Unreal preview assets from Taichi cache data and records
  camera-mode streaming hints for the future virtual twin frontend.
- `api_launcher/tile_manifests.py`: shared tile/cache manifest skeleton for Taichi, Unreal, and future local tile
  services.
- `api_launcher/rendering_profiles.py`: cross-platform render backend and performance-budget profile skeleton.
- `api_launcher/render_effects.py` and `api_launcher/simulation_bridge.py`: data-driven visual effect layer contracts
  and contract-only physics/simulation bridge inputs for water and air-quality rendering.
- `api_launcher/core.py`: current crawl, export, and CLI coordination layer.
- `APIkeys_collection.py`: thin CLI compatibility wrapper.
- `APIkeys_collection_ui.py`: thin Tk UI compatibility wrapper; implementation lives in
  `frontends/tk/launcher_ui.py`.
- `renderers/taichi_global_bathymetry.py`: Taichi visualization engine copied into the launcher repo and wired to renderer contracts for cache IDs/paths.
- `docs/appendices/render_frontends.zh-TW.md`: Chinese note that separates Taichi reference rendering from the final Unreal
  virtual twin frontend and records the future camera-driven tile streaming direction.
- `docs/USER_GUIDE.zh-TW.md`: beginner-friendly UI and day-to-day operation guide.
- `docs/TECH_STACK.md`: dependency boundary notes for launcher core, Docker, and optional renderer stack.

The next refactor should split `api_launcher/core.py` further into crawl, exports, and CLI modules.

## Launcher Features

- Provider rows can be starred in the Tk UI. Starred rows are persisted in SQLite through
  `provider_preferences` and sort above normal rows.
- The sidebar includes a starred-only view for important data sources.
- Provider descriptions now open in an on-demand right-side drawer instead of a permanently cramped side panel.
- The Tk UI now uses ratio-based sizing for the window, sidebar, detail drawer, row height, and table columns so it behaves better across Windows/macOS displays and DPI settings.
- The right detail drawer is scrollable, opens/closes with a subtle width animation, and has a dedicated AI-generated description textbox.
- Main table columns can be resized manually and remembered in ignored local config.
- Search has placeholder text so the top entry field is less mysterious.
- Users can add new provider/API sources and edit launcher descriptions directly from the UI.
- The UI now has an explicit Download Plan panel, which acts like a cart/install queue for selected data sources.
  Cart rows use plan item keys, so a row can represent either a whole provider or one dataset/version under that
  provider. This lets multiple crawler-reviewed candidates from the same provider stay in the same plan without
  overwriting each other. Exports include a plan name, provider count, planned status, priority, and target fields
  for future workers. Supported downloaded CSV/JSON plan items can now be imported from the UI into
  `state/curated_imports.sqlite` after sidecar manifest verification. The cart and download job table expose import
  readiness/status and target table hints so users can see whether an item is waiting for download, ready to import,
  imported, blocked by adapter review, or blocked by unpack/adapter work. If the target table already exists, the UI
  now safely auto-renames the new import to the next available table name instead of replacing existing data; shared
  helper skip states such as `skipped_existing_table` are shown as skipped, not failed.
- Dataset-version plan entries that are not directly downloadable, or that need post-download unpack/transform work, now
  include an `adapter_review` handoff block. It records the adapter id, source URL, required action, expected output,
  and reason so future non-direct adapters have a concrete contract instead of a vague "adapter required" label. CLI
  `--adapter-review-plan PATH` and the Tk `Adapter 待辦` panel can list these handoff items as an adapter work queue.
- The first plan-level non-direct resolver exists in `api_launcher/adapter_plan_resolver.py`. CLI
  `--resolve-adapter-plan INPUT --write-resolved-adapter-plan OUTPUT` can promote CKAN-like `resources` metadata that
  already contains direct file URLs into direct plan entries, and can now perform one bounded CKAN `package_show`
  metadata lookup when the plan has only a package API URL. It also scans NCEI/CMR/STAC-like `links` metadata for direct
  file URLs. ERDDAP metadata with `erddap_protocols` can be turned into a small CSV sample by reading the official
  `info/{dataset}/index.json`, using a 25-row limit or minimum grid slice so the MVP can download/import a sample
  without pretending to bulk install the whole dataset. STAC collections become `limit=1` item-search GeoJSON samples.
  Socrata/SODA v2-style `/resource/{id}.json` or `/api/views/{id}` URLs become `$limit=25` JSON/CSV/GeoJSON samples,
  and Socrata resource metadata is skipped by the generic direct-file resolver so it cannot accidentally become an
  unbounded full-table download. NOAA/NCEI Common Access Search candidates can now become bounded JSON metadata samples:
  `/search/v1/datasets` entries with an NCEI dataset id are rewritten to `/search/v1/data?dataset=...&limit=25&offset=0`,
  while existing `/search/v1/data` requests are clamped to the same small limit. If an explicit `/search/v1/data` request
  already has dataset plus station/bbox/location bounds, the resolver may do one `limit=1` metadata lookup and promote
  a `/data/...` direct file only when the file format is supported and `fileSize` is under 100 MB. Otherwise this records
  search metadata only and does not download NOAA data files. DataCite DOI and OpenAlex DOI entries can now do one
  DataCite DOI API metadata lookup and promote only explicit `contentUrl` direct files that are supported and have no
  declared size above 100 MB; DOI landing pages and repository HTML pages still stay in review. HTML/API/unknown resources remain in review. Tk UI exposes the same flow through
  `解析 Adapter 計畫` and the Adapter review panel.
- Archive extraction is the first bounded transform adapter: ZIP/TAR payloads marked `requires_unpack_or_adapter` can
  extract the first supported CSV/JSON member, write a derived sidecar manifest under `state/extracted/`, and continue
  into the existing SQLite import path. This keeps the MVP conservative while making simple archives actionable.
- Provider-level install identity is now represented by `provider_installations.install_id` plus a fingerprint.
  Installation assets can be registered in `provider_installation_assets`, including future SQL uninstall commands.
  UI removal currently marks registry state as removed and does not execute destructive SQL until database adapters exist.
- SQL database assets can now generate safe uninstall metadata for MySQL/MariaDB and PostgreSQL after validating the
  database identifier. Execution is still intentionally blocked.
- Assets now distinguish source, curated, derived, analysis, and cache roles, with source format and schema fingerprint metadata.
  This prevents user-generated analysis tables from being mistaken for upstream official data during self-checks.
- `taichi_global_bathymetry.py` is treated as a downstream visualization engine. The launcher should produce bridge
  assets such as GEBCO topography grids and HYG star catalogs, then register them in `render_bridge_assets`.
- Provider discovery now distinguishes source sites from canonical datasets. Built-in and local seeds produce reviewable
  candidates with dedupe keys; no API secret values are collected. Built-in source-site discovery seeds currently cover
  30 official sources across climate, ocean, biodiversity, geospatial, statistics, research metadata, and Taiwan open data.
- Dataset adapter discovery is now separate from source-site discovery. `api_launcher/dataset_adapters.py` owns the
  adapter registry, and the HYG/GEBCO adapters use shared renderer contract IDs for the HYG v3.8 star catalog and
  GEBCO 2025 global elevation grid.
- Dataset version selection is now generic. Adapters can expose `metadata.available_versions`, and the UI builds a
  right-click version menu through `api_launcher/dataset_versions.py` instead of hard-coding GEBCO-specific choices.
- Product metaphor: providers are like publishers/source stations, while datasets/databases are the library items.
  Dedupe should prefer canonical dataset identity over provider names.
- Local database tools are profile-driven through `launcher_integrations.local.json`; MySQL Workbench is only the current user's profile, not a hard-coded app dependency.
- AI-generated provider descriptions are profile-driven too. The default example uses local Ollama for no-login summaries, while Gemini and OpenAI-compatible profiles can use API keys or configured QR/device OAuth login.
- The UI includes `工具 > 開發者 CLI` for one-shot commands rooted at the project folder.
- The UI includes a file verification action that scans download manifests and syncs file health into SQLite.
- The install registry can register whole-database assets and individual table assets, then verify managed SQLite
  assets with `--self-check-databases`.
- GitHub Actions CI runs tests and a CLI smoke check on Windows and Ubuntu.
- Unreal bridge planning is documented in `docs/appendices/unreal_bridge.zh-TW.md`; no real `.uproject` has been configured yet.

## Cross-Platform Notes

- Windows on this machine uses `py`, not `python`.
- macOS handoff in the current Codex environment uses Conda env `metal_trade_312`; do not install packages into base/system
  Python without asking first.
- Keep project files UTF-8 with LF line endings.
- SQLite state on synced drives can conflict. Prefer treating `*.sqlite` as rebuildable state or copy it locally before heavy writes.
- Git for Windows was installed on 2026-05-17 and the repo was initialized on `main`.
- GitHub CLI was installed and authenticated as `YanAnnLu` on 2026-05-17.
- Docker Desktop 4.73.0 is installed and verified on this Windows machine.
- WSL is installed for Docker Desktop; the `docker-desktop` WSL distro runs as WSL2.
- Docker Compose is verified with `docker compose run --rm --build launcher`.
- The compose file does not bind-mount the RaiDrive project folder because that path did not appear inside the Linux container. Runtime SQLite state lives in the named Docker volume.

## Next Build Target

1. Add real-driver integration smoke coverage for optional MySQL/PostgreSQL paths when test services are available.
2. Expand guarded database repair beyond CSV/JSON manifest-backed missing SQLite tables only when adapter ownership is explicit, then expand download repair suggestions to adapter-specific datasets.
3. Use the SQLite manifest registry for broader update/dedupe decisions beyond exact target reuse.
4. Add financial/time-series adapter contracts for live market data, append windows, revisions, and retention policy.
5. Connect download/database JSON repair payloads to richer event logs and UI guided repair flows.
6. Continue bounded adapter closure where crawler output already reaches the MVP path, then expand crawler-first dataset discovery: use provider/source crawlers to produce NOAA/NCEI, MarineCadastre AIS, GOES-R/cloud imagery, Earth Engine, STAC, and CKAN candidates before writing provider-specific adapters.
7. Add a Marine Regions/VLIZ maritime boundaries adapter for territorial seas, EEZs, disputed zones, and high seas.
8. Evaluate GEBCO 2026 migration without breaking existing renderer cache IDs.
9. Create or configure the first Unreal `.uproject` and decide the import format for terrain/star assets.
10. Add AI-ready catalog metadata: license, attribution, redistribution, commercial-use, and training/RAG suitability.
11. After the backend MVP loop is closed, revisit Google account login as a mid-term goal with an official OAuth app or
    backend broker, then migrate the desktop UI toward PySide6/Qt rather than expanding Tk indefinitely.
