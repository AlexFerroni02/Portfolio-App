import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from utils import get_data, make_sidebar

st.set_page_config(page_title="Benchmark", layout="wide", page_icon="⚖️")

# 1. ATTIVA IL MENU LATERALE
make_sidebar()

st.title("⚖️ Sfida il Mercato")

# 2. CARICAMENTO DATI
with st.spinner("Caricamento dati..."):
    df_trans = get_data("transactions")
    df_map = get_data("mapping")
    df_prices = get_data("prices")

if df_trans.empty:
    st.warning("⚠️ Carica prima i dati nella pagina Gestione.")
    st.stop()

# Preparazione dati
try:
    df_trans['date'] = pd.to_datetime(df_trans['date'], errors='coerce').dt.normalize()
    df_prices['date'] = pd.to_datetime(df_prices['date'], errors='coerce').dt.normalize()
except Exception as e:
    st.error(f"Errore conversione date: {e}")
    st.stop()

df_full = df_trans.merge(df_map, on='isin', how='left')

# 3. SCELTA DEL BENCHMARK
st.markdown("### 1. Scegli il tuo Avversario")
col1, col2 = st.columns([1, 3])
with col1:
    bench_ticker = st.text_input("Ticker Yahoo (es. SWDA.MI)", value="SWDA.MI")
with col2:
    st.info(
        f"Stiamo simulando questo scenario: **'E se ogni volta che ho investito nel mio portafoglio, avessi invece comprato {bench_ticker}?'**"
    )

# 4. SCARICO DATI BENCHMARK
start_date = df_trans['date'].min()
end_date = pd.Timestamp.today()

if bench_ticker:
    with st.spinner(f"Sto simulando l'investimento su {bench_ticker}..."):
        try:
            bench_hist = yf.download(bench_ticker, start=start_date, end=end_date, progress=False)
            
            if isinstance(bench_hist.columns, pd.MultiIndex):
                bench_hist = bench_hist['Close']
            elif 'Close' in bench_hist.columns:
                bench_hist = bench_hist[['Close']]
            
            if bench_hist.empty:
                st.error(f"Nessun dato trovato per '{bench_ticker}'.")
                st.stop()
            
            if isinstance(bench_hist, pd.DataFrame):
                bench_hist = bench_hist.iloc[:, 0]
            
            bench_hist.index = pd.to_datetime(bench_hist.index).normalize()
            bench_hist = bench_hist.sort_index()

        except Exception as e:
            st.error(f"Errore download benchmark: {e}")
            st.stop()

    # 5. SIMULAZIONE (Shadow Portfolio)
    timeline = pd.date_range(start=start_date, end=end_date, freq='D').normalize()
    
    my_val_history = []
    bench_val_history = []
    
    # Prepariamo i dati per il loop
    pivot_user = df_prices.pivot_table(index='date', columns='ticker', values='close_price', aggfunc='last').sort_index().ffill()
    trans_grouped = df_full.groupby('date')
    
    user_qty = {} 
    bench_qty = 0 
    
    for d in timeline:
        # A. Gestione Movimenti
        daily_cash_flow = 0
        
        if d in trans_grouped.groups:
            moves = trans_grouped.get_group(d)
            for _, row in moves.iterrows():
                tk = row['ticker']
                if pd.notna(tk):
                    user_qty[tk] = user_qty.get(tk, 0) + row['quantity']
                daily_cash_flow += (-row['local_value'])
        
        # B. Compra/Vendi Benchmark Virtuale
        if daily_cash_flow != 0:
            try:
                idx = bench_hist.index.asof(d)
                if pd.notna(idx):
                    p_bench = bench_hist.at[idx]
                    if pd.notna(p_bench) and p_bench > 0:
                        quote_comprate = daily_cash_flow / p_bench
                        bench_qty += quote_comprate
            except: pass
            
        # C. Calcola Valore Giornaliero
        # 1. Valore Mio
        val_user = 0
        for tk, q in user_qty.items():
            if q > 0.001 and tk in pivot_user.columns:
                try:
                    idx = pivot_user.index.asof(d)
                    if pd.notna(idx):
                        p = pivot_user.at[idx, tk]
                        if pd.notna(p): val_user += q * p
                except: pass
        
        # 2. Valore Benchmark
        val_bench = 0
        try:
            idx = bench_hist.index.asof(d)
            if pd.notna(idx):
                p_bench = bench_hist.at[idx]
                if pd.notna(p_bench): val_bench = bench_qty * p_bench
        except: pass
        
        my_val_history.append(val_user)
        bench_val_history.append(val_bench)

    # 6. VISUALIZZAZIONE
    final_user = my_val_history[-1]
    final_bench = bench_val_history[-1]
    diff = final_user - final_bench
    
    st.divider()
    st.markdown("### 🏁 Risultato del Confronto")
    
    k1, k2, k3 = st.columns(3)
    k1.metric("Il Tuo Portafoglio", f"€ {final_user:,.2f}")
    k2.metric(f"Benchmark ({bench_ticker})", f"€ {final_bench:,.2f}")
    k3.metric("Differenza (Alpha)", f"€ {diff:,.2f}", 
              delta=f"{((final_user - final_bench)/final_bench)*100:.2f}%" if final_bench else "0%")

    # Creazione DataFrame per i grafici
    df_chart = pd.DataFrame({
        'Data': timeline,
        'Tu': my_val_history,
        'Benchmark': bench_val_history
    })
    
    # --- GRAFICO 1: PERFORMANCE ---
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df_chart['Data'], y=df_chart['Tu'], mode='lines', name='Il Tuo Portafoglio', line=dict(color='#00CC96', width=3)))
    fig.add_trace(go.Scatter(x=df_chart['Data'], y=df_chart['Benchmark'], mode='lines', name=f'Benchmark ({bench_ticker})', line=dict(color='#A0A0A0', width=2, dash='dot')))
    fig.update_layout(hovermode="x unified", title="La Gara nel Tempo")
    st.plotly_chart(fig, use_container_width=True)

    if diff > 0:
        st.success(f"🎉 COMPLIMENTI! Stai battendo il mercato di **€ {diff:,.2f}**.")
    else:
        st.warning(f"📉 Attenzione: Un investimento passivo su {bench_ticker} avrebbe reso **€ {abs(diff):,.2f}** in più.")

    # --- GRAFICO 2: DRAWDOWN (OTTIMIZZATO) ---
    st.divider()
    st.subheader("🌊 Analisi Drawdown (Rischio)")
    st.caption("Questo grafico mostra quanto il portafoglio è sceso rispetto al suo picco massimo precedente. Più l'area è profonda, maggiore è stato il 'dolore' durante la discesa.")

    # Calcolo Drawdown
    # 1. Calcola il massimo cumulativo fino a quel giorno
    df_chart['Tu_Max'] = df_chart['Tu'].cummax()
    df_chart['Bench_Max'] = df_chart['Benchmark'].cummax()

    # 2. Calcola la % di perdita dal massimo (vettoriale)
    df_chart['Tu_DD'] = ((df_chart['Tu'] - df_chart['Tu_Max']) / df_chart['Tu_Max']) * 100
    df_chart['Bench_DD'] = ((df_chart['Benchmark'] - df_chart['Bench_Max']) / df_chart['Bench_Max']) * 100

    # Gestisci eventuali NaN o valori infiniti
    df_chart['Tu_DD'] = df_chart['Tu_DD'].fillna(0)
    df_chart['Bench_DD'] = df_chart['Bench_DD'].fillna(0)

    # Crea il grafico del Drawdown
    fig_dd = go.Figure()

    # Area rossa per il tuo drawdown
    fig_dd.add_trace(go.Scatter(
        x=df_chart['Data'], 
        y=df_chart['Tu_DD'], 
        fill='tozeroy', 
        mode='lines', 
        name='Il Tuo Drawdown', 
        line=dict(color='#EF553B', width=1)
    ))

    # Linea tratteggiata per il benchmark
    fig_dd.add_trace(go.Scatter(
        x=df_chart['Data'], 
        y=df_chart['Bench_DD'], 
        mode='lines', 
        name=f'Drawdown {bench_ticker}', 
        line=dict(color='#A0A0A0', width=1, dash='dot')
    ))

    fig_dd.update_layout(
        title="Drawdown dal Picco Massimo (%)",
        yaxis_title="Perdita dal Picco (%)",
        hovermode="x unified",
        yaxis=dict(ticksuffix="%") # Aggiunge il simbolo % all'asse Y
    )
    st.plotly_chart(fig_dd, use_container_width=True)