import streamlit as st
import pandas as pd
import plotly.express as px
from typing import List, Dict, Any, Optional
from ui.components import style_chart_for_mobile
from ui.charts import render_geo_map, plot_price_history

# ========== COMPONENTI UI ==========

def render_asset_selector(asset_options: List[str]) -> str:
    """
    Renderizza il selettore dell'asset e gestisce la pre-selezione dalla sessione.
    """
    default_index = 0
    if 'selected_ticker' in st.session_state:
        try:
            selected_option_str = next(opt for opt in asset_options if st.session_state.selected_ticker in opt)
            default_index = asset_options.index(selected_option_str)
        except StopIteration:
            pass 
        del st.session_state['selected_ticker']

    selected_asset_str = st.selectbox("Seleziona un asset da analizzare:", asset_options, index=default_index)
    return selected_asset_str.split('(')[-1].replace(')', '')


def render_asset_header(kpi_data: Dict[str, Any]):
    """
    Renderizza l'header della pagina con nome, ticker, ISIN e link a JustETF.
    """
    col_title, col_btn = st.columns([4, 1])
    with col_title:
        st.header(f"{kpi_data.get('product_name', 'N/A')}")
        st.caption(f"Ticker: **{kpi_data.get('ticker', 'N/A')}** | ISIN: **{kpi_data.get('isin', 'N/A')}**")
    with col_btn:
        if 'ETF' in kpi_data.get('product_name', ''):
            st.link_button("🔎 Vedi su JustETF", f"https://www.justetf.com/it/etf-profile.html?isin={kpi_data.get('isin', '')}")


def render_asset_kpis(kpi_data: Dict[str, Any]):
    """
    Renderizza i KPI per il singolo asset.
    """
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Quantità", f"{kpi_data.get('quantity', 0):.2f}")
    c2.metric("Prezzo Corrente", f"€ {kpi_data.get('last_price', 0):.2f}")
    c3.metric("Valore di Mercato", f"€ {kpi_data.get('market_value', 0):,.2f}")
    c4.metric("P&L", f"€ {kpi_data.get('pnl', 0):,.2f}", delta=f"{kpi_data.get('pnl_perc', 0):.2f}%")
    st.divider()

"""
    Mostra composizione asset con:
    - colonna sinistra: Paesi (toggle Barre / Mappa mondo)
    - colonna destra: Settori (liste con mini-barre)
    """


# ========== COMPOSIZIONE ASSET (BARRE + MAPPA) ==========

def _render_single_allocation_card(
    title: str,
    subtitle: str,
    data: dict,
    text_color: str,
    bar_gradient: str,
    show_map_toggle: bool = False,
    map_toggle_key: str = "geo_view_mode"
):
    """
    Funzione helper riutilizzabile per renderizzare una card di allocazione
    (geografica o settoriale).
    """
    st.markdown(
        f"""
        <div style="
            padding:1rem 1.2rem;
            border-radius:12px;
            background:rgba(255,255,255,0.03);
            border:1px solid rgba(255,255,255,0.06);
            height: 100%;
            ">
          <h3 style="margin-top:0;margin-bottom:0.5rem;">{title}</h3>
          <p style="margin-top:0;color:rgba(255,255,255,0.55);font-size:0.9rem;">
            {subtitle}
          </p>
        """,
        unsafe_allow_html=True,
    )

    if not data:
        st.info("Nessun dato disponibile.")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    view_mode = "Barre"
    if show_map_toggle:
        view_mode = st.radio(
            "Vista", ["Barre", "Mappa"], horizontal=True,
            key=map_toggle_key, label_visibility="collapsed"
        )
    else:
        # Aggiunge uno spazio vuoto per allineare verticalmente le card
        st.markdown("<div style='height:38px;'></div>", unsafe_allow_html=True)

    if view_mode == "Barre":
        df = pd.DataFrame(list(data.items()), columns=["Item", "Percentuale"])
        df = df.sort_values("Percentuale", ascending=False)
        max_val = df["Percentuale"].max() if not df.empty else 0

        for _, row in df.iterrows():
            bar_width = int((row["Percentuale"] / max_val) * 100) if max_val > 0 else 0
            st.markdown(f"""
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 2px;">
                    <span style='font-weight:600;'>{row['Item']}</span>
                    <span style='color:{text_color};'>{row['Percentuale']:.2f}%</span>
                </div>
                <div style="background-color:#222; border-radius:4px; width:100%; height:6px; margin-bottom:10px;">
                    <div style="background:{bar_gradient}; width:{bar_width}%; height:6px; border-radius:4px;"></div>
                </div>
            """, unsafe_allow_html=True)

    elif view_mode == "Mappa":
        render_geo_map(data, value_type="percent", toggle_key="map_projection_toggle_asset")

    st.markdown("</div>", unsafe_allow_html=True)


# ========== COMPOSIZIONE ASSET (ORA MODULARE) ==========

def render_allocation_charts(geo_data: dict, sec_data: dict):
    """
    Mostra composizione asset chiamando il componente riutilizzabile per le card.
    
    Mostra composizione asset con:
    - colonna sinistra: Paesi (toggle Barre / Mappa mondo)
    - colonna destra: Settori (liste con mini-barre)
    
    """
    st.markdown(
        "<h2 style='margin-bottom:0.5rem;'>🧪 Composizione Asset</h2>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<p style='color:rgba(255,255,255,0.6);margin-top:0;'>Panoramica sintetica di Paesi e Settori.</p>",
        unsafe_allow_html=True,
    )

    if not geo_data and not sec_data:
        st.info("Dati di allocazione non ancora scaricati. Vai su 'Gestione Dati' per scaricarli.")
        return

    col1, col2 = st.columns(2)

    with col1:
        _render_single_allocation_card(
            title="🌍 Esposizione Geografica",
            subtitle="Principali Paesi in portafoglio.",
            data=geo_data,
            text_color="#7FDBFF",
            bar_gradient="linear-gradient(90deg,#00c9ff,#92fe9d)",
            show_map_toggle=True
        )

    with col2:
        _render_single_allocation_card(
            title="🧬 Esposizione Settoriale",
            subtitle="Distribuzione per settore.",
            data=sec_data,
            text_color="#FFDC73",
            bar_gradient="linear-gradient(90deg,#FFD166,#F77F00)",
            show_map_toggle=False
        )


# ========== STORICO PREZZI E TRANSAZIONI ==========

def render_price_history(ticker: str, asset_prices: pd.DataFrame):
    """
    Renderizza il grafico dello storico prezzi.
    """
    st.divider()
    st.subheader("📉 Storico Prezzo")
    if not asset_prices.empty:
        fig = plot_price_history(asset_prices, ticker)
        if fig:
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Nessuna informazione sullo storico prezzi per questo asset.")


def render_transactions_table(df_asset_trans: pd.DataFrame):
    """
    Renderizza la tabella con lo storico delle transazioni.
    """
    st.subheader("📝 Storico Transazioni")
    st.dataframe(
        df_asset_trans[['date', 'product', 'quantity', 'local_value', 'fees']].style.format({
            'quantity': "{:.2f}", 
            'local_value': "€ {:.2f}", 
            'fees': "€ {:.2f}", 
            'date': lambda x: x.strftime('%d-%m-%Y')
        }),
        width='stretch',
        hide_index=True
    )
