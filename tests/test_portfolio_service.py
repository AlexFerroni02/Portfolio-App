import pandas as pd
from datetime import datetime
from services.portfolio_service import calculate_liquidity

def test_calculate_liquidity_con_saldo_iniziale():
    """
    Verifica che la liquidità sia calcolata correttamente partendo da un saldo iniziale.
    """
    # 1. Prepara i dati finti (Arrange)
    df_budget = pd.DataFrame([
        {'date': datetime(2023, 1, 1), 'type': 'Entrata', 'category': 'Saldo Iniziale', 'amount': 1000.0},
        {'date': datetime(2023, 1, 15), 'type': 'Entrata', 'category': 'Stipendio', 'amount': 500.0},
        {'date': datetime(2023, 1, 20), 'type': 'Uscita', 'category': 'Spesa', 'amount': 100.0},
    ])
    df_trans = pd.DataFrame([
        {'date': datetime(2023, 1, 25), 'local_value': -200.0} # Investimento di 200
    ])

    # 2. Esegui la funzione da testare (Act)
    final_liquidity, _ = calculate_liquidity(df_budget, df_trans)

    # 3. Verifica il risultato (Assert)
    # Saldo iniziale (1000) + Stipendio (500) - Spesa (100) - Investimento (200) = 1200
    assert final_liquidity == 1200.0

def test_calculate_liquidity_senza_saldo_iniziale():
    """
    Verifica che la liquidità sia calcolata correttamente come somma totale se manca il saldo iniziale.
    """
    # 1. Arrange
    df_budget = pd.DataFrame([
        {'date': datetime(2023, 1, 15), 'type': 'Entrata', 'category': 'Stipendio', 'amount': 1500.0},
        {'date': datetime(2023, 1, 20), 'type': 'Uscita', 'category': 'Spesa', 'amount': 300.0},
    ])
    df_trans = pd.DataFrame([
        {'date': datetime(2023, 1, 25), 'local_value': -500.0} # Investimento di 500
    ])

    # 2. Act
    final_liquidity, _ = calculate_liquidity(df_budget, df_trans)

    # 3. Assert
    # Entrate (1500) - Uscite (300) - Investimento (500) = 700
    assert final_liquidity == 700.0