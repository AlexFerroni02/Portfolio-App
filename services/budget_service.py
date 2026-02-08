import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression
from typing import Dict, Tuple

def get_monthly_summary(selected_month: str, df_budget: pd.DataFrame, df_trans: pd.DataFrame = None) -> Dict[str, float]:
    """
    Calcola un riepilogo finanziario per il mese selezionato.
    Gli investimenti sono calcolati dalla categoria 'Investimento' nel budget.
    """
    df_month = df_budget[df_budget['date'].dt.strftime('%Y-%m') == selected_month]

    entrate = df_month[df_month['type'] == 'Entrata']['amount'].sum()
    # Uscite normali (escluso Investimento)
    uscite = df_month[(df_month['type'] == 'Uscita') & (df_month['category'] != 'Investimento')]['amount'].sum()
    risparmio = entrate - uscite
    savings_rate = (risparmio / entrate * 100) if entrate > 0 else 0

    # Investimenti dal budget
    investito_mese = df_month[(df_month['type'] == 'Uscita') & (df_month['category'] == 'Investimento')]['amount'].sum()

    return {
        "entrate": entrate,
        "uscite": uscite,
        "risparmio": risparmio,
        "savings_rate": savings_rate,
        "investito_mese": investito_mese
    }


def get_general_summary(df_budget: pd.DataFrame) -> Dict[str, float]:
    """
    Calcola un riepilogo finanziario generale su tutto il periodo.
    Restituisce totali e medie mensili.
    """
    if df_budget.empty:
        return {k: 0.0 for k in ["totale_entrate", "totale_uscite", "totale_investito", 
                                  "totale_risparmio", "media_entrate", "media_uscite",
                                  "media_investito", "media_risparmio", "num_mesi"]}
    
    # Conta mesi unici
    df_budget['mese'] = df_budget['date'].dt.to_period('M')
    num_mesi = df_budget['mese'].nunique()
    
    # Totali
    totale_entrate = df_budget[df_budget['type'] == 'Entrata']['amount'].sum()
    totale_uscite = df_budget[(df_budget['type'] == 'Uscita') & (df_budget['category'] != 'Investimento')]['amount'].sum()
    totale_investito = df_budget[(df_budget['type'] == 'Uscita') & (df_budget['category'] == 'Investimento')]['amount'].sum()
    totale_risparmio = totale_entrate - totale_uscite - totale_investito
    
    # Medie (se ci sono mesi)
    if num_mesi > 0:
        media_entrate = totale_entrate / num_mesi
        media_uscite = totale_uscite / num_mesi
        media_investito = totale_investito / num_mesi
        media_risparmio = totale_risparmio / num_mesi
    else:
        media_entrate = media_uscite = media_investito = media_risparmio = 0
    
    return {
        "totale_entrate": totale_entrate,
        "totale_uscite": totale_uscite,
        "totale_investito": totale_investito,
        "totale_risparmio": totale_risparmio,
        "media_entrate": media_entrate,
        "media_uscite": media_uscite,
        "media_investito": media_investito,
        "media_risparmio": media_risparmio,
        "num_mesi": num_mesi
    }


def get_category_averages(df_budget: pd.DataFrame) -> pd.DataFrame:
    """
    Calcola la media mensile per ogni categoria di spesa.
    Restituisce un DataFrame ordinato per importo decrescente.
    """
    if df_budget.empty:
        return pd.DataFrame()
    
    df = df_budget.copy()
    df['mese'] = df['date'].dt.to_period('M')
    num_mesi = df['mese'].nunique()
    
    # Solo uscite (incluso investimento)
    df_spese = df[df['type'] == 'Uscita']
    
    if df_spese.empty or num_mesi == 0:
        return pd.DataFrame()
    
    # Totale per categoria
    totali = df_spese.groupby('category')['amount'].sum().reset_index()
    totali['media_mensile'] = totali['amount'] / num_mesi
    totali = totali.sort_values('media_mensile', ascending=False)
    
    return totali


def get_yearly_summary(df_budget: pd.DataFrame) -> pd.DataFrame:
    """
    Calcola il riepilogo per ogni anno disponibile.
    """
    if df_budget.empty:
        return pd.DataFrame()
    
    df = df_budget.copy()
    df['anno'] = df['date'].dt.year
    
    result = []
    for anno in sorted(df['anno'].unique()):
        df_anno = df[df['anno'] == anno]
        entrate = df_anno[df_anno['type'] == 'Entrata']['amount'].sum()
        uscite = df_anno[(df_anno['type'] == 'Uscita') & (df_anno['category'] != 'Investimento')]['amount'].sum()
        investito = df_anno[(df_anno['type'] == 'Uscita') & (df_anno['category'] == 'Investimento')]['amount'].sum()
        risparmio = entrate - uscite - investito
        
        result.append({
            'anno': anno,
            'entrate': entrate,
            'uscite': uscite,
            'investito': investito,
            'risparmio': risparmio
        })
    
    return pd.DataFrame(result)

def calculate_net_worth_trend(df_chart: pd.DataFrame) -> Tuple[pd.DataFrame, LinearRegression]:
    """
    Calcola la linea di trend per il grafico del patrimonio netto.
    """
    if len(df_chart) < 2:
        return pd.DataFrame(), None

    X = np.array([(d - df_chart['date'].min()).days for d in df_chart['date']]).reshape(-1, 1)
    y = df_chart['net_worth'].values
    model = LinearRegression().fit(X, y)
    
    trend_dates = pd.date_range(start=df_chart['date'].min(), end=df_chart['date'].max() + pd.DateOffset(months=6))
    trend_X = np.array([(d - df_chart['date'].min()).days for d in trend_dates]).reshape(-1, 1)
    trend_y = model.predict(trend_X)
    
    df_trend = pd.DataFrame({'date': trend_dates, 'trend': trend_y})
    return df_trend, model

def parse_degiro_csv(file):
    df = pd.read_csv(file)
    cols = ['Quantità', 'Quotazione', 'Valore', 'Costi di transazione', 'Totale']
    for c in cols:
        if c in df.columns:
            df[c] = df[c].astype(str).str.replace(',', '.').apply(pd.to_numeric, errors='coerce').fillna(0)
    if 'Data' in df.columns:
        df['Data'] = pd.to_datetime(df['Data'], format='%d-%m-%Y', errors='coerce').dt.normalize()
    if 'Costi di transazione' in df.columns:
        df['Costi di transazione'] = df['Costi di transazione'].abs()
    return df

def generate_id(row, index):
    d_str = row['Data'].strftime('%Y-%m-%d') if pd.notna(row['Data']) else ""
    raw = f"{index}{d_str}{row.get('Ora','')}{row.get('ISIN','')}{row.get('Quantità','')}{row.get('Valore','')}"
    return hashlib.md5(raw.encode()).hexdigest()