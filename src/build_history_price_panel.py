"""Join validated historical RRP to generation-demand partitions.

This is deliberately separate from SCADA aggregation: it adds the immutable
``DISPATCHPRICE`` source to already audited monthly five-minute partitions and
then reproduces the project's hourly price, volatility and negative-price
outcomes.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from src.build_history_generation import _market_timestamp, _read_columns, archive_header, month_range
from src.panel_builder import EXPECTED_REGIONS, aggregate_hourly, load_project_config, validate_hourly_panel


def load_regional_price(path: Path) -> pd.DataFrame:
    """Load dispatch RRP for the non-intervention dispatch run from one archive."""
    positions = archive_header(path, "PRICE")
    required = ["SETTLEMENTDATE", "RUNNO", "REGIONID", "INTERVENTION", "RRP"]
    missing = set(required) - set(positions)
    if missing:
        raise ValueError(f"{path.name}: PRICE lacks {sorted(missing)}")
    pieces: list[pd.DataFrame] = []
    for chunk in _read_columns(path, positions, required, 100_000):
        rows = chunk.loc[
            chunk["SETTLEMENTDATE"].str.match(r"^\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2}$", na=False)
            & chunk["RUNNO"].eq("1")
            & chunk["INTERVENTION"].eq("0")
        ].copy()
        if rows.empty:
            continue
        rows["timestamp"] = _market_timestamp(rows["SETTLEMENTDATE"])
        rows["rrp_aud_mwh"] = pd.to_numeric(rows["RRP"], errors="raise")
        pieces.append(rows[["timestamp", "REGIONID", "rrp_aud_mwh"]].rename(columns={"REGIONID": "region"}))
    price = pd.concat(pieces, ignore_index=True)
    price = price.loc[price["region"].isin(EXPECTED_REGIONS)].copy()
    if price.duplicated(["timestamp", "region"]).any():
        raise ValueError(f"{path.name}: duplicate region-time RRP records")
    if set(price["region"]) != EXPECTED_REGIONS:
        raise ValueError(f"{path.name}: expected exactly five NEM regions")
    return price.sort_values(["timestamp", "region"], ignore_index=True)


def build_month(root: Path, period: str, config: dict[str, object]) -> dict[str, int | float | str]:
    """Join one price archive to the matching local generation-demand partition."""
    source_panel = root / "data/interim/history_generation_demand_5min" / f"{period}.parquet"
    price_path = root / "data/raw/aemo_history/price" / f"{period}.zip"
    if not source_panel.exists() or not price_path.exists():
        raise FileNotFoundError(f"{period}: price archive or generation-demand partition is missing")
    generation = pd.read_parquet(source_panel)
    price = load_regional_price(price_path)
    panel = generation.merge(price, on=["timestamp", "region"], how="left", validate="one_to_one")
    if panel["rrp_aud_mwh"].isna().any():
        raise ValueError(f"{period}: price is missing for one or more generation-demand records")
    panel["settlement_timestamp"] = panel["timestamp"] + pd.offsets.Minute(5)
    panel = panel.sort_values(["timestamp", "region"], ignore_index=True)
    if panel.duplicated(["timestamp", "region"]).any():
        raise ValueError(f"{period}: duplicate final five-minute panel keys")
    output_5min = root / "data/processed/nem_region_5min"
    output_hour = root / "data/interim/history_price_hour"
    output_5min.mkdir(parents=True, exist_ok=True)
    output_hour.mkdir(parents=True, exist_ok=True)
    panel.to_parquet(output_5min / f"{period}.parquet", index=False)
    hourly = aggregate_hourly(panel, config).sort_values(["timestamp", "region"], ignore_index=True)
    validate_hourly_panel(hourly)
    hourly.to_parquet(output_hour / f"{period}.parquet", index=False)
    return {
        "period": period,
        "five_minute_rows": int(len(panel)),
        "hourly_rows": int(len(hourly)),
        "negative_price_5min_share": float((panel["rrp_aud_mwh"] < 0).mean()),
        "min_rrp_aud_mwh": float(panel["rrp_aud_mwh"].min()),
        "max_rrp_aud_mwh": float(panel["rrp_aud_mwh"].max()),
    }


def build_history(root: Path, start: str, end: str, resume: bool) -> list[dict[str, int | float | str]]:
    """Write the production hourly panel and partitioned five-minute panel."""
    config = load_project_config(root / "config/project.yml")
    records: list[dict[str, int | float | str]] = []
    for period in month_range(start, end):
        existing = root / "data/interim/history_price_hour" / f"{period}.parquet"
        if resume and existing.exists():
            records.append({"period": period, "status": "existing"})
            continue
        record = build_month(root, period, config)
        record["status"] = "built"
        records.append(record)
        print(json.dumps(record), flush=True)
    selected = [root / "data/interim/history_price_hour" / f"{period}.parquet" for period in month_range(start, end)]
    if not all(path.exists() for path in selected):
        raise ValueError("Not all requested hourly price partitions are available")
    hourly = pd.concat([pd.read_parquet(path) for path in selected], ignore_index=True)
    hourly = hourly.sort_values(["timestamp", "region"], ignore_index=True)
    validate_hourly_panel(hourly)
    hourly.to_parquet(root / "data/processed/nem_region_hour.parquet", index=False)
    (root / "data/interim/history_price_panel_build_summary.json").write_text(
        json.dumps({"start": start, "end": end, "months": records}, indent=2) + "\n", encoding="utf-8"
    )
    return records


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", default="2019-07")
    parser.add_argument("--end", default="2025-06")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    build_history(args.root.resolve(), args.start, args.end, args.resume)


if __name__ == "__main__":
    main()
