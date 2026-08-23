from __future__ import annotations

import tempfile
import unittest
import warnings
from datetime import timedelta
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

from src.aemo_dispatch import (
    NEM_TIMEZONE,
    expected_interval_count,
    parse_aemo_csv_tables,
    parse_region_archive,
    parse_scada_archive,
)


ROOT = Path(__file__).resolve().parents[1]
PILOT_DISPATCH = ROOT / "data/raw/aemo_pilot/dispatch/PUBLIC_DISPATCH_20251005.zip"
PILOT_SCADA = ROOT / "data/raw/aemo_pilot/scada/PUBLIC_DISPATCHSCADA_20251005.zip"


class AemoCsvTest(unittest.TestCase):
    def test_parses_region_table(self) -> None:
        payload = b"\n".join(
            [
                b"C,NEMP.WORLD,DISPATCH,AEMO,PUBLIC,2025/10/05,00:00:00,1",
                b"I,DREGION,,3,SETTLEMENTDATE,RUNNO,REGIONID,INTERVENTION,RRP,TOTALDEMAND",
                b'D,DREGION,,3,"2025/10/05 00:05:00",1,NSW1,0,-10.5,7000.25',
            ]
        )
        tables = parse_aemo_csv_tables(payload)
        row = tables[("DREGION", "", "3")][0]
        self.assertEqual(row["REGIONID"], "NSW1")
        self.assertEqual(row["RRP"], "-10.5")

    def test_identical_duplicate_outer_members_are_deduplicated(self) -> None:
        inner = BytesIO()
        with ZipFile(inner, "w") as archive:
            archive.writestr(
                "sample.csv",
                "I,DREGION,,3,SETTLEMENTDATE,RUNNO,REGIONID,INTERVENTION,RRP,TOTALDEMAND\n"
                'D,DREGION,,3,"2025/09/08 00:05:00",1,NSW1,0,1,2\n',
            )
        with tempfile.TemporaryDirectory() as temporary:
            outer_path = Path(temporary) / "outer.zip"
            with ZipFile(outer_path, "w") as outer:
                outer.writestr("interval.zip", inner.getvalue())
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", UserWarning)
                    outer.writestr("interval.zip", inner.getvalue())
            records = parse_region_archive(outer_path)
        self.assertEqual(len(records), 1)

    def test_empty_placeholder_before_valid_duplicate_is_ignored(self) -> None:
        inner = BytesIO()
        with ZipFile(inner, "w") as archive:
            archive.writestr(
                "sample.csv",
                "I,DREGION,,3,SETTLEMENTDATE,RUNNO,REGIONID,INTERVENTION,RRP,TOTALDEMAND\n"
                'D,DREGION,,3,"2025/09/08 00:05:00",1,NSW1,0,1,2\n',
            )
        with tempfile.TemporaryDirectory() as temporary:
            outer_path = Path(temporary) / "outer.zip"
            with ZipFile(outer_path, "w") as outer:
                outer.writestr("interval.zip", b"")
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", UserWarning)
                    outer.writestr("interval.zip", inner.getvalue())
            records = parse_region_archive(outer_path)
        self.assertEqual(len(records), 1)


@unittest.skipUnless(PILOT_DISPATCH.exists() and PILOT_SCADA.exists(), "pilot data not present")
class PilotArchiveIntegrationTest(unittest.TestCase):
    def test_dst_boundary_has_288_fixed_aest_intervals(self) -> None:
        records = parse_region_archive(PILOT_DISPATCH)
        self.assertEqual(expected_interval_count(records), 288)
        self.assertEqual({record["region"] for record in records}, {"NSW1", "QLD1", "SA1", "TAS1", "VIC1"})
        self.assertEqual(len(records), 288 * 5)
        self.assertTrue(all(record["timestamp"].tzinfo == NEM_TIMEZONE for record in records))
        self.assertEqual(records[0]["timestamp"].utcoffset(), timedelta(hours=10))

    def test_scada_records_have_expected_interval_count(self) -> None:
        records = parse_scada_archive(PILOT_SCADA)
        self.assertEqual(expected_interval_count(records), 288)
        self.assertGreater(len(records), 288)
        self.assertTrue(all(record["duid"] for record in records))


if __name__ == "__main__":
    unittest.main()
