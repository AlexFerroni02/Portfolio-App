import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import streamlit as st
import pycountry
from typing import Dict, Optional


# ========== CONFIGURAZIONI CENTRALIZZATE ==========

# Configurazione base per le allocazioni geografiche e settoriali nell'analisi asset
# Utilizzata nelle pagine di analisi asset (asset_analysis_components.py)
ALLOCATION_CONFIG = {
    "geo": {
        "title": "🌍 Esposizione Geografica",  # Titolo della card
        "subtitle": "Principali Paesi in portafoglio.",  # Sottotitolo
        "text_color": "#7FDBFF",  # Colore del testo per le percentuali
        "bar_gradient": "linear-gradient(90deg,#00c9ff,#92fe9d)",  # Gradiente per le barre
        "key_prefix": "asset_geo",  # Prefisso per le chiavi Streamlit (evita conflitti)
        "show_map_toggle": True,  # Mostra il toggle per passare da barre a mappa
        "value_type": "percent",  # Tipo di valore: "percent" o "euro"
        "default_top_n": 10  # Numero di elementi top da mostrare di default
    },
    "sec": {
        "title": "🧬 Esposizione Settoriale",
        "subtitle": "Distribuzione per settore.",
        "text_color": "#FFDC73",
        "bar_gradient": "linear-gradient(90deg,#FFD166,#F77F00)",
        "key_prefix": "asset_sec",
        "show_map_toggle": False,  # Settori non hanno mappa, solo barre
        "value_type": "percent",
        "default_top_n": 10
    }
}

# Configurazione derivata per il dashboard, con valori in euro invece di percentuali
# Utilizzata nella pagina dashboard (dashboard_components.py)
ALLOCATION_CONFIG_DASH = {
    "geo": ALLOCATION_CONFIG["geo"].copy() | {
        "subtitle": "Principali Paesi",  # Sottotitolo semplificato
        "key_prefix": "dash_geo",  # Prefisso diverso per dashboard
        "value_type": "euro"  # Valori assoluti in euro
    },
    "sec": ALLOCATION_CONFIG["sec"].copy() | {
        "key_prefix": "dash_sec",
        "value_type": "euro"
    }
}


# ========== CONVERSIONE IT -> ISO3 (per mappa geografica) ==========

# Dizionario di alias per convertire nomi paesi italiani in inglesi
# Necessario perché pycountry lavora con nomi inglesi
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
    
    # Escludi voci non-paese come "Altri" che non hanno senso su una mappa
    if low in {"altri", "altro", "resto", "resto del mondo"}:
        return None
    
    # 1) Prova a tradurre con gli alias italiani
    query = COUNTRY_ALIASES_IT.get(low, name)
    
    # 2) Usa pycountry per ricerca fuzzy (approssimata)
    try:
        result = pycountry.countries.search_fuzzy(query)
        return result[0].alpha_3  # Restituisce il codice ISO3 del primo risultato
    except Exception:
        return None  # Se non trova nulla, restituisce None


def style_chart_for_mobile(fig: go.Figure) -> go.Figure:
    """
    Applica uno stile responsive e pulito ai grafici Plotly.
    """
    # Configura layout per mobile: legenda orizzontale, margini ridotti, sfondo trasparente
    fig.update_layout(
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1), 
        margin=dict(l=10, r=10, t=40, b=10), 
        hovermode="x unified",  # Hover unificato per migliore UX
        paper_bgcolor="rgba(0,0,0,0)",  # Sfondo trasparente
        plot_bgcolor="rgba(0,0,0,0)"  # Sfondo plot trasparente
    )
    return fig


def render_geo_map(geo_dict: dict, value_type: str = "euro", toggle_key: str = "map_projection_toggle", include_others: bool = False):
    """
    Mappa geografica interattiva con Plotly - versione modulare e riutilizzabile.
    
    Args:
        geo_dict: {nome_paese_IT: valore} - può essere in euro o percentuale
        value_type: "euro" o "percent" - determina il formato di visualizzazione
        toggle_key: chiave univoca per il widget di toggle (evita conflitti)
        include_others: se True, non esclude "Altri" e setta altri_value = 0
    """
    if not geo_dict:
        return  # Se non ci sono dati, esci
    
    # ========== PREPARAZIONE DATI ==========
    # Determina il nome della colonna valore basato sul tipo
    value_col = "Valore" if value_type == "euro" else "Percentuale"
    # Crea DataFrame dai dati
    df_full = pd.DataFrame(list(geo_dict.items()), columns=["Paese_it", value_col])
    df_full["key"] = df_full["Paese_it"].astype(str).str.strip().str.lower()
    
    # Calcola il totale originale (incluso "Altri")
    total_original = df_full[value_col].sum()
    
    # Gestione del valore "Altri" (paesi non mappabili)
    if include_others:
        altri_value = 0  # Non escludere "Altri"
        altri_perc = 0
        df = df_full.copy()
    else:
        # Identifica righe "Altri"
        altri_mask = df_full["key"].isin({"altri", "altro", "resto", "resto del mondo"})
        altri_value = df_full[altri_mask][value_col].sum()
        altri_perc = (altri_value / total_original * 100) if total_original > 0 and value_type == "euro" else altri_value
        df = df_full[~altri_mask].copy()  # Escludi "Altri" dal DataFrame da mappare
    
    # Converte nomi paesi italiani in codici ISO3 per Plotly
    df["iso3"] = df["Paese_it"].apply(_name_to_iso3)
    df = df[df["iso3"].notna()].copy()  # Rimuovi paesi non riconosciuti
    
    if df.empty:
        st.warning("Nessun paese riconosciuto per la mappa.")
        return
    
    # ========== TOGGLE MINIMALE + AVVISO "ALTRI" ==========
    # Crea colonne per toggle proiezione e avviso "Altri"
    col_toggle, col_alert = st.columns([1, 4])
    with col_toggle:
        # Toggle per scegliere tra globo 3D e planisfero 2D
        projection_choice = st.segmented_control(
            label="Vista",
            options=["🌐", "🗺️"],  # Globo e Mappa
            default="🌐",
            label_visibility="collapsed",
            key=toggle_key
        )
    
    with col_alert:
        # Mostra avviso se c'è valore "Altri" non mappabile
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
    # Crea choropleth map con Plotly Express
    fig = px.choropleth(
        df,
        locations="iso3",  # Codici ISO3
        locationmode="ISO-3",
        color=value_col,  # Colonna da colorare
        hover_name="Paese_it",  # Nome da mostrare su hover
        color_continuous_scale=[  # Scala colori personalizzata
            [0.0, "rgba(16, 185, 129, 0.2)"],   # verde chiaro
            [0.3, "rgba(16, 185, 129, 0.5)"],
            [0.6, "rgba(59, 130, 246, 0.7)"],   # blu
            [1.0, "rgba(99, 102, 241, 1.0)"]    # indaco
        ],
        projection=projection_type,  # Tipo di proiezione scelto
    )
    
    # ========== STILE GEO ==========
    # Personalizza l'aspetto geografico della mappa
    fig.update_geos(
        showocean=True,  # Mostra oceani
        oceancolor="#0E1117",  # Colore oceani scuro
        showlakes=True,  # Mostra laghi
        lakecolor="#0E1117",
        showcountries=True,  # Mostra confini paesi
        countrycolor="rgba(255,255,255,0.08)",  # Colore confini sottile
        showcoastlines=True,  # Mostra linee costa
        coastlinecolor="rgba(255,255,255,0.15)",
        showland=True,  # Mostra terra
        landcolor="rgba(38, 39, 48, 0.4)",  # Colore terra semi-trasparente
        projection_rotation=dict(lon=10, lat=30, roll=0) if projection_type == "orthographic" else None,  # Rotazione per globo
        bgcolor="rgba(0,0,0,0)"  # Sfondo trasparente
    )
    
    # ========== LAYOUT ==========
    # Determina titolo e formato colorbar basato sul tipo valore
    colorbar_title = "Valore €" if value_type == "euro" else "Peso %"
    colorbar_format = ",.0f" if value_type == "euro" else ".1f"
    
    # Aggiorna layout generale
    fig.update_layout(
        margin=dict(l=0, r=0, t=0, b=0),  # Margini zero
        height=480,  # Altezza fissa
        coloraxis_colorbar=dict(
            title=dict(
                text=colorbar_title,
                font=dict(size=13, color="rgba(255,255,255,0.9)")
            ),
            tickformat=colorbar_format,  # Formato numeri
            len=0.65,  # Lunghezza colorbar
            thickness=14,  # Spessore
            bgcolor="rgba(38, 39, 48, 0.8)",  # Sfondo colorbar
            bordercolor="rgba(255,255,255,0.1)",
            borderwidth=1,
            tickfont=dict(size=11, color="rgba(255,255,255,0.7)"),
            x=1.02,  # Posizione
        ),
        paper_bgcolor="rgba(0,0,0,0)",  # Sfondo carta trasparente
        geo=dict(bgcolor="rgba(0,0,0,0)"),  # Sfondo geo trasparente
        font=dict(family="Inter, sans-serif", color="rgba(255,255,255,0.9)")  # Font
    )
    
    # ========== TOOLTIP ==========
    # Personalizza i tooltip in base al tipo valore
    if value_type == "euro":
        # Per valori in euro, calcola percentuali per tooltip
        df["Percentuale"] = (df[value_col] / total_original * 100) if total_original > 0 else 0
        fig.update_traces(
            hovertemplate=(
                "<b style='font-size:14px'>%{hovertext}</b><br>"  # Nome paese
                "<span style='color:#10B981'>€%{z:,.0f}</span> "  # Valore euro
                "<span style='color:rgba(255,255,255,0.6)'>(%{customdata:.1f}%)</span>"  # Percentuale
                "<extra></extra>"
            ),
            customdata=df["Percentuale"],  # Dati personalizzati per hover
            marker_line_width=0.5,  # Bordi sottili
            marker_line_color="rgba(255,255,255,0.2)"
        )
    else:
        # Per percentuali, mostra solo il valore
        fig.update_traces(
            hovertemplate=(
                "<b style='font-size:14px'>%{hovertext}</b><br>"
                "<span style='color:#10B981'>%{z:.2f}%</span>"
                "<extra></extra>"
            ),
            marker_line_width=0.5,
            marker_line_color="rgba(255,255,255,0.2)"
        )
    
    # Mostra il grafico con stile mobile
    st.plotly_chart(style_chart_for_mobile(fig), width='content')

def plot_allocation_pie(data: Dict[str, float], title: str) -> go.Figure:
    """
    Crea un grafico a torta per l'allocazione geografica o settoriale.
    """
    if not data:
        return None  # Se non ci sono dati, restituisci None
        
    # Crea DataFrame dai dati
    df = pd.DataFrame(list(data.items()), columns=['Label', 'Value'])
    # Crea grafico a torta con buco centrale (donut)
    fig = px.pie(df, values='Value', names='Label', title=title, hole=0.4)
    fig.update_layout(showlegend=False)  # Nasconde legenda
    # Personalizza etichette e tooltip
    fig.update_traces(textinfo='percent', textposition='inside', hovertemplate='<b>%{label}</b>: %{value:.2f}%<extra></extra>')
    # Applica stile mobile
    return style_chart_for_mobile(fig)

def plot_price_history(df_prices: pd.DataFrame, ticker: str, df_asset_trans: pd.DataFrame) -> go.Figure:
    """
    Crea il grafico storico dei prezzi per un asset con indicatori delle transazioni.
    """
    if df_prices.empty:
        return None  # Se DataFrame vuoto, restituisci None
        
    # Crea grafico a linea con Plotly Express
    fig = px.line(df_prices, x='date', y='close_price', title=f"Andamento {ticker}")
    fig.update_traces(line_color='#00CC96')  # Colore linea verde
    
    # Aggiungi punti rossi per le transazioni
    if not df_asset_trans.empty:
        # Filtra le date delle transazioni che hanno un prezzo corrispondente
        trans_dates = df_asset_trans['date'].dropna().unique()
        trans_prices = []
        trans_dates_filtered = []
        for d in trans_dates:
            price_row = df_prices[df_prices['date'] == d]
            if not price_row.empty:
                trans_prices.append(price_row['close_price'].iloc[0])
                trans_dates_filtered.append(d)
        
        if trans_dates_filtered:
            fig.add_trace(go.Scatter(
                x=trans_dates_filtered,
                y=trans_prices,
                mode='markers',
                marker=dict(color='red', size=10, symbol='diamond', line=dict(color='white', width=1)),
                name='Transazioni',
                hovertemplate='Transazione: %{x}<br>Prezzo: €%{y:.2f}<extra></extra>'
            ))
    
    # Applica stile mobile
    return style_chart_for_mobile(fig)

def plot_portfolio_history(df_hist: pd.DataFrame) -> go.Figure:
    """
    Crea il grafico storico del portafoglio (Valore vs Costo).
    """
    if df_hist.empty:
        return None  # Se DataFrame vuoto, restituisci None
        
    # Crea figura con due linee: Valore e Investito
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df_hist['Data'], y=df_hist['Valore'], mode='lines', name='Valore', line=dict(color='#00CC96'), fill='tozeroy'))  # Linea verde con riempimento
    fig.add_trace(go.Scatter(x=df_hist['Data'], y=df_hist['Investito'], mode='lines', name='Costi', line=dict(color='#EF553B', dash='dash')))  # Linea rossa tratteggiata
    # Applica stile mobile
    return style_chart_for_mobile(fig)

def plot_treemap(view_df: pd.DataFrame) -> go.Figure:
    """
    Crea la treemap del portafoglio.
    """
    # Crea treemap con categorie, prodotti, valori di mercato e P&L colorato
    fig = px.treemap(view_df, path=['category', 'product'], values='mkt_val',
                        color='pnl%',  # Colora basato su P&L
                        color_continuous_scale='RdYlGn',  # Scala rosso-giallo-verde
                        color_continuous_midpoint=0)  # Punto medio a 0
    fig.update_layout(margin=dict(t=0, b=0, l=0, r=0))  # Margini zero
    return fig

def get_toggle_label(total_count: int, default_top_n: int) -> str:
    """
    Calcola l'etichetta per il toggle "Mostra tutti" basata sul numero totale di elementi e il default.
    
    Args:
        total_count: Numero totale di elementi nel dataset.
        default_top_n: Numero di elementi mostrati di default.
    
    Returns:
        Stringa per l'etichetta del toggle, o stringa vuota se non necessario.
    """
    if total_count <= default_top_n:
        return ""
    shown_count = min(default_top_n, total_count)
    return f"Mostra tutti ({shown_count} di {total_count})"

def render_allocation_card(config: dict):
    """
    Renderizza una card per l'analisi X-Ray (geografica o settoriale) in modo centralizzato.
    
    Args:
        config: Dizionario con i parametri di configurazione. Chiavi richieste:
            - title: str
            - subtitle: str
            - data: dict (dati da visualizzare)
            - value_type: str ("euro" o "percent")
            - text_color: str (colore testo)
            - bar_gradient: str (gradiente barre)
            - key_prefix: str (prefisso per chiavi Streamlit)
            - show_map_toggle: bool (se mostrare toggle mappa)
            - default_top_n: int (numero top elementi, default 5)
    """
    # Estrazione parametri con default
    title = config["title"]
    subtitle = config["subtitle"]
    data = config["data"]
    value_type = config["value_type"]
    text_color = config["text_color"]
    bar_gradient = config["bar_gradient"]
    key_prefix = config["key_prefix"]
    show_map_toggle = config.get("show_map_toggle", False)
    default_top_n = config.get("default_top_n", 5)
    
    # Validazione base delle chiavi richieste
    required_keys = ["title", "subtitle", "data", "value_type", "text_color", "bar_gradient", "key_prefix"]
    missing = [k for k in required_keys if k not in config]
    if missing:
        st.error(f"Configurazione incompleta. Mancano: {missing}")
        return
    
    # Inizia la card HTML
    st.markdown(f"""
        <div style="padding:1rem 1.2rem; border-radius:12px; background:rgba(255,255,255,0.03); border:1px solid rgba(255,255,255,0.06); height: 100%;">
            <h3 style="margin-top:0;margin-bottom:0.5rem;">{title}</h3>
            <p style="margin-top:0;color:rgba(255,255,255,0.55);font-size:0.9rem;">{subtitle}</p>
    """, unsafe_allow_html=True)

    if not data:
        st.info("Nessun dato disponibile.")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    # Gestione della vista (Barre/Mappa) e del toggle "Mostra tutti"
    col1, col2 = st.columns([2, 3])
    view_mode = "Barre"  # Default a barre
    with col1:
        if show_map_toggle:
            # Toggle per scegliere vista Barre o Mappa
            view_mode = st.radio("Vista", ["Barre", "Mappa"], horizontal=True, key=f"{key_prefix}_view_mode", label_visibility="collapsed")
        else:
            st.markdown("<div style='height:28px;'></div>", unsafe_allow_html=True) # Spacer

    # Prepara DataFrame ordinato per valore decrescente
    df = pd.DataFrame(list(data.items()), columns=["Item", "Value"]).sort_values("Value", ascending=False)
    
    show_all = False
    if view_mode == "Barre":
        with col2:
            # Usa radio button per scelta chiara tra top N e tutti, con numeri dinamici
            if len(df) <= default_top_n:
                options = [f"Top {default_top_n}"]
            else:
                options = [f"Top {default_top_n}", f"Tutti ({len(df)})"]
            selected = st.radio(
                "Elementi da mostrare",
                options,
                index=0,  # Default a Top N
                horizontal=True,
                key=f"{key_prefix}_show_all_radio",
                label_visibility="collapsed"
            )
            show_all = len(options) > 1 and selected == options[1]

    if view_mode == "Barre":
        # Calcolo delle percentuali se necessario
        if value_type == "euro":
            total_sum = df["Value"].sum()
            df["Percentuale"] = (df["Value"] / total_sum * 100) if total_sum > 0 else 0
        else: # se è già in percentuale
            df.rename(columns={"Value": "Percentuale"}, inplace=True)

        max_val = df["Percentuale"].max()
        
        # Seleziona dati da mostrare (top N o tutti)
        df_to_show = df if show_all else df.head(default_top_n)

        # Renderizza barre personalizzate con HTML
        for _, row in df_to_show.iterrows():
            bar_width = int((row["Percentuale"] / max_val) * 100) if max_val > 0 else 0
            st.markdown(f"""
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <span style='font-weight:600;'>{row['Item']}</span>
                    <span style='color:{text_color};'>{row['Percentuale']:.2f}%</span>
                </div>
                <div style="background-color:#222; border-radius:4px; width:100%; height:6px; margin-top:2px; margin-bottom:10px;">
                    <div style="background:{bar_gradient}; width:{bar_width}%; height:6px; border-radius:4px;"></div>
                </div>
            """, unsafe_allow_html=True)

    elif view_mode == "Mappa":
        # Chiama funzione mappa passando parametri
         render_geo_map(data, value_type=value_type, toggle_key=f"{key_prefix}_map_projection", include_others=show_all)

    # Chiudi la card HTML
    st.markdown("</div>", unsafe_allow_html=True)