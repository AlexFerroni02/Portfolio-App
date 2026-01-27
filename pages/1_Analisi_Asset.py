import streamlit as st
import pandas as pd

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

# Usa mapping_id per la selezione
asset_options = owned_assets.apply(lambda x: f"{x['product']} ({x['ticker']})", axis=1).tolist()
selected_idx = st.selectbox("Seleziona un asset da analizzare:", range(len(asset_options)), format_func=lambda i: asset_options[i])
mapping_id = owned_assets.iloc[selected_idx]['mapping_id']

# --- 3. PREPARAZIONE DATI PER L'ASSET SELEZIONATO ---
df_full = df_trans.merge(df_map, on='isin', how='left', suffixes=('_trans', '_map'))
# Rinomina id_map in mapping_id
if 'mapping_id' not in df_full.columns and 'id_map' in df_full.columns:
    df_full = df_full.rename(columns={'id_map': 'mapping_id'})
if 'mapping_id' not in df_full.columns:
    df_full['mapping_id'] = pd.NA
df_asset_trans = df_full[df_full['mapping_id'] == mapping_id].sort_values('date', ascending=False)
asset_prices = df_prices[df_prices['mapping_id'] == mapping_id].sort_values('date') if not df_prices.empty else pd.DataFrame()

kpi_data = get_asset_kpis(mapping_id, owned_assets, df_asset_trans, asset_prices, df_map)
geo_data, sec_data = get_asset_allocation_data(mapping_id, df_alloc)

# --- 4. RENDERIZZAZIONE COMPONENTI ---
render_asset_header(kpi_data)
render_asset_kpis(kpi_data)
render_allocation_charts(geo_data, sec_data)
render_price_history(kpi_data['ticker'], asset_prices, df_asset_trans)
render_transactions_table(df_asset_trans, kpi_data['last_price'])