-- ========================================================
-- MIGRAZIONE: Aggiunta Constraints a DB Esistente
-- Portfolio-Andrea - PostgreSQL / Neon DB
-- Eseguire nell'ordine indicato
-- ========================================================

-- ========================================================
-- STEP 1: PULIZIA DATI (verifica prima, poi pulisci se necessario)
-- ========================================================

-- Verifica valori problematici (esegui prima!)
-- SELECT * FROM mapping WHERE category NOT IN ('Azionario', 'Obbligazionario', 'Gold', 'Liquidità') OR category IS NULL OR ticker IS NULL;
-- SELECT * FROM budget WHERE type NOT IN ('Entrata', 'Uscita') OR amount < 0;
-- SELECT * FROM prices WHERE mapping_id NOT IN (SELECT id FROM mapping);
-- SELECT * FROM asset_allocation WHERE mapping_id NOT IN (SELECT id FROM mapping);

-- Elimina record orfani (se presenti)
DELETE FROM prices WHERE mapping_id NOT IN (SELECT id FROM mapping WHERE id IS NOT NULL);
DELETE FROM asset_allocation WHERE mapping_id NOT IN (SELECT id FROM mapping WHERE id IS NOT NULL);

-- ========================================================
-- STEP 2: FOREIGN KEYS CON CASCADE
-- ========================================================

-- asset_allocation
ALTER TABLE asset_allocation DROP CONSTRAINT IF EXISTS asset_allocation_mapping_id_fkey;
ALTER TABLE asset_allocation ADD CONSTRAINT asset_allocation_mapping_id_fkey 
    FOREIGN KEY (mapping_id) REFERENCES mapping(id) ON DELETE CASCADE;

-- prices
ALTER TABLE prices DROP CONSTRAINT IF EXISTS prices_mapping_id_fkey;
ALTER TABLE prices ADD CONSTRAINT prices_mapping_id_fkey 
    FOREIGN KEY (mapping_id) REFERENCES mapping(id) ON DELETE CASCADE;

-- ========================================================
-- STEP 3: NOT NULL CONSTRAINTS
-- ========================================================

-- mapping
ALTER TABLE mapping ALTER COLUMN ticker SET NOT NULL;
ALTER TABLE mapping ALTER COLUMN category SET NOT NULL;

-- asset_allocation
ALTER TABLE asset_allocation ALTER COLUMN mapping_id SET NOT NULL;

-- transactions
ALTER TABLE transactions ALTER COLUMN date SET NOT NULL;
ALTER TABLE transactions ALTER COLUMN product SET NOT NULL;
ALTER TABLE transactions ALTER COLUMN isin SET NOT NULL;
ALTER TABLE transactions ALTER COLUMN quantity SET NOT NULL;
ALTER TABLE transactions ALTER COLUMN local_value SET NOT NULL;

-- prices
ALTER TABLE prices ALTER COLUMN mapping_id SET NOT NULL;
ALTER TABLE prices ALTER COLUMN date SET NOT NULL;
ALTER TABLE prices ALTER COLUMN close_price SET NOT NULL;

-- budget
ALTER TABLE budget ALTER COLUMN date SET NOT NULL;
ALTER TABLE budget ALTER COLUMN type SET NOT NULL;
ALTER TABLE budget ALTER COLUMN category SET NOT NULL;
ALTER TABLE budget ALTER COLUMN amount SET NOT NULL;

-- settings
ALTER TABLE settings ALTER COLUMN value SET NOT NULL;

-- ========================================================
-- STEP 4: CHECK CONSTRAINTS
-- ========================================================

-- mapping.category
ALTER TABLE mapping DROP CONSTRAINT IF EXISTS mapping_category_check;
ALTER TABLE mapping ADD CONSTRAINT mapping_category_check 
    CHECK (category IN ('Azionario', 'Obbligazionario', 'Gold', 'Liquidità'));

-- budget.type
ALTER TABLE budget DROP CONSTRAINT IF EXISTS budget_type_check;
ALTER TABLE budget ADD CONSTRAINT budget_type_check 
    CHECK (type IN ('Entrata', 'Uscita'));

-- budget.amount >= 0
ALTER TABLE budget DROP CONSTRAINT IF EXISTS budget_amount_check;
ALTER TABLE budget ADD CONSTRAINT budget_amount_check CHECK (amount >= 0);

-- prices.close_price >= 0
ALTER TABLE prices DROP CONSTRAINT IF EXISTS prices_close_price_check;
ALTER TABLE prices ADD CONSTRAINT prices_close_price_check CHECK (close_price >= 0);

-- networth_history checks
ALTER TABLE networth_history DROP CONSTRAINT IF EXISTS networth_history_net_worth_check;
ALTER TABLE networth_history ADD CONSTRAINT networth_history_net_worth_check CHECK (net_worth >= 0);

ALTER TABLE networth_history DROP CONSTRAINT IF EXISTS networth_history_assets_value_check;
ALTER TABLE networth_history ADD CONSTRAINT networth_history_assets_value_check CHECK (assets_value >= 0);

ALTER TABLE networth_history DROP CONSTRAINT IF EXISTS networth_history_goal_check;
ALTER TABLE networth_history ADD CONSTRAINT networth_history_goal_check CHECK (goal >= 0);

-- ========================================================
-- STEP 5: UNIQUE CONSTRAINTS
-- ========================================================

-- asset_allocation: un solo record per mapping
ALTER TABLE asset_allocation DROP CONSTRAINT IF EXISTS asset_allocation_mapping_id_key;
ALTER TABLE asset_allocation ADD CONSTRAINT asset_allocation_mapping_id_key UNIQUE (mapping_id);

-- ========================================================
-- STEP 6: DEFAULTS
-- ========================================================

ALTER TABLE asset_allocation ALTER COLUMN geography_json SET DEFAULT '{}';
ALTER TABLE asset_allocation ALTER COLUMN sector_json SET DEFAULT '{}';
ALTER TABLE transactions ALTER COLUMN fees SET DEFAULT 0;
ALTER TABLE transactions ALTER COLUMN currency SET DEFAULT 'EUR';
ALTER TABLE budget ALTER COLUMN note SET DEFAULT '';

-- ========================================================
-- STEP 7: INDICI PER PERFORMANCE
-- ========================================================

CREATE INDEX IF NOT EXISTS idx_mapping_ticker ON mapping(ticker);
CREATE INDEX IF NOT EXISTS idx_asset_allocation_mapping ON asset_allocation(mapping_id);
CREATE INDEX IF NOT EXISTS idx_transactions_date ON transactions(date);
CREATE INDEX IF NOT EXISTS idx_transactions_isin ON transactions(isin);
CREATE INDEX IF NOT EXISTS idx_prices_date ON prices(date);
CREATE INDEX IF NOT EXISTS idx_budget_date ON budget(date);
CREATE INDEX IF NOT EXISTS idx_budget_type ON budget(type);
CREATE INDEX IF NOT EXISTS idx_budget_category ON budget(category);

-- ========================================================
-- VERIFICA FINALE
-- ========================================================
-- Esegui per verificare i constraint creati:
-- SELECT conname, contype FROM pg_constraint WHERE conrelid IN 
--   ('mapping'::regclass, 'budget'::regclass, 'prices'::regclass, 'asset_allocation'::regclass);
