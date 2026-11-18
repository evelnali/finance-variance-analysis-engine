"""Run the whole pipeline with one command:

    python -m src.run

Every quarter in the extracts is loaded and checked. Then the curated layer,
the saved queries and the workbook are rebuilt.

One connection and one run number are used from start to finish, and the
first step that fails stops the run.
"""

import argparse
import csv
import sys

from src.config import PROJECT_ROOT, load_settings
from src.logger import new_run_id, setup_logger
from src.load import connect, create_schema, land_reference, load
from src.controls import run_controls
from src.curate import curate
from src.analyze import analyze
from src.report import report, REPORT_NAME


def quarters_in_extract(settings):
    """The quarters the budget extract holds, earliest first."""
    path = PROJECT_ROOT / settings["paths"]["raw_data"] / settings["extracts"]["budget"]["file"]
    with open(path, newline="") as f:
        # { } collects each quarter once, however many rows it has; sorted puts them in order
        return sorted({row["period"] for row in csv.DictReader(f)})


def run_pipeline(conn, settings, quarters, run_id, report_path, log):
    """Run every step in order. Hands back the name of the step that failed, or None if none did."""
    create_schema(conn, log)                           # the tables, if this is a new database
    land_reference(conn, settings, run_id, log)        # asset register, cost types, thresholds

    for quarter in quarters:
        log.info(f"--- {quarter}: load (C1, R1)")
        if load(conn, settings, quarter, run_id, log) != "PASS":
            return f"load {quarter}"

        log.info(f"--- {quarter}: controls (C2 to C5)")
        if run_controls(conn, quarter, run_id, log) != "PASS":
            return f"controls {quarter}"

    log.info("--- curate (R2)")
    if curate(conn, run_id, log) != "PASS":
        return "curate"

    log.info("--- analyze (R3)")
    if analyze(conn, run_id, log) != "PASS":
        return "analyze"

    log.info("--- report (R4)")
    if report(conn, run_id, report_path, log) != "PASS":
        return "report"

    return None


def main():
    """Run the pipeline on the real database."""
    # This command takes no options. If anything is typed after it, argparse
    # stops with a message, so an option is never silently ignored.
    argparse.ArgumentParser(description="Run the whole pipeline. Takes no options.").parse_args()

    run_id = new_run_id()

    run_id = new_run_id()
    log = setup_logger(run_id)
    settings = load_settings()

    quarters = quarters_in_extract(settings)

    out_dir = PROJECT_ROOT / settings["paths"]["output"]
    out_dir.mkdir(parents=True, exist_ok=True)         # create the folder if it is missing
    report_path = out_dir / REPORT_NAME

    log.info(f"Pipeline started: {len(quarters)} quarters, {quarters[0]} to {quarters[-1]}.")
    conn = connect(settings)
    failed_step = run_pipeline(conn, settings, quarters, run_id, report_path, log)
    conn.close()

    if failed_step:
        log.error(f"Pipeline stopped at: {failed_step}. The reason is in the lines above and in the control log.")
        sys.exit(1)

    log.info(f"Pipeline finished. Every control passed. Workbook: {report_path}")


if __name__ == "__main__":
    main()