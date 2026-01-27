import streamlit as st

# Lista dei comandi SQL per creare le tabelle
# Usiamo "IF NOT EXISTS" per rendere lo script eseguibile più volte senza errori.
CREATE_TABLE_COMMANDS = [
    """
    CREATE TABLE IF NOT EXISTS transactions (
        id VARCHAR(255) PRIMARY KEY,
        date DATE,
        product VARCHAR(255),
        isin VARCHAR(50),
        quantity NUMERIC(20, 10),
        local_value NUMERIC(20, 10),
        fees NUMERIC(20, 10),
        currency VARCHAR(10)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS mapping (
        id SERIAL PRIMARY KEY,
        isin VARCHAR(50) UNIQUE NOT NULL,
        ticker VARCHAR(50),
        category VARCHAR(50)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS prices (
        mapping_id INTEGER,
        date DATE,
        close_price NUMERIC(20, 10),
        PRIMARY KEY (mapping_id, date)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS budget (
        id SERIAL PRIMARY KEY,
        date DATE,
        type VARCHAR(50),
        category VARCHAR(100),
        amount NUMERIC(20, 2),
        note TEXT
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS asset_allocation (
        id SERIAL PRIMARY KEY,
        mapping_id INTEGER,
        geography_json JSON,
        sector_json JSON,
        last_updated TIMESTAMP DEFAULT NOW()
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS networth_history (
        date DATE PRIMARY KEY,
        net_worth NUMERIC(20, 2),
        assets_value NUMERIC(20, 2),
        liquidity NUMERIC(20, 2)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS settings (
        key VARCHAR(50) PRIMARY KEY,
        value TEXT
    );
    """
]

def setup():
    """
    Esegue i comandi SQL per creare/aggiornare le tabelle del database.
    """
    st.title("🛠️ Setup Database")
    st.info("Questo script creerà o aggiornerà le tabelle nel tuo database Neon per assicurare che l'applicazione funzioni correttamente.")

    if st.button("🚀 Avvia Creazione/Verifica Tabelle", type="primary"):
        try:
            conn = st.connection("postgresql", type="sql")
            
            with conn.session as s:
                st.info("Connessione al database stabilita...")
                for command in CREATE_TABLE_COMMANDS:
                    table_name = command.split("TABLE IF NOT EXISTS ")[1].split(" ")[0]
                    st.write(f"Verificando/Creando la tabella `{table_name}`...")
                    s.execute(command)
                s.commit()
            
            st.success("✅ Tutte le tabelle sono state create/verificate con successo!")
            st.balloons()
            st.info("Ora puoi chiudere questa pagina e avviare l'app principale con `streamlit run app.py`")

        except Exception as e:
            st.error(f"❌ Si è verificato un errore: {e}")

if __name__ == "__main__":
    setup()