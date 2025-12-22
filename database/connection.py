import streamlit as st
import pandas as pd
import json
from sqlalchemy import text
from typing import Optional, Dict, Any, Union

# --- CONNESSIONE AL DATABASE (NEON/POSTGRESQL) ---
@st.cache_resource
def get_db_connection():
    """
    Stabilisce la connessione al DB usando i secrets di Streamlit.
    Restituisce un oggetto connessione SQL di Streamlit.
    """
    return st.connection("postgresql", type="sql")

# --- LETTURA DATI (CON CACHE STRUTTURALE) ---
@st.cache_data(ttl=600)
def get_data(table_name: str) -> pd.DataFrame:
    """
    Legge un'intera tabella dal database e restituisce un DataFrame.
    Converte automaticamente le colonne 'date' in datetime.
    """
    conn = get_db_connection()
    try:
        # ttl=5 per evitare query troppo frequenti se chiamato in loop, 
        # ma la cache principale è gestita da @st.cache_data
        df = conn.query(f'SELECT * FROM "{table_name}";', ttl=5)
        if not df.empty and 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'])
        return df
    except Exception:
        return pd.DataFrame()

# --- SALVATAGGIO DATI ---
def save_data(df: pd.DataFrame, table_name: str, method: str = 'replace') -> None:
    """
    Salva un DataFrame in una tabella e pulisce la cache globale.
    
    Args:
        df: DataFrame da salvare.
        table_name: Nome della tabella target.
        method: 'replace' o 'append'. Default 'replace'.
    """
    if df.empty:
        return

    conn = get_db_connection()
    try:
        # Assicura che le date siano datetime corretti
        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'])
        
        # Mapping va sempre rimpiazzato per evitare duplicati sporchi
        if table_name == 'mapping': 
            method = 'replace'
            
        df.to_sql(name=table_name, con=conn.engine, if_exists=method, index=False)
        
        # Pulisce la cache di TUTTE le funzioni @st.cache_data.
        st.cache_data.clear()
    except Exception as e:
        st.error(f"Errore durante il salvataggio della tabella '{table_name}': {e}")

def save_allocation_json(mapping_id: int, geo_dict: Dict[str, float], sec_dict: Dict[str, float]) -> None:
    """
    Salva i dizionari di allocazione come JSON nel DB usando UPSERT.
    """
    conn = get_db_connection()
    geo_json = json.dumps(geo_dict, ensure_ascii=False)
    sec_json = json.dumps(sec_dict, ensure_ascii=False)
    
    query = text("""
        INSERT INTO asset_allocation (mapping_id, geography_json, sector_json, last_updated)
        VALUES (:m, :g, :s, NOW())
        ON CONFLICT (mapping_id) DO UPDATE 
        SET geography_json = :g, sector_json = :s, last_updated = NOW();
    """)
    
    try:
        with conn.session as s:
            s.execute(query, {'m': mapping_id, 'g': geo_json, 's': sec_json})
            s.commit()
        
        st.cache_data.clear()
    except Exception as e:
        st.error(f"Errore salvataggio JSON per mapping_id={mapping_id}: {e}")