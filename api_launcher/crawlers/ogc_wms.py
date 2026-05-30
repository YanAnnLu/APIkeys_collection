from __future__ import annotations

import urllib.parse
import xml.etree.ElementTree as ET

from api_launcher.adapters.base import dataset_uid
from api_launcher.crawlers.fetch import fetch_text
from api_launcher.crawlers.metadata import (
    analysis_hint_for_family,
    merge_categories,
    safe_dataset_id,
    sql_role_for_family,
    storage_hint_for_family,
    viewer_hint_for_family,
)
from api_launcher.crawlers.registry import crawler
from api_launcher.crawlers.types import DatasetCandidate, DatasetDiscoverySource
from api_launcher.models import Dataset


def ogc_wms_capabilities_url(endpoint_url: str) -> str:
    parsed = urllib.parse.urlparse(endpoint_url)
    query_pairs = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    query_lower = {key.lower(): value for key, value in query_pairs}
    service = query_lower.get("service", "").lower()
    request = query_lower.get("request", "").lower()
    if service == "wms" and request == "getcapabilities":
        return urllib.parse.urlunparse(parsed._replace(fragment="")) if parsed.fragment else endpoint_url
    # WMS crawler must replace conflicting service/request pairs instead of appending duplicates.
    filtered_pairs = [(key, value) for key, value in query_pairs if key.lower() not in {"service", "request"}]
    filtered_pairs.extend([("service", "WMS"), ("request", "GetCapabilities")])
    return urllib.parse.urlunparse(
        parsed._replace(
            query=urllib.parse.urlencode(filtered_pairs),
            fragment="",
        )
    )


@crawler(
    source_type="ogc_wms_capabilities",
    source_family="map_capabilities",
    transport="xml",
    auth_profile="none",
    result_shape="layer_list",
    seed_scope="entry_listing",
    supports_full_crawl=False,
)
def ogc_wms_candidates_for_source(
    source: DatasetDiscoverySource,
    timeout: float,
    limit: int,
    search_terms: tuple[str, ...],
    _full_crawl: bool,
    _max_pages: int,
) -> list[DatasetCandidate]:
    url = ogc_wms_capabilities_url(source.endpoint_url)
    text, final_url = fetch_text(url, timeout=timeout)
    return ogc_wms_candidates_from_xml(source, text, final_url, limit, search_terms)


def ogc_wms_candidates_from_xml(
    source: DatasetDiscoverySource,
    text: str,
    source_url: str,
    limit: int,
    search_terms: tuple[str, ...] = (),
) -> list[DatasetCandidate]:
    root = ET.fromstring(text)
    service_title = wms_service_title(root) or source.name
    get_map_url = wms_get_map_url(root) or source_url
    candidates: list[DatasetCandidate] = []
    for layer in named_layers(root):
        name = first_child_text(layer, "Name")
        title = first_child_text(layer, "Title") or name
        abstract = first_child_text(layer, "Abstract")
        keywords = tuple(child.text.strip() for child in layer.iter() if local_name(child.tag) == "Keyword" and child.text and child.text.strip())
        searchable = " ".join((name, title, abstract, " ".join(keywords), " ".join(source.categories)))
        if search_terms and not any(term.lower() in searchable.lower() for term in search_terms):
            continue
        dataset_id = safe_dataset_id(name)
        data_family = "gis"
        dataset = Dataset(
            dataset_uid=dataset_uid(source.provider_id, dataset_id),
            provider_id=source.provider_id,
            dataset_id=dataset_id,
            title=title,
            categories=merge_categories(source.categories, ("ogc", "wms"), keywords[:8]),
            data_type=data_family,
            native_format="wms",
            geographic_scope=source.geographic_scope,
            landing_url=source.docs_url or source_url,
            api_url=get_map_url,
            version="capabilities",
            metadata={
                "candidate_status": "needs_review",
                "discovery_source_id": source.source_id,
                "discovery_source_type": source.source_type,
                "source_url": source_url,
                "provider_backed": True,
                "data_family": data_family,
                "storage_hint": storage_hint_for_family(data_family),
                "sql_role": sql_role_for_family(data_family),
                "analysis_hint": analysis_hint_for_family(data_family),
                "viewer_hint": viewer_hint_for_family(data_family),
                "service_title": service_title,
                "wms_layer_name": name,
                "wms_get_map_url": get_map_url,
                "bbox": layer_bbox(layer),
                "keywords": keywords,
                "notes": source.notes,
            },
        )
        candidates.append(
            DatasetCandidate(
                dataset=dataset,
                source_id=source.source_id,
                source_type=source.source_type,
                source_url=source_url,
                confidence=0.74,
                evidence=("OGC WMS GetCapabilities layer", f"layer: {name}"),
            )
        )
        if limit > 0 and len(candidates) >= limit:
            break
    return candidates


def named_layers(root: ET.Element) -> list[ET.Element]:
    layers: list[ET.Element] = []
    for layer in root.iter():
        if local_name(layer.tag) == "Layer" and first_child_text(layer, "Name"):
            layers.append(layer)
    return layers


def first_child_text(element: ET.Element, child_name: str) -> str:
    for child in element:
        if local_name(child.tag) == child_name and child.text and child.text.strip():
            return child.text.strip()
    return ""


def wms_service_title(root: ET.Element) -> str:
    for child in root:
        if local_name(child.tag) == "Service":
            return first_child_text(child, "Title")
    return ""


def wms_get_map_url(root: ET.Element) -> str:
    for element in root.iter():
        if local_name(element.tag) != "GetMap":
            continue
        for child in element.iter():
            if local_name(child.tag) != "OnlineResource":
                continue
            href = online_resource_href(child)
            if href:
                return href
    for element in root.iter():
        if local_name(element.tag) != "OnlineResource":
            continue
        href = online_resource_href(element)
        if href:
            return href
    return ""


def online_resource_href(element: ET.Element) -> str:
    href = (
        element.attrib.get("{http://www.w3.org/1999/xlink}href")
        or element.attrib.get("xlink:href")
        or element.attrib.get("href")
        or ""
    ).strip()
    if href.startswith(("http://", "https://")):
        return href
    return ""


def layer_bbox(layer: ET.Element) -> dict[str, object]:
    for child in layer:
        if local_name(child.tag) == "EX_GeographicBoundingBox":
            return {
                "west": child_float(child, "westBoundLongitude"),
                "east": child_float(child, "eastBoundLongitude"),
                "south": child_float(child, "southBoundLatitude"),
                "north": child_float(child, "northBoundLatitude"),
            }
        if local_name(child.tag) == "LatLonBoundingBox":
            return {key: float_value(child.attrib.get(key)) for key in ("minx", "miny", "maxx", "maxy") if child.attrib.get(key) is not None}
    return {}


def child_float(element: ET.Element, child_name: str) -> float | None:
    text = first_child_text(element, child_name)
    return float_value(text)


def float_value(value: object) -> float | None:
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return None


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


__all__ = [
    "ogc_wms_candidates_for_source",
    "ogc_wms_candidates_from_xml",
    "ogc_wms_capabilities_url",
]
