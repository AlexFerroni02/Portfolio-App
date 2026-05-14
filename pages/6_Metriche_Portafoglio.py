from datetime import date

import streamlit as st

from database.connection import get_data
from services.metrics_service import (
    prepare_portfolio_timeseries,
    calculate_ytd_return,
    calculate_return_from_date,
    calculate_yearly_return_comparison,
    build_twr_real_comparison_table,
    build_twr_audit_table,
    build_portfolio_metrics,
)
from services.portfolio_service import get_historical_portfolio
from ui.components import make_sidebar
from ui.metrics_components import (
    render_return_kpis,
    render_twr_real_comparison_table,
    render_risk_kpis,
    render_ratio_kpis,
    render_yearly_return_bars,
    render_drawdown_chart,
    render_extreme_days,
    render_twr_audit_table,
)


st.set_page_config(page_title="Metriche Portafoglio", page_icon="📐", layout="wide")
make_sidebar()
st.title("📐 Metriche Portafoglio")
st.caption("Analisi rendimento e rischio del portafoglio senza confronto benchmark.")


df_trans = get_data("transactions")
df_map = get_data("mapping")
df_prices = get_data("prices")

if df_trans.empty or df_map.empty or df_prices.empty:
    st.warning("Servono transazioni, mappatura e prezzi per calcolare le metriche.")
    st.stop()

historical_df = get_historical_portfolio(df_trans, df_map, df_prices)
portfolio_df = prepare_portfolio_timeseries(historical_df)
if portfolio_df.empty:
    st.warning("Serie storica insufficiente per il calcolo delle metriche.")
    st.stop()

min_date = portfolio_df['Data'].min().date()
max_date = portfolio_df['Data'].max().date()
default_start = date(max_date.year, 1, 1)
if default_start < min_date:
    default_start = min_date

col_date, col_rf = st.columns([2, 1])
selected_start_date = col_date.date_input(
    "Data iniziale per rendimento personalizzato",
    value=default_start,
    min_value=min_date,
    max_value=max_date,
)
risk_free_rate_pct = col_rf.number_input(
    "Tasso risk-free annuo (%)",
    min_value=0.0,
    max_value=20.0,
    value=2.0,
    step=0.1,
)

ytd_return = calculate_ytd_return(portfolio_df)
custom_return = calculate_return_from_date(portfolio_df, selected_start_date)
yearly_comparison_df = calculate_yearly_return_comparison(portfolio_df)
summary_comparison_df = build_twr_real_comparison_table(portfolio_df)
audit_df = build_twr_audit_table(portfolio_df)
metrics = build_portfolio_metrics(portfolio_df, risk_free_rate=risk_free_rate_pct / 100.0)

render_return_kpis(ytd_return, custom_return)
render_twr_real_comparison_table(summary_comparison_df)
render_yearly_return_bars(yearly_comparison_df)
st.divider()
render_risk_kpis(metrics)
render_ratio_kpis(metrics)
render_extreme_days(metrics)
render_drawdown_chart(audit_df)
render_twr_audit_table(audit_df)

st.info(
    "Metriche incluse: YTD e rendimento da data (flow-adjusted), confronto TWR vs guadagno reale, "
    "rendimento annuale a barre, CAGR, volatilità annualizzata, max drawdown, Sharpe, Sortino e Calmar."
)
