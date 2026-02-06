import streamlit as st
import pandas as pd
from database.connection import get_data
from ui.components import make_sidebar
from services.portfolio_service import calculate_liquidity
from services.budget_service import get_monthly_summary
from ui.budget_components import (
    render_month_selector,
    render_monthly_kpis,
    render_monthly_charts,
    render_net_worth_section,
    render_transactions_editor,
    render_expense_trend_chart,
    render_savings_rate_trend,
    render_budget_rule_check,
    render_expense_breakdown
)

st.set_page_config(page_title="Bilancio", layout="wide", page_icon="💰")
make_sidebar()
st.title("💰 Bilancio & Patrimonio")

# --- 1. CARICAMENTO DATI ---
with st.spinner("Caricamento dati..."):
    df_budget = get_data("budget")
    df_trans = get_data("transactions")
    df_nw = get_data("networth_history")

# Normalizzazione date
if not df_budget.empty: df_budget['date'] = pd.to_datetime(df_budget['date'], errors='coerce').dt.normalize()
if not df_trans.empty: df_trans['date'] = pd.to_datetime(df_trans['date'], errors='coerce').dt.normalize()
if not df_nw.empty: df_nw['date'] = pd.to_datetime(df_nw['date'], errors='coerce').dt.normalize()

if df_budget.empty:
    st.info("👋 Nessun dato di bilancio. Vai su 'Gestione Dati' per inserire entrate e uscite.")
    st.stop()

# --- 2. SEZIONE ANALISI MENSILE ---
st.subheader("📅 Analisi Mensile")
selected_month = render_month_selector(df_budget)
df_month = df_budget[df_budget['date'].dt.strftime('%Y-%m') == selected_month]

# Calcoli
summary = get_monthly_summary(selected_month, df_budget, df_trans)
final_liquidity, liquidity_help = calculate_liquidity(df_budget, df_trans)

# Rendering
render_monthly_kpis(summary, final_liquidity, liquidity_help)
render_monthly_charts(df_month, summary)

st.divider()

# --- 3. VERIFICA REGOLA 50/30/20 ---
render_budget_rule_check(df_budget, selected_month)

st.divider()

# --- 4. TREND E ANALISI STORICHE ---
st.subheader("📈 Analisi Trend")
col_trend1, col_trend2 = st.columns(2)

with col_trend1:
    render_expense_trend_chart(df_budget, months=6)

with col_trend2:
    render_savings_rate_trend(df_budget, months=6)

render_expense_breakdown(df_budget, months=3)

st.divider()

# --- 5. SEZIONE PATRIMONIO NETTO ---
render_net_worth_section(df_nw)

st.divider()

# --- 6. SEZIONE DETTAGLIO MOVIMENTI ---
render_transactions_editor(df_month, df_budget)