"""Run the data-quality controls against the landed raw tables.

Each control asks one question of a whole table at once, and writes two things:
one line in control_results saying what it concluded, and one line in exceptions for
every item it objected to. 
"""

import argparse
import sys
from datetime import datetime

from src.config import PROJECT_ROOT, load_settings
from src.logger import new_run_id,setup_logger
from src.load import connect, RAW_TABLES        # borrowed rather than written twice

SQL_DIR = PROJECT_ROOT/ "sql"
C2_SQL = SQL_DIR/ "10_control_c2.sql"
C2_NAME = "Duplicate key detection"


def now_stamp():
    """The time as text, in the same shape as loaded_at"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def record_results(conn,run_id,control_id,control_name,table,period,status,rows_tested,
                   exceptions_found):
    """Write one line into the control log."""
    conn.execute(
        """INSERT INTO control_results
        (run_id, control_id, control_name,target_table,period,status,rows_tested,exceptions_found,checked_at)
        VALUES(?,?,?,?,?,?,?,?,?)""" ,       # nine blanks, nine value below
        (run_id,control_id,control_name,table,period,status,rows_tested,exceptions_found,now_stamp()),
    )


def record_exception(conn,run_id,control_id,table,period,
                     asset_id, cost_type,detail):
    """Write one line into the exception listing."""
    conn.execute(
        """INSERT INTO exceptions
        (run_id,control_id,target_table,period,asset_id, 
        cost_type,detail,found_at)
        VALUES (?,?,?,?,?,?,?,?)""" ,    #eight blanks, eight values below
        (run_id, control_id, table,period, asset_id,cost_type,detail,now_stamp()),
    )


def run_c2(conn,table,period,run_id,log):
    """C2 - duplicate key detection. Hands back how many offending keys it found."""
    query = C2_SQL.read_text().format(table=table)        #paste the table name in the period it goes in as a value
    offenders = conn.execute(query,(period,)).fetchall()


    # The population the test covered. A PASS over nothing is not a pass. 
    rows_tested = conn.execute(
        f"SELECT COUNT(*) FROM {table} WHERE period = ?", (period,)
    ).fetchone()[0]

    for found_period,asset_id,cost_type, n in offenders:     # unpack the four columns
        detail = f"{n} rows share this key - {n-1} too many"
        record_exception(conn,run_id,"C2",table,found_period,
                         asset_id, cost_type,detail)

    status = "FAIL" if offenders else "PASS"    # an empty list counts as no
    record_results(conn,run_id,"C2",C2_NAME,table,period,
                  status,rows_tested,len(offenders))
    conn.commit()


    log.info(f"C2 {table}: {status} - {rows_tested} rows tested, {len(offenders)} exceptions")
    for found_period, asset_id,cost_type, n in offenders:
        log.error(f"    {asset_id} {cost_type}: {n} rows share this key")

    return len(offenders)


def parse_args():
    p = argparse.ArgumentParser(description="Run the data-quality controls for one period.")
    p.add_argument("--period", required=True, help="e.g. 2026Q3")
    return p.parse_args()


def main():
    args = parse_args()
    run_id = new_run_id()
    log = setup_logger(run_id)
    settings = load_settings()

    log.info(f"Controls started for {args.period}.")
    conn = connect(settings)

    failures = 0
    for table in RAW_TABLES.values():
       failures += run_c2(conn, table, args.period, run_id, log)

    conn.close()

    if failures:
        log.error(f"Controls failed. {failures} exceptions written to the exceptions table.")
        sys.exit(1)

    log.info("Controls finished. All passed.")



if __name__ =="__main__":
    main()