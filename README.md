# APIkeys_collection

`APIkeys_collection.py` builds a local, extensible catalog of public data-provider API metadata.

It is designed as a local catalog, download guide, update checker, and bridge planner for
scientific/geospatial/financial data sources. It is crawler preparation, not secret harvesting:

- Catalogs official docs, API base URLs, sign-up pages, auth type, and categories.
- Creates a local SQLite database: `APIkeys_collection.sqlite`.
- Generates `.env.example` and `api_keys.txt.template`.
- Optionally fetches small metadata pages from whitelisted official URLs.
- Does not search for leaked keys, scrape secrets, or download bulk datasets.

## Folder Layout

All default paths are resolved relative to this folder, not relative to your terminal's current working directory.
You can move the whole `APIkeys_collection/` folder elsewhere and the crawler will still find its database,
reference file, templates, and exports.

- `APIkeys_collection.py`: thin compatibility entry point for the CLI and existing UI imports.
- `api_launcher/`: package that holds the launcher core, models, registry loading, and SQLite setup.
- `api_launcher/core.py`: CLI coordination, metadata crawl helpers, exports, and compatibility re-exports.
- `api_launcher/repository.py`: database repository used by both the CLI and Tk UI.
- `api_launcher/models.py`: provider/catalog dataclasses.
- `api_launcher/db.py`: SQLite connection, paths, schema setup, and migrations.
- `api_launcher/registry.py`: JSON provider catalog loading and provider overlays.
- `api_launcher/integrations.py`: local integration profiles for database clients and optional AI summaries.
- `APIkeys_collection_reference.json`: the crawler credential reference file. The first entry is NOAA's `NOAA_NCEI_CDO_TOKEN` reference. Keep real key values out of this file; put real keys in your shell environment or a private `.env`.
- `APIkeys_collection.sqlite`: local SQLite database for providers, credential placeholders, and crawl metadata.
- `.env.example`: environment-variable template generated from the database.
- `api_keys.txt.template`: human-readable API key checklist generated from the database.
- `APIkeys_collection_catalog.json`: machine-readable provider catalog export.
- `APIkeys_collection_catalog.csv`: spreadsheet-friendly provider catalog export.
- `APIkeys_collection_catalog.md`: Markdown provider catalog export for review notes.
- `APIkeys_collection_ui.py`: lightweight Tk download-guide UI. It lets you browse provider/database sources, run metadata checks, and export a download plan.
- `launcher_integrations.example.json`: cross-platform examples for external database tools and AI summary providers. Copy it to `launcher_integrations.local.json` for machine-specific paths and credentials.
- `APIkeys_collection_credentials.private.template.json`: local-only credential template for your own accounts/tokens.
- `.gitignore`: excludes filled private credential files and Python cache files.
- `provider_registry.sample.json`: sample format for adding future providers without editing the Python file.

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

The bridge layer is the contract between raw downloaded data and the renderer. Raw files may be NetCDF, Zarr,
GeoTIFF, GeoParquet, CSV, or provider-native formats. Bridge assets should be compact, indexed, and shaped for
`taichi_global_bathymetry.py` to load quickly.

## Quick Start

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
.\setup_env.ps1
.\run_ui.ps1
```

macOS/Linux:

```bash
./setup_env.sh
./run_ui.sh
```

The virtual environment, SQLite database, local secrets, and Python cache files are local machine state and are ignored by git.
On Windows, the setup script keeps the virtual environment under `%LOCALAPPDATA%\APIkeys_collection\venv-py313`
so package installs do not fight the synced project folder.

## Local Integrations

The launcher can open your local database client without hard-coding one user's path. Copy the example config and edit it per machine:

```powershell
Copy-Item launcher_integrations.example.json launcher_integrations.local.json
```

`launcher_integrations.local.json` is ignored by git. Use it to choose MySQL Workbench, DBeaver, or another local database client. The same file also controls optional AI summaries.

For no-login summaries, the default profile expects a local Ollama server at `http://localhost:11434/api/generate`. Install Ollama, pull a small model such as `gemma3:1b`, and keep `active_ai_summary_profile` set to `local_ollama`.

Gemini is available as an optional cloud profile. Enable it only if you want that path and have `GEMINI_API_KEY` set in your environment.

Git identity helper:

```powershell
.\setup_git.ps1 -UserName "Your Name" -UserEmail "you@example.com"
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

## Database Tables

- `providers`: provider registry, auth requirements, docs/API URLs.
- `template_keys`: environment variable placeholders for keys or owned credentials.
- `crawl_results`: small metadata fetch results, status, title, content hash, excerpt, and regex-extracted metadata hints.
- `provider_download_state`: download-guide status, including last check time, last download/import status, remote hash, and local dataset path.
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

`APIkeys_collection_reference.json` is a reference map, not a secret store. A reference entry should describe:

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
