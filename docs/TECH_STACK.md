# APIkeys_collection Tech Stack

## Dependency Boundary

The project has two intentionally separate dependency layers:

- **Launcher core:** standard-library Python, SQLite, Tkinter UI, Docker CLI checks.
- **Renderer stack:** optional heavy scientific/visualization packages for `renderers/taichi_global_bathymetry.py`.

Do not move renderer dependencies into `requirements.txt` unless the Docker launcher image is meant to become a rendering image.

## Launcher Core

- Python 3.13
- SQLite via `sqlite3`
- Tkinter for `APIkeys_collection_ui.py`
- Standard-library networking via `urllib`
- Docker Compose for CLI validation and future workers

Install with:

```bash
python -m pip install -r requirements-dev.txt
```

The current launcher runtime intentionally uses only the Python standard library.

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
- `provider_discovery_seeds.local.json`: ignored local seeds for regional platforms and user projects.
- `api_launcher/discovery.py`: polite metadata crawler for docs/API/signup/auth hints.

Discovery searches metadata and documentation only. It must not collect real API keys, tokens, passwords, cookies, or
other secret values.

The built-in seed list is intentionally broad but shallow. It is a discovery starting point, not a hard-coded final
catalog. As of 2026-05-17 it contains 30 official source-site seeds across weather, climate, ocean, biodiversity,
geospatial, statistics, research metadata, and Taiwan regional open data.

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
-> Render bridge asset
-> taichi_global_bathymetry.py
```

API, CSV, JSON, manual SQL imports, and derived outputs must carry provenance:

- `asset_role`: `source`, `curated`, `derived`, `analysis`, or `cache`
- `source_format`: `api`, `csv`, `json`, `sqlite`, `manual`, or `unknown`
- `source_uri`
- `schema_fingerprint`

This prevents derived analysis tables from being mistaken for official upstream data.

Future AI/LLM workflows should not treat every downloaded file as training-ready. Provider and dataset metadata should
eventually include license, attribution, redistribution, commercial-use, and `training_allowed` fields. Numeric grids and
tables may be better suited for RAG, SQL agents, feature stores, or domain models than direct language-model training.

## Download Engine

Download/import work must stay off the Tk UI thread. The queue skeleton lives in
`api_launcher/download_jobs.py` and uses a worker pool with progress snapshots,
pause, resume, cancel, and retry-ready status fields.

Adapters should report progress through `DownloadProgress` and call
`DownloadJobController.wait_if_paused()` between chunks. Large HTTP adapters
should prefer ranged requests or chunk manifests so interrupted jobs can resume
instead of starting over.

The launcher is allowed to delegate large direct file transfers to external
tools through `api_launcher/transfer_tools.py`. Python remains the orchestrator
for state, UI, credentials, validation, and provenance. External tools are
profiles in `config/launcher_integrations.example.json`:

- `python_internal`: default for APIs, authenticated requests, and adapter logic.
- `aria2c`: preferred optional engine for large direct HTTP/FTP files with
  segmented resume.
- `curl`: portable fallback for simple direct URLs.

Avoid raw shell scripts as the core contract. Keep arguments as lists so Windows,
macOS, and Linux do not diverge on quoting and escaping.

The first working downloader is `api_launcher/http_downloader.py`. It supports
direct HTTP(S) URLs, chunk progress, `.part` files, HTTP Range resume, staging,
sidecar manifests, and atomic promote into the final target path. Dataset-specific API adapters should either
produce direct URLs for this adapter or implement the same `DownloadAdapter`
protocol.

Staging and manifests live in:

- `api_launcher/staging.py`: stable staging paths, legacy `.part` migration, atomic promote.
- `api_launcher/manifests.py`: JSON manifest creation with size, SHA-256, source URL, dataset UID, dataset ID, and version.
- `state/staging/`: ignored runtime staging area.

The staging directory is chosen to stay on the same filesystem as the final target whenever the target is outside the
project tree, because Windows cannot atomically replace across drives. The sidecar manifest next to a downloaded file is
the first repair/update primitive. Future update workers should compare these manifests against remote manifests before
downloading full replacements.

`APIkeys_collection_ui.py` can now submit download-plan rows into the
nonblocking queue, display job progress, and pause/resume/cancel selected jobs.
The UI intentionally starts only rows with an API/download URL; provider-specific
adapters should later decide how catalog pages become real dataset files.

Polite download behavior lives in `api_launcher/download_policy.py`. Adapters
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
- Avoid shell-specific path assumptions; use `pathlib.Path` and `resolve_project_path()`
  for project-local files.

## Logs and Recovery

Runtime logs live under ignored `state/logs/`:

- `launcher_events.jsonl`: structured JSONL records for humans and agents.
- `launcher_errors.log`: compact text summary with tracebacks for warnings/errors.

Use `api_launcher/event_log.py` instead of ad hoc `print()` or silent exception swallowing when an error affects user
state, downloads, adapters, database tools, AI summaries, or startup environment checks. Failure scenarios and recovery
rules are tracked in `docs/FAILURE_MODES.zh-TW.md`.

## Validation

Core validation:

```powershell
py -m unittest discover -s tests
$env:PYTHONDONTWRITEBYTECODE='1'; py -m py_compile APIkeys_collection.py APIkeys_collection_ui.py renderers\taichi_global_bathymetry.py api_launcher\core.py api_launcher\db.py api_launcher\models.py api_launcher\repository.py
docker compose run --rm --build launcher
```

Renderer runtime validation is separate because it needs GPU/windowing support and optional heavy packages.
