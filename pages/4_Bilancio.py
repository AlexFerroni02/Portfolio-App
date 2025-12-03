import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from sklearn.linear_model import LinearRegression
import numpy as np
from utils import get_data, save_data, make_sidebar, style_chart_for_mobile

st.set_page_config(page_title="Bilancio", layout="wide", page_icon="💰")
make_sidebar()
st.title("💰 Bilancio & Patrimonio")

with st.spinner("Caricamento dati..."):
    df_budget = get_data("budget")
    df_trans = get_data("transactions")
    df_nw = get_data("networth_history")

if not df_budget.empty:
    df_budget['date'] = pd.to_datetime(df_budget['date'], errors='coerce').dt.normalize()
if not df_trans.empty:
    df_trans['date'] = pd.to_datetime(df_trans['date'], errors='coerce').dt.normalize()
if not df_nw.empty:
    df_nw['date'] = pd.to_datetime(df_nw['date'], errors='coerce').dt.normalize()

if df_budget.empty:
    st.info("👋 Nessun dato di bilancio presente. Vai su 'Gestione Dati' per inserire entrate e uscite.")
    st.stop()

st.subheader("Analisi Mensile")
df_budget['mese_anno'] = df_budget['date'].dt.strftime('%Y-%m')
mesi_disponibili = sorted(df_budget['mese_anno'].unique(), reverse=True)

col_sel, col_msg = st.columns([1, 3])
selected_month = col_sel.selectbox("Seleziona Mese:", mesi_disponibili)
col_msg.caption("💡 Per aggiungere nuovi movimenti, vai alla pagina 'Gestione Dati'.")

df_month = df_budget[df_budget['mese_anno'] == selected_month]

entrate = df_month[df_month['type'] == 'Entrata']['amount'].sum()
uscite = df_month[df_month['type'] == 'Uscita']['amount'].sum()
risparmio = entrate - uscite
savings_rate = (risparmio / entrate * 100) if entrate > 0 else 0

investito_mese = 0.0
if not df_trans.empty:
    mask_inv = df_trans['date'].dt.strftime('%Y-%m') == selected_month
    investito_mese = -df_trans[mask_inv]['local_value'].sum()

# MODIFICATO: Logica di calcolo liquidità che rispetta Saldo Iniziale e Aggiustamenti
final_liquidity, liquidity_help_text = 0.0, "Calcolata come: (Entrate - Uscite - Investimenti) totali."
if not df_budget.empty:
    df_budget_sorted = df_budget.sort_values('date')
    initial_balance_entry = df_budget_sorted[df_budget_sorted['category'] == 'Saldo Iniziale'].head(1)
    
    start_date = pd.Timestamp.min.tz_localize('UTC')
    base_liquidity = 0.0

    if not initial_balance_entry.empty:
        start_date = initial_balance_entry['date'].iloc[0]
        base_liquidity = initial_balance_entry['amount'].iloc[0]
        liquidity_help_text = f"Partendo dal saldo di €{base_liquidity:,.2f} del {start_date.strftime('%d-%m-%Y')}."
        
        budget_to_sum = df_budget_sorted[df_budget_sorted['date'] > start_date]
        trans_to_sum = df_trans[df_trans['date'] > start_date] if not df_trans.empty else pd.DataFrame()
        
        other_entrate = budget_to_sum[(budget_to_sum['type'] == 'Entrata') & (budget_to_sum['category'] != 'Saldo Iniziale')]['amount'].sum()
        all_uscite = budget_to_sum[budget_to_sum['type'] == 'Uscita']['amount'].sum()
        investments = -trans_to_sum['local_value'].sum() if not trans_to_sum.empty else 0.0
        final_liquidity = base_liquidity + other_entrate - all_uscite - investments
    else:
        total_entrate = df_budget['amount'][df_budget['type'] == 'Entrata'].sum()
        total_uscite = df_budget['amount'][df_budget['type'] == 'Uscita'].sum()
        total_investito_netto = -df_trans['local_value'].sum() if not df_trans.empty else 0.0
        final_liquidity = total_entrate - total_uscite - total_investito_netto

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Entrate Mese", f"€ {entrate:,.2f}")
k2.metric("Uscite Mese", f"€ {uscite:,.2f}", delta=f"-{(uscite/entrate)*100:.1f}% delle entrate" if entrate else "")
k3.metric("Risparmio Mese", f"€ {risparmio:,.2f}", delta=f"{savings_rate:.1f}% Tasso di Risparmio")
k4.metric("Investito Mese", f"€ {investito_mese:,.2f}", delta=f"{(investito_mese/risparmio)*100:.1f}% del risparmio" if risparmio > 0 else "")
k5.metric("Liquidità Totale", f"€ {final_liquidity:,.2f}", help=liquidity_help_text)

c1, c2 = st.columns(2)
with c1:
    st.write("###### Spese per Categoria")
    df_spese = df_month[df_month['type'] == 'Uscita']
    if not df_spese.empty:
        fig_pie = px.pie(df_spese, values='amount', names='category', hole=0.4)
        fig_pie = style_chart_for_mobile(fig_pie)
        fig_pie.update_layout(showlegend=False, margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig_pie, use_container_width=True)
    else:
        st.info("Nessuna spesa registrata in questo mese.")
with c2:
    st.write("###### Flusso Mensile")
    fig_bar = go.Figure()
    fig_bar.add_trace(go.Bar(name='Entrate', x=['Flusso'], y=[entrate], marker_color='#28a745'))
    fig_bar.add_trace(go.Bar(name='Spese', x=['Flusso'], y=[uscite], marker_color='#dc3545'))
    fig_bar.add_trace(go.Bar(name='Investito', x=['Flusso'], y=[investito_mese], marker_color='#007bff'))
    fig_bar = style_chart_for_mobile(fig_bar)
    fig_bar.update_layout(barmode='group', margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig_bar, use_container_width=True)

st.divider()

st.subheader("📈 Andamento Patrimonio Netto")
if not df_nw.empty and 'net_worth' in df_nw.columns and not df_nw['net_worth'].dropna().empty:
    df_nw = df_nw.sort_values('date').reset_index(drop=True)
    df_nw['monthly_increase'] = df_nw['net_worth'].diff()
    
    df_chart = df_nw.dropna(subset=['net_worth']).copy()
    df_goals = df_nw.dropna(subset=['goal']).copy()

    fig_nw = go.Figure()
    fig_nw.add_trace(go.Scatter(x=df_chart['date'], y=df_chart['net_worth'], name='Patrimonio Netto', mode='lines+markers', line=dict(color='#00CC96', width=3)))
    if not df_goals.empty:
        fig_nw.add_trace(go.Scatter(x=df_goals['date'], y=df_goals['goal'], name='Obiettivo', mode='lines', line=dict(color='#EF553B', dash='dash')))
    if len(df_chart) > 1:
        X = np.array([(d - df_chart['date'].min()).days for d in df_chart['date']]).reshape(-1, 1)
        y = df_chart['net_worth'].values
        model = LinearRegression().fit(X, y)
        trend_dates = pd.date_range(start=df_chart['date'].min(), end=df_chart['date'].max() + pd.DateOffset(months=6))
        trend_X = np.array([(d - df_chart['date'].min()).days for d in trend_dates]).reshape(-1, 1)
        trend_y = model.predict(trend_X)
        fig_nw.add_trace(go.Scatter(x=trend_dates, y=trend_y, name='Trend', line=dict(dash='dot', color='rgba(255,255,0,0.6)')))
    fig_nw = style_chart_for_mobile(fig_nw)
    fig_nw.update_layout(title="Patrimonio Netto vs Obiettivo")
    st.plotly_chart(fig_nw, use_container_width=True)

    fig_increase = px.bar(df_chart[df_chart['monthly_increase'].notna() & (df_chart['monthly_increase'] != 0)], x='date', y='monthly_increase', title="Incremento Mensile del Patrimonio")
    fig_increase.update_traces(marker_color=['#28a745' if x >= 0 else '#dc3545' for x in df_chart['monthly_increase'].dropna()])
    fig_increase = style_chart_for_mobile(fig_increase)
    st.plotly_chart(fig_increase, use_container_width=True)

    st.write("###### Tabella Riassuntiva")
    df_display = df_nw[['date', 'net_worth', 'monthly_increase', 'goal']].copy()
    df_display['date'] = df_display['date'].dt.strftime('%m/%y')
    st.dataframe(df_display.dropna(subset=['net_worth']), use_container_width=True, hide_index=True,
        column_config={
            "date": "Data", "net_worth": st.column_config.NumberColumn("Patrimonio (€)", format="€ %.2f"),
            "monthly_increase": st.column_config.NumberColumn("Incremento (€)", format="€ %.2f"),
            "goal": st.column_config.NumberColumn("Obiettivo (€)", format="€ %.2f")
        }
    )
else:
    st.info("Nessun dato storico sul patrimonio netto. Vai in 'Gestione Dati > Patrimonio Netto' per iniziare a salvare gli snapshot.")

st.divider()

st.subheader("📝 Dettaglio Movimenti del Mese")
with st.expander("Visualizza o Elimina Movimenti"):
    df_edit = df_month.copy()
    df_edit.insert(0, "Elimina", False)
    edited_df = st.data_editor(
        df_edit,
        column_config={"Elimina": st.column_config.CheckboxColumn(default=False), "date": st.column_config.DateColumn("Data", format="DD-MM-YYYY"), "amount": st.column_config.NumberColumn("Importo", format="€ %.2f")},
        disabled=["date", "type", "category", "amount", "note"],
        hide_index=True, use_container_width=True
    )
    to_delete = edited_df[edited_df["Elimina"] == True]
    if not to_delete.empty:
        if st.button("🗑️ CONFERMA ELIMINAZIONE", type="primary"):
            indexes_to_drop = to_delete.index
            df_budget_updated = df_budget.drop(indexes_to_drop)
            save_data(df_budget_updated, "budget", method='replace') 
            st.success("✅ Eliminato! La pagina si aggiornerà.") 
            st.rerun()