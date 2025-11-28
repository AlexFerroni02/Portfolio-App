import streamlit as st
import pandas as pd
import yfinance as yf
import hashlib
import plotly.express as px
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta, date

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="Portfolio Manager", layout="wide", page_icon="📈")

# --- CONNESSIONE A GOOGLE SHEETS ---
@st.cache_resource
def get_google_sheet_client():
    # Recupera le credenziali dai Secrets di Streamlit Cloud
    secrets = st.secrets["gcp_service_account"]
    creds = Credentials.from_service_account_info(
        secrets,
        scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    )
    return gspread.authorize(creds)

def get_data(sheet_name):
    """Scarica i dati dal foglio Google in modo sicuro."""
    client = get_google_sheet_client()
    try:
        sh = client.open("PortfolioDB")
        wks = sh.worksheet(sheet_name)
        data = wks.get_all_records()
        return pd.DataFrame(data)
    except Exception:
        # Se il foglio non esiste o è vuoto, ritorna un DataFrame vuoto
        return pd.DataFrame()

def save_data(df, sheet_name):
    """Salva i dati sovrascrivendo il foglio."""
    client = get_google_sheet_client()
    sh = client.open("PortfolioDB")
    try:
        wks = sh.worksheet(sheet_name)
    except:
        wks = sh.add_worksheet(title=sheet_name, rows=1000, cols=20)
    
    wks.clear()
    if not df.empty:
        # Convertiamo tutto in stringa per compatibilità JSON (evita errori di scrittura)
        df_str = df.astype(str)
        wks.update([df_str.columns.values.tolist()] + df_str.values.tolist())

# --- FUNZIONI DI ELABORAZIONE ---
def parse_degiro_csv(file):
    """Legge il CSV di DEGIRO e pulisce i numeri italiani."""
    df = pd.read_csv(file)
    cols_to_clean = ['Quantità', 'Quotazione', 'Valore', 'Costi di transazione']
    
    for c in cols_to_clean:
        if c in df.columns:
            # Sostituisce virgola con punto e converte in numero
            df[c] = df[c].astype(str).str.replace(',', '.').apply(pd.to_numeric, errors='coerce').fillna(0)
    
    if 'Data' in df.columns:
        df['Data'] = pd.to_datetime(df['Data'], format='%d-%m-%Y', errors='coerce')
    
    if 'Costi di transazione' in df.columns:
        df['Costi di transazione'] = df['Costi di transazione'].abs()
        
    return df

def generate_id(row):
    """Genera un ID univoco per evitare duplicati."""
    raw = f"{row['Data']}{row['Ora']}{row['ISIN']}{row['ID Ordine']}"
    return hashlib.md5(raw.encode()).hexdigest()

def sync_prices(tickers):
    """Scarica i prezzi mancanti da Yahoo Finance."""
    if not tickers: return 0
    
    df_prices = get_data("prices")
    
    # 🛡️ PROTEZIONE DATE: Pulizia preventiva del DB prezzi esistente
    if not df_prices.empty:
        df_prices['date'] = pd.to_datetime(df_prices['date'], errors='coerce')
        df_prices = df_prices.dropna(subset=['date'])
        # Assicuriamoci che i prezzi siano numeri
        df_prices['close_price'] = pd.to_numeric(df_prices['close_price'], errors='coerce')
    
    new_data = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for i, t in enumerate(tickers):
        status_text.write(f"Controllo dati per: {t}...")
        start_date = "2020-01-01"
        
        # Cerchiamo l'ultima data salvata per questo ticker
        if not df_prices.empty:
            existing = df_prices[df_prices['ticker'] == t]
            if not existing.empty:
                last_date = existing['date'].max()
                if pd.notna(last_date):
                    if last_date.date() >= date.today():
                        continue # Già aggiornato a oggi
                    start_date = (last_date + timedelta(days=1)).strftime('%Y-%m-%d')
        
        try:
            # Scarica da Yahoo
            hist = yf.download(t, start=start_date, progress=False)
            
            if not hist.empty:
                # Gestione formato di ritorno (Series o DataFrame)
                closes = hist['Close']
                if isinstance(closes, pd.DataFrame):
                    closes = closes.iloc[:, 0] # Prende la prima colonna se multipla
                
                for d, val in closes.items():
                    if pd.notna(val):
                        new_data.append({
                            'ticker': t,
                            'date': d.strftime('%Y-%m-%d'),
                            'close_price': float(val)
                        })
        except Exception:
            pass # Se fallisce (es. ticker vecchio), ignora e prosegue
            
        progress_bar.progress((i + 1) / len(tickers))
        
    status_text.empty()
    progress_bar.empty()
    
    if new_data:
        df_new = pd.DataFrame(new_data)
        # Unisce i vecchi dati con i nuovi
        df_final = pd.concat([df_prices, df_new], ignore_index=True)
        # Rimuove eventuali duplicati
        df_final = df_final.drop_duplicates(subset=['ticker', 'date'])
        save_data(df_final, "prices")
        return len(new_data)
    
    return 0

# --- INTERFACCIA UTENTE PRINCIPALE ---
def main():
    st.title("🌐 Il Mio Portafoglio Cloud")
    
    # 1. Caricamento Dati (Mapping e Transazioni)
    with st.spinner("Connessione al Database..."):
        df_trans = get_data("transactions")
        df_map = get_data("mapping")

    # 2. Sidebar: Caricamento CSV
    with st.sidebar:
        st.header("Gestione Dati")
        uploaded_file = st.file_uploader("Carica CSV Degiro", type=['csv'])
        
        if uploaded_file and st.button("Importa Transazioni"):
            new_df = parse_degiro_csv(uploaded_file)
            rows_to_add = []
            
            # Recupera gli ID già presenti per non duplicare
            existing_ids = df_trans['id'].tolist() if not df_trans.empty else []
            
            count = 0
            for _, row in new_df.iterrows():
                if pd.isna(row['ISIN']): continue
                
                tid = generate_id(row)
                if tid not in existing_ids:
                    rows_to_add.append({
                        'id': tid,
                        'date': row['Data'].strftime('%Y-%m-%d'),
                        'product': row['Prodotto'],
                        'isin': row['ISIN'],
                        'quantity': row['Quantità'],
                        'local_value': row['Valore'], # Nota: Negativo per acquisti
                        'fees': row['Costi di transazione'],
                        'currency': 'EUR'
                    })
                    existing_ids.append(tid)
                    count += 1
            
            if rows_to_add:
                df_add = pd.DataFrame(rows_to_add)
                df_total = pd.concat([df_trans, df_add], ignore_index=True)
                save_data(df_total, "transactions")
                st.success(f"Salvate {count} nuove transazioni!")
                st.rerun()
            else:
                st.info("Nessuna nuova transazione trovata.")

    # 3. Sezione Aggiornamento Prezzi
    # Legge i ticker SOLO dal foglio 'mapping' (quelli che hai messo a mano o salvato)
    if not df_map.empty:
        col_btn, col_msg = st.columns([1, 4])
        if col_btn.button("🔄 Aggiorna Prezzi"):
            tickers_list = df_map['ticker'].unique().tolist()
            with st.spinner("Aggiornamento prezzi da Yahoo Finance..."):
                n = sync_prices(tickers_list)
            if n > 0:
                st.success(f"Scaricati {n} nuovi prezzi!")
            else:
                st.info("I prezzi sono già aggiornati a oggi.")

    # 4. Calcolo e Visualizzazione Dashboard
    df_prices = get_data("prices")
    
    # 🛡️ PROTEZIONE DATE (Critico per evitare crash)
    if not df_prices.empty:
        df_prices['date'] = pd.to_datetime(df_prices['date'], errors='coerce')
        df_prices = df_prices.dropna(subset=['date'])

    # Controlliamo di avere tutti i pezzi del puzzle
    if not df_trans.empty and not df_map.empty and not df_prices.empty:
        
        # Unisce Transazioni + Mapping
        df_full = df_trans.merge(df_map, on='isin', how='left')
        
        # Prepara l'ultimo prezzo disponibile per ogni ticker
        last_prices = df_prices.sort_values('date').groupby('ticker').tail(1).set_index('ticker')['close_price']
        
        # Raggruppa per prodotto per vedere le posizioni aperte
        view = df_full.groupby(['product', 'ticker']).agg({
            'quantity': 'sum',
            'local_value': 'sum' # Somma dei costi storici (negativi)
        }).reset_index()
        
        # Filtra solo le posizioni aperte (> 0.001 per tolleranza decimale)
        view = view[view['quantity'] > 0.001]
        
        # Calcoli Finanziari
        view['net_invested'] = -view['local_value'] # Invertiamo il segno (Spesa -> Investito Positivo)
        view['current_price'] = view['ticker'].map(last_prices)
        view['market_value'] = view['quantity'] * view['current_price']
        view['pnl'] = view['market_value'] - view['net_invested']
        view['pnl_perc'] = (view['pnl'] / view['net_invested']) * 100
        
        # Totali Generali (KPI)
        total_market_value = view['market_value'].sum()
        total_invested = view['net_invested'].sum()
        total_pnl = total_market_value - total_invested
        
        # KPI Cards
        k1, k2, k3 = st.columns(3)
        k1.metric("Valore Portafoglio", f"€ {total_market_value:,.2f}")
        k2.metric("Capitale Investito", f"€ {total_invested:,.2f}")
        k3.metric("Profitto/Perdita", f"€ {total_pnl:,.2f}", 
                  delta=f"{(total_pnl/total_invested)*100:.2f}%" if total_invested else "0%")
        
        st.divider()
        
        # --- GRAFICO STORICO ---
        st.subheader("Andamento Temporale")
        df_trans['date'] = pd.to_datetime(df_trans['date'])
        
        # Tabella Pivot dei prezzi (Date sulle righe, Ticker sulle colonne)
        pivot_prices = df_prices.pivot(index='date', columns='ticker', values='close_price').ffill()
        
        # Genera il range di date dal primo acquisto a oggi
        start_dt = df_trans['date'].min()
        date_range = pd.date_range(start=start_dt, end=datetime.today(), freq='D')
        
        history = []
        current_qty = {} # Tieni traccia delle quantità giorno per giorno
        trans_grouped = df_full.groupby('date')
        
        for d in date_range:
            # Aggiorna le quantità se quel giorno ci sono state transazioni
            if d in trans_grouped.groups:
                day_trans = trans_grouped.get_group(d)
                for _, t in day_trans.iterrows():
                    tk = t['ticker']
                    if pd.notna(tk):
                        current_qty[tk] = current_qty.get(tk, 0) + t['quantity']
            
            # Calcola il valore totale per quel giorno
            daily_val = 0
            for tk, qty in current_qty.items():
                if qty > 0 and tk in pivot_prices.columns:
                    # Prendi il prezzo di quel giorno (o l'ultimo disponibile prima)
                    idx = pivot_prices.index.asof(d)
                    if pd.notna(idx):
                        price = pivot_prices.at[idx, tk]
                        if pd.notna(price):
                            daily_val += qty * price
            
            history.append({'Data': d, 'Valore': daily_val})
            
        st.plotly_chart(px.line(pd.DataFrame(history), x='Data', y='Valore'), use_container_width=True)
        
        # --- TABELLA DETTAGLI (Corretta) ---
        st.subheader("Dettaglio Asset")
        
        # Dizionario di formattazione: Specifica SOLO le colonne numeriche
        # 'product' è testo e NON è incluso qui, così non darà errore 'Unknown format code'
        formats = {
            'quantity': "{:.2f}",
            'net_invested': "€ {:.2f}",
            'market_value': "€ {:.2f}",
            'pnl_perc': "{:.2f}%"
        }
        
        # Mostra la tabella formattata
        st.dataframe(view[['product', 'quantity', 'net_invested', 'market_value', 'pnl_perc']].style.format(formats))

if __name__ == "__main__":
    main()