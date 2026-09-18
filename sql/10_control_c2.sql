-- C2: duplicate key detection.
-- One row should exist per period, per asset, per cost type.
-- Anything appearing more than once is double counting.
--
-- Two different kinds of blank in here:
--     {table} is filled in by Python before the database ever sees this file;
--      ?      is filled by the database iteself, with the period. 
-- A table name cannot be a ?, which is why the two are handled differently. 


SELECT period,
       asset_id,
       cost_type,
       COUNT(*) AS n      -- how many rows share this key
FROM {table}
WHERE period = ?          -- one period at a time
GROUP BY period, asset_id, cost_type          -- one output row per unique combination 
HAVING COUNT(*) > 1                           -- keep only combinations appearing more than once
ORDER BY asset_id,cost_type;