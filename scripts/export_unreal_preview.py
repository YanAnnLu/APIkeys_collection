#!/usr/bin/env python3
"""Export lightweight Unreal preview assets from Taichi renderer caches.

The preview mesh is intentionally small. The long-term virtual twin path is a
camera-driven tile/LOD stream where Unreal requests only the samples needed for
the current view mode.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    import numpy as np
except ImportError:  # pragma: no cover - exercised only on machines without renderer deps
    np = None  # type: ignore[assignment]

from api_launcher.rendering_profiles import build_render_backend_profile
from api_launcher.tile_manifests import build_global_grid_manifest, write_tile_manifest


DEFAULT_CACHE_DIR = Path.home() / ".cache" / "taichi_earth"
DEFAULT_TOPO = DEFAULT_CACHE_DIR / "gebco_2025_topo_cache_step240.npy"
DEFAULT_STARS = DEFAULT_CACHE_DIR / "stars_cache.npy"
DEFAULT_BRIDGE_SUBDIR = "APIkeysCollection"


MATERIALS = (
    ("deep_ocean", (-11000, -3500), (0.02, 0.05, 0.18)),
    ("ocean", (-3500, 0), (0.02, 0.18, 0.45)),
    ("lowland", (0, 1200), (0.08, 0.32, 0.14)),
    ("highland", (1200, 3500), (0.42, 0.32, 0.22)),
    ("snow", (3500, 9000), (0.82, 0.84, 0.82)),
)


CAMERA_STREAMING_PROFILES = {
    "first_person": {
        "intent": "near-field terrain inspection",
        "lod_bias": "highest nearby tiles, aggressive far culling",
        "recommended_tile_degrees": 0.25,
        "stream_radius_tiles": 10,
        "notes": "Use for ground-level or aircraft-like views where local slope/detail matters.",
    },
    "second_person": {
        "intent": "object-follow or cinematic target view",
        "lod_bias": "high around target, medium around camera path",
        "recommended_tile_degrees": 1.0,
        "stream_radius_tiles": 8,
        "notes": "Useful when camera tracks a point of interest instead of the user's position.",
    },
    "third_person_orbit": {
        "intent": "planet-scale overview",
        "lod_bias": "coarse global tiles with selective refinement under cursor/focus",
        "recommended_tile_degrees": 5.0,
        "stream_radius_tiles": 6,
        "notes": "Use for global navigation, minimap, or strategic virtual twin views.",
    },
}


def main() -> int:
    return main_from_args_for_test(None)


def main_from_args_for_test(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export lightweight Unreal preview assets from Taichi Earth caches.")
    parser.add_argument("--topography", default=str(DEFAULT_TOPO), help="Path to cached topography .npy")
    parser.add_argument("--stars", default=str(DEFAULT_STARS), help="Path to cached HYG stars .npy")
    parser.add_argument("--project", default="", help="Path to an Unreal .uproject. Used to infer the Content output directory.")
    parser.add_argument("--out", default="", help="Output directory inside the Unreal project Content tree")
    parser.add_argument("--bridge-subdir", default=DEFAULT_BRIDGE_SUBDIR, help="Subdirectory under Content for generated assets")
    parser.add_argument("--sample-step", type=int, default=2, help="Grid decimation step for OBJ preview mesh")
    parser.add_argument("--tile-lod", type=int, default=0, help="LOD number for the preview tile manifest")
    parser.add_argument("--tile-degrees", type=float, default=30.0, help="Coarse global tile size in degrees for the preview manifest")
    args = parser.parse_args(argv)

    if np is None:
        raise SystemExit(
            "Missing optional renderer dependency: numpy. Install renderer dependencies with "
            "`py -m pip install -r requirements-renderer.txt`."
        )

    out_dir = resolve_output_dir(args.out, args.project, args.bridge_subdir)
    out_dir.mkdir(parents=True, exist_ok=True)
    topo_path = Path(args.topography)
    stars_path = Path(args.stars)
    if not topo_path.exists():
        raise SystemExit(f"Topography cache not found: {topo_path}")

    topo = np.load(topo_path)
    sampled = topo[:: max(1, args.sample_step), :: max(1, args.sample_step)]
    obj_path = out_dir / "EarthPreview.obj"
    mtl_path = out_dir / "EarthPreview.mtl"
    export_earth_obj(sampled, obj_path, mtl_path.name)

    stars_csv = out_dir / "StarsPreview.csv"
    star_count = 0
    if stars_path.exists():
        stars = np.load(stars_path)
        export_stars_csv(stars, stars_csv, max_stars=2000)
        star_count = min(len(stars), 2000)

    write_mtl(mtl_path)
    tile_manifest_path = out_dir / "TileManifest.json"
    tile_manifest = build_global_grid_manifest(
        dataset_uid="gebco:2025",
        version="2025",
        lod=args.tile_lod,
        lon_step_degrees=args.tile_degrees,
        lat_step_degrees=args.tile_degrees,
        uri_template="Content/APIkeysCollection/Preview/Tiles/{tile_id}.npy",
        tile_format="npy:int16:elevation",
        role="topography_tile",
        metadata={
            "status": "preview_index_only",
            "source": str(topo_path),
            "note": "Tiles are not materialized yet. This manifest defines the future Unreal/Taichi streaming contract.",
        },
    )
    write_tile_manifest(tile_manifest, tile_manifest_path)
    manifest = build_manifest(
        topo_path=topo_path,
        stars_path=stars_path,
        topo_shape=topo.shape,
        exported_shape=sampled.shape,
        star_count=star_count,
        obj_path=obj_path,
        mtl_path=mtl_path,
        stars_csv=stars_csv if stars_csv.exists() else None,
        tile_manifest_path=tile_manifest_path,
        project_path=Path(args.project) if args.project else None,
        bridge_subdir=args.bridge_subdir,
    )
    (out_dir / "APIkeysBridgeManifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Exported Unreal preview assets to {out_dir}")
    return 0


def resolve_output_dir(out: str, project: str, bridge_subdir: str) -> Path:
    if out:
        return Path(out)
    if not project:
        raise SystemExit("Either --out or --project is required.")
    project_path = Path(project)
    if project_path.suffix.lower() != ".uproject":
        raise SystemExit(f"--project must point to a .uproject file: {project_path}")
    return project_path.parent / "Content" / bridge_subdir / "Preview"


def build_manifest(
    topo_path: Path,
    stars_path: Path,
    topo_shape: tuple[int, ...],
    exported_shape: tuple[int, ...],
    star_count: int,
    obj_path: Path,
    mtl_path: Path,
    stars_csv: Path | None,
    tile_manifest_path: Path,
    project_path: Path | None,
    bridge_subdir: str,
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "bridge_kind": "unreal_preview",
        "project_path": str(project_path) if project_path else "",
        "unreal_mount_root": f"/Game/{bridge_subdir}/Preview",
        "source_topography": str(topo_path),
        "source_stars": str(stars_path),
        "topography_shape": list(topo_shape),
        "exported_shape": list(exported_shape),
        "star_count": star_count,
        "assets": {
            "earth_obj": str(obj_path),
            "earth_mtl": str(mtl_path),
            "stars_csv": str(stars_csv) if stars_csv else "",
            "tile_manifest": str(tile_manifest_path),
        },
        "camera_driven_streaming": CAMERA_STREAMING_PROFILES,
        "render_backend_profiles": {
            "taichi_reference": build_render_backend_profile("taichi").__dict__,
            "unreal_frontend": build_render_backend_profile("unreal").__dict__,
        },
        "future_pipeline": [
            "Keep raw scientific datasets in the launcher registry.",
            "Build normalized renderer-ready tiles with stable dataset IDs and version metadata.",
            "Expose a local tile service or file-backed tile manifest to Unreal.",
            "Let Unreal request tiles by camera mode, position, frustum, and desired LOD.",
            "Cache imported/generated Unreal assets under Content/APIkeysCollection without duplicating raw archives.",
        ],
        "notes": "Preview assets for Unreal import. This is a low-resolution bridge, not the final tiled virtual twin pipeline.",
    }


def export_earth_obj(elevation: np.ndarray, path: Path, material_library: str) -> None:
    rows, cols = elevation.shape
    radius = 100.0
    height_scale = 0.0015
    vertices = []
    for i in range(rows):
        lat = math.radians(90.0 - 180.0 * i / max(1, rows - 1))
        cos_lat = math.cos(lat)
        sin_lat = math.sin(lat)
        for j in range(cols):
            lon = math.radians(-180.0 + 360.0 * j / cols)
            elev = float(elevation[i, j])
            r = radius + elev * height_scale
            vertices.append((r * cos_lat * math.cos(lon), r * cos_lat * math.sin(lon), r * sin_lat))

    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write("# APIkeys_collection Unreal Earth preview\n")
        handle.write(f"mtllib {material_library}\n")
        for x, y, z in vertices:
            handle.write(f"v {x:.5f} {y:.5f} {z:.5f}\n")
        current_material = ""
        for i in range(rows - 1):
            for j in range(cols):
                j2 = (j + 1) % cols
                avg = float(
                    elevation[i, j].astype(np.float32)
                    + elevation[i + 1, j].astype(np.float32)
                    + elevation[i, j2].astype(np.float32)
                    + elevation[i + 1, j2].astype(np.float32)
                ) / 4.0
                material = material_for_elevation(avg)
                if material != current_material:
                    handle.write(f"usemtl {material}\n")
                    current_material = material
                a = i * cols + j + 1
                b = (i + 1) * cols + j + 1
                c = (i + 1) * cols + j2 + 1
                d = i * cols + j2 + 1
                handle.write(f"f {a} {b} {c} {d}\n")


def write_mtl(path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for name, _bounds, color in MATERIALS:
            handle.write(f"newmtl {name}\n")
            handle.write(f"Kd {color[0]:.4f} {color[1]:.4f} {color[2]:.4f}\n")
            handle.write("Ka 0.0000 0.0000 0.0000\n")
            handle.write("Ks 0.0500 0.0500 0.0500\n\n")


def material_for_elevation(value: float) -> str:
    for name, (low, high), _color in MATERIALS:
        if low <= value < high:
            return name
    return MATERIALS[-1][0]


def export_stars_csv(stars: np.ndarray, path: Path, max_stars: int) -> None:
    subset = stars[:max_stars]
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write("x,y,z,mag\n")
        for x, y, z, mag in subset:
            handle.write(f"{float(x):.6f},{float(y):.6f},{float(z):.6f},{float(mag):.3f}\n")


if __name__ == "__main__":
    raise SystemExit(main())
