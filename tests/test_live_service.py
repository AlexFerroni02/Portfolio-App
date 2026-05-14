from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from exceptions.live_exceptions import LiveDataError
from services.live_service import (
    build_live_rows,
    build_live_snapshot,
    build_owned_positions,
    calculate_live_portfolio_metrics,
    extract_last_quote_update,
    is_market_open,
)


def test_build_owned_positions_keeps_only_active_assets():
    """Owned positions must include only assets with positive residual quantity."""
    df_trans = pd.DataFrame(
        [
            {"isin": "AAA", "product": "Asset A", "quantity": 2.0, "local_value": -200.0, "fees": 2.0},
            {"isin": "AAA", "product": "Asset A", "quantity": -1.0, "local_value": 120.0, "fees": 1.0},
            {"isin": "BBB", "product": "Asset B", "quantity": 1.0, "local_value": -90.0, "fees": 1.0},
            {"isin": "BBB", "product": "Asset B", "quantity": -1.0, "local_value": 95.0, "fees": 1.0},
        ]
    )
    df_map = pd.DataFrame(
        [
            {"id": 1, "isin": "AAA", "ticker": "AAA.MI", "category": "Azionario"},
            {"id": 2, "isin": "BBB", "ticker": "BBB.MI", "category": "Azionario"},
        ]
    )

    positions = build_owned_positions(df_trans, df_map)

    assert len(positions) == 1
    assert positions.iloc[0]["ticker"] == "AAA.MI"
    assert positions.iloc[0]["quantity"] == pytest.approx(1.0)
    assert positions.iloc[0]["net_invested"] == pytest.approx(83.0)


def test_build_live_rows_uses_previous_close_on_missing_quote():
    """Live rows must fall back to previous close when quote is unavailable."""
    positions = pd.DataFrame(
        [
            {
                "mapping_id": 1,
                "product": "Asset A",
                "category": "Azionario",
                "ticker": "AAA.MI",
                "quantity": 2.0,
                "net_invested": 180.0,
            }
        ]
    )

    rows = build_live_rows(positions, {1: 100.0}, {"AAA.MI": {}})

    assert len(rows) == 1
    assert rows.iloc[0]["current_price"] == pytest.approx(100.0)
    assert rows.iloc[0]["day_change_abs"] == pytest.approx(0.0)
    assert rows.iloc[0]["source"] == "fallback_eod"


def test_calculate_live_portfolio_metrics_aggregates_values():
    """Portfolio metrics must aggregate value and daily move consistently."""
    live_rows = pd.DataFrame(
        [
            {"market_value": 120.0, "day_change_abs": 10.0, "net_invested": 100.0},
            {"market_value": 80.0, "day_change_abs": -5.0, "net_invested": 70.0},
        ]
    )

    metrics = calculate_live_portfolio_metrics(live_rows)

    assert metrics["market_value"] == pytest.approx(200.0)
    assert metrics["day_change_abs"] == pytest.approx(5.0)
    assert metrics["day_change_pct"] == pytest.approx(2.5641025641)
    assert metrics["total_pnl"] == pytest.approx(30.0)


def test_build_live_snapshot_returns_metrics_and_rows(mocker):
    """Full snapshot should include rows, metrics and freshness information."""
    df_trans = pd.DataFrame(
        [{"isin": "AAA", "product": "Asset A", "quantity": 1.0, "local_value": -100.0, "fees": 1.0}]
    )
    df_map = pd.DataFrame([{"id": 1, "isin": "AAA", "ticker": "AAA.MI", "category": "Azionario"}])
    df_prices = pd.DataFrame([{"mapping_id": 1, "date": pd.to_datetime("2026-05-10"), "close_price": 100.0}])
    quote_time = datetime(2026, 5, 14, 14, 30)

    mocker.patch(
        "services.live_service.fetch_live_quotes",
        return_value={"AAA.MI": {"price": 101.0, "timestamp": quote_time, "source": "intraday"}},
    )
    mocker.patch("services.live_service.is_market_open", return_value=False)

    snapshot = build_live_snapshot(df_trans, df_map, df_prices)

    assert snapshot["market_open"] is False
    assert snapshot["stale_count"] == 0
    assert snapshot["last_update"] == quote_time
    assert snapshot["metrics"]["day_change_abs"] == pytest.approx(1.0)
    assert len(snapshot["rows"]) == 1


def test_build_live_snapshot_raises_with_no_active_positions():
    """Snapshot should fail clearly when no positions are active."""
    df_trans = pd.DataFrame(
        [{"isin": "AAA", "product": "Asset A", "quantity": -1.0, "local_value": 100.0, "fees": 1.0}]
    )
    df_map = pd.DataFrame([{"id": 1, "isin": "AAA", "ticker": "AAA.MI", "category": "Azionario"}])
    df_prices = pd.DataFrame([{"mapping_id": 1, "date": pd.to_datetime("2026-05-10"), "close_price": 100.0}])

    with pytest.raises(LiveDataError):
        build_live_snapshot(df_trans, df_map, df_prices)


def test_extract_last_quote_update_handles_mixed_timezone_values():
    """Mixed tz-aware and tz-naive timestamps should not raise conversion errors."""
    live_rows = pd.DataFrame(
        [
            {"quote_timestamp": pd.Timestamp("2026-05-14 14:30:00+00:00")},
            {"quote_timestamp": pd.Timestamp("2026-05-14 16:20:00")},
        ]
    )

    last_update = extract_last_quote_update(live_rows)

    assert last_update is not None
    assert last_update == datetime(2026, 5, 14, 16, 30)


@pytest.mark.parametrize(
    "input_dt, expected",
    [
        (datetime(2026, 5, 14, 10, 0, tzinfo=ZoneInfo("Europe/Rome")), True),
        (datetime(2026, 5, 14, 18, 0, tzinfo=ZoneInfo("Europe/Rome")), False),
        (datetime(2026, 5, 16, 11, 0, tzinfo=ZoneInfo("Europe/Rome")), False),
    ],
)
def test_is_market_open_borsa_italiana_window(input_dt, expected):
    """Market status should follow Borsa Italiana hours and weekday rules."""
    assert is_market_open(input_dt) is expected
