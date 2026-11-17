-- query_varn_price_volume: each variance split into a volume effect and a price effect.
--
-- Built on query_varn_by_asset, so it has the same 256 lines: one per asset,
-- cost type and quarter.
--
-- The split uses the flexed budget: what the budget would have been for the
-- quantity that actually happened, at the budgeted price.
--
--     budget price   = budget amount / budget quantity
--     flexed budget  = actual quantity x budget price
--
--     volume effect  = flexed budget - budget     (more or less work than planned)
--     price effect   = actual - flexed budget     (each unit cost more or less than planned)
--
-- The two always add up to the variance:
--     (flexed - budget) + (actual - flexed) = actual - budget
--
-- If a line has no budget quantity there is no budget price to flex with.
-- COALESCE(x, y) means "x, unless x is empty, then y". Here it sets the flexed
-- budget to the actual amount, so the whole variance is counted as volume:
-- work that was not budgeted at all.

DROP VIEW IF EXISTS query_varn_price_volume;

CREATE VIEW query_varn_price_volume AS
SELECT period, period_seq, family, asset_class, asset_id, cost_type, uom,
       budget_qty, actual_qty,
       budget_amount, actual_amount, varn,
       budget_price,
       actual_amount / NULLIF(actual_qty, 0)   AS actual_price,     -- empty when nothing happened
       flexed_budget,
       flexed_budget - budget_amount           AS volume_effect,
       actual_amount - flexed_budget           AS price_effect
FROM (
    -- Work out the budget price and the flexed budget first, once per line,
    -- so the two effects above can both use them.
    SELECT *,
           budget_amount / NULLIF(budget_qty, 0)                        AS budget_price,
           COALESCE(actual_qty * budget_amount / NULLIF(budget_qty, 0),
                    actual_amount)                                      AS flexed_budget
    FROM query_varn_by_asset
);