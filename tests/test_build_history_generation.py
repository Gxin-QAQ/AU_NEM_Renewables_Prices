from __future__ import annotations

from src.build_history_generation import month_range


def test_month_range_is_inclusive_for_partition_builds():
    assert month_range("2025-05", "2025-06") == ["2025-05", "2025-06"]


def test_month_range_rejects_reverse_order_for_partition_builds():
    try:
        month_range("2025-06", "2025-05")
    except ValueError as error:
        assert "start" in str(error)
    else:
        raise AssertionError("Expected ValueError")
