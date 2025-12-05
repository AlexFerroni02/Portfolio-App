import streamlit as st
import pandas as pd
import yfinance as yf
from typing import Tuple, Dict, Optional

@st.cache_data(show_spinner=False)
def run_benchmark_simulation(bench_ticker: str, df_trans: pd.DataFrame, df_map: pd.DataFrame, df_prices: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Esegue la simulazione shadow del portafoglio contro un benchmark.
    Restituisce un DataFrame per i grafici e un DataFrame per il log delle transazioni.
    Lancia un'eccezione in caso di errore nel download dei dati.
    """
    df_trans['date'] = pd.to_datetime(df_trans['date'], errors='coerce').dt.normalize()
    if not df_prices.empty:
        df_prices['date'] = pd.to_datetime(df_prices['date'], errors='coerce').dt.normalize()
    
    df_full = df_trans.merge(df_map, on='isin', how='left')
    start_date = df_trans['date'].min()
    end_date = df_prices['date'].max() if not df_prices.empty else df_trans['date'].max()

    try:
        bench_hist = yf.download(bench_ticker, start=start_date, end=end_date, progress=False)
        if bench_hist.empty:
            raise ValueError(f"Nessun dato storico trovato per il ticker '{bench_ticker}'.")
        
        bench_hist = bench_hist[['Close']].iloc[:, 0]
        bench_hist.index = pd.to_datetime(bench_hist.index).normalize()
        full_idx = pd.date_range(start=bench_hist.index.min(), end=bench_hist.index.max(), freq='D')
        bench_hist = bench_hist.reindex(full_idx).ffill()
        
        currency_map = {'TO': 'CAD', 'MI': 'EUR', 'DE': 'EUR', 'L': 'GBP', 'AS': 'AUD'}
        bench_currency = 'EUR'
        for suffix, curr in currency_map.items():
            if bench_ticker.endswith(suffix):
                bench_currency = curr
                break
        
        fx_hist = None
        if bench_currency != 'EUR':
            pair = f"EUR{bench_currency}=X"
            fx_hist_raw = yf.download(pair, start=start_date, end=end_date, progress=False)
            if not fx_hist_raw.empty:
                fx_hist = fx_hist_raw[['Close']].iloc[:, 0]
                fx_hist.index = pd.to_datetime(fx_hist.index).normalize()
                fx_hist = fx_hist.reindex(full_idx).ffill()

    except Exception as e:
        raise ConnectionError(f"Errore durante il download dei dati per {bench_ticker}: {e}")

    timeline = pd.date_range(start=start_date, end=end_date, freq='D').normalize()
    my_val_history, bench_val_history = [], []
    pivot_user = pd.DataFrame()
    if not df_prices.empty:
        pivot_user = df_prices.pivot_table(index='date', columns='ticker', values='close_price', aggfunc='last').sort_index().ffill()
    
    trans_grouped = df_full.groupby('date')
    user_qty, bench_qty = {}, 0.0
    log_transactions = []

    for d in timeline:
        daily_cash = 0
        if d in trans_grouped.groups:
            moves = trans_grouped.get_group(d)
            daily_cash = -moves['local_value'].sum()
            for _, row in moves.iterrows():
                tk = row['ticker']
                if pd.notna(tk): 
                    user_qty[tk] = user_qty.get(tk, 0) + row['quantity']
        
        if daily_cash != 0:
            try:
                idx = bench_hist.index.asof(d)
                if pd.notna(idx):
                    p_bench = bench_hist.at[idx]
                    if pd.notna(p_bench) and p_bench > 0:
                        fx_rate = fx_hist.at[idx] if fx_hist is not None and pd.notna(fx_hist.at[idx]) else 1.0
                        cash_in_local = daily_cash * fx_rate
                        qty_bench = cash_in_local / p_bench
                        bench_qty += qty_bench
                        log_transactions.append({'Data': d, 'Tipo': 'BENCHMARK', 'Importo': daily_cash, 'Quantità': qty_bench, 'Prezzo': p_bench, 'Valuta': bench_currency})
            except Exception: pass
        
        val_user = sum(q * pivot_user.at[pivot_user.index.asof(d), tk] for tk, q in user_qty.items() if q > 0.001 and tk in pivot_user.columns and pd.notna(pivot_user.index.asof(d)))
        
        val_bench = 0
        try:
            idx = bench_hist.index.asof(d)
            if pd.notna(idx):
                p_bench = bench_hist.at[idx]
                if pd.notna(p_bench):
                    fx_rate = fx_hist.at[idx] if fx_hist is not None and pd.notna(fx_hist.at[idx]) else 1.0
                    val_bench = bench_qty * p_bench / fx_rate
        except Exception: pass
        
        my_val_history.append(val_user)
        bench_val_history.append(val_bench)

    df_chart = pd.DataFrame({'Data': timeline, 'Tu': my_val_history, 'Benchmark': bench_val_history})
    df_chart = df_chart[(df_chart['Tu'] > 0) | (df_chart['Benchmark'] > 0)].reset_index(drop=True)
    
    df_log = pd.DataFrame(log_transactions).round(2)
    
    return df_chart, df_log