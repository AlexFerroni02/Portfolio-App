import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
from utils import get_data, save_data, color_pnl, make_sidebar

# --- CONFIGURAZIONE PAGINA ---
# Deve essere la prima istruzione Streamlit
st.set_page_config(page_title="Portfolio Pro", layout="wide", page_icon="🚀")

# Genera il menu laterale personalizzato (Dashboard / Gestione Dati)
make_sidebar()

st.title("🚀 Dashboard Portafoglio")

# --- CARICAMENTO DATI ---
with st.spinner("Caricamento dati..."):
    df_trans = get_data("transactions")
    df_map = get_data("mapping")
    df_prices = get_data("prices")

# Se non ci sono transazioni, mostra messaggio di benvenuto
if df_trans.empty:
    st.info("👋 Benvenuto! Il database è vuoto. Vai su 'Gestione Dati' nel menu a sinistra per importare il CSV.")
    st.stop()

# --- CONTROLLO MAPPATURA MANCANTE (AUTO-DETECT) ---
# Verifica se ci sono ISIN nelle transazioni che non hanno un Ticker nella tabella mapping
all_isins = df_trans['isin'].unique()
mapped_isins = df_map['isin'].unique() if not df_map.empty else []
missing_isins = [i for i in all_isins if i not in mapped_isins]

if missing_isins:
    st.warning(f"⚠️ Ci sono {len(missing_isins)} nuovi asset senza Ticker Yahoo!")
    st.write("Per vedere i prezzi e i grafici, devi associare un codice Yahoo Finance (es. `SWDA.MI` o `AAPL`) a questi ISIN.")
    
    with st.form("quick_mapping_form"):
        new_mappings = []
        for isin in missing_isins:
            # Recupera il nome del prodotto dalla prima transazione disponibile
            prod_name = df_trans[df_trans['isin'] == isin]['product'].iloc[0]
            st.write(f"**{prod_name}**")
            st.caption(f"ISIN: {isin}")
            ticker_input = st.text_input(f"Ticker Yahoo", key=isin, placeholder="es. SWDA.MI")
            if ticker_input:
                new_mappings.append({'isin': isin, 'ticker': ticker_input.strip()})
            st.divider()
        
        if st.form_submit_button("💾 Salva e Aggiorna"):
            if new_mappings:
                new_df = pd.DataFrame(new_mappings)
                # Unisce i nuovi mapping a quelli esistenti
                df_final = pd.concat([df_map, new_df], ignore_index=True).drop_duplicates(subset=['isin'], keep='last')
                save_data(df_final, "mapping")
                st.success("Mappatura salvata! Ricarico la pagina...")
                st.rerun()
            else:
                st.error("Inserisci almeno un ticker per procedere.")
    
    # Blocca l'esecuzione qui finché non sono mappati tutti (o almeno finché l'utente non salva)
    st.stop() 

# --- PREPARAZIONE DATI ---
df_trans['date'] = pd.to_datetime(df_trans['date'], errors='coerce').dt.normalize()
df_prices['date'] = pd.to_datetime(df_prices['date'], errors='coerce').dt.normalize()

# Unisce transazioni e mapping
df_full = df_trans.merge(df_map, on='isin', how='left')

# Recupera l'ultimo prezzo disponibile per ogni ticker
last_p = df_prices.sort_values('date').groupby('ticker').tail(1).set_index('ticker')['close_price']

# Calcolo View aggregata per Asset
view = df_full.groupby(['product', 'ticker']).agg({'quantity':'sum', 'local_value':'sum'}).reset_index()
view = view[view['quantity'] > 0.001] # Rimuovi posizioni chiuse (quantità ~ 0)

# Calcolo metriche finanziarie
view['net_invested'] = -view['local_value'] # local_value è negativo quando compri, quindi invertiamo il segno
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
        fig_pie.update_traces(textposition='inside', textinfo='percent+label')
        st.plotly_chart(fig_pie, use_container_width=True)

with col2:
    if not view.empty:
        fig_tree = px.treemap(view, path=['product'], values='mkt_val', color='pnl%',
                              color_continuous_scale='RdYlGn', color_continuous_midpoint=0,
                              title='Mappa Performance')
        st.plotly_chart(fig_tree, use_container_width=True)

# --- GRAFICO STORICO (Valore vs Costo) ---
st.subheader("📉 Andamento Temporale")
if not df_prices.empty:
    # Crea una tabella pivot dei prezzi (Date x Ticker)
    pivot = df_prices.pivot(index='date', columns='ticker', values='close_price').sort_index().ffill()
    
    start_dt = df_trans['date'].min()
    rng = pd.date_range(start_dt, datetime.today(), freq='D').normalize()
    
    hist_data = []
    curr_qty = {}
    cum_inv = 0
    trans_g = df_full.groupby('date')
    
    # Calcola valore giorno per giorno
    for d in rng:
        # Aggiorna quantità e investito se ci sono transazioni in quel giorno
        if d in trans_g.groups:
            dm = trans_g.get_group(d)
            for _, r in dm.iterrows():
                tk = r['ticker']
                if pd.notna(tk): curr_qty[tk] = curr_qty.get(tk, 0) + r['quantity']
                cum_inv += (-r['local_value'])
        
        # Calcola valore di mercato corrente
        day_val = 0
        for tk, q in curr_qty.items():
            if q > 0.001 and tk in pivot.columns:
                try:
                    # Trova il prezzo più recente rispetto alla data d
                    idx = pivot.index.asof(d)
                    if pd.notna(idx): day_val += q * pivot.at[idx, tk]
                except: pass
        hist_data.append({'Data': d, 'Valore': day_val, 'Investito': cum_inv})
    
    hdf = pd.DataFrame(hist_data)
    
    fig_hist = go.Figure()
    fig_hist.add_trace(go.Scatter(x=hdf['Data'], y=hdf['Valore'], fill='tozeroy', name='Valore Attuale', line_color='#00CC96'))
    fig_hist.add_trace(go.Scatter(x=hdf['Data'], y=hdf['Investito'], name='Soldi Versati', line=dict(color='#EF553B', dash='dash')))
    st.plotly_chart(fig_hist, use_container_width=True)
else:
    st.info("Nessun dato storico prezzi disponibile. Vai su 'Gestione Dati' e clicca 'Aggiorna Prezzi'.")

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

# --- LOGICA DI NAVIGAZIONE ---
if selection.selection.rows:
    idx = selection.selection.rows[0]
    sel_ticker = display_df.iloc[idx]['ticker']
    # Salviamo in session state e cambiamo pagina
    st.session_state['selected_ticker'] = sel_ticker
    st.switch_page("pages/1_Analisi_Asset.py")