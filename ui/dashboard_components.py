import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import json
from ui.components import style_chart_for_mobile, color_pnl

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
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["Asset Class", "Azioni/Obbligazioni/Gold", "Tutti gli Asset", "Dettaglio Azionario", "Dettaglio Obbligazionario", "🌍 Allocazione (X-Ray)"])
    color_map = {'Azionario': '#3B82F6', 'Obbligazionario': '#EF4444', 'Gold': '#D4AF37', 'Liquidità': '#10B981', 'Altro': '#9CA3AF'}
    
    with tab1:
        composition_data = full_view.groupby('category')['mkt_val'].sum().reset_index()
        fig_cat = px.pie(composition_data, values='mkt_val', names='category', title='Suddivisione per Asset Class', color='category', color_discrete_map=color_map)
        fig_cat.update_traces(textinfo='percent+value', texttemplate='%{percent} <br>€%{value:,.0f}', hovertemplate='<b>%{label}</b><br>Valore: €%{value:,.2f}<br>(%{percent})<extra></extra>')
        st.plotly_chart(style_chart_for_mobile(fig_cat), use_container_width=True)
    
    with tab2:
        categories_to_show = ['Azionario', 'Obbligazionario', 'Gold']
        filtered_data = full_view[full_view['category'].isin(categories_to_show)]
        composition_data = filtered_data.groupby('category')['mkt_val'].sum().reset_index()
        fig_simple = px.pie(composition_data, values='mkt_val', names='category', title='Ripartizione: Azioni / Obbligazioni / Gold', color='category', color_discrete_map=color_map)
        fig_simple.update_traces(textinfo='percent+value', texttemplate='%{percent} <br>€%{value:,.0f}', hovertemplate='<b>%{label}</b><br>Valore: €%{value:,.2f}<br>(%{percent})<extra></extra>')
        st.plotly_chart(style_chart_for_mobile(fig_simple), use_container_width=True)
    
    with tab3:
        plot_df = full_view[full_view['mkt_val'] > 0].copy()
        if not plot_df.empty:
            total = plot_df['mkt_val'].sum()
            plot_df['pct'] = (plot_df['mkt_val'] / total) * 100
            plot_df['text'] = plot_df['pct'].apply(lambda x: f"{x:.1f}%" if x >= 0.5 else "")
            fig_all = px.pie(plot_df, values='mkt_val', names='product', title='Composizione per singolo Asset', color='category', color_discrete_map=color_map)
            fig_all.update_traces(text=plot_df['text'], textinfo='text', hovertemplate='<b>%{label}</b><br>Valore: €%{value:,.2f}<br>(%{percent})<extra></extra>', showlegend=False)
            st.plotly_chart(style_chart_for_mobile(fig_all), use_container_width=True)
        else:
            st.info("Nessun asset con valore da mostrare.")
            
    with tab4:
        df_azionario = full_view[full_view['category'] == 'Azionario']
        if not df_azionario.empty:
            fig = px.pie(df_azionario, values='mkt_val', names='product', title='Composizione Portafoglio Azionario')
            fig.update_traces(textinfo='percent', hovertemplate='<b>%{label}</b><br>Valore: €%{value:,.2f}<br>(%{percent})<extra></extra>', showlegend=False)
            st.plotly_chart(style_chart_for_mobile(fig), use_container_width=True)
        else: st.info("Nessun asset azionario in portafoglio.")
        
    with tab5:
        df_obbligazionario = full_view[full_view['category'] == 'Obbligazionario']
        if not df_obbligazionario.empty:
            fig = px.pie(df_obbligazionario, values='mkt_val', names='product', title='Composizione Portafoglio Obbligazionario')
            fig.update_traces(textinfo='percent', hovertemplate='<b>%{label}</b><br>Valore: €%{value:,.2f}<br>(%{percent})<extra></extra>', showlegend=False)
            st.plotly_chart(style_chart_for_mobile(fig), use_container_width=True)
        else: st.info("Nessun asset obbligazionario in portafoglio.")
        
    with tab6:
        st.caption("Questa analisi mostra l'esposizione geografica e settoriale aggregata, pesata per il valore di ogni asset.")
        view_alloc = full_view.merge(df_alloc, on='ticker', how='left') if not df_alloc.empty else full_view.copy()
        total_val = view_alloc['mkt_val'].sum()
        if total_val > 0:
            total_geo, total_sec = {}, {}
            for _, row in view_alloc.iterrows():
                val_etf = row['mkt_val']
                if val_etf == 0 or pd.isna(val_etf): continue
                
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
            with c_geo:
                if total_geo:
                    df_g = pd.DataFrame(list(total_geo.items()), columns=['Paese', 'Valore'])
                    fig1 = px.pie(df_g, values='Valore', names='Paese', hole=0.4, title="Esposizione Geografica Totale")
                    fig1.update_traces(textinfo='percent', hovertemplate='<b>%{label}</b><br>€%{value:,.0f}<br>%{percent}<extra></extra>', showlegend=False)
                    st.plotly_chart(style_chart_for_mobile(fig1), use_container_width=True)
                else: st.info("Nessun dato geografico. Vai su 'Gestione Dati' per scaricarlo.")
            with c_sec:
                if total_sec:
                    df_s = pd.DataFrame(list(total_sec.items()), columns=['Settore', 'Valore'])
                    fig2 = px.pie(df_s, values='Valore', names='Settore', hole=0.4, title="Esposizione Settoriale Totale")
                    fig2.update_traces(textinfo='percent', hovertemplate='<b>%{label}</b><br>€%{value:,.0f}<br>%{percent}<extra></extra>', showlegend=False)
                    st.plotly_chart(style_chart_for_mobile(fig2), use_container_width=True)
                else: st.info("Nessun dato settoriale. Vai su 'Gestione Dati' per scaricarlo.")
        else:
            st.warning("Il valore del portafoglio è zero o i prezzi non sono aggiornati.")

def render_assets_table(full_view: pd.DataFrame):
    """Renderizza la tabella con il dettaglio degli asset e gestisce la selezione."""
    st.divider()
    st.subheader("📋 Dettaglio Asset (Clicca per Analisi)")
    assets_only_view = full_view[full_view['ticker'] != 'CASH']
    display_df = assets_only_view[['product', 'ticker', 'quantity', 'net_invested', 'mkt_val', 'pnl%']].sort_values('mkt_val', ascending=False)
    selection = st.dataframe(
        display_df.style.format({'quantity': "{:.2f}", 'net_invested': "€ {:.2f}", 'mkt_val': "€ {:.2f}", 'pnl%': "{:.2f}%"}).applymap(color_pnl, subset=['pnl%']),
        use_container_width=True, selection_mode="single-row", on_select="rerun", hide_index=True)
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
        fig_hist.add_trace(go.Scatter(x=hdf['Data'], y=hdf['Valore'], fill='tozeroy', name='Valore Attuale', line_color='#00CC96'))
        fig_hist.add_trace(go.Scatter(x=hdf['Data'], y=hdf['Investito'], name='Soldi Versati', line=dict(color='#EF553B', dash='dash')))
        st.plotly_chart(style_chart_for_mobile(fig_hist), use_container_width=True)
    else:
        st.info("Dati insufficienti per il grafico storico.")