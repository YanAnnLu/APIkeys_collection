from __future__ import annotations

# Adapter package 的公開面集中在這裡；其他模組應優先 import 這些穩定名稱。
from api_launcher.adapters.base import DatasetAdapter, dataset_uid
from api_launcher.adapters.gebco import GEBCOTopographyAdapter
from api_launcher.adapters.hyg import HYGStarCatalogAdapter

__all__ = ["DatasetAdapter", "GEBCOTopographyAdapter", "HYGStarCatalogAdapter", "dataset_uid"]
