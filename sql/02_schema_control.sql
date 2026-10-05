-- The control log and the exception listing. 
-- Every control from C2 onward one line to control_results,
-- and one line to exceptions for each item it objected to. 



CREATE TABLE IF NOT EXISTS control_results(
    run_id        TEXT NOT NULL,    -- which run wrote this line
    control_id    TEXT NOT NULL,   -- "C2"
    control_name  TEXT NOT NULL,    -- Duplicate key detection 
    target_table  TEXT NOT NULL,   -- raw_budget or raw_actual
    period      TEXT NOT NULL,    -- the period tested
    status      TEXT NOT NULL,    -- PASS or FAIL
    rows_tested   INTEGER NOT NULL,    -- how many rows the test covered
    exceptions_found      INTEGER NOT NULL,    -- 0 when it passed
    detail            TEXT NOT NULL DEFAULT '',        -- the figures a check tied, or why it failed
    checked_at        TEXT NOT NULL         -- when the test run
);


CREATE TABLE IF NOT EXISTS exceptions(
    run_id      TEXT NOT NULL,        -- NOT NULL --> No empty is allowed.
    control_id    TEXT NOT NULL,     -- which control objected
    target_table   TEXT NOT NULL,
    period       TEXT NOT NULL,
    asset_id      TEXT,            -- empty when the objection is about a whole period
    cost_type     TEXT,            -- empty for the same reason
    detail       TEXT NOT NULL, 
    found_at      TEXT NOT NULL     
);