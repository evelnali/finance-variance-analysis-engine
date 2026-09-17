"""Pipeline entry point. Orchestrates the six layers; currently a skeleton."""

import argparse
from src.config import load_settings
from src.logger import new_run_id, setup_logger

def parse_args():
    """Parse command line arguments, --period is required. """
    parser = argparse.ArgumentParser(description="Run the maintenance expense variance pipeline.")
    parser.add_argument(
        "--period",required = True, help="Reporting period, eg. 2026Q3"
    )
    return parser.parse_args()

def main():
    """Run the pipeline for one reporting period."""
    args = parse_args()
    run_id = new_run_id()
    log = setup_logger(run_id)
    log.info(f"Run {run_id} started for period {args.period}.")
    settings = load_settings()
    threshold = settings["materiality"]["absolute_threshold"]
    percent = settings["materiality"]["percent_threshold"]
    log.info(f"Materiality: ${threshold:,.0f} and {percent:.1f}%")


    # 6 layers to be added later.......
    # ........
    log.warning("No pipeline layers implemented yet - M1 skeleton only.")
    log.info(f"Pipeline {run_id} finished.")

if __name__ == "__main__":
    main()