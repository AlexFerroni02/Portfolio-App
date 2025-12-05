import pandas as pd
from utils import parse_degiro_csv, generate_id
from services.portfolio_service import calculate_liquidity

def process_new_transactions(file: "UploadedFile", existing_transactions: pd.DataFrame) -> pd.DataFrame:
    """
    Elabora un file CSV di transazioni, lo confronta con quelle esistenti e restituisce solo le nuove.
    """
    ndf = parse_degiro_csv(file)
    rows_to_add = []
    existing_ids = set(existing_transactions['id']) if not existing_transactions.empty else set()
    
    for idx, r in ndf.iterrows():
        if pd.isna(r.get('ISIN')): continue
        tid = generate_id(r, idx)
        if tid not in existing_ids:
            val = r.get('Totale', 0) if r.get('Totale', 0) != 0 else r.get('Valore', 0)
            rows_to_add.append({
                'id': tid, 
                'date': r['Data'], 
                'product': r.get('Prodotto',''), 
                'isin': r.get('ISIN',''), 
                'quantity': r.get('Quantità',0), 
                'local_value': val, 
                'fees': r.get('Costi di transazione',0), 
                'currency': 'EUR'
            })
            existing_ids.add(tid)
            
    return pd.DataFrame(rows_to_add)

def calculate_net_worth_snapshot(snapshot_date: pd.Timestamp, df_trans: pd.DataFrame, df_map: pd.DataFrame, df_prices: pd.DataFrame, df_budget: pd.DataFrame) -> tuple[float, float, float]:
    """
    Calcola il valore degli asset, la liquidità e il patrimonio netto totale a una data specifica.
    Replica la logica complessa della pagina Gestione Dati.
    """
    # Normalizza le date per confronti sicuri
    if not df_trans.empty: df_trans['date'] = pd.to_datetime(df_trans['date']).dt.normalize()
    if not df_prices.empty: df_prices['date'] = pd.to_datetime(df_prices['date']).dt.normalize()
    if not df_budget.empty: df_budget['date'] = pd.to_datetime(df_budget['date']).dt.normalize()

    net_worth_at_date, total_assets_value, final_liquidity = 0, 0, 0

    # Filtra tutti i dati fino alla data dello snapshot
    trans_at_date = df_trans[df_trans['date'] <= snapshot_date] if not df_trans.empty else pd.DataFrame()
    prices_at_date = df_prices[df_prices['date'] <= snapshot_date] if not df_prices.empty else pd.DataFrame()
    budget_at_date = df_budget[df_budget['date'] <= snapshot_date] if not df_budget.empty else pd.DataFrame()

    # 1. Calcolo Valore Asset alla data
    if not trans_at_date.empty and not df_map.empty and not prices_at_date.empty:
        df_full_nw = trans_at_date.merge(df_map, on='isin', how='left')
        last_prices_at_date = prices_at_date.sort_values('date').groupby('ticker').tail(1).set_index('ticker')['close_price']
        view_nw = df_full_nw.groupby('ticker')['quantity'].sum().reset_index()
        view_nw['mkt_val'] = view_nw['quantity'] * view_nw['ticker'].map(last_prices_at_date).fillna(0)
        total_assets_value = view_nw['mkt_val'].sum()

    # 2. Calcolo Liquidità alla data (usando la funzione di servizio già esistente)
    final_liquidity, _ = calculate_liquidity(budget_at_date, trans_at_date)

    # 3. Calcolo Patrimonio Netto
    net_worth_at_date = total_assets_value + final_liquidity
    
    return net_worth_at_date, total_assets_value, final_liquidity