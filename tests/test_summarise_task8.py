from pathlib import Path

from src.summarise_task8 import build_headline_table


def test_task8_headline_summary_has_core_dynamic_and_nonlinear_rows():
    root = Path(__file__).resolve().parents[1]
    result = build_headline_table(root)
    assert len(result) == 15
    assert {"headline_fixed_effects", "distributed_lag_price_asinh", "secondary_nonlinear"} == set(result["section"])
    assert result.loc[result["model"] == "core_rrp_aud_mwh", "estimate"].iloc[0] < 0
