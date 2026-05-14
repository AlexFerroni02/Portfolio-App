from datetime import date
from typing import Optional, Dict, Any

import numpy as np
import pandas as pd

TRADING_DAYS_PER_YEAR = 252


def prepare_portfolio_timeseries(df_history: pd.DataFrame) -> pd.DataFrame:
    """
    Normalizza la serie storica del portafoglio per i calcoli metrici.

    Args:
        df_history: DataFrame con colonne 'Data' e 'Valore'.

    Returns:
        DataFrame pulito e ordinato per data.
    """
    required_cols = {'Data', 'Valore'}
    if df_history.empty or not required_cols.issubset(df_history.columns):
        return pd.DataFrame(columns=['Data', 'Valore', 'Investito'])

    normalized_df = df_history[['Data', 'Valore']].copy()
    if 'Investito' in df_history.columns:
        normalized_df['Investito'] = df_history['Investito']
    else:
        normalized_df['Investito'] = 0.0

    normalized_df['Data'] = pd.to_datetime(normalized_df['Data'], errors='coerce').dt.normalize()
    normalized_df['Valore'] = pd.to_numeric(normalized_df['Valore'], errors='coerce')
    normalized_df['Investito'] = pd.to_numeric(normalized_df['Investito'], errors='coerce').fillna(0.0)
    normalized_df = normalized_df.dropna(subset=['Data', 'Valore'])
    normalized_df = normalized_df[normalized_df['Valore'] >= 0]
    normalized_df = normalized_df.sort_values('Data').drop_duplicates(subset='Data', keep='last')
    normalized_df['Investito'] = normalized_df['Investito'].ffill().fillna(0.0)
    return normalized_df.reset_index(drop=True)


def _calculate_net_invested_flows(df_history: pd.DataFrame) -> pd.Series:
    """
    Calcola i versamenti/disinvestimenti giornalieri dal cumulato investito.

    Args:
        df_history: Serie storica normalizzata con colonna Investito.

    Returns:
        Serie dei flussi netti giornalieri.
    """
    if df_history.empty:
        return pd.Series(dtype='float64')

    flows = df_history['Investito'].diff().fillna(0.0)
    flows.iloc[0] = float(df_history.iloc[0]['Investito'])
    return flows.astype('float64')


def _calculate_flow_adjusted_return_series(df_history: pd.DataFrame) -> pd.Series:
    """
    Calcola rendimenti giornalieri al netto dei versamenti (Time-Weighted).

    Args:
        df_history: Serie storica normalizzata con Valore e Investito.

    Returns:
        Serie rendimenti giornalieri decimali (con NaN dove non calcolabili).
    """
    if len(df_history) < 2:
        return pd.Series(dtype='float64')

    net_flows = _calculate_net_invested_flows(df_history)
    previous_value = df_history['Valore'].shift(1)
    adjusted_base = previous_value + net_flows
    return_series = pd.Series(np.nan, index=df_history.index, dtype='float64')
    valid_rows = adjusted_base > 0
    return_series.loc[valid_rows] = (df_history.loc[valid_rows, 'Valore'] / adjusted_base.loc[valid_rows]) - 1.0
    return_series.iloc[0] = np.nan
    return return_series


def _build_return_frame(df_history: pd.DataFrame) -> pd.DataFrame:
    """
    Crea un DataFrame con date e rendimenti flow-adjusted validi.

    Args:
        df_history: Serie storica normalizzata.

    Returns:
        DataFrame con colonne Data e daily_return.
    """
    return_frame = pd.DataFrame({'Data': df_history['Data']})
    return_frame['daily_return'] = _calculate_flow_adjusted_return_series(df_history)
    return return_frame.dropna(subset=['daily_return']).reset_index(drop=True)


def _compound_return_pct(daily_returns: pd.Series) -> Optional[float]:
    """
    Compone una serie di rendimenti giornalieri in rendimento percentuale totale.

    Args:
        daily_returns: Serie rendimenti giornalieri decimali.

    Returns:
        Rendimento totale percentuale o None.
    """
    if daily_returns.empty:
        return None
    cumulative_growth = float((1.0 + daily_returns).prod())
    if cumulative_growth <= 0:
        return None
    return (cumulative_growth - 1.0) * 100.0


def calculate_period_time_weighted_return(
    df_history: pd.DataFrame,
    start_date: Optional[pd.Timestamp] = None,
    end_date: Optional[pd.Timestamp] = None,
) -> Optional[float]:
    """
    Calcola il rendimento TWR su un periodo specifico.

    Args:
        df_history: Serie storica normalizzata.
        start_date: Data inizio periodo.
        end_date: Data fine periodo.

    Returns:
        Rendimento TWR percentuale o None.
    """
    return_frame = _build_return_frame(df_history)
    if return_frame.empty:
        return None

    if start_date is not None:
        start_ts = start_date.normalize()
        return_frame = return_frame[return_frame['Data'] > start_ts]
    if end_date is not None:
        return_frame = return_frame[return_frame['Data'] <= end_date.normalize()]
    if return_frame.empty:
        return None

    return _compound_return_pct(return_frame['daily_return'])


def calculate_period_return(start_value: float, end_value: float) -> Optional[float]:
    """
    Calcola il rendimento percentuale tra due valori.

    Args:
        start_value: Valore iniziale.
        end_value: Valore finale.

    Returns:
        Rendimento percentuale o None se input non valido.
    """
    if start_value <= 0:
        return None
    return ((end_value / start_value) - 1.0) * 100.0


def calculate_ytd_return(df_history: pd.DataFrame, as_of: Optional[pd.Timestamp] = None) -> Optional[float]:
    """
    Calcola il rendimento YTD sul valore del portafoglio.

    Args:
        df_history: Serie storica normalizzata con 'Data' e 'Valore'.
        as_of: Data finale opzionale.

    Returns:
        Rendimento YTD percentuale o None se dati insufficienti.
    """
    if df_history.empty:
        return None

    end_date = as_of.normalize() if as_of is not None else df_history['Data'].max()
    year_start = pd.Timestamp(year=end_date.year, month=1, day=1)
    return calculate_period_time_weighted_return(df_history, start_date=year_start, end_date=end_date)


def calculate_return_from_date(df_history: pd.DataFrame, start_date: date) -> Optional[float]:
    """
    Calcola il rendimento del portafoglio da una data selezionata.

    Args:
        df_history: Serie storica normalizzata con 'Data' e 'Valore'.
        start_date: Data iniziale selezionata dall'utente.

    Returns:
        Rendimento percentuale o None se dati insufficienti.
    """
    if df_history.empty:
        return None

    start_ts = pd.to_datetime(start_date).normalize()
    return calculate_period_time_weighted_return(df_history, start_date=start_ts)


def calculate_daily_returns(df_history: pd.DataFrame) -> pd.Series:
    """
    Calcola i rendimenti giornalieri percentuali.

    Args:
        df_history: Serie storica normalizzata.

    Returns:
        Serie di rendimenti giornalieri in forma decimale.
    """
    return _build_return_frame(df_history)['daily_return']


def calculate_cagr(df_history: pd.DataFrame) -> Optional[float]:
    """
    Calcola il CAGR (rendimento annualizzato composto).

    Args:
        df_history: Serie storica normalizzata.

    Returns:
        CAGR percentuale o None se non calcolabile.
    """
    if len(df_history) < 2:
        return None

    total_return_pct = calculate_period_time_weighted_return(df_history)
    if total_return_pct is None:
        return None

    total_days = (df_history.iloc[-1]['Data'] - df_history.iloc[0]['Data']).days
    years = total_days / 365.25
    growth_factor = 1.0 + (total_return_pct / 100.0)
    if years <= 0 or growth_factor <= 0:
        return None

    cagr = growth_factor ** (1.0 / years) - 1.0
    return cagr * 100.0


def calculate_annualized_volatility(daily_returns: pd.Series) -> Optional[float]:
    """
    Calcola la volatilità annualizzata a partire dai rendimenti giornalieri.

    Args:
        daily_returns: Serie rendimenti giornalieri (decimali).

    Returns:
        Volatilità annualizzata in percentuale.
    """
    if daily_returns.empty:
        return None
    return float(daily_returns.std(ddof=0) * np.sqrt(TRADING_DAYS_PER_YEAR) * 100.0)


def calculate_max_drawdown(df_history: pd.DataFrame) -> Optional[float]:
    """
    Calcola il massimo drawdown percentuale della serie storica.

    Args:
        df_history: Serie storica normalizzata.

    Returns:
        Massimo drawdown percentuale (valore negativo).
    """
    daily_returns = calculate_daily_returns(df_history)
    if daily_returns.empty:
        return None

    equity_curve = (1.0 + daily_returns).cumprod()
    running_max = equity_curve.cummax()
    drawdowns = (equity_curve / running_max) - 1.0
    return float(drawdowns.min() * 100.0)


def calculate_yearly_returns(df_history: pd.DataFrame) -> pd.DataFrame:
    """
    Calcola il rendimento TWR percentuale per ogni anno calendario.

    Args:
        df_history: Serie storica normalizzata.

    Returns:
        DataFrame con colonne Year e ReturnPct.
    """
    return_frame = _build_return_frame(df_history)
    if return_frame.empty:
        return pd.DataFrame(columns=['Year', 'ReturnPct'])

    yearly_df = return_frame.copy()
    yearly_df['Year'] = yearly_df['Data'].dt.year.astype(int)
    grouped_df = yearly_df.groupby('Year')['daily_return'].apply(_compound_return_pct)
    grouped_df = grouped_df.dropna().reset_index(name='ReturnPct')
    return grouped_df.sort_values('Year').reset_index(drop=True)


def calculate_yearly_return_comparison(df_history: pd.DataFrame) -> pd.DataFrame:
    """
    Confronta rendimento TWR annuale con guadagno reale annualizzato per anno.

    Args:
        df_history: Serie storica normalizzata.

    Returns:
        DataFrame con colonne Year, TwrPeriodPct, RealPeriodPct, TwrAnnualizedPct, RealAnnualizedPct.
    """
    normalized_df = prepare_portfolio_timeseries(df_history)
    if normalized_df.empty:
        return pd.DataFrame(
            columns=['Year', 'TwrPeriodPct', 'RealPeriodPct', 'TwrAnnualizedPct', 'RealAnnualizedPct']
        )

    twr_df = calculate_yearly_returns(normalized_df).rename(columns={'ReturnPct': 'TwrPeriodPct'})
    year_df = normalized_df.copy()
    year_df['Year'] = year_df['Data'].dt.year.astype(int)

    comparison_rows = []
    for year, group in year_df.groupby('Year'):
        ordered_group = group.sort_values('Data')
        start_row = ordered_group.iloc[0]
        end_row = ordered_group.iloc[-1]
        period_days = max((end_row['Data'] - start_row['Data']).days, 1)

        twr_period = twr_df.loc[twr_df['Year'] == int(year), 'TwrPeriodPct']
        twr_period_value = float(twr_period.iloc[0]) if not twr_period.empty else None
        twr_annualized = _annualize_return_pct(twr_period_value, period_days)

        # Deriva il rendimento reale di periodo dalla serie cumulata:
        # (1 + cumul_end) / (1 + cumul_start) - 1
        start_real_cum = _calculate_real_cumulative_pct(start_row)
        end_real_cum = _calculate_real_cumulative_pct(end_row)
        real_period = None
        if start_real_cum is not None and end_real_cum is not None:
            start_growth = 1.0 + (start_real_cum / 100.0)
            end_growth = 1.0 + (end_real_cum / 100.0)
            if start_growth > 0 and end_growth > 0:
                real_period = ((end_growth / start_growth) - 1.0) * 100.0

        real_annualized = _annualize_return_pct(real_period, period_days)

        comparison_rows.append(
            {
                'Year': int(year),
                'TwrPeriodPct': twr_period_value,
                'RealPeriodPct': real_period,
                'TwrAnnualizedPct': twr_annualized,
                'RealAnnualizedPct': real_annualized,
            }
        )

    comparison_df = pd.DataFrame(comparison_rows)
    comparison_df = comparison_df.sort_values('Year').reset_index(drop=True)
    return comparison_df[['Year', 'TwrPeriodPct', 'RealPeriodPct', 'TwrAnnualizedPct', 'RealAnnualizedPct']]


def _annualize_return_pct(period_return_pct: Optional[float], period_days: int) -> Optional[float]:
    """Annualizza un rendimento percentuale su un numero di giorni."""
    if period_return_pct is None or period_days <= 0:
        return None
    growth = 1.0 + (period_return_pct / 100.0)
    if growth <= 0:
        return None
    return (growth ** (365.25 / period_days) - 1.0) * 100.0


def _calculate_modified_dietz_return_pct(df_history: pd.DataFrame) -> Optional[float]:
    """
    Calcola il rendimento di periodo con metodo Modified Dietz.

    Args:
        df_history: Serie storica ordinata con colonne Data, Valore, Investito.

    Returns:
        Rendimento percentuale del periodo o None.
    """
    normalized_df = prepare_portfolio_timeseries(df_history)
    if len(normalized_df) < 2:
        return None

    ordered_df = normalized_df.sort_values('Data').reset_index(drop=True)
    start_date = ordered_df.iloc[0]['Data']
    end_date = ordered_df.iloc[-1]['Data']
    period_days = max((end_date - start_date).days, 1)

    start_value = float(ordered_df.iloc[0]['Valore'])
    end_value = float(ordered_df.iloc[-1]['Valore'])

    flows = ordered_df['Investito'].diff().fillna(0.0)
    flows.iloc[0] = 0.0
    flow_weights = ordered_df['Data'].map(lambda current_date: (end_date - current_date).days / period_days)

    sum_flows = float(flows.sum())
    weighted_flows = float((flows * flow_weights).sum())
    denominator = start_value + weighted_flows
    if denominator <= 0:
        return None

    return ((end_value - start_value - sum_flows) / denominator) * 100.0


def _calculate_real_cumulative_pct(row: pd.Series) -> Optional[float]:
    """Calcola il guadagno reale cumulato (%) in un punto temporale."""
    try:
        value = float(row['Valore'])
        invested = float(row['Investito'])
    except (TypeError, ValueError, KeyError):
        return None
    if invested <= 0:
        return None
    return ((value - invested) / invested) * 100.0


def calculate_real_total_return(df_history: pd.DataFrame) -> Optional[float]:
    """Calcola il rendimento reale totale su versamenti netti (con costi inclusi)."""
    normalized_df = prepare_portfolio_timeseries(df_history)
    if normalized_df.empty:
        return None

    end_value = float(normalized_df.iloc[-1]['Valore'])
    end_invested = float(normalized_df.iloc[-1]['Investito'])
    if end_invested <= 0:
        return None

    return ((end_value - end_invested) / end_invested) * 100.0


def calculate_real_annualized_return(df_history: pd.DataFrame) -> Optional[float]:
    """Calcola un rendimento reale annualizzato sull'intero periodo storico."""
    normalized_df = prepare_portfolio_timeseries(df_history)
    if len(normalized_df) < 2:
        return None

    start_row = normalized_df.iloc[0]
    end_row = normalized_df.iloc[-1]
    total_days = max((end_row['Data'] - start_row['Data']).days, 1)
    real_total = calculate_real_total_return(normalized_df)
    return _annualize_return_pct(real_total, total_days)


def build_twr_real_comparison_table(df_history: pd.DataFrame) -> pd.DataFrame:
    """
    Costruisce una tabella comparativa TWR vs Reale per metriche non equivalenti.

    Args:
        df_history: Serie storica normalizzata.

    Returns:
        DataFrame con colonne Metrica, TWR, Reale.
    """
    normalized_df = prepare_portfolio_timeseries(df_history)
    if normalized_df.empty:
        return pd.DataFrame(columns=['Metrica', 'TWR', 'Reale'])

    twr_total = calculate_period_time_weighted_return(normalized_df)
    twr_cagr = calculate_cagr(normalized_df)
    real_total = calculate_real_total_return(normalized_df)
    real_annualized = calculate_real_annualized_return(normalized_df)

    comparison_rows = [
        {'Metrica': 'Rendimento Totale %', 'TWR': twr_total, 'Reale': real_total},
        {'Metrica': 'Rendimento Annualizzato %', 'TWR': twr_cagr, 'Reale': real_annualized},
    ]
    comparison_df = pd.DataFrame(comparison_rows)
    for col in ['TWR', 'Reale']:
        comparison_df[col] = comparison_df[col].map(
            lambda value: None if value is None or pd.isna(value) else round(float(value), 2)
        )
    return comparison_df


def build_twr_audit_table(df_history: pd.DataFrame) -> pd.DataFrame:
    """
    Costruisce una tabella di audit giornaliera del calcolo TWR senza mostrare importi in euro.

    Args:
        df_history: Serie storica normalizzata.

    Returns:
        DataFrame con metriche percentuali e indici normalizzati.
    """
    normalized_df = prepare_portfolio_timeseries(df_history)
    if normalized_df.empty:
        return pd.DataFrame(
            columns=[
                'Data',
                'Flusso Netto %',
                'Rendimento Giornaliero %',
                'TWR Cumulato %',
                'Guadagno Reale Cumulato %',
                'Indice Portafoglio',
                'Indice Versamenti Netti',
            ]
        )

    audit_df = normalized_df.copy()
    audit_df['PrevValue'] = audit_df['Valore'].shift(1)
    audit_df['NetFlow'] = _calculate_net_invested_flows(audit_df)
    daily_returns = _calculate_flow_adjusted_return_series(audit_df)

    flow_base = audit_df['PrevValue'].replace(0, np.nan)
    audit_df['Flusso Netto %'] = (audit_df['NetFlow'] / flow_base) * 100.0
    audit_df['Rendimento Giornaliero %'] = daily_returns * 100.0

    cumulative_twr = (1.0 + daily_returns.fillna(0.0)).cumprod() - 1.0
    audit_df['TWR Cumulato %'] = cumulative_twr * 100.0

    invested_base = audit_df['Investito'].replace(0, np.nan)
    audit_df['Guadagno Reale Cumulato %'] = (
        (audit_df['Valore'] - audit_df['Investito']) / invested_base
    ) * 100.0

    first_value = audit_df['Valore'].replace(0, np.nan).dropna().iloc[0] if not audit_df['Valore'].empty else np.nan
    first_invested_series = audit_df['Investito'].replace(0, np.nan).dropna()
    first_invested = first_invested_series.iloc[0] if not first_invested_series.empty else np.nan

    audit_df['Indice Portafoglio'] = (audit_df['Valore'] / first_value) * 100.0 if pd.notna(first_value) else np.nan
    audit_df['Indice Versamenti Netti'] = (
        (audit_df['Investito'] / first_invested) * 100.0 if pd.notna(first_invested) else np.nan
    )

    result_df = audit_df[
        [
            'Data',
            'Flusso Netto %',
            'Rendimento Giornaliero %',
            'TWR Cumulato %',
            'Guadagno Reale Cumulato %',
            'Indice Portafoglio',
            'Indice Versamenti Netti',
        ]
    ].copy()

    result_df['Data'] = pd.to_datetime(result_df['Data']).dt.date
    return result_df


def apply_fee_exclusion_to_invested(df_history: pd.DataFrame, df_trans: pd.DataFrame) -> pd.DataFrame:
    """
    Ricalcola Investito escludendo le commissioni e sovrascrive la colonna nella serie storica.

    Args:
        df_history: Serie storica con colonne Data, Valore, Investito.
        df_trans: Transazioni con date e local_value.

    Returns:
        DataFrame storico con Investito coerente ai soli versamenti netti (senza fees).
    """
    normalized_df = prepare_portfolio_timeseries(df_history)
    if normalized_df.empty or df_trans.empty:
        return normalized_df

    tx_df = df_trans.copy()
    tx_df['date'] = pd.to_datetime(tx_df['date'], errors='coerce').dt.normalize()
    tx_df['local_value'] = pd.to_numeric(tx_df.get('local_value', 0), errors='coerce').fillna(0.0)
    tx_df = tx_df.dropna(subset=['date'])
    if tx_df.empty:
        return normalized_df

    # local_value negativo = acquisto/versamento verso portafoglio; positivo = vendita/rientro.
    tx_daily = tx_df.groupby('date')['local_value'].sum().rename('local_value_sum')
    full_idx = pd.DatetimeIndex(normalized_df['Data'])
    invested_change = (-tx_daily).reindex(full_idx, fill_value=0.0)
    invested_ex_fees = invested_change.cumsum()

    adjusted_df = normalized_df.copy()
    adjusted_df['Investito'] = invested_ex_fees.values
    return adjusted_df


def calculate_contribution_metrics(df_history: pd.DataFrame) -> Dict[str, Optional[float]]:
    """
    Calcola metriche coerenti con i versamenti netti del portafoglio.

    Args:
        df_history: Serie storica normalizzata.

    Returns:
        Dizionario con valore corrente, investito netto e P&L.
    """
    if df_history.empty:
        return {
            'current_value': None,
            'net_invested_value': None,
            'pnl_value': None,
            'pnl_pct_on_invested': None,
        }

    current_value = float(df_history.iloc[-1]['Valore'])
    net_invested = float(df_history.iloc[-1]['Investito'])
    pnl_value = current_value - net_invested
    pnl_pct = (pnl_value / net_invested * 100.0) if net_invested > 0 else None
    return {
        'current_value': current_value,
        'net_invested_value': net_invested,
        'pnl_value': pnl_value,
        'pnl_pct_on_invested': pnl_pct,
    }


def calculate_sharpe_ratio(daily_returns: pd.Series, risk_free_rate: float = 0.02) -> Optional[float]:
    """
    Calcola lo Sharpe ratio usando il tasso risk-free annuale.

    Args:
        daily_returns: Serie rendimenti giornalieri (decimali).
        risk_free_rate: Tasso risk-free annuale in forma decimale.

    Returns:
        Sharpe ratio o None se non calcolabile.
    """
    if daily_returns.empty:
        return None

    daily_rf = (1.0 + risk_free_rate) ** (1.0 / TRADING_DAYS_PER_YEAR) - 1.0
    excess_returns = daily_returns - daily_rf
    excess_std = excess_returns.std(ddof=0)
    if excess_std <= 0:
        return None

    annualized_excess = excess_returns.mean() * TRADING_DAYS_PER_YEAR
    return float(annualized_excess / (excess_std * np.sqrt(TRADING_DAYS_PER_YEAR)))


def calculate_sortino_ratio(daily_returns: pd.Series, risk_free_rate: float = 0.02) -> Optional[float]:
    """
    Calcola il Sortino ratio usando solo la downside deviation.

    Args:
        daily_returns: Serie rendimenti giornalieri (decimali).
        risk_free_rate: Tasso risk-free annuale in forma decimale.

    Returns:
        Sortino ratio o None se non calcolabile.
    """
    if daily_returns.empty:
        return None

    daily_rf = (1.0 + risk_free_rate) ** (1.0 / TRADING_DAYS_PER_YEAR) - 1.0
    excess_returns = daily_returns - daily_rf
    downside_returns = excess_returns[excess_returns < 0]
    if downside_returns.empty:
        return None

    downside_std = downside_returns.std(ddof=0)
    if downside_std <= 0:
        return None

    annualized_excess = excess_returns.mean() * TRADING_DAYS_PER_YEAR
    return float(annualized_excess / (downside_std * np.sqrt(TRADING_DAYS_PER_YEAR)))


def calculate_calmar_ratio(cagr_pct: Optional[float], max_drawdown_pct: Optional[float]) -> Optional[float]:
    """
    Calcola il Calmar ratio come CAGR / |Max Drawdown|.

    Args:
        cagr_pct: CAGR in percentuale.
        max_drawdown_pct: Max drawdown in percentuale (negativo).

    Returns:
        Calmar ratio o None se non calcolabile.
    """
    if cagr_pct is None or max_drawdown_pct is None:
        return None
    if max_drawdown_pct == 0:
        return None
    return float(cagr_pct / abs(max_drawdown_pct))


def build_portfolio_metrics(df_history: pd.DataFrame, risk_free_rate: float = 0.02) -> Dict[str, Any]:
    """
    Costruisce le metriche principali di performance e rischio del portafoglio.

    Args:
        df_history: Serie storica portafoglio (Data, Valore).
        risk_free_rate: Tasso risk-free annuale (decimale).

    Returns:
        Dizionario con metriche aggregate.
    """
    normalized_df = prepare_portfolio_timeseries(df_history)
    if normalized_df.empty:
        return {}

    daily_returns = calculate_daily_returns(normalized_df)
    total_return_pct = calculate_period_time_weighted_return(normalized_df)
    cagr_pct = calculate_cagr(normalized_df)
    max_drawdown_pct = calculate_max_drawdown(normalized_df)
    contribution_metrics = calculate_contribution_metrics(normalized_df)

    return {
        'total_return_pct': total_return_pct,
        'cagr_pct': cagr_pct,
        'annualized_volatility_pct': calculate_annualized_volatility(daily_returns),
        'max_drawdown_pct': max_drawdown_pct,
        'sharpe_ratio': calculate_sharpe_ratio(daily_returns, risk_free_rate),
        'sortino_ratio': calculate_sortino_ratio(daily_returns, risk_free_rate),
        'calmar_ratio': calculate_calmar_ratio(cagr_pct, max_drawdown_pct),
        'best_day_pct': float(daily_returns.max() * 100.0) if not daily_returns.empty else None,
        'worst_day_pct': float(daily_returns.min() * 100.0) if not daily_returns.empty else None,
        'current_value': contribution_metrics['current_value'],
        'net_invested_value': contribution_metrics['net_invested_value'],
        'pnl_value': contribution_metrics['pnl_value'],
        'pnl_pct_on_invested': contribution_metrics['pnl_pct_on_invested'],
    }
