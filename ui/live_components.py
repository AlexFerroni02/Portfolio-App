from datetime import datetime

import pandas as pd
import streamlit as st

from ui.components import color_pnl


def _format_timestamp(value: datetime | None) -> str:
    """Format a timestamp for compact display."""
    if value is None:
        return "N/D"
    return value.strftime("%d/%m/%Y %H:%M")


def _format_currency(value: float) -> str:
    """Format numeric values as EUR currency."""
    return f"€ {value:,.2f}"


def _format_percentage(value: float) -> str:
    """Format a percentage value with sign."""
    sign = "+" if value >= 0 else ""
    return f"{sign}{value:.2f}%"


def _inject_live_css() -> None:
    """Inject scoped CSS styles for the Live page sections."""
    st.markdown(
        """
        <style>
        .live-panel {border: 1px solid rgba(128,128,128,.22); border-radius: 12px; padding: .75rem .9rem; background: var(--secondary-background-color);}
        .live-panel-title {font-size: .85rem; font-weight: 700; opacity: .9; margin-bottom: .25rem;}
        .live-panel-value {font-size: 1.2rem; font-weight: 800; margin-bottom: .1rem;}
        .live-badge {display: inline-block; padding: .2rem .55rem; border-radius: 999px; font-weight: 700; font-size: .8rem;}
        .live-badge-open {background: rgba(16,185,129,.18); color: #10b981;}
        .live-badge-closed {background: rgba(239,68,68,.16); color: #ef4444;}
        .live-mini-table {border: 1px solid rgba(128,128,128,.22); border-radius: 12px; overflow: hidden;}
        .live-mini-head {padding: .45rem .65rem; font-weight: 700; background: rgba(128,128,128,.10);}
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_live_status(market_open: bool, last_update: datetime | None, stale_count: int, asset_count: int):
    """Render market status, freshness, asset count and fallback warning."""
    _inject_live_css()
    status_label = "MERCATO APERTO" if market_open else "MERCATO CHIUSO"
    status_class = "live-badge-open" if market_open else "live-badge-closed"
    freshness = _format_timestamp(last_update)
    st.markdown(
        f"""
        <div class="live-panel" style="margin-bottom:.35rem;">
            <span class="live-badge {status_class}">{status_label}</span>
            <span style="margin-left:.55rem; font-weight:600;">Ultimo aggiornamento: {freshness}</span>
            <span style="margin-left:.55rem; opacity:.8;">• Titoli monitorati: {asset_count}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if stale_count > 0:
        st.warning(f"{stale_count} titoli sono in fallback su ultimo close disponibile.")


def render_live_kpis(metrics: dict[str, float]):
    """Render compact KPI cards for live portfolio overview."""
    col1, col2, col3 = st.columns(3)
    col1.markdown(
        f"<div class='live-panel'><div class='live-panel-title'>💼 Valore Attuale</div><div class='live-panel-value'>{_format_currency(metrics['market_value'])}</div></div>",
        unsafe_allow_html=True,
    )
    col2.markdown(
        f"<div class='live-panel'><div class='live-panel-title'>📈 Variazione Giornaliera</div><div class='live-panel-value'>{_format_currency(metrics['day_change_abs'])}</div><div>{_format_percentage(metrics['day_change_pct'])}</div></div>",
        unsafe_allow_html=True,
    )
    col3.markdown(
        f"<div class='live-panel'><div class='live-panel-title'>🧮 P&L Totale</div><div class='live-panel-value'>{_format_currency(metrics['total_pnl'])}</div></div>",
        unsafe_allow_html=True,
    )


def _build_movers_table(live_rows: pd.DataFrame, ascending: bool, top_n: int = 5) -> pd.DataFrame:
    """Return compact movers table sorted by daily percentage."""
    if live_rows.empty:
        return pd.DataFrame()
    table = live_rows[["ticker", "day_change_pct", "day_change_abs"]].copy()
    table = table.sort_values("day_change_pct", ascending=ascending).head(top_n)
    table.rename(columns={"ticker": "Ticker", "day_change_pct": "Var %", "day_change_abs": "Var €"}, inplace=True)
    return table


def _get_movers_per_side(total_assets: int) -> int:
    """Return movers count per side based on number of holdings."""
    if total_assets <= 2:
        return 1
    return max(1, min(6, total_assets // 2))


def render_live_movers(live_rows: pd.DataFrame):
    """Render top gainers and laggards in two compact blocks."""
    if live_rows.empty:
        return
    movers_per_side = _get_movers_per_side(len(live_rows))
    gainers = _build_movers_table(live_rows, ascending=False, top_n=movers_per_side)
    laggards = _build_movers_table(live_rows, ascending=True, top_n=movers_per_side)
    col_up, col_down = st.columns(2)
    with col_up:
        st.markdown(
            f"<div class='live-mini-table'><div class='live-mini-head'>🚀 Top Movers ({movers_per_side})</div></div>",
            unsafe_allow_html=True,
        )
        st.dataframe(gainers.style.format({"Var %": "{:+.2f}%", "Var €": "€ {:+.2f}"}).map(color_pnl, subset=["Var %", "Var €"]), width="stretch", hide_index=True)
    with col_down:
        st.markdown(
            f"<div class='live-mini-table'><div class='live-mini-head'>🧨 Peggiori Oggi ({movers_per_side})</div></div>",
            unsafe_allow_html=True,
        )
        st.dataframe(laggards.style.format({"Var %": "{:+.2f}%", "Var €": "€ {:+.2f}"}).map(color_pnl, subset=["Var %", "Var €"]), width="stretch", hide_index=True)


def _build_live_display_table(live_rows: pd.DataFrame) -> pd.DataFrame:
    """Return the compact dataframe used by the live UI table."""
    table_df = live_rows[
        ["product", "ticker", "quantity", "previous_close", "current_price", "day_change_abs", "day_change_pct"]
    ].copy()
    table_df.rename(columns={
        "product": "Prodotto",
        "ticker": "Ticker",
        "quantity": "Quantità",
        "previous_close": "Prev Close",
        "current_price": "Prezzo Live",
        "day_change_abs": "Var €",
        "day_change_pct": "Var %",
    }, inplace=True)
    return table_df


def _style_live_table(table_df: pd.DataFrame):
    """Apply numeric formatting and color map for daily variation columns."""
    styled = table_df.style.format(
        {
            "Quantità": "{:.2f}",
            "Prev Close": "€ {:.2f}",
            "Prezzo Live": "€ {:.2f}",
            "Var €": "€ {:+.2f}",
            "Var %": "{:+.2f}%",
        }
    ).map(color_pnl, subset=["Var €", "Var %"])
    return styled


def render_live_table(live_rows: pd.DataFrame):
    """Render per-asset live table with compact day-change columns."""
    if live_rows.empty:
        st.info("Nessun titolo disponibile per la vista live.")
        return
    st.subheader("📋 Dettaglio Titoli")
    table_df = _build_live_display_table(live_rows)
    styled = _style_live_table(table_df)
    st.dataframe(styled, width="stretch", hide_index=True)


def render_live_delay_note():
    """Render the data-delay disclosure note."""
    st.caption("Fonte Yahoo Finance: dati intraday con possibile ritardo di circa 5-15 minuti.")
