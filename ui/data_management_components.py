import streamlit as st
import pandas as pd
import json
import numpy as np
from datetime import date
from database.connection import get_data, save_data, save_allocation_json
from services.data_service import (
    process_new_transactions, 
    calculate_net_worth_snapshot,
    sync_prices,
    fetch_justetf_allocation_robust
)

# Disabilita warning pandas per downcasting
pd.set_option('future.no_silent_downcasting', True)

CATEGORIE_ASSET = ["Azionario", "Obbligazionario", "Gold", "Liquidità"]

def render_import_tab():
    st.write("Carica il file `Transactions.csv` di DEGIRO.")
    up = st.file_uploader("Upload CSV", type=['csv'], key="csv_uploader")
    if up and st.button("Importa Transazioni"):
        with st.spinner("Importazione in corso..."):
            df_trans = get_data("transactions")
            new_df = process_new_transactions(up, df_trans)
            if not new_df.empty:
                save_data(new_df, "transactions", method='append')
                st.success(f"✅ Importate {len(new_df)} nuove transazioni!")
            else:
                st.info("Nessuna nuova transazione trovata.")

def render_mapping_tab():
    st.subheader("Modifica, Aggiungi o Elimina Mappature")
    st.caption("Fai doppio clic su una cella per modificarla. Aggiungi una riga in fondo per una nuova mappatura.")

    df_map = get_data("mapping")
    df_trans = get_data("transactions")
    # Filtra solo gli ISIN posseduti (quantità > 0)
    if not df_trans.empty:
        holdings = df_trans.groupby('isin')['quantity'].sum()
        owned_isin = holdings[holdings > 0].index.tolist()
        df_map = df_map[df_map['isin'].isin(owned_isin)]

    # 1. Reset dell'indice (spesso è questo che appare come colonna extra)
    df_map = df_map.reset_index(drop=True)

    df_map_edit = df_map.copy()

    # 2. Rimuovi qualsiasi colonna che si chiami 'id' (maiuscolo o minuscolo)
    cols_to_drop = [c for c in df_map_edit.columns if c.lower() == 'id']
    if cols_to_drop:
        df_map_edit = df_map_edit.drop(columns=cols_to_drop)

    df_map_edit.insert(0, "Elimina", False)
    
    # 3. Aggiungi "id": None nella configurazione per nasconderla forzatamente
    edited_df = st.data_editor(df_map_edit, num_rows="dynamic", width='stretch', hide_index=True,
        column_config={
            "Elimina": st.column_config.CheckboxColumn(required=True),
            "isin": st.column_config.TextColumn("ISIN (Obbligatorio)", required=True),
            "ticker": st.column_config.TextColumn("Ticker Yahoo (Obbligatorio)", required=True),
            "category": st.column_config.SelectboxColumn("Categoria (Obbligatorio)", options=CATEGORIE_ASSET, required=True,),
            "proxy_ticker": None,
            "id": None  # <--- Nascondi forzatamente se dovesse ancora esserci
        })
    if st.button("💾 Salva Modifiche Mappatura", type="primary"):
        df_to_process = edited_df.copy()
        df_to_process = df_to_process[df_to_process["Elimina"] == False].drop(columns=["Elimina"])
        df_to_process.dropna(subset=['isin'], inplace=True)
        df_to_process = df_to_process[df_to_process['isin'].str.strip() != '']
        df_to_process.drop_duplicates(subset=['isin'], keep='last', inplace=True)
        save_data(df_to_process, "mapping", method='replace')
        st.success("✅ Mappatura aggiornata con successo!")

def render_prices_tab():
    st.write("Scarica gli ultimi prezzi di chiusura da Yahoo Finance **solo per gli asset che possiedi**.")
    if st.button("Avvia Sincronizzazione Prezzi"):
        df_trans, df_map = get_data("transactions"), get_data("mapping")
        if not df_map.empty and not df_trans.empty:
            n = sync_prices(df_trans, df_map)
            if n > 0: st.success(f"✅ Aggiornamento completato: {n} nuovi prezzi salvati.")
            else: st.info("Tutti i prezzi per gli asset posseduti sono già aggiornati.")
        else:
            st.error("Database transazioni o mappatura vuoto. Impossibile aggiornare i prezzi.")

def render_budget_tab(initial_balance_exists: bool):
    st.header("➕ Inserimento Rapido Movimenti")
    CATEGORIE_ENTRATE_BASE = ["Stipendio", "Bonus", "Regali", "Dividendi", "Rimborso", "Altro", "Aggiustamento Liquidità"]
    CATEGORIE_USCITE = ["Affitto/Casa", "Spesa Alimentare", "Ristoranti/Svago", "Trasporti", "Viaggi", "Salute", "Shopping", "Bollette", "Altro", "Aggiustamento Liquidità"]
    ALL_CATEGORIES = sorted(list(set(CATEGORIE_ENTRATE_BASE + CATEGORIE_USCITE + ["Saldo Iniziale"])))
    
    if not initial_balance_exists:
        CATEGORIE_ENTRATE = ["Saldo Iniziale"] + CATEGORIE_ENTRATE_BASE
        st.warning("**Imposta il tuo Saldo Iniziale!** Questo è il primo passo fondamentale.", icon="🎯")
    else:
        CATEGORIE_ENTRATE = CATEGORIE_ENTRATE_BASE
        st.success("✅ Hai già inserito un 'Saldo Iniziale'.", icon="👍")
    
    st.info("💡 Inserisci solo gli importi > 0, gli altri verranno ignorati automaticamente.")
    
    col_date, col_type = st.columns(2)
    selected_date = col_date.date_input("📅 Data", date.today(), key="batch_date")
    f_type = col_type.radio("📌 Tipo:", ["Uscita", "Entrata"], horizontal=True, key="budget_type_radio")
    
    active_categories = CATEGORIE_USCITE if f_type == "Uscita" else CATEGORIE_ENTRATE
    
    with st.form("batch_form", clear_on_submit=True):
        st.subheader("🔴 Inserisci Uscite" if f_type == "Uscita" else "🟢 Inserisci Entrate")
        
        # Layout compatto: 3 categorie per riga
        for i in range(0, len(active_categories), 3):
            cols = st.columns(3)
            for j, col in enumerate(cols):
                if i + j < len(active_categories):
                    cat = active_categories[i + j]
                    with col:
                        st.number_input(
                            f"💰 {cat}", 
                            key=f"movimento_{cat}", 
                            min_value=0.0, 
                            value=0.0, 
                            format="%.2f",
                            help=f"Inserisci importo per {cat}"
                        )
        
        st.divider()
        submitted = st.form_submit_button("💾 Salva Movimenti", type="primary", use_container_width=True)
        
        if submitted:
            rows_to_add = []
            for cat in active_categories:
                amount = st.session_state.get(f"movimento_{cat}", 0.0)
                if amount > 0:
                    rows_to_add.append({
                        'date': pd.to_datetime(selected_date), 
                        'type': f_type, 
                        'category': cat, 
                        'amount': amount, 
                        'note': ''
                    })
            if rows_to_add:
                save_data(pd.DataFrame(rows_to_add), "budget", method='append')
                st.success(f"✅ Salvati {len(rows_to_add)} nuovi movimenti!")
            else:
                st.warning("⚠️ Nessun importo inserito. Inserisci almeno un valore > 0.")
    
    st.divider()
    
    # --- STORICO MOVIMENTI ---
    st.subheader("📊 Storico Movimenti (Modifica o Elimina)")
    df_budget_all = get_data("budget")
    if not df_budget_all.empty:
        df_budget_all['date'] = pd.to_datetime(df_budget_all['date']).dt.date
        df_edit = df_budget_all.sort_values('date', ascending=False).copy()
        df_edit.insert(0, "Elimina", False)
        
        edited_budget = st.data_editor(
            df_edit, 
            width='stretch', 
            hide_index=True, 
            num_rows="dynamic", 
            key="budget_editor",
            column_config={
                "Elimina": st.column_config.CheckboxColumn("🗑️", required=True),
                "date": st.column_config.DateColumn("📅 Data", format="DD/MM/YYYY", required=True),
                "type": st.column_config.SelectboxColumn("📌 Tipo", options=["Entrata", "Uscita"], required=True),
                "category": st.column_config.SelectboxColumn("🏷️ Categoria", options=ALL_CATEGORIES, required=True),
                "amount": st.column_config.NumberColumn("💰 Importo", format="€ %.2f", required=True),
                "note": st.column_config.TextColumn("📝 Note"),
                "id": None
            }
        )
        if st.button("💾 Salva Modifiche Storico", type="primary"):
            df_to_save = pd.DataFrame(edited_budget)
            df_to_save = df_to_save[df_to_save["Elimina"] == False].drop(columns=["Elimina"])
            if "id" in df_to_save.columns:
                df_to_save = df_to_save.drop(columns=["id"])
            save_data(df_to_save, "budget", method='replace')
            st.success("✅ Movimenti aggiornati!")
            st.rerun()
    else:
        st.info("Nessun movimento presente. Inizia ad aggiungere le tue entrate e uscite!")

def render_allocation_tab():
    st.subheader("Scarica e Modifica Dati di Allocazione (X-Ray)")

    # Controlli per evitare comportamenti strani della pagina
    if 'allocation_data_modified' not in st.session_state:
        st.session_state.allocation_data_modified = False

    df_map, df_trans, df_alloc = get_data("mapping"), get_data("transactions"), get_data("asset_allocation")
    if df_map.empty or df_trans.empty:
        st.warning("Mancano transazioni o mappatura.")
        return
    df_full = df_trans.merge(df_map, on='isin', how='left')
    holdings = df_full.groupby(['product', 'ticker', 'isin']).agg(quantity=('quantity', 'sum')).reset_index()
    view = holdings[holdings['quantity'] > 0.001].copy()
    
    # Crea un dizionario per mappare la stringa visualizzata all'ISIN
    display_to_isin = {}
    options = []
    for _, row in view.iterrows():
        display_str = f"{row['product']} ({row['ticker']})"
        display_to_isin[display_str] = row['isin']
        options.append(display_str)
    
    st.subheader("1. Scarica Nuovi Dati")
    col_sel, col_btn = st.columns([3, 1])
    selected_option = col_sel.selectbox("Seleziona un asset da analizzare:", options, key="asset_selector_alloc")
    if col_btn.button("⚡ Analizza Asset (JustETF)", type="primary"):
        with st.spinner("Scraping in corso..."):
            try:
                isin = display_to_isin[selected_option]
                geo_dict, sec_dict = fetch_justetf_allocation_robust(isin)
                if geo_dict or sec_dict:
                    st.session_state.scraped_data = {'geo': geo_dict, 'sec': sec_dict, 'isin': isin}
                    st.success(f"✅ Dati scaricati! Paesi: {len(geo_dict)}, Settori: {len(sec_dict)}")
                else:
                    st.error("❌ Nessun dato trovato. Il sito JustETF potrebbe aver cambiato struttura o l'ISIN non è valido.")
                    st.info("💡 Prova a inserire i dati manualmente nella sezione sottostante.")
            except Exception as e:
                st.error(f"❌ Errore durante lo scraping: {str(e)}")
                st.info("💡 Prova a inserire i dati manualmente nella sezione sottostante.")
    
    if st.session_state.get('scraped_data'):
        st.subheader("2. Verifica e Salva Dati")
        data = st.session_state.scraped_data
        with st.form("verify_and_save_form"):
            st.write(f"**ISIN:** {data['isin']}")
            geo_input = st.text_area("Dati Geografici (JSON)", value=json.dumps(data['geo'], indent=2), height=150)
            sec_input = st.text_area("Dati Settoriali (JSON)", value=json.dumps(data['sec'], indent=2), height=150)
            if st.form_submit_button("💾 Salva nel Database"):
                try:
                    geo_parsed = json.loads(geo_input)
                    sec_parsed = json.loads(sec_input)
                    # Trova mapping_id dall'ISIN
                    mapping_row = df_map[df_map['isin'] == data['isin']]
                    if not mapping_row.empty:
                        mapping_id = int(mapping_row['id'].iloc[0])
                        save_allocation_json(mapping_id, geo_parsed, sec_parsed)
                        st.success("✅ Dati salvati!")
                        del st.session_state.scraped_data
                        # Segnala che i dati sono stati modificati
                        st.session_state.allocation_data_modified = True
                    else:
                        st.error("❌ ISIN non trovato nella mappatura.")
                except json.JSONDecodeError:
                    st.error("❌ JSON non valido. Correggi e riprova.")
    
    st.divider()
    st.subheader("3. Modifica Dati Esistenti")
    # Merge per aggiungere ticker a df_alloc (se esiste)
    df_alloc_with_ticker = df_alloc.merge(df_map[['id', 'ticker']], left_on='mapping_id', right_on='id', how='left') if not df_alloc.empty else pd.DataFrame()
    
    # Ottieni tutti i ticker posseduti (da holdings)
    all_tickers = view['ticker'].unique()
    
    ticker_options = sorted(all_tickers)
    
    ticker_to_edit = st.selectbox("Seleziona un asset da modificare:", ticker_options, key="alloc_ticker_edit")
    if ticker_to_edit:
        # Cerca dati esistenti per questo ticker
        asset_data = None
        if not df_alloc_with_ticker.empty:
            asset_row = df_alloc_with_ticker[df_alloc_with_ticker['ticker'] == ticker_to_edit]
            if not asset_row.empty:
                asset_data = asset_row.iloc[0]
        
        with st.form("edit_allocation_form"):
            st.write(f"**Modifica per {ticker_to_edit}**")
            if asset_data is not None:
                # Dati esistenti
                geo_edit = st.text_area("Geografia (JSON)", value=json.dumps(asset_data.get('geography_json', {}), indent=2), height=150)
                sec_edit = st.text_area("Settori (JSON)", value=json.dumps(asset_data.get('sector_json', {}), indent=2), height=150)
            else:
                # Nessun dato esistente, campi vuoti per inserimento manuale
                geo_edit = st.text_area("Geografia (JSON)", value="{}", height=150, placeholder="Inserisci manualmente, es: {\"Italia\": 50, \"USA\": 30, \"Altri\": 20}")
                sec_edit = st.text_area("Settori (JSON)", value="{}", height=150, placeholder="Inserisci manualmente, es: {\"Tecnologia\": 40, \"Finanza\": 30, \"Altro\": 30}")
            
            if st.form_submit_button("💾 Aggiorna/Salva"):
                try:
                    geo_parsed = json.loads(geo_edit)
                    sec_parsed = json.loads(sec_edit)
                    # Trova mapping_id dal ticker
                    mapping_row = df_map[df_map['ticker'] == ticker_to_edit]
                    if not mapping_row.empty:
                        mapping_id = int(mapping_row['id'].iloc[0])
                        save_allocation_json(mapping_id, geo_parsed, sec_parsed)
                        st.success("✅ Salvato!")
                        # Segnala che i dati sono stati modificati
                        st.session_state.allocation_data_modified = True
                    else:
                        st.error(f"❌ Ticker '{ticker_to_edit}' non trovato nella mappatura.")
                except json.JSONDecodeError as e:
                    st.error(f"❌ JSON non valido: {e}")
                except Exception as e:
                    st.error(f"❌ Errore salvataggio: {e}")

    # --- 4. TABELLE RIEPILOGATIVE ---
    st.divider()
    col_title, col_refresh = st.columns([3, 1])
    with col_title:
        st.subheader("4. 📊 Riepilogo Allocazioni per Ticker")
    with col_refresh:
        if st.button("🔄", help="Aggiorna vista dati"):
            st.cache_data.clear()
            st.session_state.allocation_data_modified = False
            st.rerun()

    # Mostra messaggio se i dati sono stati modificati
    if st.session_state.get('allocation_data_modified', False):
        st.info("📝 **Dati modificati!** Clicca '🔄' per vedere gli aggiornamenti.")

    if not df_alloc.empty and not df_map.empty:
        # Unisci dati allocazione con mapping per ottenere ticker
        df_alloc_with_ticker = df_alloc.merge(df_map[['id', 'ticker']], left_on='mapping_id', right_on='id', how='left')

        # Crea tabella geografia
        st.markdown("#### 🌍 Allocazione Geografica per Ticker")
        geo_rows = []
        for _, row in df_alloc_with_ticker.iterrows():
            if row.get('geography_json'):
                try:
                    geo_data = json.loads(row['geography_json']) if isinstance(row['geography_json'], str) else row['geography_json']
                    geo_data['Ticker'] = row['ticker']
                    geo_rows.append(geo_data)
                except (json.JSONDecodeError, TypeError):
                    continue

        if geo_rows:
            df_geo_pivot = pd.DataFrame(geo_rows).set_index('Ticker').fillna(0)
            # Calcola totale per riga (sostituendo temporaneamente zeri con 0 per calcolo)
            df_geo_numeric = df_geo_pivot.replace(0, 0).astype(float)
            df_geo_pivot['Totale'] = df_geo_numeric.sum(axis=1)
            # Ordina colonne per importanza (paesi con valori più alti prima, totale alla fine)
            col_sums = df_geo_numeric.sum().sort_values(ascending=False)
            ordered_cols = col_sums.index.tolist() + ['Totale']
            df_geo_pivot = df_geo_pivot[ordered_cols]

            # Converti tutto a stringa per evitare problemi di tipo con PyArrow
            df_geo_display = df_geo_pivot.applymap(lambda x: '-' if x == 0 else f"{x:.1f}%" if isinstance(x, (int, float)) else str(x))
            st.dataframe(df_geo_display, width='stretch')
        else:
            st.info("Nessun dato geografico disponibile.")

        # Crea tabella settori
        st.markdown("#### 🧬 Allocazione Settoriale per Ticker")
        sec_rows = []
        for _, row in df_alloc_with_ticker.iterrows():
            if row.get('sector_json'):
                try:
                    sec_data = json.loads(row['sector_json']) if isinstance(row['sector_json'], str) else row['sector_json']
                    sec_data['Ticker'] = row['ticker']
                    sec_rows.append(sec_data)
                except (json.JSONDecodeError, TypeError):
                    continue

        if sec_rows:
            df_sec_pivot = pd.DataFrame(sec_rows).set_index('Ticker').fillna(0)
            # Calcola totale per riga (sostituendo temporaneamente zeri con 0 per calcolo)
            df_sec_numeric = df_sec_pivot.replace(0, 0).astype(float)
            df_sec_pivot['Totale'] = df_sec_numeric.sum(axis=1)
            # Ordina colonne per importanza (settori con valori più alti prima, totale alla fine)
            col_sums = df_sec_numeric.sum().sort_values(ascending=False)
            ordered_cols = col_sums.index.tolist() + ['Totale']
            df_sec_pivot = df_sec_pivot[ordered_cols]

            # Converti tutto a stringa per evitare problemi di tipo con PyArrow
            df_sec_display = df_sec_pivot.applymap(lambda x: '-' if x == 0 else f"{x:.1f}%" if isinstance(x, (int, float)) else str(x))
            st.dataframe(df_sec_display, width='stretch')
        else:
            st.info("Nessun dato settoriale disponibile.")
    else:
        st.info("Nessun dato di allocazione disponibile.")

def render_net_worth_tab():
    st.subheader("🎯 Gestione Patrimonio Netto")
    
    # --- 1. SNAPSHOT AUTOMATICO ---
    st.markdown("### 1. Snapshot Automatico")
    snapshot_date_input = st.date_input("Data per lo Snapshot", date.today(), key="snapshot_date_input")
    
    if st.button("Calcola Patrimonio a questa data"):
        with st.spinner("Calcolo in corso..."):
            snapshot_date = pd.to_datetime(snapshot_date_input).normalize()
            dfs = {name: get_data(name) for name in ["transactions", "mapping", "prices", "budget"]}
            st.session_state.calculated_snapshot = {"date": snapshot_date, "values": calculate_net_worth_snapshot(snapshot_date, **dfs)}
            
    if st.session_state.get('calculated_snapshot'):
        snap = st.session_state.calculated_snapshot
        net_worth, assets_val, liquidity_val = snap['values']
        st.metric(f"Patrimonio Calcolato al {snap['date'].strftime('%d-%m-%Y')}", f"€ {net_worth:,.2f}", f"Asset: € {assets_val:,.2f} | Liquidità: € {liquidity_val:,.2f}")
        
        if st.button("💾 Salva questo Snapshot", type="primary"):
            df_history = get_data("networth_history")
            new_snapshot = pd.DataFrame([{'date': snap['date'], 'net_worth': net_worth}])
            df_merged = pd.concat([df_history, new_snapshot]).drop_duplicates(subset='date', keep='last')
            save_data(df_merged.sort_values('date'), "networth_history", method='replace')
            st.success("Snapshot salvato!"); st.session_state.calculated_snapshot = None; st.rerun()
            
    st.divider()

    # --- 2. AGGIUNTA MANUALE ---
    st.markdown("### 2. Aggiunta Manuale Rapida")
    with st.form("manual_add_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        manual_date = c1.date_input("Data", key="manual_date_input")
        manual_nw = c2.number_input("Patrimonio Netto (€)", min_value=0.0, format="%.2f")
        
        if st.form_submit_button("➕ Aggiungi Valore Manuale") and manual_nw > 0:
            df_history = get_data("networth_history")
            new_entry = pd.DataFrame([{'date': pd.to_datetime(manual_date), 'net_worth': manual_nw}])
            df_merged = pd.concat([df_history, new_entry]).drop_duplicates(subset='date', keep='last')
            save_data(df_merged.sort_values('date'), "networth_history", method='replace')
            st.success("Valore aggiunto!"); st.rerun()
            
    st.divider()

    # --- 3. MODIFICA STORICO ---
    st.markdown("### 3. Modifica o Elimina Storico")
    df_history_full = get_data("networth_history")
    
    df_nw_edit = pd.DataFrame(columns=['date', 'net_worth'])
    if not df_history_full.empty and 'net_worth' in df_history_full.columns:
        df_nw_edit = df_history_full[['date', 'net_worth']].dropna(subset=['net_worth']).copy()
        if not df_nw_edit.empty:
            df_nw_edit['date'] = pd.to_datetime(df_nw_edit['date']).dt.date

    df_nw_edit = df_nw_edit.reset_index(drop=True)
    cols_to_drop = [c for c in df_nw_edit.columns if c.lower() == 'id']
    if cols_to_drop: df_nw_edit = df_nw_edit.drop(columns=cols_to_drop)
    
    df_nw_edit.insert(0, "Elimina", False)

    edited_nw = st.data_editor(
        df_nw_edit.sort_values('date', ascending=False), 
        num_rows="dynamic", 
        width='stretch', 
        hide_index=True, 
        key="nw_editor",
        column_config={
            "Elimina": st.column_config.CheckboxColumn(required=True),
            "date": st.column_config.DateColumn("Data", required=True), 
            "net_worth": st.column_config.NumberColumn("Patrimonio Netto (€)", format="€ %.2f", required=True),
            "id": None
        }
    )

    if st.button("💾 Salva Modifiche Storico", type="primary"):
        df_new_nw = pd.DataFrame(edited_nw)
        df_new_nw = df_new_nw[df_new_nw["Elimina"] == False].drop(columns=["Elimina"])
        if "id" in df_new_nw.columns: df_new_nw = df_new_nw.drop(columns=["id"])

        df_goals_only = pd.DataFrame(columns=['date', 'goal'])
        if not df_history_full.empty and 'goal' in df_history_full.columns:
            df_goals_only = df_history_full[['date', 'goal']].dropna(subset=['goal'])

        if not df_new_nw.empty:
            df_new_nw['date'] = pd.to_datetime(df_new_nw['date'])
            df_final = pd.merge(df_new_nw, df_goals_only, on='date', how='outer')
        else:
            df_final = df_goals_only

        save_data(df_final.sort_values('date'), "networth_history", method='replace')
        st.success("Storico aggiornato!"); st.rerun()
            
    st.divider()

    # --- 4. OBIETTIVI FUTURI ---
    st.markdown("### 4. Imposta Obiettivi Futuri")
    
    # Preparazione dati puliti
    df_goals_edit = pd.DataFrame(columns=['date', 'goal'])
    if not df_history_full.empty and 'goal' in df_history_full.columns:
        df_goals_edit = df_history_full[['date', 'goal']].dropna(subset=['goal']).copy()
        if not df_goals_edit.empty:
            df_goals_edit['date'] = pd.to_datetime(df_goals_edit['date']).dt.date

    # Pulizia robusta ID e Indice
    df_goals_edit = df_goals_edit.reset_index(drop=True)
    cols_to_drop_g = [c for c in df_goals_edit.columns if c.lower() == 'id']
    if cols_to_drop_g: df_goals_edit = df_goals_edit.drop(columns=cols_to_drop_g)

    df_goals_edit.insert(0, "Elimina", False)

    edited_goals = st.data_editor(
        df_goals_edit.sort_values('date'), 
        num_rows="dynamic", 
        width='stretch', 
        hide_index=True, 
        key="goal_editor",
        column_config={
            "Elimina": st.column_config.CheckboxColumn(required=True),
            "date": st.column_config.DateColumn("Data Obiettivo", required=True), 
            "goal": st.column_config.NumberColumn("Obiettivo (€)", format="€ %.2f", required=True),
            "id": None
        }
    )

    if st.button("💾 Salva Obiettivi"):
        # Filtra eliminati e pulisci
        df_new_goals = pd.DataFrame(edited_goals)
        df_new_goals = df_new_goals[df_new_goals["Elimina"] == False].drop(columns=["Elimina"])
        if "id" in df_new_goals.columns: df_new_goals = df_new_goals.drop(columns=["id"])

        # Ricarica per sicurezza lo stato attuale
        df_history_curr = get_data("networth_history")
        
        if not df_new_goals.empty: 
            df_new_goals['date'] = pd.to_datetime(df_new_goals['date']).dt.normalize()
        
        # Logica di merge complessa per mantenere i dati esistenti
        df_combined = pd.concat([df_history_curr, df_new_goals]).drop_duplicates(subset=['date'], keep='last').sort_values('date')
        
        # Ricostruzione pulita
        df_nw_points = df_combined[['date', 'net_worth']].dropna()
        df_goal_points = df_combined[['date', 'goal']].dropna()
        
        if not df_goal_points.empty:
            df_final = pd.merge_asof(df_nw_points.sort_values('date'), df_goal_points.sort_values('date'), on='date', direction='forward')
            # Aggiungi anche i goal futuri che non hanno ancora un net_worth corrispondente
            df_final = pd.concat([df_final, df_goal_points]).drop_duplicates(subset=['date'], keep='last').sort_values('date')
        else:
            df_final = df_nw_points
            df_final['goal'] = np.nan
            
        # Pulizia finale: rimuovi righe vuote o goal passati inutili
        future_goals = df_final['date'] > pd.Timestamp.now().normalize()
        df_final = df_final[df_final['net_worth'].notna() | (df_final['goal'].notna() & future_goals)]
        save_data(df_final, "networth_history", method='replace')
        st.success("Obiettivi salvati e propagati!"); st.rerun()