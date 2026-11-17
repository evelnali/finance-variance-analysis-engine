-- query_varn_by_class: variance by asset class, cost type and quarter, with the materiality flag.
--
-- This is the level the analysis is reported at. The three copy routers are
-- added together, the four saws are added together, and so on.
-- 8 classes x 2 cost types x 8 quarters = 128 lines.
--
-- A threshold belongs to a level. The same dollar limit gives different answers
-- applied machine by machine than applied class by class, so the limits in
-- ref_materiality are applied here and only here.
--
-- A line is material when it breaches BOTH tests for its family:
--     the variance is bigger than the dollar threshold, in either direction, AND
--     the variance is bigger than the percent threshold, in either direction.
-- ABS() drops the sign, so a large underspend is flagged as well as a large overspend.
--
-- Every line is matched to its family's thresholds with a JOIN. A family with
-- no threshold would drop out of this query; R3 would then fail, because this
-- query's total would no longer equal the expense table's.

DROP VIEW IF EXISTS query_varn_by_class;

CREATE VIEW query_varn_by_class AS
SELECT t.period, t.period_seq, t.family, t.asset_class, t.cost_type, t.uom,
       t.assets,
       t.budget_qty, t.actual_qty,
       t.budget_amount, t.actual_amount,
       t.varn,
       100.0 * t.varn / NULLIF(t.budget_amount, 0)        AS varn_pct,
       t.volume_effect,
       t.price_effect,
       m.absolute_threshold,
       m.percent_threshold,
       -- 1 when material, 0 when not. A number, so SUM(is_material) counts the flags.
       CASE WHEN ABS(t.varn) > m.absolute_threshold
             AND ABS(100.0 * t.varn / NULLIF(t.budget_amount, 0)) > m.percent_threshold
            THEN 1 ELSE 0 END                             AS is_material
FROM (
    -- Add the asset lines up to one line per class, cost type and quarter.
    SELECT period, period_seq, family, asset_class, cost_type, uom,
           COUNT(*)            AS assets,            -- how many assets are in the line
           SUM(budget_qty)     AS budget_qty,
           SUM(actual_qty)     AS actual_qty,
           SUM(budget_amount)  AS budget_amount,
           SUM(actual_amount)  AS actual_amount,
           SUM(varn)           AS varn,
           SUM(volume_effect)  AS volume_effect,
           SUM(price_effect)   AS price_effect
    FROM query_varn_price_volume
    GROUP BY period, period_seq, family, asset_class, cost_type, uom
) AS t
JOIN ref_materiality AS m ON m.family = t.family;       -- the thresholds for this line's family