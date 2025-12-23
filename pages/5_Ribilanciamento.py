import streamlit as st
from database.connection import get_data
from services.portfolio_service import calculate_portfolio_view
from services.rebalancing_service import (
    validate_asset_class_allocation,
    build_ticker_targets,
    calculate_rebalancing_operations,
    check_budget_alignment,
    get_portfolio_summary
)
from ui.components import make_sidebar
from ui.rebalancing_components import (
    render_portfolio_summary,
    render_asset_class_inputs,
    render_investment_amount_input,
    render_ticker_distribution,
    render_rebalancing_results
)

st.set_page_config(page_title="Ribilanciamento", page_icon="🔄", layout="wide")
make_sidebar()
st.title("🔄 Ribilanciamento Portafoglio")

# --- 1. Carica dati attuali ---
df_trans = get_data("transactions")
df_map = get_data("mapping")
df_prices = get_data("prices")

assets_view = calculate_portfolio_view(df_trans, df_map, df_prices)
summary = get_portfolio_summary(assets_view)
total_portfolio = summary["total_value"]

# Summary metric
render_portfolio_summary(summary)

# --- 2. Input utente: Asset Class ---
asset_classes = render_asset_class_inputs()

is_valid, error_msg = validate_asset_class_allocation(asset_classes)
if not is_valid:
    st.error(f"❌ {error_msg}")
    st.stop()
else:
    st.success("✅ Percentuali asset class valide!")

# --- 2b. Input capitale ---
invest_amount, new_total = render_investment_amount_input(total_portfolio)

# --- 3. Input utente: Distribuzione per Ticker ---
global_pct_inputs, global_ticker_prices, ticker_to_cat = render_ticker_distribution(
    assets_view, asset_classes
)

# --- 4. Calcola differenze ---
st.header("3️⃣ Calcola Ribilanciamento")

if st.button("Calcola Ribilanciamento"):
    # Build ticker_targets
    ticker_targets = build_ticker_targets(
        global_pct_inputs, ticker_to_cat, asset_classes, new_total
    )
    
    if ticker_targets:
        dettagli, total_cost = calculate_rebalancing_operations(
            ticker_targets, assets_view, global_ticker_prices, 
            ticker_to_cat, total_portfolio, new_total
        )
        
        is_aligned, proposed_budget = check_budget_alignment(total_cost, invest_amount)
        
        render_rebalancing_results(
            dettagli, total_cost, invest_amount, is_aligned, proposed_budget
        )
    else:
        st.warning("⚠️ Nessun target impostato. Verifica le distribuzioni.")
