"""Export compact, saved Phase 2 metrics without fitting a model."""
from pathlib import Path
import csv
import json


def build(root: Path) -> None:
    result = {}
    for period in ("development", "confirmation"):
        with (root / f"outputs/phase2/{period}_metrics.csv").open() as handle:
            rows = list(csv.DictReader(handle))
        result[period] = [
            {key: row[key] if key in ("scope", "model") else float(row[key])
             for key in ("scope", "model", "nobs", "brier_score", "mean_predicted", "observed_rate", "calibration_bias_pp")}
            for row in rows
        ]
        assert len(rows) == 20
        assert all(0 <= row["brier_score"] <= 1 for row in result[period])
    (root / "site/data/phase2.js").write_text(
        "window.NEM_PHASE2 = " + json.dumps(result, indent=2) + ";\n"
    )


if __name__ == "__main__":
    build(Path(__file__).resolve().parents[1])
