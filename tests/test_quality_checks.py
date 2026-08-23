import pandas as pd
import pytest

from src.quality_checks import validate_region_panel


def test_valid_panel_passes():
    frame = pd.DataFrame(
        {
            "timestamp": [pd.Timestamp("2024-01-01 00:00:00+11:00")],
            "region": ["NSW1"],
            "rrp_aud_mwh": [72.5],
            "demand_mw": [7500.0],
        }
    )
    validate_region_panel(frame)


def test_duplicate_region_time_fails():
    frame = pd.DataFrame(
        {
            "timestamp": ["2024-01-01", "2024-01-01"],
            "region": ["NSW1", "NSW1"],
            "rrp_aud_mwh": [1.0, 1.0],
            "demand_mw": [1.0, 1.0],
        }
    )
    with pytest.raises(ValueError, match="duplicate"):
        validate_region_panel(frame)


def test_negative_operational_demand_is_retained_for_downstream_handling():
    frame = pd.DataFrame(
        {
            "timestamp": ["2024-01-01"],
            "region": ["SA1"],
            "rrp_aud_mwh": [-5.0],
            "demand_mw": [-10.0],
        }
    )
    validate_region_panel(frame)
