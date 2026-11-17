-- query_varn_by_asset: budget against actual, one line per asset, cost type and quarter.
--
-- This is a VIEW: a saved query with a name. It stores no rows of its own. Every
-- time it is read, it runs on fact_expense as it is at that moment, so it can
-- never be out of date and can never disagree with the tables.
--
-- fact_expense holds budget and actual as separate ROWS. This turns them into
-- separate COLUMNS, side by side, which is the shape a variance report needs.
--
-- varn means variance. It is actual minus budget, so for an expense:
--     positive varn = over budget
--     negative varn = under budget
--
-- Nothing is rounded here. Rounding is for display only; a rounded figure used
-- in a later calculation would stop the totals from tying.
--
-- The view is dropped and created again each time this file runs, so a change
-- to the query below always takes effect.

DROP VIEW IF EXISTS query_varn_by_asset;

CREATE VIEW query_varn_by_asset AS
SELECT s.period,
       p.period_seq,                 -- the running quarter number, for ordering and "the quarter before"
       a.family,                     -- looked up from dim_asset
       a.asset_class,
       s.asset_id,
       s.cost_type,
       c.uom,                        -- what the quantities count, looked up from dim_cost_type
       s.budget_qty,
       s.actual_qty,
       s.budget_amount,
       s.actual_amount,
       s.actual_amount - s.budget_amount                          AS varn,
       -- variance as a percent of budget. NULLIF turns a budget of 0 into
       -- "nothing", so the percent comes out empty instead of dividing by zero.
       100.0 * (s.actual_amount - s.budget_amount)
             / NULLIF(s.budget_amount, 0)                         AS varn_pct
FROM (
    -- Step 1: one line per asset, cost type and quarter, with budget and actual
    -- side by side. SUM(CASE WHEN ...) is SUMIFS: add the amount only on budget
    -- rows, or only on actual rows.
    SELECT period,
           asset_id,
           cost_type,
           SUM(CASE WHEN scenario = 'budget' THEN quantity ELSE 0 END) AS budget_qty,
           SUM(CASE WHEN scenario = 'actual' THEN quantity ELSE 0 END) AS actual_qty,
           SUM(CASE WHEN scenario = 'budget' THEN amount   ELSE 0 END) AS budget_amount,
           SUM(CASE WHEN scenario = 'actual' THEN amount   ELSE 0 END) AS actual_amount
    FROM fact_expense
    GROUP BY period, asset_id, cost_type
) AS s
-- Step 2: look up the descriptions, the way VLOOKUP would.
JOIN dim_asset     AS a ON a.asset_id  = s.asset_id
JOIN dim_cost_type AS c ON c.cost_type = s.cost_type
JOIN dim_period    AS p ON p.period    = s.period;