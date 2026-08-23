from __future__ import annotations

import unittest
from pathlib import Path

from src.build_dashboard_data import build_dashboard_payload


ROOT = Path(__file__).resolve().parents[1]


class DashboardDataTest(unittest.TestCase):
    def test_payload_uses_only_primary_regions_and_frozen_outputs(self) -> None:
        payload = build_dashboard_payload(ROOT)

        self.assertEqual(payload["meta"]["primaryRegions"], ["NSW1", "VIC1", "QLD1", "SA1"])
        self.assertEqual(len(payload["trends"]), 288)
        self.assertEqual({row["region"] for row in payload["trends"]}, {"NSW1", "VIC1", "QLD1", "SA1"})
        self.assertEqual(len(payload["regionalHeterogeneity"]), 4)
        self.assertEqual(len(payload["priceRobustness"]), 7)
        self.assertAlmostEqual(payload["headline"]["priceLevel"]["estimate"], -11.802049)
        self.assertAlmostEqual(payload["headline"]["negativePriceProbabilityPp"]["estimate"], 3.5769)
        self.assertIn("not causal", payload["meta"]["claimBoundary"])


if __name__ == "__main__":
    unittest.main()
