import streamlit as st

from database.connection import get_data
from exceptions.live_exceptions import LiveDataError
from services.live_service import build_live_snapshot, fetch_live_quotes
from ui.components import make_sidebar
from ui.live_components import (
    render_live_delay_note,
    render_live_kpis,
    render_live_movers,
    render_live_status,
    render_live_table,
)

try:
    from streamlit_autorefresh import st_autorefresh
except ImportError:  # pragma: no cover - optional dependency fallback
    st_autorefresh = None


st.set_page_config(page_title="Live", page_icon="📈", layout="wide")
make_sidebar()
st.title("📈 Live Monitor")
st.caption("Monitor intraday del portafoglio con focus su variazione giornaliera e titoli più movimentati.")

col_toggle, col_button = st.columns([3, 1])
auto_refresh = col_toggle.toggle(
    "Aggiornamento automatico ogni 5 minuti (solo in questa pagina)",
    value=True,
    key="live_auto_refresh_toggle",
)
if col_button.button("🔄 Aggiorna Ora"):
    fetch_live_quotes.clear()
    st.rerun()

if auto_refresh and st_autorefresh:
    st_autorefresh(interval=300000, key="live_auto_refresh_clock")
if auto_refresh and st_autorefresh is None:
    st.info("Auto-refresh non disponibile: installa la dipendenza streamlit-autorefresh.")

with st.spinner("Caricamento dati live..."):
    df_trans = get_data("transactions")
    df_map = get_data("mapping")
    df_prices = get_data("prices")

if df_trans.empty or df_map.empty or df_prices.empty:
    st.warning("Servono transazioni, mappatura e prezzi per mostrare la vista live.")
    st.stop()

try:
    snapshot = build_live_snapshot(df_trans, df_map, df_prices)
except LiveDataError as exc:
    st.info(str(exc))
    st.stop()

render_live_status(snapshot["market_open"], snapshot["last_update"], snapshot["stale_count"], len(snapshot["rows"]))
render_live_kpis(snapshot["metrics"])
st.divider()
render_live_movers(snapshot["rows"])
st.divider()
render_live_table(snapshot["rows"])
render_live_delay_note()
