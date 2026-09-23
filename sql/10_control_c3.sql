-- C3: data completeness test
-- Every asset in the register should appear for this period with every cost type
-- its family can have. 
-- Anything expected and not found is a missing row. 
--
-- {table} is pasted in by Python before the database sees this file.
-- The ? is filled in by database itself, with the period. 
--
-- The expected set is built first, from the two reference tables.   Every expected pair
-- is then matched against the data, and only the ones that found nothing are kept. 


SELECT e.asset_id,
       e.cost_type
FROM (
    SELECT a.asset_id, c.cost_type
    FROM ref_assets a
    JOIN ref_cost_types c ON c.family = a.family               -- the 32 pairs that should exist
) e
LEFT JOIN {table} r
       ON r.asset_id = e.asset_id
       AND r.cost_type = e.cost_type
       AND r.period = ?
WHERE r.asset_id IS NULL
ORDER BY e.asset_id, e.cost_type; 
