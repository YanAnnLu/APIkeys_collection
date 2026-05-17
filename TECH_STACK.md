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

## Validation

Core validation:

```powershell
py -m unittest discover -s tests
$env:PYTHONDONTWRITEBYTECODE='1'; py -m py_compile APIkeys_collection.py APIkeys_collection_ui.py renderers\taichi_global_bathymetry.py api_launcher\core.py api_launcher\db.py api_launcher\models.py api_launcher\repository.py
docker compose run --rm --build launcher
```

Renderer runtime validation is separate because it needs GPU/windowing support and optional heavy packages.
