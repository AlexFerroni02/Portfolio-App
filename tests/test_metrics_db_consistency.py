import pandas as pd
import pytest

from database.connection import get_data
from services.metrics_service import (
    prepare_portfolio_timeseries,
    calculate_yearly_return_comparison,
    build_twr_real_comparison_table,
)
from services.portfolio_service import get_historical_portfolio


def _load_portfolio_timeseries_from_db() -> pd.DataFrame:
    """Carica la serie storica portafoglio usando lo stesso percorso dati della pagina Metriche."""
    df_trans = get_data("transactions")
    df_map = get_data("mapping")
    df_prices = get_data("prices")

    if df_trans.empty or df_map.empty or df_prices.empty:
        pytest.skip("DB non pronto: transazioni/mapping/prezzi mancanti")

    hist_df = get_historical_portfolio(df_trans, df_map, df_prices)
    portfolio_df = prepare_portfolio_timeseries(hist_df)
    if portfolio_df.empty or len(portfolio_df) < 2:
        pytest.skip("Serie storica insufficiente per test di consistenza")
    return portfolio_df


def test_db_yearly_real_period_matches_cumulative_endpoints():
    """Il reale di periodo annuale deve derivare dagli endpoint della serie cumulata reale del DB."""
    portfolio_df = _load_portfolio_timeseries_from_db()

    comparison_df = calculate_yearly_return_comparison(portfolio_df)
    assert not comparison_df.empty

    yearly_df = portfolio_df.copy()
    yearly_df["Year"] = yearly_df["Data"].dt.year.astype(int)

    for _, row in comparison_df.iterrows():
        year = int(row["Year"])
        year_slice = yearly_df[yearly_df["Year"] == year].sort_values("Data")
        if year_slice.empty:
            continue

        start_row = year_slice.iloc[0]
        end_row = year_slice.iloc[-1]

        start_real_cum = ((float(start_row["Valore"]) - float(start_row["Investito"])) / float(start_row["Investito"])) * 100.0
        end_real_cum = ((float(end_row["Valore"]) - float(end_row["Investito"])) / float(end_row["Investito"])) * 100.0

        expected_period_pct = ((1.0 + end_real_cum / 100.0) / (1.0 + start_real_cum / 100.0) - 1.0) * 100.0
        computed_period_pct = float(row["RealPeriodPct"])
        assert computed_period_pct == pytest.approx(expected_period_pct, rel=1e-9)


def test_db_real_total_matches_latest_cumulative_value():
    """Il reale totale in tabella confronto deve combaciare con il cumulato reale dell'ultimo giorno DB."""
    portfolio_df = _load_portfolio_timeseries_from_db()

    summary_df = build_twr_real_comparison_table(portfolio_df)
    assert not summary_df.empty

    real_total_row = summary_df[summary_df["Metrica"] == "Rendimento Totale %"]
    assert not real_total_row.empty

    computed_real_total = float(real_total_row.iloc[0]["Reale"])
    last_row = portfolio_df.sort_values("Data").iloc[-1]
    expected_real_total = ((float(last_row["Valore"]) - float(last_row["Investito"])) / float(last_row["Investito"])) * 100.0

    # In tabella viene mostrato arrotondato a 2 decimali.
    assert computed_real_total == pytest.approx(round(expected_real_total, 2), rel=1e-12)
