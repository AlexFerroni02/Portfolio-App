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


# =============================================
# NUOVI GRAFICI PER ANALISI BUDGET
# =============================================

def render_expense_trend_chart(df_budget: pd.DataFrame, months: int = 6):
    """Mostra il trend delle spese negli ultimi N mesi."""
    st.subheader(f"📊 Trend Spese (Ultimi {months} Mesi)")
    
    if df_budget.empty:
        st.info("Nessun dato disponibile.")
        return
    
    df = df_budget.copy()
    df['mese'] = df['date'].dt.to_period('M').astype(str)
    
    # Filtra ultimi N mesi
    mesi_unici = sorted(df['mese'].unique(), reverse=True)[:months]
    df_filtered = df[df['mese'].isin(mesi_unici)]
    
    # Aggrega per mese e tipo
    df_agg = df_filtered.groupby(['mese', 'type'])['amount'].sum().reset_index()
    df_pivot = df_agg.pivot(index='mese', columns='type', values='amount').fillna(0).reset_index()
    df_pivot = df_pivot.sort_values('mese')
    
    # Crea grafico
    fig = go.Figure()
    
    if 'Uscita' in df_pivot.columns:
        fig.add_trace(go.Scatter(
            x=df_pivot['mese'], y=df_pivot['Uscita'],
            name='Spese', mode='lines+markers',
            line=dict(color='#dc3545', width=3),
            fill='tozeroy', fillcolor='rgba(220, 53, 69, 0.2)'
        ))
    
    if 'Entrata' in df_pivot.columns:
        fig.add_trace(go.Scatter(
            x=df_pivot['mese'], y=df_pivot['Entrata'],
            name='Entrate', mode='lines+markers',
            line=dict(color='#28a745', width=3)
        ))
    
    fig.update_layout(
        title=None,
        xaxis_title="Mese",
        yaxis_title="Importo (€)",
        hovermode='x unified',
        margin=dict(l=10, r=10, t=10, b=10)
    )
    st.plotly_chart(style_chart_for_mobile(fig), use_container_width=True)


def render_investment_trend(df_budget: pd.DataFrame, months: int = 6):
    """Mostra il trend degli investimenti negli ultimi N mesi."""
    st.subheader(f"📈 Trend Investimenti (Ultimi {months} Mesi)")
    
    if df_budget.empty:
        st.info("Nessun dato disponibile.")
        return
    
    df = df_budget.copy()
    df['mese'] = df['date'].dt.to_period('M').astype(str)
    
    # Filtra ultimi N mesi e solo investimenti
    mesi_unici = sorted(df['mese'].unique(), reverse=True)[:months]
    df_filtered = df[(df['mese'].isin(mesi_unici)) & (df['type'] == 'Uscita') & (df['category'] == 'Investimento')]
    
    if df_filtered.empty:
        st.info("Nessun investimento registrato negli ultimi mesi.")
        return
    
    # Aggrega per mese
    df_agg = df_filtered.groupby('mese')['amount'].sum().reset_index()
    df_agg = df_agg.sort_values('mese')
    
    # Crea grafico
    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        x=df_agg['mese'], 
        y=df_agg['amount'],
        marker_color='#007bff',
        text=[f"€ {v:,.0f}" for v in df_agg['amount']],
        textposition='outside'
    ))
    
    # Linea media
    media_inv = df_agg['amount'].mean()
    fig.add_hline(y=media_inv, line_dash="dash", line_color="orange", 
                  annotation_text=f"Media: € {media_inv:,.0f}", annotation_position="right")
    
    fig.update_layout(
        title=None,
        xaxis_title="Mese",
        yaxis_title="Importo Investito (€)",
        margin=dict(l=10, r=10, t=10, b=10)
    )
    st.plotly_chart(style_chart_for_mobile(fig), use_container_width=True)


def render_savings_rate_trend(df_budget: pd.DataFrame, months: int = 6):
    """Mostra l'andamento del tasso di risparmio."""
    st.subheader(f"📈 Andamento Tasso di Risparmio")
    
    if df_budget.empty:
        st.info("Nessun dato disponibile.")
        return
    
    df = df_budget.copy()
    df['mese'] = df['date'].dt.to_period('M').astype(str)
    
    # Calcola entrate e uscite per mese
    mesi_unici = sorted(df['mese'].unique(), reverse=True)[:months]
    df_filtered = df[df['mese'].isin(mesi_unici)]
    
    df_agg = df_filtered.groupby(['mese', 'type'])['amount'].sum().reset_index()
    df_pivot = df_agg.pivot(index='mese', columns='type', values='amount').fillna(0).reset_index()
    
    # Calcola savings rate
    if 'Entrata' in df_pivot.columns and 'Uscita' in df_pivot.columns:
        df_pivot['risparmio'] = df_pivot['Entrata'] - df_pivot['Uscita']
        df_pivot['savings_rate'] = (df_pivot['risparmio'] / df_pivot['Entrata'] * 100).clip(lower=-100, upper=100)
    else:
        st.info("Dati insufficienti per calcolare il tasso di risparmio.")
        return
    
    df_pivot = df_pivot.sort_values('mese')
    
    # Colori basati sul valore
    colors = ['#28a745' if x >= 20 else '#ffc107' if x >= 0 else '#dc3545' for x in df_pivot['savings_rate']]
    
    fig = go.Figure(data=[
        go.Bar(
            x=df_pivot['mese'], 
            y=df_pivot['savings_rate'],
            marker_color=colors,
            text=[f"{x:.1f}%" for x in df_pivot['savings_rate']],
            textposition='outside'
        )
    ])
    
    # Linea obiettivo 20%
    fig.add_hline(y=20, line_dash="dash", line_color="green", 
                  annotation_text="Obiettivo 20%", annotation_position="right")
    
    fig.update_layout(
        xaxis_title="Mese",
        yaxis_title="Tasso Risparmio (%)",
        margin=dict(l=10, r=10, t=10, b=10),
        yaxis=dict(range=[-50, 100])
    )
    st.plotly_chart(style_chart_for_mobile(fig), use_container_width=True)


def render_budget_rule_check(df_budget: pd.DataFrame, selected_month: str):
    """Verifica la regola 50/30/20: 50% necessità, 30% desideri, 20% risparmio+investimento."""
    st.subheader("🎯 Verifica Regola 50/30/20")
    
    # Categorie classificate
    NECESSITA = ["Affitto/Casa", "Spesa Alimentare", "Trasporti", "Bollette", "Salute"]
    DESIDERI = ["Ristoranti/Svago", "Shopping", "Viaggi"]
    
    df_month = df_budget[df_budget['date'].dt.strftime('%Y-%m') == selected_month].copy()
    
    if df_month.empty:
        st.info("Nessun dato per questo mese.")
        return
    
    entrate = df_month[df_month['type'] == 'Entrata']['amount'].sum()
    if entrate == 0:
        st.warning("Nessuna entrata registrata per questo mese.")
        return
    
    # Calcola spese per categoria (escluso Investimento)
    df_spese = df_month[(df_month['type'] == 'Uscita') & (df_month['category'] != 'Investimento')]
    spese_necessita = df_spese[df_spese['category'].isin(NECESSITA)]['amount'].sum()
    spese_desideri = df_spese[df_spese['category'].isin(DESIDERI)]['amount'].sum()
    
    # Investimenti e risparmio
    investimenti = df_month[(df_month['type'] == 'Uscita') & (df_month['category'] == 'Investimento')]['amount'].sum()
    spese_totali = df_spese['amount'].sum()
    risparmio_puro = entrate - spese_totali - investimenti  # Liquidità risparmiata
    risparmio_totale = risparmio_puro + investimenti  # Risparmio + Investimento per regola 50/30/20
    
    # Percentuali
    pct_necessita = (spese_necessita / entrate) * 100
    pct_desideri = (spese_desideri / entrate) * 100
    pct_risparmio_totale = (risparmio_totale / entrate) * 100
    pct_investimenti = (investimenti / entrate) * 100
    pct_risparmio_puro = (risparmio_puro / entrate) * 100
    
    # Layout a colonne
    c1, c2, c3 = st.columns(3)
    
    with c1:
        delta_n = pct_necessita - 50
        st.metric(
            "🏠 Necessità", 
            f"{pct_necessita:.1f}%",
            delta=f"{delta_n:+.1f}% vs 50%",
            delta_color="inverse"
        )
        st.caption(f"€ {spese_necessita:,.2f}")
    
    with c2:
        delta_d = pct_desideri - 30
        st.metric(
            "🎉 Desideri", 
            f"{pct_desideri:.1f}%",
            delta=f"{delta_d:+.1f}% vs 30%",
            delta_color="inverse"
        )
        st.caption(f"€ {spese_desideri:,.2f}")
    
    with c3:
        delta_r = pct_risparmio_totale - 20
        st.metric(
            "💰 Risparmio + Investimento", 
            f"{pct_risparmio_totale:.1f}%",
            delta=f"{delta_r:+.1f}% vs 20%",
            delta_color="normal"
        )
        # Breakdown dettagliato
        st.caption(f"💵 Liquidità: € {risparmio_puro:,.2f} ({pct_risparmio_puro:.1f}%)")
        st.caption(f"📈 Investito: € {investimenti:,.2f} ({pct_investimenti:.1f}%)")
    
    # Grafico a ciambella comparativo
    fig = go.Figure()
    
    # Valori attuali - mostra risparmio e investimento separati
    fig.add_trace(go.Pie(
        values=[pct_necessita, pct_desideri, max(0, pct_risparmio_puro), max(0, pct_investimenti)],
        labels=['Necessità', 'Desideri', 'Risparmio', 'Investimento'],
        hole=0.6,
        marker_colors=['#17a2b8', '#ffc107', '#28a745', '#007bff'],
        textinfo='label+percent',
        name='Attuale'
    ))
    
    fig.update_layout(
        annotations=[dict(text='Attuale', x=0.5, y=0.5, font_size=16, showarrow=False)],
        margin=dict(l=10, r=10, t=10, b=10),
        showlegend=False
    )
    st.plotly_chart(style_chart_for_mobile(fig), use_container_width=True)
    
    # Suggerimenti
    if pct_necessita > 55:
        st.warning("⚠️ Le spese per necessità superano il 55%. Valuta se puoi ridurre affitto o bollette.")
    if pct_desideri > 35:
        st.warning("⚠️ Le spese per desideri superano il 35%. Considera di ridurre svago e shopping.")
    if pct_risparmio_totale >= 20:
        st.success("✅ Ottimo! Stai risparmiando/investendo almeno il 20% delle entrate.")
    elif pct_risparmio_totale > 0:
        st.info(f"💡 Risparmio + Investimento positivo ma sotto l'obiettivo. Mancano {20 - pct_risparmio_totale:.1f}% per raggiungere il 20%.")


def render_expense_breakdown(df_budget: pd.DataFrame, months: int = 3):
    """Mostra le top 5 categorie di spesa."""
    st.subheader("🔥 Top Categorie di Spesa")
    
    if df_budget.empty:
        st.info("Nessun dato disponibile.")
        return
    
    df = df_budget.copy()
    df['mese'] = df['date'].dt.to_period('M').astype(str)
    
    # Ultimi N mesi
    mesi_unici = sorted(df['mese'].unique(), reverse=True)[:months]
    df_filtered = df[(df['mese'].isin(mesi_unici)) & (df['type'] == 'Uscita')]
    
    if df_filtered.empty:
        st.info("Nessuna spesa negli ultimi mesi.")
        return
    
    # Top 5 categorie
    df_cat = df_filtered.groupby('category')['amount'].sum().sort_values(ascending=False).head(5)
    
    fig = px.bar(
        x=df_cat.values,
        y=df_cat.index,
        orientation='h',
        color=df_cat.values,
        color_continuous_scale='Reds',
        text=[f"€ {v:,.0f}" for v in df_cat.values]
    )
    
    fig.update_layout(
        showlegend=False,
        coloraxis_showscale=False,
        xaxis_title="Totale Speso (€)",
        yaxis_title=None,
        margin=dict(l=10, r=10, t=10, b=10)
    )
    fig.update_traces(textposition='outside')
    
    st.plotly_chart(style_chart_for_mobile(fig), use_container_width=True)


# =============================================
# COMPONENTI SEZIONE PANORAMICA GENERALE
# =============================================

def render_general_kpis(summary: dict):
    """Renderizza i KPI generali con totali e medie."""
    st.subheader("📊 Riepilogo Generale")
    
    # Prima riga: Totali
    st.write("##### Totali (tutto il periodo)")
    t1, t2, t3, t4 = st.columns(4)
    t1.metric("💰 Totale Entrate", f"€ {summary['totale_entrate']:,.0f}")
    t2.metric("💸 Totale Uscite", f"€ {summary['totale_uscite']:,.0f}")
    t3.metric("📈 Totale Investito", f"€ {summary['totale_investito']:,.0f}")
    t4.metric("🏦 Totale Risparmio", f"€ {summary['totale_risparmio']:,.0f}")
    
    # Seconda riga: Medie
    st.write(f"##### Medie Mensili ({int(summary['num_mesi'])} mesi)")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("📥 Media Entrate", f"€ {summary['media_entrate']:,.0f}")
    m2.metric("📤 Media Uscite", f"€ {summary['media_uscite']:,.0f}")
    m3.metric("📊 Media Investito", f"€ {summary['media_investito']:,.0f}")
    m4.metric("💵 Media Risparmio", f"€ {summary['media_risparmio']:,.0f}")


def render_income_vs_expense_totals(df_budget: pd.DataFrame):
    """Grafico a barre con totali entrate/uscite/investimenti/risparmio."""
    if df_budget.empty:
        st.info("Nessun dato disponibile.")
        return
    
    # Calcola totali
    entrate = df_budget[df_budget['type'] == 'Entrata']['amount'].sum()
    uscite = df_budget[(df_budget['type'] == 'Uscita') & (df_budget['category'] != 'Investimento')]['amount'].sum()
    investito = df_budget[(df_budget['type'] == 'Uscita') & (df_budget['category'] == 'Investimento')]['amount'].sum()
    risparmio = entrate - uscite - investito
    
    df_chart = pd.DataFrame({
        'Categoria': ['Entrate', 'Uscite', 'Investimenti', 'Risparmio'],
        'Importo': [entrate, uscite, investito, risparmio],
        'Colore': ['#28a745', '#dc3545', '#007bff', '#ffc107']
    })
    
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df_chart['Categoria'],
        y=df_chart['Importo'],
        marker_color=df_chart['Colore'],
        text=[f"€ {v:,.0f}" for v in df_chart['Importo']],
        textposition='outside'
    ))
    
    fig.update_layout(
        title="Flussi Totali",
        xaxis_title=None,
        yaxis_title="Importo (€)",
        margin=dict(l=10, r=10, t=40, b=10),
        showlegend=False
    )
    
    st.plotly_chart(style_chart_for_mobile(fig), use_container_width=True)


def render_category_averages_chart(df_averages: pd.DataFrame):
    """Grafico a barre orizzontali delle medie per categoria."""
    if df_averages.empty:
        st.info("Nessun dato disponibile.")
        return
    
    fig = px.bar(
        df_averages.head(10),  # Top 10 categorie
        x='media_mensile',
        y='category',
        orientation='h',
        color='media_mensile',
        color_continuous_scale='RdYlGn_r',
        text=[f"€ {v:,.0f}" for v in df_averages.head(10)['media_mensile']]
    )
    
    fig.update_layout(
        title="Media Mensile per Categoria",
        xaxis_title="Importo Medio (€)",
        yaxis_title=None,
        yaxis={'categoryorder': 'total ascending'},
        coloraxis_showscale=False,
        margin=dict(l=10, r=10, t=40, b=10)
    )
    fig.update_traces(textposition='outside')
    
    st.plotly_chart(style_chart_for_mobile(fig), use_container_width=True)


def render_yearly_summary_chart(df_yearly: pd.DataFrame):
    """Grafico a barre raggruppate per anno."""
    if df_yearly.empty:
        st.info("Nessun dato annuale disponibile.")
        return
    
    st.subheader("📅 Riepilogo Annuale")
    
    fig = go.Figure()
    
    fig.add_trace(go.Bar(name='Entrate', x=df_yearly['anno'], y=df_yearly['entrate'], marker_color='#28a745'))
    fig.add_trace(go.Bar(name='Uscite', x=df_yearly['anno'], y=df_yearly['uscite'], marker_color='#dc3545'))
    fig.add_trace(go.Bar(name='Investito', x=df_yearly['anno'], y=df_yearly['investito'], marker_color='#007bff'))
    fig.add_trace(go.Bar(name='Risparmio', x=df_yearly['anno'], y=df_yearly['risparmio'], marker_color='#ffc107'))
    
    fig.update_layout(
        barmode='group',
        xaxis_title="Anno",
        yaxis_title="Importo (€)",
        xaxis={'tickmode': 'linear'},
        margin=dict(l=10, r=10, t=10, b=10)
    )
    
    st.plotly_chart(style_chart_for_mobile(fig), use_container_width=True)
    
    # Tabella riepilogativa
    with st.expander("📋 Dettaglio Annuale"):
        df_display = df_yearly.copy()
        df_display.columns = ['Anno', 'Entrate', 'Uscite', 'Investito', 'Risparmio']
        for col in ['Entrate', 'Uscite', 'Investito', 'Risparmio']:
            df_display[col] = df_display[col].apply(lambda x: f"€ {x:,.0f}")
        st.dataframe(df_display, use_container_width=True, hide_index=True)


def render_sankey_flow(df_budget: pd.DataFrame, year: int = None):
    """Diagramma Sankey del flusso di denaro."""
    if df_budget.empty:
        st.info("Nessun dato disponibile.")
        return
    
    df = df_budget.copy()
    if year:
        df = df[df['date'].dt.year == year]
    
    if df.empty:
        st.info(f"Nessun dato per l'anno {year}.")
        return
    
    # Calcola valori
    entrate = df[df['type'] == 'Entrata']['amount'].sum()
    
    # Spese per categoria (escluso investimento)
    df_spese = df[(df['type'] == 'Uscita') & (df['category'] != 'Investimento')]
    spese_per_cat = df_spese.groupby('category')['amount'].sum().to_dict()
    
    investito = df[(df['type'] == 'Uscita') & (df['category'] == 'Investimento')]['amount'].sum()
    totale_spese = sum(spese_per_cat.values())
    risparmio = entrate - totale_spese - investito
    
    if entrate == 0:
        st.info("Nessuna entrata registrata.")
        return
    
    # Costruisci nodi e link
    labels = ["Entrate", "Spese", "Investimenti", "Risparmio Liquido"] + list(spese_per_cat.keys())
    
    # Colori per nodi
    node_colors = ['#28a745', '#dc3545', '#007bff', '#ffc107'] + ['#ff6b6b'] * len(spese_per_cat)
    
    source = []
    target = []
    value = []
    
    # Entrate -> Spese, Investimenti, Risparmio
    if totale_spese > 0:
        source.append(0)
        target.append(1)
        value.append(totale_spese)
    
    if investito > 0:
        source.append(0)
        target.append(2)
        value.append(investito)
    
    if risparmio > 0:
        source.append(0)
        target.append(3)
        value.append(risparmio)
    
    # Spese -> Categorie
    for i, (cat, amt) in enumerate(spese_per_cat.items()):
        if amt > 0:
            source.append(1)
            target.append(4 + i)
            value.append(amt)
    
    fig = go.Figure(data=[go.Sankey(
        node=dict(
            pad=15,
            thickness=20,
            line=dict(color="black", width=0.5),
            label=labels,
            color=node_colors
        ),
        link=dict(
            source=source,
            target=target,
            value=value
        )
    )])
    
    title = f"Flusso di Denaro {year}" if year else "Flusso di Denaro (Totale)"
    fig.update_layout(
        title=title,
        margin=dict(l=10, r=10, t=40, b=10)
    )
    
    st.plotly_chart(fig, use_container_width=True)


def render_general_50_30_20(df_budget: pd.DataFrame):
    """Verifica la regola 50/30/20 su tutto il periodo."""
    st.subheader("🎯 Regola 50/30/20 (Generale)")
    
    if df_budget.empty:
        st.info("Nessun dato disponibile.")
        return
    
    # Categorie di necessità e desideri (stesse del check mensile)
    NECESSITA = ['Affitto/Casa', 'Spesa Alimentare', 'Trasporti', 'Bollette', 'Salute']
    DESIDERI = ['Ristoranti/Svago', 'Viaggi', 'Shopping', 'Altro']
    
    entrate = df_budget[df_budget['type'] == 'Entrata']['amount'].sum()
    
    if entrate == 0:
        st.warning("Nessuna entrata registrata.")
        return
    
    df_spese = df_budget[(df_budget['type'] == 'Uscita') & (df_budget['category'] != 'Investimento')]
    investimenti = df_budget[(df_budget['type'] == 'Uscita') & (df_budget['category'] == 'Investimento')]['amount'].sum()
    
    spese_necessita = df_spese[df_spese['category'].isin(NECESSITA)]['amount'].sum()
    spese_desideri = df_spese[df_spese['category'].isin(DESIDERI)]['amount'].sum()
    spese_totali = df_spese['amount'].sum()
    risparmio_puro = entrate - spese_totali - investimenti
    risparmio_totale = risparmio_puro + investimenti
    
    # Percentuali
    pct_necessita = (spese_necessita / entrate) * 100
    pct_desideri = (spese_desideri / entrate) * 100
    pct_risparmio = (risparmio_totale / entrate) * 100
    pct_investimenti = (investimenti / entrate) * 100
    pct_risparmio_puro = (risparmio_puro / entrate) * 100
    
    # Layout a colonne
    c1, c2, c3 = st.columns(3)
    
    with c1:
        delta_n = pct_necessita - 50
        color = "normal" if pct_necessita <= 50 else "inverse"
        st.metric(
            "🏠 Necessità",
            f"{pct_necessita:.1f}%",
            delta=f"{delta_n:+.1f}% vs 50%",
            delta_color="inverse"
        )
        st.caption(f"€ {spese_necessita:,.0f} totali")
    
    with c2:
        delta_d = pct_desideri - 30
        st.metric(
            "🎉 Desideri",
            f"{pct_desideri:.1f}%",
            delta=f"{delta_d:+.1f}% vs 30%",
            delta_color="inverse"
        )
        st.caption(f"€ {spese_desideri:,.0f} totali")
    
    with c3:
        delta_r = pct_risparmio - 20
        st.metric(
            "💰 Risparmio + Investimento",
            f"{pct_risparmio:.1f}%",
            delta=f"{delta_r:+.1f}% vs 20%",
            delta_color="normal"
        )
        st.caption(f"💵 Liquido: € {risparmio_puro:,.0f} ({pct_risparmio_puro:.1f}%)")
        st.caption(f"📈 Investito: € {investimenti:,.0f} ({pct_investimenti:.1f}%)")
    
    # Grafico a torta
    fig = go.Figure(data=[go.Pie(
        labels=['Necessità', 'Desideri', 'Risparmio Liquido', 'Investimenti'],
        values=[spese_necessita, spese_desideri, max(0, risparmio_puro), investimenti],
        hole=0.4,
        marker_colors=['#dc3545', '#fd7e14', '#28a745', '#007bff'],
        textinfo='label+percent'
    )])
    
    fig.update_layout(
        title="Distribuzione Generale",
        margin=dict(l=10, r=10, t=40, b=10),
        showlegend=False
    )
    
    st.plotly_chart(style_chart_for_mobile(fig), use_container_width=True)
    
    # Valutazione complessiva
    status = []
    if pct_necessita <= 55:
        status.append("✅ Necessità sotto controllo")
    else:
        status.append("⚠️ Necessità troppo alte")
    
    if pct_desideri <= 35:
        status.append("✅ Desideri sotto controllo")
    else:
        status.append("⚠️ Desideri troppo alti")
    
    if pct_risparmio >= 15:
        status.append("✅ Buon tasso di risparmio")
    else:
        status.append("⚠️ Risparmio insufficiente")
    
    st.info(" | ".join(status))