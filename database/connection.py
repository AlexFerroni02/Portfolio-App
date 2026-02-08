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
        # ttl=0 forza sempre una query fresca; la cache è gestita
        # dal decoratore esterno @st.cache_data(ttl=600)
        df = conn.query(f'SELECT * FROM "{table_name}";', ttl=0)
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
            
        df.to_sql(name=table_name, con=conn.engine, if_exists=method, index=False)
        
        # Pulisce la cache di TUTTE le funzioni @st.cache_data.
        st.cache_data.clear()
    except Exception as e:
        st.error(f"Errore durante il salvataggio della tabella '{table_name}': {e}")

def insert_single_mapping(isin: str, ticker: str, category: str, proxy_ticker: Optional[str] = None) -> Optional[int]:
    """
    Inserisce una singola riga nella tabella mapping usando SQL diretto.
    Ritorna il mapping_id generato (SERIAL), o None in caso di errore/duplicato.
    NON tocca le righe esistenti.
    """
    conn = get_db_connection()
    try:
        with conn.session as s:
            result = s.execute(
                text(
                    "INSERT INTO mapping (isin, ticker, category, proxy_ticker) "
                    "VALUES (:isin, :ticker, :category, :proxy) "
                    "ON CONFLICT (isin) DO UPDATE SET "
                    "  ticker = EXCLUDED.ticker, "
                    "  category = EXCLUDED.category, "
                    "  proxy_ticker = EXCLUDED.proxy_ticker "
                    "RETURNING id"
                ),
                {'isin': isin, 'ticker': ticker, 'category': category, 'proxy': proxy_ticker},
            )
            row = result.fetchone()
            s.commit()
        st.cache_data.clear()
        return row[0] if row else None
    except Exception as e:
        st.error(f"Errore inserimento mappatura per ISIN={isin}: {e}")
        return None


def insert_single_transaction(tx_dict: dict) -> bool:
    """
    Inserisce una singola transazione con SQL diretto.
    Usa ON CONFLICT per evitare duplicati sull'id (TEXT PRIMARY KEY).
    """
    conn = get_db_connection()
    try:
        with conn.session as s:
            s.execute(
                text(
                    "INSERT INTO transactions (id, date, product, isin, quantity, local_value, fees, currency) "
                    "VALUES (:id, :date, :product, :isin, :quantity, :local_value, :fees, :currency) "
                    "ON CONFLICT (id) DO NOTHING"
                ),
                tx_dict,
            )
            s.commit()
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"Errore inserimento transazione: {e}")
        return False


def update_transaction(tx_id: str, updates: dict) -> bool:
    """
    Aggiorna i campi di una transazione esistente.
    `updates` è un dict con solo i campi da aggiornare (es. {'quantity': 10, 'local_value': -500}).
    """
    allowed = {'date', 'product', 'isin', 'quantity', 'local_value', 'fees', 'currency'}
    updates = {k: v for k, v in updates.items() if k in allowed}
    if not updates:
        return False
    conn = get_db_connection()
    try:
        set_clause = ", ".join(f"{k} = :{k}" for k in updates)
        params = {**updates, 'tx_id': tx_id}
        with conn.session as s:
            s.execute(text(f"UPDATE transactions SET {set_clause} WHERE id = :tx_id"), params)
            s.commit()
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"Errore aggiornamento transazione: {e}")
        return False


def delete_transactions(tx_ids: list) -> int:
    """
    Elimina una o più transazioni per ID.
    Ritorna il numero di righe eliminate.
    Sicuro: transactions non ha foreign key che puntano ad essa.
    """
    if not tx_ids:
        return 0
    conn = get_db_connection()
    try:
        with conn.session as s:
            result = s.execute(
                text("DELETE FROM transactions WHERE id = ANY(:ids)"),
                {'ids': list(tx_ids)}
            )
            s.commit()
        st.cache_data.clear()
        return result.rowcount
    except Exception as e:
        st.error(f"Errore eliminazione transazioni: {e}")
        return 0


def replace_all_mappings(df: pd.DataFrame) -> bool:
    """
    Aggiorna la tabella mapping usando UPSERT + DELETE degli ISIN rimossi.
    PRESERVA gli ID esistenti per non rompere i riferimenti in prices/asset_allocation.
    """
    if df.empty:
        return False
    conn = get_db_connection()
    try:
        with conn.session as s:
            # 1. Raccogli gli ISIN nel nuovo DataFrame
            new_isins = set(df['isin'].dropna().str.strip().tolist())
            new_isins.discard('')

            # 2. Elimina solo le righe il cui ISIN NON è più presente
            if new_isins:
                s.execute(
                    text("DELETE FROM mapping WHERE isin NOT IN :isins"),
                    {'isins': tuple(new_isins)}
                )
            else:
                s.execute(text("DELETE FROM mapping"))

            # 3. UPSERT: inserisci nuovi o aggiorna ticker/category per esistenti
            for _, row in df.iterrows():
                isin = str(row.get('isin', '')).strip()
                if not isin:
                    continue
                s.execute(
                    text(
                        "INSERT INTO mapping (isin, ticker, category, proxy_ticker) "
                        "VALUES (:isin, :ticker, :category, :proxy) "
                        "ON CONFLICT (isin) DO UPDATE SET "
                        "  ticker = EXCLUDED.ticker, "
                        "  category = EXCLUDED.category, "
                        "  proxy_ticker = EXCLUDED.proxy_ticker"
                    ),
                    {
                        'isin': isin,
                        'ticker': str(row.get('ticker', '')).strip(),
                        'category': str(row.get('category', '')).strip(),
                        'proxy': row.get('proxy_ticker') if pd.notna(row.get('proxy_ticker')) else None,
                    },
                )
            s.commit()
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"Errore sostituzione mappatura: {e}")
        return False


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