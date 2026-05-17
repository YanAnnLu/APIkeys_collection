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

- `APIkeys_collection.py` is still the main core file. It now exposes the repository API used by `APIkeys_collection_ui.py`.
- Built-in providers are now loaded from `APIkeys_collection_catalog.json` with a small Python overlay for fields that should not clutter the catalog, such as extra credential env vars.
- `APIkeys_collection_ui.py` is a Tk launcher prototype for selecting providers and exporting a download plan.
- `APIkeys_collection.sqlite` currently contains provider-level catalog state.
- Dataset-level adapters are not implemented yet.

Current SQLite counts observed on this machine:

- `providers`: 25
- `template_keys`: 18
- `provider_download_state`: 25
- `crawl_results`: 4
- `datasets`: 0
- `dataset_sync_state`: 0
- `render_bridge_assets`: 0

## Structural Concern

The main file is too large. It was reduced by moving the provider registry out of Python, but it is still over 1000 lines. The next refactor should split it into modules instead of continuing to grow one script.

Suggested module split:

- `api_launcher/models.py`: dataclasses such as `Provider` and `ProviderCatalogEntry`.
- `api_launcher/registry.py`: built-in providers and JSON registry loading.
- `api_launcher/db.py`: SQLite connection and schema migrations.
- `api_launcher/repository.py`: `ApiCatalogRepository`.
- `api_launcher/crawl.py`: metadata fetch and crawl status updates.
- `api_launcher/exports.py`: JSON/CSV/Markdown/template writers.
- `APIkeys_collection.py`: thin CLI compatibility wrapper.

## Cross-Platform Notes

- Windows on this machine uses `py`, not `python`.
- macOS should normally use `python3`.
- Keep project files UTF-8 with LF line endings.
- SQLite state on synced drives can conflict. Prefer treating `*.sqlite` as rebuildable state or copy it locally before heavy writes.
- Git for Windows was installed on 2026-05-17 and the repo was initialized on `main`.
- GitHub CLI was installed on 2026-05-17, but it is not authenticated yet. Run `gh auth login`.
- Docker configuration files exist for CLI/dev-worker checks, but Docker Desktop is not installed on this Windows machine yet.

## Next Build Target

1. Refactor the single large core file into a small package.
2. Keep the UI import path stable by re-exporting the public API from `APIkeys_collection.py`.
3. Add the first dataset adapter candidate: GEBCO or NOAA NCEI CDO.
4. Add download queue state that matches the launcher metaphor: queued, checking, downloading, paused, installed, update_available, failed.
