from __future__ import annotations

from src.download_aemo_history import TABLES, archive_url_candidates, month_range


def test_month_range_is_inclusive_across_year_boundary():
    assert month_range("2019-11", "2020-02") == ["2019-11", "2019-12", "2020-01", "2020-02"]


def test_month_range_rejects_reverse_order():
    try:
        month_range("2020-02", "2020-01")
    except ValueError as error:
        assert "Start month" in str(error)
    else:
        raise AssertionError("Expected ValueError")


def test_archive_candidates_cover_current_and_legacy_conventions():
    current, legacy = archive_url_candidates(TABLES["scada"], "2020-07")
    assert "PUBLIC_ARCHIVE%23DISPATCH_UNIT_SCADA%23FILE01%23202007010000.zip" in current
    assert legacy.endswith("PUBLIC_DVD_DISPATCH_UNIT_SCADA_202007010000.zip")


def test_price_is_a_separate_required_source_table():
    assert TABLES["price"] == "DISPATCHPRICE"
