from pathlib import Path

from src.summarise_task9 import build_summary


def test_task9_summary_excludes_demand_controls_and_labels_claims():
    root = Path(__file__).resolve().parents[1]
    result = build_summary(root)
    assert not result["parameter"].str.startswith("log_demand").any()
    assert result["claim_boundary"].eq("conditional association; not causal").all()
    assert "per 100 MW wind-plus-solar output" in set(result["effect_unit"])
