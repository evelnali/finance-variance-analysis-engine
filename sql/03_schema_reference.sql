-- Reference data: what exists, as opposed to what happened. 
-- raw_budget and row_actual hold transactions. These two tables hold the standing data
-- those trnasactions refer to - the assset master, and the rule saying 
-- which kinds of cost each famiy of asset can have.
--
-- Both tables are wiped and rebuilt from config on every run, so they
-- cannot drift away from the files they came from. 

CREATE TABLE IF NOT EXISTS ref_assets(
    asset_id           TEXT NOT NULL,
    family             TEXT NOT NULL,
    asset_class        TEXT NOT NULL,
    acquired_year      TEXT,
    replacement_cycle_years       TEXT,    -- blank for software
    capitalized_cost             TEXT,
    seats               TEXT,    -- blank for machines
    runs_on             TEXT,    -- blank unless the software drives named machines
    notes               TEXT,
    run_id              TEXT NOT NULL,
    loaded_at           TEXT NOT NULL
);



CREATE TABLE IF NOT EXISTS ref_cost_types(
    family                TEXT NOT NULL,
    cost_type             TEXT NOT NULL,
    run_id                TEXT NOT NULL,
    loaded_at             TEXT NOT NULL
);




-- The materiality thresholds, one row per family of asset.
-- A SQL query cannot read settings.yml, so load.py copies the thresholds in here,
-- the same way it copies the cost type rule.
--
-- These two are numbers, not text. They come from settings.yml, where they are
-- already numbers, and the queries do arithmetic with them.
--
-- They are applied at one level: asset class, by cost type, by quarter.
CREATE TABLE IF NOT EXISTS ref_materiality(
    family                TEXT PRIMARY KEY NOT NULL,   -- tangible / intangible
    absolute_threshold    REAL NOT NULL,               -- dollars: 25000
    percent_threshold     REAL NOT NULL,               -- percent: 5.0 means 5%
    run_id                TEXT NOT NULL,
    loaded_at             TEXT NOT NULL
);