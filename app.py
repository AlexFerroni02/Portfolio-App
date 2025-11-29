import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
from utils import get_data, save_data, color_pnl, make_sidebar

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="Portfolio Pro", layout="wide", page_icon="🚀")
make_sidebar()
st.title("🚀 Dashboard Portafoglio")

# --- CARICAMENTO DATI ---
with st.spinner("Caricamento dati..."):
    df_trans = get_data("transactions")
    df_map = get_data("mapping")
    df_prices = get_data("prices")

if df_trans.empty:
    st.info("👋 Benvenuto! Il database è vuoto. Vai su 'Gestione Dati' nel menu a sinistra per importare il CSV.")
    st.stop()

# --- CONTROLLO MAPPATURA MANCANTE (Auto-Detect) ---
all_isins = df_trans['isin'].unique()
mapped_isins = df_map['isin'].unique() if not df_map.empty else []
missing_isins = [i for i in all_isins if i not in mapped_isins]

if missing_isins:
    st.warning(f"⚠️ Ci sono {len(missing_isins)} nuovi asset senza Ticker Yahoo!")
    with st.form("quick_mapping_form"):
        new_mappings = []
        for isin in missing_isins:
            prod_name = df_trans[df_trans['isin'] == isin]['product'].iloc[0]
            st.write(f"**{prod_name}** ({isin})")
            ticker_input = st.text_input(f"Ticker", key=isin, placeholder="es. SWDA.MI")
            if ticker_input:
                new_mappings.append({'isin': isin, 'ticker': ticker_input.strip()})
            st.divider()
        if st.form_submit_button("💾 Salva e Aggiorna"):
            if new_mappings:
                new_df = pd.DataFrame(new_mappings)
                df_final = pd.concat([df_map, new_df], ignore_index=True).drop_duplicates(subset=['isin'], keep='last')
                save_data(df_final, "mapping")
                st.success("Salvato! Ricarico...")
                st.rerun()
    st.stop() 

# --- PREPARAZIONE DATI ---
df_trans['date'] = pd.to_datetime(df_trans['date'], errors='coerce').dt.normalize()
df_prices['date'] = pd.to_datetime(df_prices['date'], errors='coerce').dt.normalize()

# Unisce transazioni e mapping
df_full = df_trans.merge(df_map, on='isin', how='left')

# Recupera l'ultimo prezzo disponibile
last_p = df_prices.sort_values('date').groupby('ticker').tail(1).set_index('ticker')['close_price']

# Calcolo View aggregata
view = df_full.groupby(['product', 'ticker']).agg({'quantity':'sum', 'local_value':'sum'}).reset_index()
view = view[view['quantity'] > 0.001] 

view['net_invested'] = -view['local_value']
view['curr_price'] = view['ticker'].map(last_p)
view['mkt_val'] = view['quantity'] * view['curr_price']
view['pnl'] = view['mkt_val'] - view['net_invested']
view['pnl%'] = (view['pnl'] / view['net_invested']) * 100

# --- KPI TOTALI ---
tot_val = view['mkt_val'].sum()
tot_inv = view['net_invested'].sum()
tot_pnl = tot_val - tot_inv

c1, c2, c3 = st.columns(3)
c1.metric("💰 Valore Totale", f"€ {tot_val:,.2f}")
c2.metric("💳 Capitale Investito", f"€ {tot_inv:,.2f}")
c3.metric("📈 P&L Netto", f"€ {tot_pnl:,.2f}", delta=f"{(tot_pnl/tot_inv)*100:.2f}%" if tot_inv else "0%")

st.divider()

# --- GRAFICI (Torta + Treemap) ---
col1, col2 = st.columns(2)
with col1:
    if not view.empty:
        fig_pie = px.pie(view, values='mkt_val', names='product', title='Allocazione Asset', hole=0.4)
        # MODIFICA: Mostra solo la percentuale dentro le fette
        fig_pie.update_traces(textposition='inside', textinfo='percent', textfont_size=12)
        # Legenda orizzontale sotto il grafico
        fig_pie.update_layout(
            height=400, # Aumentiamo un po' l'altezza per far spazio alla legenda
            title_font_size=18,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=-0.2, # Sposta la legenda sotto
                xanchor="center",
                x=0.5
            ),
            margin=dict(l=20, r=20, t=40, b=20)
        )
        st.plotly_chart(fig_pie, use_container_width=True)
with col2:
    if not view.empty:
        fig_tree = px.treemap(view, path=['product'], values='mkt_val', color='pnl%',
                              color_continuous_scale='RdYlGn', color_continuous_midpoint=0,
                              title='Mappa Performance')
        fig_tree.update_layout(
            height=400,
            title_font_size=18,
            margin=dict(l=20, r=20, t=40, b=40) # Aumentato margine inferiore
        )
        st.plotly_chart(fig_tree, use_container_width=True)

# --- GRAFICO STORICO (OTTIMIZZATO - VETTORIALE) ---
st.subheader("📉 Andamento Temporale")
if not df_prices.empty and not df_full.empty:
    # 1. Crea timeline completa
    start_dt = df_trans['date'].min()
    end_dt = datetime.today()
    full_idx = pd.date_range(start_dt, end_dt, freq='D').normalize()

    # 2. Calcola quantità giornaliere (Pivot + Cumsum)
    daily_qty_change = df_full.pivot_table(index='date', columns='ticker', values='quantity', aggfunc='sum').fillna(0)
    daily_holdings = daily_qty_change.reindex(full_idx, fill_value=0).cumsum()

    # 3. Prepara i prezzi (Pivot + Ffill)
    price_matrix = df_prices.pivot(index='date', columns='ticker', values='close_price')
    price_matrix = price_matrix.reindex(full_idx).ffill() 

    # 4. Calcola Valore (Moltiplicazione matriciale: Holdings * Prices)
    common_cols = daily_holdings.columns.intersection(price_matrix.columns)
    daily_value = (daily_holdings[common_cols] * price_matrix[common_cols]).sum(axis=1)

    # 5. Calcola Investito (Cumulativo)
    daily_inv_change = df_full.pivot_table(index='date', values='local_value', aggfunc='sum').fillna(0)
    daily_invested = -daily_inv_change.reindex(full_idx, fill_value=0).cumsum()

    # 6. Crea DataFrame finale per il grafico
    hdf = pd.DataFrame({
        'Data': full_idx,
        'Valore': daily_value,
        'Investito': daily_invested['local_value']
    })

    fig_hist = go.Figure()
    fig_hist.add_trace(go.Scatter(x=hdf['Data'], y=hdf['Valore'], fill='tozeroy', name='Valore Attuale', line_color='#00CC96'))
    fig_hist.add_trace(go.Scatter(x=hdf['Data'], y=hdf['Investito'], name='Soldi Versati', line=dict(color='#EF553B', dash='dash')))
    fig_hist.update_layout(
        height=400,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
        margin=dict(l=0, r=0, t=20, b=0) # Aggiunto margine superiore per la legenda
    )
    st.plotly_chart(fig_hist, use_container_width=True)
else:
    st.info("Dati insufficienti per il grafico storico.")

# --- TABELLA INTERATTIVA ---
st.subheader("📋 Dettaglio Asset (Clicca per Analisi)")
display_df = view[['product', 'ticker', 'quantity', 'net_invested', 'mkt_val', 'pnl%']].sort_values('mkt_val', ascending=False)

selection = st.dataframe(
    display_df.style.format({
        'quantity': "{:.2f}", 'net_invested': "€ {:.2f}", 'mkt_val': "€ {:.2f}", 'pnl%': "{:.2f}%"
    }).applymap(color_pnl, subset=['pnl%']),
    use_container_width=True,
    selection_mode="single-row",
    on_select="rerun",
    hide_index=True
)

if selection.selection.rows:
    idx = selection.selection.rows[0]
    sel_ticker = display_df.iloc[idx]['ticker']
    st.session_state['selected_ticker'] = sel_ticker
    st.switch_page("pages/1_Analisi_Asset.py")