-- R2: the curated layer holds exactly the same money as the raw layer.
--
-- One line per quarter and scenario, raw and curated side by side, with a
-- row count and a dollar total for each. curate.py compares them and writes
-- the result: both figures must agree, or the transform lost, doubled or
-- altered something.
--
-- Why stack and label, instead of totalling each side and joining them:
-- a join only keeps lines found on BOTH sides. A quarter missing from the
-- curated table would simply drop out, and the rec would look clean. Stacked,
-- a missing quarter still appears, with 0 on the side that lost it. The same
-- lesson as C3: you cannot find what is missing by looking only at what is there.
--
-- SUM(CASE WHEN side = 'raw' THEN amount ELSE 0 END) is SUMIFS with one
-- criterion: add up the amount, but only on rows labelled raw.
--
-- The raw side is read straight from raw_budget and raw_actual, by its own
-- route - not through the build files. If R2 reused the build's logic, a
-- mistake in the build would appear on both sides and tie perfectly.
-- A reconciliation is only worth something if the two figures were reached
-- independently.
--
-- No ? in this one. It checks every quarter at once, so it can be run
-- directly with sqlite3.

SELECT period,
       scenario,
       SUM(CASE WHEN side = 'raw'     THEN 1      ELSE 0 END)           AS raw_rows,
       ROUND(SUM(CASE WHEN side = 'raw'     THEN amount ELSE 0 END), 2) AS raw_total,
       SUM(CASE WHEN side = 'curated' THEN 1      ELSE 0 END)           AS curated_rows,
       ROUND(SUM(CASE WHEN side = 'curated' THEN amount ELSE 0 END), 2) AS curated_total
FROM (
    -- raw: stamp the side and the scenario, turn amount into a number
    SELECT 'raw' AS side, 'budget' AS scenario, period, CAST(amount AS REAL) AS amount
    FROM raw_budget
    UNION ALL
    SELECT 'raw', 'actual', period, CAST(amount AS REAL)
    FROM raw_actual
    UNION ALL
    -- curated: scenario is already a column here, amount already a number
    SELECT 'curated', scenario, period, amount
    FROM fact_expense
)
GROUP BY period, scenario
ORDER BY period, scenario;