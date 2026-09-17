"""Logging setup: console and file output, every line stamped with the run id."""

import logging
from datetime import datetime


# import from own code. src.config is the module,
# so PROJECT_ROOT and load_settings are reused rather than redefined here.
from src.config import PROJECT_ROOT, load_settings

def new_run_id():
    """Return a sortable, readable identifier for one pipeline run."""
    # a timestamp rather than a random id: run idenfiers sort chronologically
    # and can be read by humans reviewing the log folder.

    return datetime.now().strftime("%Y%m%dT%H%M%S")

def setup_logger (run_id):
    """"Configure logging to console and to logs/run_<run_id>.log, and return the logger. """
    settings = load_settings()

    # Paths in settings.yml are relative to the project root, never to the folder the command was run from.
    log_dir = PROJECT_ROOT / settings["paths"]["logs"]
    # create a folder if it doesn't exist,
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"run_{run_id}.log"

    # the run id is fixed for the whole run, so it goes straight into the log format
    # string instead of being passed at every call site. 
    fmt = logging.Formatter(
        f"%(asctime)s | %(levelname)-7s| [{run_id}] | %(message)s",datefmt="%Y-%m-%d %H:%M:%S",
    )
    logger = logging.getLogger("variance_engine")
    logger.setLevel(settings["logging"]["level"])

    # Clear existing handlers so repeated setup calls don't duplicate every line. 
    logger.handlers.clear() 
    console = logging.StreamHandler()
    console.setFormatter(fmt)
    logger.addHandler(console)

    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler) 

    return logger

if __name__ == "__main__":
    run_id = new_run_id()
    log = setup_logger(run_id)

    log.info("Pipeline started.")
    log.info("Loaded 5 work orders")
    log.warning("Asset SAW-03 has no operating hours for 2026Q3")
    log.error("Control C4 failed: 2 accounts unmapped")
    log.info("Pipeline finished.")
