import streamlit as st
from datetime import datetime

def make_sidebar():
    """
    Crea la sidebar di navigazione.
    """
    with st.sidebar:
        st.page_link("app.py", label="Dashboard", icon="🏠")
        st.page_link("pages/1_Analisi_Asset.py", label="Analisi Asset", icon="🔎")
        st.page_link("pages/2_Gestione_Dati.py", label="Gestione Dati", icon="📂")
        st.page_link("pages/3_Benchmark.py", label="Benchmark", icon="⚖️")
        st.page_link("pages/4_Bilancio.py", label="Bilancio", icon="💰")
        
        st.divider()
        st.caption(f"Portfolio Pro v1.2\n© {datetime.now().year}")

def style_chart_for_mobile(fig):
    """
    Applica uno stile responsive e pulito ai grafici Plotly.
    """
    fig.update_layout(
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1), 
        margin=dict(l=10, r=10, t=40, b=10), 
        hovermode="x unified", 
        paper_bgcolor="rgba(0,0,0,0)", 
        plot_bgcolor="rgba(0,0,0,0)"
    )
    return fig

def color_pnl(val):
    """
    Applica uno sfondo colorato in base al segno del P&L.
    """
    v = 0
    try:
        if isinstance(val, (int, float)): v = val
        else: v = float(str(val).replace('%', '').strip())
        color = '#d4edda' if v >= 0 else '#f8d7da'
        text_color = '#155724' if v >= 0 else '#721c24'
        return f'background-color: {color}; color: {text_color}'
    except (ValueError, TypeError): 
        return ''