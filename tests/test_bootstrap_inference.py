from __future__ import annotations

import numpy as np
from scipy.stats import norm

from src.bootstrap_inference import multiplier_summary, nonlinear_ame_gradient


def test_multiplier_summary_is_reproducible_and_centered_on_estimate():
    influence = np.array([0.2, -0.1])
    weights = np.array([[1.0, 1.0], [1.0, -1.0], [-1.0, 1.0], [-1.0, -1.0]])
    summary = multiplier_summary(0.5, influence, weights)
    assert summary["estimate"] == 0.5
    assert summary["bootstrap_std_error"] > 0
    assert summary["ci_lower"] < 0.5 < summary["ci_upper"]


def test_nonlinear_ame_gradients_match_finite_differences():
    design = np.array([[1.0, -0.5, 0.2], [1.0, 0.2, -0.1], [1.0, 0.8, 0.4]])
    params = np.array([-0.2, 0.4, 0.1])
    exposure_index = 1
    step = 1e-6
    for name in ["logit", "probit"]:
        _, gradient, _ = nonlinear_ame_gradient(name, design, params, exposure_index)
        numerical = []
        for index in range(len(params)):
            plus = params.copy()
            minus = params.copy()
            plus[index] += step
            minus[index] -= step
            eta_plus = design @ plus
            eta_minus = design @ minus
            if name == "logit":
                mu_plus = 1 / (1 + np.exp(-eta_plus))
                mu_minus = 1 / (1 + np.exp(-eta_minus))
                ame_plus = plus[exposure_index] * np.mean(mu_plus * (1 - mu_plus))
                ame_minus = minus[exposure_index] * np.mean(mu_minus * (1 - mu_minus))
            else:
                ame_plus = plus[exposure_index] * norm.pdf(eta_plus).mean()
                ame_minus = minus[exposure_index] * norm.pdf(eta_minus).mean()
            numerical.append((ame_plus - ame_minus) / (2 * step))
        assert np.allclose(gradient, numerical, atol=1e-7)
