-- Fill the cost type list: four rows, one per kind of cost. 
--
-- Two sources, because each knows something the other does not. : 
--      -- ref_cost_types (from settings.yml) knows which family each cost type belongs to. 
--          the row tables know the unit it's counted in. 
--
-- The schema promised this build would prove there is exactly one unit per cost type. 
-- The table's own rules do that proving:
--    - a cost type arriving with two different units makes two rows for it, and PRIMARY KEY refuses the second one.
--    - a cost type in settings.yml with no rows in the data gets no unit, and NOT NULL refuses it. 
--    That is why this is a LEFT JOIN starting from the setting list: a plain JOIN would quietly drop it and 
--    leave three rows. 

INSERT INTO dim_cost_type(cost_type, family, uom, run_id, built_at)
SELECT r.cost_type,
       r.family,
       u.uom, 
        ?, ?    -- filled by curated.py with run_id and built_at
FROM ref_cost_types AS r            -- r is the short name for this table. 
LEFT JOIN (
    SELECT cost_type, NULLIF(uom, '') AS uom FROM raw_budget
    UNION
    SELECT cost_type, NULLIF(uom, '') AS uom FROM raw_actual
) AS u
  ON u.cost_type = r.cost_type
ORDER BY r.cost_type;