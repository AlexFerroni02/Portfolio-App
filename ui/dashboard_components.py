import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import json
from typing import Optional
from ui.components import style_chart_for_mobile, color_pnl
from ui.charts import plot_portfolio_history, render_allocation_card, ALLOCATION_CONFIG_DASH

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


def _render_asset_class_pie(full_view: pd.DataFrame, color_map: dict):
    """Renderizza il grafico a torta della composizione per asset class."""
    composition_data = full_view.groupby('category')['mkt_val'].sum().reset_index()
    composition_data['percent'] = composition_data['mkt_val'] / composition_data['mkt_val'].sum() * 100
    
    fig_cat = go.Figure()
    
    fig_cat.add_trace(go.Pie(
        labels=composition_data['category'],
        values=composition_data['mkt_val'],
        hole=0.5,
        marker=dict(
            colors=[color_map.get(cat) for cat in composition_data['category']],
            line=dict(color='#1e1e1e', width=4)
        ),
        direction='clockwise',
        rotation=270,
        textinfo='percent',
        textfont=dict(size=16, color='#ffffff'),
        hovertemplate='%{label}<br>€%{value:,.2f}<br>%{percent}<extra></extra>',
        domain={'x': [0, 1], 'y': [0, 1]}
    ))
    
    total = composition_data['mkt_val'].sum()
    fig_cat.add_annotation(
        text=f"<b style='font-size:24px; color:#ffffff'>€{total:,.0f}</b>",
        x=0.5, y=0.5,
        font=dict(family='Arial Black'),
        showarrow=False
    )
    
    fig_cat.update_layout(
        title=dict(text='💼 Composizione Portfolio', font=dict(size=18, color='#ffffff')),
        showlegend=True,
        height=650,
        font=dict(size=20, color='#e8e8e8'),
        paper_bgcolor='#0e1117',
        plot_bgcolor='#0e1117',
        legend=dict(
            font=dict(color='#e8e8e8'),
            bgcolor='rgba(30,30,30,0.5)',
            bordercolor='#333333',
            borderwidth=1
        )
    )
    
    st.plotly_chart(style_chart_for_mobile(fig_cat), use_container_width=True)


def _render_sunburst_chart(full_view: pd.DataFrame, color_map: dict):
    """Renderizza il grafico sunburst per macro categorie e asset."""
    categories_to_show = ['Azionario', 'Obbligazionario', 'Gold']
    plot_df = full_view[(full_view['mkt_val'] > 0) & (full_view['category'].isin(categories_to_show))].copy()
    
    if plot_df.empty:
        st.info("Nessun asset da mostrare per il grafico sunburst.")
        return

    def extract_ticker(ticker):
        return str(ticker).split('.')[0] if pd.notna(ticker) else 'N/A'
    
    plot_df['ticker_short'] = plot_df['ticker'].apply(extract_ticker)
    plot_df = plot_df.sort_values(['category', 'mkt_val'], ascending=[True, False])
    
    blue_scale = px.colors.sequential.Blues
    red_scale = px.colors.sequential.Reds
    gold_transparent = 'rgba(212,175,55,0.6)'
    
    labels, parents, values, colors_list = [], [], [], []
    
    root_val = plot_df['mkt_val'].sum()
    labels.append(f'€{root_val:,.0f}')
    parents.append('')
    values.append(root_val)
    colors_list.append('#0e1117')
    
    for cat in plot_df['category'].unique():
        labels.append(cat)
        parents.append(labels[0])
        cat_df = plot_df[plot_df['category'] == cat]
        cat_val = cat_df['mkt_val'].sum()
        values.append(cat_val)
        colors_list.append(color_map.get(cat, '#9CA3AF'))
        
        cat_df = cat_df.reset_index(drop=True)
        n_assets = len(cat_df)
        
        for idx, row in cat_df.iterrows():
            labels.append(row['ticker_short'])
            parents.append(cat)
            values.append(row['mkt_val'])
            
            color_intensity = (n_assets - idx - 1) / (n_assets - 1) if n_assets > 1 else 1.0
            
            if cat == 'Azionario':
                color_idx = min(int(color_intensity * 5) + 3, len(blue_scale) - 1)
                colors_list.append(blue_scale[color_idx])
            elif cat == 'Obbligazionario':
                color_idx = min(int(color_intensity * 5) + 3, len(red_scale) - 1)
                colors_list.append(red_scale[color_idx])
            elif cat == 'Gold':
                colors_list.append(gold_transparent)
            else:
                colors_list.append('#9CA3AF')

    fig_sunburst = go.Figure(go.Sunburst(
        labels=labels,
        parents=parents,
        values=values,
        marker=dict(colors=colors_list, line=dict(color='#1e1e1e', width=2)),
        textinfo='label+percent root',
        textfont=dict(size=16, color='#ffffff'),
        hovertemplate='<b>%{label}</b><br>€%{value:,.2f}<extra></extra>',
        branchvalues='total'
    ))
    
    fig_sunburst.update_layout(
        title=dict(text='📊 Macro Categorie e Asset', font=dict(size=18, color='#ffffff')),
        height=650,
        margin=dict(l=10, r=10, t=80, b=10),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(size=13, color='#e8e8e8'),
        legend=dict(
            orientation='h', yanchor='top', y=1.02, xanchor='center', x=0.5,
            bgcolor='rgba(30,30,30,0.5)', bordercolor='#333333', borderwidth=1,
            font=dict(size=12, color='#e8e8e8')
        )
    )
    st.plotly_chart(style_chart_for_mobile(fig_sunburst), use_container_width=True)


def _render_detail_pie_chart(full_view: pd.DataFrame, category: str, color_scale: list, title: str):
    """Funzione generica per renderizzare grafici a torta di dettaglio."""
    df_category = full_view[full_view['category'] == category].copy()
    if df_category.empty:
        st.info(f"Nessun asset {category.lower()} in portafoglio.")
        return

    df_category = df_category.sort_values('mkt_val', ascending=False)
    
    def extract_ticker(ticker):
        return str(ticker).split('.')[0] if pd.notna(ticker) else 'N/A'
    
    df_category['ticker_short'] = df_category['ticker'].apply(extract_ticker)
    total = df_category['mkt_val'].sum()
    
    n = len(df_category)
    colors = []
    for idx in range(n):
        color_intensity = (n - idx - 1) / (n - 1) if n > 1 else 1.0
        color_idx = min(int(color_intensity * 5) + 3, len(color_scale) - 1)
        colors.append(color_scale[color_idx])

    fig = go.Figure(go.Pie(
        labels=df_category['ticker_short'],
        values=df_category['mkt_val'],
        hole=0.5,
        marker=dict(colors=colors, line=dict(color='#1e1e1e', width=2)),
        direction='clockwise',
        rotation=270,
        textinfo='label+percent',
        texttemplate='<b>%{label}</b><br>%{percent}',
        textfont=dict(size=16, color='#ffffff'),
        hovertemplate='%{label}<br>€%{value:,.2f}<br>%{percent}<extra></extra>'
    ))
    
    fig.add_annotation(
        text=f"<b style='font-size:24px; color:#ffffff'>€{total:,.0f}</b>",
        x=0.5, y=0.5, font=dict(family='Arial Black'), showarrow=False
    )
    
    fig.update_layout(
        title=dict(text=title, font=dict(size=18, color='#ffffff')),
        showlegend=False,
        height=650,
        paper_bgcolor='#0e1117',
        plot_bgcolor='#0e1117'
    )
    st.plotly_chart(style_chart_for_mobile(fig), use_container_width=True)


def _render_xray_allocation_tab(full_view: pd.DataFrame, df_alloc: pd.DataFrame):
    """Renderizza il tab con l'analisi X-Ray (geografica e settoriale)."""
    st.caption("Questa analisi mostra l'esposizione geografica e settoriale aggregata, pesata per il valore di ogni asset.")
    view_alloc = full_view.merge(df_alloc, on='ticker', how='left') if not df_alloc.empty else full_view.copy()
    total_val = view_alloc['mkt_val'].sum()
    
    if total_val <= 0:
        st.warning("Il valore del portafoglio è zero o i prezzi non sono aggiornati.")
        return

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
            continue
        
        for country, perc in g_map.items():
            total_geo[country] = total_geo.get(country, 0) + (val_etf * (float(perc) / 100))
        for sector, perc in s_map.items():
            total_sec[sector] = total_sec.get(sector, 0) + (val_etf * (float(perc) / 100))

    c_geo, c_sec = st.columns(2)
    
    with c_geo:
        render_allocation_card(ALLOCATION_CONFIG_DASH["geo"] | {"data": total_geo})
    
    with c_sec:
        render_allocation_card(ALLOCATION_CONFIG_DASH["sec"] | {"data": total_sec})


def render_composition_tabs(full_view: pd.DataFrame, df_alloc: pd.DataFrame):
    """Renderizza i tab con i grafici di composizione (inclusa liquidità)."""
    st.subheader("🔬 Analisi Composizione Portafoglio")
    
    tabs = st.tabs([
        "Asset Class", 
        "Macro + Dettaglio Asset", 
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
    
    with tabs[0]:
        _render_asset_class_pie(full_view, color_map)
    
    with tabs[1]:
        _render_sunburst_chart(full_view, color_map)
    
    with tabs[2]:
        _render_detail_pie_chart(
            full_view, 
            category='Azionario', 
            color_scale=px.colors.sequential.Blues, 
            title='📈 Dettaglio Sezione Azionaria'
        )
    
    with tabs[3]:
        _render_detail_pie_chart(
            full_view, 
            category='Obbligazionario', 
            color_scale=px.colors.sequential.Reds, 
            title='📉 Dettaglio Sezione Obbligazionaria'
        )
    
    with tabs[4]:
        _render_xray_allocation_tab(full_view, df_alloc)

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
        }).map(color_pnl, subset=['pnl%']),
        width='stretch',
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
        # SOSTITUITO: Il vecchio 'go.Figure(...)' è stato rimpiazzato da questa chiamata.
        fig_hist = plot_portfolio_history(hdf)
        if fig_hist:
            st.plotly_chart(fig_hist, use_container_width=True)
    else:
        st.info("Dati insufficienti per il grafico storico.")
