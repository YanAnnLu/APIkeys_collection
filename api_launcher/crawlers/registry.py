from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from api_launcher.crawlers.types import DatasetCandidate, DatasetCrawlerOutput, DatasetDiscoverySource


DatasetSourceCrawler = Callable[
    [DatasetDiscoverySource, float, int, tuple[str, ...], bool, int],
    list[DatasetCandidate] | tuple[DatasetCandidate, ...] | DatasetCrawlerOutput,
]

CrawlerMatrixKey = tuple[str, str, str, str]


@dataclass(frozen=True)
class CrawlerSpec:
    """Declarative metadata for a crawler handler.

    The registry is a transitional layer toward profile/gateway based crawling.
    It describes what a handler is, but it does not hide the handler's normal
    Python implementation behind a custom DSL.
    """

    source_type: str
    source_family: str
    transport: str
    auth_profile: str
    result_shape: str
    supports_full_crawl: bool
    handler: DatasetSourceCrawler

    @property
    def matrix_key(self) -> CrawlerMatrixKey:
        return (self.source_family, self.transport, self.auth_profile, self.result_shape)

    def to_dict(self) -> dict[str, object]:
        return {
            "source_type": self.source_type,
            "source_family": self.source_family,
            "transport": self.transport,
            "auth_profile": self.auth_profile,
            "result_shape": self.result_shape,
            "supports_full_crawl": self.supports_full_crawl,
            "matrix_key": self.matrix_key,
            "handler_name": self.handler.__name__,
        }


_REGISTRY: dict[str, CrawlerSpec] = {}


def crawler(
    *,
    source_type: str,
    source_family: str,
    transport: str,
    auth_profile: str,
    result_shape: str,
    supports_full_crawl: bool = False,
) -> Callable[[DatasetSourceCrawler], DatasetSourceCrawler]:
    """Register a crawler handler with declarative capability metadata."""

    def decorator(func: DatasetSourceCrawler) -> DatasetSourceCrawler:
        normalized_source_type = source_type.strip()
        if not normalized_source_type:
            raise ValueError("Crawler source_type must not be blank")
        if normalized_source_type in _REGISTRY:
            raise ValueError(f"Duplicate crawler source_type: {normalized_source_type}")
        _REGISTRY[normalized_source_type] = CrawlerSpec(
            source_type=normalized_source_type,
            source_family=source_family.strip(),
            transport=transport.strip(),
            auth_profile=auth_profile.strip(),
            result_shape=result_shape.strip(),
            supports_full_crawl=bool(supports_full_crawl),
            handler=func,
        )
        return func

    return decorator


def crawler_spec(source_type: str) -> CrawlerSpec:
    normalized_source_type = source_type.strip()
    try:
        return _REGISTRY[normalized_source_type]
    except KeyError as exc:
        raise ValueError(f"Unsupported dataset discovery source_type: {normalized_source_type}") from exc


def crawler_handler(source_type: str) -> DatasetSourceCrawler:
    return crawler_spec(source_type).handler


def crawler_specs() -> tuple[CrawlerSpec, ...]:
    return tuple(_REGISTRY[source_type] for source_type in sorted(_REGISTRY))


def crawler_handlers_by_source_type() -> dict[str, DatasetSourceCrawler]:
    return {source_type: spec.handler for source_type, spec in _REGISTRY.items()}


def crawler_matrix() -> dict[CrawlerMatrixKey, tuple[str, ...]]:
    matrix: dict[CrawlerMatrixKey, list[str]] = {}
    for spec in _REGISTRY.values():
        matrix.setdefault(spec.matrix_key, []).append(spec.source_type)
    return {key: tuple(sorted(source_types)) for key, source_types in matrix.items()}


def crawler_specs_by_source_type() -> dict[str, CrawlerSpec]:
    return dict(_REGISTRY)


__all__ = [
    "CrawlerMatrixKey",
    "CrawlerSpec",
    "DatasetSourceCrawler",
    "crawler",
    "crawler_handler",
    "crawler_handlers_by_source_type",
    "crawler_matrix",
    "crawler_spec",
    "crawler_specs",
    "crawler_specs_by_source_type",
]
