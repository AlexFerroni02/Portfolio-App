import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import streamlit as st
import pycountry
from typing import Dict, Optional


# ========== CONVERSIONE IT -> ISO3 (per mappa geografica) ==========

COUNTRY_ALIASES_IT = {
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
    "United Arab Emirates": "United Arab Emirates",
    "saudi arabia": "Saudi Arabia",
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
    "repubblica sudafricana": "South Africa",
    "egitto": "Egypt",
    "nigeria": "Nigeria",
    "marocco": "Morocco",
    
    # Russia
    "russia": "Russian Federation",
}

def _name_to_iso3(country_name: str) -> Optional[str]:
    """
    Converte nome paese (anche italiano) in ISO3.
    Usa pycountry + alias minimi per i casi non riconosciuti.
    """
    if not country_name:
        return None
    
    name = str(country_name).strip()
    low = name.lower()
    
    # Escludi voci non-paese
    if low in {"altri", "altro", "resto", "resto del mondo"}:
        return None
    
    # 1) Prova alias IT -> EN
    query = COUNTRY_ALIASES_IT.get(low, name)
    
    # 2) Prova pycountry (fuzzy search)
    try:
        result = pycountry.countries.search_fuzzy(query)
        return result[0].alpha_3
    except Exception:
        return None


def style_chart_for_mobile(fig: go.Figure) -> go.Figure:
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


def render_geo_map(geo_dict: dict, value_type: str = "euro", toggle_key: str = "map_projection_toggle"):
    """
    Mappa geografica interattiva con Plotly - versione modulare e riutilizzabile.
    
    Args:
        geo_dict: {nome_paese_IT: valore} - può essere in euro o percentuale
        value_type: "euro" o "percent" - determina il formato di visualizzazione
        toggle_key: chiave univoca per il widget di toggle (evita conflitti)
    """
    if not geo_dict:
        return
    
    # ========== PREPARAZIONE DATI ==========
    value_col = "Valore" if value_type == "euro" else "Percentuale"
    df_full = pd.DataFrame(list(geo_dict.items()), columns=["Paese_it", value_col])
    df_full["key"] = df_full["Paese_it"].astype(str).str.strip().str.lower()
    
    # Totale ORIGINALE (con "Altri")
    total_original = df_full[value_col].sum()
    
    # Valore "Altri"
    altri_mask = df_full["key"].isin({"altri", "altro", "resto", "resto del mondo"})
    altri_value = df_full[altri_mask][value_col].sum()
    altri_perc = (altri_value / total_original * 100) if total_original > 0 and value_type == "euro" else altri_value
    
    # Dataset filtrato (senza "Altri")
    df = df_full[~altri_mask].copy()
    
    # Conversione IT -> ISO3
    df["iso3"] = df["Paese_it"].apply(_name_to_iso3)
    df = df[df["iso3"].notna()].copy()
    
    if df.empty:
        st.warning("Nessun paese riconosciuto per la mappa.")
        return
    
    # ========== TOGGLE MINIMALE + AVVISO "ALTRI" ==========
    col_toggle, col_alert = st.columns([1, 4])
    with col_toggle:
        projection_choice = st.segmented_control(
            label="Vista",
            options=["🌐", "🗺️"],
            default="🌐",
            label_visibility="collapsed",
            key=toggle_key
        )
    
    with col_alert:
        if altri_value > 0:
            if value_type == "euro":
                st.caption(
                    f"ℹ️ **{altri_perc:.1f}%** (€{altri_value:,.0f}) allocato in paesi non visualizzabili sulla mappa.",
                    help="Questa quota include paesi non riconosciuti o voci generiche ('Altri', 'Resto del mondo', ecc.)"
                )
            else:
                st.caption(
                    f"ℹ️ **{altri_value:.1f}%** allocato in paesi non visualizzabili sulla mappa.",
                    help="Questa quota include paesi non riconosciuti o voci generiche ('Altri', 'Resto del mondo', ecc.)"
                )
    
    # Mappa icone -> proiezioni
    projection_map = {
        "🌐": "orthographic",      # Globo 3D
        "🗺️": "natural earth"      # Planisfero 2D
    }
    projection_type = projection_map.get(projection_choice, "orthographic")
    
    # ========== CREAZIONE MAPPA ==========
    fig = px.choropleth(
        df,
        locations="iso3",
        locationmode="ISO-3",
        color=value_col,
        hover_name="Paese_it",
        color_continuous_scale=[
            [0.0, "rgba(16, 185, 129, 0.2)"],   # verde chiaro
            [0.3, "rgba(16, 185, 129, 0.5)"],
            [0.6, "rgba(59, 130, 246, 0.7)"],   # blu
            [1.0, "rgba(99, 102, 241, 1.0)"]    # indaco
        ],
        projection=projection_type,
    )
    
    # ========== STILE GEO ==========
    fig.update_geos(
        showocean=True, 
        oceancolor="#0E1117",
        showlakes=True,
        lakecolor="#0E1117",
        showcountries=True,
        countrycolor="rgba(255,255,255,0.08)",
        showcoastlines=True,
        coastlinecolor="rgba(255,255,255,0.15)",
        showland=True,
        landcolor="rgba(38, 39, 48, 0.4)",
        projection_rotation=dict(lon=10, lat=30, roll=0) if projection_type == "orthographic" else None,
        bgcolor="rgba(0,0,0,0)"
    )
    
    # ========== LAYOUT ==========
    colorbar_title = "Valore €" if value_type == "euro" else "Peso %"
    colorbar_format = ",.0f" if value_type == "euro" else ".1f"
    
    fig.update_layout(
        margin=dict(l=0, r=0, t=0, b=0),
        height=480,
        coloraxis_colorbar=dict(
            title=dict(
                text=colorbar_title,
                font=dict(size=13, color="rgba(255,255,255,0.9)")
            ),
            tickformat=colorbar_format,
            len=0.65,
            thickness=14,
            bgcolor="rgba(38, 39, 48, 0.8)",
            bordercolor="rgba(255,255,255,0.1)",
            borderwidth=1,
            tickfont=dict(size=11, color="rgba(255,255,255,0.7)"),
            x=1.02,
        ),
        paper_bgcolor="rgba(0,0,0,0)",
        geo=dict(bgcolor="rgba(0,0,0,0)"),
        font=dict(family="Inter, sans-serif", color="rgba(255,255,255,0.9)")
    )
    
    # ========== TOOLTIP ==========
    if value_type == "euro":
        # Calcola percentuali per tooltip
        df["Percentuale"] = (df[value_col] / total_original * 100) if total_original > 0 else 0
        fig.update_traces(
            hovertemplate=(
                "<b style='font-size:14px'>%{hovertext}</b><br>"
                "<span style='color:#10B981'>€%{z:,.0f}</span> "
                "<span style='color:rgba(255,255,255,0.6)'>(%{customdata:.1f}%)</span>"
                "<extra></extra>"
            ),
            customdata=df["Percentuale"],
            marker_line_width=0.5,
            marker_line_color="rgba(255,255,255,0.2)"
        )
    else:
        fig.update_traces(
            hovertemplate=(
                "<b style='font-size:14px'>%{hovertext}</b><br>"
                "<span style='color:#10B981'>%{z:.2f}%</span>"
                "<extra></extra>"
            ),
            marker_line_width=0.5,
            marker_line_color="rgba(255,255,255,0.2)"
        )
    
    st.plotly_chart(style_chart_for_mobile(fig), width='stretch')

def plot_allocation_pie(data: Dict[str, float], title: str) -> go.Figure:
    """
    Crea un grafico a torta per l'allocazione geografica o settoriale.
    """
    if not data:
        return None
        
    df = pd.DataFrame(list(data.items()), columns=['Label', 'Value'])
    fig = px.pie(df, values='Value', names='Label', title=title, hole=0.4)
    fig.update_layout(showlegend=False)
    fig.update_traces(textinfo='percent', textposition='inside', hovertemplate='<b>%{label}</b>: %{value:.2f}%<extra></extra>')
    return style_chart_for_mobile(fig)

def plot_price_history(df_prices: pd.DataFrame, ticker: str) -> go.Figure:
    """
    Crea il grafico storico dei prezzi per un asset.
    """
    if df_prices.empty:
        return None
        
    fig = px.line(df_prices, x='date', y='close_price', title=f"Andamento {ticker}")
    fig.update_traces(line_color='#00CC96')
    return style_chart_for_mobile(fig)

def plot_portfolio_history(df_hist: pd.DataFrame) -> go.Figure:
    """
    Crea il grafico storico del portafoglio (Valore vs Costo).
    """
    if df_hist.empty:
        return None
        
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df_hist['Data'], y=df_hist['Valore'], mode='lines', name='Valore', line=dict(color='#00CC96'), fill='tozeroy'))
    fig.add_trace(go.Scatter(x=df_hist['Data'], y=df_hist['Spesa'], mode='lines', name='Costi', line=dict(color='#EF553B', dash='dash')))
    return style_chart_for_mobile(fig)

def plot_treemap(view_df: pd.DataFrame) -> go.Figure:
    """
    Crea la treemap del portafoglio.
    """
    fig = px.treemap(view_df, path=['category', 'product'], values='mkt_val',
                        color='pnl%', 
                        color_continuous_scale='RdYlGn',
                        color_continuous_midpoint=0)
    fig.update_layout(margin=dict(t=0, b=0, l=0, r=0))
    return fig