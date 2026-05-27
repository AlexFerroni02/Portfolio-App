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

-- 8. BUDGET_CATEGORIES - Categorie personalizzabili per il bilancio
-- L'utente può aggiungere/rimuovere categorie; quelle di sistema sono protette
CREATE TABLE IF NOT EXISTS budget_categories (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    type TEXT NOT NULL CHECK (type IN ('Entrata', 'Uscita', 'Entrambi')),
    budget_group TEXT CHECK (budget_group IN ('necessita', 'desideri', 'risparmio') OR budget_group IS NULL),
    is_system BOOLEAN DEFAULT FALSE,
    sort_order INTEGER DEFAULT 0,
    UNIQUE (name, type)
);

-- Indice per query frequenti su tipo
CREATE INDEX IF NOT EXISTS idx_budget_categories_type ON budget_categories(type);

-- ========================================================
-- SEED: Categorie di default
-- ========================================================

-- Categorie di sistema (protette, non eliminabili)
INSERT INTO budget_categories (name, type, budget_group, is_system, sort_order) VALUES
    ('Saldo Iniziale', 'Entrata', NULL, TRUE, 0),
    ('Investimento', 'Uscita', 'risparmio', TRUE, 0),
    ('Aggiustamento Liquidità', 'Entrambi', NULL, TRUE, 0)
ON CONFLICT (name, type) DO NOTHING;

-- Categorie entrate di default
INSERT INTO budget_categories (name, type, budget_group, is_system, sort_order) VALUES
    ('Stipendio', 'Entrata', NULL, FALSE, 1),
    ('Bonus', 'Entrata', NULL, FALSE, 2),
    ('Regali', 'Entrata', NULL, FALSE, 3),
    ('Dividendi', 'Entrata', NULL, FALSE, 4),
    ('Rimborso', 'Entrata', NULL, FALSE, 5),
    ('Altro', 'Entrambi', NULL, FALSE, 99)
ON CONFLICT (name, type) DO NOTHING;

-- Categorie uscite di default (con classificazione 50/30/20)
INSERT INTO budget_categories (name, type, budget_group, is_system, sort_order) VALUES
    ('Affitto/Casa', 'Uscita', 'necessita', FALSE, 1),
    ('Spesa Alimentare', 'Uscita', 'necessita', FALSE, 2),
    ('Trasporti', 'Uscita', 'necessita', FALSE, 3),
    ('Bollette', 'Uscita', 'necessita', FALSE, 4),
    ('Salute', 'Uscita', 'necessita', FALSE, 5),
    ('Ristoranti/Svago', 'Uscita', 'desideri', FALSE, 6),
    ('Shopping', 'Uscita', 'desideri', FALSE, 7),
    ('Viaggi', 'Uscita', 'desideri', FALSE, 8)
ON CONFLICT (name, type) DO NOTHING;

-- ========================================================
-- NOTE IMPORTANTI:
-- ========================================================
-- 
-- RELAZIONI:
--   • transactions.isin → mapping.isin (join nel codice, no FK strict per flessibilità import)
--   • prices.mapping_id → mapping.id (FK con CASCADE)
--   • asset_allocation.mapping_id → mapping.id (FK con CASCADE, UNIQUE)
--   • budget.category → budget_categories.name (join nel codice, no FK strict per retrocompatibilità)
--
-- COLONNE CALCOLATE A RUNTIME (non salvate nel DB):
--   • budget.mese_anno → calcolato come df['date'].dt.strftime('%Y-%m')
--   • Liquidità → calcolata da Saldo Iniziale + Entrate - Uscite - Investimenti
--
-- FORMATO JSON:
--   • geography_json: {"italia": 30.5, "usa": 25.0, "altri": 44.5}
--   • sector_json: {"tecnologia": 40.0, "finanza": 30.0, "altro": 30.0}
--
-- CATEGORIE BUDGET:
--   Le categorie sono ora dinamiche e gestite dalla tabella budget_categories.
--   Tre categorie di sistema sono protette (is_system=TRUE):
--     • Saldo Iniziale (Entrata) - punto di partenza liquidità
--     • Investimento (Uscita) - ponte tra budget e portafoglio
--     • Aggiustamento Liquidità (Entrambi) - correzione manuale
--
-- GRUPPI REGOLA 50/30/20 (budget_group):
--   • 'necessita' → spese necessarie (obiettivo ≤ 50% entrate)
--   • 'desideri'  → spese discrezionali (obiettivo ≤ 30% entrate)
--   • 'risparmio' → risparmio/investimento (obiettivo ≥ 20% entrate)
--   • NULL        → non classificata (esclusa dal calcolo 50/30/20)
--
-- ========================================================
