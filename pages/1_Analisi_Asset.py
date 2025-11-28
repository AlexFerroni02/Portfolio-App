import streamlit as st
import pandas as pd
import plotly.express as px
from utils import load_and_clean_data

st.set_page_config(page_title="Analisi Asset", layout="wide", page_icon="🔎")

# --- BOTTONE TORNA ALLA HOME ---
if st.button("⬅️ Torna alla Dashboard"):
    st.switch_page("app.py")

st.title("🔎 Dettaglio ETF")

df_trans, df_map, df_prices, df_full = load_and_clean_data()
if df_full is None: st.stop()

# Lista prodotti
products = df_full['product'].unique()

# LOGICA INTELLIGENTE DI SELEZIONE
# Se arriviamo dalla Home con un click, usiamo quello. Altrimenti il primo della lista.
default_index = 0
if 'selected_etf_from_home' in st.session_state:
    target = st.session_state['selected_etf_from_home']
    if target in products:
        # Trova l'indice del prodotto cliccato
        default_index = list(products).index(target)

# Il menu a tendina si posiziona automaticamente sull'ETF cliccato
selected_product = st.selectbox("Seleziona ETF:", products, index=default_index)

# --- IL RESTO DELLA PAGINA ---
df_asset = df_full[df_full['product'] == selected_product]
ticker = df_asset['ticker'].iloc[0] if not df_asset.empty else None

qty = df_asset['quantity'].sum()
inv = -df_asset['local_value'].sum()

last_p = 0
if ticker in df_prices['ticker'].values:
    last_date = df_prices[df_prices['ticker']==ticker]['date'].max()
    last_p = df_prices[(df_prices['ticker']==ticker) & (df_prices['date']==last_date)]['close_price'].values[0]

cur_val = qty * last_p
pnl = cur_val - inv

c1, c2, c3, c4 = st.columns(4)
c1.metric("Quantità", f"{qty:.2f}")
c2.metric("Prezzo Oggi", f"€ {last_p:.2f}")
c3.metric("Valore", f"€ {cur_val:,.2f}")
c4.metric("P&L", f"€ {pnl:,.2f}", delta=f"{(pnl/inv)*100:.2f}%" if inv else "0%")

if ticker:
    st.caption(f"Ticker: {ticker}")
    asset_p = df_prices[df_prices['ticker'] == ticker].sort_values('date')
    if not asset_p.empty:
        st.plotly_chart(px.line(asset_p, x='date', y='close_price', title="Prezzo Storico"), use_container_width=True)

st.subheader("Movimenti")
st.dataframe(df_asset[['date', 'quantity', 'local_value', 'fees']].sort_values('date', ascending=False)
             .style.format({'quantity': '{:.2f}', 'local_value': '€ {:.2f}', 'fees': '€ {:.2f}'}))