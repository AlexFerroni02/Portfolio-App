import streamlit as st
import pandas as pd
from database.connection import get_data
from ui.components import make_sidebar
from services.portfolio_service import calculate_liquidity
from services.budget_service import get_monthly_summary, get_general_summary, get_category_averages, get_yearly_summary
from ui.budget_components import (
    # Componenti mensili
    render_month_selector,
    render_monthly_kpis,
    render_monthly_charts,
    render_net_worth_section,
    render_transactions_editor,
    render_expense_trend_chart,
    render_savings_rate_trend,
    render_budget_rule_check,
    render_expense_breakdown,
    render_investment_trend,
    # Componenti generali
    render_general_kpis,
    render_income_vs_expense_totals,
    render_category_averages_chart,
    render_yearly_summary_chart,
    render_sankey_flow,
    render_general_50_30_20
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

# --- 2. STRUTTURA A TAB ---
tab_mensile, tab_generale = st.tabs(["📅 Analisi Mensile", "📊 Panoramica Generale"])

# =============================================
# TAB MENSILE (contenuto esistente)
# =============================================
with tab_mensile:
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
    
    # Verifica regola 50/30/20
    render_budget_rule_check(df_budget, selected_month)
    
    st.divider()
    
    # Trend e analisi storiche
    st.subheader("📈 Analisi Trend")
    col_trend1, col_trend2 = st.columns(2)
    
    with col_trend1:
        render_expense_trend_chart(df_budget, months=6)
    
    with col_trend2:
        render_savings_rate_trend(df_budget, months=6)
    
    render_expense_breakdown(df_budget, months=3)
    render_investment_trend(df_budget, months=6)
    
    st.divider()
    
    # Dettaglio movimenti
    render_transactions_editor(df_month, df_budget)

# =============================================
# TAB GENERALE (nuova sezione)
# =============================================
with tab_generale:
    # KPI generali
    general_summary = get_general_summary(df_budget)
    render_general_kpis(general_summary)
    
    st.divider()
    
    # Grafici principali
    col_g1, col_g2 = st.columns(2)
    
    with col_g1:
        render_income_vs_expense_totals(df_budget)
    
    with col_g2:
        category_averages = get_category_averages(df_budget)
        render_category_averages_chart(category_averages)
    
    st.divider()
    
    # Regola 50/30/20 generale
    render_general_50_30_20(df_budget)
    
    st.divider()
    
    # Riepilogo annuale
    yearly_summary = get_yearly_summary(df_budget)
    render_yearly_summary_chart(yearly_summary)
    
    st.divider()
    
    # Diagramma Sankey
    st.subheader("🔀 Flusso di Denaro")
    
    # Selettore anno per Sankey
    anni_disponibili = sorted(df_budget['date'].dt.year.unique(), reverse=True)
    col_sankey_sel, col_sankey_empty = st.columns([1, 3])
    
    with col_sankey_sel:
        opzioni_anno = ["Tutto il periodo"] + [str(a) for a in anni_disponibili]
        anno_selezionato = st.selectbox("Seleziona periodo:", opzioni_anno)
    
    if anno_selezionato == "Tutto il periodo":
        render_sankey_flow(df_budget, year=None)
    else:
        render_sankey_flow(df_budget, year=int(anno_selezionato))

# =============================================
# SEZIONE PATRIMONIO NETTO (fuori dai tab)
# =============================================
st.divider()
render_net_worth_section(df_nw)