import pandas as pd
from datetime import datetime
from services.portfolio_service import calculate_liquidity

def test_calculate_liquidity_con_saldo_iniziale():
    """
    Verifica che la liquidità sia calcolata correttamente partendo da un saldo iniziale.
    Gli investimenti vengono dalla categoria 'Investimento' nel budget, non dalle transazioni.
    """
    # 1. Prepara i dati finti (Arrange)
    df_budget = pd.DataFrame([
        {'date': datetime(2023, 1, 1), 'type': 'Entrata', 'category': 'Saldo Iniziale', 'amount': 1000.0},
        {'date': datetime(2023, 1, 15), 'type': 'Entrata', 'category': 'Stipendio', 'amount': 500.0},
        {'date': datetime(2023, 1, 20), 'type': 'Uscita', 'category': 'Spesa', 'amount': 100.0},
        {'date': datetime(2023, 1, 25), 'type': 'Uscita', 'category': 'Investimento', 'amount': 200.0},
    ])

    # 2. Esegui la funzione da testare (Act)
    final_liquidity, _ = calculate_liquidity(df_budget)

    # 3. Verifica il risultato (Assert)
    # Saldo iniziale (1000) + Stipendio (500) - Spesa (100) - Investimento (200) = 1200
    assert final_liquidity == 1200.0

def test_calculate_liquidity_senza_saldo_iniziale():
    """
    Verifica che la liquidità sia calcolata correttamente come somma totale se manca il saldo iniziale.
    Gli investimenti vengono dalla categoria 'Investimento' nel budget.
    """
    # 1. Arrange
    df_budget = pd.DataFrame([
        {'date': datetime(2023, 1, 15), 'type': 'Entrata', 'category': 'Stipendio', 'amount': 1500.0},
        {'date': datetime(2023, 1, 20), 'type': 'Uscita', 'category': 'Spesa', 'amount': 300.0},
        {'date': datetime(2023, 1, 25), 'type': 'Uscita', 'category': 'Investimento', 'amount': 500.0},
    ])

    # 2. Act
    final_liquidity, _ = calculate_liquidity(df_budget)

    # 3. Assert
    # Entrate (1500) - Uscite (300) - Investimento (500) = 700
    assert final_liquidity == 700.0

def test_allocation_display_logic():
    """
    Verifica che la logica di selezione degli elementi da mostrare funzioni correttamente
    al variare di default_top_n e show_all, simulando la logica di render_allocation_card.
    """
    # Dati di test: 7 elementi con valori diversi
    data = {
        "A": 10, "B": 9, "C": 8, "D": 7, "E": 6, "F": 5, "G": 4
    }
    
    # Funzione helper locale per simulare la logica
    def get_items_to_show_local(data: dict, default_top_n: int, show_all: bool) -> list[str]:
        df = pd.DataFrame(list(data.items()), columns=["Item", "Value"]).sort_values("Value", ascending=False)
        if show_all:
            return df["Item"].tolist()
        else:
            return df.head(default_top_n)["Item"].tolist()
    
    # Test 1: default_top_n = 5, show_all = False -> primi 5 ordinati per valore desc
    result = get_items_to_show_local(data, 5, False)
    expected = ["A", "B", "C", "D", "E"]  # Ordinati per valore decrescente
    assert result == expected
    
    # Test 2: default_top_n = 5, show_all = True -> tutti 7
    result = get_items_to_show_local(data, 5, True)
    expected = ["A", "B", "C", "D", "E", "F", "G"]
    assert result == expected
    
    # Test 3: default_top_n = 3, show_all = False -> primi 3
    result = get_items_to_show_local(data, 3, False)
    expected = ["A", "B", "C"]
    assert result == expected
    
    # Test 4: default_top_n = 10 (maggiore del totale), show_all = False -> tutti
    result = get_items_to_show_local(data, 10, False)
    expected = ["A", "B", "C", "D", "E", "F", "G"]
    assert result == expected
    
    # Test 5: dati vuoti
    result = get_items_to_show_local({}, 5, False)
    assert result == []
    
    # Test 6: dati con meno elementi del default
    small_data = {"X": 1, "Y": 2}
    result = get_items_to_show_local(small_data, 5, False)
    expected = ["Y", "X"]  # Ordinati
    assert result == expected