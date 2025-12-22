import pandas as pd
import json
from typing import Dict, Any

def get_owned_assets(df_trans: pd.DataFrame, df_map: pd.DataFrame) -> pd.DataFrame:
    """
    Restituisce un DataFrame con gli asset attualmente posseduti (quantità > 0).
    """
    if df_trans.empty or df_map.empty:
        return pd.DataFrame()
    
    df_full = df_trans.merge(df_map, on='isin', how='left', suffixes=('_trans', '_map'))
    # Rinomina id_map in mapping_id solo se serve
    if 'mapping_id' not in df_full.columns and 'id_map' in df_full.columns:
        df_full = df_full.rename(columns={'id_map': 'mapping_id'})
    if 'mapping_id' not in df_full.columns:
        df_full['mapping_id'] = pd.NA

    holdings = df_full.groupby(['product', 'mapping_id', 'isin']).agg(quantity=('quantity', 'sum')).reset_index()
    owned_assets = holdings[holdings['quantity'] > 0.001].copy()
    # Aggiungi il ticker per visualizzazione
    owned_assets = owned_assets.merge(df_map[['id', 'ticker']], left_on='mapping_id', right_on='id', how='left')
    return owned_assets

def get_asset_kpis(mapping_id: int, owned_assets: pd.DataFrame, df_asset_trans: pd.DataFrame, asset_prices: pd.DataFrame, df_map: pd.DataFrame) -> Dict[str, Any]:
    """
    Calcola i KPI principali per un singolo asset.
    """
    if owned_assets.empty or df_asset_trans.empty:
        return {}
    asset_info = owned_assets[owned_assets['mapping_id'] == mapping_id].iloc[0]
    qty = asset_info['quantity']
    invested = -df_asset_trans['local_value'].sum()
    last_price = asset_prices.iloc[-1]['close_price'] if not asset_prices.empty else 0
    curr_val = qty * last_price
    pnl = curr_val - invested
    map_row = df_map[df_map['id'] == mapping_id].iloc[0] if not df_map.empty else {}
    ticker = map_row['ticker'] if 'ticker' in map_row else None
    product_name = asset_info['product']
    return {
        "quantity": qty,
        "last_price": last_price,
        "market_value": curr_val,
        "pnl": pnl,
        "pnl_perc": (pnl / invested) * 100 if invested else 0,
        "product_name": product_name,
        "isin": asset_info['isin'],
        "ticker": ticker
    }

def get_asset_allocation_data(mapping_id: int, df_alloc: pd.DataFrame) -> tuple[dict, dict]:
    """
    Estrae e decodifica i dati di allocazione geografica e settoriale per un asset.
    """
    geo_data, sec_data = {}, {}
    if df_alloc.empty:
        return geo_data, sec_data
    asset_alloc_data = df_alloc[df_alloc['mapping_id'] == mapping_id]
    if not asset_alloc_data.empty:
        geo_raw = asset_alloc_data.iloc[0].get('geography_json', '{}')
        sec_raw = asset_alloc_data.iloc[0].get('sector_json', '{}')
        try:
            geo_data = geo_raw if isinstance(geo_raw, dict) else json.loads(geo_raw or '{}')
            sec_data = sec_raw if isinstance(sec_raw, dict) else json.loads(sec_raw or '{}')
        except (json.JSONDecodeError, TypeError):
            pass
    return geo_data, sec_data