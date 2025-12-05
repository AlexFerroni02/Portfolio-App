import streamlit as st
import pandas as pd

# Importazioni da moduli
from database.connection import get_data
from ui.components import make_sidebar
from services.asset_service import get_owned_assets, get_asset_kpis, get_asset_allocation_data
from ui.asset_analysis_components import (
    render_asset_selector, 
    render_asset_header, 
    render_asset_kpis, 
    render_allocation_charts,
    render_price_history,
    render_transactions_table
)

st.set_page_config(page_title="Analisi Asset", page_icon="🔎", layout="wide")
make_sidebar()
st.title("🔎 Analisi per Singolo Asset")

# --- 1. CARICAMENTO DATI ---
with st.spinner("Caricamento dati..."):
    df_trans = get_data("transactions")
    df_map = get_data("mapping")
    df_prices = get_data("prices")
    df_alloc = get_data("asset_allocation")

if df_trans.empty or df_map.empty:
    st.warning("⚠️ Dati di transazioni o mappatura mancanti. Vai su 'Gestione Dati' per configurarli.")
    st.stop()

# --- 2. LOGICA DI SELEZIONE ---
owned_assets = get_owned_assets(df_trans, df_map)
if owned_assets.empty:
    st.info("Nessun asset attualmente in portafoglio.")
    st.stop()

asset_options = owned_assets.apply(lambda x: f"{x['product']} ({x['ticker']})", axis=1).tolist()
ticker = render_asset_selector(asset_options)

# --- 3. PREPARAZIONE DATI PER L'ASSET SELEZIONATO ---
df_full = df_trans.merge(df_map, on='isin', how='left')
df_asset_trans = df_full[df_full['ticker'] == ticker].sort_values('date', ascending=False)
asset_prices = df_prices[df_prices['ticker'] == ticker].sort_values('date') if not df_prices.empty else pd.DataFrame()

kpi_data = get_asset_kpis(ticker, owned_assets, df_asset_trans, asset_prices)
kpi_data['ticker'] = ticker # Aggiungo il ticker per passarlo all'header
geo_data, sec_data = get_asset_allocation_data(ticker, df_alloc)

# --- 4. RENDERIZZAZIONE COMPONENTI ---
render_asset_header(kpi_data)
render_asset_kpis(kpi_data)
render_allocation_charts(geo_data, sec_data)
render_price_history(ticker, asset_prices)
render_transactions_table(df_asset_trans)