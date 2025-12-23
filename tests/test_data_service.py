import pandas as pd
from datetime import datetime
from unittest.mock import MagicMock, ANY

from services.data_service import sync_prices

def test_sync_prices_handles_duplicates_and_replaces(mocker):
    """
    Verifica che sync_prices gestisca i duplicati e salvi i dati con il metodo 'replace'.
    
    - Simula prezzi esistenti nel DB (con mapping_id).
    - Simula il download di nuovi prezzi (con sovrapposizioni).
    - Controlla che il DataFrame finale salvato sia corretto (senza duplicati per date+mapping_id, con i valori più recenti).
    - Verifica che il metodo di salvataggio sia 'replace'.
    """
    # 1. ARRANGE: Prepara dati finti
    df_trans = pd.DataFrame([{'isin': 'ISIN1', 'quantity': 10, 'date': pd.to_datetime('2025-12-19')}])
    df_map = pd.DataFrame([{'isin': 'ISIN1', 'ticker': 'TEST.MI', 'mapping_id': 1}])

    # Dati già presenti nel database (usa mapping_id come chiave)
    prices_in_db = pd.DataFrame({
        'date': [pd.to_datetime('2025-12-19')],
        'ticker': ['TEST.MI'],
        'close_price': [100.0],
        'mapping_id': [1]  # Il DB ora usa mapping_id
    })

    # Nuovi dati scaricati da yfinance (con un duplicato e un nuovo valore)
    new_prices_from_yf = pd.DataFrame({
        'Close': [105.0, 110.0] # Il prezzo del 19/12 è aggiornato
    }, index=pd.to_datetime(['2025-12-19', '2025-12-20']))

    # 2. MOCK: Simula le dipendenze esterne
    mocker.patch('services.data_service.get_data', return_value=prices_in_db)
    mocker.patch('yfinance.download', return_value=new_prices_from_yf)
    mock_save_data = mocker.patch('services.data_service.save_data')
    mocker.patch('streamlit.progress') # Ignora la barra di avanzamento di Streamlit

    # 3. ACT: Esegui la funzione
    sync_prices(df_trans, df_map)

    # 4. ASSERT: Verifica i risultati
    # Controlla che save_data sia stato chiamato
    mock_save_data.assert_called_once()

    # Estrai gli argomenti con cui è stata chiamata save_data
    # args[0] è il DataFrame, args[1] è il nome della tabella
    # kwargs['method'] è il metodo di salvataggio
    call_args, call_kwargs = mock_save_data.call_args
    saved_df = call_args[0]
    
    # Verifica che il metodo di salvataggio sia 'replace'
    assert call_kwargs['method'] == 'replace'
    
    # Verifica che il DataFrame salvato abbia 2 righe per mapping_id=1
    # (il duplicato per date+mapping_id è stato gestito con drop_duplicates keep='last')
    df_filtered = saved_df[saved_df['mapping_id'] == 1]
    assert len(df_filtered) == 2, f"Expected 2 rows for mapping_id=1, got {len(df_filtered)}"
    
    # Verifica che il prezzo per la data duplicata ('2025-12-19') sia quello nuovo (105.0)
    price_on_duplicate_date = df_filtered[df_filtered['date'] == pd.to_datetime('2025-12-19')]['close_price'].iloc[0]
    assert price_on_duplicate_date == 105.0
    
    # Verifica che il nuovo prezzo per '2025-12-20' sia presente
    assert pd.to_datetime('2025-12-20') in df_filtered['date'].values

def test_sync_prices_no_new_data(mocker):
    import pandas as pd
    from services.data_service import sync_prices

    df_trans = pd.DataFrame([{'isin': 'ISIN1', 'quantity': 10, 'date': pd.to_datetime('2025-12-19')}])
    df_map = pd.DataFrame([{'isin': 'ISIN1', 'ticker': 'TEST.MI', 'mapping_id': 1}])
    
    # Dati già presenti nel database con mapping_id
    prices_in_db = pd.DataFrame({
        'date': [pd.to_datetime('2025-12-19')],
        'ticker': ['TEST.MI'],
        'close_price': [100.0],
        'mapping_id': [1]
    })

    # yfinance restituisce dati già presenti (stesso prezzo, stessa data)
    new_prices_from_yf = pd.DataFrame({
        'Close': [100.0]
    }, index=pd.to_datetime(['2025-12-19']))

    mocker.patch('services.data_service.get_data', return_value=prices_in_db)
    mocker.patch('yfinance.download', return_value=new_prices_from_yf)
    mock_save_data = mocker.patch('services.data_service.save_data')
    mocker.patch('streamlit.progress')

    result = sync_prices(df_trans, df_map)

    # La funzione ora salva sempre il DataFrame combinato, ma il numero di righe aggiunte deve essere 0
    # perché drop_duplicates(subset=['date', 'mapping_id'], keep='last') rimuove i duplicati
    assert result == 0, f"Expected 0 new rows added, got {result}"
    
    # Verifica che, se save_data è stato chiamato, il DataFrame abbia ancora 1 riga
    if mock_save_data.called:
        call_args, call_kwargs = mock_save_data.call_args
        saved_df = call_args[0]
        df_filtered = saved_df[saved_df['mapping_id'] == 1]
        assert len(df_filtered) == 1, f"Expected 1 row for mapping_id=1, got {len(df_filtered)}"