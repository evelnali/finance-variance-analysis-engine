"""Build the curated layer from the raw tables, then prove it holds the same money. """
"""currated = final report out put.  what the readers actually see. """

"""The four build files in sql/ each file one curated table. This module runs them in order on the 
real database, runs R2 to tie the results back to the raw tables, and writes R2's result into the control log.

The whole build is one unit. NOthing is saved until the single commit at the end, so the
database either holds a complete build that tied, or stays exactly as it was before the run.
or none do. 
"""


import sqlite3
import sys

from src.config import PROJECT_ROOT, load_settings
from src.logger import new_run_id, setup_logger
from src.load import connect
from src.results import record_results, record_exception, now_stamp

SQL_DIR = PROJECT_ROOT / "sql"

# Each curated table and the file that fills it, in the order they are Built: 
# the three description tables first, the expense table last, because an expense 
# row must point at a quarter, an asset and a cost type that already exist.
BUILD_FILES = [
    ("dim_period",      "20_build_dim_period.sql"),
    ("dim_asset",       "21_build_dim_asset.sql"),
    ("dim_cost_type",   "22_build_dim_cost_type.sql"),
    ("fact_expense",    "23_build_fact_expense.sql"),
]

R2_SQL = SQL_DIR / "24_control_r2.sql"
R2_NAME = "Raw to curated reconciliation"
TOLERANCE = 0.01  # how much difference between raw and curated is acceptable, in dollars. 0.01 = one cent.

def switch_on_foreign_keys(conn):
    """sqlite does not enforce foreign keys by default. This turns them on."""
    conn.execute("PRAGMA foreign_keys = ON;")

    # Ask the setting back instead of assuming it took. 1 means on, 0 means off.
    if conn.execute("PRAGMA foreign_keys;").fetchone()[0] != 1:
        raise RuntimeError("Foreign keys did not turn on. The database is not enforcing referential integrity.")



def build_curated(conn,run_id, log):
      """Empty the four curated tables, then fill them from the raw tables.
      Nothing here is saved. the caller decides whether to commit or undo.
      """

      built_at = now_stamp()       # one time stamp for the whole build, so all four tables have the same built_at value.

      # Empty the OPPOSITE order to building: the expense table first, because it points at the other three tables. If we emptied the other three first, the expense rows would point at nothing and violate foreign key constraints.
      # While expense rows still point at an asset, the database will not let that asset to be removed. 
      for table, filename in reversed(BUILD_FILES):
          removed = conn.execute(f"DELETE FROM {table}").rowcount
          log.info(f"{table}: emptied, {removed} rows removed")

      for table, filename in BUILD_FILES:
          sql = (SQL_DIR / filename).read_text()
          # (run_id, built_at) fills the two ? blanks at the end of every build file.
          added = conn.execute(sql, (run_id, built_at)).rowcount
          log.info (f"{table}: built, {added} rows added by {filename}")


def reconcile_r2(conn, log): 
    """R2: the curated expense table holds the same rows and dollars as the raw tables. 
    
    The query lines the two sides up, one line per quarter and scenario.
    This function compares each line and hands back what it concluded."""
    lines = conn.execute(R2_SQL.read_text()).fetchall()

    differ = []      # one (period, what was wrong) pair per line that does not tie. 
    for period, scenorio, raw_rows, raw_total, curated_rows, curated_total in lines:
        if raw_rows != curated_rows or abs(raw_total - curated_total) >= TOLERANCE:
            differ.append((period, 
                           f"{scenorio}: raw {raw_rows} rows / {raw_total:,.2f}"
                           f" vs curated {curated_rows} rows / {curated_total:,.2f}"))

    # a PASS  over nothing is not a pass. It means the query found no rows, which is not what we expect.
    if not lines: 
        differ.append(("ALL", "nothing to compare - the raw tables are empty."))


    # Grand totals for the contol log. line[2] is raw_rows, line[3] is raw_total
    # line[4] is curated_rows, line[5] is curated_total -- the positions in the SELECT. 
    raw_rows_all = sum(line[2] for line in lines)
    raw_total_all = sum(line[3] for line in lines)
    curated_rows_all = sum(line[4] for line in lines)
    curated_total_all = sum(line[5] for line in lines)

    result = {
        "control_id": "R2",
        "status": "FAIL" if differ else "PASS", 
        "row_tested": raw_rows_all,      # what should have arrived.
        "differ": differ,
        "detail": (f"{len(lines)} lines compared, {len(differ)} differ - "
                   f"raw {raw_rows_all} rows / {raw_total_all:,.2f} "
                   f"vs curated {curated_rows_all} rows / {curated_total_all:,.2f}"),
    }

    if result["status"] == "PASS":
        log.info(f"R2 fact_expense: PASS -- {result['detail']}")
    else:
        log.error(f"R2 fact_expense: FAIL -- {result['detail']}")
        for period, what in differ:
            log.error(f"R2 fact_expense: FAIL -- {period} {what}")

    return result



def record_r2(conn, run_id, result):
    """Write the R2's line into the control log, and one exception per line that differed.
    """
    for period, what in result["differ"]:
        # None, None:  the objection is about a whole quarter, not one asset or cost type. 
        record_exception (conn, run_id, "R2", "fact_expense", period, None, None, what)

    # period is "ALL": the curated layer is rebuilt whole, every quarter at once.
    record_results(conn,run_id, "R2", R2_NAME, "fact_expense", "ALL",
                   result["status"], result["row_tested"],len(result["differ"]), result["detail"])



def curate(conn, run_id, log):
    """Build, reconcile and save, as one unit. Hands back "PASS", "FAIL" or "STOPPED".

    The connection comes in as an input rather than being opened here, so a test
    can hand this function a small throwaway database instead of the real one.
    """
    switch_on_foreign_keys(conn)

    # ------ build. A row the table rules refuse stops it here. --------
    try:
        build_curated(conn, run_id, log)
    except sqlite3.IntegrityError as problem:
        conn.rollback()              # undo everything since the run started.
        log.error(f"Build stopped: {problem}")
        log.error("Nothing was saved. The curated tables are as they were before this run.")
        return "STOPPED"

    # ------ reconcile. R2 reads the new build before it is saved. --------
    result = reconcile_r2(conn, log)

    if result["status"] == "FAIL":
        conn.rollback()              # a build that does not tie is not saved.

    # The R2 line is written either way. On a PASS this one commit saves the build
    # and the line together. On a FAIL the build is already undone, so it saves
    # only the record of the failure.
    record_r2(conn, run_id, result)
    conn.commit()

    return result["status"]


def main():
    """Rebuild the curated layer in the real database and tie it back to raw."""
    run_id = new_run_id()
    log = setup_logger(run_id)
    settings = load_settings()

    log.info("Curated build started.")
    conn = connect(settings)
    outcome = curate(conn, run_id, log)
    conn.close()

    if outcome == "FAIL":
        log.error("Curate failed. The build was undone; the failure is in the control log.")
    if outcome != "PASS":
        sys.exit(1)              # STOPPED has already logged its reason

    log.info("Curate finished. The curated layer tied to raw.")


if __name__ == "__main__":
    main()