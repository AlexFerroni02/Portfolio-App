import streamlit as st
import pandas as pd
import plotly.express as px
from typing import List, Dict, Any
from ui.components import style_chart_for_mobile

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

def render_allocation_charts(geo_data: dict, sec_data: dict):
    """
    Renderizza i grafici a torta per l'allocazione geografica e settoriale.
    """
    st.subheader("🔬 Composizione Asset")
    if not geo_data and not sec_data:
        st.info("Dati di allocazione non ancora scaricati. Vai su 'Gestione Dati' per scaricarli.")
        return

    col1, col2 = st.columns(2)
    with col1:
        if geo_data:
            df_g = pd.DataFrame(list(geo_data.items()), columns=['Paese', 'Percentuale'])
            fig_geo = px.pie(df_g, values='Percentuale', names='Paese', title='Esposizione Geografica', hole=0.4)
            fig_geo.update_layout(showlegend=False)
            fig_geo.update_traces(textinfo='percent', textposition='inside', hovertemplate='<b>%{label}</b>: %{value:.2f}%<extra></extra>')
            st.plotly_chart(style_chart_for_mobile(fig_geo), use_container_width=True)
        else:
            st.info("Nessun dato geografico disponibile.")
    with col2:
        if sec_data:
            df_s = pd.DataFrame(list(sec_data.items()), columns=['Settore', 'Percentuale'])
            fig_sec = px.pie(df_s, values='Percentuale', names='Settore', title='Esposizione Settoriale', hole=0.4)
            fig_sec.update_layout(showlegend=False)
            fig_sec.update_traces(textinfo='percent', textposition='inside', hovertemplate='<b>%{label}</b>: %{value:.2f}%<extra></extra>')
            st.plotly_chart(style_chart_for_mobile(fig_sec), use_container_width=True)
        else:
            st.info("Nessun dato settoriale disponibile.")

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
            'quantity': "{:.2f}", 'local_value': "€ {:.2f}", 'fees': "€ {:.2f}", 'date': lambda x: x.strftime('%d-%m-%Y')
        }),
        use_container_width=True,
        hide_index=True
    )