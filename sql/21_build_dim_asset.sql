-- Fill the asset list, from the reference copy of the asset register. 
--
-- ref_assets holds every value as text, exactly as the register file had it. 
-- This is where those become numbers. 
--
-- Every column goes through NULLIF(column,'') first. The register's empty cell arrives as 
-- empty text '',  and CAST turns '' into 0 without a word: so a machine would get 0 seats
-- and software a 0-year replacement cycle.
-- Blank means "does not apply"; 0 is a real number that claims something. 
-- NULLIF turns '' into NULL, and NULL stays NULL through CAST. 
--
-- It is applied to every column, not only the ones allowed to be blank. 
-- That way the tables own NOT NUll rules decide: a blank seat count is allowed and lands
-- as NULL; a blank capitalized cost is not, and the build stops loudly instead of recording $0. 

INSERT INTO dim_asset(asset_id, family, asset_class, acquired_year, replacement_cycle_years,
                    capitalized_cost, seats, runs_on, notes, run_id, built_at)
SELECT NULLIF(asset_id, ''),
       NULLIF(family, ''),
       NULLIF(asset_class,''), 
       CAST(NULLIF(acquired_year,'') AS INTEGER),
       CAST(NULLIF(replacement_cycle_years,'') AS INTEGER),
       CAST(NULLIF(capitalized_cost,'') AS REAL),    -- REAL: it is money
       CAST(NULLIF(seats,'') AS INTEGER),
       NULLIF(runs_on,''),
       NULLIF(notes,''),
       ?, ?    -- filled by curated.py with run_id and built_at
FROM ref_assets
ORDER BY asset_id;