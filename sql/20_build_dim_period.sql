-- Fill the quarter list. 
--
-- Built from the periods that actually appear in the raw tables, not from a hand-typed list.
-- A hand-typed list is one more thing to keep in step with reality, and it would be wrong
-- the first time a new quarter starts. 
--
-- period_seq is the point of this table. '2025Q4' and '2026Q1' are next to each other in a 
-- fiscal year and nowhere each other as text. 
-- 2025*4 +4 = 8034, 2026*4 +1 = 8035, and the difference is exactly 1.

INSERT INTO dim_period(period, year, quarter, period_seq, run_id, built_at)
SELECT period,
        -- '2026Q3' --> the year. SUSBSTR(text, start, how many) cuts characters of text.
        -- Position 1 , four characters long, gives '2026'. 
        -- same job as Excel =MID(A1,1,4) 
        CAST(SUBSTR(period, 1, 4) AS INTEGER),

        -- position 6, one character long, gives '3'. Position 5 is the 'Q' in '2026Q3'
        CAST(SUBSTR(period, 6, 1) AS INTEGER),

        -- year*4 + quarter number: converting to one unit, so consecutive quarters differ by exactly 1. 
        -- The way 3 years 7 months becomes 43 months, consecutive quarters land on consecutive numbers.
        CAST(SUBSTR(period, 1, 4) AS INTEGER) * 4 + CAST(SUBSTR(period, 6, 1) AS INTEGER),
        

        ?, ?    -- filled by curated.py with run_id and built_at
FROM (
    -- UNION stacks two lists on top of each other AND drops the duplicates. 
    -- Both tables hold all eight quarters, so this gives eight rows, not sixteen.
    -- UNION ALL would keep all sixteen rows : a different word for a different job.
    SELECT period FROM row_budget
    UNION
    SELECT period FROM row_actual
)
ORDER BY period; 
