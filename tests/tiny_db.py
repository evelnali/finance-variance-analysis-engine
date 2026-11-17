"""The small throwaway database the tests share, and the helpers that go with it.

test_curate.py and test_analyze.py both need the same starting point. When two
files need the same thing, that thing gets its own home. This file's name does
not start with test_, so pytest does not look for tests in it.

The data is small enough to add up by hand: one machine and one software
product, two cost types each, two quarters. Every budget row is 100.00 and
every actual row is 150.00, with the same quantity on both.

    8 budget rows x 100.00 =   800.00
    8 actual rows x 150.00 = 1,200.00
"""

import logging
import sqlite3

from src.config import PROJECT_ROOT
from src.curate import switch_on_foreign_keys

SQL_DIR = PROJECT_ROOT / "sql"
SCHEMA_FILES = ["01_schema_raw.sql", "02_schema_control.sql",
                "03_schema_reference.sql", "04_schema_curated.sql"]

LOG = logging.getLogger("tests")             # somewhere for the log lines to go


def tiny_database():
    """A complete small database: real table layouts, sixteen raw rows."""
    conn = sqlite3.connect(":memory:")       # lives in memory only, gone when the test ends

    # The real layouts, so a test can never drift away from the real tables.
    for name in SCHEMA_FILES:
        conn.executescript((SQL_DIR / name).read_text())

    # The asset register, as text, blanks as '' - the way load.py lands it.
    conn.executemany("INSERT INTO ref_assets VALUES (?,?,?,?,?,?,?,?,?,?,?)", [
        # asset_id     family        class                   year    cycle  cost      seats runs_on notes
        ("CNC-01",    "tangible",   "CNC_MACHINING_CENTRE", "2010", "12",  "350000", "",   "",     "", "t", "t"),
        ("SW-CADCAM", "intangible", "CAD_CAM_SUITE",        "2015", "",    "140000", "6",  "",     "", "t", "t"),
    ])

    conn.executemany("INSERT INTO ref_cost_types VALUES (?,?,?,?)", [
        ("tangible", "PM", "t", "t"), ("tangible", "CM", "t", "t"),
        ("intangible", "LICENSE", "t", "t"), ("intangible", "SUPPORT", "t", "t"),
    ])

    # Thresholds sized for this tiny data. Every line here is 50.00 over budget,
    # so 50 is material for software (limit 40) and not for machines (limit 75).
    conn.executemany("INSERT INTO ref_materiality VALUES (?,?,?,?,?)", [
        # family       dollars  percent
        ("tangible",   75.0,    5.0, "t", "t"),
        ("intangible", 40.0,    5.0, "t", "t"),
    ])

    # Two quarters either side of a year end, so the quarter numbering is tested there.
    for table, amount in [("raw_budget", "100.00"), ("raw_actual", "150.00")]:
        for period in ["2025Q4", "2026Q1"]:
            conn.executemany(f"INSERT INTO {table} VALUES (?,?,?,?,?,?,?,?,?)", [
                (period, "CNC-01",    "tangible",   "PM",      "2.0", "WORK_ORDER", amount, "t", "t"),
                (period, "CNC-01",    "tangible",   "CM",      "1.0", "WORK_ORDER", amount, "t", "t"),
                (period, "SW-CADCAM", "intangible", "LICENSE", "6.0", "SEAT",       amount, "t", "t"),
                (period, "SW-CADCAM", "intangible", "SUPPORT", "1.0", "INCIDENT",   amount, "t", "t"),
            ])

    conn.commit()
    switch_on_foreign_keys(conn)
    return conn


def spoil(conn, sql):
    """Change the tiny database on purpose, and save the change.

    Saved straight away so that it is part of the starting point. Otherwise the
    undo inside curate() would undo the change as well.
    """
    conn.execute(sql)
    conn.commit()


def count(conn, table):
    """How many rows a table or saved query holds."""
    return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]