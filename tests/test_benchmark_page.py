import pandas as pd
from services.benchmark_service import run_benchmark_simulation

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