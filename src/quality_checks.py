"""Small, fail-fast validation checks for the region-time panel."""

from __future__ import annotations

import pandas as pd


EXPECTED_REGIONS = {"NSW1", "VIC1", "QLD1", "SA1", "TAS1"}


def validate_region_panel(frame: pd.DataFrame) -> None:
    """Raise a useful error when core panel keys or outcome fields are invalid."""
    required = {"timestamp", "region", "rrp_aud_mwh", "demand_mw"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"Panel is missing required columns: {sorted(missing)}")
    if frame[["timestamp", "region"]].duplicated().any():
        raise ValueError("Panel has duplicate region-time observations.")
    unexpected = set(frame["region"].dropna().unique()) - EXPECTED_REGIONS
    if unexpected:
        raise ValueError(f"Unexpected NEM region codes: {sorted(unexpected)}")
    # AEMO operational demand can be negative during very high distributed-PV
    # output. Downstream share construction must flag non-positive denominators
    # rather than rejecting otherwise valid regional price observations.
