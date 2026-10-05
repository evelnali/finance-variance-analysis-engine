-- The curated layer:  the same money as the raw talbes, in a shape you can actually ask quetions of.  
-- Think like: a raw_TB directly exported from Oracle --> XLOOKUP against the a Mapping sheet,
-- then a raw_TB becomes a mapped_TB, which later used for Financial statements. 
-- 
-- Raw is a phtocopy file -- everything TEXT, budget and actual in separate tables, 
-- the assets's description repeated on every line. That is evidence, and it statys
-- untouched. It is not something you want to query. 
--
-- This layer is a star:  one table of things that happened in the middle, 
-- three tables of description around it - on what, of what kind, when. 
-- A description is stored once, in the table that describes it. 
--
-- Three things change here, and this is the only place they change: 
--    1. TEXT becomes numbers. "4200.00" becomes 4200.0,  once, at this bundary, 
--       so no later query has to keep saying CAST.
--    2. Budget and actual stop being two tables and become one column, scenario. 
--    3. family and uom (unit of measurement) stop repeating on every row and move to where they belong. 
--  
-- Everything here can be thrown away and rebuilt from raw. Raw cannot.
-- That is the difference between evidence and a model. 
--
-- The columns the data does not supply: run_id says which run built the row, buit_at says when.
-- "built", not "loaded" -- these rows were derived, not copied. 
--  ------------------------------------------------------------------------------------------------------


--  ----------------------------------- dim_period -------------------------------
-- One row per quarter. dim = dimension  -- a way of slicing the numbers. 
-- In a pivot table, this is what you drag into Rows or Columns. 
--
-- period_seq is the reason this table exists. '2026Q1' and '2025Q4' are just text, and text cannot tell 
-- you they are next to each other -- character by character, '2025Q4' and '2026Q1' look no closer than '2019Q2'
-- period_seq is year*4 + quarter number,  so consecutive quarters differ by exactly 1. 
-- M5 needs to ask "did this also happen the quarter before", and this is what let it. 
-- Same idea as a searial period number in a GL calendar. 
CREATE TABLE IF NOT EXISTS dim_period(
    period       TEXT PRIMARY KEY,      -- '2026Q3', the form files use
    year         INTEGER NOT NULL,      -- 2026
    quarter      INTEGER NOT NULL,      -- 3
    period_seq   INTEGER NOT NULL,      -- 8017 (2026*4 + 3)
    run_id       TEXT NOT NULL,
    built_at     TEXT NOT NULL
);



-- ------------------------------------deim_asset--------------------------------------------
-- One row per asset. The asset register, with the text turned into numbers. 
-- 
-- The blanks stay blank. A machine has no seats; software has no replacement cycle.
-- Those columns have no NOT NULL, because empty is the correct answer for them,
-- not a missing one. 
--
-- No asset_age column on pupose. Age changes every Janurary, and a stored copy would quietly go wrong. 
-- It gets worked out when needed, from acquired_year, which never changes.
CREATE TABLE IF NOT EXISTS dim_asset(
    asset_id           TEXT PRIMARY KEY,        -- 'CNC-01'
    family             TEXT NOT NULL,           -- tangible / intangible
    asset_class        TEXT NOT NULL,           -- "CNC_MACHINING_CENTRE"
    aquired_year       INTEGER NOT NULL,
    replacement_cycle_years     INTEGER,             -- blank for software
    capitalized_cost          REAL NOT NULL,
    seats                     INTEGER,
    runs_on                   TEXT, 
    notes                     TEXT,
    run_id                    TEXT NOT NULL,
    built_at                 TEXT NOT NULL
);


-- --------------- dim_cost_type -----------------------------------------------------
-- One row per kind of cost. Four rows, and it will stay four rows. 
--
-- uom sits here rather than on every transaction because it never varies:
-- a LICENSE cost is always counted in SEATs. Storing it 512 times would be 512 chances
-- for one of them to disagree with others. 
-- The build proves there is exactly one uom per cost type before writing it. 
CREATE TABLE IF NOT EXISTS dim_cost_type(
    cost_type          TEXT PRIMARY KEY,            --  PM / CM / LICENSE / SUPPORT
    family             TEXT NOT NULL,           -- which family of asset is applies to
    uom               TEXT NOT NULL,           -- WORK_ORDER / SEAT/ INCIDENT
    run_id            TEXT NOT NULL, 
    built_at           TEXT NOT NULL
);



-- ------------------- fact_expense --------------------------------------------------
-- What was expensed. One row per asset, per cost type, per quarter, per scenario. 
-- 16 assets x 2 cost types x 8 quarters x 2 scenarios = 512 rows
--
-- scenario is what lets budget and actual live in one table. Adding a forecast later is
-- then a new set of ROWS, not a change to the table's shape. If budget and actual were 
-- two columns, every new scenario would mean altering the table and every query written
-- against it. A GL stores one line per posting for the same reason, rather than column per version. 
--
-- quantity and amount are REAL here -- the conversion from text happened in the build,
-- and this layer holds numbers only. 
CREATE TABLE IF NOT EXISTS fact_expense(
    period           TEXT NOT NULL,
    asset_id         TEXT NOT NULL, 
    cost_type        TEXT NOT NULL,
    scenario         TEXT NOT NULL,           -- 'budget' or 'actual' 
    quantity         REAL NOT NULL,
    amount           REAL NOT NULL,
    run_id           TEXT NOT NULL,
    built_at         TEXT NOT NULL,



    -- Four columns together identify one row. The database will refuse a second row with same 
    -- four variables. This is C2's job done at the door instead of afterwards, -- a preventative
    -- control, where C2 is a detective one. 
    PRIMARY KEY (period, asset_id, cost_type, scenario),

    -- The three lines below are the star drawn into the table itself: an expense
    -- row must point at an asset, a cost type and a quarter that actually exist. 
    -- Same idea as data validation restricing a cell to a list. 
    -- SQLite only applies these when the connection says PRAGMA foreign_keys = ON, which curated.py
    -- does.  Written down but not switched on , they would be decoration -- the same trap as NO NULL.
    FOREIGN KEY (asset_id) REFERENCES dim_asset(asset_id),
    FOREIGN KEY (cost_type) REFERENCES dim_cost_type(cost_type),
    FOREIGN KEY (period) REFERENCES dim_period(period)
);


-- Almost every question starts with "for this quarter" of "for this asset".
-- These keep those lookups quick as the table grows. 
CREATE INDEX IF NOT EXISTS idx_fact_expense_period ON fact_expense(period);
CREATE INDEX IF NOT EXISTS idx_fact_expense_asset ON fact_expense(asset_id);
CREATE INDEX IF NOT EXISTS idx_fact_expense_scenario ON fact_expense(scenario);