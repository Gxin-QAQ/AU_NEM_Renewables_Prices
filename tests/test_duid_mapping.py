from __future__ import annotations

import unittest
from datetime import datetime

from src.aemo_dispatch import NEM_TIMEZONE
from src.duid_mapping import (
    classify_registration,
    classify_scada_flow,
    normalise_fueltech,
    registration_index,
    resolve_registration,
)


def registration(
    duid: str = "UNIT1",
    start: str = "2025/01/01 00:00:00",
    end: str = "2025/07/01 00:00:00",
    dispatch_type: str = "GENERATOR",
) -> dict[str, str]:
    return {
        "DUID": duid,
        "START_DATE": start,
        "END_DATE": end,
        "DISPATCHTYPE": dispatch_type,
        "REGIONID": "NSW1",
        "STATIONID": "STATION1",
        "PARTICIPANTID": "OWNER1",
        "SCHEDULE_TYPE": "SCHEDULED",
    }


class DuidMappingTest(unittest.TestCase):
    def test_effective_join_is_start_inclusive_end_exclusive(self) -> None:
        index = registration_index([registration()])
        start = datetime(2025, 1, 1, tzinfo=NEM_TIMEZONE)
        before_end = datetime(2025, 6, 30, 23, 55, tzinfo=NEM_TIMEZONE)
        end = datetime(2025, 7, 1, tzinfo=NEM_TIMEZONE)
        self.assertIsNotNone(resolve_registration(index, "UNIT1", start))
        self.assertIsNotNone(resolve_registration(index, "UNIT1", before_end))
        self.assertIsNone(resolve_registration(index, "UNIT1", end))

    def test_overlapping_registration_intervals_fail(self) -> None:
        rows = [
            registration(end="2025/08/01 00:00:00"),
            registration(start="2025/07/01 00:00:00", end="2025/09/01 00:00:00"),
        ]
        with self.assertRaisesRegex(ValueError, "Overlapping"):
            registration_index(rows)

    def test_fueltech_collapsing(self) -> None:
        self.assertEqual(normalise_fueltech("wind"), "WIND")
        self.assertEqual(normalise_fueltech("gas_ccgt"), "GAS")
        self.assertEqual(normalise_fueltech("battery_charging"), "BATTERY")
        self.assertEqual(normalise_fueltech(None), "UNKNOWN")

    def test_unmatched_bidirectional_unit_uses_pilot_battery_rule(self) -> None:
        category, _, method, review = classify_registration(
            registration(dispatch_type="BIDIRECTIONAL"), None, allow_bdu_pilot_rule=True
        )
        self.assertEqual(category, "BATTERY")
        self.assertEqual(method, "aemo_bdu_pilot_rule")
        self.assertEqual(review, "pilot_rule_reviewed")

    def test_bidirectional_rule_is_not_global(self) -> None:
        category, _, method, review = classify_registration(
            registration(dispatch_type="BIDIRECTIONAL"), None
        )
        self.assertEqual(category, "UNKNOWN")
        self.assertEqual(method, "unmapped")
        self.assertEqual(review, "needs_review")

    def test_battery_flow_is_not_renewable(self) -> None:
        discharge = classify_scada_flow("BATTERY", 25.0)
        charge = classify_scada_flow("BATTERY", -18.0)
        self.assertEqual(discharge["battery_discharge_mw"], 25.0)
        self.assertEqual(discharge["headline_renewable_mw"], 0.0)
        self.assertEqual(charge["battery_charge_mw"], 18.0)
        self.assertEqual(charge["generation_mw"], 0.0)

    def test_hydro_only_enters_broad_renewable_measure(self) -> None:
        flow = classify_scada_flow("HYDRO", 40.0)
        self.assertEqual(flow["headline_renewable_mw"], 0.0)
        self.assertEqual(flow["broad_renewable_mw"], 40.0)


if __name__ == "__main__":
    unittest.main()
