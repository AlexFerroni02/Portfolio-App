import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import json
from typing import Optional
from ui.components import style_chart_for_mobile, color_pnl
from ui.charts import render_geo_map


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

# Ora usiamo render_geo_map da ui/charts.py
def _render_geo_map_globe(geo_dict: dict):
    """
    DEPRECATED: Usa render_geo_map da ui.charts invece.
    Manteniamo questo wrapper per retrocompatibilità.
    """
    render_geo_map(geo_dict, value_type="euro", toggle_key="map_projection_toggle")



def render_kpis(assets_view: pd.DataFrame):
    """Renderizza i KPI principali basandosi SOLO sugli asset."""
    tot_val_assets = assets_view['mkt_val'].sum()
    tot_inv_assets = assets_view['net_invested'].sum()
    tot_pnl_assets = tot_val_assets - tot_inv_assets
    
    c1, c2, c3 = st.columns(3)
    c1.metric("💰 Valore Portafoglio Attuale", f"€ {tot_val_assets:,.2f}")
    c2.metric("💳 Capitale Versato (Asset)", f"€ {tot_inv_assets:,.2f}")
    c3.metric("📈 P&L Netto (Asset)", f"€ {tot_pnl_assets:,.2f}", delta=f"{(tot_pnl_assets/tot_inv_assets)*100:.2f}%" if tot_inv_assets else "0%")
    st.divider()


def render_composition_tabs(full_view: pd.DataFrame, df_alloc: pd.DataFrame):
    """Renderizza i tab con i grafici di composizione (inclusa liquidità)."""
    st.subheader("🔬 Analisi Composizione Portafoglio")
    
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "Asset Class", 
        "Azioni/Obbligazioni/Gold", 
        "Tutti gli Asset", 
        "Dettaglio Azionario", 
        "Dettaglio Obbligazionario", 
        "🌍 Allocazione (X-Ray)"
    ])
    
    color_map = {
        'Azionario': '#3B82F6', 
        'Obbligazionario': '#EF4444', 
        'Gold': '#D4AF37', 
        'Liquidità': '#10B981', 
        'Altro': '#9CA3AF'
    }
    
    with tab1:
        composition_data = full_view.groupby('category')['mkt_val'].sum().reset_index()
        composition_data['percent'] = composition_data['mkt_val'] / composition_data['mkt_val'].sum() * 100
        
        fig_cat = go.Figure()
        
        fig_cat.add_trace(go.Pie(
            labels=composition_data['category'],
            values=composition_data['mkt_val'],
            hole=0.5,
            marker=dict(
                colors=[color_map.get(cat) for cat in composition_data['category']],
                line=dict(color='#1e1e1e', width=4)  # Bordo scuro
            ),
            direction='clockwise',
            rotation=270,
            textinfo='label+percent',
            texttemplate='<b>%{label}</b><br>%{percent}',
            textfont=dict(size=13, color='#e8e8e8'),  # Testo chiaro
            hovertemplate='%{label}<br>€%{value:,.2f}<br>%{percent}<extra></extra>',
            domain={'x': [0, 1], 'y': [0, 1]}
        ))
        
        # Valore totale al centro con stile dark
        total = composition_data['mkt_val'].sum()
        fig_cat.add_annotation(
            text=f"<b style='font-size:24px; color:#ffffff'>€{total:,.0f}</b><br><span style='font-size:14px; color:#a0a0a0'>Totale Portfolio</span>",
            x=0.5, y=0.5,
            font=dict(family='Arial Black'),
            showarrow=False
        )
        
        fig_cat.update_layout(
            title=dict(
                text='💼 Composizione Portfolio',
                font=dict(size=18, color='#ffffff')
            ),
            showlegend=True,
            height=550,
            font=dict(size=12, color='#e8e8e8'),
            paper_bgcolor='#0e1117',  # Sfondo dark Streamlit
            plot_bgcolor='#0e1117',
            legend=dict(
                font=dict(color='#e8e8e8'),
                bgcolor='rgba(30,30,30,0.5)',
                bordercolor='#333333',
                borderwidth=1
            )
        )
        
        st.plotly_chart(style_chart_for_mobile(fig_cat), use_container_width=True)


    
    with tab2:
        categories_to_show = ['Azionario', 'Obbligazionario', 'Gold']
        filtered_data = full_view[full_view['category'].isin(categories_to_show)]
        composition_data = filtered_data.groupby('category')['mkt_val'].sum().reset_index()
        composition_data['percent'] = composition_data['mkt_val'] / composition_data['mkt_val'].sum() * 100
        
        fig_simple = go.Figure()
        
        fig_simple.add_trace(go.Pie(
            labels=composition_data['category'],
            values=composition_data['mkt_val'],
            hole=0.5,
            marker=dict(
                colors=[color_map.get(cat) for cat in composition_data['category']],
                line=dict(color='#1e1e1e', width=4)
            ),
            direction='clockwise',
            rotation=270,
            textinfo='label+percent',
            texttemplate='<b>%{label}</b><br>%{percent}',
            textfont=dict(size=13, color='#e8e8e8'),
            hovertemplate='%{label}<br>€%{value:,.2f}<br>%{percent}<extra></extra>',
            domain={'x': [0, 1], 'y': [0, 1]}
        ))
        
        total = composition_data['mkt_val'].sum()
        fig_simple.add_annotation(
            text=f"<b style='font-size:24px; color:#ffffff'>€{total:,.0f}</b><br><span style='font-size:14px; color:#a0a0a0'>Valore Portafoglio</span>",
            x=0.5, y=0.5,
            font=dict(family='Arial Black'),
            showarrow=False
        )
        
        fig_simple.update_layout(
            title=dict(
                text='📊 Azioni / Obbligazioni / Gold',
                font=dict(size=18, color='#ffffff')
            ),
            showlegend=True,
            height=550,
            font=dict(size=12, color='#e8e8e8'),
            paper_bgcolor='#0e1117',
            plot_bgcolor='#0e1117',
            legend=dict(
                font=dict(color='#e8e8e8'),
                bgcolor='rgba(30,30,30,0.5)',
                bordercolor='#333333',
                borderwidth=1
            )
        )
        
        st.plotly_chart(style_chart_for_mobile(fig_simple), use_container_width=True)
    
    with tab3:
        plot_df = full_view[full_view['mkt_val'] > 0].copy()
        if not plot_df.empty:
            # Ordina per categoria e valore per raggruppare visivamente asset dello stesso tipo
            plot_df = plot_df.sort_values(['category', 'mkt_val'], ascending=[True, False])
            
            # Funzione per estrarre ticker senza suffisso (es. UST.MI -> UST)
            def extract_ticker(ticker):
                if pd.isna(ticker):
                    return 'CASH'
                ticker_str = str(ticker)
                if ticker_str.lower() in ['cash', 'liquidità', 'liquidita']:
                    return 'CASH'
                # Prende solo la parte prima del punto
                return ticker_str.split('.')[0]
            
            plot_df['ticker_short'] = plot_df['ticker'].apply(extract_ticker)
            plot_df['label'] = plot_df['ticker_short']
            
            total = plot_df['mkt_val'].sum()
            
            fig_all = go.Figure()
            
            # Aggiungi le fette del grafico a torta
            fig_all.add_trace(go.Pie(
                labels=plot_df['label'],
                values=plot_df['mkt_val'],
                hole=0.5,
                marker=dict(
                    colors=[color_map.get(cat, '#9CA3AF') for cat in plot_df['category']],
                    line=dict(color='#1e1e1e', width=2)
                ),
                direction='clockwise',
                rotation=270,
                textinfo='label+percent',
                texttemplate='<b>%{label}</b><br>%{percent}',
                textfont=dict(size=11, color='#e8e8e8'),
                hovertemplate='%{label}<br>€%{value:,.2f}<br>%{percent}<extra></extra>',
                domain={'x': [0, 1], 'y': [0, 1]},
                showlegend=False  # Nascondi la legenda automatica dei singoli asset
            ))
            
            # Crea legenda manuale solo per le categorie
            categories_present = plot_df['category'].unique()
            for cat in categories_present:
                fig_all.add_trace(go.Scatter(
                    x=[None], y=[None],
                    mode='markers',
                    marker=dict(size=10, color=color_map.get(cat, '#9CA3AF')),
                    legendgroup=cat,
                    showlegend=True,
                    name=cat
                ))
            
            fig_all.add_annotation(
                text=f"<b style='font-size:24px; color:#ffffff'>€{total:,.0f}</b><br><span style='font-size:14px; color:#a0a0a0'>Totale Assets</span>",
                x=0.5, y=0.5,
                font=dict(family='Arial Black'),
                showarrow=False
            )
            
            fig_all.update_layout(
                title=dict(
                    text='🎯 Tutti gli Asset (raggruppati per tipo)',
                    font=dict(size=18, color='#ffffff')
                ),
                showlegend=True,
                height=550,
                font=dict(size=12, color='#e8e8e8'),
                paper_bgcolor='#0e1117',
                plot_bgcolor='#0e1117',
                legend=dict(
                    font=dict(color='#e8e8e8'),
                    bgcolor='rgba(30,30,30,0.5)',
                    bordercolor='#333333',
                    borderwidth=1
                ),
                xaxis=dict(visible=False),
                yaxis=dict(visible=False)
            )
            
            st.plotly_chart(style_chart_for_mobile(fig_all), use_container_width=True)
        else:
            st.info("Nessun asset con valore da mostrare.")
    
    with tab4:
        df_azionario = full_view[full_view['category'] == 'Azionario'].copy()
        if not df_azionario.empty:
            df_azionario = df_azionario.sort_values('mkt_val', ascending=False)
            
            # Funzione per estrarre ticker senza suffisso
            def extract_ticker(ticker):
                if pd.isna(ticker):
                    return 'CASH'
                ticker_str = str(ticker)
                if ticker_str.lower() in ['cash', 'liquidità', 'liquidita']:
                    return 'CASH'
                return ticker_str.split('.')[0]
            
            df_azionario['ticker_short'] = df_azionario['ticker'].apply(extract_ticker)
            df_azionario['label'] = df_azionario['ticker_short']
            
            total = df_azionario['mkt_val'].sum()
            
            # Calcola percentuali per gradiente di colore
            df_azionario['pct'] = (df_azionario['mkt_val'] / total) * 100
            
            # Crea gradienti di blu basati sulla percentuale (più scuro = più alta)
            import plotly.colors
            blue_scale = plotly.colors.sequential.Blues
            n = len(df_azionario)
            # Usa la stessa logica del tab5 per consistenza visiva
            colors = [blue_scale[min(int((pct / df_azionario['pct'].max()) * (len(blue_scale) - 1)), len(blue_scale) - 1)] 
                     for pct in df_azionario['pct']]
            
            fig = go.Figure()
            
            fig.add_trace(go.Pie(
                labels=df_azionario['label'],
                values=df_azionario['mkt_val'],
                hole=0.5,
                marker=dict(
                    colors=colors,
                    line=dict(color='#1e1e1e', width=2)
                ),
                direction='clockwise',
                rotation=270,
                textinfo='label+percent',
                texttemplate='<b>%{label}</b><br>%{percent}',
                textfont=dict(size=12, color='#ffffff'),  # Testo bianco e più grande
                hovertemplate='%{label}<br>€%{value:,.2f}<br>%{percent}<extra></extra>',
                domain={'x': [0, 1], 'y': [0, 1]}
            ))
            
            fig.add_annotation(
                text=f"<b style='font-size:24px; color:#ffffff'>€{total:,.0f}</b><br><span style='font-size:14px; color:#a0a0a0'>Sezione Azionaria</span>",
                x=0.5, y=0.5,
                font=dict(family='Arial Black'),
                showarrow=False
            )
            
            fig.update_layout(
                title=dict(
                    text='📈 Dettaglio Sezione Azionaria',
                    font=dict(size=18, color='#ffffff')
                ),
                showlegend=True,
                height=550,
                font=dict(size=12, color='#e8e8e8'),
                paper_bgcolor='#0e1117',
                plot_bgcolor='#0e1117',
                legend=dict(
                    font=dict(color='#e8e8e8'),
                    bgcolor='rgba(30,30,30,0.5)',
                    bordercolor='#333333',
                    borderwidth=1
                )
            )
            
            st.plotly_chart(style_chart_for_mobile(fig), use_container_width=True)
        else:
            st.info("Nessun asset azionario in portafoglio.")
    
    with tab5:
        df_obbligazionario = full_view[full_view['category'] == 'Obbligazionario'].copy()
        if not df_obbligazionario.empty:
            df_obbligazionario = df_obbligazionario.sort_values('mkt_val', ascending=False)
            
            # Funzione per estrarre ticker senza suffisso
            def extract_ticker(ticker):
                if pd.isna(ticker):
                    return 'CASH'
                ticker_str = str(ticker)
                if ticker_str.lower() in ['cash', 'liquidità', 'liquidita']:
                    return 'CASH'
                return ticker_str.split('.')[0]
            
            df_obbligazionario['ticker_short'] = df_obbligazionario['ticker'].apply(extract_ticker)
            df_obbligazionario['label'] = df_obbligazionario['ticker_short']
            
            total = df_obbligazionario['mkt_val'].sum()
            
            # Calcola percentuali per gradiente di colore
            df_obbligazionario['pct'] = (df_obbligazionario['mkt_val'] / total) * 100
            
            # Crea gradienti di rosso basati sulla percentuale (più scuro = più alta)
            import plotly.colors
            red_scale = plotly.colors.sequential.Reds
            n = len(df_obbligazionario)
            # Inverti per avere il più scuro per i valori più alti
            colors = [red_scale[min(int((pct / df_obbligazionario['pct'].max()) * (len(red_scale) - 1)), len(red_scale) - 1)] 
                     for pct in df_obbligazionario['pct']]
            
            fig = go.Figure()
            
            fig.add_trace(go.Pie(
                labels=df_obbligazionario['label'],
                values=df_obbligazionario['mkt_val'],
                hole=0.5,
                marker=dict(
                    colors=colors,
                    line=dict(color='#1e1e1e', width=2)
                ),
                direction='clockwise',
                rotation=270,
                textinfo='label+percent',
                texttemplate='<b>%{label}</b><br>%{percent}',
                textfont=dict(size=12, color='#ffffff'),
                hovertemplate='%{label}<br>€%{value:,.2f}<br>%{percent}<extra></extra>',
                domain={'x': [0, 1], 'y': [0, 1]}
            ))
            
            fig.add_annotation(
                text=f"<b style='font-size:24px; color:#ffffff'>€{total:,.0f}</b><br><span style='font-size:14px; color:#a0a0a0'>Sezione Obbligazionaria</span>",
                x=0.5, y=0.5,
                font=dict(family='Arial Black'),
                showarrow=False
            )
            
            fig.update_layout(
                title=dict(
                    text='📉 Dettaglio Sezione Obbligazionario',
                    font=dict(size=18, color='#ffffff')
                ),
                showlegend=True,
                height=550,
                font=dict(size=12, color='#e8e8e8'),
                paper_bgcolor='#0e1117',
                plot_bgcolor='#0e1117',
                legend=dict(
                    font=dict(color='#e8e8e8'),
                    bgcolor='rgba(30,30,30,0.5)',
                    bordercolor='#333333',
                    borderwidth=1
                )
            )
            
            st.plotly_chart(style_chart_for_mobile(fig), use_container_width=True)
        else:
            st.info("Nessun asset obbligazionario in portafoglio.")
    
    with tab6:
        st.caption("Questa analisi mostra l'esposizione geografica e settoriale aggregata, pesata per il valore di ogni asset.")
        view_alloc = full_view.merge(df_alloc, on='ticker', how='left') if not df_alloc.empty else full_view.copy()
        total_val = view_alloc['mkt_val'].sum()
        
        if total_val > 0:
            total_geo, total_sec = {}, {}
            
            for _, row in view_alloc.iterrows():
                val_etf = row['mkt_val']
                if val_etf == 0 or pd.isna(val_etf):
                    continue
                
                try:
                    geo_raw = row.get('geography_json', '{}')
                    sec_raw = row.get('sector_json', '{}')
                    g_map = geo_raw if isinstance(geo_raw, dict) else json.loads(geo_raw or '{}')
                    s_map = sec_raw if isinstance(sec_raw, dict) else json.loads(sec_raw or '{}')
                except (json.JSONDecodeError, TypeError):
                    g_map, s_map = {}, {}
                
                for country, perc in g_map.items():
                    euro_exposure = val_etf * (float(perc) / 100)
                    total_geo[country] = total_geo.get(country, 0) + euro_exposure
                
                for sector, perc in s_map.items():
                    euro_exposure = val_etf * (float(perc) / 100)
                    total_sec[sector] = total_sec.get(sector, 0) + euro_exposure
            
            c_geo, c_sec = st.columns(2)
            
            # ---------- CARD GEOGRAFICA ----------
            with c_geo:
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
                
                if total_geo:
                    df_g = pd.DataFrame(list(total_geo.items()), columns=["Paese", "Valore"])
                    df_g = df_g.sort_values("Valore", ascending=False)
                    total_geo_sum = df_g["Valore"].sum()
                    df_g["Percentuale"] = (df_g["Valore"] / total_geo_sum * 100) if total_geo_sum > 0 else 0
                    max_val_g = df_g["Percentuale"].max()
                    
                    # Toggle Barre/Mappa dentro la card
                    view_mode_geo = st.radio(
                        "Vista",
                        ["Barre", "Mappa"],
                        horizontal=True,
                        key="geo_view_mode_dashboard",
                        label_visibility="collapsed"
                    )
                    
                    if view_mode_geo == "Barre":
                        # Vista a barre
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
                        _render_geo_map_globe(total_geo)
                else:
                    st.info("Nessun dato geografico. Vai su 'Gestione Dati' per scaricarlo.")
                
                st.markdown("</div>", unsafe_allow_html=True)
            
            # ---------- CARD SETTORIALE (solo barre) ----------
            with c_sec:
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
                
                if total_sec:
                    # Spazio per allineare con il toggle della colonna geografica
                    st.markdown("<div style='height:56px;'></div>", unsafe_allow_html=True)
                    
                    df_s = pd.DataFrame(list(total_sec.items()), columns=["Settore", "Valore"])
                    df_s = df_s.sort_values("Valore", ascending=False)
                    total_sec_sum = df_s["Valore"].sum()
                    df_s["Percentuale"] = (df_s["Valore"] / total_sec_sum * 100) if total_sec_sum > 0 else 0
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
                    st.info("Nessun dato settoriale. Vai su 'Gestione Dati' per scaricarlo.")
                
                st.markdown("</div>", unsafe_allow_html=True)
        else:
            st.warning("Il valore del portafoglio è zero o i prezzi non sono aggiornati.")


def render_assets_table(full_view: pd.DataFrame):
    """Renderizza la tabella con il dettaglio degli asset e gestisce la selezione."""
    st.divider()
    st.subheader("📋 Dettaglio Asset (Clicca per Analisi)")
    
    assets_only_view = full_view[full_view['ticker'] != 'CASH']
    display_df = assets_only_view[['product', 'ticker', 'quantity', 'net_invested', 'mkt_val', 'pnl%']].sort_values('mkt_val', ascending=False)
    
    selection = st.dataframe(
        display_df.style.format({
            'quantity': "{:.2f}", 
            'net_invested': "€ {:.2f}", 
            'mkt_val': "€ {:.2f}", 
            'pnl%': "{:.2f}%"
        }).applymap(color_pnl, subset=['pnl%']),
        use_container_width=True,
        selection_mode="single-row",
        on_select="rerun",
        hide_index=True
    )
    
    if selection.selection.rows:
        idx = selection.selection.rows[0]
        sel_ticker = display_df.iloc[idx]['ticker']
        if sel_ticker != 'CASH':
            st.session_state['selected_ticker'] = sel_ticker
            st.switch_page("pages/1_Analisi_Asset.py")


def render_historical_chart(hdf: pd.DataFrame):
    """Renderizza il grafico dell'andamento temporale."""
    st.divider()
    st.subheader("📉 Andamento Temporale")
    
    if not hdf.empty:
        fig_hist = go.Figure()
        fig_hist.add_trace(go.Scatter(
            x=hdf['Data'], 
            y=hdf['Valore'], 
            fill='tozeroy', 
            name='Valore Attuale', 
            line_color='#00CC96'
        ))
        fig_hist.add_trace(go.Scatter(
            x=hdf['Data'], 
            y=hdf['Investito'], 
            name='Soldi Versati', 
            line=dict(color='#EF553B', dash='dash')
        ))
        st.plotly_chart(style_chart_for_mobile(fig_hist), use_container_width=True)
    else:
        st.info("Dati insufficienti per il grafico storico.")
