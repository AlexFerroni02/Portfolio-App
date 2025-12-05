import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from typing import Dict, Optional

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