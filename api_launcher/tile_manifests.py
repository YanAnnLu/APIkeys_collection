from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from typing import Any


@dataclasses.dataclass(frozen=True)
class GeoBounds:
    west: float
    south: float
    east: float
    north: float

    def as_dict(self) -> dict[str, float]:
        return dataclasses.asdict(self)


@dataclasses.dataclass(frozen=True)
class TileAsset:
    tile_id: str
    dataset_uid: str
    version: str
    bounds: GeoBounds
    lod: int
    resolution: str
    uri: str
    byte_size: int = 0
    checksum: str = ""
    format: str = ""
    role: str = "data_tile"
    metadata: dict[str, Any] = dataclasses.field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        data = dataclasses.asdict(self)
        data["bounds"] = self.bounds.as_dict()
        return data


@dataclasses.dataclass(frozen=True)
class TileManifest:
    manifest_id: str
    dataset_uid: str
    version: str
    schema_version: int
    coordinate_reference_system: str
    root_bounds: GeoBounds
    tiles: tuple[TileAsset, ...]
    source_manifest: str = ""
    generated_at_utc: str = ""
    metadata: dict[str, Any] = dataclasses.field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "manifest_id": self.manifest_id,
            "dataset_uid": self.dataset_uid,
            "version": self.version,
            "coordinate_reference_system": self.coordinate_reference_system,
            "root_bounds": self.root_bounds.as_dict(),
            "source_manifest": self.source_manifest,
            "generated_at_utc": self.generated_at_utc,
            "metadata": self.metadata,
            "tiles": [tile.as_dict() for tile in self.tiles],
        }


def tile_id(dataset_uid: str, version: str, lod: int, x: int, y: int) -> str:
    safe_dataset = _safe_token(dataset_uid)
    safe_version = _safe_token(version or "unversioned")
    return f"{safe_dataset}/{safe_version}/lod{lod}/x{x}/y{y}"


def build_global_grid_manifest(
    dataset_uid: str,
    version: str,
    lod: int,
    lon_step_degrees: float,
    lat_step_degrees: float,
    uri_template: str,
    tile_format: str,
    role: str = "data_tile",
    metadata: dict[str, Any] | None = None,
) -> TileManifest:
    if lon_step_degrees <= 0 or lat_step_degrees <= 0:
        raise ValueError("tile steps must be positive")
    lon_count = round(360.0 / lon_step_degrees)
    lat_count = round(180.0 / lat_step_degrees)
    if abs(lon_count * lon_step_degrees - 360.0) > 1e-6:
        raise ValueError("longitude step must evenly divide 360 degrees")
    if abs(lat_count * lat_step_degrees - 180.0) > 1e-6:
        raise ValueError("latitude step must evenly divide 180 degrees")

    tiles = []
    for y in range(lat_count):
        north = 90.0 - y * lat_step_degrees
        south = north - lat_step_degrees
        for x in range(lon_count):
            west = -180.0 + x * lon_step_degrees
            east = west + lon_step_degrees
            current_id = tile_id(dataset_uid, version, lod, x, y)
            uri = uri_template.format(
                dataset_uid=dataset_uid,
                version=version,
                lod=lod,
                x=x,
                y=y,
                tile_id=current_id,
            )
            tiles.append(
                TileAsset(
                    tile_id=current_id,
                    dataset_uid=dataset_uid,
                    version=version,
                    bounds=GeoBounds(west=west, south=south, east=east, north=north),
                    lod=lod,
                    resolution=f"{lon_step_degrees:g}x{lat_step_degrees:g}deg",
                    uri=uri,
                    format=tile_format,
                    role=role,
                )
            )
    return TileManifest(
        manifest_id=f"{_safe_token(dataset_uid)}:{_safe_token(version or 'unversioned')}:lod{lod}",
        dataset_uid=dataset_uid,
        version=version,
        schema_version=1,
        coordinate_reference_system="EPSG:4326",
        root_bounds=GeoBounds(west=-180.0, south=-90.0, east=180.0, north=90.0),
        tiles=tuple(tiles),
        metadata=metadata or {},
    )


def write_tile_manifest(manifest: TileManifest, path: str | Path) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest.as_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output


def read_tile_manifest(path: str | Path) -> TileManifest:
    data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    return TileManifest(
        manifest_id=str(data["manifest_id"]),
        dataset_uid=str(data["dataset_uid"]),
        version=str(data.get("version") or ""),
        schema_version=int(data.get("schema_version") or 1),
        coordinate_reference_system=str(data.get("coordinate_reference_system") or "EPSG:4326"),
        root_bounds=_bounds_from_dict(data["root_bounds"]),
        source_manifest=str(data.get("source_manifest") or ""),
        generated_at_utc=str(data.get("generated_at_utc") or ""),
        metadata=dict(data.get("metadata") or {}),
        tiles=tuple(_tile_from_dict(item) for item in data.get("tiles") or []),
    )


def _tile_from_dict(data: dict[str, Any]) -> TileAsset:
    return TileAsset(
        tile_id=str(data["tile_id"]),
        dataset_uid=str(data["dataset_uid"]),
        version=str(data.get("version") or ""),
        bounds=_bounds_from_dict(data["bounds"]),
        lod=int(data.get("lod") or 0),
        resolution=str(data.get("resolution") or ""),
        uri=str(data.get("uri") or ""),
        byte_size=int(data.get("byte_size") or 0),
        checksum=str(data.get("checksum") or ""),
        format=str(data.get("format") or ""),
        role=str(data.get("role") or "data_tile"),
        metadata=dict(data.get("metadata") or {}),
    )


def _bounds_from_dict(data: dict[str, Any]) -> GeoBounds:
    return GeoBounds(
        west=float(data["west"]),
        south=float(data["south"]),
        east=float(data["east"]),
        north=float(data["north"]),
    )


def _safe_token(value: str) -> str:
    clean = "".join(char if char.isalnum() or char in {"_", "-"} else "_" for char in value.strip())
    return clean.strip("_") or "unknown"
