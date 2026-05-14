import pandas as pd
import pytest

from services.metrics_service import (
    prepare_portfolio_timeseries,
    apply_fee_exclusion_to_invested,
    calculate_period_time_weighted_return,
    calculate_ytd_return,
    calculate_return_from_date,
    calculate_max_drawdown,
    calculate_yearly_returns,
    calculate_yearly_return_comparison,
    build_twr_real_comparison_table,
    build_twr_audit_table,
    build_portfolio_metrics,
)


def _build_sample_history() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Data": pd.to_datetime(
                [
                    "2024-01-01",
                    "2024-01-02",
                    "2024-01-03",
                    "2024-12-31",
                    "2025-01-01",
                    "2025-05-01",
                ]
            ),
            "Valore": [100.0, 110.0, 90.0, 120.0, 130.0, 150.0],
        }
    )


def _build_history_with_contributions() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Data": pd.to_datetime(
                [
                    "2025-01-01",
                    "2025-01-02",
                    "2025-01-03",
                ]
            ),
            "Valore": [100.0, 200.0, 220.0],
            "Investito": [100.0, 200.0, 200.0],
        }
    )


def test_calculate_ytd_return():
    """Il rendimento YTD deve usare il primo valore disponibile dell'anno corrente."""
    history_df = prepare_portfolio_timeseries(_build_sample_history())

    ytd_return = calculate_ytd_return(history_df)

    assert ytd_return == pytest.approx(((150.0 / 130.0) - 1.0) * 100.0, rel=1e-9)


def test_time_weighted_return_handles_contributions():
    """I versamenti non devono gonfiare il rendimento (TWR)."""
    history_df = prepare_portfolio_timeseries(_build_history_with_contributions())

    twr_return = calculate_period_time_weighted_return(history_df)

    assert twr_return == pytest.approx(10.0, rel=1e-9)


def test_calculate_return_from_date():
    """Il rendimento personalizzato deve partire dalla data richiesta."""
    history_df = prepare_portfolio_timeseries(_build_sample_history())

    period_return = calculate_return_from_date(history_df, pd.Timestamp("2024-01-02").date())

    assert period_return == pytest.approx(((150.0 / 110.0) - 1.0) * 100.0, rel=1e-9)


def test_calculate_max_drawdown():
    """Il max drawdown deve rappresentare il peggior calo peak-to-trough."""
    history_df = prepare_portfolio_timeseries(_build_sample_history())

    mdd = calculate_max_drawdown(history_df)

    assert mdd == pytest.approx(-18.18181818, rel=1e-6)


def test_calculate_yearly_returns():
    """Il rendimento anno per anno deve essere calcolato in percentuale TWR."""
    yearly_history_df = pd.DataFrame(
        {
            "Data": pd.to_datetime([
                "2024-12-31",
                "2025-01-01",
                "2025-12-31",
                "2026-01-02",
            ]),
            "Valore": [100.0, 200.0, 220.0, 242.0],
            "Investito": [100.0, 200.0, 200.0, 200.0],
        }
    )
    history_df = prepare_portfolio_timeseries(yearly_history_df)

    yearly_returns_df = calculate_yearly_returns(history_df)

    assert yearly_returns_df['Year'].tolist() == [2025, 2026]
    assert yearly_returns_df['ReturnPct'].iloc[0] == pytest.approx(10.0, rel=1e-9)
    assert yearly_returns_df['ReturnPct'].iloc[1] == pytest.approx(10.0, rel=1e-9)


def test_build_portfolio_metrics_returns_expected_keys():
    """Le metriche aggregate devono includere i campi principali di analisi."""
    history_df = prepare_portfolio_timeseries(_build_sample_history())

    metrics = build_portfolio_metrics(history_df, risk_free_rate=0.0)

    expected_keys = {
        "total_return_pct",
        "cagr_pct",
        "annualized_volatility_pct",
        "max_drawdown_pct",
        "sharpe_ratio",
        "sortino_ratio",
        "calmar_ratio",
        "best_day_pct",
        "worst_day_pct",
        "current_value",
        "net_invested_value",
        "pnl_value",
        "pnl_pct_on_invested",
    }
    assert set(metrics.keys()) == expected_keys
    assert metrics["total_return_pct"] == pytest.approx(50.0, rel=1e-9)


def test_apply_fee_exclusion_to_invested_rebuilds_invested_series_without_fees():
    """Investito deve essere ricalcolato usando solo local_value, senza commissioni."""
    history_df = pd.DataFrame(
        {
            "Data": pd.to_datetime(["2025-01-01", "2025-01-02", "2025-01-03"]),
            "Valore": [100.0, 105.0, 110.0],
            "Investito": [101.0, 206.0, 206.0],
        }
    )
    tx_df = pd.DataFrame(
        {
            "date": pd.to_datetime(["2025-01-01", "2025-01-02"]),
            "local_value": [-100.0, -100.0],
            "fees": [1.0, 5.0],
        }
    )

    adjusted_df = apply_fee_exclusion_to_invested(history_df, tx_df)

    assert adjusted_df["Investito"].tolist() == [100.0, 200.0, 200.0]


def test_calculate_yearly_return_comparison_contains_twr_and_real_gain():
    """Confronto annuale deve esporre entrambe le metriche percentuali."""
    history_df = pd.DataFrame(
        {
            "Data": pd.to_datetime(["2024-12-31", "2025-12-31", "2026-12-31"]),
            "Valore": [100.0, 120.0, 132.0],
            "Investito": [100.0, 100.0, 100.0],
        }
    )

    comparison_df = calculate_yearly_return_comparison(history_df)

    assert set(comparison_df.columns) == {
        "Year",
        "TwrPeriodPct",
        "RealPeriodPct",
        "TwrAnnualizedPct",
        "RealAnnualizedPct",
    }
    assert 2025 in comparison_df["Year"].tolist()
    assert 2026 in comparison_df["Year"].tolist()


def test_yearly_comparison_matches_when_no_flows_in_year():
    """Se non ci sono flussi, TWR annualizzato e Reale annualizzato devono coincidere."""
    history_df = pd.DataFrame(
        {
            "Data": pd.to_datetime(["2026-01-01", "2026-02-01", "2026-03-01"]),
            "Valore": [100.0, 105.0, 110.0],
            "Investito": [100.0, 100.0, 100.0],
        }
    )

    comparison_df = calculate_yearly_return_comparison(history_df)

    row_2026 = comparison_df[comparison_df["Year"] == 2026].iloc[0]
    assert row_2026["TwrAnnualizedPct"] == pytest.approx(row_2026["RealAnnualizedPct"], rel=1e-9)


def test_build_twr_real_comparison_table_contains_expected_rows():
    """La tabella comparativa deve includere righe per totale e annualizzato."""
    history_df = pd.DataFrame(
        {
            "Data": pd.to_datetime(["2024-01-01", "2025-01-01", "2026-01-01"]),
            "Valore": [100.0, 110.0, 132.0],
            "Investito": [100.0, 100.0, 100.0],
        }
    )

    comparison_df = build_twr_real_comparison_table(history_df)

    assert set(comparison_df.columns) == {"Metrica", "TWR", "Reale"}
    assert "Rendimento Totale %" in comparison_df["Metrica"].tolist()
    assert "Rendimento Annualizzato %" in comparison_df["Metrica"].tolist()


def test_build_twr_audit_table_contains_only_percentage_or_index_columns():
    """Audit TWR deve includere colonne leggibili per verifica riga-per-riga."""
    history_df = pd.DataFrame(
        {
            "Data": pd.to_datetime(["2025-01-01", "2025-01-02", "2025-01-03"]),
            "Valore": [100.0, 110.0, 121.0],
            "Investito": [100.0, 100.0, 100.0],
        }
    )

    audit_df = build_twr_audit_table(history_df)

    expected_columns = {
        "Data",
        "Flusso Netto %",
        "Rendimento Giornaliero %",
        "TWR Cumulato %",
        "Guadagno Reale Cumulato %",
        "Indice Portafoglio",
        "Indice Versamenti Netti",
    }
    assert set(audit_df.columns) == expected_columns
    assert len(audit_df) == 3
