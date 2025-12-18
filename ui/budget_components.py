import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from database.connection import save_data
from services.budget_service import calculate_net_worth_trend
from ui.components import style_chart_for_mobile

def render_month_selector(df_budget: pd.DataFrame) -> str:
    """Renderizza il selettore del mese e il messaggio di aiuto."""
    df_budget['mese_anno'] = df_budget['date'].dt.strftime('%Y-%m')
    mesi_disponibili = sorted(df_budget['mese_anno'].unique(), reverse=True)
    
    col_sel, col_msg = st.columns([1, 3])
    selected_month = col_sel.selectbox("Seleziona Mese:", mesi_disponibili)
    col_msg.caption("💡 Per aggiungere nuovi movimenti, vai alla pagina 'Gestione Dati'.")
    return selected_month

def render_monthly_kpis(summary: dict, liquidity: float, liquidity_help: str):
    """Renderizza i KPI per il mese selezionato."""
    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Entrate Mese", f"€ {summary['entrate']:,.2f}")
    k2.metric("Uscite Mese", f"€ {summary['uscite']:,.2f}", delta=f"-{(summary['uscite']/summary['entrate'])*100:.1f}% delle entrate" if summary['entrate'] else "")
    k3.metric("Risparmio Mese", f"€ {summary['risparmio']:,.2f}", delta=f"{summary['savings_rate']:.1f}% Tasso di Risparmio")
    k4.metric("Investito Mese", f"€ {summary['investito_mese']:,.2f}", delta=f"{(summary['investito_mese']/summary['risparmio'])*100:.1f}% del risparmio" if summary['risparmio'] > 0 else "")
    k5.metric("Liquidità Totale", f"€ {liquidity:,.2f}", help=liquidity_help)

def render_monthly_charts(df_month: pd.DataFrame, summary: dict):
    """Renderizza i grafici a torta e a barre per il mese."""
    c1, c2 = st.columns(2)
    with c1:
        st.write("###### Spese per Categoria")
        df_spese = df_month[df_month['type'] == 'Uscita']
        if not df_spese.empty:
            fig_pie = px.pie(df_spese, values='amount', names='category', hole=0.4)
            fig_pie.update_layout(showlegend=False, margin=dict(l=10, r=10, t=10, b=10))
            st.plotly_chart(style_chart_for_mobile(fig_pie), width='stretch')
        else:
            st.info("Nessuna spesa registrata.")
    with c2:
        st.write("###### Flusso Mensile")
        fig_bar = go.Figure()
        fig_bar.add_trace(go.Bar(name='Entrate', x=['Flusso'], y=[summary['entrate']], marker_color='#28a745'))
        fig_bar.add_trace(go.Bar(name='Spese', x=['Flusso'], y=[summary['uscite']], marker_color='#dc3545'))
        fig_bar.add_trace(go.Bar(name='Investito', x=['Flusso'], y=[summary['investito_mese']], marker_color='#007bff'))
        fig_bar.update_layout(barmode='group', margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(style_chart_for_mobile(fig_bar), width='stretch')

def render_net_worth_section(df_nw: pd.DataFrame):
    """Renderizza la sezione completa del patrimonio netto (grafici e tabella)."""
    st.subheader("📈 Andamento Patrimonio Netto")
    if df_nw.empty or 'net_worth' not in df_nw.columns or df_nw['net_worth'].dropna().empty:
        st.info("Nessun dato storico sul patrimonio. Vai in 'Gestione Dati' per salvarli.")
        return

    df_nw = df_nw.sort_values('date').reset_index(drop=True)
    df_nw['monthly_increase'] = df_nw['net_worth'].diff()
    
    df_chart = df_nw.dropna(subset=['net_worth']).copy()
    df_goals = df_nw.dropna(subset=['goal']).copy()
    df_trend, _ = calculate_net_worth_trend(df_chart)

    fig_nw = go.Figure()
    fig_nw.add_trace(go.Scatter(x=df_chart['date'], y=df_chart['net_worth'], name='Patrimonio Netto', mode='lines+markers', line=dict(color='#00CC96', width=3)))
    if not df_goals.empty:
        fig_nw.add_trace(go.Scatter(x=df_goals['date'], y=df_goals['goal'], name='Obiettivo', mode='lines', line=dict(color='#EF553B', dash='dash')))
    if not df_trend.empty:
        fig_nw.add_trace(go.Scatter(x=df_trend['date'], y=df_trend['trend'], name='Trend', line=dict(dash='dot', color='rgba(255,255,0,0.6)')))
    
    fig_nw.update_layout(title="Patrimonio Netto vs Obiettivo")
    st.plotly_chart(style_chart_for_mobile(fig_nw), width='stretch')

    fig_increase = px.bar(df_chart[df_chart['monthly_increase'].notna() & (df_chart['monthly_increase'] != 0)], x='date', y='monthly_increase', title="Incremento Mensile del Patrimonio")
    fig_increase.update_traces(marker_color=['#28a745' if x >= 0 else '#dc3545' for x in df_chart['monthly_increase'].dropna()])
    st.plotly_chart(style_chart_for_mobile(fig_increase), width='stretch')

    st.write("###### Tabella Riassuntiva")
    df_display = df_nw[['date', 'net_worth', 'monthly_increase', 'goal']].copy()
    df_display['date'] = df_display['date'].dt.strftime('%m/%y')
    st.dataframe(df_display.dropna(subset=['net_worth']), width='stretch', hide_index=True,
        column_config={
            "date": "Data", "net_worth": st.column_config.NumberColumn("Patrimonio (€)", format="€ %.2f"),
            "monthly_increase": st.column_config.NumberColumn("Incremento (€)", format="€ %.2f"),
            "goal": st.column_config.NumberColumn("Obiettivo (€)", format="€ %.2f")
        }
    )

def render_transactions_editor(df_month: pd.DataFrame, df_budget_full: pd.DataFrame):
    """Renderizza l'editor per eliminare i movimenti del mese."""
    st.subheader("📝 Dettaglio Movimenti del Mese")
    with st.expander("Visualizza o Elimina Movimenti"):
        df_edit = df_month.copy()
        df_edit.insert(0, "Elimina", False)
        edited_df = st.data_editor(
            df_edit,
            column_config={"Elimina": st.column_config.CheckboxColumn(default=False), "date": st.column_config.DateColumn("Data", format="DD-MM-YYYY"), "amount": st.column_config.NumberColumn("Importo", format="€ %.2f")},
            disabled=["date", "type", "category", "amount", "note"],
            hide_index=True, width='stretch'
        )
        to_delete = edited_df[edited_df["Elimina"] == True]
        if not to_delete.empty:
            if st.button("🗑️ CONFERMA ELIMINAZIONE", type="primary"):
                indexes_to_drop = to_delete.index
                df_budget_updated = df_budget_full.drop(indexes_to_drop)
                save_data(df_budget_updated, "budget", method='replace') 
                st.success("✅ Eliminato! La pagina si aggiornerà.") 
                st.rerun()