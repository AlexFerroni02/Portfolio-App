import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from ui.components import style_chart_for_mobile


def _build_cumulative_gain_df(df_chart: pd.DataFrame) -> pd.DataFrame:
    """Costruisce la serie di guadagno reale cumulato (%) per portafoglio e benchmark."""
    gain_df = df_chart.copy()
    required_cols = {'CashFlow', 'Tu', 'Benchmark'}
    if not required_cols.issubset(gain_df.columns):
        return pd.DataFrame(columns=['Data', 'Tu_GainPct', 'Benchmark_GainPct'])

    invested = pd.to_numeric(gain_df['CashFlow'], errors='coerce').fillna(0.0).cumsum()
    valid_rows = invested > 0

    gain_df['Tu_GainPct'] = 0.0
    gain_df['Benchmark_GainPct'] = 0.0

    gain_df.loc[valid_rows, 'Tu_GainPct'] = (
        pd.to_numeric(gain_df.loc[valid_rows, 'Tu'], errors='coerce') / invested.loc[valid_rows] - 1.0
    ) * 100.0
    gain_df.loc[valid_rows, 'Benchmark_GainPct'] = (
        pd.to_numeric(gain_df.loc[valid_rows, 'Benchmark'], errors='coerce') / invested.loc[valid_rows] - 1.0
    ) * 100.0
    return gain_df[['Data', 'Tu_GainPct', 'Benchmark_GainPct']]

def render_benchmark_selector() -> str:
    """Renderizza il selettore del ticker per il benchmark."""
    col1, col2 = st.columns([1, 3])
    bench_ticker = col1.text_input("Ticker Yahoo del Benchmark", value="SWDA.MI").upper()
    col2.info("Simulazione: ogni euro investito nel tuo portafoglio viene replicato virtualmente sul benchmark nello stesso istante.")
    return bench_ticker

def render_benchmark_kpis(df_chart: pd.DataFrame, bench_ticker: str):
    """Renderizza i KPI di confronto tra portafoglio e benchmark."""
    if df_chart.empty:
        return
    final_user = df_chart['Tu'].iloc[-1]
    final_bench = df_chart['Benchmark'].iloc[-1]
    diff = final_user - final_bench
    perc_diff = (diff / final_bench * 100) if final_bench else 0

    st.divider()
    k1, k2, k3 = st.columns(3)
    k1.metric("Valore Tuo Portafoglio", f"€ {final_user:,.2f}")
    k2.metric(f"Valore Benchmark ({bench_ticker})", f"€ {final_bench:,.2f}")
    k3.metric("Alpha (Differenza)", f"€ {diff:,.2f}", delta=f"{perc_diff:.2f}%")

def render_transaction_log(df_log: pd.DataFrame, bench_ticker: str):
    """Mostra il log delle transazioni simulate per il benchmark."""
    with st.expander("📋 Log Transazioni Simulate sul Benchmark"):
        st.dataframe(df_log, width='stretch', hide_index=True)
        csv = df_log.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Scarica Log",
            data=csv,
            file_name=f"benchmark_log_{bench_ticker}.csv",
            mime="text/csv"
        )

def render_performance_chart(df_chart: pd.DataFrame, bench_ticker: str):
    """Mostra il grafico dell'andamento del valore nel tempo."""
    st.subheader("📈 Gara di Rendimento")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df_chart['Data'], y=df_chart['Tu'], name='Il Tuo Portafoglio', line=dict(color='#00CC96', width=3)))
    fig.add_trace(go.Scatter(x=df_chart['Data'], y=df_chart['Benchmark'], name=f'Benchmark ({bench_ticker})', line=dict(color='#A0A0A0', width=2, dash='dot')))
    fig.update_layout(title_text="Valore nel Tempo (€)")
    st.plotly_chart(style_chart_for_mobile(fig), width='stretch')


def render_gain_chart(df_chart: pd.DataFrame, bench_ticker: str):
    """Mostra il guadagno reale cumulato (%) nel tempo tra portafoglio e benchmark."""
    st.subheader("📊 Guadagno Cumulato nel Tempo")
    st.caption("Confronto del guadagno reale %: valore corrente rispetto al capitale netto investito cumulato.")

    gain_df = _build_cumulative_gain_df(df_chart)
    if gain_df.empty:
        st.info("Dati insufficienti per il grafico del guadagno cumulato.")
        return

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=gain_df['Data'],
            y=gain_df['Tu_GainPct'],
            name='Guadagno Portafoglio',
            line=dict(color='#00CC96', width=3),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=gain_df['Data'],
            y=gain_df['Benchmark_GainPct'],
            name=f'Guadagno Benchmark ({bench_ticker})',
            line=dict(color='#636EFA', width=2, dash='dot'),
        )
    )
    fig.update_layout(title_text="Guadagno Cumulato (%)", yaxis_ticksuffix="%")
    st.plotly_chart(style_chart_for_mobile(fig), width='stretch')

def render_drawdown_chart(df_chart: pd.DataFrame):
    """Calcola e mostra il grafico del drawdown."""
    st.subheader("🌊 Analisi del Rischio (Drawdown)")
    st.caption("Quanto perdi dai massimi? Il calcolo usa rendimenti flow-adjusted per non falsare il drawdown su acquisti/vendite.")
    
    df_dd = df_chart.copy()
    if {'Tu_Return', 'Benchmark_Return'}.issubset(df_dd.columns):
        user_growth = (1.0 + pd.to_numeric(df_dd['Tu_Return'], errors='coerce').fillna(0.0)).cumprod()
        bench_growth = (1.0 + pd.to_numeric(df_dd['Benchmark_Return'], errors='coerce').fillna(0.0)).cumprod()

        user_max = user_growth.cummax().replace(0, pd.NA)
        bench_max = bench_growth.cummax().replace(0, pd.NA)
        df_dd['Tu_DD'] = ((user_growth - user_max) / user_max) * 100
        df_dd['Bench_DD'] = ((bench_growth - bench_max) / bench_max) * 100
    else:
        df_dd['Tu_Max'] = df_dd['Tu'].cummax()
        df_dd['Bench_Max'] = df_dd['Benchmark'].cummax()
        df_dd['Tu_DD'] = ((df_dd['Tu'] - df_dd['Tu_Max']) / df_dd['Tu_Max'].replace(0, pd.NA)) * 100
        df_dd['Bench_DD'] = ((df_dd['Benchmark'] - df_dd['Bench_Max']) / df_dd['Bench_Max'].replace(0, pd.NA)) * 100

    df_dd = df_dd.fillna(0)

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df_dd['Data'], y=df_dd['Tu_DD'], name='Il Tuo Drawdown', fill='tozeroy', line=dict(color='#EF553B', width=1)))
    fig.add_trace(go.Scatter(x=df_dd['Data'], y=df_dd['Bench_DD'], name='Benchmark Drawdown', line=dict(color='#A0A0A0', width=1, dash='dot')))
    fig.update_layout(title_text="Perdita dai Massimi (%)", yaxis_ticksuffix="%")
    st.plotly_chart(style_chart_for_mobile(fig), width='stretch')