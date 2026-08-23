from __future__ import annotations

import numpy as np
import pandas as pd
import yaml

from src.specification_audit import add_model_features, alternating_demean


def test_alternating_demean_removes_crossed_group_means():
    frame = pd.DataFrame(
        {
            "value": [1.0, 2.0, 4.0, 8.0, 2.0, 3.0, 5.0, 9.0],
            "region_month": ["a", "a", "b", "b", "a", "a", "b", "b"],
            "timestamp": ["t1", "t2", "t1", "t2", "t3", "t4", "t3", "t4"],
        }
    )
    residual = alternating_demean(frame["value"], [frame["region_month"], frame["timestamp"]])
    assert residual.groupby(frame["region_month"]).mean().abs().max() < 1e-9
    assert residual.groupby(frame["timestamp"]).mean().abs().max() < 1e-9


def test_frozen_spec_forbids_a_causal_claim():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    spec = yaml.safe_load((root / "config/econometric_spec.yml").read_text(encoding="utf-8"))
    assert spec["version"] == "1.0-task7-frozen"
    assert spec["estimand"]["causal_claim"] is False
    assert spec["exposure"]["headline"]["transformed"] == "renewable_share_ws_10pp_winsor_p999"


def test_dynamic_sample_requires_all_lag_blocks_not_only_lag_24():
    timestamps = pd.date_range("2024-01-01", periods=26, freq="h", tz="Australia/Brisbane")
    frame = pd.DataFrame(
        {
            "region": "NSW1",
            "timestamp": timestamps,
            "rrp_aud_mwh": 50.0,
            "intrahour_price_sd": 5.0,
            "renewable_share_ws": 0.2,
            "renewable_share_broad": 0.3,
            "wind_mw": 100.0,
            "solar_utility_mw": 100.0,
            "demand_mw": 1000.0,
            "local_weekday": timestamps.dayofweek,
            "local_hour": timestamps.hour,
            "peak": False,
            "season": "DJF",
            "negative_price_any": False,
            "negative_price_below_minus_50_any_5min": False,
            "negative_price_below_minus_100_any_5min": False,
        }
    )
    # A missing exposure at t=10 contaminates the 13--24-hour lag block at t=25
    # even though its 24-hour lag is populated.
    frame.loc[10, "renewable_share_ws"] = np.nan
    result = add_model_features(frame)
    assert not result.loc[25, "dynamic_sample"]
