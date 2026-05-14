import streamlit as st
from ui.components import make_sidebar


st.set_page_config(page_title="Metriche (Legacy)", page_icon="📐", layout="wide")
make_sidebar()
st.title("📐 Metriche Spostate")
st.info("La sezione Metriche è stata accorpata nella pagina Performance insieme al Benchmark.")
st.page_link("pages/3_Benchmark.py", label="Apri Performance", icon="⚖️")
