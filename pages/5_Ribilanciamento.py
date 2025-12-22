import streamlit as st
import pandas as pd
from database.connection import get_data
from services.portfolio_service import calculate_portfolio_view, calculate_liquidity
from ui.components import make_sidebar

st.set_page_config(page_title="Ribilanciamento", page_icon="🔄", layout="wide")
make_sidebar()
st.title("🔄 Ribilanciamento Portafoglio")

# --- 1. Carica dati attuali ---
df_trans = get_data("transactions")
df_map = get_data("mapping")
df_prices = get_data("prices")
df_budget = get_data("budget")

assets_view = calculate_portfolio_view(df_trans, df_map, df_prices)
final_liquidity, _ = calculate_liquidity(df_budget, df_trans)

# --- 2. Input utente ---
st.header("Imposta i tuoi obiettivi di allocazione")
col1, col2 = st.columns(2)
with col1:
    invest_amount = st.number_input("Capitale da investire/disinvestire (€)", value=0.0, step=100.0, format="%.2f")
with col2:
    st.caption("Inserisci le percentuali target per ciascuna asset class (la somma deve essere 100%)")
    pct_az = st.number_input("Azionario (%)", min_value=0, max_value=100, value=50)
    pct_ob = st.number_input("Obbligazionario (%)", min_value=0, max_value=100, value=30)
    pct_gold = st.number_input("Gold (%)", min_value=0, max_value=100, value=10)
    pct_cash = st.number_input("Liquidità (%)", min_value=0, max_value=100, value=10)

target_pct = {
    "Azionario": pct_az,
    "Obbligazionario": pct_ob,
    "Gold": pct_gold,
    "Liquidità": pct_cash
}
if sum(target_pct.values()) != 100:
    st.error("La somma delle percentuali deve essere 100%.")
    st.stop()

# --- 3. Calcola situazione attuale ---
current_alloc = assets_view.groupby("category")["mkt_val"].sum().to_dict()
current_alloc["Liquidità"] = final_liquidity
total_now = sum(current_alloc.values())
total_new = total_now + invest_amount

# --- 4. Calcola target e differenze ---
target_eur = {k: total_new * v / 100 for k, v in target_pct.items()}
diff = {k: target_eur.get(k, 0) - current_alloc.get(k, 0) for k in target_pct}

# --- 5. Mostra risultati ---
st.subheader("Situazione attuale e suggerimenti di ribilanciamento")
df_out = pd.DataFrame({
    "Attuale (€)": [current_alloc.get(k, 0) for k in target_pct],
    "Target (€)": [target_eur[k] for k in target_pct],
    "Da comprare/vendere (€)": [diff[k] for k in target_pct]
}, index=target_pct.keys())
st.dataframe(df_out.style.format("€ {:.2f}"))

st.info("Valori positivi = comprare; valori negativi = vendere/disinvestire. Puoi dettagliare la logica per singolo ETF/asset se vuoi.")

# --- 6. Dettaglio operazioni per ETF posseduti ---
st.subheader("Dettaglio operazioni suggerite per ETF posseduti")

dettagli = []
for cat in ["Azionario", "Obbligazionario", "Gold"]:
    etf_cat = assets_view[assets_view["category"] == cat]
    totale_cat = etf_cat["mkt_val"].sum()
    diff_cat = diff[cat]
    if not etf_cat.empty and abs(diff_cat) > 1e-2:
        for _, row in etf_cat.iterrows():
            # Peso attuale dell'ETF nella categoria
            peso = row["mkt_val"] / totale_cat if totale_cat > 0 else 1 / len(etf_cat)
            # Quota della differenza da attribuire a questo ETF
            euro_op = peso * diff_cat
            # Calcola quante quote comprare/vendere (arrotonda a 2 decimali)
            n_quote = euro_op / row["curr_price"] if row["curr_price"] > 0 else 0
            dettagli.append({
                "ETF": row["product"],
                "Ticker": row["ticker"],
                "Categoria": cat,
                "Operazione": "Compra" if euro_op > 0 else "Vendi",
                "Valore (€)": euro_op,
                "Quote": n_quote,
                "Prezzo attuale (€)": row["curr_price"]
            })

if dettagli:
    df_dettagli = pd.DataFrame(dettagli)
    st.dataframe(
        df_dettagli[["ETF", "Ticker", "Categoria", "Operazione", "Valore (€)", "Quote", "Prezzo attuale (€)"]]
        .style.format({"Valore (€)": "€ {:.2f}", "Quote": "{:.2f}", "Prezzo attuale (€)": "€ {:.2f}"})
    )
else:
    st.info("Nessuna operazione suggerita: il portafoglio è già allineato ai target.")