-- Fill the expense table: every row of both raw tables, stacked into one.
--
-- 'budget' AS scenario stamps the word budget on every row that comes from
-- raw_budget, and 'actual' on every row from raw_actual - the same as typing
-- a label at the top of a column and filling it down. That is how two tables
-- become one without losing which was which.
--
-- UNION ALL, not UNION. File 2 used UNION to squeeze 16 rows of quarters
-- down to 8, because removing duplicates was the point. Here every row is
-- money. UNION would silently merge two identical rows into one and the total
-- would drop. UNION ALL keeps every row, so a duplicate reaches the primary
-- key and stops the build loudly instead.
--
-- family and uom are deliberately not here. They live in dim_asset and
-- dim_cost_type now, stored once each, and get looked up with a JOIN.
--
-- quantity and amount become numbers here, once. NULLIF first, as in the
-- asset build, so a blank stops the build on NOT NULL instead of becoming 0.
--
-- The whole table is rebuilt from raw every run, not one quarter at a time.
-- Raw is loaded quarter by quarter because that is what protects a closed
-- quarter. This table is derived from raw, so throwing it all away and
-- rebuilding it is always safe.
--
-- The two ? are run_id and built_at, filled in by curate.py.

INSERT INTO fact_expense (period, asset_id, cost_type, scenario,
                          quantity, amount, run_id, built_at)
SELECT NULLIF(period, ''),
       NULLIF(asset_id, ''),
       NULLIF(cost_type, ''),
       scenario,
       CAST(NULLIF(quantity, '') AS REAL),
       CAST(NULLIF(amount, '') AS REAL),
       ?, ?
FROM (
    SELECT 'budget' AS scenario, period, asset_id, cost_type, quantity, amount
    FROM raw_budget
    UNION ALL
    SELECT 'actual' AS scenario, period, asset_id, cost_type, quantity, amount
    FROM raw_actual
)
ORDER BY period, asset_id, cost_type, scenario;