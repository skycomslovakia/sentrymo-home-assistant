"""Tests for persisted API URL migration."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest

MODULE_PATH = (
    Path(__file__).parents[1]
    / "custom_components"
    / "sentrymo"
    / "api_url.py"
)
SPEC = importlib.util.spec_from_file_location("sentrymo_api_url", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
normalize_api_url = MODULE.normalize_api_url

PROD = "https://ha-api.sentrymo.eu/api/v1"
QA = "https://ha-api.qa.sentrymo.eu/api/v1"


class NormalizeAPIURLTest(unittest.TestCase):
    """Verify both host and path migrations."""

    def test_current_hosts_are_unchanged(self) -> None:
        self.assertEqual(normalize_api_url(PROD, PROD), PROD)
        self.assertEqual(normalize_api_url(QA, PROD), QA)

    def test_legacy_laravel_production_hosts_move_to_dedicated_api(self) -> None:
        for host in ("api.sentrymo.eu", "api.prod.sentrymo.eu"):
            with self.subTest(host=host):
                self.assertEqual(
                    normalize_api_url(f"https://{host}/ha-api/v1", PROD),
                    PROD,
                )

    def test_legacy_laravel_qa_host_moves_to_dedicated_api(self) -> None:
        self.assertEqual(
            normalize_api_url("https://api.qa.sentrymo.eu/api/v1", PROD),
            QA,
        )

    def test_intermediate_ha_hosts_are_migrated(self) -> None:
        self.assertEqual(
            normalize_api_url("https://ha.sentrymo.eu/ha-api/v1", PROD),
            PROD,
        )
        self.assertEqual(
            normalize_api_url("https://ha.qa.sentrymo.eu/ha-api", PROD),
            QA,
        )

    def test_origin_gets_current_path(self) -> None:
        self.assertEqual(
            normalize_api_url("https://ha-api.sentrymo.eu", PROD),
            PROD,
        )


if __name__ == "__main__":
    unittest.main()
