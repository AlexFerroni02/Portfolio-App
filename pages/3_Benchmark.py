from datetime import date

import streamlit as st

from database.connection import get_data
from services.benchmark_service import run_benchmark_simulation
from services.metrics_service import (
    build_portfolio_metrics,
    build_twr_audit_table,
    build_twr_real_comparison_table,
    calculate_return_from_date,
    calculate_yearly_return_comparison,
    calculate_ytd_return,
    prepare_portfolio_timeseries,
)
from services.portfolio_service import get_historical_portfolio
from ui.benchmark_components import (
    render_benchmark_kpis,
    render_benchmark_selector,
    render_drawdown_chart as render_benchmark_drawdown_chart,
    render_gain_chart,
    render_performance_chart,
    render_transaction_log,
)
from ui.components import make_sidebar
from ui.metrics_components import (
    render_drawdown_chart,
    render_extreme_days,
    render_ratio_kpis,
    render_return_kpis,
    render_risk_kpis,
    render_twr_audit_table,
    render_twr_real_comparison_table,
    render_yearly_return_bars,
)


def _render_benchmark_tab(df_trans, df_map, df_prices) -> None:
    """Render benchmark simulation content."""
    bench_ticker = render_benchmark_selector()
    if not bench_ticker:
        return
    try:
        with st.spinner(f"Calcolo simulazione su {bench_ticker}..."):
            df_chart, df_log = run_benchmark_simulation(bench_ticker, df_trans, df_map, df_prices)
        if df_chart.empty:
            st.info("Nessun dato da visualizzare per la simulazione.")
            return
        render_benchmark_kpis(df_chart, bench_ticker)
        render_transaction_log(df_log, bench_ticker)
        render_performance_chart(df_chart, bench_ticker)
        render_gain_chart(df_chart, bench_ticker)
        render_benchmark_drawdown_chart(df_chart)
    except Exception as exc:
        st.error(f"Impossibile completare la simulazione: {exc}")


def _render_metrics_tab(df_trans, df_map, df_prices) -> None:
    """Render portfolio metrics content."""
    historical_df = get_historical_portfolio(df_trans, df_map, df_prices)
    portfolio_df = prepare_portfolio_timeseries(historical_df)
    if portfolio_df.empty:
        st.warning("Serie storica insufficiente per il calcolo delle metriche.")
        return
    min_date = portfolio_df['Data'].min().date()
    max_date = portfolio_df['Data'].max().date()
    default_start = max(date(max_date.year, 1, 1), min_date)
    col_date, col_rf = st.columns([2, 1])
    start_date = col_date.date_input("Data iniziale per rendimento personalizzato", value=default_start, min_value=min_date, max_value=max_date)
    risk_free = col_rf.number_input("Tasso risk-free annuo (%)", min_value=0.0, max_value=20.0, value=2.0, step=0.1)
    ytd = calculate_ytd_return(portfolio_df)
    custom = calculate_return_from_date(portfolio_df, start_date)
    yearly = calculate_yearly_return_comparison(portfolio_df)
    comparison = build_twr_real_comparison_table(portfolio_df)
    audit_df = build_twr_audit_table(portfolio_df)
    metrics = build_portfolio_metrics(portfolio_df, risk_free_rate=risk_free / 100.0)
    render_return_kpis(ytd, custom)
    render_twr_real_comparison_table(comparison)
    render_yearly_return_bars(yearly)
    st.divider()
    render_risk_kpis(metrics)
    render_ratio_kpis(metrics)
    render_extreme_days(metrics)
    render_drawdown_chart(audit_df)
    render_twr_audit_table(audit_df)


st.set_page_config(page_title="Performance", layout="wide", page_icon="⚖️")
make_sidebar()
st.title("⚖️ Performance")
st.caption("Benchmark e Metriche in un unico hub di analisi.")

with st.spinner("Caricamento dati di portafoglio..."):
    df_trans = get_data("transactions")
    df_map = get_data("mapping")
    df_prices = get_data("prices")

if df_trans.empty or df_map.empty:
    st.warning("⚠️ Dati di transazioni o mappatura mancanti. Vai su 'Gestione Dati' per configurarli.")
    st.stop()

tab_benchmark, tab_metrics = st.tabs(["⚖️ Confronto Benchmark", "📐 Metriche Portafoglio"])
with tab_benchmark:
    _render_benchmark_tab(df_trans, df_map, df_prices)
with tab_metrics:
    _render_metrics_tab(df_trans, df_map, df_prices)