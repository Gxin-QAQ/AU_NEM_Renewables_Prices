from __future__ import annotations

import pandas as pd

from src.nonlinear_estimation import coarse_nonlinear_design


def test_coarse_design_has_intercept_and_drops_one_category_per_effect():
    frame = pd.DataFrame(
        {
            "headline_sample": [True, True, True, True],
            "negative_price_any": [False, True, False, True],
            "renewable_share_ws_10pp_winsor_p999": [0.1, 0.2, 0.3, 0.4],
            "log_demand_centered": [0.0, 0.1, 0.2, 0.3],
            "log_demand_centered_sq": [0.0, 0.01, 0.04, 0.09],
            "region_month": ["a", "a", "b", "b"],
            "local_hour_weekday": ["x", "y", "x", "y"],
            "aest_week": ["w1", "w1", "w2", "w2"],
        }
    )
    outcome, design, clusters = coarse_nonlinear_design(frame)
    assert len(outcome) == 4
    assert design["const"].eq(1.0).all()
    assert design.shape[1] == 1 + 3 + 1 + 1
    assert clusters.nunique() == 2
