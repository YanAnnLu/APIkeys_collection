from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from api_launcher.crawlers.source_patterns import SourcePatternDetection
from api_launcher.source_pattern_drafts import (
    dataset_source_from_detected_url,
    write_source_draft_from_url,
)


class SourcePatternDraftTest(unittest.TestCase):
    def test_detected_url_writes_ignored_local_source_draft(self) -> None:
        def detector(_url: str) -> SourcePatternDetection:
            return SourcePatternDetection(
                pattern_id="stac",
                confidence=0.95,
                evidence=("json_contains_stac_version", "json_references_collections"),
                source_type_hint="stac_collections",
            )

        with TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "dataset_discovery_sources.local.json"

            summary = write_source_draft_from_url(
                "https://example.test/stac",
                output_path,
                categories=("satellite", "raster"),
                max_results=5,
                detector=detector,
            )

            payload = json.loads(output_path.read_text(encoding="utf-8"))

        source = payload["sources"][0]
        self.assertEqual("local dataset discovery source draft from source pattern detector; ignored local config only", summary["role"])
        self.assertEqual("stac", summary["source_pattern_detection"]["pattern_id"])
        self.assertEqual(["example_test_stac_stac_collections"], summary["audit_source_ids"])
        self.assertEqual("stac_collections", source["source_type"])
        self.assertEqual(["satellite", "raster"], source["categories"])
        self.assertEqual(5, source["max_results"])
        self.assertIn("--promote-local-discovery-dry-run", str(summary["audit_command"]))

    def test_unknown_detection_stays_in_review(self) -> None:
        def detector(_url: str) -> SourcePatternDetection:
            return SourcePatternDetection(
                pattern_id="unknown",
                confidence=0.25,
                evidence=("below_minimum_confidence",),
                candidates=(),
            )

        with self.assertRaisesRegex(ValueError, "unknown"):
            dataset_source_from_detected_url("https://example.test/landing", detector=detector)

    def test_unsupported_source_type_is_rejected_before_local_draft(self) -> None:
        def detector(_url: str) -> SourcePatternDetection:
            return SourcePatternDetection(
                pattern_id="vendor_custom",
                confidence=0.9,
                evidence=("custom_api_shape",),
                source_type_hint="unsupported_custom_api",
            )

        with self.assertRaisesRegex(ValueError, "not supported"):
            dataset_source_from_detected_url("https://example.test/api", detector=detector)

    def test_non_http_source_url_is_rejected_before_detection(self) -> None:
        def detector(_url: str) -> SourcePatternDetection:
            raise AssertionError("detector should not run for invalid source URL")

        with self.assertRaisesRegex(ValueError, "absolute http"):
            dataset_source_from_detected_url("file:///K:/private/source.json", detector=detector)

    def test_source_url_with_embedded_credentials_is_rejected_before_detection(self) -> None:
        def detector(_url: str) -> SourcePatternDetection:
            raise AssertionError("detector should not run for credential-bearing source URL")

        with self.assertRaisesRegex(ValueError, "must not embed credentials"):
            dataset_source_from_detected_url("https://user:secret@example.test/catalog", detector=detector)


if __name__ == "__main__":
    unittest.main()
