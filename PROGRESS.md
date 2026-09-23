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