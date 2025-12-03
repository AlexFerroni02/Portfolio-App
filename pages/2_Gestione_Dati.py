import streamlit as st
import pandas as pd
from datetime import date
import json
import numpy as np
from utils import get_data, save_data, parse_degiro_csv, generate_id, sync_prices, make_sidebar, fetch_justetf_allocation_robust, save_allocation_json

st.set_page_config(page_title="Gestione Dati", page_icon="📂", layout="wide")
make_sidebar()
st.title("📂 Gestione Database")

CATEGORIE_ASSET = ["Azionario", "Obbligazionario", "Gold", "Liquidità"]

if 'scraped_data' not in st.session_state:
    st.session_state.scraped_data = None
if 'calculated_snapshot' not in st.session_state:
    st.session_state.calculated_snapshot = None

# Caricamento preliminare per controllo saldo iniziale
df_budget_check = get_data("budget")
initial_balance_exists = False
if not df_budget_check.empty:
    if not df_budget_check[df_budget_check['category'] == 'Saldo Iniziale'].empty:
        initial_balance_exists = True

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["📥 Importa CSV", "🔗 Mappatura Ticker", "🔄 Aggiorna Prezzi", "💸 Movimenti Bilancio", "🔬 Allocazione Asset (X-Ray)", "🎯 Patrimonio Netto"])

# --- TAB 1: IMPORT ---
with tab1:
    st.write("Carica il file `Transactions.csv` di DEGIRO.")
    up = st.file_uploader("Upload CSV", type=['csv'])
    if up and st.button("Importa Transazioni"):
        with st.spinner("Importazione in corso..."):
            ndf = parse_degiro_csv(up)
            df_trans = get_data("transactions")
            rows_to_add = []
            existing_ids = set(df_trans['id']) if not df_trans.empty else set()
            for idx, r in ndf.iterrows():
                if pd.isna(r.get('ISIN')): continue
                tid = generate_id(r, idx)
                if tid not in existing_ids:
                    val = r.get('Totale', 0) if r.get('Totale', 0) != 0 else r.get('Valore', 0)
                    rows_to_add.append({'id': tid, 'date': r['Data'], 'product': r.get('Prodotto',''), 'isin': r.get('ISIN',''), 'quantity': r.get('Quantità',0), 'local_value': val, 'fees': r.get('Costi di transazione',0), 'currency': 'EUR'})
                    existing_ids.add(tid)
            if rows_to_add:
                new_df = pd.DataFrame(rows_to_add)
                save_data(new_df, "transactions", method='append')
                st.success(f"✅ Importate {len(rows_to_add)} nuove transazioni!")
            else:
                st.info("Nessuna nuova transazione trovata.")

# --- TAB 2: MAPPATURA INTERATTIVA ---
with tab2:
    st.subheader("Modifica, Aggiungi o Elimina Mappature")
    st.caption("Fai doppio clic su una cella per modificarla. Aggiungi una riga in fondo per una nuova mappatura.")
    df_map = get_data("mapping")
    df_map_edit = df_map.copy()
    df_map_edit.insert(0, "Elimina", False)
    edited_df = st.data_editor(df_map_edit, num_rows="dynamic", use_container_width=True, hide_index=True,
        column_config={
            "Elimina": st.column_config.CheckboxColumn(required=True),
            "isin": st.column_config.TextColumn("ISIN (Obbligatorio)", required=True),
            "ticker": st.column_config.TextColumn("Ticker Yahoo (Obbligatorio)", required=True),
            "category": st.column_config.SelectboxColumn("Categoria (Obbligatorio)", options=CATEGORIE_ASSET, required=True,)
        })
    if st.button("💾 Salva Modifiche Mappatura", type="primary"):
        df_to_process = edited_df.copy()
        df_to_process = df_to_process[df_to_process["Elimina"] == False].drop(columns=["Elimina"])
        df_to_process.dropna(subset=['isin'], inplace=True)
        df_to_process = df_to_process[df_to_process['isin'].str.strip() != '']
        df_to_process.drop_duplicates(subset=['isin'], keep='last', inplace=True)
        save_data(df_to_process, "mapping", method='replace')
        st.success("✅ Mappatura aggiornata con successo!")
        st.rerun()

# --- TAB 3: PREZZI ---
with tab3:
    st.write("Scarica gli ultimi prezzi di chiusura da Yahoo Finance **solo per gli asset che possiedi**.")
    if st.button("Avvia Sincronizzazione Prezzi"):
        df_trans, df_map = get_data("transactions"), get_data("mapping")
        if not df_map.empty and not df_trans.empty:
            n = sync_prices(df_trans, df_map)
            if n > 0: st.success(f"✅ Aggiornamento completato: {n} nuovi prezzi salvati.")
            else: st.info("Tutti i prezzi per gli asset posseduti sono già aggiornati.")
        else:
            st.error("Database transazioni o mappatura vuoto. Impossibile aggiornare i prezzi.")

# --- TAB 4: MOVIMENTI BILANCIO (POTENZIATO) ---
with tab4:
    st.header("➕ Inserimento Rapido Movimenti")
    
    CATEGORIE_ENTRATE_BASE = ["Stipendio", "Bonus", "Regali", "Dividendi", "Rimborso", "Altro", "Aggiustamento Liquidità"]
    CATEGORIE_USCITE = ["Affitto/Casa", "Spesa Alimentare", "Ristoranti/Svago", "Trasporti", "Viaggi", "Salute", "Shopping", "Bollette", "Altro", "Aggiustamento Liquidità"]
    
    if not initial_balance_exists:
        CATEGORIE_ENTRATE = ["Saldo Iniziale"] + CATEGORIE_ENTRATE_BASE
        st.warning(
            "**Imposta il tuo Saldo Iniziale!**\n\n"
            "Questo è il primo passo fondamentale. Inserisci qui sotto il valore della tua liquidità a una data di partenza a tua scelta. "
            "Tutti i calcoli futuri si baseranno su questo valore.",
            icon="🎯"
        )
    else:
        CATEGORIE_ENTRATE = CATEGORIE_ENTRATE_BASE
        st.success("✅ Hai già inserito un 'Saldo Iniziale'. Puoi aggiungere altri movimenti o usare 'Aggiustamento Liquidità' per correzioni.", icon="👍")

    st.info("💡 Usa 'Aggiustamento Liquidità' (in Entrata o Uscita) per correggere eventuali discrepanze future.")

    col_date, col_type = st.columns(2)
    selected_date = col_date.date_input("Data per i movimenti", date.today(), key="batch_date")
    f_type = col_type.radio("Tipo Movimento:", ["Uscita", "Entrata"], horizontal=True, key="budget_type_radio")
    st.divider()

    with st.form("batch_form", clear_on_submit=True):
        active_categories = CATEGORIE_USCITE if f_type == "Uscita" else CATEGORIE_ENTRATE
        if f_type == "Uscita": st.subheader("🔴 Inserisci Uscite")
        else: st.subheader("🟢 Inserisci Entrate")
        
        for cat in active_categories:
            st.markdown(f"**{cat}**")
            col_val, col_note = st.columns(2)
            col_val.number_input("Importo", label_visibility="collapsed", key=f"movimento_{cat}", min_value=0.0, value=0.0, format="%.2f")
            col_note.text_input("Note", label_visibility="collapsed", key=f"nota_{cat}", placeholder="Nota opzionale...")
            st.divider()
            
        submitted = st.form_submit_button("💾 Salva Movimenti", type="primary", use_container_width=True)
        if submitted:
            rows_to_add = []
            for cat in active_categories:
                amount = st.session_state[f"movimento_{cat}"]
                note = st.session_state[f"nota_{cat}"]
                if amount > 0:
                    rows_to_add.append({'date': pd.to_datetime(selected_date), 'type': f_type, 'category': cat, 'amount': amount, 'note': note if note else ''})
            if rows_to_add:
                new_entries_df = pd.DataFrame(rows_to_add)
                save_data(new_entries_df, "budget", method='append')
                st.success(f"✅ Salvati {len(rows_to_add)} nuovi movimenti!")
                st.rerun()
            else:
                st.warning("Nessun importo inserito. Nessun movimento salvato.")

    st.divider()
    st.subheader("Storico Movimenti (Modifica o Elimina)")
    df_budget_all = get_data("budget")
    if not df_budget_all.empty:
        df_budget_all['date'] = pd.to_datetime(df_budget_all['date']).dt.date
        df_edit = df_budget_all.sort_values('date', ascending=False).copy()
        df_edit.insert(0, "Elimina", False)

        all_categories = sorted(list(set(CATEGORIE_ENTRATE_BASE + CATEGORIE_USCITE + ["Saldo Iniziale"])))

        edited_budget = st.data_editor(
            df_edit,
            use_container_width=True,
            hide_index=True,
            num_rows="dynamic",
            column_config={
                "Elimina": st.column_config.CheckboxColumn(required=True),
                "date": st.column_config.DateColumn("Data", format="DD/MM/YYYY", required=True),
                "type": st.column_config.SelectboxColumn("Tipo", options=["Entrata", "Uscita"], required=True),
                "category": st.column_config.SelectboxColumn("Categoria", options=all_categories, required=True),
                "amount": st.column_config.NumberColumn("Importo", format="€ %.2f", required=True),
                "note": st.column_config.TextColumn("Note")
            }
        )
        
        if st.button("💾 Salva Modifiche Movimenti", type="primary"):
            df_to_save = pd.DataFrame(edited_budget)
            df_to_save = df_to_save[df_to_save["Elimina"] == False].drop(columns=["Elimina"])
            save_data(df_to_save, "budget", method='replace')
            st.success("✅ Movimenti aggiornati con successo!")
            st.rerun()
    else:
        st.info("Nessun movimento ancora registrato.")

# --- TAB 5: GESTIONE ALLOCAZIONE ASSET ---
with tab5:
    st.subheader("Scarica e Modifica Dati di Allocazione (X-Ray)")
    st.caption("Scarica i dati da JustETF, modificali se necessario e salvali.")
    df_map = get_data("mapping")
    df_trans = get_data("transactions")
    df_alloc = get_data("asset_allocation")
    if df_map.empty or df_trans.empty:
        st.warning("Mancano le transazioni o la mappatura. Completa i passaggi precedenti.")
    else:
        df_full = df_trans.merge(df_map, on='isin', how='left')
        holdings = df_full.groupby(['product', 'ticker', 'isin']).agg({'quantity':'sum'}).reset_index()
        view = holdings[holdings['quantity'] > 0.001].copy()
        options = view.apply(lambda x: f"{x['product']} ({x['ticker']})", axis=1).unique()
        
        st.divider()
        st.subheader("1. Scarica Nuovi Dati")
        col_sel, col_btn = st.columns([3, 1])
        selected_option = col_sel.selectbox("Seleziona un asset da analizzare:", options, key="asset_selector_alloc")
        
        if col_btn.button("⚡ Analizza Asset (JustETF)", type="primary"):
            with st.spinner("Scraping in corso..."):
                sel_ticker = selected_option.split('(')[-1].replace(')', '')
                sel_isin = view[view['ticker'] == sel_ticker].iloc[0]['isin']
                geo, sec = fetch_justetf_allocation_robust(sel_isin)
                if geo or sec:
                    st.session_state.scraped_data = {'ticker': sel_ticker, 'geo': geo, 'sec': sec}
                    st.success(f"Dati per {sel_ticker} scaricati! Vai al punto 2 per verificare e salvare.")
                else:
                    st.session_state.scraped_data = None
                    st.error("Nessun dato di allocazione trovato automaticamente per questo ISIN.")
        
        if st.session_state.scraped_data:
            st.divider()
            st.subheader("2. Verifica e Salva Dati")
            data = st.session_state.scraped_data
            st.info(f"Dati scaricati per **{data['ticker']}**. Puoi modificarli prima di salvare.")
            
            with st.form("verify_and_save_form"):
                c1, c2 = st.columns(2)
                geo_text = c1.text_area("JSON Geografico", value=json.dumps(data['geo'], indent=2, ensure_ascii=False), height=300)
                sec_text = c2.text_area("JSON Settoriale", value=json.dumps(data['sec'], indent=2, ensure_ascii=False), height=300)
                
                submitted = st.form_submit_button("💾 Salva Dati nel Database", type="primary")
                if submitted:
                    try:
                        final_geo = json.loads(geo_text)
                        final_sec = json.loads(sec_text)
                        save_allocation_json(data['ticker'], final_geo, final_sec)
                        st.success(f"Dati di allocazione per {data['ticker']} salvati con successo!")
                        st.session_state.scraped_data = None
                        st.rerun()
                    except json.JSONDecodeError:
                        st.error("Errore nel formato JSON. Controlla la sintassi.")
                    except Exception as e:
                        st.error(f"Errore durante il salvataggio: {e}")

        st.divider()
        st.subheader("3. Modifica Dati Esistenti")
        if not df_alloc.empty:
            alloc_tickers = df_alloc['ticker'].unique()
            ticker_to_edit = st.selectbox("Seleziona un asset da modificare:", alloc_tickers)
            if ticker_to_edit:
                record = df_alloc[df_alloc['ticker'] == ticker_to_edit].iloc[0]
                with st.form("edit_alloc_form"):
                    st.write(f"**Dati per: {ticker_to_edit}**")
                    c1_edit, c2_edit = st.columns(2)
                    try:
                        geo_db = record['geography_json'] if isinstance(record['geography_json'], dict) else json.loads(record['geography_json'] or '{}')
                        sec_db = record['sector_json'] if isinstance(record['sector_json'], dict) else json.loads(record['sector_json'] or '{}')
                    except:
                        geo_db, sec_db = {}, {}
                    
                    geo_key = f"geo_edit_{ticker_to_edit}"
                    sec_key = f"sec_edit_{ticker_to_edit}"

                    c1_edit.text_area("JSON Geografico Esistente", value=json.dumps(geo_db, indent=2, ensure_ascii=False), height=300, key=geo_key)
                    c2_edit.text_area("JSON Settoriale Esistente", value=json.dumps(sec_db, indent=2, ensure_ascii=False), height=300, key=sec_key)
                    
                    submitted_edit = st.form_submit_button("💾 Aggiorna Dati", type="primary")
                    if submitted_edit:
                        try:
                            geo_dict_edit = json.loads(st.session_state[geo_key])
                            sec_dict_edit = json.loads(st.session_state[sec_key])
                            
                            save_allocation_json(ticker_to_edit, geo_dict_edit, sec_dict_edit)
                            st.success(f"Dati di allocazione per {ticker_to_edit} aggiornati!")
                            st.rerun()
                        except json.JSONDecodeError:
                            st.error("Errore nel formato JSON. Controlla la sintassi.")
        else:
            st.info("Nessun dato di allocazione ancora salvato nel database.")

# --- TAB 6: GESTIONE PATRIMONIO NETTO ---
with tab6:
    st.subheader("🎯 Gestione Patrimonio Netto")
    
    st.markdown("### 1. Snapshot Automatico")
    st.info("Usa questa sezione per 'fotografare' il tuo patrimonio a una data specifica, basandoti sui dati presenti nell'app.")
    
    snapshot_date_input = st.date_input("Data per lo Snapshot", date.today())

    if st.button("Calcola Patrimonio a questa data", type="secondary"):
        snapshot_date = pd.to_datetime(snapshot_date_input).normalize()
        with st.spinner(f"Calcolo patrimonio netto al {snapshot_date.strftime('%d-%m-%Y')}..."):
            df_trans_nw, df_map_nw, df_prices_nw, df_budget_nw = get_data("transactions"), get_data("mapping"), get_data("prices"), get_data("budget")

            if not df_trans_nw.empty: df_trans_nw['date'] = pd.to_datetime(df_trans_nw['date']).dt.normalize()
            if not df_prices_nw.empty: df_prices_nw['date'] = pd.to_datetime(df_prices_nw['date']).dt.normalize()
            if not df_budget_nw.empty: df_budget_nw['date'] = pd.to_datetime(df_budget_nw['date']).dt.normalize()

            net_worth_at_date, total_assets_value, final_liquidity = 0, 0, 0

            if not df_trans_nw.empty and not df_map_nw.empty and not df_prices_nw.empty:
                trans_at_date = df_trans_nw[df_trans_nw['date'] <= snapshot_date]
                if not trans_at_date.empty:
                    df_full_nw = trans_at_date.merge(df_map_nw, on='isin', how='left')
                    prices_at_date = df_prices_nw[df_prices_nw['date'] <= snapshot_date]
                    last_prices_at_date = prices_at_date.sort_values('date').groupby('ticker').tail(1).set_index('ticker')['close_price']
                    view_nw = df_full_nw.groupby('ticker')['quantity'].sum().reset_index()
                    view_nw['mkt_val'] = view_nw['quantity'] * view_nw['ticker'].map(last_prices_at_date).fillna(0)
                    total_assets_value = view_nw['mkt_val'].sum()

                    if not df_budget_nw.empty:
                        budget_until_snapshot = df_budget_nw[df_budget_nw['date'] <= snapshot_date].sort_values('date')
                        initial_balance_entry = budget_until_snapshot[budget_until_snapshot['category'] == 'Saldo Iniziale'].head(1)
                        if not initial_balance_entry.empty:
                            start_date = initial_balance_entry['date'].iloc[0]
                            base_liquidity = initial_balance_entry['amount'].iloc[0]
                            budget_to_sum = budget_until_snapshot[budget_until_snapshot['date'] > start_date]
                            trans_to_sum = trans_at_date[trans_at_date['date'] > start_date]
                            other_entrate = budget_to_sum[(budget_to_sum['type'] == 'Entrata') & (budget_to_sum['category'] != 'Saldo Iniziale')]['amount'].sum()
                            all_uscite = budget_to_sum[budget_to_sum['type'] == 'Uscita']['amount'].sum()
                            investments = -trans_to_sum['local_value'].sum() if not trans_to_sum.empty else 0.0
                            final_liquidity = base_liquidity + other_entrate - all_uscite - investments
                        else:
                            total_entrate = budget_until_snapshot[budget_until_snapshot['type'] == 'Entrata']['amount'].sum()
                            total_uscite = budget_until_snapshot[budget_until_snapshot['type'] == 'Uscita']['amount'].sum()
                            total_investito_netto = -trans_at_date['local_value'].sum()
                            final_liquidity = total_entrate - total_uscite - total_investito_netto
                    net_worth_at_date = total_assets_value + final_liquidity
            
            st.session_state.calculated_snapshot = {
                "date": snapshot_date, "net_worth": net_worth_at_date,
                "assets": total_assets_value, "liquidity": final_liquidity
            }

    if st.session_state.calculated_snapshot:
        snap = st.session_state.calculated_snapshot
        st.metric(f"Patrimonio Calcolato al {snap['date'].strftime('%d-%m-%Y')}", f"€ {snap['net_worth']:,.2f}")
        st.caption(f"Dettaglio: Valore Asset (€ {snap['assets']:,.2f}) + Liquidità (€ {snap['liquidity']:,.2f})")
        
        if st.button("💾 Salva questo Snapshot", type="primary"):
            df_history = get_data("networth_history")
            new_snapshot = pd.DataFrame([{'date': snap['date'], 'net_worth': snap['net_worth']}])
            
            if not df_history.empty:
                df_history['date'] = pd.to_datetime(df_history['date']).dt.normalize()
                df_merged = pd.concat([df_history, new_snapshot]).drop_duplicates(subset='date', keep='last')
            else:
                df_merged = new_snapshot
            
            save_data(df_merged.sort_values('date'), "networth_history", method='replace')
            st.success(f"Snapshot per il {snap['date'].strftime('%d-%m-%Y')} salvato!")
            st.session_state.calculated_snapshot = None
            st.rerun()

    st.divider()
    
    st.markdown("### 2. Aggiunta Manuale Rapida")
    st.info("Inserisci qui un valore del patrimonio per una data specifica, utile per ricostruire lo storico.")
    with st.form("manual_add_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        manual_date = c1.date_input("Data")
        manual_nw = c2.number_input("Patrimonio Netto (€)", min_value=0.0, format="%.2f")
        submitted = st.form_submit_button("➕ Aggiungi Valore Manuale")

        if submitted and manual_nw > 0:
            df_history = get_data("networth_history")
            new_entry = pd.DataFrame([{'date': pd.to_datetime(manual_date), 'net_worth': manual_nw}])
            
            if not df_history.empty:
                df_history['date'] = pd.to_datetime(df_history['date']).dt.normalize()
                df_merged = pd.concat([df_history, new_entry]).drop_duplicates(subset='date', keep='last')
            else:
                df_merged = new_entry
            
            save_data(df_merged.sort_values('date'), "networth_history", method='replace')
            st.success(f"Valore per il {manual_date.strftime('%d-%m-%Y')} aggiunto con successo!")
            st.rerun()

    st.divider()

    st.markdown("### 3. Modifica o Elimina Storico")
    st.info("Usa questa tabella per correggere o cancellare valori esistenti del patrimonio. Fai doppio clic su una cella per modificarla.")
    
    df_history_full = get_data("networth_history")
    
    df_nw_edit = pd.DataFrame(columns=['date', 'net_worth'])
    if not df_history_full.empty and 'net_worth' in df_history_full.columns:
        df_nw_edit = df_history_full[['date', 'net_worth']].dropna(subset=['net_worth']).copy()
        df_nw_edit['date'] = pd.to_datetime(df_nw_edit['date']).dt.date

    edited_nw = st.data_editor(
        df_nw_edit.sort_values('date', ascending=False), num_rows="dynamic",
        column_config={
            "date": st.column_config.DateColumn("Data", required=True),
            "net_worth": st.column_config.NumberColumn("Patrimonio Netto (€)", format="€ %.2f", required=True)
        }, use_container_width=True, hide_index=True, key="nw_editor"
    )

    if st.button("💾 Salva Modifiche Storico", type="primary"):
        df_goals_only = pd.DataFrame(columns=['date', 'goal'])
        if not df_history_full.empty and 'goal' in df_history_full.columns:
            df_goals_only = df_history_full[['date', 'goal']].dropna(subset=['goal'])
            df_goals_only['date'] = pd.to_datetime(df_goals_only['date']).dt.normalize()

        df_new_nw = pd.DataFrame(edited_nw)
        if not df_new_nw.empty:
            df_new_nw['date'] = pd.to_datetime(df_new_nw['date']).dt.normalize()
            df_final = pd.merge(df_new_nw, df_goals_only, on='date', how='outer')
        else: 
            df_final = df_goals_only

        save_data(df_final.sort_values('date'), "networth_history", method='replace')
        st.success("Storico del patrimonio netto aggiornato!")
        st.rerun()

    st.divider()
    st.markdown("### 4. Imposta Obiettivi Futuri")
    st.info("Definisci i tuoi obiettivi di patrimonio per visualizzarli nei grafici.")

    df_goals_edit = pd.DataFrame(columns=['date', 'goal'])
    if not df_history_full.empty and 'goal' in df_history_full.columns:
        df_goals_edit = df_history_full[['date', 'goal']].dropna(subset=['goal']).copy()
        df_goals_edit['date'] = pd.to_datetime(df_goals_edit['date']).dt.date
    
    edited_goals = st.data_editor(
        df_goals_edit.sort_values('date'), num_rows="dynamic",
        column_config={
            "date": st.column_config.DateColumn("Data Obiettivo", required=True),
            "goal": st.column_config.NumberColumn("Obiettivo (€)", format="€ %.2f", required=True)
        }, use_container_width=True, hide_index=True, key="goal_editor"
    )

    if st.button("💾 Salva Obiettivi"):
        # Carica tutti i dati esistenti
        df_history_full = get_data("networth_history")
        if not df_history_full.empty:
            df_history_full['date'] = pd.to_datetime(df_history_full['date']).dt.normalize()

        # Prendi i nuovi obiettivi dall'editor
        df_new_goals = pd.DataFrame(edited_goals)
        if not df_new_goals.empty:
            df_new_goals['date'] = pd.to_datetime(df_new_goals['date']).dt.normalize()
            df_new_goals.dropna(subset=['date', 'goal'], inplace=True)

        # Unisci tutti i dati (vecchi e nuovi) per avere un quadro completo
        df_combined = pd.concat([df_history_full, df_new_goals]).drop_duplicates(subset=['date'], keep='last').sort_values('date')
        
        # Separa i dati del patrimonio da quelli degli obiettivi
        df_nw_points = df_combined[['date', 'net_worth']].dropna().copy()
        df_goal_points = df_combined[['date', 'goal']].dropna().copy()

        # Se ci sono obiettivi, propaga all'indietro
        if not df_goal_points.empty:
            # Usa merge_asof per trovare l'obiettivo futuro più vicino per ogni punto del patrimonio
            df_final = pd.merge_asof(
                df_nw_points.sort_values('date'), 
                df_goal_points.sort_values('date'), 
                on='date', 
                direction='forward'
            )
            # Unisci di nuovo con i punti obiettivo originali per non perderli
            df_final = pd.concat([df_final, df_goal_points]).drop_duplicates(subset=['date'], keep='last').sort_values('date')
        else:
            # Se non ci sono obiettivi, salva solo i punti del patrimonio
            df_final = df_nw_points
            df_final['goal'] = np.nan
        
        # Pulisci le righe che potrebbero avere solo goal ma non net_worth (a meno che non sia un obiettivo futuro)
        future_goals = df_final['date'] > pd.Timestamp.now().normalize()
        df_final = df_final[df_final['net_worth'].notna() | (df_final['goal'].notna() & future_goals)]

        save_data(df_final, "networth_history", method='replace')
        st.success("Obiettivi salvati e propagati nel database!")
        st.rerun()