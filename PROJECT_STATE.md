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
- Built-in providers are now loaded from `APIkeys_collection_catalog.json` with a small Python overlay for fields that should not clutter the catalog, such as extra credential env vars.
- `APIkeys_collection_ui.py` is a Tk launcher prototype for selecting providers and exporting a download plan.
- `APIkeys_collection.sqlite` currently contains provider-level catalog state.
- Dataset-level adapter interfaces now exist, but provider-specific adapters such as GEBCO or NOAA are not implemented yet.

Current SQLite counts observed on this machine:

- `providers`: 25
- `template_keys`: 18
- `provider_download_state`: 25
- `crawl_results`: 4
- `datasets`: 0
- `dataset_sync_state`: 0
- `render_bridge_assets`: 0

## Structural Progress

The root `APIkeys_collection.py` is now a thin compatibility entry point. The old core has moved into the
`api_launcher` package, and the first stable modules have been split out:

- `api_launcher/models.py`: dataclasses such as `Provider` and `ProviderCatalogEntry`.
- `api_launcher/registry.py`: provider catalog JSON loading and provider overlays.
- `api_launcher/db.py`: project paths, SQLite connection, timestamps, and schema setup.
- `api_launcher/repository.py`: provider seeding, provider queries, UI catalog entries, and starred preferences.
- `api_launcher/adapters/`: dataset adapter interface and stable dataset UID helper.
- `api_launcher/core.py`: current crawl, export, and CLI coordination layer.
- `APIkeys_collection.py`: thin CLI/UI compatibility wrapper.

The next refactor should split `api_launcher/core.py` further into crawl, exports, and CLI modules.

## Launcher Features

- Provider rows can be starred in the Tk UI. Starred rows are persisted in SQLite through
  `provider_preferences` and sort above normal rows.
- The sidebar includes a starred-only view for important data sources.
- Provider descriptions now open in an on-demand right-side drawer instead of a permanently cramped side panel.
- The Tk UI now uses ratio-based sizing for the window, sidebar, detail drawer, row height, and table columns so it behaves better across Windows/macOS displays and DPI settings.
- Users can add new provider/API sources and edit launcher descriptions directly from the UI.
- The UI now has an explicit Download Plan panel, which acts like a cart/install queue for selected data sources.
  Exports include a plan name, provider count, planned status, priority, and target fields for future workers.
- Provider-level install identity is now represented by `provider_installations.install_id` plus a fingerprint.
  Installation assets can be registered in `provider_installation_assets`, including future SQL uninstall commands.
  UI removal currently marks registry state as removed and does not execute destructive SQL until database adapters exist.
- SQL database assets can now generate safe uninstall metadata for MySQL/MariaDB and PostgreSQL after validating the
  database identifier. Execution is still intentionally blocked.
- Local database tools are profile-driven through `launcher_integrations.local.json`; MySQL Workbench is only the current user's profile, not a hard-coded app dependency.
- AI-generated provider descriptions are profile-driven too. The default example uses local Ollama for no-login summaries, while Gemini remains an optional API-key profile.

## Cross-Platform Notes

- Windows on this machine uses `py`, not `python`.
- macOS should normally use `python3`.
- Keep project files UTF-8 with LF line endings.
- SQLite state on synced drives can conflict. Prefer treating `*.sqlite` as rebuildable state or copy it locally before heavy writes.
- Git for Windows was installed on 2026-05-17 and the repo was initialized on `main`.
- GitHub CLI was installed and authenticated as `YanAnnLu` on 2026-05-17.
- Docker Desktop 4.73.0 is installed and verified on this Windows machine.
- WSL is installed for Docker Desktop; the `docker-desktop` WSL distro runs as WSL2.
- Docker Compose is verified with `docker compose run --rm --build launcher`.
- The compose file does not bind-mount the RaiDrive project folder because that path did not appear inside the Linux container. Runtime SQLite state lives in the named Docker volume.

## Next Build Target

1. Refactor the single large core file into a small package.
2. Keep the UI import path stable by re-exporting the public API from `APIkeys_collection.py`.
3. Add the first dataset adapter candidate: GEBCO or NOAA NCEI CDO.
4. Add download queue state that matches the launcher metaphor: queued, checking, downloading, paused, installed, update_available, failed.
