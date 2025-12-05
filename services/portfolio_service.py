import pandas as pd
from datetime import datetime

def calculate_portfolio_view(df_trans: pd.DataFrame, df_map: pd.DataFrame, df_prices: pd.DataFrame) -> pd.DataFrame:
    """Calcola la vista aggregata degli ASSET del portafoglio (esclusa liquidità)."""
    if df_trans.empty or df_map.empty:
        return pd.DataFrame()
    df_full = df_trans.merge(df_map, on='isin', how='left')
    last_p = pd.Series(dtype='float64')
    if not df_prices.empty:
        last_p = df_prices.sort_values('date').groupby('ticker').tail(1).set_index('ticker')['close_price']
    view = df_full.groupby(['product', 'ticker', 'category']).agg(quantity=('quantity', 'sum'), local_value=('local_value', 'sum')).reset_index()
    view = view[view['quantity'] > 0.001].copy()
    view['net_invested'] = -view['local_value']
    view['curr_price'] = view['ticker'].map(last_p)
    view['mkt_val'] = view['quantity'] * view['curr_price']
    view['pnl'] = view['mkt_val'] - view['net_invested']
    view['pnl%'] = (view['pnl'] / view['net_invested'].replace(0, pd.NA)) * 100
    return view.fillna({'curr_price': 0, 'mkt_val': 0, 'pnl': 0, 'pnl%': 0})

def calculate_liquidity(df_budget: pd.DataFrame, df_trans: pd.DataFrame) -> tuple[float, str]:
    """Calcola la liquidità finale partendo dal saldo iniziale o, in sua assenza, dai totali."""
    if df_budget.empty:
        return 0.0, "Liquidità"
    df_budget_sorted = df_budget.sort_values('date')
    initial_balance_entry = df_budget_sorted[df_budget_sorted['category'] == 'Saldo Iniziale'].head(1)
    if not initial_balance_entry.empty:
        start_date = initial_balance_entry['date'].iloc[0]
        base_liquidity = initial_balance_entry['amount'].iloc[0]
        budget_to_sum = df_budget_sorted[df_budget_sorted['date'] > start_date]
        trans_to_sum = df_trans[df_trans['date'] > start_date] if not df_trans.empty else pd.DataFrame()
        other_entrate = budget_to_sum[(budget_to_sum['type'] == 'Entrata') & (budget_to_sum['category'] != 'Saldo Iniziale')]['amount'].sum()
        all_uscite = budget_to_sum[budget_to_sum['type'] == 'Uscita']['amount'].sum()
        investments = -trans_to_sum['local_value'].sum() if not trans_to_sum.empty else 0.0
        final_liquidity = base_liquidity + other_entrate - all_uscite - investments
    else:
        total_entrate = df_budget['amount'][df_budget['type'] == 'Entrata'].sum()
        total_uscite = df_budget['amount'][df_budget['type'] == 'Uscita'].sum()
        total_investito_netto = -df_trans['local_value'].sum() if not df_trans.empty else 0.0
        final_liquidity = total_entrate - total_uscite - total_investito_netto
    return final_liquidity, "Liquidità Calcolata"

def get_historical_portfolio(df_trans: pd.DataFrame, df_map: pd.DataFrame, df_prices: pd.DataFrame) -> pd.DataFrame:
    """Calcola l'andamento storico del valore di portafoglio e del capitale investito."""
    if df_prices.empty or df_trans.empty or df_map.empty:
        return pd.DataFrame()
    df_full = df_trans.merge(df_map, on='isin', how='left')
    start_dt, end_dt = df_trans['date'].min(), datetime.today()
    full_idx = pd.date_range(start_dt, end_dt, freq='D').normalize()
    daily_qty_change = df_full.pivot_table(index='date', columns='ticker', values='quantity', aggfunc='sum').fillna(0)
    daily_holdings = daily_qty_change.reindex(full_idx, fill_value=0).cumsum()
    price_matrix = df_prices.pivot(index='date', columns='ticker', values='close_price').reindex(full_idx).ffill()
    common_cols = daily_holdings.columns.intersection(price_matrix.columns)
    daily_value = (daily_holdings[common_cols] * price_matrix[common_cols]).sum(axis=1)
    daily_inv_change = df_full.pivot_table(index='date', values='local_value', aggfunc='sum').fillna(0)
    daily_invested = -daily_inv_change.reindex(full_idx, fill_value=0).cumsum()
    hdf = pd.DataFrame({'Data': full_idx, 'Valore': daily_value, 'Investito': daily_invested['local_value']})
    return hdf