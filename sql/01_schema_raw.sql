-- ----------------------------------------------------------------
-- The raw tables : a copy of each file exactly as it arrived.
--
-- Every column says TEXT, including amount. That is deliberate. These tables exist
-- so you can always point at a row here and show it matches a line in the file. 
-- Turning "35000.0" in to a number is a change, however small, and a changed copy proves nothing. 
-- 
-- It also keeps the load from falling over. If a file ever arrived with "n/a" where a number should be,
-- storing it as text lets the run continue and lets a control test report it. 
-- Trying to store it at a number would stop the run with an error and nothing would land at all. 
--
-- The numbers get turned into numbers later, in the tidied table at M4.
--
-- run_id and loaded_at are the only two columns the file do not supply. 
-- run_id syas which run put the row here; laoded_at says when.
-- ----------------------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS raw_budget(
    period         TEXT,
    asset_id        TEXT,
    family         TEXT,
    cost_type    TEXT,
    quantity      TEXT,
    uom          TEXT,
    amount     TEXT,
    run_id      TEXT NOT NULL,
    loaded_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS raw_actual(
    period         TEXT,
    asset_id        TEXT,
    family         TEXT,
    cost_type    TEXT,
    quantity      TEXT,
    uom          TEXT,
    amount     TEXT,
    run_id      TEXT NOT NULL,
    loaded_at    TEXT NOT NULL
);

-- Nearly every question the pipeline asks starts with "for this quarter". 
-- These two lines tell the database to keep the period column sorted, behind the scene, so 
-- finding one quarter's row statys quick as the table grows. Same idea as sorting 
-- a spreadsheet column before you start looking things up in it. 
CREATE INDEX IF NOT EXISTS idx_raw_budget_period ON raw_budget(period);
CREATE INDEX IF NOT EXISTS idx_raw_actual_period ON raw_actual(period);