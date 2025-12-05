import streamlit as st
from database.connection import get_data
from ui.components import make_sidebar
from services.benchmark_service import run_benchmark_simulation
from ui.benchmark_components import (
    render_benchmark_selector,
    render_benchmark_kpis,
    render_transaction_log,
    render_performance_chart,
    render_drawdown_chart
)

st.set_page_config(page_title="Benchmark", layout="wide", page_icon="⚖️")
make_sidebar()
st.title("⚖️ Sfida il Mercato")

# --- 1. CARICAMENTO DATI ---
with st.spinner("Caricamento dati di portafoglio..."):
    df_trans = get_data("transactions")
    df_map = get_data("mapping")
    df_prices = get_data("prices")

if df_trans.empty or df_map.empty:
    st.warning("⚠️ Dati di transazioni o mappatura mancanti. Vai su 'Gestione Dati' per configurarli.")
    st.stop()

# --- 2. SELEZIONE E LOGICA ---
bench_ticker = render_benchmark_selector()

if bench_ticker:
    try:
        with st.spinner(f"Calcolo simulazione su {bench_ticker}..."):
            df_chart, df_log = run_benchmark_simulation(bench_ticker, df_trans, df_map, df_prices)

        if not df_chart.empty:
            # --- 3. RENDERIZZAZIONE COMPONENTI ---
            render_benchmark_kpis(df_chart, bench_ticker)
            render_transaction_log(df_log, bench_ticker)
            render_performance_chart(df_chart, bench_ticker)
            render_drawdown_chart(df_chart)
            
        else:
            st.info("Nessun dato da visualizzare per la simulazione.")

    except Exception as e:
        st.error(f"Impossibile completare la simulazione: {e}")

"""
⚖️ Sfida il Mercato - Simulazione Benchmark

Questo script consente di confrontare le performance del tuo portafoglio con un benchmark di riferimento.
Ogni transazione reale viene replicata virtualmente sul benchmark, tenendo conto di:
- Prezzi storici del benchmark (scaricati da Yahoo Finance)
- Tassi di cambio (se il benchmark è in una valuta diversa dall'euro)
- Valore complessivo del benchmark convertito in euro per un confronto diretto

Funzionalità principali:
1. Log dettagliato delle transazioni reali e virtuali (benchmark), con prezzi in EUR.
2. Grafico del valore nel tempo (€) per il portafoglio e il benchmark.
3. Analisi del rischio tramite il calcolo del drawdown (perdita dai massimi).

L'utente può scaricare un log dettagliato delle transazioni per analisi aggiuntive.
"""