# Progress log

One line per session: what was done, and the single next thing to do.

## 2026-09-08
- Done: M1 chunk 1-4. Toolchain installed, repo published to GitHub,
venv + pinned dependencies, first Python script running (scratch.py).
- Next: chunk 5. Write config.py to read settings.yml.

## 2026-09-09
- Done: M1 complete. config.py loads validates settings.yml, logger.py writes timestamped run log
to console and file, run.py is the entry point with --period. 
Caught a %-format bug turning 5% into 500%
- Next M2 - assumptions.yml and the driver model. 

## 2026-09-10
- Done: M2 chunks 1-2. assumptions.yml written as an assumptions register
(units and meaning on every value, worked example per family, 
CM(corrective maintenance) at 5x PM(preventative maintenance), downtime excluded). 
asset_register.csv: 16 assets. model.py computes expected
cost for both families - 2026Q3 gives 284,100 across 12 machines and 12,131
across 4 software products. Rescaling the fleet showed a single materiality
threshold would hide the software family; switched to per-family thresholds.
Bugs found: a return indented inside a for loop (wrong number, no error),
= instead of +=, and an f-string that compiles on 3.13 but not on 3.10.
- Next: M2 chunk 3. generate_data.py, the seeded generator.

## 2026-09-11
- Done: M2 chunk 3a. generate_data.py writes data/raw/budget.csv - 256 rows,
the modelled expectation for all 8 periods. Grain is asset x period x cost
type, with quantity + uom so work orders, seats and incidents stay separable
for price/volume/mix later. Added a per-period total printed at generation
time as a standing self-check. Bug: order counts passed into the amount slot
- no error, just a budget where machines cost 2 dollars. Found by explaining
the 39.36 difference rather than eyeballing it.
- Next: M2 chunk 3b. The actuals extract - same shape, plus noise and the
planted anomalies.

## 2026-09-14
- Done: M2 chunk 3b-i. actual.csv now written alongside budget.csv - each
budget row turned into an outcome. Unplanned counts (CM, support) drawn from
Poisson; unit costs drawn around standard; licences left untouched because a
contract is a contract. producer.yml holds the seed and the noise settings and
is read only by generate_data.py - model.py never sees it, which is what keeps
the analysis a test rather than a mirror. Checks pass: 256 rows, licence total
44,496 unchanged, scheduled servicing count exactly 192.
- Finding: baseline noise is +2.2% overall but swings +/-22% quarter to quarter,
because 3 CNC machines carry 45% of spend at ~2 breakdowns each. Noise alone
breaches the 25k threshold in 4 quarters of 8. Not yet resolved - decide after
seeing whether the planted anomalies stand out against it.
- Bugs: YAML keys not indented under their parent (came back empty, not empty
box); price noise stranded inside one branch of an if, so PM rows never got an
amount; return inside the loop again; .of instead of .0f.
- Next: M2 chunk 3b-ii. The planted anomalies.


## 2026-09-15
- Done: M2 chunk 3b-ii. Five anomalies planted into actual.csv from producer.yml
- Total five effects - three volume effects, one price effect, one favourable. All config-driven:
adding a sixth is a YAML change, not a code change. model.py still knows nothing
about any of them. Verified at row level: PM count drops to 12 in 2025Q4 only,
routers draw 5 and 9 corrective jobs against a budget of 3.1, SAW-02 draws 3
against 1.4.
- Bugs, all the same kind: a mistyped key in .get() returns empty and the program
carries on. "anomolies" in the YAML meant nothing was planted at all; "asseets"
and "csot_types" in the Python meant every rule applied to every asset and every
cost type, giving a 175% variance. Python cannot tell a key you don't have from
a key you meant to have.
- FINDING - this is the one that matters. Period totals cannot see the planted
problems, because they net opposing stories into one line. 2025Q4 shows +32,160
overall; split by cost type it is -30,624 on scheduled servicing and +62,440 on
breakdowns - two real and opposite stories hidden in one figure. The copy router
fault is worth ~17,000 a quarter against a 25,000 threshold, so no dollar-amount
test ever fires on it; but the routers run under budget through 2025 and over
budget in all four quarters of 2026, flipping at exactly the date the fault
starts. Counter-example: 2025Q1 has nothing planted and still ran 46,621 over on
breakdowns, which is larger than the real fault. So a rule of "flag anything over
40,000" would chase 2025Q1 and never look at the routers.
- Verified by a planting check built into the generator: it prints, per rule,
the budgeted work orders on the rows that rule targets, what the multiplier
should make of them, and what actually landed. A4a ties exactly (24 -> 12);
the drawn ones land near expectation; the price-only rule leaves volume alone.
- Consequence for M5: variance views must split by cost type and by asset class,
and must test direction repeating across consecutive quarters, not dollar amount
in any single quarter.
- Next: M2 chunk 4. ingest.py and control C1.


## 2026-09-15 (evening)
- Done: M2 chunk 4. ingest.py reads both extracts and runs control C1 -
schema conformance, in Python, before the load. First pipeline module to use
the logger instead of print(). Result is shaped like a control_results row so
M3 can store it unchanged; a failure exits non-zero, which is what CI reads.
Expected columns live in settings.yml, so a third extract is a config change.
Verified by breaking a column name on purpose and watching C1 catch it.
- config.py had been asking for materiality.absolute_threshold since the split
into per-family thresholds - caught at startup the first time ingest loaded
settings, with the key named. The M1 validation doing its job. Fixed, and it
now walks keys at any depth and reports all missing ones at once.
- Next: M2 chunk 5. load.py - land raw into SQLite idempotently with a run_id,
then R1.

## 2026-09-17
- Done: M2 chunk 5, and M2 is finished. load.py puts both extracts into
SQLite one quarter at a time. Table layouts live in sql/01_schema_raw.sql,
not in Python. Every column is stored as text on purpose - so a row in the
raw table can always be shown to match a line in the file, and a bad value
gets caught by a control instead of stopping the load.
- Re-running the same quarter shows "removed 32, added 32" and leaves the
database as one run did. Running a different quarter shows "removed 0",
proving the removal is scoped.
- R1 ties for both extracts: file against table, row count and amount total.
2026Q3 budget 296,230.92, actual 419,418.50, 32 rows each. First of the four
reconciliations, and the first time two independently produced figures had
to agree.
- Next: M3. Controls C2 to C5 in SQL, the rejects table they write into, and
the first proper tests.


## 2026-09-18 — M3 started, C2 done

- sql/02_schema_control.sql: control_results (the control log) and exceptions
  (the exception listing). One exceptions shape serves all of C2–C5.
- sql/10_control_c2.sql: duplicate key detection — GROUP BY the three key columns,
  HAVING COUNT(*) > 1.
- controls.py: runs C2 over both raw tables, writes the log and the exceptions,
  exits non-zero if anything failed.
- Decisions: any failed control stops the run, after finishing and writing what
  it found. Exceptions store the key plus a detail line, never a copy of the row.
- Proven both ways: PASS on clean data, FAIL on a planted duplicate (CNC-01 CM,
  4 rows sharing one key), exit code 1.
- Bugs: TO NULL instead of NOT NULL ×7 in the schema; missing comma in the
  exceptions column list — which only showed up the first time a control failed,
  because record_exception is dead code until then; %Y-%m%-%d in the timestamp.
- Next: C3 — completeness. Every expected asset and period present.


## 2026-09-22 — M3, C3 completeness

- ref_assets and ref_cost_types: reference data, rebuilt from config every run.
  Master data, not transactions — hence the ref_ prefix, not raw_.
- The tangible/intangible → cost type rule was implicit in the generator; now it
  is written down in settings.yml where a control can read it.
- 10_control_c3.sql: builds the 32 expected pairs from the two reference tables,
  LEFT JOINs to the extract, keeps the ones that found nothing.
- rows_tested for C3 is what SHOULD exist, not what does — otherwise a missing
  row shrinks its own population.
- Seen failing: SAW-03 PM deleted → C3 FAIL, C2 still PASS. Completeness needs an
  independent source; nothing inside the data can reveal a row that never arrived.
- Bugs: plurals (EXIST, VALUE, ref_cost_type), trailing comma before ), NO NULL again.
- Next: C4 mapping coverage, C5 reasonability, then the first tests.



## 2026-09-24 — M3, C4 mapping coverage

- 10_control_c4.sql: C3's query with the sides swapped. Keeps every DATA row and
  looks for ones the register never matched — an unknown asset, or a known asset
  carrying a cost type its family can't have.
- Learned: a condition about the RIGHT table goes in ON; about the LEFT table it
  goes in WHERE. In WHERE it would discard the unmatched rows, which are the only
  ones a LEFT JOIN exists to keep.
- rows_tested is what exists here, not what's expected — C4 tests the data.
- Seen failing: a planted MILL-03 row, caught by C4 while C2 and C3 stayed green.
- Pre-flight for query files: run the .sql against data/variance.db before the
  pipeline. Names the bad word in two seconds instead of a traceback.
- Next: C5 reasonability, then the first tests.



## 2026-09-25 — M3, C5 reasonability. All four controls built.

- 10_control_c5.sql: quantity and amount must AGREE about whether anything
  happened. Not "neither may be zero" — that version would flag SAW-04 CM in
  2026Q3, which legitimately has zero work orders and zero cost, and would halt
  a clean run every time under the stop-on-failure rule.
- Uses CASE WHEN to report WHY each row failed, so the exception listing reads
  on its own: "cost with no work behind it (quantity 0.0, amount 7000.0)".
- CAST(... AS REAL) throughout — the raw layer is text, and text compares
  character by character, so '10' would sort before '9'.
- Negatives are flagged outright. A real ERP would exempt credit notes by
  document type; nothing here produces one, so no untested exemption was added.
- Seen failing: CNC-01 PM quantity zeroed with its $7,000 left in place.
  C2, C3 and C4 all stayed green — the row is unique, present and refers to a
  real machine. It is simply impossible.
- Next: the first pytest tests, then R1 and C1 results into control_results.

## 2026-09-25 (later) — M3 complete. First tests.

- tests/test_anomaly_rules.py: five tests on rule_matches. The asset test is the
  one that would have caught the .get("asseets") bug the moment it was typed.
- tests/test_control_c5.py: seven tests, run against a six-row database built in
  memory and thrown away. Nothing touches data/variance.db.
- test_nothing_else_is_flagged pins the count at 3 — without it C5 could start
  flagging everything and the other tests would all still pass.
- Two of my own tests were wrong before the code was: ROUTER-1 missing a zero,
  and a missing "not". A red test means the code OR the test is wrong. A test
  that passes for the wrong reason is the expensive kind.
- ("2026Q3") with no comma is not a tuple — sqlite3 read the six characters as
  six values. Same trap as ("extracts",) in config.py.

M3 done: C2–C5 built, each seen failing, first tests green.
Next: M4 — the curated layer. Plus two tidies: R1 and C1 results into
control_results.


## 2026-09-30 — C1 and R1 into the control log. M4 begins.

- src/results.py: record_results and record_exception moved out of controls.py,
  because load.py needs them too. Two files needing the same thing is what
  earns that thing its own file — and importing controls.py from load.py
  would have been circular, each needing the other before either finished.
- control_results gained a detail column, so a check records the figures it
  tied when it passes, not only when it fails. DEFAULT '' so every call
  written before the column existed still works.
- C1 and R1 now write to control_results like C2–C5. C1's period is "ALL" —
  it reads the whole file, every quarter in it, not one quarter.
- Committed C1's line BEFORE the sys.exit on failure. A control log that
  only records passes proves nothing.
- All eight quarters loaded: 256 rows per raw table, R1 tied all 16
  file-to-table pairs.
- Found: idx_raw_actual_period was pointing at raw_budget. Harmless today,
  and the kind of copy-paste slip that gets inherited quietly.
- M4 file 1: sql/04_schema_curated.sql. dim_period, dim_asset, dim_cost_type,
  fact_expense.
- "fact_spend" renamed to "fact_expense" before anything was built. Expense is
  the accounting word and none of this is capitalized.
- PRIMARY KEY on fact_expense is C2 done as a preventive control — the door
  refuses the duplicate, instead of a test finding it afterwards. C2 still
  runs on raw, where there is no key and duplicates can land.
- Foreign keys are declared AND switched on with PRAGMA foreign_keys = ON.
  Declared but not switched on, they would be decoration — the NO NULL trap.
- Trap: the file parsed clean and printed OK while dim_cost_type was missing
  entirely. SQLite accepts a foreign key pointing at a table that does not
  exist; it only looks for it when a row is inserted. "No errors" is not
  "it built what I meant" — count the tables, don't trust the silence.

Next: M4 files 2–9. Build the four curated tables, then R2.



## 2026-10-23 to 2026-11-16 — M4: the curated layer builds and ties

- Four build files (sql/20–23) fill dim_period, dim_asset, dim_cost_type and
  fact_expense. sql/24_control_r2.sql lines raw up against curated.
- src/curate.py runs them on the real database: empties the four tables
  (expense table first, because of the foreign keys), rebuilds them, runs R2,
  and saves once at the end. If a table rule refuses a row or R2 does not tie,
  the build is undone and the database stays as it was.
- First real run: 8 quarters, 16 assets, 4 cost types, 512 expense rows.
  R2 PASS: budget 2,314,551.36 and actual 2,760,090.95 on both sides.
- NULLIF(column, '') on every column before CAST. CAST('' AS INTEGER) gives 0
  with no error, which would have recorded machines with 0 seats.
- INSERT and SELECT lists match by position, not by name. I had seats and
  capitalized_cost swapped; the build stopped only because of a NOT NULL rule.
- A preview is not a test of the file. sql/20 was committed on a clean preview
  with row_budget in it. From then on, every file was run on a copy first.
- aquired_year sat misspelled in the schema for three weeks. .tables shows
  table names, not columns. CREATE TABLE IF NOT EXISTS will not fix an
  existing table; it needs DROP TABLE first.
- First curate run failed on a wrong file name, after the four builds had run.
  Nothing was saved, because the commit had not been reached.
- Known gap: CAST('n/a' AS REAL) gives 0.0 silently. Needs its own test.

Next: tests/test_curate.py, then docs/data_dictionary.md, then M5.