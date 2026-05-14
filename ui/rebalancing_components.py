import streamlit as st
import pandas as pd
from typing import Dict, List
from services.rebalancing_service import (
    calculate_percentage_gap,
    validate_ticker_distribution,
    get_ticker_price
)

def render_portfolio_summary(summary: Dict[str, float]):
    """
    Renderizza le metriche di riepilogo del portafoglio.
    """
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("💰 Valore Portafoglio", f"€{summary['total_value']:,.2f}")
    with col2:
        st.metric("📊 Asset Posseduti", summary['num_assets'])
    with col3:
        avg_pnl = summary['avg_pnl']
        st.metric("📈 P&L Medio", f"{avg_pnl:.1f}%", delta=f"{avg_pnl:.1f}%" if avg_pnl != 0 else None)

def render_asset_class_inputs() -> Dict[str, float]:
    """
    Renderizza gli input per le percentuali delle asset class.
    
    Returns:
        Dizionario {categoria: percentuale}
    """
    st.header("1️⃣ Imposta percentuali per Asset Class")
    st.caption("La somma deve essere 100%")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        pct_az = st.number_input("📈 Azionario (%)", min_value=0, max_value=100, value=70)
    with col2:
        pct_ob = st.number_input("💼 Obbligazionario (%)", min_value=0, max_value=100, value=20)
    with col3:
        pct_gold = st.number_input("🪙 Gold (%)", min_value=0, max_value=100, value=10)
    
    return {
        "Azionario": pct_az,
        "Obbligazionario": pct_ob,
        "Gold": pct_gold
    }

def render_investment_amount_input(total_portfolio: float) -> tuple[float, float]:
    """
    Renderizza l'input per il capitale da investire/disinvestire.
    
    Args:
        total_portfolio: Valore attuale del portafoglio
    
    Returns:
        Tuple (invest_amount, new_total)
    """
    st.header("1️⃣ Imposta Capitale da Investire/Disinvestire")
    invest_amount = st.number_input(
        "💰 Capitale (€)", 
        value=0.0, 
        step=100.0, 
        format="%.2f", 
        help="Valore positivo per investimento, negativo per disinvestimento."
    )
    new_total = total_portfolio + invest_amount
    return invest_amount, new_total

def render_ticker_distribution(
    assets_view: pd.DataFrame,
    asset_classes: Dict[str, float]
) -> tuple[Dict[str, float], Dict[str, float], Dict[str, str], Dict[str, str]]:
    """
    Renderizza gli expander per distribuire le percentuali tra i ticker di ogni categoria.
    
    Args:
        assets_view: DataFrame con la vista del portafoglio
        asset_classes: Dizionario {categoria: percentuale}
    
    Returns:
        Tuple (global_pct_inputs, global_ticker_prices, ticker_to_cat, invalid_categories)
    """
    st.header("2️⃣ Distribuisci all'interno di ogni Asset Class")
    
    global_pct_inputs = {}
    global_ticker_prices = {}
    ticker_to_cat = {}
    invalid_categories = {}
    
    for cat, pct_cat in asset_classes.items():
        if pct_cat > 0:
            emoji_cat = {"Azionario": "📈", "Obbligazionario": "💼", "Gold": "🪙"}.get(cat, "📊")
            
            with st.expander(f"{emoji_cat} {cat} ({pct_cat}%) - Distribuisci tra i ticker"):
                tickers_cat = assets_view[assets_view["category"] == cat]
                
                if tickers_cat.empty:
                    st.info(f"ℹ️ Nessun asset in {cat}.")
                    continue
                
                # Inizializza session_state per questa categoria
                _initialize_category_session_state(cat, tickers_cat)
                _sync_category_session_state(cat, tickers_cat)
                
                pct_inputs = st.session_state[f"pct_inputs_{cat}"]
                ticker_prices = st.session_state[f"ticker_prices_{cat}"]
                new_tickers = st.session_state[f"new_tickers_{cat}"]
                
                # Renderizza i ticker esistenti
                _render_existing_tickers(cat, pct_inputs, ticker_prices, new_tickers, assets_view)
                
                # Sezione per aggiungere nuovi ticker
                _render_add_ticker_section(cat, pct_inputs, ticker_prices, new_tickers)

                # Mostra quanto manca/sfora per arrivare al 100%
                gap = calculate_percentage_gap(pct_inputs)
                _render_distribution_gap(cat, gap)
                
                # Valida la distribuzione
                is_valid, error_msg = validate_ticker_distribution(pct_inputs, cat)
                if not is_valid:
                    invalid_categories[cat] = error_msg
                    st.error(f"❌ {error_msg}")
                    continue
                else:
                    st.success(f"✅ Distribuzione {cat} valida!")
                
                # Aggiungi a global
                for ticker, pct in pct_inputs.items():
                    global_pct_inputs[ticker] = pct
                    global_ticker_prices[ticker] = ticker_prices[ticker]
                    ticker_to_cat[ticker] = cat
    
    return global_pct_inputs, global_ticker_prices, ticker_to_cat, invalid_categories


def _normalize_ticker_code(ticker: str) -> str:
    """Normalizza il ticker per evitare duplicati dovuti a maiuscole/spazi."""
    return str(ticker).strip().upper()


def _render_distribution_gap(category: str, gap: float):
    """Mostra lo scostamento dal 100% per una categoria."""
    if abs(gap) <= 0.1:
        st.caption(f"✅ {category}: somma allineata al 100%")
        return

    if gap > 0:
        st.caption(f"⚠️ {category}: mancano {gap:.2f}% per arrivare al 100%")
        return

    st.caption(f"⚠️ {category}: superi il 100% di {abs(gap):.2f}%")

def _initialize_category_session_state(cat: str, tickers_cat: pd.DataFrame):
    """Inizializza lo stato della sessione per una categoria."""
    tickers = [_normalize_ticker_code(t) for t in tickers_cat["ticker"].dropna().tolist()]
    default_pct = 100.0 / len(tickers) if tickers else 0.0
    ticker_prices = {
        _normalize_ticker_code(row["ticker"]): float(row.get("curr_price", 0) or 0)
        for _, row in tickers_cat.iterrows()
    }

    if f"pct_inputs_{cat}" not in st.session_state:
        st.session_state[f"pct_inputs_{cat}"] = {
            ticker: default_pct for ticker in tickers
        }
    if f"ticker_prices_{cat}" not in st.session_state:
        st.session_state[f"ticker_prices_{cat}"] = ticker_prices
    if f"new_tickers_{cat}" not in st.session_state:
        st.session_state[f"new_tickers_{cat}"] = []


def _sync_category_session_state(cat: str, tickers_cat: pd.DataFrame):
    """Mantiene coerente lo stato sessione con ticker correnti e ticker aggiunti."""
    pct_key = f"pct_inputs_{cat}"
    price_key = f"ticker_prices_{cat}"
    new_key = f"new_tickers_{cat}"

    pct_inputs = st.session_state.get(pct_key, {})
    ticker_prices = st.session_state.get(price_key, {})
    new_tickers = st.session_state.get(new_key, [])

    existing_prices = {
        _normalize_ticker_code(row["ticker"]): float(row.get("curr_price", 0) or 0)
        for _, row in tickers_cat.iterrows()
    }
    existing_tickers = set(existing_prices.keys())

    normalized_new_tickers = [_normalize_ticker_code(t) for t in new_tickers]
    normalized_new_tickers = [t for t in normalized_new_tickers if t and t not in existing_tickers]
    valid_tickers = existing_tickers | set(normalized_new_tickers)

    normalized_pct_inputs = {}
    for ticker, value in pct_inputs.items():
        normalized_ticker = _normalize_ticker_code(ticker)
        if normalized_ticker not in valid_tickers:
            continue
        try:
            normalized_pct_inputs[normalized_ticker] = float(value)
        except (TypeError, ValueError):
            normalized_pct_inputs[normalized_ticker] = 0.0

    normalized_ticker_prices = {}
    for ticker, value in ticker_prices.items():
        normalized_ticker = _normalize_ticker_code(ticker)
        if normalized_ticker not in valid_tickers:
            continue
        try:
            normalized_ticker_prices[normalized_ticker] = float(value)
        except (TypeError, ValueError):
            normalized_ticker_prices[normalized_ticker] = 0.0

    pct_inputs = normalized_pct_inputs
    ticker_prices = normalized_ticker_prices

    for ticker, price in existing_prices.items():
        pct_inputs.setdefault(ticker, 0.0)
        ticker_prices[ticker] = price
    for ticker in normalized_new_tickers:
        pct_inputs.setdefault(ticker, 0.0)
        ticker_prices.setdefault(ticker, 0.0)

    st.session_state[pct_key] = pct_inputs
    st.session_state[price_key] = ticker_prices
    st.session_state[new_key] = normalized_new_tickers

def _render_existing_tickers(
    cat: str,
    pct_inputs: Dict[str, float],
    ticker_prices: Dict[str, float],
    new_tickers: List[str],
    assets_view: pd.DataFrame
):
    """Renderizza i ticker esistenti con i loro input."""
    st.caption(f"Distribuisci il 100% della categoria {cat} tra i seguenti ticker:")
    owned_tickers = {
        _normalize_ticker_code(ticker)
        for ticker in assets_view["ticker"].dropna().tolist()
    }
    
    for ticker in list(pct_inputs.keys()):
        col_t, col_p, col_r = st.columns([2, 1, 1])
        
        with col_t:
            if ticker in new_tickers:
                st.markdown(f"<center><i><b>{ticker} (nuovo)</b></i></center>", unsafe_allow_html=True)
            else:
                st.markdown(f"<center><b>{ticker}</b></center>", unsafe_allow_html=True)
        
        with col_p:
            pct_inputs[ticker] = st.number_input(
                label=f"Pct {ticker}",
                min_value=0.0, 
                max_value=100.0, 
                value=pct_inputs[ticker], 
                step=1.0,
                key=f"{cat}_{ticker}",
                label_visibility="collapsed"
            )
        
        with col_r:
            # Permetti rimozione solo per ticker non presenti nel portafoglio
            if ticker not in owned_tickers:
                if st.button(f"Rimuovi {ticker}", key=f"remove_{cat}_{ticker}"):
                    del pct_inputs[ticker]
                    del ticker_prices[ticker]
                    new_tickers.remove(ticker)
                    st.session_state[f"new_tickers_{cat}"] = new_tickers
                    st.session_state[f"pct_inputs_{cat}"] = pct_inputs
                    st.session_state[f"ticker_prices_{cat}"] = ticker_prices
                    st.rerun()

def _render_add_ticker_section(
    cat: str,
    pct_inputs: Dict[str, float],
    ticker_prices: Dict[str, float],
    new_tickers: List[str]
):
    """Renderizza la sezione per aggiungere nuovi ticker."""
    st.subheader(f"➕ Aggiungi Nuovo Ticker per {cat}")
    
    col_add_t, col_add_b = st.columns([3, 1])
    
    with col_add_t:
        new_ticker_raw = st.text_input(
            f"Nuovo Ticker", 
            key=f"new_ticker_input_{cat}", 
            placeholder="Es: AAPL"
        )
        new_ticker = _normalize_ticker_code(new_ticker_raw)
    
    with col_add_b:
        if st.button(f"Aggiungi", key=f"add_{cat}"):
            if new_ticker:
                if new_ticker not in pct_inputs:
                    with st.spinner(f"Scarico prezzo per {new_ticker}..."):
                        new_price = get_ticker_price(new_ticker)
                        
                        if new_price is not None:
                            pct_inputs[new_ticker] = 0.0
                            ticker_prices[new_ticker] = new_price
                            new_tickers.append(new_ticker)
                            st.session_state[f"pct_inputs_{cat}"] = pct_inputs
                            st.session_state[f"ticker_prices_{cat}"] = ticker_prices
                            st.session_state[f"new_tickers_{cat}"] = new_tickers
                            st.session_state[f"new_ticker_input_{cat}"] = ""
                            st.success(f"Aggiunto {new_ticker} con 0% - Prezzo: €{new_price:.2f}")
                            st.rerun()
                        else:
                            st.error(f"Prezzo non trovato per {new_ticker}")
                else:
                    st.warning(f"{new_ticker} già presente.")
            else:
                st.warning("Inserisci un ticker valido.")

def render_rebalancing_results(
    dettagli: List[Dict],
    total_cost: float,
    invest_amount: float,
    is_aligned: bool,
    proposed_budget: float = None
):
    """
    Renderizza i risultati del ribilanciamento.
    
    Args:
        dettagli: Lista di operazioni
        total_cost: Costo totale delle operazioni
        invest_amount: Budget specificato
        is_aligned: Se il budget è allineato
        proposed_budget: Budget proposto se non allineato
    """
    if not is_aligned and proposed_budget is not None:
        st.warning(
            f"⚠️ Il costo totale delle operazioni (€{total_cost:,.2f}) differisce dal budget "
            f"specificato (€{invest_amount:,.2f}). Budget proposto: €{proposed_budget:,.2f}"
        )
    else:
        st.success("✅ Budget allineato con le operazioni!")
    
    if dettagli:
        df_dettagli = pd.DataFrame(dettagli)
        st.dataframe(
            df_dettagli[[
                "Ticker", "Categoria", "Attuale (€)", "Attuale (%)", 
                "Target (€)", "Target (%)", "Dopo Ribilancio (%)", 
                "Da comprare/vendere (€)", "Operazione", "Quote", "Prezzo attuale (€)"
            ]].style.format({
                "Attuale (€)": "€ {:.2f}",
                "Attuale (%)": "{:.2f}%",
                "Target (€)": "€ {:.2f}",
                "Target (%)": "{:.2f}%",
                "Dopo Ribilancio (%)": "{:.2f}%",
                "Da comprare/vendere (€)": "€ {:.2f}",
                "Quote": "{:.0f}",
                "Prezzo attuale (€)": "€ {:.2f}"
            }).apply(
                lambda x: [
                    'background-color: #28a745; color: white' if 'Compra' in str(val) 
                    else 'background-color: #dc3545; color: white' if 'Vendi' in str(val) 
                    else '' 
                    for val in x
                ], 
                subset=['Operazione']
            )
        )
        
        # Summary costi
        st.subheader("💰 Riepilogo Costi")
        col_bud, col_cost, col_diff = st.columns(3)
        with col_bud:
            st.metric("Budget Specificato", f"€{invest_amount:,.2f}")
        with col_cost:
            st.metric("Costo Totale Operazioni", f"€{total_cost:,.2f}")
        with col_diff:
            diff_budget = total_cost - invest_amount
            st.metric(
                "Differenza", 
                f"€{diff_budget:,.2f}", 
                delta=f"€{diff_budget:,.2f}" if diff_budget != 0 else None
            )
        
        st.info("💡 **Compra** = valori positivi (aggiungi al portafoglio); **Vendi** = valori negativi (riduci posizione).")
    else:
        st.success("🎉 Il portafoglio è già allineato ai target!")
