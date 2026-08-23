from __future__ import annotations

import numpy as np
import pandas as pd

from src.robustness_estimation import prepare_task9_frame


def test_task9_frame_adds_labelled_cap_and_samples():
    frame = pd.DataFrame(
        {
            "region": ["NSW1", "TAS1", "SA1"],
            "renewable_share_ws": [0.5, 1.5, np.nan],
            "renewable_share_ws_10pp": [5.0, 15.0, np.nan],
            "log_demand": [1.0, 1.0, 1.0],
            "demand_mw": [10.0, 10.0, 10.0],
            "wind_mw": [2.0, 2.0, 2.0],
            "solar_utility_mw": [1.0, 1.0, 1.0],
            "unmapped_scada_mw": [1.0, 0.0, 0.0],
            "renewable_share_ws_winsor_p999": [0.5, 1.5, np.nan],
            "headline_sample": [True, False, False],
            "post_5ms": [True, True, True],
        }
    )
    result = prepare_task9_frame(frame)
    assert result["renewable_share_ws_10pp_cap1"].iloc[:2].tolist() == [5.0, 10.0]
    assert result["all_five_sample"].tolist() == [True, True, False]
    assert result["post_5ms_sample"].tolist() == [True, False, False]
    assert result["renewable_share_ws_unknown_upper_10pp_p999"].iloc[0] == 4.0
