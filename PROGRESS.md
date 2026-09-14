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