from __future__ import annotations

from src.build_history_price_panel import load_regional_price


def test_load_regional_price_uses_verified_first_historical_archive():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    price = load_regional_price(root / "data/raw/aemo_history/price/2019-07.zip")
    assert len(price) == 31 * 288 * 5
    assert set(price["region"]) == {"NSW1", "VIC1", "QLD1", "SA1", "TAS1"}
    assert not price.duplicated(["timestamp", "region"]).any()
    assert price["rrp_aud_mwh"].notna().all()
