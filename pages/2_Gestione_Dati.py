import streamlit as st
import pandas as pd
from datetime import date
from utils import get_data, save_data, parse_degiro_csv, generate_id, sync_prices, make_sidebar

st.set_page_config(page_title="Gestione Dati", page_icon="📂", layout="wide")
make_sidebar()
st.title("📂 Gestione Database")

CATEGORIE_ASSET = ["Azionario", "Obbligazionario", "Gold", "Liquidità"]

tab1, tab2, tab3, tab4, tab5 = st.tabs(["📥 Importa CSV", "🔗 Mappatura Ticker", "🔄 Aggiorna Prezzi", "💸 Movimenti Bilancio", "💰 Liquidità"])

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

# --- TAB 4: MOVIMENTI BILANCIO (LAYOUT VERTICALE) ---
with tab4:
    st.header("➕ Inserimento Rapido Movimenti")
    
    CATEGORIE_ENTRATE = ["Stipendio", "Bonus", "Regali", "Dividendi", "Rimborso", "Altro"]
    CATEGORIE_USCITE = ["Affitto/Casa", "Spesa Alimentare", "Ristoranti/Svago", "Trasporti", "Viaggi", "Salute", "Shopping", "Bollette", "Altro"]

    col_date, col_type = st.columns(2)
    selected_date = col_date.date_input("Data per i movimenti", date.today(), key="batch_date")
    f_type = col_type.radio("Tipo Movimento:", ["Uscita", "Entrata"], horizontal=True, key="budget_type_radio")
    
    st.divider()

    with st.form("batch_form", clear_on_submit=True):
        active_categories = CATEGORIE_USCITE if f_type == "Uscita" else CATEGORIE_ENTRATE
        
        if f_type == "Uscita":
            st.subheader("🔴 Inserisci Uscite")
        else:
            st.subheader("🟢 Inserisci Entrate")

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
                    rows_to_add.append({
                        'date': pd.to_datetime(selected_date),
                        'type': f_type,
                        'category': cat,
                        'amount': amount,
                        'note': note if note else ''
                    })

            if rows_to_add:
                new_entries_df = pd.DataFrame(rows_to_add)
                save_data(new_entries_df, "budget", method='append')
                st.success(f"✅ Salvati {len(rows_to_add)} nuovi movimenti!")
            else:
                st.warning("Nessun importo inserito. Nessun movimento salvato.")

    st.subheader("Ultimi Movimenti Inseriti")
    df_budget_display = get_data("budget")
    if not df_budget_display.empty:
        df_budget_display['date'] = pd.to_datetime(df_budget_display['date'])
        cols_to_show = ['date', 'type', 'category', 'amount', 'note']
        st.dataframe(df_budget_display[cols_to_show].sort_values('date', ascending=False).head(10), use_container_width=True, hide_index=True,
            column_config={
                "date": st.column_config.DateColumn("Data", format="DD-MM-YYYY"), 
                "amount": st.column_config.NumberColumn("Importo", format="€ %.2f"),
                "note": st.column_config.TextColumn("Note")
            })
    else:
        st.info("Nessun movimento ancora registrato.")

# --- TAB 5: GESTIONE LIQUIDITA' ---
with tab5:
    st.subheader("Gestione Liquidità Cash")
    st.info("Di default, la liquidità è calcolata automaticamente. Se vuoi, puoi **sovrascrivere** questo calcolo con un valore manuale (es. il saldo del tuo conto corrente).")

    df_settings = get_data("settings")
    current_liquidity = 0.0
    is_manual_mode = False
    if not df_settings.empty:
        liquidity_setting = df_settings[df_settings['key'] == 'manual_liquidity']
        if not liquidity_setting.empty:
            current_liquidity = float(liquidity_setting['value'].iloc[0])
            if current_liquidity > 0:
                is_manual_mode = True

    if is_manual_mode:
        st.success(f"Modalità Attiva: **Manuale**. Valore attuale: **€ {current_liquidity:,.2f}**")
    else:
        st.info("Modalità Attiva: **Automatica**. La liquidità è calcolata da entrate, uscite e investimenti.")

    st.divider()
    st.subheader("Imposta Valore Manuale")
    manual_liquidity_input = st.number_input("Importo da impostare (€)", value=current_liquidity if is_manual_mode else 0.0, min_value=0.0, step=100.0, format="%.2f")

    col1, col2 = st.columns(2)
    if col1.button("💾 Salva Valore Manuale", type="primary"):
        new_setting = pd.DataFrame([{'key': 'manual_liquidity', 'value': str(manual_liquidity_input)}])
        df_existing_settings = get_data("settings")
        if not df_existing_settings.empty:
            df_existing_settings = df_existing_settings[df_existing_settings['key'] != 'manual_liquidity']
        df_final_settings = pd.concat([df_existing_settings, new_setting], ignore_index=True)
        save_data(df_final_settings, "settings", method='replace')
        st.success(f"✅ Liquidità manuale impostata a € {manual_liquidity_input:,.2f}")
        st.rerun()

    if col2.button("🗑️ Elimina e Usa Calcolo Automatico"):
        df_existing_settings = get_data("settings")
        if not df_existing_settings.empty:
            df_final_settings = df_existing_settings[df_existing_settings['key'] != 'manual_liquidity']
            save_data(df_final_settings, "settings", method='replace')
            st.success("✅ Impostazione manuale rimossa. L'app userà il calcolo automatico.")
            st.rerun()
        else:
            st.info("Nessuna impostazione manuale da rimuovere.")