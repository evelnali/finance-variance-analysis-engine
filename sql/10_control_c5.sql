-- C5: data resonability test
-- quantity and amount must agree about whether anthing happened. 
-- Quantity & Amount$
-- 0 & 0      fine - no work, no cost. possible. 
-- 0 & >0     flag - no work completed, while has a cost behind it
-- >0 & 0     flag - has work order, but no expense charged, need investigate
-- <0 or <0    flog -- either quantity or amount is negavitive, is impossible. 
--
-- Note: in a real ERP a credit note or reversal is legitimately negative, and would be exempted by 
-- ducoment type. Nothing here ever produces one, so the rule statys strickt rather than carring 
-- an examptiion nothing would test. 
--
-- CAST(... AS REAL) because the raw data layer stores everything as text, and text compares 
-- character by character: '10' would sort before '9'. 

SELECT asset_id,
       cost_type,
       quantity,
       amount,
       CASE 
           WHEN CAST(quantity AS REAL) < 0 THEN 'negative quantity'
           WHEN CAST(amount AS REAL) <0 THEN 'negative amount'
           WHEN CAST(quantity AS REAL) = 0 THEN 'cost with no work behind it'
           ELSE 'work recorded with no cost'
        END AS reason
FROM {table}
WHERE period = ?
    AND (CAST(quantity AS REAL) <0
         OR CAST(amount AS REAL) <0
         OR (CAST(quantity AS REAL) =0 AND CAST(amount AS REAL) <> 0)
         OR (CAST(quantity AS REAL)<>0 AND CAST(amount AS REAL) = 0)
    )
ORDER BY asset_id, cost_type;