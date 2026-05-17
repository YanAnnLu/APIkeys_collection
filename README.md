# APIkeys_collection

`APIkeys_collection.py` builds a local, extensible launcher for public scientific data-provider metadata.

It is designed as a local catalog, download guide, update checker, and bridge planner for
scientific/geospatial/financial data sources. It is crawler/downloader preparation, not secret harvesting:

- Catalogs official docs, API base URLs, sign-up pages, auth type, and categories.
- Creates a local SQLite database: `APIkeys_collection.sqlite`.
- Generates `.env.example` and `api_keys.txt.template`.
- Optionally fetches small metadata pages from whitelisted official URLs.
- Plans and runs direct downloads only when the source is explicitly safe enough for the current downloader.
- Exports adapter-discovered dataset-version download plans with direct/review eligibility.
- Runs direct entries from a download-plan JSON and registers healthy manifest-backed file assets.
- Imports verified CSV/CSV.GZ manifests into curated SQLite tables and registers table assets.
- Batch-imports healthy CSV/CSV.GZ manifests from the registry while skipping non-CSV, unhealthy, or already-imported tables.
- Does not search for leaked keys or scrape secrets.

## Current Launcher Features

- Tk desktop UI in Traditional Chinese by default, with a language setting under `設定 > 介面語言`.
- Steam-like source browsing with category/provider sidebar modes; provider mode can show cached website favicons.
- Search box, star/pin rows, right detail drawer, generated-description textbox, and a download-plan panel.
- Manual table-column resizing like a spreadsheet; widths are remembered in local config.
- `設定 > AI 輔助模型` lets the user choose which AI profile is actually used.
- AI summaries support local Ollama, Gemini, and OpenAI-compatible chat-completions profiles.
- AI profiles can use API keys or QR/device-code OAuth when the provider exposes such an endpoint; tokens stay under `state/private/`.
- `工具 > 開發者 CLI` opens a small command panel rooted at this project folder.
- Startup checks catch common cross-platform path mistakes, including Windows-style paths on macOS.

## Folder Layout

All default paths are resolved relative to this folder, not relative to your terminal's current working directory.
You can move the whole `APIkeys_collection/` folder elsewhere and the crawler will still find its database,
reference file, templates, and exports.

- `APIkeys_collection.py`: thin compatibility entry point for the CLI and existing UI imports.
- `docs/TECH_STACK.md`: dependency boundaries for launcher, Docker, and optional renderer packages.
- `docs/ARCHITECTURE.md`: pipeline, module ownership, and folder-hygiene notes.
- `docs/TECHNICAL_OVERVIEW.zh-TW.md`: Chinese technical overview for the team.
- `docs/DATASET_TYPE_MAP.zh-TW.md`: beginner-friendly taxonomy for dataset families, storage choices, analysis tools, and rendering targets.
- `docs/USER_GUIDE.zh-TW.md`: beginner-friendly UI and daily-use guide.
- `docs/DOCS_INDEX.zh-TW.md`: suggested reading order and next-stage documentation cleanup plan.
- `docs/PRODUCT_POSITIONING.zh-TW.md`: Chinese product positioning note for the evolved Steam-like dataset launcher and virtual twin data pipeline.
- `docs/PROJECT_GTD.md`: current product status and next steps.
- `api_launcher/`: package that holds the launcher core, models, registry loading, and SQLite setup.
- `api_launcher/core.py`: CLI coordination, metadata crawl helpers, exports, and compatibility re-exports.
- `api_launcher/repository.py`: database repository used by both the CLI and Tk UI.
- `api_launcher/models.py`: provider/catalog dataclasses.
- `api_launcher/plans.py`: shared Download Plan JSON schema builder.
- `api_launcher/renderer_contracts.py`: shared IDs and bridge-asset contracts for downstream renderers such as `taichi_global_bathymetry.py`.
- `api_launcher/adapters/`: dataset-adapter interfaces. Adapters discover dataset records without downloading bulk data.
- `api_launcher/curation.py`: small, testable data-cleaning primitives for normalizing records after API/download ingestion.
- `api_launcher/db.py`: SQLite connection, paths, schema setup, and migrations.
- `api_launcher/registry.py`: JSON provider catalog loading and provider overlays.
- `api_launcher/integrations.py`: local integration profiles for database clients and optional AI summaries.
- `catalog/APIkeys_collection_reference.json`: the crawler credential reference file. The first entry is NOAA's `NOAA_NCEI_CDO_TOKEN` reference. Keep real key values out of this file; put real keys in your shell environment or a private `.env`.
- `APIkeys_collection.sqlite`: local SQLite database for providers, credential placeholders, and crawl metadata.
- `.env.example`: environment-variable template generated from the database.
- `catalog/api_keys.txt.template`: human-readable API key checklist generated from the database.
- `catalog/APIkeys_collection_catalog.json`: machine-readable provider catalog export.
- `catalog/APIkeys_collection_catalog.csv`: spreadsheet-friendly provider catalog export.
- `catalog/APIkeys_collection_catalog.md`: Markdown provider catalog export for review notes.
- `APIkeys_collection_ui.py`: compatibility entry point for the Tk launcher UI. The implementation lives in `frontends/tk/launcher_ui.py`.
- `frontends/`: UI and frontend-specific bridge code. Keep frontend concerns out of the backend data-management package.
- `renderers/taichi_global_bathymetry.py`: downstream Taichi visualization engine copied into this repo for bridge-asset integration.
- `.codex/skills/apikeys-collection-launcher/`: project-local Codex skill draft for AI-agent handoff and safe development workflows.
- `config/launcher_integrations.example.json`: cross-platform examples for external database tools and AI summary providers. Copy it to `launcher_integrations.local.json` for machine-specific paths and credentials.
- `catalog/APIkeys_collection_credentials.private.template.json`: local-only credential template for your own accounts/tokens.
- `.gitignore`: excludes filled private credential files and Python cache files.
- `catalog/provider_registry.sample.json`: sample format for adding future providers without editing the Python file.

## Pipeline Role

This folder is upstream preparation for a larger crawler/rendering pipeline:

```text
provider/API key reference -> dataset catalog -> raw download/import -> render bridge assets -> taichi_global_bathymetry.py render layer
```

`APIkeys_collection.py` should stay focused on API metadata and credential references. It intentionally does not download global datasets. The renderer-facing output should come later from a separate crawler/adapter that reads this catalog, fetches only the data you request, normalizes it, and writes compact local files for `taichi_global_bathymetry.py`.

In system terms:

- `providers` are upstream data platforms.
- `datasets` are provider-specific dataset entries.
- `dataset_sync_state` is the install/update state.
- `render_bridge_assets` are optimized local assets for the renderer.
- The Tk UI is the first control panel for browsing, checking, and planning downloads.

Built-in `Provider(...)` entries are bootstrap seeds, not authoritative metadata. The long-term source of truth should
be provider discovery APIs and official metadata pages. The crawler stores extracted hints in `crawl_results.extracted_json`
so provider-specific adapters can promote those hints into `datasets`.

Provider URLs are normalized through URL dictionaries and provider specs where possible. Dataset dictionaries should not
be hard-coded; they should be discovered from official APIs with bounded pagination loops. For example, the NOAA CDO
dataset adapter walks the `/datasets` endpoint until it reaches an empty page, a duplicate page, an error, or `max_pages`.

The Tk UI acts as a download guide:

```text
provider catalog -> dataset catalog -> selectable source list -> metadata crawl/self-check -> JSON download plan -> future downloader/importer
```

The current UI lists provider/database sources. Actual dataset-level packs, such as NOAA dataset IDs or NASA CMR collections, should be added through provider-specific adapters in a later stage.
Rows with detected remote metadata changes show a `Refresh` action at the right edge. In the current version this refreshes metadata only; later downloader/importer stages can reuse the same action for real local data refreshes.

The download plan is the launcher's cart/install queue. Users browse provider rows, add sources to the plan,
review the plan panel, and export a JSON task list for later dataset adapters. The exported file is intentionally
machine-readable so future workers can turn planned providers into real downloads, imports, and update checks.

The strict update target is local-vs-remote equivalence: each dataset should eventually have a remote fingerprint
and a local fingerprint. A row is current only when the local imported data matches the provider's current dataset
metadata/version/checksum. Provider pages are only a first approximation; precise checks require provider-specific
dataset adapters.

Local installs use a launcher registry instead of path/name guessing. `provider_installations` stores the stable
`install_id` and fingerprint for a managed source, while `provider_installation_assets` records owned assets such
as files, schemas, tables, or future SQL uninstall commands. This is meant to prevent duplicate installs and avoid
leaving dead registry entries when a source is unmanaged or removed.

Assets also carry provenance: `asset_role`, `source_format`, `source_uri`, and `schema_fingerprint`. This separates
official source imports from curated CSV/JSON/manual imports and derived analysis outputs. A user-written table pushed
back into SQL should be registered as `derived` or `curated`, not compared directly against upstream provider metadata.

SQL uninstall commands are generated only for validated identifiers and stored as registry metadata first. For example,
a MySQL database asset can store `DROP DATABASE IF EXISTS \`sample_db\`;`, but destructive execution stays disabled
until a database adapter can verify the target connection and ownership.

Dataset adapters should return `Dataset` records first, then let later downloader/importer workers create local assets.
This keeps discovery, download, import, and uninstall as separate stages.

Renderer contracts define stable IDs shared by the launcher and render layer. For `taichi_global_bathymetry.py`, the
current contracts are GEBCO 2025 topography (`topography_grid`) and HYG v3.8 stars (`star_catalog`), both targeting
`~/.cache/taichi_earth` bridge assets.

Provider discovery is seed-driven. `catalog/provider_discovery_seeds.json` contains built-in official source sites, while
`provider_discovery_seeds.local.json` is ignored by git and can hold user-added regional or project-specific source
sites. Discovery outputs reviewable candidates only; it never collects API secret values.

Think of providers as publishers or source stations, not the canonical database identity. A provider may expose many
datasets, and the same canonical dataset may later have multiple mirrors. Dataset identity and dedupe should be handled
by dataset names/IDs, versions, scope, and fingerprints, while providers remain provenance/download context.

Downloaded API data still needs curation. The `curation` layer is where raw records are renamed, type-cast,
deduplicated, checked for required fields, and eventually normalized for database/import targets.

The bridge layer is the contract between raw downloaded data and the renderer. Raw files may be NetCDF, Zarr,
GeoTIFF, GeoParquet, CSV, or provider-native formats. Bridge assets should be compact, indexed, and shaped for
`taichi_global_bathymetry.py` to load quickly.

## Quick Start

If you are on the current macOS handoff machine, prefer the existing Conda environment and do not install packages into `base`:

```bash
cd "/Users/yen-an/Library/CloudStorage/CloudMounter-Google#1/APIkeys_collection"
conda run -n metal_trade_312 python APIkeys_collection_ui.py
```

Generic CLI smoke:

```bash
python APIkeys_collection.py
```

On macOS/Linux, use `python3` if `python` is not mapped to Python 3. On Windows, use `py` if the `python`
command opens the Microsoft Store launcher:

```powershell
py APIkeys_collection.py
```

## Development Setup

Windows PowerShell:

```powershell
.\scripts\setup_env.ps1
.\scripts\run_ui.ps1
```

macOS/Linux:

```bash
./scripts/setup_env.sh
./scripts/run_ui.sh
```

The virtual environment, SQLite database, local secrets, and Python cache files are local machine state and are ignored by git.
On Windows, the setup script keeps the virtual environment under `%LOCALAPPDATA%\APIkeys_collection\venv-py313`
so package installs do not fight the synced project folder.
On the current macOS handoff machine, use `metal_trade_312` for installs/tests instead of `base`:

```bash
conda run -n metal_trade_312 python -m pip install -r requirements-dev.txt
conda run -n metal_trade_312 python -m unittest discover -s tests
```

Renderer dependencies are optional and heavier than the launcher dependencies:

```bash
python -m pip install -r requirements-renderer.txt
python renderers/taichi_global_bathymetry.py
```

## Local Integrations

The launcher can open your local database client without hard-coding one user's path. Copy the example config and edit it per machine:

```powershell
Copy-Item config\launcher_integrations.example.json launcher_integrations.local.json
```

`launcher_integrations.local.json` is ignored by git. Use it to choose MySQL Workbench, DBeaver, or another local database client. The same file also controls optional AI summaries, UI language, table column widths, and OAuth/device-login profile settings.

For no-login summaries, the default profile expects a local Ollama server at `http://localhost:11434/api/generate`. Install Ollama, pull a small model such as `gemma3:1b`, and keep `active_ai_summary_profile` set to `local_ollama`.

Gemini is available as an optional cloud profile. It can use `GEMINI_API_KEY`, or QR/device login when `GOOGLE_OAUTH_CLIENT_ID` is configured. Other OpenAI-compatible providers can be configured through `ai_summary_profiles`; if a provider supports OAuth device-code login, add its endpoints under that profile's `oauth_device`.

Important: logging in to an AI service is separate from choosing the model. The model used for generated descriptions is selected in the UI under `設定 > AI 輔助模型`.

Git identity helper:

```powershell
.\scripts\setup_git.ps1 -UserName "Your Name" -UserEmail "you@example.com"
```

## Docker

The Docker setup is for CLI checks and future downloader workers. The Tk UI should still run on the host machine.

```bash
docker compose run --rm launcher
```

On Windows/RaiDrive, the compose file intentionally does not bind-mount the project folder into `/app`.
The code is copied into the image at build time, while runtime SQLite state lives in the Docker volume
`apikeys_collection_state`.

The default action initializes the DB, seeds built-in providers, writes templates, and prints a summary.

To refresh the NOAA key reference and regenerate templates:

```bash
python APIkeys_collection.py \
  --init-db \
  --seed \
  --write-sample-key-reference APIkeys_collection_reference.json \
  --seed-key-reference \
  --generate-templates \
  --summary
```

## Useful Commands

```bash
# List all providers
python APIkeys_collection.py --list-providers

# List categories
python APIkeys_collection.py --list-categories

# List weather-related providers
python APIkeys_collection.py --list-providers --category weather

# Export the catalog for inspection or downstream crawler planning
python APIkeys_collection.py --export-json APIkeys_collection_catalog.json
python APIkeys_collection.py --export-csv APIkeys_collection_catalog.csv
python APIkeys_collection.py --export-markdown APIkeys_collection_catalog.md

# Crawl only small metadata pages for selected providers
python APIkeys_collection.py --crawl --provider noaa_ncei_cdo
python APIkeys_collection.py --crawl --category weather --max-bytes 65536

# Refresh download-guide status from latest metadata crawl results
python APIkeys_collection.py --self-check

# Discover dataset-level entries where an adapter exists
export NOAA_NCEI_CDO_TOKEN="your_token"
python APIkeys_collection.py --discover-datasets --provider noaa_ncei_cdo

# Write a private credentials template
python APIkeys_collection.py --write-credentials-template

# Launch the Tk download-guide UI
python APIkeys_collection_ui.py
```

Run tests:

```bash
python -m unittest discover -s tests
```

## Database Tables

- `providers`: provider registry, auth requirements, docs/API URLs.
- `template_keys`: environment variable placeholders for keys or owned credentials.
- `crawl_results`: small metadata fetch results, status, title, content hash, excerpt, and regex-extracted metadata hints.
- `provider_download_state`: download-guide status, including last check time, last download/import status, remote hash, and local dataset path.
- `provider_installations`: launcher-owned install identities for provider-level managed sources.
- `provider_installation_assets`: files, database objects, or future SQL uninstall commands owned by an install identity.
- `datasets`: dataset-level catalog entries under each provider.
- `dataset_sync_state`: per-dataset local-vs-remote equivalence status, raw path, curated path, and bridge asset pointer.
- `render_bridge_assets`: renderer-facing assets produced from raw data, intended for `taichi_global_bathymetry.py`.

## Extending

Add new `Provider(...)` entries in `PROVIDERS`.

For no-code registry updates, generate a sample JSON file and seed from it:

```bash
python APIkeys_collection.py --write-sample-registry provider_registry.sample.json
python APIkeys_collection.py --seed-json provider_registry.sample.json --generate-templates
```

Keep provider entries constrained to official documentation and metadata endpoints. Avoid adding bulk download URLs unless they are clearly marked as catalog-only and are not crawled for data payloads.

## Credential Reference Rules

`catalog/APIkeys_collection_reference.json` is a reference map, not a secret store. A reference entry should describe:

- `provider_id`: the provider in SQLite, such as `noaa_ncei_cdo`.
- `env_var`: the environment variable your crawler should read, such as `NOAA_NCEI_CDO_TOKEN`.
- `docs_url` and `signup_url`: official places to confirm usage and request your own key.
- `usage`: how the downstream crawler should attach the key.

The `value` field should stay empty unless you are keeping a strictly local, private copy outside version control.

For owned account credentials, generate a private template:

```bash
python APIkeys_collection.py --write-credentials-template
```

Copy `APIkeys_collection_credentials.private.template.json` to `APIkeys_collection_credentials.private.json` if you
choose to keep local plaintext values. Prefer environment variables when possible.
