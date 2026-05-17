# APIkeys_collection Project State

Last local review: 2026-05-17

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
- Built-in providers are now loaded from `catalog/APIkeys_collection_catalog.json` with a small Python overlay for fields that should not clutter the catalog, such as extra credential env vars.
- `APIkeys_collection_ui.py` is now a compatibility wrapper for the Tk launcher implementation in
  `frontends/tk/launcher_ui.py`.
- `APIkeys_collection.sqlite` currently contains provider-level catalog state.
- Dataset-level adapter interfaces now exist. Concrete provider-specific adapters include `HYGStarCatalogAdapter` for
  the HYG v3.8 star catalog and `GEBCOTopographyAdapter` for the GEBCO 2025 global elevation grid.
- HTTP downloads now use staging, sidecar manifests, and SQLite manifest registration so downloaded files can be
  verified later instead of being treated as anonymous blobs. If the target file and sidecar manifest already verify
  and match the requested provider/dataset/version/source/path, the HTTP adapter reuses the file instead of downloading again.
- CLI handoff and observability commands now exist: `--verify-downloads`, `--manifest-health`, `--show-logs`, and
  `--handoff-report`.
- Data-store checks now use `api_launcher/data_store_connections.py` as the single profile contract. CLI
  `--test-data-store PROFILE_ID|all` can test configured profiles without storing secrets.
- Database self-check now verifies managed SQLite database and table assets from the install registry. Whole-database
  assets use read-only schema fingerprints; table assets use `source_uri` as the SQLite path and `asset_name` as the
  table name, preserving missing/error details for repair work.
- MySQL/PostgreSQL connection probes now have reusable `information_schema` helpers for table counts, table names,
  table existence, column signatures, and schema fingerprints. Database assets with registered fingerprints can request
  deep schema summaries when the optional DB driver and env vars are available.
- MySQL/PostgreSQL table assets now carry install ownership through `AssetRecord.install_location`; self-check can parse
  the target database, check table existence, and compare table-level fingerprints when drivers/env vars are available.
- Database self-check failures now map to stable repair suggestions and can be emitted as pure JSON through
  `--self-check-databases-json` for UI or agent handoff workflows.
- Tk Repair / verify assets now has a Databases tab that surfaces those suggestions in Traditional Chinese without
  executing destructive SQL. UI language is configurable through `ui_language` in local integration config.
- Tk source browsing now supports category/provider sidebar modes. Provider mode can show cached website favicons from
  `state/favicons/`.
- AI-generated provider descriptions now use explicit AI profile selection under `設定 > AI 輔助模型`; per-profile
  QR/device OAuth login can store local tokens under `state/private/ai_oauth_tokens/`.
- Unreal Engine 5 is now treated as the future interactive frontend. Local UE 5.7 is detected on this Windows machine,
  and the launcher has an Unreal bridge profile/check/plan skeleton.

Current SQLite counts observed on this machine:

- `providers`: 25
- `template_keys`: 18
- `provider_download_state`: 25
- `crawl_results`: 4
- `datasets`: depends on adapter discovery; HYG and GEBCO can be inserted by `--discover-datasets`
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
- `api_launcher/plans.py`: shared Download Plan JSON schema builder used by the UI and future workers.
- `api_launcher/renderer_contracts.py`: shared renderer IDs and bridge-asset contracts for `taichi_global_bathymetry.py`.
- `api_launcher/adapters/`: dataset adapter interface and stable dataset UID helper.
- `api_launcher/asset_verifier.py`, `asset_roles.py`, and `provenance.py`: local asset verification and provenance helpers for SQL/API/CSV/JSON/manual imports.
- `api_launcher/curation.py`: first data-cleaning primitives for field mapping, type casting, required checks, and deduplication.
- `api_launcher/discovery.py`: seed-driven official source-site metadata discovery for reviewable provider candidates.
- `api_launcher/manifests.py`, `staging.py`, and `repair.py`: staged downloads, sidecar manifest creation, and manifest verification.
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
- `docs/RENDER_FRONTENDS.zh-TW.md`: Chinese note that separates Taichi reference rendering from the final Unreal
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
  Exports include a plan name, provider count, planned status, priority, and target fields for future workers.
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
- Unreal bridge planning is documented in `docs/UNREAL_BRIDGE.zh-TW.md`; no real `.uproject` has been configured yet.

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

1. Add per-asset SQL profile/schema selection instead of relying only on default MySQL/PostgreSQL env vars.
2. Add real-driver integration smoke coverage for optional MySQL/PostgreSQL paths when test services are available.
3. Turn database repair suggestions into guarded adapter-owned repair actions, then expand repair suggestions to adapter-specific datasets.
4. Use the SQLite manifest registry for broader update/dedupe decisions beyond exact target reuse.
5. Add NOAA/NASA or ERDDAP dataset adapters with real download manifests.
6. Evaluate GEBCO 2026 migration without breaking existing renderer cache IDs.
7. Create or configure the first Unreal `.uproject` and decide the import format for terrain/star assets.
8. Add AI-ready catalog metadata: license, attribution, redistribution, commercial-use, and training/RAG suitability.
