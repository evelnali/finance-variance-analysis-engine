"""Create the saved variance queries, then prove they hold the same money as the expense table.

Each query file in sql/ defines one saved query (a SQL view). This module runs
those files in order, runs R3 to tie the queries back to fact_expense, and
writes R3's result into the control log.

A saved query stores no rows. Creating one changes nothing in the data, so
unlike curate.py there is nothing to undo when R3 fails: the failure is
recorded, and the run exits non-zero.
"""

import sys

from src.config import PROJECT_ROOT, load_settings
from src.logger import new_run_id, setup_logger
from src.load import connect                          # borrowed rather than written twice
from src.results import record_results, record_exception


SQL_DIR = PROJECT_ROOT / "sql"

# The saved queries and the file that defines each one, in the order they must
# be created: each query reads from the one before it.
QUERY_FILES = [
    ("query_varn_by_asset",     "30_query_varn_by_asset.sql"),
    ("query_varn_price_volume", "31_query_varn_price_volume.sql"),
    ("query_varn_by_class",     "32_query_varn_by_class.sql"),
]

R3_SQL = SQL_DIR / "33_control_r3.sql"
R3_NAME = "Curated to analysis reconciliation"
TOLERANCE = 0.01          # two figures agree when they are within a cent of each other


def create_queries(conn, log):
    """Create the three saved queries, replacing any older versions."""
    for name, filename in QUERY_FILES:
        # executescript, not execute: each file holds two statements,
        # DROP VIEW and then CREATE VIEW.
        conn.executescript((SQL_DIR / filename).read_text())

        lines = conn.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
        log.info(f"{name}: created by {filename}, {lines} lines")


def reconcile_r3(conn, log):
    """R3: the saved queries hold the same money as fact_expense.

    The query gives one line per check: a name, the figure expected and the
    figure found. This function compares the two and hands back what it concluded.
    """
    checks = conn.execute(R3_SQL.read_text()).fetchall()

    differ = []        # one sentence per check that does not tie
    for check_name, expected, found in checks:
        if expected is None or found is None:
            # SUM over no rows gives nothing at all. A PASS over nothing is not a pass.
            differ.append(f"{check_name}: nothing to compare")
        elif abs(expected - found) >= TOLERANCE:
            differ.append(f"{check_name}: expected {expected:,.2f}, found {found:,.2f}")

    # The figures the checks tied, for the control log. "or 0.0" covers an empty
    # query, where SUM gives nothing and there would be no number to print.
    lines, budget, actual, varn = conn.execute(
        """SELECT COUNT(*), SUM(budget_amount), SUM(actual_amount), SUM(varn)
           FROM query_varn_by_asset"""
    ).fetchone()

    result = {
        "control_id": "R3",
        "status": "FAIL" if differ else "PASS",
        "rows_tested": lines,
        "differ": differ,
        "detail": (f"{len(checks)} checks, {len(differ)} differ - "
                   f"budget {budget or 0.0:,.2f}, actual {actual or 0.0:,.2f}, "
                   f"variance {varn or 0.0:,.2f}"),
    }

    if result["status"] == "PASS":
        log.info(f"R3 saved queries: PASS - {result['detail']}")
    else:
        log.error(f"R3 saved queries: FAIL - {result['detail']}")
        for what in differ:
            log.error(f"    {what}")

    return result


def record_r3(conn, run_id, result):
    """Write R3's line into the control log, and one exception per check that differed."""
    for what in result["differ"]:
        # None, None: the objection is about a whole query, not one asset or cost type
        record_exception(conn, run_id, "R3", "query_varn", "ALL", None, None, what)

    record_results(conn, run_id, "R3", R3_NAME, "query_varn", "ALL",
                   result["status"], result["rows_tested"], len(result["differ"]),
                   result["detail"])


def analyze(conn, run_id, log):
    """Create the queries, reconcile them and record the result. Hands back "PASS" or "FAIL".

    The connection comes in as an input, so a test can hand this function a
    small throwaway database instead of the real one.
    """
    create_queries(conn, log)

    result = reconcile_r3(conn, log)
    record_r3(conn, run_id, result)
    conn.commit()

    if result["status"] == "PASS":
        # What the analysis found, in one line.
        material, total = conn.execute(
            "SELECT SUM(is_material), COUNT(*) FROM query_varn_by_class").fetchone()
        log.info(f"{material} of {total} asset class lines are material.")

    return result["status"]


def main():
    """Create the saved queries in the real database and tie them back to the expense table."""
    run_id = new_run_id()
    log = setup_logger(run_id)
    settings = load_settings()

    log.info("Analysis started.")
    conn = connect(settings)
    outcome = analyze(conn, run_id, log)
    conn.close()

    if outcome != "PASS":
        log.error("Analysis failed. The queries do not tie to the expense table; see the control log.")
        sys.exit(1)

    log.info("Analysis finished. The saved queries tie to the expense table.")


if __name__ == "__main__":
    main()