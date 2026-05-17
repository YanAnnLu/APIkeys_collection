import taichi as ti
import numpy as np
import xarray as xr
import os
import platform
import sys
import matplotlib.pyplot as plt
import math
import time
import datetime
import pandas as pd
from tqdm import tqdm
import urllib.request

try:
    from api_launcher.renderer_contracts import (
        GEBCO_2025_OPENDAP_URL,
        GEBCO_2025_TOPOGRAPHY_CONTRACT,
        GEBCO_2025_TOPO_SOURCE,
        HYG_V38_STAR_CONTRACT,
        HYG_V38_URL,
    )
except Exception:
    GEBCO_2025_TOPO_SOURCE = "gebco_2025"
    GEBCO_2025_OPENDAP_URL = (
        "https://dap.ceda.ac.uk/thredds/dodsC/bodc/gebco/global/"
        "gebco_2025/ice_surface_elevation/netcdf/GEBCO_2025.nc"
    )
    GEBCO_2025_TOPOGRAPHY_CONTRACT = None
    HYG_V38_STAR_CONTRACT = None
    HYG_V38_URL = "https://raw.githubusercontent.com/astronexus/HYG-Database/main/hyg/v3/hyg_v38.csv.gz"

def configure_stdio():
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream is not None and hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def init_taichi():
    preferred = os.environ.get("TAICHI_ARCH", "").strip().lower()
    system = platform.system()
    arch_order = {
        "metal": [ti.metal, ti.cpu],
        "vulkan": [ti.vulkan, ti.cpu],
        "opengl": [ti.opengl, ti.cpu],
        "cuda": [ti.cuda, ti.cpu],
        "gpu": [ti.gpu, ti.cpu],
        "cpu": [ti.cpu],
    }

    if preferred in arch_order:
        candidates = arch_order[preferred]
    elif system == "Darwin":
        candidates = [ti.metal, ti.vulkan, ti.opengl, ti.cpu]
    elif system == "Windows":
        candidates = [ti.cuda, ti.vulkan, ti.opengl, ti.cpu]
    else:
        candidates = [ti.cuda, ti.vulkan, ti.opengl, ti.cpu]

    last_error = None
    for arch in candidates:
        try:
            ti.init(arch=arch)
            print(f"Taichi backend: {arch}")
            return
        except Exception as exc:
            last_error = exc
            print(f"Taichi backend {arch} unavailable: {exc}")

    raise RuntimeError("No usable Taichi backend was found") from last_error


configure_stdio()
init_taichi()

def parse_bool(value, default=False):
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "y", "on")


def get_screen_resolution(default=(1600, 1000)):
    try:
        import tkinter as tk

        root = tk.Tk()
        root.withdraw()
        width = root.winfo_screenwidth()
        height = root.winfo_screenheight()
        root.destroy()
        return width, height
    except Exception:
        return default


def get_work_area_resolution(default=(1600, 1000)):
    if platform.system() == "Windows":
        try:
            import ctypes
            from ctypes import wintypes

            rect = wintypes.RECT()
            SPI_GETWORKAREA = 0x0030
            ctypes.windll.user32.SystemParametersInfoW(SPI_GETWORKAREA, 0, ctypes.byref(rect), 0)
            width = rect.right - rect.left
            height = rect.bottom - rect.top

            frame_x = ctypes.windll.user32.GetSystemMetrics(32)
            frame_y = ctypes.windll.user32.GetSystemMetrics(33)
            padded = ctypes.windll.user32.GetSystemMetrics(92)
            caption = ctypes.windll.user32.GetSystemMetrics(4)
            client_width = width - 2 * (frame_x + padded)
            client_height = height - 2 * (frame_y + padded) - caption
            return max(640, client_width), max(400, client_height)
        except Exception:
            pass

    return get_screen_resolution(default)


def align_to_multiple(value, multiple=8):
    return max(multiple, value - value % multiple)


def maximize_window_by_title(title):
    if platform.system() != "Windows":
        return False

    try:
        import ctypes
        import time as time_module

        user32 = ctypes.windll.user32
        hwnd = 0
        for _ in range(20):
            hwnd = user32.FindWindowW(None, title)
            if hwnd:
                break
            time_module.sleep(0.05)
        if not hwnd:
            return False

        SW_MAXIMIZE = 3
        user32.ShowWindow(hwnd, SW_MAXIMIZE)
        return True
    except Exception:
        return False


# ================= 畫質與精細度設定 =================
TOPO_SOURCE = GEBCO_2025_TOPO_SOURCE
STEP = int(os.environ.get("TOPO_STEP", "2"))   # 【地形網格精細度】: GEBCO_2025 的採樣步長。
            # GEBCO_2025 原生 STEP=1 為 15 arc-second，尺寸 86400x43200，8GB GPU 不適合整張載入。
            # 預設 STEP=2 為 30 arc-second；若要提高 FPS，可用 TOPO_STEP=4 或 8。
FULLSCREEN = parse_bool(os.environ.get("TAICHI_EARTH_FULLSCREEN"), default=False)
MAXIMIZED_WINDOW = parse_bool(os.environ.get("TAICHI_EARTH_MAXIMIZED"), default=True)
FAST_GUI = parse_bool(os.environ.get("TAICHI_EARTH_FAST_GUI"), default=True)
SCREEN_X, SCREEN_Y = get_screen_resolution()
WORK_AREA_X, WORK_AREA_Y = get_work_area_resolution()
default_res_x = SCREEN_X if FULLSCREEN else (WORK_AREA_X if MAXIMIZED_WINDOW else 1600)
default_res_y = SCREEN_Y if FULLSCREEN else (WORK_AREA_Y if MAXIMIZED_WINDOW else 1000)
RES_X = align_to_multiple(int(os.environ.get("TAICHI_EARTH_RES_X", default_res_x))) # 【視窗寬度】
RES_Y = align_to_multiple(int(os.environ.get("TAICHI_EARTH_RES_Y", default_res_y))) # 【視窗高度】

LOCAL_CACHE_DIR = os.path.expanduser("~/.cache/taichi_earth")
os.makedirs(LOCAL_CACHE_DIR, exist_ok=True)

CACHE_FILE = (
    GEBCO_2025_TOPOGRAPHY_CONTRACT.cache_path(step=STEP)
    if GEBCO_2025_TOPOGRAPHY_CONTRACT
    else os.path.join(LOCAL_CACHE_DIR, f"{TOPO_SOURCE}_topo_cache_step{STEP}.npy")
)
STAR_CACHE_FILE = (
    HYG_V38_STAR_CONTRACT.cache_path()
    if HYG_V38_STAR_CONTRACT
    else os.path.join(LOCAL_CACHE_DIR, "stars_cache.npy")
)
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))

# ================= 專業環境設定 =================
class AppConfig:
    TIDE_LEVEL = 0.0                 # 潮汐參數 (海平面基準位移，單位：公尺)
    SHOW_GRID = 1                    # 顯示經緯度網格 (15度一格)
# =======================================================
MIN_ELEV = -11000.0
MAX_ELEV = 8848.0


def synthetic_topography(step):
    h = max(24, 10800 // step + 1)
    w = max(48, 21600 // step + 1)
    lat = np.linspace(-90, 90, h)
    lon = np.linspace(-180, 180, w)
    lon_r, lat_r = np.meshgrid(np.radians(lon), np.radians(lat))

    continents = (
        3000 * np.sin(2.1 * lon_r) * np.cos(1.4 * lat_r)
        + 1800 * np.sin(3.3 * lon_r + 0.8) * np.sin(2.0 * lat_r)
        + 900 * np.cos(5.5 * lon_r - lat_r)
    )
    ocean_bias = -2200 + 1200 * np.cos(lat_r) ** 2
    return np.rint(continents + ocean_bias).astype(np.int16)


def load_topography():
    print(f"地形來源：GEBCO_2025 Grid")
    print(f"地形採樣 STEP={STEP}（1=15 arc-second 原生解析度；2=30 arc-second；4=1 arc-minute）")
    if os.path.exists(CACHE_FILE):
        print(f"⚡ 載入快取的地形資料：{CACHE_FILE}")
        file_size = os.path.getsize(CACHE_FILE)
        with tqdm.wrapattr(open(CACHE_FILE, "rb"), "read", total=file_size, desc="   📥 讀取地形快取") as f:
            return np.load(f)

    print("🌍 讀取全球地形資料 (GEBCO_2025)...")
    urls = [GEBCO_2025_OPENDAP_URL]
    last_error = None
    try:
        for url in urls:
            try:
                print(f"   嘗試資料來源：{url}")
                ds = xr.open_dataset(url)
                break
            except Exception as exc:
                last_error = exc
                print(f"   來源不可用：{exc}")
        else:
            raise last_error

        ds_z = ds["elevation"][::STEP, ::STEP]
        h, w = ds_z.shape
        estimated_mb = h * w * np.dtype(np.int16).itemsize / (1024 * 1024)
        print(f"   目標網格：{h}x{w}，快取/地形場約 {estimated_mb:.1f} MB")
        
        z = np.zeros((h, w), dtype=np.int16)
        chunk_size = 2000
        total_chunks = ((h - 1) // chunk_size + 1) * ((w - 1) // chunk_size + 1)
        print(f"📡 為了避免伺服器拒絕大流量，開始分塊下載 (共 {total_chunks} 塊)...")
        
        with tqdm(total=total_chunks, desc="   📥 地形下載進度", unit="塊") as pbar:
            for i in range(0, h, chunk_size):
                for j in range(0, w, chunk_size):
                    z[i:i+chunk_size, j:j+chunk_size] = ds_z[i:i+chunk_size, j:j+chunk_size].values.astype(np.int16)
                    pbar.update(1)
                
        print("✅ 下載完成！正在儲存快取...")
    except Exception as exc:
        print(f"⚠️ GEBCO_2025 地形資料讀取失敗，改用可離線啟動的合成地形：{exc}")
        z = synthetic_topography(STEP)

    np.save(CACHE_FILE, z)
    return z

def load_stars():
    if os.path.exists(STAR_CACHE_FILE):
        print(f"⚡ 載入快取的真實星表資料：{STAR_CACHE_FILE}")
        file_size = os.path.getsize(STAR_CACHE_FILE)
        with tqdm.wrapattr(open(STAR_CACHE_FILE, "rb"), "read", total=file_size, desc="   📥 讀取星表快取") as f:
            return np.load(f)

    project_star_cache = os.path.join(PROJECT_DIR, "stars_cache.npy")
    if os.path.exists(project_star_cache):
        print(f"⚡ 載入專案內的星表資料：{project_star_cache}")
        stars_data = np.load(project_star_cache)
        np.save(STAR_CACHE_FILE, stars_data)
        return stars_data
    
    print("✨ 從 GitHub 下載真實星表 (HYG Database v3.8)...")
    url = HYG_V38_URL
    
    class DownloadProgressBar(tqdm):
        def update_to(self, b=1, bsize=1, tsize=None):
            if tsize is not None:
                self.total = tsize
            self.update(b * bsize - self.n)
            
    temp_file = os.path.join(LOCAL_CACHE_DIR, "temp_stars_cache.csv.gz")
    with DownloadProgressBar(unit='B', unit_scale=True, miniters=1, desc="   📥 星表下載進度") as t:
        urllib.request.urlretrieve(url, filename=temp_file, reporthook=t.update_to)
        
    df = pd.read_csv(temp_file, compression='gzip', usecols=['ra', 'dec', 'mag'])
    os.remove(temp_file)
    # 篩選肉眼可見亮星 (星等 < 6.5)
    df = df[df['mag'] < 6.5].dropna()
    print(f"   📥 取得 {len(df)} 顆真實亮星！")
    
    ra_rad = (df['ra'].values / 24.0) * 2 * np.pi
    dec_rad = (df['dec'].values / 180.0) * np.pi
    mag = df['mag'].values
    
    # 轉換為 3D 座標 (X, Y, Z)
    x = np.cos(dec_rad) * np.sin(ra_rad)
    y = np.sin(dec_rad)
    z = np.cos(dec_rad) * np.cos(ra_rad)
    
    stars_data = np.column_stack((x, y, z, mag)).astype(np.float32)
    np.save(STAR_CACHE_FILE, stars_data)
    return stars_data

topo_np = load_topography()
h, w = topo_np.shape
print(f"地形網格大小: {h}x{w}")

# 建立 1D 顏色紋理 (避免直接產生巨大彩色圖片導致記憶體爆掉)
print("🎨 初始化色彩對應表 (修正海平面基準)...")
# 我們把高度分成兩段：海洋與陸地，確保 z=0 (海平面) 精準對應到海岸線顏色
# 海洋：純藍漸層 (深海 -> 淺海)，移除 terrain colormap 中靠近海岸的綠色成分
ocean_r = np.linspace(0.0, 0.0, 128)
ocean_g = np.linspace(0.05, 0.6, 128)
ocean_b = np.linspace(0.2, 0.8, 128)
c_ocean = np.column_stack((ocean_r, ocean_g, ocean_b, np.ones(128)))
c_land = plt.cm.terrain(np.linspace(0.26, 1.0, 128))
colors_rgba = np.vstack((c_ocean, c_land))[:, :3].astype(np.float32)

# Taichi 記憶體配置
# 為了大幅提升 GPU 的快取命中率 (L1/L2 Cache)，我們將記憶體配置改為 Block-tiled 結構
pad_h = (16 - h % 16) % 16
pad_w = (16 - w % 16) % 16
if pad_h > 0 or pad_w > 0:
    topo_np_padded = np.pad(topo_np, ((0, pad_h), (0, pad_w)), mode='edge')
else:
    topo_np_padded = topo_np

topo_field = ti.field(dtype=ti.i16)
ti.root.dense(ti.ij, (topo_np_padded.shape[0] // 16, topo_np_padded.shape[1] // 16)).dense(ti.ij, (16, 16)).place(topo_field)
colormap_field = ti.Vector.field(3, dtype=ti.f32, shape=256)
topo_field.from_numpy(topo_np_padded)
colormap_field.from_numpy(colors_rgba)

stars_np = load_stars()
num_stars = stars_np.shape[0]
stars_field = ti.Vector.field(4, dtype=ti.f32, shape=num_stars)
stars_field.from_numpy(stars_np)

image = ti.Vector.field(3, dtype=ti.f32)
# 確保視窗寬高能被 8 整除 (1600x1000 可被 8 整除)，改用 8x8 區塊排列提升寫入效能
ti.root.dense(ti.ij, (RES_X // 8, RES_Y // 8)).dense(ti.ij, (8, 8)).place(image)

@ti.func
def rotate_view_to_world(v, yaw: ti.f32, pitch: ti.f32):
    # 第一步：繞 X 軸旋轉 (俯仰 pitch)
    cp = ti.cos(pitch)
    sp = ti.sin(pitch)
    y1 = cp * v.y - sp * v.z
    z1 = sp * v.y + cp * v.z
    x1 = v.x
    # 第二步：繞 Y 軸旋轉 (偏擺 yaw)
    cy = ti.cos(yaw)
    sy = ti.sin(yaw)
    x2 = cy * x1 + sy * z1
    y2 = y1
    z2 = -sy * x1 + cy * z1
    return ti.Vector([x2, y2, z2])

@ti.func
def get_sky_color(ray_dir, time_val):
    return ti.Vector([0.005, 0.015, 0.03]) # 極深的宇宙背景色

@ti.func
def rotate_world_to_view(v, yaw: ti.f32, pitch: ti.f32):
    # 1. 繞 Y 軸反向旋轉 (yaw)
    cy = ti.cos(-yaw)
    sy = ti.sin(-yaw)
    x1 = cy * v.x + sy * v.z
    y1 = v.y
    z1 = -sy * v.x + cy * v.z
    
    # 2. 繞 X 軸反向旋轉 (pitch)
    cp = ti.cos(-pitch)
    sp = ti.sin(-pitch)
    x2 = x1
    y2 = cp * y1 - sp * z1
    z2 = sp * y1 + cp * z1
    return ti.Vector([x2, y2, z2])

@ti.kernel
def render_stars(yaw: ti.f32, pitch: ti.f32, zoom: ti.f32):
    for idx in range(num_stars):
        star = stars_field[idx]
        pos_world = ti.Vector([star.x, star.y, star.z])
        mag = star.w
        
        # 轉換為視角座標
        pos_view = rotate_world_to_view(pos_world, yaw, pitch)
        
        # 必須在鏡頭前方 (Z < 0)
        if pos_view.z < 0.0:
            sx = pos_view.x / -pos_view.z
            sy = pos_view.y / -pos_view.z
            
            # 判斷是否被地球擋住
            r2 = sx * sx + sy * sy
            if r2 > 1.0:
                aspect = ti.cast(RES_X, ti.f32) / ti.cast(RES_Y, ti.f32)
                # 轉成像素座標
                u = (sx / (zoom * aspect) + 1.0) * 0.5
                v = (sy / zoom + 1.0) * 0.5
                i = ti.cast(u * RES_X, ti.i32)
                j = ti.cast(v * RES_Y, ti.i32)
                
                if 0 <= i < RES_X and 0 <= j < RES_Y:
                    # 星星星等轉換為亮度 (mag 越小越亮)
                    intensity = ti.max(0.1, (6.5 - mag) / 8.0)
                    star_color = ti.Vector([1.0, 0.95, 0.9]) * intensity * 2.5
                    
                    # 依據亮度計算渲染大小 (1~2 px)
                    size = ti.cast(ti.max(1.0, intensity * 2.5), ti.i32)
                    for di in range(-size + 1, size):
                        for dj in range(-size + 1, size):
                            if di*di + dj*dj <= size*size:
                                ni = i + di
                                nj = j + dj
                                if 0 <= ni < RES_X and 0 <= nj < RES_Y:
                                    dist_factor = 1.0 - ti.sqrt(ti.cast(di*di+dj*dj, ti.f32))/ti.cast(size, ti.f32)
                                    image[ni, nj] = ti.min(ti.Vector([1.0, 1.0, 1.0]), image[ni, nj] + star_color * dist_factor)

@ti.kernel
def render_globe(yaw: ti.f32, pitch: ti.f32, bump_scale: ti.f32, zoom: ti.f32, time_val: ti.f32, sun_x: ti.f32, sun_y: ti.f32, sun_z: ti.f32):
    for i, j in image:
        # i 是畫面水平 X 軸，j 是畫面垂直 Y 軸
        # 將像素座標映射到 [-zoom, zoom] 並處理 Aspect Ratio 防止變形
        u = (ti.cast(i, ti.f32) + 0.5) / ti.cast(RES_X, ti.f32)
        v = (ti.cast(j, ti.f32) + 0.5) / ti.cast(RES_Y, ti.f32)
        aspect = ti.cast(RES_X, ti.f32) / ti.cast(RES_Y, ti.f32)
        sx = (u * 2.0 - 1.0) * zoom * aspect
        sy = (v * 2.0 - 1.0) * zoom
        r2 = sx * sx + sy * sy

        # 背景色：宇宙背景色
        color = ti.Vector([0.005, 0.015, 0.03])
        
        # ====== Colorbar 區域 ======
        if u >= 0.898 and u <= 0.922 and v >= 0.098 and v <= 0.902:
            if u > 0.90 and u < 0.92 and v > 0.1 and v < 0.9:
                norm_z = (v - 0.1) / 0.8
                norm_z = ti.max(0.0, ti.min(1.0, norm_z))
                
                c_idx = norm_z * 255.0
                idx0 = ti.cast(ti.floor(c_idx), ti.i32)
                idx1 = ti.min(255, idx0 + 1)
                frac = c_idx - ti.cast(idx0, ti.f32)
                color = colormap_field[idx0] * (1.0 - frac) + colormap_field[idx1] * frac
            else:
                color = ti.Vector([0.8, 0.8, 0.8])
        elif r2 <= 1.0:
            # 計算球體上的 3D 座標
            z = ti.sqrt(1.0 - r2)
            n_view = ti.Vector([sx, sy, z])
            
            # 轉換到世界座標系
            n_world = rotate_view_to_world(n_view, yaw, pitch)

            # 將世界座標轉換為經緯度
            lon = ti.atan2(n_world.x, n_world.z)
            lat = ti.asin(ti.max(-1.0, ti.min(1.0, n_world.y)))
            
            # 映射到地形資料陣列的索引 (0 ~ w-1, 0 ~ h-1)
            tx = ti.cast((lon / (2.0 * math.pi) + 0.5) * ti.cast(w - 1, ti.f32), ti.i32)
            ty = ti.cast((lat / math.pi + 0.5) * ti.cast(h - 1, ti.f32), ti.i32)
            
            tx = ti.max(0, ti.min(w - 1, tx))
            ty = ti.max(0, ti.min(h - 1, ty))

            # 獲取高度並精準正規化 (確保海平面 z=0 剛好是 colormap 中間值 0.5)
            z_val = ti.cast(topo_field[ty, tx], ti.f32)
            norm_z = 0.0
            if z_val < AppConfig.TIDE_LEVEL:
                # 海洋：MIN_ELEV ~ tide_level 映射到 0.0 ~ 0.5
                norm_z = (z_val - MIN_ELEV) / (AppConfig.TIDE_LEVEL - MIN_ELEV) * 0.5
            else:
                # 陸地：tide_level ~ 8848 (珠穆朗瑪峰) 映射到 0.5 ~ 1.0
                norm_z = 0.5 + ((z_val - AppConfig.TIDE_LEVEL) / (MAX_ELEV - AppConfig.TIDE_LEVEL)) * 0.5
                
            norm_z = ti.max(0.0, ti.min(1.0, norm_z))
            
            # 從 1D colormap 取得顏色 (線性插值)
            c_idx = norm_z * 255.0
            idx0 = ti.cast(ti.floor(c_idx), ti.i32)
            idx1 = ti.min(255, idx0 + 1)
            frac = c_idx - ti.cast(idx0, ti.f32)
            base = colormap_field[idx0] * (1.0 - frac) + colormap_field[idx1] * frac
            
            # ===== 凹凸貼圖 (Bump Mapping) 核心 =====
            # 利用相鄰高度差計算地形的法向量擾動，產生 3D 立體感！
            n_world_bump = n_world
            if bump_scale > 0.0:
                tx_next = ti.min(w - 1, tx + 1)
                ty_next = ti.min(h - 1, ty + 1)
                
                # 高度變化率 (梯度) - 改為前向差分 (Forward Difference)，直接複用 z_val！
                # 這將 GPU 的記憶體讀取量瞬間減少一半，大幅提升 FPS
                dz_dx = (ti.cast(topo_field[ty, tx_next], ti.f32) - z_val) * bump_scale
                dz_dy = (ti.cast(topo_field[ty_next, tx], ti.f32) - z_val) * bump_scale
                
                # 優化：利用 n_world 直接推導切線向量，大幅減少三角函數 (ti.sin/cos) 計算
                r_xz = ti.sqrt(n_world.x * n_world.x + n_world.z * n_world.z)
                cos_lon = n_world.z / (r_xz + 1e-7)
                sin_lon = n_world.x / (r_xz + 1e-7)
                
                tan_x = ti.Vector([cos_lon, 0.0, -sin_lon])
                tan_y = ti.Vector([-n_world.y * sin_lon, r_xz, -n_world.y * cos_lon])
                
                # 擾動法向量 (Normal Perturbation)
                n_world_bump = (n_world - tan_x * dz_dx - tan_y * dz_dy).normalized()
            
            # 計算光照 (Lambertian Shading + Rim Lighting)
            # 引入真實太陽光方向與晨昏線效果 (Twilight)
            light_dir = ti.Vector([sun_x, sun_y, sun_z]).normalized()
            
            # 內積計算受光面
            dot_l = n_world_bump.dot(light_dir)
            shade = ti.max(0.15, dot_l) # 提高暗部環境光，讓黑夜面地形仍可見
            
            # 晨昏線效果 (Twilight): 當 dot_l 接近 0 時，加入紅色/橘色漸層
            twilight = 0.0
            if dot_l > -0.2 and dot_l < 0.2:
                twilight = (0.2 - ti.abs(dot_l)) / 0.2
                
            rim = ti.pow(ti.max(0.0, 1.0 - z), 2.5)       # 邊緣光
            
            # 最終像素顏色 (Base * 光照 + 晨昏線散射 + 邊緣光僅限受光面)
            color = base * shade + ti.Vector([0.8, 0.35, 0.15]) * twilight * 0.15 + ti.Vector([0.15, 0.25, 0.35]) * rim * ti.max(0.0, dot_l + 0.2)

            # ====== 經緯度網格顯示 ======
            if AppConfig.SHOW_GRID == 1:
                # 轉換為角度
                lon_deg = lon * 180.0 / math.pi
                lat_deg = lat * 180.0 / math.pi
                
                # 計算與 15 度的倍數距離
                # ti.abs 不支援 modulo 時，可以用算術推導
                rem_lon = ti.abs(lon_deg - ti.floor(lon_deg / 15.0) * 15.0)
                rem_lat = ti.abs(lat_deg - ti.floor(lat_deg / 15.0) * 15.0)
                
                # 確保線條在兩側都有寬度，所以要判斷距離 0 或 15 的距離
                dist_lon = ti.min(rem_lon, 15.0 - rem_lon)
                dist_lat = ti.min(rem_lat, 15.0 - rem_lat)
                
                # 線寬設定 (隨 zoom 縮小而變細以保持清晰)
                line_width = 0.3 * zoom 
                if dist_lon < line_width or dist_lat < line_width:
                    grid_color = ti.Vector([1.0, 1.0, 1.0])
                    # 依據與中心線距離產生柔和的淡出
                    intensity = 1.0 - ti.min(dist_lon, dist_lat) / line_width
                    color = color * (1.0 - 0.4 * intensity) + grid_color * 0.4 * intensity

        image[i, j] = color

def apply_zoom(zoom, scale):
    return max(0.08, min(zoom * scale, 4.0))


def is_pressed_any(gui, keys):
    for key in keys:
        try:
            if gui.is_pressed(key):
                return True
        except Exception:
            pass
    return False


def main():
    print("🎬 開始渲染！")
    if FULLSCREEN:
        display_mode = "全螢幕"
    elif MAXIMIZED_WINDOW:
        display_mode = "視窗最大化"
    else:
        display_mode = "視窗"
    print(f"顯示模式：{display_mode} ({RES_X}x{RES_Y})")
    print("操作方式：")
    print("  - [旋轉] 滑鼠『左鍵』按住並拖曳")
    print("  - [放大] 滾輪往上、右鍵往上拖、方向鍵上、+、W")
    print("  - [縮小] 滾輪往下、右鍵往下拖、方向鍵下、-、S")
    print("  - [離開] Esc 或關閉視窗")
    
    window_title = "Taichi Global Bathymetry - Bump Mapped"
    gui = ti.GUI(
        window_title,
        res=(RES_X, RES_Y),
        fullscreen=FULLSCREEN,
        fast_gui=FAST_GUI,
    )
    if MAXIMIZED_WINDOW and not FULLSCREEN:
        maximize_window_by_title(window_title)
    
    yaw = 0.0
    pitch = 0.0
    zoom = 1.0
    is_dragging = False
    is_zooming = False
    last_mouse_pos = (0.0, 0.0)
    start_time = time.time()
    max_frames = int(os.environ.get("TAICHI_EARTH_MAX_FRAMES", "0"))
    frame_count = 0
    fps = 0.0
    fps_last_time = time.time()
    fps_last_frame = 0

    # 渲染迴圈
    while gui.running:
        time_val = time.time() - start_time
        
        # 處理鍵盤縮放。zoom 越小代表畫面放得越大。
        if is_pressed_any(gui, (ti.GUI.UP, "+", "=", "w", "W")):
            zoom = apply_zoom(zoom, 0.96)
        if is_pressed_any(gui, (ti.GUI.DOWN, "-", "_", "s", "S")):
            zoom = apply_zoom(zoom, 1.04)

        # 處理滑鼠事件
        for e in gui.get_events(ti.GUI.PRESS, ti.GUI.MOTION, ti.GUI.RELEASE, ti.GUI.WHEEL):
            if e.type == ti.GUI.PRESS and e.key == ti.GUI.LMB:
                is_dragging = True
                last_mouse_pos = gui.get_cursor_pos()
            elif e.type == ti.GUI.RELEASE and e.key == ti.GUI.LMB:
                is_dragging = False
                
            elif e.type == ti.GUI.PRESS and e.key == ti.GUI.RMB:
                is_zooming = True
                last_mouse_pos = gui.get_cursor_pos()
            elif e.type == ti.GUI.RELEASE and e.key == ti.GUI.RMB:
                is_zooming = False
                
            elif e.type == ti.GUI.MOTION:
                curr_pos = gui.get_cursor_pos()
                dx = curr_pos[0] - last_mouse_pos[0]
                dy = curr_pos[1] - last_mouse_pos[1]
                
                if is_dragging:
                    yaw -= dx * 3.0 * zoom
                    pitch += dy * 3.0 * zoom
                    pitch = max(min(pitch, math.pi / 2 - 0.01), -math.pi / 2 + 0.01)
                    last_mouse_pos = curr_pos
                elif is_zooming:
                    # 右鍵往上拖放大，往下拖縮小。
                    zoom = apply_zoom(zoom, math.exp(-dy * 4.0))
                    last_mouse_pos = curr_pos

            elif e.type == ti.GUI.WHEEL:
                delta = e.delta[1] if isinstance(e.delta, (tuple, list)) else e.delta
                zoom = apply_zoom(zoom, 0.88 ** delta)
                
        # 取得系統 UTC 時間計算太陽直射點
        now = datetime.datetime.now(datetime.timezone.utc)
        day_of_year = now.timetuple().tm_yday
        # 考慮地球自轉軸傾角 23.44 度
        lat_sun = math.radians(-23.44 * math.cos(2 * math.pi / 365.0 * (day_of_year + 10)))
        utc_hour = now.hour + now.minute / 60.0 + now.second / 3600.0
        # 經度：UTC 12:00 太陽在 0 度經線
        lon_sun = math.radians((12.0 - utc_hour) * 15.0)
        
        # 轉換太陽的 3D 向量 (X=90E, Y=North Pole, Z=Prime Meridian)
        sun_y = math.sin(lat_sun)
        xz_r = math.cos(lat_sun)
        sun_z = xz_r * math.cos(lon_sun)
        sun_x = xz_r * math.sin(lon_sun)
        
        # 執行 Shader 計算，bump_scale 可調整 3D 立體感的誇張程度
        # 原本是 0.00008，現在調高到 0.0004 讓海底山脈與海溝的立體感大幅提升！
        render_globe(yaw, pitch, 0.0004, zoom, time_val, sun_x, sun_y, sun_z)
        
        # 繪製真實星表
        render_stars(yaw, pitch, zoom)
        
        # 顯示影像與 UI
        gui.set_image(image)
        gui.text(f"{int(MAX_ELEV)}m (Everest)", pos=(0.91, 0.90), font_size=18, color=0xFFFFFF)
        gui.text(f"Tide: {AppConfig.TIDE_LEVEL}m", pos=(0.91, 0.50), font_size=18, color=0x00FFaa)
        gui.text(f"Zoom: {1.0 / zoom:.2f}x", pos=(0.03, 0.94), font_size=18, color=0xFFFFFF)
        gui.text(f"FPS: {fps:.1f}", pos=(0.03, 0.90), font_size=18, color=0xFFFFFF)
        gui.text(f"{int(MIN_ELEV)}m", pos=(0.91, 0.10), font_size=18, color=0xFFFFFF)
        gui.show()

        frame_count += 1
        fps_now = time.time()
        if fps_now - fps_last_time >= 0.5:
            fps = (frame_count - fps_last_frame) / (fps_now - fps_last_time)
            fps_last_time = fps_now
            fps_last_frame = frame_count

        if max_frames and frame_count >= max_frames:
            gui.running = False

if __name__ == "__main__":
    main()
