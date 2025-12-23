import pytest
import pandas as pd
from services.rebalancing_service import (
    validate_asset_class_allocation,
    validate_ticker_distribution,
    get_ticker_price,
    build_ticker_targets,
    calculate_rebalancing_operations,
    check_budget_alignment,
    get_portfolio_summary
)


class TestValidation:
    """Test per le funzioni di validazione."""
    
    def test_validate_asset_class_allocation_valid(self):
        """Test con allocazione valida al 100%."""
        asset_classes = {"Azionario": 70, "Obbligazionario": 20, "Gold": 10}
        is_valid, error_msg = validate_asset_class_allocation(asset_classes)
        assert is_valid is True
        assert error_msg is None
    
    def test_validate_asset_class_allocation_invalid_sum(self):
        """Test con allocazione non valida (somma diversa da 100)."""
        asset_classes = {"Azionario": 60, "Obbligazionario": 20, "Gold": 10}
        is_valid, error_msg = validate_asset_class_allocation(asset_classes)
        assert is_valid is False
        assert "90.0%" in error_msg
    
    def test_validate_asset_class_allocation_over_100(self):
        """Test con allocazione superiore al 100%."""
        asset_classes = {"Azionario": 80, "Obbligazionario": 30, "Gold": 10}
        is_valid, error_msg = validate_asset_class_allocation(asset_classes)
        assert is_valid is False
        assert "120.0%" in error_msg
    
    def test_validate_ticker_distribution_valid(self):
        """Test con distribuzione ticker valida al 100%."""
        pct_inputs = {"AAPL": 50, "GOOGL": 30, "MSFT": 20}
        is_valid, error_msg = validate_ticker_distribution(pct_inputs, "Azionario")
        assert is_valid is True
        assert error_msg is None
    
    def test_validate_ticker_distribution_over_100(self):
        """Test con distribuzione ticker superiore al 100%."""
        pct_inputs = {"AAPL": 60, "GOOGL": 50, "MSFT": 20}
        is_valid, error_msg = validate_ticker_distribution(pct_inputs, "Azionario")
        assert is_valid is False
        assert "supera 100%" in error_msg
    
    def test_validate_ticker_distribution_under_100(self):
        """Test con distribuzione ticker inferiore al 100%."""
        pct_inputs = {"AAPL": 40, "GOOGL": 30, "MSFT": 20}
        is_valid, error_msg = validate_ticker_distribution(pct_inputs, "Azionario")
        assert is_valid is False
        assert "sotto 100%" in error_msg


class TestBuildTickerTargets:
    """Test per la costruzione dei target dei ticker."""
    
    def test_build_ticker_targets_single_category(self):
        """Test con una singola categoria."""
        global_pct_inputs = {"AAPL": 50, "GOOGL": 50}
        ticker_to_cat = {"AAPL": "Azionario", "GOOGL": "Azionario"}
        asset_classes = {"Azionario": 100, "Obbligazionario": 0, "Gold": 0}
        new_total = 10000
        
        targets = build_ticker_targets(
            global_pct_inputs, ticker_to_cat, asset_classes, new_total
        )
        
        assert targets["AAPL"] == 5000  # 100% * 50% * 10000
        assert targets["GOOGL"] == 5000
    
    def test_build_ticker_targets_multiple_categories(self):
        """Test con multiple categorie."""
        global_pct_inputs = {"AAPL": 100, "AGG": 100, "GLD": 100}
        ticker_to_cat = {"AAPL": "Azionario", "AGG": "Obbligazionario", "GLD": "Gold"}
        asset_classes = {"Azionario": 70, "Obbligazionario": 20, "Gold": 10}
        new_total = 10000
        
        targets = build_ticker_targets(
            global_pct_inputs, ticker_to_cat, asset_classes, new_total
        )
        
        assert targets["AAPL"] == 7000  # 70% * 100% * 10000
        assert targets["AGG"] == 2000   # 20% * 100% * 10000
        assert targets["GLD"] == 1000   # 10% * 100% * 10000
    
    def test_build_ticker_targets_split_within_category(self):
        """Test con ticker divisi all'interno della stessa categoria."""
        global_pct_inputs = {"AAPL": 60, "GOOGL": 40}
        ticker_to_cat = {"AAPL": "Azionario", "GOOGL": "Azionario"}
        asset_classes = {"Azionario": 70, "Obbligazionario": 20, "Gold": 10}
        new_total = 10000
        
        targets = build_ticker_targets(
            global_pct_inputs, ticker_to_cat, asset_classes, new_total
        )
        
        # 70% della categoria Azionario = 7000
        # AAPL prende il 60% di 7000 = 4200
        # GOOGL prende il 40% di 7000 = 2800
        assert targets["AAPL"] == pytest.approx(4200, rel=1e-9)
        assert targets["GOOGL"] == pytest.approx(2800, rel=1e-9)


class TestCalculateRebalancingOperations:
    """Test per il calcolo delle operazioni di ribilanciamento."""
    
    def test_calculate_rebalancing_buy_operation(self):
        """Test per un'operazione di acquisto."""
        ticker_targets = {"AAPL": 5000}
        assets_view = pd.DataFrame({
            "ticker": ["AAPL"],
            "mkt_val": [3000],
            "category": ["Azionario"]
        })
        global_ticker_prices = {"AAPL": 100}
        ticker_to_cat = {"AAPL": "Azionario"}
        total_portfolio = 3000
        new_total = 5000
        
        dettagli, total_cost = calculate_rebalancing_operations(
            ticker_targets, assets_view, global_ticker_prices, 
            ticker_to_cat, total_portfolio, new_total
        )
        
        assert len(dettagli) == 1
        assert dettagli[0]["Ticker"] == "AAPL"
        assert dettagli[0]["Operazione"] == "🟢 Compra"
        assert dettagli[0]["Quote"] == 20  # (5000 - 3000) / 100
        assert total_cost == 2000  # 20 * 100
    
    def test_calculate_rebalancing_sell_operation(self):
        """Test per un'operazione di vendita."""
        ticker_targets = {"AAPL": 3000}
        assets_view = pd.DataFrame({
            "ticker": ["AAPL"],
            "mkt_val": [5000],
            "category": ["Azionario"]
        })
        global_ticker_prices = {"AAPL": 100}
        ticker_to_cat = {"AAPL": "Azionario"}
        total_portfolio = 5000
        new_total = 3000
        
        dettagli, total_cost = calculate_rebalancing_operations(
            ticker_targets, assets_view, global_ticker_prices, 
            ticker_to_cat, total_portfolio, new_total
        )
        
        assert len(dettagli) == 1
        assert dettagli[0]["Ticker"] == "AAPL"
        assert dettagli[0]["Operazione"] == "🔴 Vendi"
        assert dettagli[0]["Quote"] == -20  # (3000 - 5000) / 100
        assert total_cost == -2000  # -20 * 100
    
    def test_calculate_rebalancing_new_ticker(self):
        """Test per un nuovo ticker non presente nel portafoglio."""
        ticker_targets = {"GOOGL": 2000}
        assets_view = pd.DataFrame({
            "ticker": ["AAPL"],
            "mkt_val": [5000],
            "category": ["Azionario"]
        })
        global_ticker_prices = {"GOOGL": 150}
        ticker_to_cat = {"GOOGL": "Azionario"}
        total_portfolio = 5000
        new_total = 7000
        
        dettagli, total_cost = calculate_rebalancing_operations(
            ticker_targets, assets_view, global_ticker_prices, 
            ticker_to_cat, total_portfolio, new_total
        )
        
        assert len(dettagli) == 1
        assert dettagli[0]["Ticker"] == "GOOGL"
        assert dettagli[0]["Attuale (€)"] == 0
        assert dettagli[0]["Operazione"] == "🟢 Compra"
        assert dettagli[0]["Quote"] == 13  # round(2000 / 150)
    
    def test_calculate_rebalancing_no_change_needed(self):
        """Test quando non sono necessarie operazioni (differenza minima)."""
        ticker_targets = {"AAPL": 5000}
        assets_view = pd.DataFrame({
            "ticker": ["AAPL"],
            "mkt_val": [5000],
            "category": ["Azionario"]
        })
        global_ticker_prices = {"AAPL": 100}
        ticker_to_cat = {"AAPL": "Azionario"}
        total_portfolio = 5000
        new_total = 5000
        
        dettagli, total_cost = calculate_rebalancing_operations(
            ticker_targets, assets_view, global_ticker_prices, 
            ticker_to_cat, total_portfolio, new_total
        )
        
        # Nessuna operazione perché la differenza è 0
        assert len(dettagli) == 0
        assert total_cost == 0


class TestCheckBudgetAlignment:
    """Test per il controllo dell'allineamento del budget."""
    
    def test_check_budget_alignment_aligned(self):
        """Test quando il budget è allineato (entro tolleranza)."""
        total_cost = 10000
        invest_amount = 10100
        
        is_aligned, proposed_budget = check_budget_alignment(total_cost, invest_amount)
        
        # 1% di differenza, entro la tolleranza del 5%
        assert is_aligned is True
        assert proposed_budget is None
    
    def test_check_budget_alignment_not_aligned(self):
        """Test quando il budget non è allineato (oltre tolleranza)."""
        total_cost = 10000
        invest_amount = 9000
        
        is_aligned, proposed_budget = check_budget_alignment(total_cost, invest_amount)
        
        # 11% di differenza, oltre la tolleranza del 5%
        assert is_aligned is False
        assert proposed_budget == 10000  # invest_amount + (total_cost - invest_amount)
    
    def test_check_budget_alignment_zero_budget(self):
        """Test quando il budget è 0 ma il costo totale è significativo."""
        total_cost = 200
        invest_amount = 0
        
        is_aligned, proposed_budget = check_budget_alignment(total_cost, invest_amount)
        
        # Costo > 100€ con budget 0, non allineato
        assert is_aligned is False
        assert proposed_budget == 200
    
    def test_check_budget_alignment_zero_budget_minimal_cost(self):
        """Test quando il budget è 0 e il costo totale è minimo."""
        total_cost = 50
        invest_amount = 0
        
        is_aligned, proposed_budget = check_budget_alignment(total_cost, invest_amount)
        
        # Costo < 100€ con budget 0, allineato
        assert is_aligned is True
        assert proposed_budget is None


class TestGetPortfolioSummary:
    """Test per il calcolo del riepilogo del portafoglio."""
    
    def test_get_portfolio_summary(self):
        """Test per il calcolo delle metriche di riepilogo."""
        assets_view = pd.DataFrame({
            "ticker": ["AAPL", "GOOGL", "MSFT"],
            "mkt_val": [5000, 3000, 2000],
            "pnl%": [10, 15, 5]
        })
        
        summary = get_portfolio_summary(assets_view)
        
        assert summary["total_value"] == 10000
        assert summary["num_assets"] == 3
        assert summary["avg_pnl"] == 10  # (10 + 15 + 5) / 3
    
    def test_get_portfolio_summary_empty(self):
        """Test con portafoglio vuoto."""
        assets_view = pd.DataFrame(columns=["ticker", "mkt_val", "pnl%"])
        
        summary = get_portfolio_summary(assets_view)
        
        assert summary["total_value"] == 0
        assert summary["num_assets"] == 0
        assert summary["avg_pnl"] == 0


class TestGetTickerPrice:
    """Test per il download del prezzo dei ticker (con mock)."""
    
    def test_get_ticker_price_success(self, mocker):
        """Test con download riuscito."""
        mock_ticker = mocker.MagicMock()
        mock_history = pd.DataFrame({
            "Close": [150.5]
        })
        mock_ticker.history.return_value = mock_history
        mocker.patch("yfinance.Ticker", return_value=mock_ticker)
        
        price = get_ticker_price("AAPL")
        
        assert price == 150.5
    
    def test_get_ticker_price_empty_data(self, mocker):
        """Test quando non ci sono dati disponibili."""
        mock_ticker = mocker.MagicMock()
        mock_ticker.history.return_value = pd.DataFrame()
        mocker.patch("yfinance.Ticker", return_value=mock_ticker)
        
        price = get_ticker_price("INVALID")
        
        assert price is None
    
    def test_get_ticker_price_exception(self, mocker):
        """Test quando si verifica un'eccezione."""
        mocker.patch("yfinance.Ticker", side_effect=Exception("Network error"))
        
        price = get_ticker_price("AAPL")
        
        assert price is None
