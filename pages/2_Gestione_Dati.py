import streamlit as st
import pandas as pd
from utils import get_data, save_data, parse_degiro_csv, generate_id, sync_prices, make_sidebar

st.set_page_config(page_title="Gestione Dati", page_icon="📂", layout="wide")
make_sidebar()
st.title("📂 Gestione Database")

tab1, tab2, tab3 = st.tabs(["📥 Importa CSV", "🔗 Mappatura Ticker", "🔄 Aggiorna Prezzi"])

# --- TAB 1: IMPORT ---
with tab1:
    st.write("Carica il file `Transactions.csv` di DEGIRO.")
    up = st.file_uploader("Upload CSV", type=['csv'])
    if up and st.button("Importa Transazioni"):
        ndf = parse_degiro_csv(up)
        df_trans = get_data("transactions")
        exist = df_trans['id'].tolist() if not df_trans.empty else []
        rows = []
        c = 0
        for idx, r in ndf.iterrows():
            if pd.isna(r.get('ISIN')): continue
            tid = generate_id(r, idx)
            if tid not in exist:
                val = r.get('Totale', 0) if r.get('Totale', 0) != 0 else r.get('Valore', 0)
                rows.append({
                    'id': tid, 'date': r['Data'].strftime('%Y-%m-%d'),
                    'product': r.get('Prodotto',''), 'isin': r.get('ISIN',''),
                    'quantity': r.get('Quantità',0), 'local_value': val,
                    'fees': r.get('Costi di transazione',0), 'currency': 'EUR'
                })
                exist.append(tid)
                c += 1
        if rows:
            new_df = pd.concat([df_trans, pd.DataFrame(rows)], ignore_index=True) if not df_trans.empty else pd.DataFrame(rows)
            save_data(new_df, "transactions")
            st.success(f"✅ Importate {c} nuove transazioni!")
        else:
            st.info("Nessuna nuova transazione trovata.")

# --- TAB 2: MAPPING ---
with tab2:
    df_map = get_data("mapping")
    st.dataframe(df_map, use_container_width=True)
    
    with st.form("add_map"):
        c1, c2 = st.columns(2)
        isin = c1.text_input("ISIN (es. IE00B4L5Y983)")
        ticker = c2.text_input("Ticker Yahoo (es. SWDA.MI)")
        if st.form_submit_button("Salva Mappatura"):
            if isin and ticker:
                new = pd.DataFrame([{'isin': isin.strip(), 'ticker': ticker.strip()}])
                df_final = pd.concat([df_map, new], ignore_index=True).drop_duplicates(subset=['isin'], keep='last')
                save_data(df_final, "mapping")
                st.success("Salvato! Ricarica la pagina.")
                st.rerun()

# --- TAB 3: PREZZI ---
with tab3:
    st.write("Scarica gli ultimi prezzi di chiusura da Yahoo Finance.")
    if st.button("Avvia Sincronizzazione Prezzi"):
        df_map = get_data("mapping")
        if not df_map.empty:
            tickers = df_map['ticker'].unique().tolist()
            n = sync_prices(tickers)
            st.success(f"✅ Aggiornamento completato: {n} nuovi prezzi salvati.")
        else:
            st.error("Nessuna mappatura trovata. Configura prima i ticker.")