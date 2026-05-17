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
direct HTTP(S) URLs, chunk progress, `.part` files, HTTP Range resume, and atomic
rename into the final target path. Dataset-specific API adapters should either
produce direct URLs for this adapter or implement the same `DownloadAdapter`
protocol.

`APIkeys_collection_ui.py` can now submit download-plan rows into the
nonblocking queue, display job progress, and pause/resume/cancel selected jobs.
The UI intentionally starts only rows with an API/download URL; provider-specific
adapters should later decide how catalog pages become real dataset files.

## Cross-platform Path and Encoding Rules

- Source files are UTF-8 with LF endings. See `.editorconfig` and `.gitattributes`.
- Local machine paths belong in ignored `*.local.json` files, not in tracked code.
- Startup path checks live in `api_launcher/environment.py` and should run before
  expensive downloader or renderer work.
- Avoid shell-specific path assumptions; use `pathlib.Path` and `resolve_project_path()`
  for project-local files.

## Validation

Core validation:

```powershell
py -m unittest discover -s tests
$env:PYTHONDONTWRITEBYTECODE='1'; py -m py_compile APIkeys_collection.py APIkeys_collection_ui.py renderers\taichi_global_bathymetry.py api_launcher\core.py api_launcher\db.py api_launcher\models.py api_launcher\repository.py
docker compose run --rm --build launcher
```

Renderer runtime validation is separate because it needs GPU/windowing support and optional heavy packages.
