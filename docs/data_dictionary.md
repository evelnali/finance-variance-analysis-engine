# Data dictionary

What every table and column in the curated layer means, what type it holds, and
where it came from. The curated layer is the part of the database built for
asking questions. If you are writing a query, these four tables are the ones to use.

On top of them sit three saved queries that put budget next to actual and work
out the variance. They are described under "The saved queries" further down.

## How the four tables fit together

```
                     dim_period
                     one row per quarter
                          |
    dim_asset ------- fact_expense ------- dim_cost_type
    one row per       one row per          one row per
    asset             asset, cost type,    kind of cost
                      quarter and scenario
```

`fact_expense` holds the amounts. The three `dim_` tables describe what those
amounts relate to: which asset, which kind of cost, which quarter. `dim` is
short for dimension. A description is stored once, in its own table, and looked
up with a `JOIN`.

## Conventions

| Convention | Meaning |
|---|---|
| Currency | Canadian dollars throughout. |
| Empty values | An empty value (NULL) means "does not apply". A machine has no seats. It never means zero or unknown. |
| Text values | Spelled exactly as they appear in the source files, including capitals: `CNC-01`, `PM`, `tangible`. |
| `run_id` | Which run of the pipeline built the row, as a time stamp: `20261116T161359`. |
| `built_at` | When the row was built: `2026-11-16 16:13:59`. |
| `varn` | Short for variance, the way finance writes it. Always actual minus budget: a positive figure is over budget, a negative figure is under. |
| Rebuilt every run | All four tables are emptied and rebuilt from the raw tables each time `src/curate.py` runs. Nothing is edited in place. |

---

## fact_expense

Maintenance and support expense. **One row per asset, cost type, quarter and
scenario.** 512 rows: 16 assets x 2 cost types x 8 quarters x 2 scenarios.

Key: `period` + `asset_id` + `cost_type` + `scenario`. The database refuses a
second row with the same four values.

| Column | Type | May be empty | Meaning | Example | Comes from |
|---|---|---|---|---|---|
| `period` | text | no | The quarter. Must exist in `dim_period`. | `2026Q3` | `period` in the extract |
| `asset_id` | text | no | The asset the expense belongs to. Must exist in `dim_asset`. | `CNC-01` | `asset_id` in the extract |
| `cost_type` | text | no | The kind of cost. Must exist in `dim_cost_type`. | `CM` | `cost_type` in the extract |
| `scenario` | text | no | `budget` or `actual`. | `actual` | Which extract the row came from: `budget.csv` or `actual.csv` |
| `quantity` | number | no | How many units of work. The unit depends on the cost type and is in `dim_cost_type.uom`. | `4.0` | `quantity` in the extract, converted from text |
| `amount` | number | no | The expense in dollars. | `64905.31` | `amount` in the extract, converted from text |
| `run_id` | text | no | The run that built the row. | `20261116T161359` | `src/curate.py` |
| `built_at` | text | no | When the row was built. | `2026-11-16 16:13:59` | `src/curate.py` |

Things to know when reading it:

- **Budget and actual are separate rows, not separate columns.** To compare
  them, filter or group by `scenario`.
- **A budget quantity can be a fraction.** The budget for breakdowns is an
  expected count, for example 2.12 work orders. An actual quantity is always a
  whole number.
- **A quantity of 0 with an amount of 0 is valid.** It means nothing happened
  for that asset and cost type in that quarter. 22 rows are like this.
- **No amount is negative.** Control C5 checks this before the data reaches
  this table.
- **Capitalized amounts are not here.** This table holds expense only. What
  was capitalized for an asset is in `dim_asset.capitalized_cost`.

## dim_asset

The asset register. **One row per asset.** 16 rows: 12 machines and 4 software products.

Key: `asset_id`.

| Column | Type | May be empty | Meaning | Example | Comes from |
|---|---|---|---|---|---|
| `asset_id` | text | no | The asset's identifier. | `CNC-01` | `config/asset_register.csv` |
| `family` | text | no | `tangible` (machinery) or `intangible` (software). | `tangible` | asset register |
| `asset_class` | text | no | The type of asset. See the list below. | `CNC_MACHINING_CENTRE` | asset register |
| `acquired_year` | whole number | no | The year the asset was acquired. | `2010` | asset register, converted from text |
| `replacement_cycle_years` | whole number | **yes** | Planned life in years. Empty for software. | `12` | asset register, converted from text |
| `capitalized_cost` | number | no | The amount capitalized for the asset, in dollars. For reference; it is not part of `fact_expense`. | `350000.0` | asset register, converted from text |
| `seats` | whole number | **yes** | Number of licensed seats. Empty for machines. | `6` | asset register, converted from text |
| `runs_on` | text | **yes** | For software that controls machines: the machines it runs, separated by semicolons. Empty otherwise. | `CNC-01;CNC-02;CNC-03` | asset register |
| `notes` | text | **yes** | Free-text remark. | `2010 modernization; never replaced` | asset register |
| `run_id` | text | no | The run that built the row. | | `src/curate.py` |
| `built_at` | text | no | When the row was built. | | `src/curate.py` |

Asset classes:

| Family | Asset class | Assets |
|---|---|---|
| tangible | `CNC_MACHINING_CENTRE` | 3 |
| tangible | `DOUBLE_HEAD_CUTTING_SAW` | 4 |
| tangible | `COPY_ROUTER` | 3 |
| tangible | `END_MILLING_MACHINE` | 2 |
| intangible | `CAD_CAM_SUITE` | 1 |
| intangible | `CNC_CONTROL` | 1 |
| intangible | `ROUTER_CONTROL` | 1 |
| intangible | `ERP_OPTIMIZATION` | 1 |

There is no age column. Age changes every year, so it is worked out from
`acquired_year` when it is needed.

## dim_cost_type

The kinds of cost. **One row per cost type.** 4 rows.

Key: `cost_type`.

| Column | Type | May be empty | Meaning | Example | Comes from |
|---|---|---|---|---|---|
| `cost_type` | text | no | The kind of cost. | `PM` | `config/settings.yml` |
| `family` | text | no | The family of asset this cost type applies to. | `tangible` | `config/settings.yml` |
| `uom` | text | no | Unit of measure: what `fact_expense.quantity` counts for this cost type. | `WORK_ORDER` | `uom` in the extracts |
| `run_id` | text | no | The run that built the row. | | `src/curate.py` |
| `built_at` | text | no | When the row was built. | | `src/curate.py` |

The four cost types:

| Cost type | Family | Counted in | What it is |
|---|---|---|---|
| `PM` | tangible | `WORK_ORDER` | Preventive maintenance: scheduled servicing. |
| `CM` | tangible | `WORK_ORDER` | Corrective maintenance: repairs after a breakdown. |
| `LICENSE` | intangible | `SEAT` | Software licence and update fees. |
| `SUPPORT` | intangible | `INCIDENT` | Software support incidents. |

Each cost type has exactly one unit. The build stops if the extracts ever show
a cost type with two.

## dim_period

The quarters. **One row per quarter that appears in the extracts.** 8 rows,
2025Q1 to 2026Q4.

Key: `period`.

| Column | Type | May be empty | Meaning | Example | Comes from |
|---|---|---|---|---|---|
| `period` | text | no | The quarter, in the form the extracts use. | `2026Q3` | `period` in the extracts |
| `year` | whole number | no | The year. | `2026` | Worked out from `period` |
| `quarter` | whole number | no | The quarter, 1 to 4. | `3` | Worked out from `period` |
| `period_seq` | whole number | no | A running number for the quarter: `year x 4 + quarter`. Consecutive quarters are exactly 1 apart, including across a year end. Use it to find "the quarter before". | `8107` | Worked out from `period` |
| `run_id` | text | no | The run that built the row. | | `src/curate.py` |
| `built_at` | text | no | When the row was built. | | `src/curate.py` |

`period_seq` has no meaning on its own. Only the difference between two values matters:
2025Q4 is 8104 and 2026Q1 is 8105.

---

## Example: budget against actual, by family, for one quarter

```sql
SELECT a.family,
       f.scenario,
       ROUND(SUM(f.amount), 2) AS total
FROM fact_expense AS f
JOIN dim_asset AS a ON a.asset_id = f.asset_id      -- look up each asset's family
WHERE f.period = '2026Q3'
GROUP BY a.family, f.scenario;
```

| family | scenario | total |
|---|---|---|
| intangible | actual | 13,488.46 |
| intangible | budget | 12,130.92 |
| tangible | actual | 405,930.04 |
| tangible | budget | 284,100.00 |

## How the curated layer is built and checked

| Step | What happens | Where |
|---|---|---|
| Build | The four tables are emptied and refilled from the raw tables, as one unit. If anything fails, the database is left as it was before the run. | `src/curate.py`, `sql/20` to `sql/23` |
| Table rules | A duplicate key, an unknown asset, cost type or quarter, or an empty required value stops the build. | `sql/04_schema_curated.sql` |
| R2 | Row counts and dollar totals in `fact_expense` are compared with the raw tables, by quarter and scenario. The result is written to `control_results`. | `sql/24_control_r2.sql` |
| Tests | Eighteen tests run the build and R2 against a small database with known totals. | `tests/test_curate.py` |

Check totals for the data in this repository:

| Scenario | Rows | Total |
|---|---|---|
| budget | 256 | 2,314,551.36 |
| actual | 256 | 2,760,090.95 |

---

## The saved queries

A saved query is a `SELECT` stored in the database under a name. SQL calls it a
view. It holds no rows of its own. Each time it is read it is worked out again
from `fact_expense`, so it cannot fall out of date. Read it the way you read a
table: `SELECT * FROM query_varn_by_class`.

```
    fact_expense and the three dim_ tables
                  |
        query_varn_by_asset          budget next to actual            256 lines
                  |
        query_varn_price_volume      variance split into              256 lines
                  |                  volume and price
                  |
        query_varn_by_class          added up by asset class,         128 lines
                  ^                  material lines flagged
                  |
           ref_materiality           the thresholds
```

Each query is built on the one above it.

### query_varn_by_asset

Budget and actual side by side. **One line per asset, cost type and quarter.**
256 lines: 16 assets x 2 cost types x 8 quarters.

| Column | Meaning | Example |
|---|---|---|
| `period` | The quarter. | `2026Q3` |
| `period_seq` | The running number for the quarter, from `dim_period`. Use it to sort. | `8107` |
| `family` | `tangible` or `intangible`, from `dim_asset`. | `tangible` |
| `asset_class` | The type of asset, from `dim_asset`. | `COPY_ROUTER` |
| `asset_id` | The asset. | `ROUTER-02` |
| `cost_type` | The kind of cost. | `CM` |
| `uom` | What the two quantities count, from `dim_cost_type`. | `WORK_ORDER` |
| `budget_qty` | Budgeted units of work. | `1.28` |
| `actual_qty` | Actual units of work. | `3.0` |
| `budget_amount` | Budgeted expense in dollars. | `11520.00` |
| `actual_amount` | Actual expense in dollars. | `32454.90` |
| `varn` | The variance: `actual_amount - budget_amount`. | `20934.90` |
| `varn_pct` | The variance as a percent of `budget_amount`. Empty when the budget amount is 0. | `181.73` |

### query_varn_price_volume

Each variance split into two parts. **The same 256 lines** as
`query_varn_by_asset`, with the same columns except `varn_pct`, and five more:

| Column | Meaning | Example |
|---|---|---|
| `budget_price` | Budgeted cost per unit: `budget_amount / budget_qty`. Empty when the budget quantity is 0. | `9000.00` |
| `actual_price` | Actual cost per unit: `actual_amount / actual_qty`. Empty when nothing was done. | `10818.30` |
| `flexed_budget` | What the budget would have been for the work actually done: `actual_qty x budget_price`. | `27000.00` |
| `volume_effect` | `flexed_budget - budget_amount`. More or less work than planned. | `15480.00` |
| `price_effect` | `actual_amount - flexed_budget`. Each unit cost more or less than planned. | `5454.90` |

The example line worked through, corrective maintenance on ROUTER-02 in 2026Q3:

```
budget          1.28 work orders x  9,000.00  =  11,520.00
flexed budget   3.00 work orders x  9,000.00  =  27,000.00
actual          3.00 work orders              =  32,454.90

volume effect   27,000.00 - 11,520.00  =  15,480.00    more breakdowns than planned
price effect    32,454.90 - 27,000.00  =   5,454.90    each repair cost more than planned
variance        32,454.90 - 11,520.00  =  20,934.90    the two added together
```

Things to know when reading it:

- **Volume and price always add up to the variance.** Control R3 checks this on
  every line.
- **A line where nothing was done is all volume.** The actual quantity is 0, so
  there is no actual price. 22 lines are like this.
- **Work that was not budgeted is counted as volume.** With no budget quantity
  there is no budget price to work with, so the whole variance is put in
  `volume_effect`. No line in this data is like this.
- **There is no mix effect.** Volume and price are the two parts this project
  works out.

### query_varn_by_class

The asset lines added up, with the material ones flagged. **One line per asset
class, cost type and quarter.** 128 lines: 8 asset classes x 2 cost types x 8 quarters.

This is the level the materiality thresholds are tested at.

| Column | Meaning | Example |
|---|---|---|
| `period`, `period_seq`, `family`, `asset_class`, `cost_type`, `uom` | As in `query_varn_by_asset`. | `2026Q3`, `COPY_ROUTER`, `CM` |
| `assets` | How many assets were added together to make the line. | `3` |
| `budget_qty`, `actual_qty` | The quantities of those assets added together. | `3.12`, `11.0` |
| `budget_amount`, `actual_amount` | The amounts of those assets added together. | `28080.00`, `109960.08` |
| `varn` | The variance for the class: actual minus budget. | `81880.08` |
| `varn_pct` | The variance as a percent of the class budget. Worked out again from the class totals, not added up or averaged from the asset lines. | `291.60` |
| `volume_effect`, `price_effect` | The two parts from `query_varn_price_volume`, added together. | `70920.00`, `10960.08` |
| `absolute_threshold` | The dollar limit for the line's family, from `ref_materiality`. | `25000.0` |
| `percent_threshold` | The percent limit for the line's family, from `ref_materiality`. | `5.0` |
| `is_material` | `1` when the line is material, `0` when it is not. | `1` |

A line is material when it breaches **both** limits:

```
the variance, ignoring its sign, is more than absolute_threshold
AND
the percent, ignoring its sign, is more than percent_threshold
```

Things to know when reading it:

- **Under budget counts the same as over budget.** A large underspend is flagged too.
- **`is_material` is a number**, so `SUM(is_material)` counts the flagged lines.
- **A family with no threshold drops out of this query.** Control R3 then fails,
  because the totals no longer agree with `fact_expense`.

## ref_materiality

The materiality thresholds. **One row per family.** 2 rows. The table is emptied
and refilled from `config/settings.yml` each time `src/load.py` runs. Its layout
is in `sql/03_schema_reference.sql`.

Key: `family`.

| Column | Type | May be empty | Meaning | Example |
|---|---|---|---|---|
| `family` | text | no | `tangible` or `intangible`. | `tangible` |
| `absolute_threshold` | number | no | The dollar limit. | `25000.0` |
| `percent_threshold` | number | no | The percent limit, written as a percent: 5.0 means 5%. | `5.0` |
| `run_id` | text | no | The run that loaded the row. | |
| `loaded_at` | text | no | When the row was loaded. | |

| Family | Dollar limit | Percent limit |
|---|---|---|
| tangible | 25,000 | 5% |
| intangible | 3,000 | 5% |

The two families have different dollar limits because they are different sizes.
The budget is about 277,000 a quarter for machinery and about 12,000 for software.

**A threshold belongs to the level it is tested at.** These limits are set for
one asset class, one cost type, one quarter. The same figures would be too high
for a single asset and too low for the whole plant.

## What the flags show in this data

13 of the 128 lines are material:

```sql
SELECT period, asset_class, cost_type,
       ROUND(varn, 2)     AS varn,
       ROUND(varn_pct, 1) AS varn_pct
FROM query_varn_by_class
WHERE is_material = 1                 -- only the flagged lines
ORDER BY period_seq, asset_class;
```

| period | asset_class | cost_type | varn | varn_pct |
|---|---|---|---|---|
| 2025Q1 | CNC_MACHINING_CENTRE | CM | 44,025.36 | 43.7 |
| 2025Q1 | DOUBLE_HEAD_CUTTING_SAW | CM | 26,339.34 | 36.7 |
| 2025Q2 | CNC_MACHINING_CENTRE | CM | -34,054.04 | -33.8 |
| 2025Q2 | COPY_ROUTER | CM | -25,920.00 | -100.0 |
| 2025Q2 | DOUBLE_HEAD_CUTTING_SAW | CM | 48,850.50 | 68.2 |
| 2025Q4 | DOUBLE_HEAD_CUTTING_SAW | CM | 54,881.33 | 76.6 |
| 2026Q1 | DOUBLE_HEAD_CUTTING_SAW | CM | 83,720.37 | 109.1 |
| 2026Q2 | COPY_ROUTER | CM | 72,474.61 | 258.1 |
| 2026Q3 | CNC_MACHINING_CENTRE | CM | 38,313.44 | 35.8 |
| 2026Q3 | COPY_ROUTER | CM | 81,880.08 | 291.6 |
| 2026Q4 | CNC_MACHINING_CENTRE | CM | 31,051.83 | 29.0 |
| 2026Q4 | COPY_ROUTER | CM | 58,829.76 | 209.5 |
| 2026Q4 | DOUBLE_HEAD_CUTTING_SAW | CM | 35,473.61 | 46.2 |

Three things the flags do not show. Each follows from the level the thresholds
are tested at. They are recorded here as observations about the method, not as
faults to fix.

- **Every flagged line is corrective maintenance, on three of the four machine
  classes.** The end milling machines are never flagged. Their corrective
  maintenance budget is 12,000 a quarter, so a line would have to run more than
  twice its budget over before it passed the 25,000 limit.
- **No software line is flagged.** The largest software variance is 2,870.91,
  support for the CAD/CAM suite in 2025Q2. That is 179% over its budget and
  still under the 3,000 limit.
- **The servicing skipped in 2025Q4 is not flagged.** Preventive maintenance
  that quarter is about half of budget in every machine class, 30,623.72 under
  in total. The largest single class is 11,316.81 under, so no line reaches
  25,000. The variance is in the query; it is only the flag that is missing.

## How the saved queries are created and checked

| Step | What happens | Where |
|---|---|---|
| Create | The three queries are removed and created again, in order, each time `src/analyze.py` runs. | `src/analyze.py`, `sql/30` to `sql/32` |
| R3 | Nine checks compare the saved queries with `fact_expense`: the budget and actual totals, the number of lines, volume plus price against the variance on every line, and every asset line counted once at class level. The result is written to `control_results`. | `sql/33_control_r3.sql` |
| Tests | Eighteen tests run the queries and R3 against a small database where every figure can be worked out by hand. | `tests/test_analyze.py`, `tests/tiny_db.py` |

Check figures for the data in this repository, all eight quarters:

| Figure | Amount |
|---|---|
| Budget | 2,314,551.36 |
| Actual | 2,760,090.95 |
| Variance | 445,539.59 |
| of which volume | 390,169.84 |
| of which price | 55,369.75 |
| Material lines | 13 of 128 |

## Known limits

- **Text where a number should be becomes 0.** A blank quantity or amount in
  an extract stops the build. A word such as `n/a` does not: it is converted
  to 0 with no error. There is no check for this yet.
- **`runs_on` holds a list in one column.** To query which software runs on
  which machine, the value has to be split on the semicolons.
- **A line with no budget cannot be flagged.** With a budget of 0 the percent
  cannot be worked out, so `is_material` is 0 whatever the dollar amount. No
  line in this data has a budget of 0.
- **Materiality is tested at one level only:** asset class, cost type and
  quarter. A variance that is large for one asset, or for one cost type across
  the whole plant, is not flagged unless it is also large at that level.

## The other tables

These are not part of the curated layer. Their layouts are in the `sql/` schema files.

| Table | What it holds | Layout in |
|---|---|---|
| `raw_budget`, `raw_actual` | The two extracts exactly as they arrived, every value stored as text. Evidence, not for analysis. | `sql/01_schema_raw.sql` |
| `control_results` | One line per control per run: what was tested, PASS or FAIL, and the figures. | `sql/02_schema_control.sql` |
| `exceptions` | One line for each item a control objected to. | `sql/02_schema_control.sql` |
| `ref_materiality` | The materiality thresholds. Described above. | `sql/03_schema_reference.sql` |
| `ref_assets`, `ref_cost_types` | Copies of the asset register and the cost type rule, as text. The source for `dim_asset` and `dim_cost_type`. | `sql/03_schema_reference.sql` |
