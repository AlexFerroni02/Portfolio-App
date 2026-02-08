import streamlit as st
import pandas as pd

# Importazioni modularizzate
from database.connection import get_data, save_data, insert_single_mapping
from services.portfolio_service import calculate_portfolio_view, calculate_liquidity, get_historical_portfolio
from ui.components import make_sidebar
from ui.dashboard_components import render_kpis, render_composition_tabs, render_assets_table, render_historical_chart

st.set_page_config(page_title="Portfolio Pro", layout="wide", page_icon="🚀")
make_sidebar()
st.title("🚀 Dashboard Portafoglio")

@st.cache_data(show_spinner="Caricamento dati...")
def load_all_data():
    """Carica tutti i dataframe necessari in un'unica funzione con cache."""
    return {
        "transactions": get_data("transactions"),
        "mapping": get_data("mapping"),
        "prices": get_data("prices"),
        "budget": get_data("budget"),
        "asset_allocation": get_data("asset_allocation")
    }

data = load_all_data()

df_trans, df_map, df_prices, df_budget, df_alloc = data.values()
if df_trans.empty:
    st.info("👋 Benvenuto! Il database è vuoto. Vai su 'Gestione Dati' per importare il CSV.")
    st.stop()

# Calcola solo gli ISIN attualmente posseduti (quantità > 0)
# Gli asset venduti mantengono la mappatura esistente ma non richiedono nuove mappature
if not df_trans.empty:
    holdings = df_trans.groupby('isin')['quantity'].sum()
    held_isins = holdings[holdings > 0].index.tolist()
else:
    held_isins = []
mapped_isins = df_map['isin'].unique() if not df_map.empty else []
missing_isins = [i for i in held_isins if i not in mapped_isins]
if missing_isins:
    st.warning(f"⚠️ Ci sono {len(missing_isins)} nuovi asset da mappare!")
    with st.form("quick_mapping_form"):
        new_mappings = []
        CATEGORIE_ASSET = ["Azionario", "Obbligazionario", "Gold", "Liquidità"]
        for isin in missing_isins:
            prod_name = df_trans[df_trans['isin'] == isin]['product'].iloc[0]
            st.write(f"**{prod_name}** ({isin})")
            col1, col2 = st.columns(2)
            ticker_input = col1.text_input("Ticker Yahoo", key=f"ticker_{isin}", placeholder="es. SWDA.MI")
            category_input = col2.selectbox("Categoria", CATEGORIE_ASSET, key=f"cat_{isin}")
            if ticker_input and category_input:
                new_mappings.append({'isin': isin, 'ticker': ticker_input.strip(), 'category': category_input})
        if st.form_submit_button("💾 Salva e Aggiorna"):
            if new_mappings:
                saved = 0
                for m in new_mappings:
                    result = insert_single_mapping(
                        isin=m['isin'], ticker=m['ticker'], category=m['category']
                    )
                    if result is not None:
                        saved += 1
                if saved > 0:
                    st.success(f"Mappatura salvata ({saved} asset)! Ricarico la pagina...")
                    st.rerun()
                else:
                    st.error("Nessuna mappatura salvata. Verifica i dati inseriti.")
    st.stop() 

# --- CALCOLI PRINCIPALI ---
with st.spinner("Calcolo indicatori..."):
    # 1. Calcola la vista degli ASSET (senza liquidità) per i KPI.
    assets_view = calculate_portfolio_view(df_trans, df_map, df_prices)
    
    # 2. Calcola la liquidità separatamente.
    final_liquidity, liquidity_label = calculate_liquidity(df_budget, df_trans)
    
    # 3. Calcola lo storico.
    hdf = get_historical_portfolio(df_trans, df_map, df_prices)

# 4. Crea una vista COMPLETA (full_view) per i grafici, aggiungendo la liquidità.
full_view = assets_view.copy()
if final_liquidity > 0:
    liquidita_row = pd.DataFrame([{'product': liquidity_label, 'ticker': 'CASH', 'category': 'Liquidità', 'quantity': 1, 'local_value': 0, 'net_invested': final_liquidity, 'curr_price': final_liquidity, 'mkt_val': final_liquidity, 'pnl': 0, 'pnl%': 0}])
    full_view = pd.concat([full_view, liquidita_row], ignore_index=True)

# --- RENDERIZZAZIONE COMPONENTI UI ---
render_kpis(assets_view)
render_composition_tabs(full_view, df_alloc)
render_historical_chart(hdf)
render_assets_table(full_view)
