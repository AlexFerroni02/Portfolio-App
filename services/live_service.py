import logging
from datetime import datetime, time
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st
import yfinance as yf

from exceptions.live_exceptions import LiveDataError, QuoteFetchError

LOGGER = logging.getLogger(__name__)
ROME_TZ = ZoneInfo("Europe/Rome")
BORSA_ITALIANA_OPEN = time(9, 0)
BORSA_ITALIANA_CLOSE = time(17, 30)


def _ensure_mapping_identifier(df: pd.DataFrame) -> pd.DataFrame:
    """Return a dataframe with a guaranteed mapping_id column."""
    if "mapping_id" in df.columns:
        return df
    if "id_map" in df.columns:
        return df.rename(columns={"id_map": "mapping_id"})
    if "id" in df.columns:
        return df.rename(columns={"id": "mapping_id"})
    copy_df = df.copy()
    copy_df["mapping_id"] = pd.NA
    return copy_df


def build_owned_positions(df_trans: pd.DataFrame, df_map: pd.DataFrame) -> pd.DataFrame:
    """Build currently held positions with quantity, ticker and net invested."""
    if df_trans.empty or df_map.empty:
        return pd.DataFrame()
    merged = df_trans.merge(df_map, on="isin", how="left", suffixes=("_trans", "_map"))
    merged = _ensure_mapping_identifier(merged)
    grouped = merged.groupby(["mapping_id", "product", "ticker", "category"]).agg(
        quantity=("quantity", "sum"),
        local_value=("local_value", "sum"),
        fees=("fees", "sum"),
    ).reset_index()
    positions = grouped[grouped["quantity"] > 0.001].copy()
    positions["ticker"] = positions["ticker"].fillna("").astype(str).str.strip().str.upper()
    positions = positions[positions["ticker"] != ""]
    positions["net_invested"] = -positions["local_value"] + positions["fees"]
    return positions.reset_index(drop=True)


def build_previous_close_lookup(df_prices: pd.DataFrame) -> dict[int, float]:
    """Map mapping_id to last available close price from the prices table."""
    if df_prices.empty:
        return {}
    local_prices = df_prices.copy()
    local_prices["date"] = pd.to_datetime(local_prices["date"])
    latest = local_prices.sort_values("date").groupby("mapping_id").tail(1)
    lookup = dict(zip(latest["mapping_id"], latest["close_price"], strict=False))
    return {int(key): float(value) for key, value in lookup.items() if pd.notna(key)}


def fetch_intraday_quote(ticker: str) -> dict[str, Any]:
    """Fetch latest intraday quote for a ticker using Yahoo Finance."""
    try:
        history = yf.Ticker(ticker).history(period="2d", interval="5m", auto_adjust=False)
        if history.empty:
            raise QuoteFetchError(f"No intraday data for ticker {ticker}")
        timestamp = pd.Timestamp(history.index[-1]).to_pydatetime()
        return {
            "price": float(history["Close"].iloc[-1]),
            "timestamp": timestamp,
            "source": "intraday",
        }
    except Exception as exc:
        LOGGER.error("Quote fetch failed", extra={"ticker": ticker, "error": str(exc)})
        if isinstance(exc, QuoteFetchError):
            raise
        raise QuoteFetchError(f"Intraday quote failed for {ticker}") from exc


@st.cache_data(ttl=300, show_spinner=False)
def fetch_live_quotes(tickers: tuple[str, ...]) -> dict[str, dict[str, Any]]:
    """Fetch and cache live quotes for a set of tickers for five minutes."""
    quotes: dict[str, dict[str, Any]] = {}
    for ticker in sorted(set(tickers)):
        if not ticker:
            continue
        try:
            quotes[ticker] = fetch_intraday_quote(ticker)
            LOGGER.debug("Live quote loaded", extra={"ticker": ticker})
        except QuoteFetchError:
            quotes[ticker] = {}
    LOGGER.info("Live quotes batch completed", extra={"count": len(quotes)})
    return quotes


def is_market_open(now: datetime | None = None) -> bool:
    """Return True during Borsa Italiana weekday trading hours (Europe/Rome)."""
    current = now.astimezone(ROME_TZ) if now else datetime.now(ROME_TZ)
    if current.weekday() >= 5:
        return False
    return BORSA_ITALIANA_OPEN <= current.time() <= BORSA_ITALIANA_CLOSE


def normalize_quote_timestamp(raw_value: Any) -> datetime | None:
    """Normalize quote timestamps to a timezone-naive datetime in Europe/Rome."""
    if raw_value is None:
        return None
    try:
        timestamp = pd.Timestamp(raw_value)
    except (TypeError, ValueError):
        return None
    if timestamp.tzinfo is not None:
        timestamp = timestamp.tz_convert(ROME_TZ).tz_localize(None)
    return timestamp.to_pydatetime()


def build_single_live_row(
    position: dict[str, Any],
    previous_close_lookup: dict[int, float],
    live_quotes: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Build one live row using intraday quote data with EOD fallback."""
    ticker = position["ticker"]
    mapping_id = int(position["mapping_id"])
    quote = live_quotes.get(ticker, {})
    previous_close = float(previous_close_lookup.get(mapping_id, 0.0))
    current_price = float(quote.get("price", previous_close))
    quantity = float(position["quantity"])
    market_value = quantity * current_price
    abs_change = quantity * (current_price - previous_close)
    pct_change = ((current_price / previous_close) - 1) * 100 if previous_close > 0 else 0.0
    quote_timestamp = normalize_quote_timestamp(quote.get("timestamp"))
    return {
        "mapping_id": mapping_id,
        "product": position["product"],
        "category": position["category"],
        "ticker": ticker,
        "quantity": quantity,
        "net_invested": float(position["net_invested"]),
        "previous_close": previous_close,
        "current_price": current_price,
        "market_value": market_value,
        "day_change_abs": abs_change,
        "day_change_pct": pct_change,
        "source": quote.get("source", "fallback_eod"),
        "quote_timestamp": quote_timestamp,
    }


def build_live_rows(
    positions: pd.DataFrame,
    previous_close_lookup: dict[int, float],
    live_quotes: dict[str, dict[str, Any]],
) -> pd.DataFrame:
    """Build per-asset live rows with daily variation and fallback handling."""
    if positions.empty:
        return pd.DataFrame()
    rows = [
        build_single_live_row(row, previous_close_lookup, live_quotes)
        for row in positions.to_dict("records")
    ]
    return pd.DataFrame(rows).sort_values("day_change_pct", ascending=False)


def calculate_live_portfolio_metrics(live_rows: pd.DataFrame) -> dict[str, float]:
    """Calculate compact portfolio-level live KPIs from per-asset rows."""
    if live_rows.empty:
        return {"market_value": 0.0, "day_change_abs": 0.0, "day_change_pct": 0.0, "total_pnl": 0.0}
    market_value = float(live_rows["market_value"].sum())
    day_change_abs = float(live_rows["day_change_abs"].sum())
    previous_value = market_value - day_change_abs
    day_change_pct = (day_change_abs / previous_value) * 100 if previous_value > 0 else 0.0
    total_pnl = float((live_rows["market_value"] - live_rows["net_invested"]).sum())
    return {
        "market_value": market_value,
        "day_change_abs": day_change_abs,
        "day_change_pct": day_change_pct,
        "total_pnl": total_pnl,
    }


def extract_last_quote_update(live_rows: pd.DataFrame) -> datetime | None:
    """Get the latest quote timestamp from live rows."""
    if live_rows.empty or "quote_timestamp" not in live_rows.columns:
        return None
    normalized_values = [normalize_quote_timestamp(value) for value in live_rows["quote_timestamp"].tolist()]
    valid_ts = [value for value in normalized_values if value is not None]
    if not valid_ts:
        return None
    return max(valid_ts)


def build_live_snapshot(
    df_trans: pd.DataFrame,
    df_map: pd.DataFrame,
    df_prices: pd.DataFrame,
) -> dict[str, Any]:
    """Build a full live snapshot for the portfolio and owned assets."""
    positions = build_owned_positions(df_trans, df_map)
    if positions.empty:
        raise LiveDataError("No active positions available for live monitoring")
    previous_close_lookup = build_previous_close_lookup(df_prices)
    tickers = tuple(positions["ticker"].dropna().astype(str).tolist())
    quotes = fetch_live_quotes(tickers)
    live_rows = build_live_rows(positions, previous_close_lookup, quotes)
    metrics = calculate_live_portfolio_metrics(live_rows)
    last_update = extract_last_quote_update(live_rows)
    stale_count = int((live_rows["source"] == "fallback_eod").sum()) if not live_rows.empty else 0
    return {
        "rows": live_rows,
        "metrics": metrics,
        "last_update": last_update,
        "market_open": is_market_open(),
        "stale_count": stale_count,
    }
