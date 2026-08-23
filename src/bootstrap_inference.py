"""Task 9 week-cluster score-multiplier inference for costly contrasts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
from linearmodels.iv import AbsorbingLS
from scipy.stats import norm

from src.core_estimation import CONTROLS, EFFECTS, EXPOSURE, LAG_BLOCKS
from src.nonlinear_estimation import coarse_nonlinear_design


REPLICATIONS = 399
SEED = 20260823


def multiplier_summary(estimate: float, cluster_influence: np.ndarray, weights: np.ndarray) -> dict[str, float]:
    """Summarise a centred cluster-score multiplier distribution."""
    delta = weights @ cluster_influence
    boot_estimate = estimate + delta
    p_value = (1.0 + np.count_nonzero(np.abs(delta) >= abs(estimate))) / (len(delta) + 1.0)
    return {
        "estimate": float(estimate),
        "bootstrap_std_error": float(delta.std(ddof=1)),
        "bootstrap_p_value": float(p_value),
        "ci_lower": float(np.quantile(boot_estimate, 0.025)),
        "ci_upper": float(np.quantile(boot_estimate, 0.975)),
    }


def cluster_scores(x: np.ndarray, score_factor: np.ndarray, cluster_codes: np.ndarray, n_clusters: int) -> np.ndarray:
    """Aggregate per-observation score rows without forming a second full matrix."""
    scores = np.zeros((n_clusters, x.shape[1]), dtype=float)
    chunk_size = 5_000
    for start in range(0, len(x), chunk_size):
        stop = min(start + chunk_size, len(x))
        np.add.at(scores, cluster_codes[start:stop], x[start:stop] * score_factor[start:stop, None])
    return scores


def distributed_lag_bootstrap(frame: pd.DataFrame, weights: np.ndarray) -> dict[str, object]:
    """Bootstrap the frozen contemporaneous-plus-lag-block price contrast."""
    regressors = [EXPOSURE, *LAG_BLOCKS, *CONTROLS]
    sample = frame.loc[frame["dynamic_sample"]].dropna(subset=["price_asinh", *regressors]).copy()
    model = AbsorbingLS(
        sample["price_asinh"].astype(float),
        sample[regressors].astype(float),
        absorb=sample[EFFECTS].astype("category"),
        drop_absorbed=True,
    )
    result = model.fit(cov_type="unadjusted")
    x = np.asarray(model.absorbed_exog, dtype=float)
    residual = np.asarray(result.resids, dtype=float)
    codes = pd.Categorical(sample["aest_week"]).codes
    scores = cluster_scores(x, residual, codes, weights.shape[1])
    bread = np.linalg.pinv(x.T @ x)
    contrast = np.array([1.0] * (1 + len(LAG_BLOCKS)) + [0.0] * len(CONTROLS))
    estimate = float(contrast @ result.params.to_numpy())
    influence = scores @ bread.T @ contrast
    summary = multiplier_summary(estimate, influence, weights)
    return {
        "model": "distributed_lag_price_asinh",
        "contrast": "contemporaneous_plus_lags_1_24",
        **summary,
        "nobs": int(result.nobs),
        "week_clusters": int(sample["aest_week"].nunique()),
    }


def nonlinear_ame_gradient(name: str, design: np.ndarray, params: np.ndarray, exposure_index: int) -> tuple[float, np.ndarray, np.ndarray]:
    """Return AME, its beta gradient, and the GLM per-observation score factor."""
    eta = design @ params
    if name == "logit":
        mu = 1.0 / (1.0 + np.exp(-np.clip(eta, -35.0, 35.0)))
        derivative = mu * (1.0 - mu)
        ame = params[exposure_index] * derivative.mean()
        gradient = np.zeros(len(params))
        gradient[exposure_index] = derivative.mean()
        gradient += params[exposure_index] * np.mean(
            design * (derivative * (1.0 - 2.0 * mu))[:, None], axis=0
        )
        return float(ame), gradient, mu
    if name == "probit":
        mu = norm.cdf(eta)
        derivative = norm.pdf(eta)
        ame = params[exposure_index] * derivative.mean()
        gradient = np.zeros(len(params))
        gradient[exposure_index] = derivative.mean()
        gradient += params[exposure_index] * np.mean(
            design * (-eta * derivative)[:, None], axis=0
        )
        return float(ame), gradient, mu
    raise ValueError(f"Unknown link: {name}")


def nonlinear_bootstrap(frame: pd.DataFrame, weights: np.ndarray) -> list[dict[str, object]]:
    """Use a cluster-score multiplier approximation for Logit/Probit AMEs."""
    outcome, design_frame, clusters = coarse_nonlinear_design(frame)
    design = design_frame.to_numpy(dtype=float, copy=False)
    y = outcome.to_numpy(dtype=float)
    codes = pd.Categorical(clusters).codes
    exposure_index = design_frame.columns.get_loc(EXPOSURE)
    rows: list[dict[str, object]] = []
    for name, link in [("logit", sm.families.links.Logit()), ("probit", sm.families.links.Probit())]:
        model = sm.GLM(y, design, family=sm.families.Binomial(link=link))
        result = model.fit(maxiter=150, tol=1e-9)
        if not result.converged:
            raise RuntimeError(f"{name} GLM did not converge in Task 9")
        params = np.asarray(result.params)
        ame, gradient, mu = nonlinear_ame_gradient(name, design, params, exposure_index)
        if name == "logit":
            score_factor = y - mu
        else:
            derivative = norm.pdf(design @ params)
            variance = np.clip(mu * (1.0 - mu), 1e-12, None)
            score_factor = (y - mu) * derivative / variance
        scores = cluster_scores(design, score_factor, codes, weights.shape[1])
        bread = np.asarray(result.normalized_cov_params)
        influence = scores @ bread.T @ gradient
        summary = multiplier_summary(ame, influence, weights)
        rows.append(
            {
                "model": name,
                "contrast": "negative_price_average_marginal_effect",
                **summary,
                "nobs": int(result.nobs),
                "week_clusters": int(clusters.nunique()),
            }
        )
    return rows


def run_bootstrap_inference(root: Path) -> dict[str, object]:
    """Run the bounded 399-replication week-cluster multiplier audit."""
    frame = pd.read_parquet(root / "data/processed/nem_region_hour_model.parquet")
    cluster_order = sorted(frame.loc[frame["headline_sample"], "aest_week"].unique())
    rng = np.random.default_rng(SEED)
    weights = rng.choice([-1.0, 1.0], size=(REPLICATIONS, len(cluster_order)))
    rows = [distributed_lag_bootstrap(frame, weights), *nonlinear_bootstrap(frame, weights)]
    output = root / "outputs/tables"
    output.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(output / "task9_week_multiplier_bootstrap.csv", index=False)
    manifest = {
        "replications": REPLICATIONS,
        "seed": SEED,
        "week_clusters": len(cluster_order),
        "method": "Rademacher week-cluster score-multiplier bootstrap",
        "method_boundary": "Computationally bounded influence-function approximation; not a pairs block refit of the high-dimensional fixed-effect and nonlinear models.",
        "models": [row["model"] for row in rows],
    }
    (root / "data/interim/task9_bootstrap_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    print(json.dumps(run_bootstrap_inference(args.root.resolve()), indent=2))


if __name__ == "__main__":
    main()
