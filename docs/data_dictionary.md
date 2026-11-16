# Data dictionary

What every table and column in the curated layer means, what type it holds, and
where it came from. The curated layer is the part of the database built for
asking questions. If you are writing a query, these four tables are the ones to use.

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

## Known limits

- **Text where a number should be becomes 0.** A blank quantity or amount in
  an extract stops the build. A word such as `n/a` does not: it is converted
  to 0 with no error. There is no check for this yet.
- **`runs_on` holds a list in one column.** To query which software runs on
  which machine, the value has to be split on the semicolons.

## The other tables

These are not part of the curated layer. Their layouts are in the `sql/` schema files.

| Table | What it holds | Layout in |
|---|---|---|
| `raw_budget`, `raw_actual` | The two extracts exactly as they arrived, every value stored as text. Evidence, not for analysis. | `sql/01_schema_raw.sql` |
| `control_results` | One line per control per run: what was tested, PASS or FAIL, and the figures. | `sql/02_schema_control.sql` |
| `exceptions` | One line for each item a control objected to. | `sql/02_schema_control.sql` |
| `ref_assets`, `ref_cost_types` | Copies of the asset register and the cost type rule, as text. The source for `dim_asset` and `dim_cost_type`. | `sql/03_schema_reference.sql` |
