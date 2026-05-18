# APIkeys_collection Tech Stack

## Dependency Boundary

The project has two intentionally separate dependency layers:

- **Launcher core:** standard-library Python, SQLite, Tkinter UI, Docker CLI checks.
- **Renderer stack:** optional heavy scientific/visualization packages for `renderers/taichi_global_bathymetry.py`.

Do not move renderer dependencies into `requirements.txt` unless the Docker launcher image is meant to become a rendering image.

## Launcher Core

- Python 3.13
- SQLite via `sqlite3`
- Tkinter for `frontends/tk/launcher_ui.py` with root-level `APIkeys_collection_ui.py` kept as a compatibility wrapper.
- Standard-library networking via `urllib`
- Docker Compose for CLI validation and future workers

Install with:

```bash
python -m pip install -r requirements-dev.txt
```

The current launcher runtime intentionally uses only the Python standard library.
On the current macOS Codex handoff machine, use Conda env `metal_trade_312` for validation and any optional package
installs. Do not install into base/system Python unless the user explicitly approves.

For short-lived SQLite reads/writes, do not rely on `with sqlite3.connect(...)` to close the file handle. That context
manager commits or rolls back transactions, but it does not close the connection; Windows CI can keep temp `.sqlite`
files locked. Use `contextlib.closing(sqlite3.connect(...))` or an explicit `finally: conn.close()`.

## Renderer Stack

Optional dependencies live in `requirements-renderer.txt`.

- `taichi`: GPU/CPU compute and GUI rendering engine.
- `numpy`: array representation for bridge assets such as `.npy` terrain grids and star catalogs.
- `xarray`: remote NetCDF/OPeNDAP access for GEBCO gridded elevation data.
- `matplotlib`: colormap generation for elevation rendering.
- `pandas`: CSV loading and filtering for HYG star catalog data.
- `tqdm`: progress bars for large cache reads/downloads.

Install only when running the renderer:

```bash
python -m pip install -r requirements-renderer.txt
python renderers/taichi_global_bathymetry.py
```

## Renderer Contract

`taichi_global_bathymetry.py` is treated as a visualization engine. It should not be the owner of data discovery,
install identity, curation, or uninstall behavior.

The launcher owns these bridge contracts in `api_launcher/renderer_contracts.py`:

- Renderer ID: `taichi_global_bathymetry`
- GEBCO 2025 elevation dataset: `gebco_2025_elevation`
- HYG v3.8 star catalog dataset: `hyg_v38_bright_star_catalog`
- Bridge asset roles: `topography_grid`, `star_catalog`
- Cache location: `~/.cache/taichi_earth`

The renderer may read the contract constants, but the launcher should register bridge assets in SQLite through
`render_bridge_assets`.

## Discovery Stack

Provider/source discovery currently uses only the Python standard library:

- `catalog/provider_discovery_seeds.json`: built-in official source-site seeds.
- `catalog/dataset_discovery_sources.json`: configurable dataset-catalog crawlers for provider-backed sources.
- `provider_discovery_seeds.local.json`: ignored local seeds for regional platforms and user projects.
- `api_launcher/discovery.py`: polite metadata crawler for docs/API/signup/auth hints.
- `api_launcher/crawlers/`: metadata-only dataset candidate crawlers. The orchestrator runs source crawlers concurrently, dedupes results, and reports both errors and audit warnings; source-specific parsers handle searchable APIs, ERDDAP JSON tables, HTML file indexes, CMR, STAC, GBIF, and CKAN.

Discovery searches metadata and documentation only. It must not collect real API keys, tokens, passwords, cookies, or
other secret values.

The built-in seed list is intentionally broad but shallow. It is a discovery starting point, not a hard-coded final
catalog. As of 2026-05-18 it contains 33 official source-site seeds across weather, climate, ocean, biodiversity,
geospatial, statistics, research metadata, Taiwan regional open data, Google Earth Engine, NOAA AIS, and GOES-R cloud imagery.

Dataset discovery is the next layer below provider discovery. The CLI can write reviewable dataset candidates without
bulk downloading:

```bash
python3 APIkeys_collection.py --init-db --seed --discover-dataset-candidates \
  --dataset-discovery-source marinecadastre_ais_daily_index_2025 \
  --dataset-discovery-limit 2 \
  --write-dataset-candidates dataset_candidates.smoke.json \
  --upsert-dataset-candidates
```

Reviewed crawler candidates can then be turned into the same dataset-version plan schema used by adapters:

```bash
python3 APIkeys_collection.py --db state/candidate_plan_smoke.sqlite \
  --export-candidate-plan state/candidate_plan.json \
  --candidate-plan-status needs_review \
  --candidate-plan-limit 2
```

Plan entries include `download_eligibility`, stable `target_path` for direct file URLs, `dataset_version`, and an
`import_plan`. The import plan is intentionally conservative: CSV/CSV.GZ and JSON/JSONL/GeoJSON can be routed to the
current SQLite MVP importers after manifest verification; compressed bundles such as CSV.ZST are downloadable but
marked `requires_unpack_or_adapter`; API selectors and landing pages stay `adapter_review_required`.

AIS and satellite cloud imagery should be treated as representative crawler targets. Avoid turning each one into a
hardcoded Python adapter until the crawler has produced a candidate and the remaining work is provider-specific query,
auth, transform, or import logic.

Dataset-specific discovery is separate from source-site discovery:

- `api_launcher/adapters/base.py`: adapter protocol and stable dataset UID helper.
- `api_launcher/dataset_adapters.py`: registry for provider-specific dataset adapters.
- `api_launcher/adapters/gebco.py`: maps GEBCO to the GEBCO 2025 elevation grid through the renderer contract ID.
- `api_launcher/adapters/hyg.py`: first concrete adapter; maps HYG Database to the HYG v3.8 star catalog dataset using
  the renderer contract ID.

Run the HYG dataset adapter smoke path with:

```powershell
py APIkeys_collection.py --init-db --seed --discover-datasets --provider hyg_database --db state\hyg_adapter_smoke.sqlite --summary
py APIkeys_collection.py --init-db --seed --discover-datasets --provider gebco --db state\gebco_adapter_smoke.sqlite --summary
```

GEBCO's public site now advertises the 2026 grid, while the renderer contract is still pinned to GEBCO 2025. Treat
the 2025 adapter as the compatibility bridge for the current renderer cache names until the renderer migration is tested.

Seeds and adapters must not be treated as proof of freshness. A seed may point to an official entry page whose newest
dataset changes over time, while an adapter may intentionally pin an older version for renderer or schema compatibility.
Dataset metadata should therefore carry version status fields such as `version_status`, `latest_known_version`,
`latest_known_release_date`, and `freshness_review_required`.

Version selection is generic, not GEBCO-specific. Adapters may expose `metadata.available_versions`; the shared
`api_launcher/dataset_versions.py` layer converts any dataset into sorted version options for CLI/UI use. The Tk UI
uses that shared function to build the right-click dataset-version menu dynamically.

The CLI can export adapter-discovered dataset versions into a download-plan JSON:

```powershell
py APIkeys_collection.py --init-db --seed --provider hyg_database --export-dataset-plan state\hyg_dataset_plan.json
```

Direct file URLs get `download_url`, `target_path`, `dataset_version`, and `use_staging` fields. URLs that look like
landing pages, API selectors, or download portals are deliberately marked `adapter_required` with an
`adapter_review_url`, so the downloader does not accidentally save an HTML page as if it were a dataset.

Adapter review entries can now be passed through a conservative resource resolver:

```powershell
py APIkeys_collection.py --resolve-adapter-plan state\candidate_plan.json --write-resolved-adapter-plan state\candidate_plan.resolved.json
```

`api_launcher/adapter_plan_resolver.py` currently handles common catalog/resource shapes used by CKAN-like and
metadata-link sources. If a review entry carries `dataset_version.metadata.resources` or `dataset_version.metadata.links`, the resolver promotes only URLs that already
look like direct downloadable files into new direct plan entries with fresh `target_path`, `download_eligibility`, and
`import_plan` fields. It leaves HTML pages, API selectors, and unknown resources in adapter review, so this is a
bounded plan rewrite rather than a hidden scraper.

The Tk UI exposes this through `資料庫 > 解析 Adapter 計畫`, `更多 > 解析 Adapter 計畫`, and the Adapter review panel's
`解析可下載 resources` button. When it finds direct resources, it adds them back into the bottom download plan so the
user can continue with the normal Start -> verify manifest -> import flow.

The direct entries in a plan can then be executed by the CLI:

```powershell
py APIkeys_collection.py --init-db --seed --run-download-plan state\hyg_dataset_plan.json --verify-downloads --manifest-health
```

`--run-download-plan` only submits entries that have a direct `download_url` and are not marked `adapter_required`.
Completed downloads are verified through their sidecar manifest and registered as managed filesystem `file` assets.
Use `--download-plan-limit N` for smoke tests or when you want to run only the first few direct entries.

If a plan entry has `import_plan.status=supported_after_download`, the runner can import supported CSV/JSON payloads
immediately after manifest verification:

```powershell
py APIkeys_collection.py --run-download-plan state\candidate_plan.json --import-supported-plan-results --import-sqlite-db state\curated_imports.sqlite
```

This is intentionally opt-in. The runner skips unsupported formats, and import failures are reported separately from
download/manifest failures.

Verified CSV or CSV.GZ payloads can now be imported into a curated SQLite table:

```powershell
py APIkeys_collection.py --init-db --seed --import-csv-manifest downloads\sample.csv.manifest.json --import-sqlite-db state\curated_imports.sqlite --import-table sample_curated
```

This is intentionally conservative for the backend MVP: every imported column is stored as `TEXT`, column names are
normalized into safe SQL identifiers, the CSV schema fingerprint is recorded, and the resulting SQLite table is
registered as a managed `curated` table asset. Use `--import-replace-table` only when you intentionally want to drop
and recreate the target table.

To import every healthy CSV/CSV.GZ manifest already registered in SQLite:

```powershell
py APIkeys_collection.py --import-verified-csv-manifests --import-sqlite-db state\curated_imports.sqlite
```

The batch importer skips non-CSV manifests, non-healthy manifests, and existing tables by default. Add `--provider ID`
to scope the batch import to one or more providers, or `--import-replace-table` when you intentionally want to recreate
matching curated tables.

Dataset transitions should avoid brute-force delete-and-redownload when possible. The generic planner in
`api_launcher/dataset_updates.py` decides whether to install new data, skip an already-current version, upgrade,
downgrade, move to an intermediate newer/older version, compare before updating, or keep an older compatibility version
side by side. Provider adapters should add manifests, checksums, schema fingerprints, and dedupe keys so future update
workers can download only changed files/rows/tiles when the upstream source supports it.

## Data Pipeline

```text
Provider catalog
-> Dataset adapter
-> Raw download/import
-> Curation
-> Optional Hadoop/HDFS/Hive/Spark handoff for large batch/data-lake workloads
-> Render bridge asset
-> taichi_global_bathymetry.py
```

API, CSV, JSON, manual SQL imports, and derived outputs must carry provenance:

- `asset_role`: `source`, `curated`, `derived`, `analysis`, or `cache`
- `source_format`: `api`, `csv`, `json`, `sqlite`, `manual`, or `unknown`
- `source_uri`
- `schema_fingerprint`

For mid-term Hadoop integration, keep the launcher/Hadoop boundary manifest-driven. The launcher should not assume it
owns the Hadoop cluster. It should hand over verified dataset IDs, versions, checksums, partitions, HDFS/Hive targets,
job run IDs, and lineage metadata, then read back status/output manifests from the Hadoop team's pipeline.

For mid-term Kubernetes integration, keep the launcher/K8S boundary job-spec-driven. K8S should run containerized
workers, scheduled jobs, API services, and repair scanners, while the launcher records desired job specs and consumes
status/output manifests. Cluster secrets, scaling, network policy, and operational health belong to the K8S team.

This prevents derived analysis tables from being mistaken for official upstream data.

Database assets are checked through `api_launcher/database_self_check.py`. SQLite database assets use read-only
database-level schema fingerprints; SQLite table assets use `source_uri` as the database path and `asset_name` as the
table name for existence and table-level fingerprint checks. MySQL/PostgreSQL checks should continue through
`api_launcher/data_store_connections.py` so missing env vars and optional drivers are reported before any connection
attempt. The same module now owns reusable MySQL/PostgreSQL `information_schema` helpers for table counts, table names,
table existence, column signatures, and optional schema fingerprints. SQL table assets should keep database ownership in
the install record location; PostgreSQL table assets may use `schema.table` in `asset_name`.

When database self-check finds a missing/error asset, `api_launcher/database_self_check.py` maps the error into a stable
repair suggestion such as `configure_data_store_env`, `install_optional_driver_in_project_env`,
`restore_or_reimport_table`, or `review_schema_drift`. Use `--self-check-databases-json` for pure JSON output that UI
code or a future agent can consume without parsing human text.

Tk UI localization is intentionally lightweight for now. `launcher_integrations.local.json` may contain
`"ui_language": "zh-TW"` or `"en-US"`; the UI reads it at startup, `Settings > Interface language` can update it, and
new dialogs use the latest value immediately. The default user-facing path should stay Traditional Chinese, with English
fallback text added through `ApiCollectionUi.tr(...)` as UI sections are touched.

Provider-sidebar favicons are a UI convenience layer, not catalog truth. They are fetched from official provider home
URLs, normalized to small PNG files, and cached under ignored `state/favicons/`. Missing icons should never block the UI.

AI summary profiles can carry either API-key env vars or an `oauth_device` block. OAuth/device-code tokens are saved
under ignored `state/private/ai_oauth_tokens/`, but the Tk launcher must not activate OAuth tokens, open browsers, or
open config files during startup. Gemini API keys can be saved under ignored `state/private/ai_api_keys.private.json`
and loaded at startup for the current MVP. The selected model remains `active_ai_summary_profile`; logging into a
service must not silently change that selection. Google account sign-in is still a mid-term product goal, not
abandoned, but it should wait until the MVP backend loop is closed and the project can provide an official OAuth app or
broker.

Future AI/LLM workflows should not treat every downloaded file as training-ready. Provider and dataset metadata should
eventually include license, attribution, redistribution, commercial-use, and `training_allowed` fields. Numeric grids and
tables may be better suited for RAG, SQL agents, feature stores, or domain models than direct language-model training.

## Download Engine

Download/import work must stay off the Tk UI thread. The queue skeleton lives in
`api_launcher/downloads/jobs.py` and uses a worker pool with progress snapshots,
pause, resume, cancel, and retry-ready status fields.

Adapters should report progress through `DownloadProgress` and call
`DownloadJobController.wait_if_paused()` between chunks. Large HTTP adapters
should prefer ranged requests or chunk manifests so interrupted jobs can resume
instead of starting over.

The launcher is allowed to delegate large direct file transfers to external
tools through `api_launcher/downloads/transfer_tools.py`. Python remains the orchestrator
for state, UI, credentials, validation, and provenance. External tools are
profiles in `config/launcher_integrations.example.json`:

- `python_internal`: default for APIs, authenticated requests, and adapter logic.
- `aria2c`: preferred optional engine for large direct HTTP/FTP files with
  segmented resume.
- `curl`: portable fallback for simple direct URLs.

Avoid raw shell scripts as the core contract. Keep arguments as lists so Windows,
macOS, and Linux do not diverge on quoting and escaping.

The first working downloader is `api_launcher/downloads/http.py`. It supports
direct HTTP(S) URLs, chunk progress, `.part` files, HTTP Range resume, staging,
sidecar manifests, and atomic promote into the final target path. Dataset-specific API adapters should either
produce direct URLs for this adapter or implement the same `DownloadAdapter`
protocol.

Staging and manifests live in:

- `api_launcher/downloads/staging.py`: stable staging paths, legacy `.part` migration, atomic promote.
- `api_launcher/manifests.py`: JSON manifest creation with size, SHA-256, source URL, dataset UID, dataset ID, and version.
- `state/staging/`: ignored runtime staging area.

The staging directory is chosen to stay on the same filesystem as the final target whenever the target is outside the
project tree, because Windows cannot atomically replace across drives. The sidecar manifest next to a downloaded file is
the first repair/update primitive. Future update workers should compare these manifests against remote manifests before
downloading full replacements.

Sidecar manifests are also registered in SQLite table `dataset_asset_manifests`. CLI `--verify-downloads` scans the
manifest files, verifies payload presence/size/SHA-256, and syncs the health status back into SQLite for future UI and
agent repair workflows. `--verify-downloads-json` emits the same scan as agent-readable JSON with issues, repair
suggestions, and safe HTTP(S) requeue plan entries.

`APIkeys_collection_ui.py` can now submit download-plan rows into the
nonblocking queue, display job progress, and pause/resume/cancel selected jobs.
The UI intentionally starts only rows with an API/download URL; provider-specific
adapters should later decide how catalog pages become real dataset files.

Polite download behavior lives in `api_launcher/downloads/policy.py`. Adapters
should respect per-host pacing, bounded retries, `Retry-After`, and cooldowns for
rate-limit responses such as HTTP 429 and temporary overload responses such as
HTTP 503. Do not increase concurrency globally without checking provider terms.
The default policy is configured in `config/launcher_integrations.example.json`
and can be overridden in ignored `launcher_integrations.local.json`.

## Cross-platform Path and Encoding Rules

- Source files are UTF-8 with LF endings. See `.editorconfig` and `.gitattributes`.
- Local machine paths belong in ignored `*.local.json` files, not in tracked code.
- Startup path checks live in `api_launcher/environment.py` and should run before
  expensive downloader or renderer work.
- Startup checks must not treat another platform's absolute path as a blocking error. For example, `K:\...` in a local
  config on macOS should be a warning or a per-platform config gap, not a Mac UI launch failure.
- For Unreal config, prefer `project_path_by_platform` and `content_root_by_platform`; generic Windows paths are ignored
  on macOS/Linux before `pathlib.Path` tries to resolve them.
- Avoid shell-specific path assumptions; use `pathlib.Path` and `resolve_project_path()`
  for project-local files.

## Logs and Recovery

Runtime logs live under ignored `state/logs/`:

- `launcher_events.jsonl`: structured JSONL records for humans and agents.
- `launcher_errors.log`: compact text summary with tracebacks for warnings/errors.

Use `api_launcher/event_log.py` instead of ad hoc `print()` or silent exception swallowing when an error affects user
state, downloads, adapters, database tools, AI summaries, or startup environment checks. Failure scenarios and recovery
rules are tracked in `docs/appendices/failure_modes.zh-TW.md`.

## Validation

Core validation:

```powershell
py -m unittest discover -s tests
$env:PYTHONDONTWRITEBYTECODE='1'; py -m py_compile APIkeys_collection.py APIkeys_collection_ui.py frontends\tk\launcher_ui.py renderers\taichi_global_bathymetry.py api_launcher\core.py api_launcher\db.py api_launcher\models.py api_launcher\repository.py
docker compose run --rm --build launcher
```

Renderer runtime validation is separate because it needs GPU/windowing support and optional heavy packages.

## Unreal Bridge

Unreal Engine is treated as the future interactive frontend for the virtual twin. The launcher should prepare and
verify data before Unreal imports or reads it.

- `config/launcher_integrations.example.json`: `unreal_projects` profile with engine/editor/project/content paths.
- `api_launcher/environment.py`: Unreal engine/editor/project/content checks.
- `api_launcher/unreal_bridge.py`: maps `render_bridge_assets` to Unreal `Content/APIkeysCollection` targets and
  `/Game/APIkeysCollection/...` mount paths.
- `api_launcher/tile_manifests.py`: shared JSON schema helpers for file-backed or service-backed data tiles.
- `api_launcher/rendering_profiles.py`: cross-platform frontend/backend and tile-budget hints for Taichi/Unreal.
- `scripts/export_unreal_preview.py`: exports lightweight OBJ/MTL/CSV preview assets from Taichi Earth caches into
  a local Unreal project.
- `docs/appendices/unreal_bridge.zh-TW.md`: Chinese design notes for the frontend bridge.
- `docs/appendices/render_frontends.zh-TW.md`: Chinese notes that define Taichi as the cross-platform GPU reference renderer
  and Unreal as the final camera-driven streaming frontend.

Current bridge command:

```powershell
py APIkeys_collection.py --unreal-bridge-plan
py scripts\export_unreal_preview.py --project K:\UnrealProjects\APIkeysVirtualTwin\APIkeysVirtualTwin.uproject --sample-step 2
```

Taichi is a cross-platform reference renderer and smoke-test path, not the final frontend. The final Unreal path should
use camera-driven tile streaming: first-person views request high-detail nearby tiles, second-person views refine around
the followed target, and orbit/third-person views keep coarse global tiles with selective refinement.
