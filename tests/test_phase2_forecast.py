from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.phase2_forecast import (
    ACTIVE_REGIONS,
    CONFIRMATION_START,
    DEVELOPMENT_END,
    DEVELOPMENT_START,
    DataValidationError,
    EMBARGO,
    FitBudgetExceeded,
    Phase2Error,
    PROTOCOL_HASH,
    add_exact_lags,
    brier_score,
    calibration_curve_points,
    compute_metrics,
    evaluate_adoption_gate,
    fit_logistic,
    predict_logistic,
    seasonal_frequency_predictions,
    validate_label_availability,
    validate_information_set,
    validate_replay_scope,
)


def _frame(hours: int = 8) -> pd.DataFrame:
    timestamps = pd.date_range("2024-01-01", periods=hours, freq="h", tz="Australia/Brisbane")
    rows = []
    for region in ("NSW1", "VIC1"):
        for index, timestamp in enumerate(timestamps):
            rows.append(
                {
                    "timestamp": timestamp,
                    "region": region,
                    "demand_mw": 100.0 + index,
                    "wind_mw": 10.0 + index,
                    "solar_utility_mw": 5.0 + index,
                    "rrp_aud_mwh": float(index - 3),
                    "negative_price_any": float(index % 2),
                }
            )
    return pd.DataFrame(rows)


def _long_frame(hours: int = 240) -> pd.DataFrame:
    timestamps = pd.date_range("2019-07-01", periods=hours, freq="h", tz="Australia/Brisbane")
    rows = []
    for region_index, region in enumerate(ACTIVE_REGIONS):
        for index, timestamp in enumerate(timestamps):
            rows.append(
                {
                    "timestamp": timestamp,
                    "region": region,
                    "demand_mw": 900.0 + 10.0 * region_index + (index % 24),
                    "wind_mw": 100.0 + 2.0 * region_index + (index % 13),
                    "solar_utility_mw": 80.0 + 3.0 * region_index + (index % 11),
                    "rrp_aud_mwh": 30.0 + 4.0 * region_index + (index % 19),
                    "negative_price_any": float((index + region_index) % 17 == 0),
                }
            )
    return pd.DataFrame(rows)


def test_exact_lags_are_within_region_and_do_not_bridge_gaps() -> None:
    frame = _frame()
    lagged = add_exact_lags(frame, lags=(1, 2))
    nsw = lagged[lagged.region.eq("NSW1")].sort_values("timestamp")
    vic = lagged[lagged.region.eq("VIC1")].sort_values("timestamp")
    assert nsw.iloc[2]["demand_mw_lag_1"] == 101.0
    assert vic.iloc[2]["demand_mw_lag_2"] == 100.0
    broken = frame.drop(frame.index[(frame.region.eq("NSW1")) & (frame.timestamp.dt.hour == 3)])
    broken_lags = add_exact_lags(broken, lags=(1, 2))
    broken_nsw = broken_lags[broken_lags.region.eq("NSW1")].sort_values("timestamp")
    row_after_gap = broken_nsw[broken_nsw.timestamp.dt.hour.eq(4)].iloc[0]
    assert pd.isna(row_after_gap["demand_mw_lag_1"])
    assert pd.isna(vic.iloc[0]["demand_mw_lag_1"])


def test_label_availability_accepts_boundary_and_rejects_one_nanosecond_before() -> None:
    timestamp = pd.Timestamp("2024-01-01 00:00", tz="Australia/Brisbane")
    row = pd.DataFrame({"timestamp": [timestamp]})
    validate_label_availability(row, timestamp + EMBARGO)
    with pytest.raises(DataValidationError):
        validate_label_availability(row, timestamp + EMBARGO - pd.to_timedelta(1, unit="ns"))


def test_information_set_rejects_a_lag_after_origin() -> None:
    frame = _frame().iloc[:2].copy()
    origin = pd.Timestamp("2024-01-01 00:00", tz="Australia/Brisbane")
    with pytest.raises(DataValidationError):
        validate_information_set(frame, origin)


def test_future_mutation_cannot_change_earlier_lags() -> None:
    original = _frame()
    changed = original.copy()
    changed.loc[changed.timestamp.eq(pd.Timestamp("2024-01-01 07:00", tz="Australia/Brisbane")), "wind_mw"] = 999_999.0
    first = add_exact_lags(original, lags=(2, 24))
    second = add_exact_lags(changed, lags=(2, 24))
    mask = first.timestamp < pd.Timestamp("2024-01-01 07:00", tz="Australia/Brisbane")
    for column in ("rrp_aud_mwh_lag_2", "wind_mw_lag_2"):
        pd.testing.assert_series_equal(first.loc[mask, column], second.loc[mask, column], check_names=False)


def test_future_mutation_cannot_change_selected_fit_or_prediction() -> None:
    from src.phase2_forecast import _feature_frame, _fit_rows

    origin = pd.Timestamp("2019-07-10 04:00", tz="Australia/Brisbane")
    raw = _long_frame()
    changed = raw.copy()
    future = changed["timestamp"] > origin + pd.to_timedelta(4, unit="h")
    for column in ("demand_mw", "wind_mw", "solar_utility_mw", "rrp_aud_mwh", "negative_price_any"):
        changed.loc[future, column] = 999_999.0 if column != "negative_price_any" else 1.0
    base_features = _feature_frame(raw)
    changed_features = _feature_frame(changed)
    train_base = _fit_rows(base_features, origin)
    train_changed = _fit_rows(changed_features, origin)
    pd.testing.assert_frame_equal(train_base, train_changed)
    fitted_base = fit_logistic(train_base, candidate=True)
    fitted_changed = fit_logistic(train_changed, candidate=True)
    np.testing.assert_allclose(
        fitted_base.standardization.means,
        fitted_changed.standardization.means,
    )
    targets = base_features[
        (base_features["timestamp"] >= origin)
        & (base_features["timestamp"] <= origin + pd.to_timedelta(4, unit="h"))
    ]
    changed_targets = changed_features.loc[targets.index]
    np.testing.assert_allclose(
        predict_logistic(fitted_base, targets),
        predict_logistic(fitted_changed, changed_targets),
    )


def test_missing_hour_is_fail_closed_for_model_fitting() -> None:
    from src.phase2_forecast import _feature_frame

    raw = _long_frame()
    raw = raw.drop(raw.index[(raw.region == "NSW1") & (raw.timestamp == pd.Timestamp("2019-07-05 00:00", tz="Australia/Brisbane"))])
    with pytest.raises(DataValidationError):
        fit_logistic(_feature_frame(raw), candidate=False)


def test_replay_scope_rejects_confirmation_rows_in_development() -> None:
    predictions = pd.DataFrame(
        {
            "timestamp": [DEVELOPMENT_START, CONFIRMATION_START],
            "fit_origin": [DEVELOPMENT_START, CONFIRMATION_START],
        }
    )
    with pytest.raises(DataValidationError, match="out-of-period"):
        validate_replay_scope(predictions, "development")


def test_calibration_points_use_actual_predicted_means() -> None:
    calibration = pd.DataFrame(
        {
            "scope": ["pooled"] * 3,
            "model": ["seasonal_naive"] * 3,
            "probability_bin": [0, 1, 9],
            "mean_predicted": [0.0, np.nan, 1.0],
            "observed_rate": [0.15, np.nan, 0.61],
        }
    )
    predicted, observed = calibration_curve_points(calibration, "seasonal_naive")
    np.testing.assert_array_equal(predicted, [0.0, 1.0])
    np.testing.assert_array_equal(observed, [0.15, 0.61])


def test_fit_budget_check_is_fail_closed_with_injected_clock() -> None:
    with pytest.raises(FitBudgetExceeded):
        from src.phase2_forecast import _check_fit_deadline

        _check_fit_deadline(10.0, clock=lambda: 10.001)


def test_training_only_standardization_is_not_full_sample() -> None:
    from src.phase2_forecast import _design_matrix

    frame = _frame()
    train = frame.iloc[:4].copy()
    train = add_exact_lags(train, lags=(1,))
    train = train.dropna().copy()
    names = ("demand_mw_lag_1",)
    _, standardization, _ = _design_matrix(train, names)
    assert standardization is not None
    assert standardization.means[0] == pytest.approx(train["demand_mw_lag_1"].mean())
    assert standardization.means[0] != pytest.approx(frame["demand_mw"].mean())


def test_seasonal_frequency_uses_training_only_and_laplace_smoothing() -> None:
    train = pd.DataFrame(
        {
            "region": ["NSW1", "NSW1"],
            "local_hour": [4, 5],
            "local_weekday": [0, 0],
            "negative_price_any": [1.0, 0.0],
        }
    )
    rows = pd.DataFrame(
        {
            "region": ["NSW1", "VIC1"],
            "local_hour": [4, 4],
            "local_weekday": [0, 0],
        }
    )
    predictions = seasonal_frequency_predictions(train, rows)
    assert predictions[0] == pytest.approx((1 + 1) / (1 + 2))
    assert predictions[1] == pytest.approx((1 + 1) / (2 + 2))


def test_brier_and_metrics_are_deterministic() -> None:
    assert brier_score([0, 1], [0.25, 0.75]) == pytest.approx(0.0625)
    timestamps = pd.date_range("2024-01-01", periods=4, freq="h", tz="Australia/Brisbane")
    predictions = pd.DataFrame(
        {
            "timestamp": timestamps,
            "region": ["NSW1", "VIC1", "QLD1", "SA1"],
            "target": [0.0, 1.0, 0.0, 1.0],
            "fit_origin": timestamps,
            "seasonal_naive": [0.0, 1.0, 0.0, 1.0],
            "seasonal_frequency": [0.5] * 4,
            "statistical_control": [0.25] * 4,
            "renewable_candidate": [0.25] * 4,
        }
    )
    metrics, calibration, risk = compute_metrics(predictions)
    pooled_naive = metrics[(metrics.scope == "pooled") & (metrics.model == "seasonal_naive")].iloc[0]
    assert pooled_naive.brier_score == pytest.approx(0.0)
    assert len(calibration[(calibration.scope == "pooled") & (calibration.model == "seasonal_naive")]) == 10
    assert risk[(risk.scope == "pooled") & (risk.model == "renewable_candidate")].iloc[0].realised_negative_price_hours == 2


def test_failed_gate_is_explicit() -> None:
    metrics = pd.DataFrame(
        [
            {"scope": "pooled", "model": model, "brier_score": 0.1, "calibration_bias_pp": 0.0}
            for model in ("seasonal_naive", "seasonal_frequency", "statistical_control", "renewable_candidate")
        ]
        + [
            {"scope": region, "model": model, "brier_score": 0.1, "calibration_bias_pp": 0.0}
            for region in ("NSW1", "QLD1", "SA1", "VIC1")
            for model in ("statistical_control", "renewable_candidate")
        ]
    )
    gate = evaluate_adoption_gate(metrics, "development")
    assert gate["passed"] is False
    assert gate["reasons"]


def test_confirmation_prerequisite_blocks_failed_development(tmp_path) -> None:
    import json

    from src.phase2_forecast import _check_confirmation_prerequisite

    output_dir = tmp_path / "phase2"
    output_dir.mkdir()
    (output_dir / "development_gate.json").write_text(
        json.dumps({"passed": False, "run_status": "complete"}), encoding="utf-8"
    )
    (output_dir / "development_manifest.json").write_text(
        json.dumps({"run_status": "complete"}), encoding="utf-8"
    )
    with pytest.raises(Phase2Error, match="development gate failed"):
        _check_confirmation_prerequisite(output_dir, "unused", "unused")


def test_confirmation_prerequisite_rejects_configuration_or_source_drift(tmp_path) -> None:
    import json

    from src.phase2_forecast import _check_confirmation_prerequisite

    output_dir = tmp_path / "phase2"
    output_dir.mkdir()
    complete = {
        "passed": True,
        "run_status": "complete",
        "input_sha256": "input",
        "configuration_sha256": "old-config",
        "protocol_hash": "old-config",
        "source_sha256": "old-source",
    }
    (output_dir / "development_gate.json").write_text(json.dumps(complete), encoding="utf-8")
    (output_dir / "development_manifest.json").write_text(json.dumps(complete), encoding="utf-8")
    with pytest.raises(Phase2Error, match="configuration differs"):
        _check_confirmation_prerequisite(output_dir, "input", "old-source")


def test_confirmation_prerequisite_rejects_incomplete_development(tmp_path) -> None:
    import json

    from src.phase2_forecast import _check_confirmation_prerequisite

    output_dir = tmp_path / "phase2"
    output_dir.mkdir()
    incomplete = {
        "passed": True,
        "run_status": "incomplete_budget",
        "input_sha256": "input",
        "configuration_sha256": PROTOCOL_HASH,
        "protocol_hash": PROTOCOL_HASH,
        "source_sha256": "source",
    }
    (output_dir / "development_gate.json").write_text(json.dumps(incomplete), encoding="utf-8")
    (output_dir / "development_manifest.json").write_text(json.dumps(incomplete), encoding="utf-8")
    with pytest.raises(Phase2Error, match="incomplete or stale"):
        _check_confirmation_prerequisite(output_dir, "input", "source")


def test_confirmation_prerequisite_rejects_source_drift_when_configuration_matches(tmp_path) -> None:
    import json

    from src.phase2_forecast import _check_confirmation_prerequisite

    output_dir = tmp_path / "phase2"
    output_dir.mkdir()
    complete = {
        "passed": True,
        "run_status": "complete",
        "input_sha256": "input",
        "configuration_sha256": PROTOCOL_HASH,
        "protocol_hash": PROTOCOL_HASH,
        "source_sha256": "old-source",
    }
    (output_dir / "development_gate.json").write_text(json.dumps(complete), encoding="utf-8")
    (output_dir / "development_manifest.json").write_text(json.dumps(complete), encoding="utf-8")
    with pytest.raises(Phase2Error, match="implementation differs"):
        _check_confirmation_prerequisite(output_dir, "input", "new-source")


def test_confirmation_prerequisite_requires_saved_development_evidence(tmp_path) -> None:
    import json

    from src.phase2_forecast import _check_confirmation_prerequisite

    output_dir = tmp_path / "phase2"
    output_dir.mkdir()
    complete = {
        "passed": True,
        "run_status": "complete",
        "input_sha256": "input",
        "configuration_sha256": PROTOCOL_HASH,
        "protocol_hash": PROTOCOL_HASH,
        "source_sha256": "source",
    }
    (output_dir / "development_gate.json").write_text(json.dumps(complete), encoding="utf-8")
    (output_dir / "development_manifest.json").write_text(json.dumps(complete), encoding="utf-8")
    with pytest.raises(Phase2Error, match="saved development evidence is missing"):
        _check_confirmation_prerequisite(output_dir, "input", "source")


def test_confirmation_prerequisite_rejects_stale_saved_development_evidence(tmp_path) -> None:
    import json

    from src.phase2_forecast import _artifact_paths, _check_confirmation_prerequisite, sha256_file

    output_dir = tmp_path / "phase2"
    output_dir.mkdir()
    artifact_paths = _artifact_paths("development", output_dir)
    for path in artifact_paths.values():
        path.write_bytes(b"evidence")
    complete = {
        "passed": True,
        "run_status": "complete",
        "input_sha256": "input",
        "configuration_sha256": PROTOCOL_HASH,
        "protocol_hash": PROTOCOL_HASH,
        "source_sha256": "source",
        "artifact_sha256": {
            name: sha256_file(path) for name, path in artifact_paths.items()
        },
    }
    (output_dir / "development_gate.json").write_text(json.dumps(complete), encoding="utf-8")
    (output_dir / "development_manifest.json").write_text(json.dumps(complete), encoding="utf-8")
    (artifact_paths["predictions"]).write_bytes(b"tampered")
    with pytest.raises(Phase2Error, match="saved development evidence is stale: predictions"):
        _check_confirmation_prerequisite(output_dir, "input", "source")


def test_development_runner_scores_only_registered_period(monkeypatch) -> None:
    import src.phase2_forecast as phase2

    start = pd.Timestamp("2019-07-15 00:00", tz="Australia/Brisbane")
    end = pd.Timestamp("2019-07-16 00:00", tz="Australia/Brisbane")
    monkeypatch.setattr(phase2, "DEVELOPMENT_START", start)
    monkeypatch.setattr(phase2, "DEVELOPMENT_END", end)
    monkeypatch.setitem(phase2.EXPECTED_COUNTS, "development", 96)
    monkeypatch.setattr(phase2, "_month_starts", lambda _start, _end: [start])

    fit_calls: list[tuple[bool, pd.Timestamp]] = []
    original_fit = phase2.fit_logistic

    def recording_fit(train, candidate, deadline=None):
        fit_calls.append((candidate, train["timestamp"].max()))
        return original_fit(train, candidate, deadline=deadline)

    monkeypatch.setattr(phase2, "fit_logistic", recording_fit)
    predictions, _ = phase2.generate_predictions(
        phase2._feature_frame(_long_frame(hours=600)), "development"
    )

    assert len(predictions) == 96
    assert predictions["timestamp"].min() >= start
    assert predictions["timestamp"].max() < end
    assert len(fit_calls) == 2
    assert all(train_end + EMBARGO <= start for _, train_end in fit_calls)
