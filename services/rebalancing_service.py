import pandas as pd
import yfinance as yf
from typing import Dict, List, Tuple, Optional

def validate_asset_class_allocation(asset_classes: Dict[str, float]) -> Tuple[bool, Optional[str]]:
    """
    Valida che la somma delle percentuali delle asset class sia 100%.
    
    Args:
        asset_classes: Dizionario {categoria: percentuale}
    
    Returns:
        Tuple (is_valid, error_message)
    """
    total = sum(asset_classes.values())
    if abs(total - 100) < 0.01:  # Tolleranza per errori di arrotondamento
        return True, None
    return False, f"La somma deve essere 100%, attualmente è {total:.1f}%"

def validate_ticker_distribution(pct_inputs: Dict[str, float], category: str) -> Tuple[bool, Optional[str]]:
    """
    Valida che la distribuzione dei ticker all'interno di una categoria sia 100%.
    
    Args:
        pct_inputs: Dizionario {ticker: percentuale}
        category: Nome della categoria
    
    Returns:
        Tuple (is_valid, error_message)
    """
    total_pct = sum(pct_inputs.values())
    if abs(total_pct - 100) < 0.01:
        return True, None
    
    if total_pct > 100:
        over = total_pct - 100
        return False, f"La somma delle percentuali per {category} supera 100% di {over:.1f}%."
    else:
        under = 100 - total_pct
        return False, f"La somma delle percentuali per {category} è sotto 100% di {under:.1f}%."

def get_ticker_price(ticker: str) -> Optional[float]:
    """
    Scarica il prezzo corrente di un ticker da Yahoo Finance.
    
    Args:
        ticker: Simbolo del ticker
    
    Returns:
        Prezzo corrente o None se non trovato
    """
    try:
        price_data = yf.Ticker(ticker).history(period='1d')
        if not price_data.empty:
            return float(price_data['Close'].iloc[-1])
        return None
    except Exception:
        return None

def build_ticker_targets(
    global_pct_inputs: Dict[str, float],
    ticker_to_cat: Dict[str, str],
    asset_classes: Dict[str, float],
    new_total: float
) -> Dict[str, float]:
    """
    Costruisce i target in valore assoluto (€) per ogni ticker.
    
    Args:
        global_pct_inputs: {ticker: percentuale_nella_categoria}
        ticker_to_cat: {ticker: categoria}
        asset_classes: {categoria: percentuale_totale}
        new_total: Valore totale del portafoglio dopo investimento
    
    Returns:
        Dizionario {ticker: valore_target_in_euro}
    """
    ticker_targets = {}
    for ticker, pct_ticker in global_pct_inputs.items():
        cat = ticker_to_cat[ticker]
        pct_cat = asset_classes[cat]
        target_pct_total = (pct_cat / 100) * (pct_ticker / 100)
        ticker_targets[ticker] = target_pct_total * new_total
    return ticker_targets

def calculate_rebalancing_operations(
    ticker_targets: Dict[str, float],
    assets_view: pd.DataFrame,
    global_ticker_prices: Dict[str, float],
    ticker_to_cat: Dict[str, str],
    total_portfolio: float,
    new_total: float
) -> Tuple[List[Dict], float]:
    """
    Calcola le operazioni di ribilanciamento necessarie.
    
    Args:
        ticker_targets: {ticker: valore_target_in_euro}
        assets_view: DataFrame con la vista corrente del portafoglio
        global_ticker_prices: {ticker: prezzo_corrente}
        ticker_to_cat: {ticker: categoria}
        total_portfolio: Valore attuale del portafoglio
        new_total: Valore totale dopo investimento
    
    Returns:
        Tuple (lista_operazioni, costo_totale)
    """
    dettagli = []
    total_cost = 0
    
    for ticker, target_val in ticker_targets.items():
        # Trova il valore corrente
        if ticker in assets_view['ticker'].values:
            row = assets_view[assets_view['ticker'] == ticker].iloc[0]
            current_val = row["mkt_val"]
        else:
            current_val = 0
        
        curr_price = global_ticker_prices[ticker]
        diff_eur = target_val - current_val
        
        # Solo se la differenza è significativa (> 1€)
        if abs(diff_eur) > 1:
            n_quote_float = diff_eur / curr_price if curr_price > 0 else 0
            n_quote = round(n_quote_float)  # Arrotonda a intero
            diff_eff = n_quote * curr_price
            operazione = "🟢 Compra" if n_quote > 0 else "🔴 Vendi"
            cat = ticker_to_cat[ticker]
            
            dettagli.append({
                "Ticker": ticker,
                "Categoria": cat,
                "Attuale (€)": current_val,
                "Attuale (%)": (current_val / total_portfolio) * 100 if total_portfolio > 0 else 0,
                "Target (€)": target_val,
                "Target (%)": (target_val / new_total) * 100 if new_total > 0 else 0,
                "Dopo Ribilancio (%)": ((current_val + diff_eff) / new_total) * 100 if new_total > 0 else 0,
                "Da comprare/vendere (€)": diff_eff,
                "Operazione": operazione,
                "Quote": n_quote,
                "Prezzo attuale (€)": curr_price
            })
            total_cost += diff_eff
    
    return dettagli, total_cost

def check_budget_alignment(
    total_cost: float,
    invest_amount: float,
    tolerance: float = 0.05
) -> Tuple[bool, Optional[float]]:
    """
    Controlla se il costo totale delle operazioni è allineato al budget specificato.
    
    Args:
        total_cost: Costo totale delle operazioni
        invest_amount: Budget specificato dall'utente
        tolerance: Tolleranza percentuale (default 5%)
    
    Returns:
        Tuple (is_aligned, proposed_budget)
        - is_aligned: True se il costo è entro la tolleranza
        - proposed_budget: Budget proposto se non allineato, None altrimenti
    """
    if invest_amount == 0:
        # Se budget è 0, controlla che il costo totale sia minimo
        if abs(total_cost) > 100:
            return False, total_cost
        return True, None
    
    deviation = abs(total_cost - invest_amount) / abs(invest_amount)
    if deviation > tolerance:
        proposed_budget = invest_amount + (total_cost - invest_amount)
        return False, proposed_budget
    
    return True, None

def get_portfolio_summary(assets_view: pd.DataFrame) -> Dict[str, float]:
    """
    Calcola le metriche di riepilogo del portafoglio.
    
    Args:
        assets_view: DataFrame con la vista del portafoglio
    
    Returns:
        Dizionario con le metriche
    """
    total_portfolio = assets_view["mkt_val"].sum()
    num_assets = len(assets_view)
    avg_pnl = assets_view["pnl%"].mean() if not assets_view.empty else 0
    
    return {
        "total_value": total_portfolio,
        "num_assets": num_assets,
        "avg_pnl": avg_pnl
    }
