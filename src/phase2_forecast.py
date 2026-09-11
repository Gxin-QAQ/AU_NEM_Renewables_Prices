"""Information-set-audited Phase 2 negative-price forecasting replay.

The module deliberately uses the retained hourly snapshot as a conditional
historical replay.  It never reads the frozen model frame, and every model is
refit at a month boundary using labels that satisfy the declared two-hour
availability embargo.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import signal
import sys
import threading
import time
import warnings
from contextlib import contextmanager
from dataclasses import dataclass
from importlib import metadata
from pathlib import Path
from typing import Callable, Iterable, Iterator, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import LogisticRegression


MARKET_TZ = "Australia/Brisbane"
PHASE2_CONFIG = {
    "protocol_id": "phase2-negative-event-replay-v2",
    "target": "negative_price_any",
    "regions": ["NSW1", "QLD1", "SA1", "VIC1"],
    "lags_hours": [2, 24, 168],
    "availability": {
        "embargo_hours": 2,
        "rule": "source_interval_start + 2h <= target_or_fit_origin",
    },
    "initial_history_start": "2019-07-08 00:00",
    "evaluation": {
        "development": {
            "start": "2023-07-01 00:00",
            "end": "2024-07-01 00:00",
            "expected_nobs": 35136,
        },
        "confirmation": {
            "start": "2024-07-01 00:00",
            "end": "2025-07-01 00:00",
            "expected_nobs": 35040,
        },
    },
    "refit": "monthly_expanding",
    "models": [
        "seasonal_naive",
        "seasonal_frequency",
        "statistical_control",
        "renewable_candidate",
    ],
    "logistic": {
        "C": 1.0,
        "solver": "lbfgs",
        "max_iter": 1000,
        "tol": 1e-6,
        "class_weight": None,
        "random_state": 0,
    },
    "preprocessing": {
        "price_transform": "asinh",
        "price_scale_aud_mwh": 1.0,
        "numeric_standardisation": "training_window_mean_std_ddof0",
        "categorical_effects": {
            "region": ["NSW1", "QLD1", "SA1", "VIC1"],
            "local_hour": list(range(24)),
            "local_weekday": list(range(7)),
            "drop_first": True,
        },
    },
    "acceptance_gate": {
        "minimum_relative_brier_improvement": 0.02,
        "maximum_pooled_calibration_abs_bias_pp": 2.0,
        "maximum_regional_brier_degradation_vs_control": 0.02,
        "minimum_confirmation_bootstrap_q025": 0.0,
    },
    "bootstrap": {
        "replicates": 1000,
        "block_days": 7,
        "seed": 20260910,
    },
    "runtime": {"fit_budget_seconds": 1800},
    "risk_translation": {
        "unit": "expected region-hour negative-price events",
        "event_definition": "any negative five-minute RRP in target hour",
    },
}


def _config_timestamp(value: str) -> pd.Timestamp:
    return pd.Timestamp(value).tz_localize(MARKET_TZ)


ACTIVE_REGIONS = tuple(PHASE2_CONFIG["regions"])
TARGET_COLUMN = str(PHASE2_CONFIG["target"])
LAGS = tuple(PHASE2_CONFIG["lags_hours"])
EMBARGO_HOURS = float(PHASE2_CONFIG["availability"]["embargo_hours"])
EMBARGO = pd.to_timedelta(EMBARGO_HOURS, unit="h")
INITIAL_HISTORY_START = _config_timestamp(PHASE2_CONFIG["initial_history_start"])
EXPECTED_COUNTS = {
    mode: int(values["expected_nobs"])
    for mode, values in PHASE2_CONFIG["evaluation"].items()
}
DEVELOPMENT_START = _config_timestamp(PHASE2_CONFIG["evaluation"]["development"]["start"])
DEVELOPMENT_END = _config_timestamp(PHASE2_CONFIG["evaluation"]["development"]["end"])
CONFIRMATION_START = _config_timestamp(PHASE2_CONFIG["evaluation"]["confirmation"]["start"])
CONFIRMATION_END = _config_timestamp(PHASE2_CONFIG["evaluation"]["confirmation"]["end"])
MODEL_NAMES = tuple(PHASE2_CONFIG["models"])
FIT_BUDGET_SECONDS = float(PHASE2_CONFIG["runtime"]["fit_budget_seconds"])
EXPECTED_INPUT_SHA256 = "ad849647098e863a68e68951b40397c45b3995c833d9928f1a0a147a0dc93ffc"
DEFAULT_INPUT = Path("../tmp/AU_NEM_Task11_Baseline_20260823_1556/nem_region_hour.parquet")
DEFAULT_OUTPUT_DIR = Path("outputs/phase2")
BOOTSTRAP_SEED = int(PHASE2_CONFIG["bootstrap"]["seed"])
BOOTSTRAP_REPLICATES = int(PHASE2_CONFIG["bootstrap"]["replicates"])
BLOCK_DAYS = int(PHASE2_CONFIG["bootstrap"]["block_days"])
PROTOCOL_TEXT = json.dumps(PHASE2_CONFIG, sort_keys=True, separators=(",", ":"))
PROTOCOL_HASH = hashlib.sha256(PROTOCOL_TEXT.encode("utf-8")).hexdigest()

REQUIRED_INPUT_COLUMNS = (
    "timestamp",
    "region",
    "demand_mw",
    "wind_mw",
    "solar_utility_mw",
    "rrp_aud_mwh",
    TARGET_COLUMN,
)
BASE_LAG_COLUMNS = ("rrp_aud_mwh", TARGET_COLUMN, "demand_mw")
RENEWABLE_LAG_COLUMNS = ("wind_mw", "solar_utility_mw")


class Phase2Error(RuntimeError):
    """Base exception for an auditable protocol or data failure."""


class DataValidationError(Phase2Error):
    """Raised when the input cannot satisfy the fixed data contract."""


class ModelValidationError(Phase2Error):
    """Raised when a fixed statistical model is not safe to score."""


class FitBudgetExceeded(Phase2Error):
    """Raised when the fixed total fitting budget is exhausted."""


@dataclass(frozen=True)
class Standardization:
    means: np.ndarray
    scales: np.ndarray


@dataclass
class FittedLogistic:
    model: LogisticRegression
    standardization: Standardization
    candidate: bool
    feature_names: tuple[str, ...]
    fit_elapsed_seconds: float


def sha256_file(path: Path) -> str:
    """Return a file's SHA-256 without loading the whole file into memory."""

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def implementation_sha256() -> str:
    """Hash this implementation so development and confirmation bind together."""

    return sha256_file(Path(__file__).resolve())


def _check_fit_deadline(deadline: float | None, clock: Callable[[], float] = time.monotonic) -> None:
    """Raise before work when the fixed total fitting deadline has elapsed."""

    if deadline is not None and clock() >= deadline:
        raise FitBudgetExceeded("the fixed fitting budget has been exhausted")


@contextmanager
def _fit_deadline_guard(deadline: float | None) -> Iterator[None]:
    """Interrupt a scikit-learn fit when the process-level deadline expires."""

    _check_fit_deadline(deadline)
    if deadline is None or not hasattr(signal, "SIGALRM"):
        yield
        return
    if threading.current_thread() is not threading.main_thread():
        yield
        return
    previous_handler = signal.getsignal(signal.SIGALRM)
    previous_timer = signal.setitimer(signal.ITIMER_REAL, 0)

    def alarm_handler(_signum: int, _frame: object) -> None:
        raise FitBudgetExceeded("the fixed fitting budget has been exhausted")

    remaining = max(deadline - time.monotonic(), 0.001)
    signal.signal(signal.SIGALRM, alarm_handler)
    signal.setitimer(signal.ITIMER_REAL, remaining)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)
        if previous_timer[0] > 0 or previous_timer[1] > 0:
            signal.setitimer(signal.ITIMER_REAL, previous_timer[0], previous_timer[1])


def _as_market_timestamp(values: pd.Series) -> pd.Series:
    timestamps = pd.to_datetime(values)
    if timestamps.dt.tz is None:
        return timestamps.dt.tz_localize(MARKET_TZ)
    return timestamps.dt.tz_convert(MARKET_TZ)


def _required_lag_names(candidate: bool) -> list[str]:
    columns = list(BASE_LAG_COLUMNS)
    if candidate:
        columns.extend(RENEWABLE_LAG_COLUMNS)
    return [f"{column}_lag_{lag}" for column in columns for lag in LAGS]


def _validate_required_columns(frame: pd.DataFrame, columns: Iterable[str]) -> None:
    missing = sorted(set(columns).difference(frame.columns))
    if missing:
        raise DataValidationError(f"missing required columns: {missing}")
    invalid = [column for column in columns if frame[column].isna().any()]
    if invalid:
        raise DataValidationError(f"missing values in required columns: {invalid}")


def load_hourly_snapshot(path: Path, expected_sha256: str = EXPECTED_INPUT_SHA256) -> tuple[pd.DataFrame, str]:
    """Load and validate only the base hourly fields used by this extension."""

    if not path.exists():
        raise DataValidationError(f"input does not exist: {path}")
    actual_hash = sha256_file(path)
    if expected_sha256 and actual_hash != expected_sha256:
        raise DataValidationError(
            f"input SHA-256 mismatch: expected {expected_sha256}, got {actual_hash}"
        )
    frame = pd.read_parquet(path, columns=list(REQUIRED_INPUT_COLUMNS))
    _validate_required_columns(frame, REQUIRED_INPUT_COLUMNS)
    frame = frame.copy()
    frame["timestamp"] = _as_market_timestamp(frame["timestamp"])
    frame["region"] = frame["region"].astype(str)
    frame[TARGET_COLUMN] = frame[TARGET_COLUMN].astype(float)
    if not set(frame[TARGET_COLUMN].unique()).issubset({0.0, 1.0}):
        raise DataValidationError(f"{TARGET_COLUMN} must contain only 0/1 labels")
    for column in ("demand_mw", "wind_mw", "solar_utility_mw", "rrp_aud_mwh"):
        frame[column] = pd.to_numeric(frame[column], errors="raise").astype(float)
    if frame.duplicated(["timestamp", "region"]).any():
        raise DataValidationError("duplicate region-hour keys in input")
    unknown = sorted(set(frame["region"]) - set(ACTIVE_REGIONS) - {"TAS1"})
    if unknown:
        raise DataValidationError(f"unexpected regions in input: {unknown}")
    return frame.sort_values(["region", "timestamp"], ignore_index=True), actual_hash


def add_exact_lags(frame: pd.DataFrame, lags: Sequence[int] = LAGS) -> pd.DataFrame:
    """Add timestamp-checked within-region lags without bridging a gap.

    A shifted value is retained only when its source timestamp is exactly the
    requested number of hours earlier.  This makes a missing hour visible as a
    missing feature instead of silently treating the prior row as the lag.
    """

    result = frame.sort_values(["region", "timestamp"], ignore_index=True).copy()
    for column in (*BASE_LAG_COLUMNS, *RENEWABLE_LAG_COLUMNS):
        if column not in result.columns:
            continue
        grouped = result.groupby("region", sort=False, observed=True)
        for lag in lags:
            shifted = grouped[column].shift(lag)
            prior_timestamp = grouped["timestamp"].shift(lag)
            exact = result["timestamp"].sub(prior_timestamp).eq(pd.to_timedelta(lag, unit="h"))
            result[f"{column}_lag_{lag}"] = shifted.where(exact)
    result["local_hour"] = result["timestamp"].dt.hour.astype(int)
    result["local_weekday"] = result["timestamp"].dt.dayofweek.astype(int)
    return result


def validate_information_set(rows: pd.DataFrame, origin: pd.Series | pd.Timestamp) -> None:
    """Verify that every declared lag is available by the supplied origin."""

    if isinstance(origin, pd.Timestamp):
        origins = pd.Series(origin, index=rows.index)
    else:
        origins = _as_market_timestamp(origin)
    target_time = _as_market_timestamp(rows["timestamp"])
    for lag in LAGS:
        source_time = target_time - pd.to_timedelta(lag, unit="h")
        available_at = source_time + EMBARGO
        if (available_at > origins).any():
            raise DataValidationError(f"lag {lag} has a value after its forecast origin")


def validate_label_availability(rows: pd.DataFrame, fit_origin: pd.Timestamp) -> None:
    """Ensure no realised target label enters a fit before its assumed release."""

    available_at = _as_market_timestamp(rows["timestamp"]) + EMBARGO
    if (available_at > fit_origin).any():
        raise DataValidationError("training labels include a value unavailable at fit origin")


def _assert_finite(frame: pd.DataFrame, columns: Iterable[str], label: str) -> None:
    values = frame[list(columns)].to_numpy(dtype=float)
    if not np.isfinite(values).all():
        bad = [column for column in columns if not np.isfinite(frame[column].to_numpy(dtype=float)).all()]
        raise DataValidationError(f"non-finite {label} columns: {bad}")


def _feature_frame(frame: pd.DataFrame) -> pd.DataFrame:
    result = add_exact_lags(frame)
    result = result[result["region"].isin(ACTIVE_REGIONS)].copy()
    result[TARGET_COLUMN] = result[TARGET_COLUMN].astype(float)
    return result.sort_values(["timestamp", "region"], ignore_index=True)


def _calendar_matrix(frame: pd.DataFrame) -> tuple[np.ndarray, tuple[str, ...]]:
    category_config = PHASE2_CONFIG["preprocessing"]["categorical_effects"]
    categories: tuple[tuple[object, ...], ...] = (
        tuple(category_config["region"]),
        tuple(category_config["local_hour"]),
        tuple(category_config["local_weekday"]),
    )
    values = (frame["region"], frame["local_hour"], frame["local_weekday"])
    matrices: list[np.ndarray] = []
    names: list[str] = []
    for series, allowed in zip(values, categories):
        codes = pd.Categorical(series, categories=list(allowed)).codes
        if (codes < 0).any():
            raise DataValidationError("categorical calendar value is outside fixed categories")
        matrix = np.zeros((len(frame), len(allowed) - 1), dtype=float)
        for output_column, category_code in enumerate(range(1, len(allowed))):
            matrix[:, output_column] = codes == category_code
            names.append(f"{series.name}_{allowed[category_code]}")
        matrices.append(matrix)
    return np.column_stack(matrices), tuple(names)


def _numeric_values(frame: pd.DataFrame, numeric_names: Sequence[str]) -> np.ndarray:
    values = frame[list(numeric_names)].to_numpy(dtype=float)
    if any(name.startswith("rrp_aud_mwh_lag_") for name in numeric_names):
        price_columns = [
            index
            for index, name in enumerate(numeric_names)
            if name.startswith("rrp_aud_mwh_lag_")
        ]
        price_transform = PHASE2_CONFIG["preprocessing"]["price_transform"]
        price_scale = float(PHASE2_CONFIG["preprocessing"]["price_scale_aud_mwh"])
        if price_scale <= 0:
            raise DataValidationError("price scale must be positive")
        if price_transform == "asinh":
            values[:, price_columns] = np.arcsinh(values[:, price_columns] / price_scale)
        elif price_transform != "identity":
            raise DataValidationError(f"unsupported price transform: {price_transform}")
    return values


def _design_matrix(
    frame: pd.DataFrame,
    numeric_names: Sequence[str],
    standardization: Standardization | None = None,
) -> tuple[np.ndarray, Standardization | None, tuple[str, ...]]:
    numeric = _numeric_values(frame, numeric_names)
    if not np.isfinite(numeric).all():
        raise DataValidationError("non-finite numeric feature value")
    if standardization is None:
        means = numeric.mean(axis=0)
        scales = numeric.std(axis=0, ddof=0)
        scales = np.where(scales == 0, 1.0, scales)
        standardization = Standardization(means=means, scales=scales)
    numeric = (numeric - standardization.means) / standardization.scales
    calendar, calendar_names = _calendar_matrix(frame)
    names = tuple(numeric_names) + calendar_names
    return np.column_stack([numeric, calendar]), standardization, names


def _numeric_feature_names(candidate: bool) -> tuple[str, ...]:
    names: list[str] = []
    for base in ("rrp_aud_mwh", TARGET_COLUMN, "demand_mw"):
        names.extend(f"{base}_lag_{lag}" for lag in LAGS)
    if candidate:
        for base in ("wind", "solar_utility"):
            names.extend(f"{base}_mw_lag_{lag}" for lag in LAGS)
    return tuple(names)


def fit_logistic(
    train: pd.DataFrame,
    candidate: bool,
    deadline: float | None = None,
) -> FittedLogistic:
    """Fit one fixed pooled logistic model using training-window statistics."""

    _check_fit_deadline(deadline)
    numeric_names = _numeric_feature_names(candidate)
    _assert_finite(train, [TARGET_COLUMN, *(_required_lag_names(candidate))], "training")
    y = train[TARGET_COLUMN].to_numpy(dtype=int)
    if np.unique(y).size < 2:
        raise ModelValidationError("training window contains only one target class")
    design, standardization, feature_names = _design_matrix(train, numeric_names)
    classifier = LogisticRegression(**PHASE2_CONFIG["logistic"])
    fit_started = time.monotonic()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", ConvergenceWarning)
        with _fit_deadline_guard(deadline):
            classifier.fit(design, y)
    fit_elapsed_seconds = time.monotonic() - fit_started
    _check_fit_deadline(deadline)
    if any(isinstance(item.message, ConvergenceWarning) for item in caught):
        raise ModelValidationError("logistic regression did not converge")
    if np.asarray(classifier.n_iter_).max() >= classifier.max_iter:
        raise ModelValidationError("logistic regression reached max_iter")
    return FittedLogistic(
        classifier,
        standardization,
        candidate,
        feature_names,
        fit_elapsed_seconds,
    )


def predict_logistic(fitted: FittedLogistic, rows: pd.DataFrame) -> np.ndarray:
    numeric_names = _numeric_feature_names(fitted.candidate)
    design, _, feature_names = _design_matrix(rows, numeric_names, fitted.standardization)
    if feature_names != fitted.feature_names:
        raise ModelValidationError("feature design changed between fit and prediction")
    predictions = fitted.model.predict_proba(design)[:, 1]
    if not np.isfinite(predictions).all() or ((predictions < 0) | (predictions > 1)).any():
        raise ModelValidationError("logistic prediction outside [0, 1]")
    return predictions


def seasonal_frequency_predictions(train: pd.DataFrame, rows: pd.DataFrame) -> np.ndarray:
    """Return smoothed region-hour-weekday event rates from training only."""

    training = train[["region", "local_hour", "local_weekday", TARGET_COLUMN]].copy()
    training["target"] = training.pop(TARGET_COLUMN).astype(float)
    pooled = (training["target"].sum() + 1.0) / (len(training) + 2.0)
    region_stats = training.groupby("region", observed=True)["target"].agg(["sum", "count"])
    region_prob = (region_stats["sum"] + 1.0) / (region_stats["count"] + 2.0)
    cell_stats = training.groupby(
        ["region", "local_hour", "local_weekday"], observed=True
    )["target"].agg(["sum", "count"])
    cell_prob = (cell_stats["sum"] + 1.0) / (cell_stats["count"] + 2.0)
    predictions: list[float] = []
    for row in rows[["region", "local_hour", "local_weekday"]].itertuples(index=False):
        key = (row.region, row.local_hour, row.local_weekday)
        if key in cell_prob.index:
            predictions.append(float(cell_prob.loc[key]))
        elif row.region in region_prob.index:
            predictions.append(float(region_prob.loc[row.region]))
        else:
            predictions.append(float(pooled))
    return np.asarray(predictions, dtype=float)


def _month_starts(start: pd.Timestamp, end: pd.Timestamp) -> list[pd.Timestamp]:
    return list(pd.date_range(start=start, end=end, freq="MS", inclusive="left"))


def _period(mode: str) -> tuple[pd.Timestamp, pd.Timestamp]:
    if mode == "development":
        return DEVELOPMENT_START, DEVELOPMENT_END
    if mode == "confirmation":
        return CONFIRMATION_START, CONFIRMATION_END
    raise ValueError(f"unknown mode: {mode}")


def _validate_evaluation_rows(frame: pd.DataFrame, mode: str) -> pd.DataFrame:
    start, end = _period(mode)
    rows = frame[(frame["timestamp"] >= start) & (frame["timestamp"] < end)].copy()
    expected = EXPECTED_COUNTS[mode]
    if len(rows) != expected:
        raise DataValidationError(f"{mode} row count {len(rows)} != expected {expected}")
    required = [TARGET_COLUMN, *_required_lag_names(True)]
    _assert_finite(rows, required, f"{mode} evaluation")
    validate_information_set(rows, rows["timestamp"])
    return rows


def validate_replay_scope(predictions: pd.DataFrame, mode: str) -> None:
    """Ensure a replay output contains only its registered target period."""

    start, end = _period(mode)
    if predictions.empty:
        raise DataValidationError(f"{mode} replay produced no predictions")
    timestamps = _as_market_timestamp(predictions["timestamp"])
    fit_origins = _as_market_timestamp(predictions["fit_origin"])
    if ((timestamps < start) | (timestamps >= end)).any():
        raise DataValidationError(f"{mode} predictions include an out-of-period target")
    if ((fit_origins < start) | (fit_origins >= end)).any():
        raise DataValidationError(f"{mode} predictions include an out-of-period fit origin")
    if (fit_origins > timestamps).any():
        raise DataValidationError(f"{mode} fit origin occurs after its target")


def _fit_rows(frame: pd.DataFrame, fit_origin: pd.Timestamp) -> pd.DataFrame:
    rows = frame[
        (frame["timestamp"] >= INITIAL_HISTORY_START)
        & (frame["timestamp"] + EMBARGO <= fit_origin)
    ].copy()
    validate_label_availability(rows, fit_origin)
    _assert_finite(rows, [TARGET_COLUMN, *_required_lag_names(True)], "training")
    return rows


def generate_predictions(
    frame: pd.DataFrame,
    mode: str,
    deadline: float | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Run the fixed monthly expanding replay for one evaluation period."""

    evaluation = _validate_evaluation_rows(frame, mode)
    records: list[pd.DataFrame] = []
    fit_records: list[dict[str, object]] = []
    start, end = _period(mode)
    for fit_origin in _month_starts(start, end):
        _check_fit_deadline(deadline)
        month_end = min(fit_origin + pd.offsets.MonthBegin(1), end)
        rows = evaluation[(evaluation["timestamp"] >= fit_origin) & (evaluation["timestamp"] < month_end)].copy()
        train = _fit_rows(frame, fit_origin)
        if rows.empty:
            raise DataValidationError(f"empty evaluation month at {fit_origin}")
        validate_information_set(rows, rows["timestamp"])
        seasonal_naive = rows[f"{TARGET_COLUMN}_lag_168"].to_numpy(dtype=float)
        seasonal_frequency = seasonal_frequency_predictions(train, rows)
        control = fit_logistic(train, candidate=False, deadline=deadline)
        candidate = fit_logistic(train, candidate=True, deadline=deadline)
        statistical_control = predict_logistic(control, rows)
        renewable_candidate = predict_logistic(candidate, rows)
        block = rows[["timestamp", "region", TARGET_COLUMN]].rename(
            columns={TARGET_COLUMN: "target"}
        )
        block["fit_origin"] = fit_origin
        block["seasonal_naive"] = seasonal_naive
        block["seasonal_frequency"] = seasonal_frequency
        block["statistical_control"] = statistical_control
        block["renewable_candidate"] = renewable_candidate
        records.append(block)
        fit_records.extend(
            [
                {
                    "fit_origin": fit_origin,
                    "model": "statistical_control",
                    "n_train": len(train),
                    "train_start": train["timestamp"].min(),
                    "train_end": train["timestamp"].max(),
                    "train_event_rate": train[TARGET_COLUMN].mean(),
                    "n_iter": int(np.asarray(control.model.n_iter_).max()),
                    "fit_elapsed_seconds": control.fit_elapsed_seconds,
                },
                {
                    "fit_origin": fit_origin,
                    "model": "renewable_candidate",
                    "n_train": len(train),
                    "train_start": train["timestamp"].min(),
                    "train_end": train["timestamp"].max(),
                    "train_event_rate": train[TARGET_COLUMN].mean(),
                    "n_iter": int(np.asarray(candidate.model.n_iter_).max()),
                    "fit_elapsed_seconds": candidate.fit_elapsed_seconds,
                },
            ]
        )
    predictions = pd.concat(records, ignore_index=True).sort_values(
        ["timestamp", "region"], ignore_index=True
    )
    if predictions[["timestamp", "region"]].duplicated().any():
        raise DataValidationError("duplicate evaluation keys in predictions")
    if len(predictions) != EXPECTED_COUNTS[mode]:
        raise DataValidationError("prediction count changed during monthly replay")
    validate_replay_scope(predictions, mode)
    for model in MODEL_NAMES:
        if not np.isfinite(predictions[model].to_numpy(dtype=float)).all():
            raise ModelValidationError(f"non-finite predictions for {model}")
    return predictions, pd.DataFrame(fit_records)


def brier_score(y_true: Sequence[float], probabilities: Sequence[float]) -> float:
    y = np.asarray(y_true, dtype=float)
    p = np.asarray(probabilities, dtype=float)
    if len(y) != len(p):
        raise ValueError("y and probabilities have different lengths")
    return float(np.mean((p - y) ** 2))


def log_loss_clipped(y_true: Sequence[float], probabilities: Sequence[float]) -> float:
    y = np.asarray(y_true, dtype=float)
    p = np.clip(np.asarray(probabilities, dtype=float), 1e-6, 1 - 1e-6)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log1p(-p)))


def _long_predictions(predictions: pd.DataFrame) -> pd.DataFrame:
    long = predictions.melt(
        id_vars=["timestamp", "region", "target", "fit_origin"],
        value_vars=list(MODEL_NAMES),
        var_name="model",
        value_name="probability",
    )
    long["loss_brier"] = (long["probability"] - long["target"]) ** 2
    return long


def _metric_row(scope: str, model: str, rows: pd.DataFrame) -> dict[str, object]:
    y = rows["target"].to_numpy(dtype=float)
    p = rows["probability"].to_numpy(dtype=float)
    return {
        "scope": scope,
        "model": model,
        "nobs": len(rows),
        "brier_score": brier_score(y, p),
        "log_loss": log_loss_clipped(y, p),
        "mean_predicted": float(p.mean()),
        "observed_rate": float(y.mean()),
        "calibration_bias_pp": float((p.mean() - y.mean()) * 100.0),
    }


def compute_metrics(predictions: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Return pooled/region scores, fixed-bin calibration and risk translation."""

    long = _long_predictions(predictions)
    metric_rows: list[dict[str, object]] = []
    calibration_rows: list[dict[str, object]] = []
    risk_rows: list[dict[str, object]] = []
    scopes: list[tuple[str, pd.Series]] = [("pooled", pd.Series(True, index=long.index))]
    scopes.extend((region, long["region"].eq(region)) for region in ACTIVE_REGIONS)
    for model in MODEL_NAMES:
        model_rows = long[long["model"].eq(model)]
        for scope, mask in scopes:
            selected = model_rows[mask.loc[model_rows.index]]
            metric_rows.append(_metric_row(scope, model, selected))
            probabilities = selected["probability"].to_numpy(dtype=float)
            for bin_id in range(10):
                lower = bin_id / 10.0
                upper = (bin_id + 1) / 10.0
                if bin_id == 9:
                    in_bin = (probabilities >= lower) & (probabilities <= upper)
                else:
                    in_bin = (probabilities >= lower) & (probabilities < upper)
                bin_rows = selected.iloc[np.flatnonzero(in_bin)]
                calibration_rows.append(
                    {
                        "scope": scope,
                        "model": model,
                        "probability_bin": bin_id,
                        "bin_lower": lower,
                        "bin_upper": upper,
                        "nobs": len(bin_rows),
                        "mean_predicted": float(bin_rows["probability"].mean()) if len(bin_rows) else np.nan,
                        "observed_rate": float(bin_rows["target"].mean()) if len(bin_rows) else np.nan,
                        "calibration_bias_pp": float((bin_rows["probability"].mean() - bin_rows["target"].mean()) * 100.0)
                        if len(bin_rows)
                        else np.nan,
                    }
                )
            risk_rows.append(
                {
                    "scope": scope,
                    "model": model,
                    "n_target_hours": len(selected),
                    "expected_negative_price_hours": float(selected["probability"].sum()),
                    "realised_negative_price_hours": int(selected["target"].sum()),
                    "expected_minus_realised_hours": float(selected["probability"].sum() - selected["target"].sum()),
                }
            )
    return (
        pd.DataFrame(metric_rows),
        pd.DataFrame(calibration_rows),
        pd.DataFrame(risk_rows),
    )


def evaluate_adoption_gate(
    metrics: pd.DataFrame,
    mode: str,
    bootstrap_lower_quantile: float | None = None,
) -> dict[str, object]:
    """Apply the pre-registered adoption gate without model selection."""

    pooled = metrics[metrics["scope"].eq("pooled")].set_index("model")
    candidate_brier = float(pooled.loc["renewable_candidate", "brier_score"])
    comparator_checks: dict[str, bool] = {}
    comparator_improvements: dict[str, float] = {}
    reasons: list[str] = []
    gate_config = PHASE2_CONFIG["acceptance_gate"]
    minimum_improvement = float(gate_config["minimum_relative_brier_improvement"])
    maximum_calibration_bias = float(gate_config["maximum_pooled_calibration_abs_bias_pp"])
    maximum_regional_degradation = float(gate_config["maximum_regional_brier_degradation_vs_control"])
    minimum_bootstrap_q025 = float(gate_config["minimum_confirmation_bootstrap_q025"])
    for comparator in MODEL_NAMES[:3]:
        comparator_brier = float(pooled.loc[comparator, "brier_score"])
        if comparator_brier <= 0:
            comparator_checks[comparator] = False
            comparator_improvements[comparator] = np.nan
            reasons.append(f"{comparator} has zero Brier score")
        else:
            improvement = 1.0 - candidate_brier / comparator_brier
            comparator_improvements[comparator] = improvement
            comparator_checks[comparator] = candidate_brier <= (1.0 - minimum_improvement) * comparator_brier
            if not comparator_checks[comparator]:
                reasons.append(f"candidate is not at least 2% below {comparator}")
    candidate_bias = abs(float(pooled.loc["renewable_candidate", "calibration_bias_pp"]))
    calibration_check = candidate_bias <= maximum_calibration_bias
    if not calibration_check:
        reasons.append(
            f"candidate pooled calibration bias exceeds {maximum_calibration_bias:g} percentage points"
        )
    regional = metrics[metrics["scope"].isin(ACTIVE_REGIONS)].pivot(
        index="scope", columns="model", values="brier_score"
    )
    regional_checks = {
        region: float(regional.loc[region, "renewable_candidate"])
        <= (1.0 + maximum_regional_degradation) * float(regional.loc[region, "statistical_control"])
        for region in ACTIVE_REGIONS
    }
    for region, passed in regional_checks.items():
        if not passed:
            reasons.append(f"candidate is more than 2% above control in {region}")
    bootstrap_check = True
    if mode == "confirmation":
        bootstrap_check = (
            bootstrap_lower_quantile is not None
            and bootstrap_lower_quantile > minimum_bootstrap_q025
        )
        if not bootstrap_check:
            reasons.append("confirmation bootstrap lower quantile is not positive")
    passed = all(comparator_checks.values()) and calibration_check and all(regional_checks.values()) and bootstrap_check
    return {
        "mode": mode,
        "passed": bool(passed),
        "reasons": reasons,
        "candidate_brier": candidate_brier,
        "candidate_calibration_abs_bias_pp": candidate_bias,
        "comparator_checks": comparator_checks,
        "comparator_relative_improvements": comparator_improvements,
        "regional_checks": regional_checks,
        "bootstrap_lower_quantile": bootstrap_lower_quantile,
        "gate_configuration": gate_config,
        "configuration_sha256": PROTOCOL_HASH,
        "protocol_hash": PROTOCOL_HASH,
    }


def moving_block_bootstrap(
    predictions: pd.DataFrame,
    replicates: int = BOOTSTRAP_REPLICATES,
    block_days: int = BLOCK_DAYS,
    seed: int = BOOTSTRAP_SEED,
) -> tuple[pd.DataFrame, dict[str, object]]:
    """Bootstrap daily control-minus-candidate Brier improvements in 7-day blocks."""

    long = _long_predictions(predictions)
    wide = long.pivot_table(
        index=["timestamp", "region", "target"], columns="model", values="loss_brier", aggfunc="first"
    ).reset_index()
    required = {"statistical_control", "renewable_candidate"}
    if not required.issubset(wide.columns):
        raise DataValidationError("bootstrap requires control and candidate losses")
    wide["local_date"] = wide["timestamp"].dt.date.astype(str)
    daily = (
        wide.assign(improvement=wide["statistical_control"] - wide["renewable_candidate"])
        .groupby("local_date", sort=True, observed=True)["improvement"]
        .mean()
    )
    values = daily.to_numpy(dtype=float)
    if len(values) < block_days:
        raise DataValidationError("confirmation period is shorter than bootstrap block")
    rng = np.random.default_rng(seed)
    starts = np.arange(len(values) - block_days + 1)
    n_blocks = int(np.ceil(len(values) / block_days))
    draws = np.empty(replicates, dtype=float)
    for replicate in range(replicates):
        chosen = rng.choice(starts, size=n_blocks, replace=True)
        sample = np.concatenate([values[start : start + block_days] for start in chosen])[: len(values)]
        draws[replicate] = sample.mean()
    result = pd.DataFrame({"replicate": np.arange(replicates), "mean_brier_improvement": draws})
    summary = {
        "daily_observations": len(values),
        "block_days": block_days,
        "replicates": replicates,
        "seed": seed,
        "observed_mean_improvement": float(values.mean()),
        "q025": float(np.quantile(draws, 0.025)),
        "q500": float(np.quantile(draws, 0.5)),
        "q975": float(np.quantile(draws, 0.975)),
    }
    return result, summary


def calibration_curve_points(
    calibration: pd.DataFrame,
    model: str,
    scope: str = "pooled",
) -> tuple[np.ndarray, np.ndarray]:
    """Return observed calibration points at their actual predicted means."""

    rows = calibration[
        calibration["scope"].eq(scope) & calibration["model"].eq(model)
    ][["mean_predicted", "observed_rate"]].dropna()
    return (
        rows["mean_predicted"].to_numpy(dtype=float),
        rows["observed_rate"].to_numpy(dtype=float),
    )


def plot_calibration(calibration: pd.DataFrame, output_path: Path) -> None:
    """Write the fixed pooled probability-decile calibration figure."""

    fig, axis = plt.subplots(figsize=(7.2, 5.4), constrained_layout=True)
    axis.plot([0, 1], [0, 1], color="#555555", linestyle="--", linewidth=1, label="perfect calibration")
    for model in MODEL_NAMES:
        predicted, observed = calibration_curve_points(calibration, model)
        axis.plot(predicted, observed, marker="o", linewidth=1.6, label=model.replace("_", " "))
    axis.set(xlim=(0, 1), ylim=(0, 1), xlabel="Mean predicted probability", ylabel="Observed event rate")
    axis.set_title("Negative-price event calibration by fixed probability decile")
    axis.legend(frameon=False, fontsize=8)
    fig.savefig(output_path, dpi=180)
    plt.close(fig)


def _json_safe(value: object) -> object:
    if isinstance(value, (np.integer, np.floating)):
        return value.item()
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, (pd.Timestamp,)):  # pragma: no cover - manifest formatting
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(_json_safe(payload), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _package_versions() -> dict[str, str]:
    names = ("numpy", "pandas", "pyarrow", "scikit-learn", "matplotlib")
    return {name: metadata.version(name) for name in names}


def _artifact_paths(mode: str, destination: Path) -> dict[str, Path]:
    """Return the persisted evidence files that bind a completed replay."""

    if mode not in ("development", "confirmation"):
        raise ValueError(f"unknown mode: {mode}")
    paths = {
        "configuration": destination / "phase2_configuration.json",
        "predictions": destination / f"{mode}_predictions.parquet",
        "metrics": destination / f"{mode}_metrics.csv",
        "calibration": destination / f"{mode}_calibration.csv",
        "risk_translation": destination / f"{mode}_risk_translation.csv",
        "fit_manifest": destination / f"{mode}_fit_manifest.csv",
        "calibration_figure": destination / f"{mode}_calibration.png",
    }
    if mode == "confirmation":
        paths.update(
            {
                "bootstrap": destination / "confirmation_bootstrap.csv",
                "bootstrap_summary": destination / "confirmation_bootstrap_summary.json",
            }
        )
    return paths


def _check_confirmation_prerequisite(
    output_dir: Path,
    input_hash: str,
    source_digest: str,
) -> None:
    gate_path = output_dir / "development_gate.json"
    manifest_path = output_dir / "development_manifest.json"
    if not gate_path.exists() or not manifest_path.exists():
        raise Phase2Error("confirmation is blocked until development outputs exist")
    gate = json.loads(gate_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("run_status") != "complete" or gate.get("run_status") != "complete":
        raise Phase2Error("confirmation is blocked because development is incomplete or stale")
    if not gate.get("passed", False):
        raise Phase2Error("confirmation is blocked because the development gate failed")
    if manifest.get("input_sha256") != input_hash:
        raise Phase2Error("confirmation input hash differs from development")
    if manifest.get("configuration_sha256") != PROTOCOL_HASH or manifest.get("protocol_hash") != PROTOCOL_HASH:
        raise Phase2Error("confirmation configuration differs from development")
    if gate.get("configuration_sha256") != PROTOCOL_HASH or gate.get("protocol_hash") != PROTOCOL_HASH:
        raise Phase2Error("confirmation gate configuration differs from development")
    if manifest.get("source_sha256") != source_digest or gate.get("source_sha256") != source_digest:
        raise Phase2Error("confirmation implementation differs from development")
    artifact_hashes = manifest.get("artifact_sha256")
    if not isinstance(artifact_hashes, dict):
        raise Phase2Error("confirmation is blocked because saved development evidence is missing")
    for name, path in _artifact_paths("development", output_dir).items():
        expected = artifact_hashes.get(name)
        if not path.exists() or not isinstance(expected, str):
            raise Phase2Error(f"confirmation is blocked because saved development evidence is missing: {name}")
        if sha256_file(path) != expected:
            raise Phase2Error(f"confirmation is blocked because saved development evidence is stale: {name}")


def _manifest_base(
    mode: str,
    path: Path,
    input_hash: str,
    source_digest: str,
) -> dict[str, object]:
    """Return the common provenance fields written before and after a run."""

    return {
        "mode": mode,
        "input_path": path,
        "input_sha256": input_hash,
        "configuration": PHASE2_CONFIG,
        "configuration_sha256": PROTOCOL_HASH,
        "protocol_hash": PROTOCOL_HASH,
        "protocol_id": PHASE2_CONFIG["protocol_id"],
        "source_path": Path(__file__).resolve(),
        "source_sha256": source_digest,
        "regions": list(ACTIVE_REGIONS),
        "lags_hours": list(LAGS),
        "embargo_hours": EMBARGO_HOURS,
        "availability_rule": PHASE2_CONFIG["availability"]["rule"],
        "availability_checks": {
            "exact_within_region_lags": True,
            "evaluation_feature_origin_check": True,
            "training_label_origin_check": True,
            "training_window_standardisation": True,
        },
        "initial_history_start": INITIAL_HISTORY_START,
        "period_start": _period(mode)[0],
        "period_end": _period(mode)[1],
        "models": list(MODEL_NAMES),
        "feature_groups": {
            "calendar": ["region", "local_hour", "local_weekday"],
            "lag_hours": list(LAGS),
            "control_lags": ["rrp_aud_mwh", TARGET_COLUMN, "demand_mw"],
            "candidate_additions": ["wind_mw", "solar_utility_mw"],
        },
        "fit_budget_seconds": FIT_BUDGET_SECONDS,
        "package_versions": _package_versions(),
    }


def run(mode: str, root: Path, input_path: Path | None = None, output_dir: Path | None = None) -> dict[str, object]:
    """Run development or confirmation mode and persist all audit artefacts."""

    if mode not in ("development", "confirmation"):
        raise ValueError(f"unknown mode: {mode}")
    run_started = time.monotonic()
    root = root.resolve()
    path = (root / (input_path or DEFAULT_INPUT)).resolve()
    destination = (root / (output_dir or DEFAULT_OUTPUT_DIR)).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    frame, input_hash = load_hourly_snapshot(path)
    source_digest = implementation_sha256()
    prefix = mode
    if mode == "confirmation":
        _check_confirmation_prerequisite(destination, input_hash, source_digest)
    manifest_path = destination / f"{prefix}_manifest.json"
    base_manifest = _manifest_base(mode, path, input_hash, source_digest)
    _write_json(destination / "phase2_configuration.json", PHASE2_CONFIG)
    _write_json(
        manifest_path,
        {
            **base_manifest,
            "run_status": "in_progress",
            "run_elapsed_seconds": 0.0,
        },
    )
    deadline = run_started + FIT_BUDGET_SECONDS
    try:
        feature_frame = _feature_frame(frame)
        predictions, fit_manifest = generate_predictions(feature_frame, mode, deadline=deadline)
        metrics, calibration, risk = compute_metrics(predictions)
        bootstrap_summary: dict[str, object] | None = None
        if mode == "confirmation":
            bootstrap, bootstrap_summary = moving_block_bootstrap(predictions)
            bootstrap.to_csv(destination / "confirmation_bootstrap.csv", index=False)
        lower = None if bootstrap_summary is None else float(bootstrap_summary["q025"])
        gate = evaluate_adoption_gate(metrics, mode, lower)
        gate = {
            **gate,
            "run_status": "complete",
            "input_sha256": input_hash,
            "source_sha256": source_digest,
            "configuration_sha256": PROTOCOL_HASH,
        }
        predictions.to_parquet(destination / f"{prefix}_predictions.parquet", index=False)
        metrics.to_csv(destination / f"{prefix}_metrics.csv", index=False)
        calibration.to_csv(destination / f"{prefix}_calibration.csv", index=False)
        risk.to_csv(destination / f"{prefix}_risk_translation.csv", index=False)
        fit_manifest.to_csv(destination / f"{prefix}_fit_manifest.csv", index=False)
        plot_calibration(calibration, destination / f"{prefix}_calibration.png")
        if bootstrap_summary is not None:
            _write_json(destination / "confirmation_bootstrap_summary.json", bootstrap_summary)
        artifact_hashes = {
            name: sha256_file(path)
            for name, path in _artifact_paths(mode, destination).items()
        }
        _write_json(destination / f"{prefix}_gate.json", gate)
        manifest = {
            **base_manifest,
            "run_status": "complete",
            "run_elapsed_seconds": time.monotonic() - run_started,
            "n_predictions": len(predictions),
            "fit_elapsed_seconds": float(fit_manifest["fit_elapsed_seconds"].sum()),
            "gate_passed": gate["passed"],
            "bootstrap": bootstrap_summary,
            "artifact_sha256": artifact_hashes,
        }
        _write_json(manifest_path, manifest)
    except Phase2Error as error:
        status = "incomplete_budget" if isinstance(error, FitBudgetExceeded) else "failed"
        elapsed = time.monotonic() - run_started
        failure_manifest = {
            **base_manifest,
            "run_status": status,
            "run_elapsed_seconds": elapsed,
            "error": str(error),
        }
        _write_json(manifest_path, failure_manifest)
        _write_json(
            destination / f"{prefix}_gate.json",
            {
                "mode": mode,
                "passed": False,
                "reasons": [str(error)],
                "run_status": status,
                "input_sha256": input_hash,
                "source_sha256": source_digest,
                "configuration_sha256": PROTOCOL_HASH,
                "protocol_hash": PROTOCOL_HASH,
            },
        )
        raise
    return {
        "mode": mode,
        "n_predictions": len(predictions),
        "gate_passed": bool(gate["passed"]),
        "candidate_brier": float(gate["candidate_brier"]),
        "output_dir": destination,
        "reasons": gate["reasons"],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("development", "confirmation"), required=True)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--input", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=None)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        summary = run(args.mode, args.root, args.input, args.output_dir)
    except Phase2Error as error:
        print(f"PHASE2 BLOCKED: {error}", file=sys.stderr)
        return 2
    print(json.dumps(_json_safe(summary), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
