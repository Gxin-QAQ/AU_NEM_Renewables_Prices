from __future__ import annotations

import pandas as pd

from src.panel_builder import add_local_time_fields, aggregate_hourly, validate_hourly_panel


def test_local_time_uses_dst_for_nsw_and_fixed_aest_for_qld():
    frame = pd.DataFrame(
        {
            "timestamp": [
                pd.Timestamp("2025-10-05 02:00:00", tz="Australia/Brisbane"),
                pd.Timestamp("2025-10-05 02:00:00", tz="Australia/Brisbane"),
            ],
            "region": ["NSW1", "QLD1"],
        }
    )
    config = {"definitions": {"peak_hours_local": [7], "peak_weekdays_only": True}}
    result = add_local_time_fields(frame, config)
    nsw = result.loc[result["region"] == "NSW1"].iloc[0]
    qld = result.loc[result["region"] == "QLD1"].iloc[0]
    assert nsw["local_hour"] == 3
    assert nsw["local_utc_offset_hours"] == 11
    assert qld["local_hour"] == 2
    assert qld["local_utc_offset_hours"] == 10


def test_hourly_aggregation_uses_twelve_five_minute_intervals():
    timestamp = pd.date_range("2025-09-08 00:00", periods=12, freq="5min", tz="Australia/Brisbane")
    frame = pd.DataFrame(
        {
            "timestamp": timestamp,
            "region": "NSW1",
            "rrp_aud_mwh": list(range(-5, 7)),
            "demand_mw": 100.0,
            "wind_mw": 20.0,
            "solar_utility_mw": 10.0,
            "hydro_mw": 5.0,
            "battery_discharge_mw": 1.0,
            "battery_charge_mw": 2.0,
            "load_scada_mw": 0.0,
            "unmapped_scada_mw": 0.0,
            "mapped_nonstorage_generation_mw": 35.0,
            "renewable_share_ws": 0.3,
            "renewable_share_broad": 0.35,
        }
    )
    config = {"definitions": {"peak_hours_local": [7], "peak_weekdays_only": True}}
    result = aggregate_hourly(frame, config)
    assert len(result) == 1
    assert result.loc[0, "n_5min_intervals"] == 12
    assert result.loc[0, "rrp_aud_mwh"] == 0.5
    assert result.loc[0, "negative_price_share_5min"] == 5 / 12
    assert bool(result.loc[0, "negative_price_any"])
    assert not bool(result.loc[0, "negative_price_below_minus_50_any_5min"])
    assert not bool(result.loc[0, "negative_price_below_minus_100_any_5min"])
    validate_hourly_panel(result)
