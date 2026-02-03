-- ========================================================
-- PORTFOLIO-ANDREA DATABASE SCHEMA
-- Compatibile con PostgreSQL / Neon DB
-- Generato il: 2026-02-03
-- ========================================================

-- 1. MAPPING - Anagrafica Strumenti Finanziari
-- Fulcro del sistema: collega ISIN a ticker e categorie
CREATE TABLE IF NOT EXISTS mapping (
    id SERIAL PRIMARY KEY,
    isin TEXT UNIQUE NOT NULL,
    ticker TEXT,
    category TEXT,
    proxy_ticker TEXT
);

-- 2. ASSET_ALLOCATION - Dati X-Ray (Geografia/Settori)
-- Contiene i dati di allocazione in formato JSON
CREATE TABLE IF NOT EXISTS asset_allocation (
    id SERIAL PRIMARY KEY,
    mapping_id INTEGER REFERENCES mapping(id),
    geography_json JSONB,
    sector_json JSONB,
    last_updated TIMESTAMP DEFAULT NOW()
);

-- 3. TRANSACTIONS - Storico Transazioni
-- Registra acquisti e vendite importati da DEGIRO
CREATE TABLE IF NOT EXISTS transactions (
    id TEXT PRIMARY KEY,
    date DATE,
    product TEXT,
    isin TEXT,
    quantity DOUBLE PRECISION,
    local_value DOUBLE PRECISION,
    fees DOUBLE PRECISION,
    currency TEXT
);

-- 4. PRICES - Prezzi Storici
-- Prezzi di chiusura giornalieri per gli strumenti
CREATE TABLE IF NOT EXISTS prices (
    mapping_id INTEGER REFERENCES mapping(id),
    date DATE,
    close_price DOUBLE PRECISION,
    PRIMARY KEY (mapping_id, date)
);

-- 5. NETWORTH_HISTORY - Storico Patrimonio Netto
-- Monitoraggio del patrimonio netto rispetto agli obiettivi
CREATE TABLE IF NOT EXISTS networth_history (
    date DATE PRIMARY KEY,
    net_worth DOUBLE PRECISION,
    assets_value DOUBLE PRECISION,
    liquidity DOUBLE PRECISION,
    goal DOUBLE PRECISION
);

-- 6. BUDGET - Gestione Entrate/Uscite
-- Nota: "mese_anno" è calcolato a runtime, non salvato nel DB
CREATE TABLE IF NOT EXISTS budget (
    id SERIAL PRIMARY KEY,
    date DATE,
    type TEXT,
    category TEXT,
    amount DOUBLE PRECISION,
    note TEXT
);

-- 7. SETTINGS - Impostazioni Applicazione
-- Chiave-valore per configurazioni varie
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
);

-- ========================================================
-- NOTE IMPORTANTI:
-- ========================================================
-- 
-- RELAZIONI IMPLICITE (usate nel codice ma senza FK strict):
--   • transactions.isin → mapping.isin (join nel codice)
--   • prices.mapping_id → mapping.id (FK esplicita)
--   • asset_allocation.mapping_id → mapping.id (FK esplicita)
--
-- COLONNE CALCOLATE A RUNTIME (non salvate nel DB):
--   • budget.mese_anno → calcolato come df['date'].dt.strftime('%Y-%m')
--
-- FORMATO JSON:
--   • geography_json: {"italia": 30.5, "usa": 25.0, "altri": 44.5}
--   • sector_json: {"tecnologia": 40.0, "finanza": 30.0, "altro": 30.0}
--
-- ========================================================
