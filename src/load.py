"""Put the two files into the database, exactly as they arrived. 

Running this twice for the same quarter leaves the database in the same state as running it once:
the quarter's rows are removed and put back, and no other quarter is touched. That is what lets 
you reload one quarter at a time without disturbing the ones already closed.
"""

import argparse
import sqlite3
import sys
from datetime import datetime
import csv

from src.config import PROJECT_ROOT, load_settings
from src.logger import new_run_id, setup_logger
from src.ingest import read_extract
from src.results import record_results

SCHEMA_DIR = PROJECT_ROOT/"sql"            # the folder, not one file.
SCHEMA_FILES = ["01_schema_raw.sql","02_schema_control.sql","03_schema_reference.sql","04_schema_curated.sql"]      #run in this order

# which file goes into which table. 
RAW_TABLES = {"budget": "raw_budget", "actual": "raw_actual"}

def connect(settings):
    """Open the database file, creating it and its folder if they are missing."""
    db_path = PROJECT_ROOT/settings["paths"]["database"]
    db_path.parent.mkdir(parents=True,exist_ok=True)

    return sqlite3.connect(db_path)


def create_schema(conn,log):
    """Create the tables, by running the  .sql file.
    The table layouts live in their own .sql file rather than inside Python, so someone can 
    read what the tables look like without reading any code.

    Every CREATE in those files says "if not exists", so running them again on a database
    that already has the tables does nothing and harms nothing.
    """
    for name in SCHEMA_FILES:
        conn.executescript((SCHEMA_DIR/name).read_text())
        log.info(f"Tables ready, from {name}")
    conn.commit()



def land_extract(conn,table,rows,period,run_id,log):
    """Remove this quarter's rows, then put the files 's rows for it back.
    
    Remove-then-add, rather than just adding, is what makes a second run harmless. if it ony added, every run
    would leave another copy of the quarter behind and the totals would quietly grow, with 
    no error anywhere to tell you.
    """
    loaded_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")


    # the ? is a blank that database fills in from the values that follow. Always leave a blank rather than building
    # the sentence with the value already inside it. 
    # the table's "NAME" is the exception: the database will not accept a blank for that, so it has to be written
    # into text.
    deleted=conn.execute(f"DELETE FROM {table} WHERE PERIOD = ?", (period,)).rowcount

    # keep only the rows for the quarter being loaded. 
    period_rows = [r for r in rows if r["period"]== period]

    # executemany runs the same instruction once for each item in the list.
    conn.executemany(
        f"""INSERT INTO {table} (period,asset_id,family,cost_type,quantity,uom,amount,run_id,loaded_at)
        VALUES (?,?,?,?,?,?,?,?,?)""",
        [
            (
                r["period"],r["asset_id"],r["family"],r["cost_type"],r["quantity"],r["uom"],r["amount"],run_id,loaded_at,
            )
            for r in period_rows
        ],
    )

    conn.commit()

    log.info(f"{table}: removed {deleted}, added {len(period_rows)} for {period}")
    return period_rows




def reconcile_r1(conn,table,file_rows,period,log):
    """R1: prove what I landed matches what was in the file. 
    
    Two figures for this quarter - how many rows, and the total amount. if eith one differs,
    something was lost, doubled or altered between ready the file and writing the table. 

    This is the first tie-out in the chain. Every handoff between one part of the pipeline and the next
    gets one, and the last of them (R4) proves the figures in the Excel file match the figures database returned.
    """
    file_count = len(file_rows)
    file_total = sum(float(r["amount"]) for r in file_rows)

    #The amount column is stored as text, so it has to be read as a number to add it up.
    # CAST does that, here, for this check only - the stored value stays exactly the characters file had.
    db_count,db_total = conn.execute(
        f"""SELECT COUNT(*), SUM(CAST(amount AS REAL))
            FROM {table}
            WHERE PERIOD = ? """,
        (period,),
    ).fetchone()

    #if no rows matched, SUM gives back nothing rather than zero.
    db_total = db_total or 0.0

    #Two totals that reached here by different routes are almost never identical to the last decimal place,
    # so agree within a cent instead of asking for an exact match. 
    matched = file_count == db_count and abs(file_total - db_total) < 0.01

    result = {
        "control_id": "R1",
        "target": table,
        "status":"PASS" if matched else "FAIL",
        "detail": (
            f"file {file_count} rows / {file_total:,.2f} "
            f"vs table {db_count} rows / {db_total:,.2f}"
        ),
    }

    if matched:
        log.info(f"R1 {table}: PASS - {result['detail']}")
    else:
        log.error(f"R1 {table}: FAIL - {result['detail']}")


    return result




def parse_arg():
    """Read the quarter from the command line. Required - it never guesses."""
    parser = argparse.ArgumentParser(description="Put the extracts into database.")
    parser.add_argument("--period",required=True,help="Reporting priod,  eg.2026Q3")
    return parser.parse_args()


def land_reference(conn, settings, run_id, log):
    """Rebuild both reference tables from config.
    
    No period involved: these are replaced in whole every run, not one quarter at a time,
    because they describe what exists rather than what happened in a quarter.
    """
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # -- the assset master file, straight from the register file ------------
    register_path = PROJECT_ROOT / settings["paths"]["asset_register"]
    with open(register_path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))            # each line become a dict, keyed by the headings

    conn.execute("DELETE FROM ref_assets")     # no WHERE - the hwole table gose
    for r in rows: 
        conn.execute(
            """INSERT INTO ref_assets
            (asset_id, family, asset_class, acquired_year, replacement_cycle_years, capitalized_cost,
            seats, runs_on, notes, run_id, loaded_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)""",            # 11 fields, 11 values. 
            (r["asset_id"], r["family"], r["asset_class"],r["acquired_year"],r["replacement_cycle_years"],
             r["capitalized_cost"], r["seats"], r["runs_on"], r["notes"],run_id,stamp),
        )


    #  -------------- the cost type rule, from settings. -------------------
    conn.execute("DELETE FROM ref_cost_types")
    pairs = 0
    for family, kinds in settings["cost_types"].items():      # "tangible" --> ["PM", "CM"]
        for cost_type in kinds:
            conn.execute(
                "INSERT INTO ref_cost_types (family, cost_type, run_id, loaded_at) VALUES (?,?,?,?)",
                (family, cost_type, run_id, stamp),
            )
            pairs += 1


    # -------------- the materiality thresholds, from settings. -------------------
    conn.execute("DELETE FROM ref_materiality")                # empty the table first, so a second run cannot add the rows twice
    for family, limits in settings["materiality"].items():     # walks the two families in settings.yml, one at a time
        conn.execute(
            """INSERT INTO ref_materiality
            (family, absolute_threshold, percent_threshold, run_id, loaded_at)
            VALUES (?,?,?,?,?)""",                             # 5 fields, 5 values.
            (family, limits["absolute_threshold"], limits["percent_threshold"], run_id, stamp),
        )

    conn.commit()
    log.info(f"Reference rebuilt: {len(rows)} assets, {pairs} family/cost type pairs, "
             f"{len(settings['materiality'])} materiality thresholds")


def load(conn, settings, period, run_id, log):
    """Check both files and load one quarter. Hands back "PASS" or "FAIL".

    The connection and the run number come in as inputs, so run.py can use one
    connection and one run number for the whole pipeline.
    """
    results = []

    for name,table in RAW_TABLES.items():
        # Control c1 runs first. A file that fails its column check never reaches the database at all. 
        rows,result = read_extract(name,settings,log)

        # C1's line goes in whether it passed or failed. A log that only records passess
        # proves nothing -- failure is the one line an auditor wants to see. 
        # period is "ALL": C1 read the whole file, every quarter in it, not one quarter .
        # target_table is the table this file feeds, so the solumn always holds a real table name.
        record_results(
            conn, run_id, "C1","Schema conformance", table, "ALL",
            result["status"], len(rows),
            0 if result["status"] == "PASS" else 1,
            result["detail"],         # "256 rows, 7 columns", or what was wrong
        )
        conn.commit()            # saved now, so the line survives the exit below

        if result["status"] == "FAIL":
            log.error(f"{name} failed C1. Nothing was loaded.")
            return "FAIL"

        landed = land_extract(conn,table,rows,period,run_id,log)

        r1 = reconcile_r1(conn, table, landed, period, log)
        results.append(r1)

        # R1's line. rows_tested is this quarter's rows -- the ones R1 actually tied, 
        # not the whole file. Each control counts what it looked at. 
        record_results(
            conn, run_id, "R1","File to raw reconciliation", table, period,
            r1["status"], len(landed),
            0 if r1["status"] == "PASS" else 1,
            r1["detail"],             # "file 32 rows/296,230.92  vs.  table 32 rows / ...... "
         )
        conn.commit()

    if [r for r in results if r["status"] == "FAIL"]:
        log.error("R1 did not tie. The raw layer does not match the files.")
        return "FAIL"

    return "PASS"


def main():
    """Load one quarter into the real database."""
    args = parse_arg()
    run_id = new_run_id()
    log = setup_logger(run_id)
    settings = load_settings()

    log.info(f"Load started for {args.period}.")

    conn = connect(settings)
    create_schema(conn,log)
    land_reference(conn,settings,run_id,log)   # reference tables before the extracts
    outcome = load(conn, settings, args.period, run_id, log)
    conn.close()

    if outcome != "PASS":
        sys.exit(1)

    log.info("Load finished. R1 tied for both extracts.")


if __name__=="__main__":
    main()

