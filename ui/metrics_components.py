from typing import Dict, Any

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st


def _format_percentage(value: float | None) -> str:
    """Formatta una percentuale con fallback leggibile."""
    if value is None:
        return "N/D"
    return f"{value:.2f}%"


def _format_ratio(value: float | None) -> str:
    """Formatta un ratio numerico con fallback leggibile."""
    if value is None:
        return "N/D"
    return f"{value:.2f}"


def render_return_kpis(ytd_return: float | None, period_return: float | None):
    """Mostra KPI di rendimento periodico e YTD."""
    col1, col2 = st.columns(2)
    with col1:
        st.metric("📅 Rendimento YTD", _format_percentage(ytd_return))
    with col2:
        st.metric("🗓️ Rendimento da data selezionata", _format_percentage(period_return))


def render_risk_kpis(metrics: Dict[str, Any]):
    """Mostra KPI sintetici di rischio non inclusi nella tabella comparativa."""
    col1, col2 = st.columns(2)
    with col1:
        st.metric("🌪️ Volatilità Annua", _format_percentage(metrics.get('annualized_volatility_pct')))
    with col2:
        st.metric("📉 Max Drawdown", _format_percentage(metrics.get('max_drawdown_pct')))



def render_ratio_kpis(metrics: Dict[str, Any]):
    """Mostra KPI con ratio risk-adjusted."""
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("⚖️ Sharpe", _format_ratio(metrics.get('sharpe_ratio')))
    with col2:
        st.metric("🛡️ Sortino", _format_ratio(metrics.get('sortino_ratio')))
    with col3:
        st.metric("📐 Calmar", _format_ratio(metrics.get('calmar_ratio')))


def render_yearly_return_bars(comparison_df: pd.DataFrame):
    """Renderizza il confronto anno per anno tra TWR e reale usando rendimenti di periodo."""
    if comparison_df.empty:
        st.info("Nessun dato sufficiente per il grafico annuale.")
        return

    chart_df = comparison_df.melt(
        id_vars=['Year'],
        value_vars=['TwrPeriodPct', 'RealPeriodPct'],
        var_name='Metrica',
        value_name='RendimentoPct',
    ).dropna(subset=['RendimentoPct'])
    if chart_df.empty:
        st.info("Nessun dato sufficiente per il confronto TWR vs guadagno reale.")
        return

    metric_labels = {
        'TwrPeriodPct': 'TWR',
        'RealPeriodPct': 'Reale',
    }
    chart_df['Metrica'] = chart_df['Metrica'].map(metric_labels)

    fig = px.bar(
        chart_df,
        x='Year',
        y='RendimentoPct',
        color='Metrica',
        barmode='group',
        color_discrete_map={'TWR': '#2e7d32', 'Reale': '#1565c0'},
        title='Confronto Anno per Anno: TWR vs Reale',
        labels={'Year': 'Anno', 'RendimentoPct': 'Rendimento %'},
        text=chart_df['RendimentoPct'].map(lambda value: f"{value:.2f}%"),
        hover_data={'RendimentoPct': ':.2f', 'Metrica': True, 'Year': True},
    )
    fig.update_layout(margin=dict(l=10, r=10, t=50, b=10), hovermode='x unified')
    fig.update_traces(textposition='outside')
    st.plotly_chart(fig, width='stretch')


def render_twr_real_comparison_table(comparison_df: pd.DataFrame):
    """Mostra tabella di confronto tra metriche TWR e metriche reali."""
    st.subheader("🧾 Confronto TWR vs Reale")
    st.markdown(
        "<span title=\"Il TWR misura la performance al netto dei flussi: r = Valore_oggi / (Valore_ieri + Flusso_netto) - 1\">"
        "ℹ️ Passa il mouse qui per la definizione di TWR"
        "</span>",
        unsafe_allow_html=True,
    )

    if comparison_df.empty:
        st.info("Nessun dato disponibile per il confronto TWR vs Reale.")
        return

    display_df = comparison_df.copy()
    display_df['TWR'] = display_df['TWR'].map(lambda value: "N/D" if pd.isna(value) else f"{value:.2f}%")
    display_df['Reale'] = display_df['Reale'].map(lambda value: "N/D" if pd.isna(value) else f"{value:.2f}%")
    st.dataframe(display_df, width='stretch', hide_index=True)

def render_drawdown_chart(df_history: pd.DataFrame):
    """Renderizza la curva storica dei drawdown percentuali."""
    if df_history.empty:
        st.info("Nessun dato disponibile per il drawdown.")
        return

    chart_df = df_history.copy()
    if 'Rendimento Giornaliero %' in chart_df.columns:
        daily_returns = pd.to_numeric(chart_df['Rendimento Giornaliero %'], errors='coerce').fillna(0.0) / 100.0
        chart_df['TwrGrowth'] = (1.0 + daily_returns).cumprod()
    elif 'Valore' in chart_df.columns:
        base_value = pd.to_numeric(chart_df['Valore'], errors='coerce').replace(0, pd.NA).ffill()
        chart_df['TwrGrowth'] = base_value / float(base_value.dropna().iloc[0])
    else:
        st.info("Dati insufficienti per il drawdown.")
        return

    chart_df['RunningMax'] = chart_df['TwrGrowth'].cummax()
    chart_df['DrawdownPct'] = ((chart_df['TwrGrowth'] / chart_df['RunningMax']) - 1.0) * 100.0

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=chart_df['Data'],
            y=chart_df['DrawdownPct'],
            mode='lines',
            line=dict(color='#c0392b', width=2),
            name='Drawdown %',
        )
    )
    fig.update_layout(
        title='Curva Drawdown Portafoglio',
        yaxis_title='Drawdown (%)',
        margin=dict(l=10, r=10, t=50, b=10),
        hovermode='x unified',
    )
    st.plotly_chart(fig, width='stretch')


def render_extreme_days(metrics: Dict[str, Any]):
    """Mostra i migliori e peggiori rendimenti giornalieri osservati."""
    col1, col2 = st.columns(2)
    with col1:
        st.metric("🚀 Miglior Giorno", _format_percentage(metrics.get('best_day_pct')))
    with col2:
        st.metric("🧨 Peggior Giorno", _format_percentage(metrics.get('worst_day_pct')))


def render_twr_audit_table(audit_df: pd.DataFrame):
    """Mostra il dettaglio giornaliero del calcolo TWR in forma auditabile."""
    st.subheader("🔎 Audit Calcolo TWR (Riga per Riga)")
    st.caption("La tabella mostra solo percentuali e indici normalizzati, senza importi monetari.")
    if audit_df.empty:
        st.info("Nessun dato disponibile per l'audit TWR.")
        return

    display_df = audit_df.copy()
    display_df = display_df.sort_values('Data', ascending=False)
    st.dataframe(display_df, width='stretch')
