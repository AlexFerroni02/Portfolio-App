import pandas as pd
import numpy as np
from datetime import datetime

def calculate_portfolio_view(df_trans, df_map, df_prices):
    if df_trans.empty or df_map.empty:
        return pd.DataFrame()
    # Join transazioni e mapping su isin, con suffixes per evitare conflitti di colonne
    df_full = df_trans.merge(df_map, on='isin', how='left', suffixes=('_trans', '_map'))
    # Rinomina id_map in mapping_id
    if 'mapping_id' not in df_full.columns and 'id_map' in df_full.columns:
        df_full = df_full.rename(columns={'id_map': 'mapping_id'})
    if 'mapping_id' not in df_full.columns:
        df_full['mapping_id'] = pd.NA
    # Join prezzi e mapping su mapping_id
    if not df_prices.empty:
        last_p = df_prices.sort_values('date').groupby('mapping_id').tail(1).set_index('mapping_id')['close_price']
    else:
        last_p = pd.Series(dtype='float64')
    view = df_full.groupby(['product', 'mapping_id', 'category']).agg(
        quantity=('quantity', 'sum'),
        local_value=('local_value', 'sum')
    ).reset_index()
    view = view[view['quantity'] > 0.001].copy()
    view['net_invested'] = -view['local_value']
    view['curr_price'] = view['mapping_id'].map(last_p)
    view['mkt_val'] = view['quantity'] * view['curr_price']
    view['pnl'] = view['mkt_val'] - view['net_invested']
    view['pnl%'] = (view['pnl'] / view['net_invested'].replace(0, np.nan)) * 100
    # Join per ottenere il ticker solo per visualizzazione
    view = view.merge(df_map[['id', 'ticker']], left_on='mapping_id', right_on='id', how='left')
    return view.fillna({'curr_price': 0, 'mkt_val': 0, 'pnl': 0, 'pnl%': 0})

def calculate_liquidity(df_budget: pd.DataFrame, df_trans: pd.DataFrame = None) -> tuple[float, str]:
    """Calcola la liquidità finale partendo dal saldo iniziale o, in sua assenza, dai totali.
    Gli investimenti sono calcolati dalla categoria 'Investimento' nel budget, non dalle transazioni DEGIRO.
    """
    if df_budget.empty:
        return 0.0, "Liquidità"
    df_budget_sorted = df_budget.sort_values('date')
    initial_balance_entry = df_budget_sorted[df_budget_sorted['category'] == 'Saldo Iniziale'].head(1)
    if not initial_balance_entry.empty:
        start_date = initial_balance_entry['date'].iloc[0]
        base_liquidity = initial_balance_entry['amount'].iloc[0]
        budget_to_sum = df_budget_sorted[df_budget_sorted['date'] > start_date]
        other_entrate = budget_to_sum[(budget_to_sum['type'] == 'Entrata') & (budget_to_sum['category'] != 'Saldo Iniziale')]['amount'].sum()
        # Uscite normali (escluso Investimento)
        all_uscite = budget_to_sum[(budget_to_sum['type'] == 'Uscita') & (budget_to_sum['category'] != 'Investimento')]['amount'].sum()
        # Investimenti dal budget
        investments = budget_to_sum[(budget_to_sum['type'] == 'Uscita') & (budget_to_sum['category'] == 'Investimento')]['amount'].sum()
        final_liquidity = base_liquidity + other_entrate - all_uscite - investments
    else:
        total_entrate = df_budget['amount'][df_budget['type'] == 'Entrata'].sum()
        # Uscite normali (escluso Investimento)
        total_uscite = df_budget[(df_budget['type'] == 'Uscita') & (df_budget['category'] != 'Investimento')]['amount'].sum()
        # Investimenti dal budget
        total_investito = df_budget[(df_budget['type'] == 'Uscita') & (df_budget['category'] == 'Investimento')]['amount'].sum()
        final_liquidity = total_entrate - total_uscite - total_investito
    return final_liquidity, "Liquidità Calcolata"

def get_historical_portfolio(df_trans, df_map, df_prices):
    if df_prices.empty or df_trans.empty or df_map.empty:
        return pd.DataFrame()
    df_full = df_trans.merge(df_map, on='isin', how='left', suffixes=('_trans', '_map'))
    # FIX: rinomina id_map in mapping_id solo se serve
    if 'mapping_id' not in df_full.columns and 'id_map' in df_full.columns:
        df_full = df_full.rename(columns={'id_map': 'mapping_id'})
    if 'mapping_id' not in df_full.columns:
        df_full['mapping_id'] = pd.NA
    start_dt, end_dt = df_trans['date'].min(), datetime.today()
    full_idx = pd.date_range(start_dt, end_dt, freq='D').normalize()
    # Pivot su mapping_id invece che ticker
    daily_qty_change = df_full.pivot_table(index='date', columns='mapping_id', values='quantity', aggfunc='sum').fillna(0)
    daily_holdings = daily_qty_change.reindex(full_idx, fill_value=0).cumsum()
    price_matrix = df_prices.pivot_table(index='date', columns='mapping_id', values='close_price', aggfunc='last').reindex(full_idx).ffill()
    common_cols = daily_holdings.columns.intersection(price_matrix.columns)
    daily_value = (daily_holdings[common_cols] * price_matrix[common_cols]).sum(axis=1)
    daily_inv_change = df_full.pivot_table(index='date', values='local_value', aggfunc='sum').fillna(0)
    daily_invested = -daily_inv_change.reindex(full_idx, fill_value=0).cumsum()
    hdf = pd.DataFrame({'Data': full_idx, 'Valore': daily_value, 'Investito': daily_invested['local_value']})
    return hdf