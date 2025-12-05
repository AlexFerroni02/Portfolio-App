import streamlit as st
from ui.components import make_sidebar
from database.connection import get_data
from ui.data_management_components import (
    render_import_tab,
    render_mapping_tab,
    render_prices_tab,
    render_budget_tab,
    render_allocation_tab,
    render_net_worth_tab
)

st.set_page_config(page_title="Gestione Dati", page_icon="📂", layout="wide")
make_sidebar()
st.title("📂 Gestione Database")

# Inizializzazione session_state per evitare errori al primo avvio
if 'scraped_data' not in st.session_state:
    st.session_state.scraped_data = None
if 'calculated_snapshot' not in st.session_state:
    st.session_state.calculated_snapshot = None

# Caricamento preliminare per controllo saldo iniziale
df_budget_check = get_data("budget")
initial_balance_exists = not df_budget_check.empty and not df_budget_check[df_budget_check['category'] == 'Saldo Iniziale'].empty

# Definizione dei Tab
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "📥 Importa CSV", 
    "🔗 Mappatura Ticker", 
    "🔄 Aggiorna Prezzi", 
    "💸 Movimenti Bilancio", 
    "🔬 Allocazione Asset (X-Ray)", 
    "🎯 Patrimonio Netto"
])

with tab1:
    render_import_tab()

with tab2:
    render_mapping_tab()

with tab3:
    render_prices_tab()

with tab4:
    render_budget_tab(initial_balance_exists)

with tab5:
    render_allocation_tab()

with tab6:
    render_net_worth_tab()