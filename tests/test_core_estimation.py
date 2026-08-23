from __future__ import annotations

import numpy as np
import pandas as pd

from src.core_estimation import interaction_regressors


def test_peak_interaction_uses_off_peak_as_the_base_slope():
    frame = pd.DataFrame(
        {
            "renewable_share_ws_10pp_winsor_p999": [1.0, 2.0],
            "log_demand_centered": [0.0, 0.1],
            "log_demand_centered_sq": [0.0, 0.01],
            "peak": [False, True],
        }
    )
    regressors, contrasts = interaction_regressors(frame, "peak")
    column = "renewable_share_ws_10pp_winsor_p999_x_peak"
    assert column in regressors
    assert np.allclose(frame[column], [0.0, 2.0])
    assert contrasts["off_peak"] == {"renewable_share_ws_10pp_winsor_p999": 1.0}
    assert contrasts["peak"][column] == 1.0
