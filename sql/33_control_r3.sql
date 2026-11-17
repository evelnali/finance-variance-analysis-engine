-- R3: the three saved queries hold the same money as the expense table,
-- and volume plus price adds back to the variance.
--
-- One line per check. Each line gives the figure that is EXPECTED and the
-- figure that was FOUND. analyze.py compares the two and writes the result.
--
-- The expected side is read straight from fact_expense wherever it can be, by
-- its own route and not through the queries. If R3 trusted a query to check a
-- query, a mistake in the first one would show on both sides and tie.
--
-- (SELECT SUM(...) FROM ...) in brackets is a query that gives back one number.
-- It can be used anywhere a number can.
--
-- UNION ALL stacks the checks into one list.
--
-- No ? in this file, so it can be run directly with sqlite3.

SELECT 'query_varn_by_asset: budget total' AS check_name,
       (SELECT SUM(amount) FROM fact_expense WHERE scenario = 'budget')      AS expected,
       (SELECT SUM(budget_amount) FROM query_varn_by_asset)                  AS found
UNION ALL
SELECT 'query_varn_by_asset: actual total',
       (SELECT SUM(amount) FROM fact_expense WHERE scenario = 'actual'),
       (SELECT SUM(actual_amount) FROM query_varn_by_asset)
UNION ALL
-- one line in the query for every asset, cost type and quarter in the expense table
SELECT 'query_varn_by_asset: number of lines',
       (SELECT COUNT(*) FROM (SELECT DISTINCT period, asset_id, cost_type FROM fact_expense)),
       (SELECT COUNT(*) FROM query_varn_by_asset)
UNION ALL
SELECT 'query_varn_price_volume: volume + price, in total',
       (SELECT SUM(CASE WHEN scenario = 'actual' THEN amount ELSE -amount END) FROM fact_expense),
       (SELECT SUM(volume_effect + price_effect) FROM query_varn_price_volume)
UNION ALL
-- and line by line: how many lines have volume + price different from the variance
SELECT 'query_varn_price_volume: lines where volume + price is not the variance',
       0,
       (SELECT COUNT(*) FROM query_varn_price_volume
        WHERE ABS(volume_effect + price_effect - varn) > 0.005
           OR volume_effect IS NULL OR price_effect IS NULL)
UNION ALL
SELECT 'query_varn_by_class: budget total',
       (SELECT SUM(amount) FROM fact_expense WHERE scenario = 'budget'),
       (SELECT SUM(budget_amount) FROM query_varn_by_class)
UNION ALL
SELECT 'query_varn_by_class: actual total',
       (SELECT SUM(amount) FROM fact_expense WHERE scenario = 'actual'),
       (SELECT SUM(actual_amount) FROM query_varn_by_class)
UNION ALL
SELECT 'query_varn_by_class: volume + price, in total',
       (SELECT SUM(CASE WHEN scenario = 'actual' THEN amount ELSE -amount END) FROM fact_expense),
       (SELECT SUM(volume_effect + price_effect) FROM query_varn_by_class)
UNION ALL
-- every asset line must have been counted into exactly one class line
SELECT 'query_varn_by_class: asset lines counted',
       (SELECT COUNT(*) FROM (SELECT DISTINCT period, asset_id, cost_type FROM fact_expense)),
       (SELECT SUM(assets) FROM query_varn_by_class);