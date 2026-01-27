import streamlit as st
import pandas as pd
import json
import unicodedata
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
    Salva i dizionari di allocazione come JSON nel DB usando INSERT/UPDATE.
    Normalizza le chiavi in minuscolo per garantire coerenza con COUNTRY_ALIASES_IT.
    Aggiusta automaticamente le percentuali per fare 100% usando la voce "altri".
    """
    conn = get_db_connection()
    
    def normalize_and_adjust(data_dict: Dict[str, float], is_geo: bool = False) -> Dict[str, float]:
        """Normalizza chiavi in minuscolo e aggiusta percentuali a 100%."""
        if not data_dict:
            return {}  # Se vuoto, lascia vuoto
        
        # Normalizza le chiavi: per geo rimuovi accenti, per settori mantieni
        def normalize_key(key: str) -> str:
            if is_geo:
                # Per paesi: rimuovi accenti e caratteri speciali
                normalized = unicodedata.normalize('NFD', key)
                normalized = normalized.encode('ascii', 'ignore').decode('ascii')
                return normalized.lower().strip()
            else:
                # Per settori: mantieni accenti, solo minuscolo e strip
                return key.lower().strip()
        
        normalized = {normalize_key(k): v for k, v in data_dict.items()}
        
        # Calcola la somma delle percentuali
        total = sum(normalized.values())
        
        # Se la somma non è 100, aggiusta usando "altri"
        if abs(total - 100) > 0.01:  # Tolleranza per errori di arrotondamento
            diff = 100 - total
            
            # Se "altri" esiste già, aggiungi/sottrai la differenza
            if "altri" in normalized:
                normalized["altri"] += diff
                # Arrotonda a 2 decimali
                normalized["altri"] = round(normalized["altri"], 2)
                # Se "altri" diventa negativo o troppo piccolo, rimuovilo
                if normalized["altri"] < 0.01:
                    del normalized["altri"]
            else:
                # Se "altri" non esiste, crealo sempre con il valore necessario
                normalized["altri"] = round(diff, 2)
                # Se diventa negativo o troppo piccolo, rimuovilo
                if normalized["altri"] < 0.01:
                    del normalized["altri"]
        
        return normalized
    
    # Normalizza e aggiusta entrambi i dizionari
    geo_dict_normalized = normalize_and_adjust(geo_dict, is_geo=True)
    sec_dict_normalized = normalize_and_adjust(sec_dict, is_geo=False)
    
    geo_json = json.dumps(geo_dict_normalized, ensure_ascii=False)
    sec_json = json.dumps(sec_dict_normalized, ensure_ascii=False)
    
    try:
        with conn.session as s:
            # Prima verifica se esiste già un record per questo mapping_id
            check_query = text("SELECT COUNT(*) as count FROM asset_allocation WHERE mapping_id = :m")
            result = s.execute(check_query, {'m': mapping_id}).fetchone()
            
            if result[0] > 0:
                # UPDATE se esiste
                update_query = text("""
                    UPDATE asset_allocation 
                    SET geography_json = :g, sector_json = :s, last_updated = NOW()
                    WHERE mapping_id = :m
                """)
                s.execute(update_query, {'m': mapping_id, 'g': geo_json, 's': sec_json})
            else:
                # INSERT se non esiste
                insert_query = text("""
                    INSERT INTO asset_allocation (mapping_id, geography_json, sector_json, last_updated)
                    VALUES (:m, :g, :s, NOW())
                """)
                s.execute(insert_query, {'m': mapping_id, 'g': geo_json, 's': sec_json})
            
            s.commit()
        
        st.cache_data.clear()
    except Exception as e:
        st.error(f"Errore salvataggio JSON per mapping_id={mapping_id}: {e}")