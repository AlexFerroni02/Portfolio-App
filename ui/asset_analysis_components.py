import streamlit as st
import pandas as pd
import plotly.express as px
from typing import List, Dict, Any, Optional
from ui.components import style_chart_for_mobile
from ui.charts import render_geo_map, plot_price_history


# Le costanti e funzioni per la mappa geografica sono ora in ui/charts.py
# Manteniamo qui solo un riferimento per retrocompatibilità se necessario
from ui.charts import COUNTRY_ALIASES_IT as _COUNTRY_ALIASES_IT_UNUSED

_COUNTRY_ALIASES_IT_OLD = {
    # Nord America
    "stati uniti": "United States",
    "canada": "Canada",
    "messico": "Mexico",
    
    # Europa
    "regno unito": "United Kingdom",
    "paesi bassi": "Netherlands",
    "germania": "Germany",
    "francia": "France",
    "svizzera": "Switzerland",
    "irlanda": "Ireland",
    "belgio": "Belgium",
    "italia": "Italy",
    "spagna": "Spain",
    "austria": "Austria",
    "finlandia": "Finland",
    "portogallo": "Portugal",
    "grecia": "Greece",
    "norvegia": "Norway",
    "svezia": "Sweden",
    "danimarca": "Denmark",
    "polonia": "Poland",
    
    # Asia
    "giappone": "Japan",
    "cina": "China",
    "india": "India",
    "taiwan": "Taiwan",
    "corea del sud": "Korea, Republic of",
    "corea del nord": "Korea, Democratic People's Republic of",
    "singapore": "Singapore",
    "hong kong": "Hong Kong",
    "indonesia": "Indonesia",
    "malesia": "Malaysia",
    "thailandia": "Thailand",
    "vietnam": "Vietnam",
    "filippine": "Philippines",
    "emirati arabi uniti": "United Arab Emirates",
    "arabia saudita": "Saudi Arabia",
    "israele": "Israel",
    "turchia": "Turkey",
    
    # Oceania
    "australia": "Australia",
    "nuova zelanda": "New Zealand",
    
    # Sud America
    "brasile": "Brazil",
    "argentina": "Argentina",
    "cile": "Chile",
    "colombia": "Colombia",
    "perù": "Peru",
    "venezuela": "Venezuela",
    
    # Africa
    "sudafrica": "South Africa",
    "sud africa": "South Africa",
    "egitto": "Egypt",
    "nigeria": "Nigeria",
    "marocco": "Morocco",
    
    # Russia
    "russia": "Russian Federation",
}  # Mantenuto per retrocompatibilità, ma non più usato


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


# ========== MAPPA GEOGRAFICA (ORA MODULARE) ==========

def render_geo_map_folium(geo_data: dict):
    """
    DEPRECATED: Usa render_geo_map da ui.charts invece.
    Manteniamo questo wrapper per retrocompatibilità.
    geo_data: {nome_paese_IT: percentuale}
    """
    render_geo_map(geo_data, value_type="percent", toggle_key="map_projection_toggle_asset")


# ========== COMPOSIZIONE ASSET (BARRE + MAPPA) ==========

def render_allocation_charts(geo_data: dict, sec_data: dict):
    """
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

    # ---------- CARD GEOGRAFICA ----------
    with col1:
        st.markdown(
            """
            <div style="
                padding:1rem 1.2rem;
                border-radius:12px;
                background:rgba(255,255,255,0.03);
                border:1px solid rgba(255,255,255,0.06);
                ">
              <h3 style="margin-top:0;margin-bottom:0.5rem;">🌍 Esposizione Geografica</h3>
              <p style="margin-top:0;color:rgba(255,255,255,0.55);font-size:0.9rem;">
                Principali Paesi in portafoglio.
              </p>
            """,
            unsafe_allow_html=True,
        )

        if geo_data:
            df_g = pd.DataFrame(list(geo_data.items()), columns=["Paese", "Percentuale"])
            df_g = df_g.sort_values("Percentuale", ascending=False)
            max_val_g = df_g["Percentuale"].max()

            # Toggle Barre/Mappa dentro la card
            view_mode = st.radio(
                "Vista",
                ["Barre", "Mappa"],
                horizontal=True,
                key="geo_view_mode",
                label_visibility="collapsed"
            )

            if view_mode == "Barre":
                # Vista a barre (lista + mini-barre)
                for _, row in df_g.iterrows():
                    bar_width = int((row["Percentuale"] / max_val_g) * 100)

                    left, right = st.columns([3, 1])
                    with left:
                        st.markdown(
                            f"<span style='font-weight:600;'>{row['Paese']}</span>",
                            unsafe_allow_html=True,
                        )
                    with right:
                        st.markdown(
                            f"<span style='float:right;color:#7FDBFF;'>{row['Percentuale']:.2f}%</span>",
                            unsafe_allow_html=True,
                        )

                    st.markdown(
                        f"""
                        <div style="background-color:#222;border-radius:4px;
                                    width:100%;height:6px;margin-top:2px;margin-bottom:10px;">
                            <div style="
                                background:linear-gradient(90deg,#00c9ff,#92fe9d);
                                width:{bar_width}%;
                                height:6px;
                                border-radius:4px;">
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
            else:
                # Vista mappa mondo
                render_geo_map_folium(geo_data)
        else:
            st.info("Nessun dato geografico disponibile.")

        st.markdown("</div>", unsafe_allow_html=True)

    # ---------- CARD SETTORIALE ----------
    with col2:
        st.markdown(
            """
            <div style="
                padding:1rem 1.2rem;
                border-radius:12px;
                background:rgba(255,255,255,0.03);
                border:1px solid rgba(255,255,255,0.06);
                ">
              <h3 style="margin-top:0;margin-bottom:0.5rem;">🧬 Esposizione Settoriale</h3>
              <p style="margin-top:0;color:rgba(255,255,255,0.55);font-size:0.9rem;">
                Distribuzione per settore.
              </p>
            """,
            unsafe_allow_html=True,
        )

        if sec_data:
            # Spazio per allineare con il toggle della colonna geografica
            st.markdown("<div style='height:56px;'></div>", unsafe_allow_html=True)
            
            df_s = pd.DataFrame(list(sec_data.items()), columns=["Settore", "Percentuale"])
            df_s = df_s.sort_values("Percentuale", ascending=False)
            max_val_s = df_s["Percentuale"].max()

            for _, row in df_s.iterrows():
                bar_width = int((row["Percentuale"] / max_val_s) * 100)

                left, right = st.columns([3, 1])
                with left:
                    st.markdown(
                        f"<span style='font-weight:600;'>{row['Settore']}</span>",
                        unsafe_allow_html=True,
                    )
                with right:
                    st.markdown(
                        f"<span style='float:right;color:#FFDC73;'>{row['Percentuale']:.2f}%</span>",
                        unsafe_allow_html=True,
                    )

                st.markdown(
                    f"""
                    <div style="background-color:#222;border-radius:4px;
                                width:100%;height:6px;margin-top:2px;margin-bottom:10px;">
                        <div style="
                            background:linear-gradient(90deg,#FFD166,#F77F00);
                            width:{bar_width}%;
                            height:6px;
                            border-radius:4px;">
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
        else:
            st.info("Nessun dato settoriale disponibile.")

        st.markdown("</div>", unsafe_allow_html=True)


# ========== STORICO PREZZI E TRANSAZIONI ==========

def render_price_history(ticker: str, asset_prices: pd.DataFrame):
    """
    Renderizza il grafico dello storico prezzi.
    """
    st.divider()
    st.subheader("📉 Storico Prezzo")
    if not asset_prices.empty:
        fig = px.line(asset_prices, x='date', y='close_price', title=f"Andamento {ticker}")
        fig.update_traces(line_color='#00CC96')
        st.plotly_chart(style_chart_for_mobile(fig), use_container_width=True)
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
        use_container_width=True,
        hide_index=True
    )
