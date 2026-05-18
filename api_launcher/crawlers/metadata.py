from __future__ import annotations

import re


def safe_dataset_id(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip().lower()).strip("_")
    return cleaned or "dataset"


def tuple_names(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    names = []
    for item in value:
        if isinstance(item, dict):
            name = str(item.get("name") or item.get("id") or "").strip()
        else:
            name = str(item).strip()
        if name:
            names.append(name)
    return tuple(names)


def merge_categories(*groups: tuple[str, ...]) -> tuple[str, ...]:
    values: list[str] = []
    seen: set[str] = set()
    for group in groups:
        for value in group:
            normalized = safe_dataset_id(value).replace("-", "_")
            if normalized and normalized not in seen:
                values.append(normalized)
                seen.add(normalized)
    return tuple(values)


def first_link_url(links: object, groups: tuple[str, ...]) -> str:
    if not isinstance(links, dict):
        return ""
    for group in groups:
        values = links.get(group)
        if not isinstance(values, list):
            continue
        for item in values:
            if isinstance(item, dict) and item.get("url"):
                return str(item["url"])
    return ""


def choose_native_format(formats: tuple[str, ...]) -> str:
    preferred = (
        "parquet",
        "geoparquet",
        "zarr",
        "netcdf",
        "hdf5",
        "geotiff",
        "tiff",
        "grib",
        "geojson",
        "shapefile",
        "csv",
        "json",
        "api",
        "native",
    )
    lowered = {safe_dataset_id(value).replace("-", "_"): value.lower() for value in formats}
    for value in preferred:
        if value in lowered:
            return lowered[value]
    return formats[0].lower() if formats else "unknown"


def temporal_coverage(start: object, end: object) -> str:
    start_text = str(start or "").strip()
    end_text = str(end or "").strip()
    if start_text and end_text:
        return f"{start_text}/{end_text}"
    return start_text or end_text


def infer_data_family(text: str) -> str:
    lowered = text.lower()
    if any(value in lowered for value in ("gbif", "biodiversity", "species occurrence", "occurrence", "taxon")):
        return "biodiversity_occurrence"
    if any(value in lowered for value in ("ais", "vessel", "trajectory", "ship")):
        return "spatiotemporal_trajectory"
    if any(value in lowered for value in ("cloud", "imagery", "satellite", "raster", "abi", "goes")):
        return "raster_or_grid"
    if any(value in lowered for value in ("netcdf", "grib", "grid", "sst", "sea surface temperature")):
        return "grid_or_array"
    if any(value in lowered for value in ("boundary", "polygon", "shapefile", "geojson", "gis")):
        return "gis"
    if any(value in lowered for value in ("hourly", "daily", "time series", "timeseries")):
        return "timeseries"
    return "table_or_document"


def storage_hint_for_family(data_family: str) -> str:
    hints = {
        "biodiversity_occurrence": "duckdb_postgis_or_partitioned_occurrence_files",
        "spatiotemporal_trajectory": "filesystem_or_object_storage_then_partitioned_columnar_store",
        "raster_or_grid": "netcdf_zarr_cog_or_object_storage",
        "grid_or_array": "netcdf_zarr_hdf5_or_object_storage",
        "gis": "geopackage_geojson_shapefile_or_postgis",
        "timeseries": "timeseries_db_or_partitioned_files",
    }
    return hints.get(data_family, "filesystem_or_sql_after_review")


def sql_role_for_family(data_family: str) -> str:
    if data_family in {"spatiotemporal_trajectory", "raster_or_grid", "grid_or_array", "gis"}:
        return "metadata_index_or_curated_sample_table"
    return "primary_or_curated_table_after_review"


def analysis_hint_for_family(data_family: str) -> str:
    hints = {
        "biodiversity_occurrence": "duckdb_postgis_geopandas_or_gbif_tools",
        "spatiotemporal_trajectory": "duckdb_geopandas_postgis_dask_spark",
        "raster_or_grid": "xarray_rioxarray_dask_or_gdal",
        "grid_or_array": "xarray_dask_or_netcdf_tools",
        "gis": "qgis_postgis_geopandas",
        "timeseries": "duckdb_timescaledb_clickhouse",
    }
    return hints.get(data_family, "python_sql_or_domain_adapter")


def viewer_hint_for_family(data_family: str) -> str:
    hints = {
        "biodiversity_occurrence": "map_points_heatmap_or_species_filter",
        "spatiotemporal_trajectory": "map_trajectory_heatmap_or_timeline",
        "raster_or_grid": "globe_texture_or_time_animation",
        "grid_or_array": "map_layer_or_timeseries_preview",
        "gis": "map_layer_or_unreal_globe_overlay",
        "timeseries": "tradingview_like_chart",
    }
    return hints.get(data_family, "table_or_document_preview")


def matches_any_term(text: str, search_terms: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(term.lower() in lowered for term in search_terms)
