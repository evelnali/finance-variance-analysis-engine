-- C4: mapping coverage
-- every row must refer to an asset in the register, with a cost type its family can have.
-- Cathes an unknow asset, and known asset carrying the wrong kind of cost -
-- eg. machine with a LICENSE charge
--
-- This is C3 with te two sides swapped. C3 keeps all the EXPECTED rows and looks for ones
-- the data never matched. 
-- C4 keeps all the DATA rows and looks for ones the register never matched. 

SELECT r.asset_id,
       r.cost_type
FROM {table} r
LEFT JOIN (
    SELECT a.asset_id, c.cost_type
    FROM ref_assets a
    JOIN ref_cost_types c ON c.family = a.family 
) e ON e.asset_id = r.asset_id
    AND e.cost_type = r.cost_type
WHERE r.period = ?           -- on the left table, so it belongs in WHERE
  AND e.asset_id IS NULL       -- nothing in the register matched this row
ORDER BY r.asset_id, r.cost_type;