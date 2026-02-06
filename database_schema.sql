-- ========================================================
-- PORTFOLIO-ANDREA DATABASE SCHEMA
-- Compatibile con PostgreSQL / Neon DB
-- Aggiornato il: 2026-02-06
-- ========================================================

-- 1. MAPPING - Anagrafica Strumenti Finanziari
-- Fulcro del sistema: collega ISIN a ticker e categorie
CREATE TABLE IF NOT EXISTS mapping (
    id SERIAL PRIMARY KEY,
    isin TEXT UNIQUE NOT NULL,
    ticker TEXT NOT NULL,
    category TEXT NOT NULL CHECK (category IN ('Azionario', 'Obbligazionario', 'Gold', 'Liquidità')),
    proxy_ticker TEXT
);

-- Indice per ricerche frequenti su ticker
CREATE INDEX IF NOT EXISTS idx_mapping_ticker ON mapping(ticker);

-- 2. ASSET_ALLOCATION - Dati X-Ray (Geografia/Settori)
-- Contiene i dati di allocazione in formato JSON
CREATE TABLE IF NOT EXISTS asset_allocation (
    id SERIAL PRIMARY KEY,
    mapping_id INTEGER NOT NULL REFERENCES mapping(id) ON DELETE CASCADE,
    geography_json JSONB DEFAULT '{}',
    sector_json JSONB DEFAULT '{}',
    last_updated TIMESTAMP DEFAULT NOW(),
    UNIQUE (mapping_id)  -- Un solo record di allocazione per mapping
);

-- Indice per FK
CREATE INDEX IF NOT EXISTS idx_asset_allocation_mapping ON asset_allocation(mapping_id);

-- 3. TRANSACTIONS - Storico Transazioni
-- Registra acquisti e vendite importati da DEGIRO
CREATE TABLE IF NOT EXISTS transactions (
    id TEXT PRIMARY KEY,
    date DATE NOT NULL,
    product TEXT NOT NULL,
    isin TEXT NOT NULL,
    quantity DOUBLE PRECISION NOT NULL,
    local_value DOUBLE PRECISION NOT NULL,
    fees DOUBLE PRECISION DEFAULT 0,
    currency TEXT DEFAULT 'EUR'
);

-- Indici per query frequenti
CREATE INDEX IF NOT EXISTS idx_transactions_date ON transactions(date);
CREATE INDEX IF NOT EXISTS idx_transactions_isin ON transactions(isin);

-- 4. PRICES - Prezzi Storici
-- Prezzi di chiusura giornalieri per gli strumenti
CREATE TABLE IF NOT EXISTS prices (
    mapping_id INTEGER NOT NULL REFERENCES mapping(id) ON DELETE CASCADE,
    date DATE NOT NULL,
    close_price DOUBLE PRECISION NOT NULL CHECK (close_price >= 0),
    PRIMARY KEY (mapping_id, date)
);

-- Indice per query su date
CREATE INDEX IF NOT EXISTS idx_prices_date ON prices(date);

-- 5. NETWORTH_HISTORY - Storico Patrimonio Netto
-- Monitoraggio del patrimonio netto rispetto agli obiettivi
CREATE TABLE IF NOT EXISTS networth_history (
    date DATE PRIMARY KEY,
    net_worth DOUBLE PRECISION CHECK (net_worth >= 0),
    assets_value DOUBLE PRECISION CHECK (assets_value >= 0),
    liquidity DOUBLE PRECISION,
    goal DOUBLE PRECISION CHECK (goal >= 0)
);

-- 6. BUDGET - Gestione Entrate/Uscite
CREATE TABLE IF NOT EXISTS budget (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL,
    type TEXT NOT NULL CHECK (type IN ('Entrata', 'Uscita')),
    category TEXT NOT NULL,
    amount DOUBLE PRECISION NOT NULL CHECK (amount >= 0),
    note TEXT DEFAULT ''
);

-- Indici per query frequenti
CREATE INDEX IF NOT EXISTS idx_budget_date ON budget(date);
CREATE INDEX IF NOT EXISTS idx_budget_type ON budget(type);
CREATE INDEX IF NOT EXISTS idx_budget_category ON budget(category);

-- 7. SETTINGS - Impostazioni Applicazione
-- Chiave-valore per configurazioni varie
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- ========================================================
-- NOTE IMPORTANTI:
-- ========================================================
-- 
-- RELAZIONI:
--   • transactions.isin → mapping.isin (join nel codice, no FK strict per flessibilità import)
--   • prices.mapping_id → mapping.id (FK con CASCADE)
--   • asset_allocation.mapping_id → mapping.id (FK con CASCADE, UNIQUE)
--
-- COLONNE CALCOLATE A RUNTIME (non salvate nel DB):
--   • budget.mese_anno → calcolato come df['date'].dt.strftime('%Y-%m')
--
-- FORMATO JSON:
--   • geography_json: {"italia": 30.5, "usa": 25.0, "altri": 44.5}
--   • sector_json: {"tecnologia": 40.0, "finanza": 30.0, "altro": 30.0}
--
-- CATEGORIE VALIDE (budget):
--   Entrate: Stipendio, Bonus, Regali, Dividendi, Rimborso, Altro, Aggiustamento Liquidità, Saldo Iniziale
--   Uscite: Affitto/Casa, Spesa Alimentare, Ristoranti/Svago, Trasporti, Viaggi, Salute, Shopping, 
--           Bollette, Altro, Aggiustamento Liquidità, Investimento
--
-- ========================================================
