import pandas as pd

from database.connection import normalize_mapping_dataframe


def test_normalize_mapping_dataframe_normalizes_and_deduplicates_isin():
    """Verifica normalizzazione ISIN/ticker e deduplica su ISIN."""
    raw_df = pd.DataFrame(
        [
            {
                "isin": " ie00abc12345 ",
                "ticker": " swda.mi ",
                "category": "Azionario",
                "proxy_ticker": None,
            },
            {
                "isin": "IE00ABC12345",
                "ticker": " vwce.mi ",
                "category": "Azionario",
                "proxy_ticker": None,
            },
            {
                "isin": " ie00def67890 ",
                "ticker": " agg ",
                "category": "Obbligazionario",
                "proxy_ticker": None,
            },
            {
                "isin": "IE00ZZZ00000",
                "ticker": "",
                "category": "Azionario",
                "proxy_ticker": None,
            },
        ]
    )

    normalized_df = normalize_mapping_dataframe(raw_df)

    assert len(normalized_df) == 2
    assert set(normalized_df["isin"].tolist()) == {"IE00ABC12345", "IE00DEF67890"}

    row_abc = normalized_df[normalized_df["isin"] == "IE00ABC12345"].iloc[0]
    row_def = normalized_df[normalized_df["isin"] == "IE00DEF67890"].iloc[0]

    assert row_abc["ticker"] == "VWCE.MI"
    assert row_def["ticker"] == "AGG"


def test_normalize_mapping_dataframe_handles_empty_input():
    """Input vuoto deve produrre DataFrame vuoto con colonne attese."""
    normalized_df = normalize_mapping_dataframe(pd.DataFrame())

    assert normalized_df.empty
    assert list(normalized_df.columns) == ["isin", "ticker", "category", "proxy_ticker"]
