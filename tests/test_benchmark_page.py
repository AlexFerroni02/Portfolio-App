import pandas as pd
import pytest
from services.benchmark_service import run_benchmark_simulation
from ui.benchmark_components import _build_cumulative_gain_df

def test_run_benchmark_simulation_logic(mocker):
    """
    Testa la logica di run_benchmark_simulation "mockando" yfinance.
    Verifica che i calcoli di base siano corretti.
    """
    # 1. Prepara dati finti (Arrange)
    df_trans = pd.DataFrame([
        {'date': pd.to_datetime('2023-01-10'), 'isin': 'ISIN1', 'local_value': -1000.0, 'quantity': 10},
    ])
    df_map = pd.DataFrame([{'isin': 'ISIN1', 'ticker': 'TICKER1'}])
    df_prices = pd.DataFrame() # Non serve per questo test semplificato

    # Dati finti che yf.download dovrebbe restituire
    mock_bench_hist = pd.Series([100.0, 101.0], index=pd.to_datetime(['2023-01-10', '2023-01-11']), name='Close')
    
    # 2. Configura il Mock (Simulazione)
    # Dici a pytest: "Quando qualcuno chiama yf.download, non eseguirlo davvero.
    # Invece, restituisci il DataFrame 'mock_bench_hist' che ho creato".
    mocker.patch('yfinance.download', return_value=pd.DataFrame(mock_bench_hist))

    # 3. Esegui la funzione (Act)
    df_chart, df_log = run_benchmark_simulation('SWDA.MI', df_trans, df_map, df_prices)

    # 4. Verifica i risultati (Assert)
    assert not df_chart.empty
    assert not df_log.empty
    
    # Il primo giorno, hai investito 1000€. Il benchmark valeva 100.
    # Quindi dovresti aver comprato 10 quote del benchmark (1000 / 100).
    assert df_log.iloc[0]['Quantità'] == 10.0
    
    # Il secondo giorno, il benchmark vale 101. Il valore del tuo benchmark dovrebbe essere 10 * 101 = 1010.
    # Cerchiamo la riga corrispondente nel df_chart
    valore_benchmark_giorno_2 = df_chart[df_chart['Data'] == pd.to_datetime('2023-01-11')]['Benchmark'].iloc[0]
    assert valore_benchmark_giorno_2 == 1010.0


def test_run_benchmark_simulation_flow_adjusted_returns_on_sell_day(mocker):
    """Una vendita con prezzo invariato non deve generare un falso drawdown nei return flow-adjusted."""
    df_trans = pd.DataFrame([
        {'date': pd.to_datetime('2024-01-27'), 'isin': 'ISIN1', 'local_value': -1000.0, 'quantity': 10.0},
        {'date': pd.to_datetime('2024-01-28'), 'isin': 'ISIN1', 'local_value': 500.0, 'quantity': -5.0},
    ])
    df_map = pd.DataFrame([{'id': 1, 'isin': 'ISIN1', 'ticker': 'TICKER1'}])
    df_prices = pd.DataFrame([
        {'mapping_id': 1, 'date': pd.to_datetime('2024-01-27'), 'close_price': 100.0},
        {'mapping_id': 1, 'date': pd.to_datetime('2024-01-28'), 'close_price': 100.0},
    ])

    mock_bench_hist = pd.Series([100.0, 100.0], index=pd.to_datetime(['2024-01-27', '2024-01-28']), name='Close')
    mocker.patch('yfinance.download', return_value=pd.DataFrame(mock_bench_hist))

    df_chart, _ = run_benchmark_simulation('SWDA.MI', df_trans, df_map, df_prices)
    sell_day = df_chart[df_chart['Data'] == pd.to_datetime('2024-01-28')].iloc[0]

    assert float(sell_day['Tu_Return']) == 0.0
    assert float(sell_day['Benchmark_Return']) == 0.0


def test_build_cumulative_gain_df_uses_real_gain_over_net_invested():
    """Guadagno cumulato deve usare valore / investito netto cumulato - 1."""
    df_chart = pd.DataFrame(
        {
            'Data': pd.to_datetime(['2024-01-01', '2024-01-02', '2024-01-03']),
            'CashFlow': [100.0, 100.0, -50.0],
            'Tu': [100.0, 220.0, 180.0],
            'Benchmark': [100.0, 210.0, 170.0],
        }
    )

    gain_df = _build_cumulative_gain_df(df_chart)

    # Investito cumulato finale: 100 + 100 - 50 = 150
    # Portafoglio: (180 / 150 - 1) * 100 = 20
    assert gain_df.iloc[-1]['Tu_GainPct'] == pytest.approx(20.0, rel=1e-12)
    # Benchmark: (170 / 150 - 1) * 100 = 13.3333...
    assert gain_df.iloc[-1]['Benchmark_GainPct'] == pytest.approx(13.3333333333, rel=1e-10)


def test_build_cumulative_gain_df_returns_empty_without_cashflow_column():
    """Senza CashFlow non si deve usare fallback non reale: output vuoto."""
    df_chart = pd.DataFrame(
        {
            'Data': pd.to_datetime(['2024-01-01', '2024-01-02']),
            'Tu': [100.0, 105.0],
            'Benchmark': [100.0, 103.0],
        }
    )

    gain_df = _build_cumulative_gain_df(df_chart)

    assert gain_df.empty