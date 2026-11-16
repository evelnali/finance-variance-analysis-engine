"""Tests for the curated build and R2.

Each test gets its own small database, built in memory and thrown away. It uses
the real schema files and the real build files, so what is tested is exactly
what runs. Nothing here touches data/variance.db.

The data is small enough to add up by hand: one machine and one software
product, two cost types each, two quarters. Every budget row is 100.00 and
every actual row is 150.00.

    8 budget rows x 100.00 =   800.00
    8 actual rows x 150.00 = 1,200.00
"""

import logging
import sqlite3

import pytest

from src.config import PROJECT_ROOT
from src.curate import (build_curated, reconcile_r2, record_r2, curate,
                        switch_on_foreign_keys)

SQL_DIR = PROJECT_ROOT / "sql"
SCHEMA_FILES = ["01_schema_raw.sql", "02_schema_control.sql",
                "03_schema_reference.sql", "04_schema_curated.sql"]

LOG = logging.getLogger("test_curate")       # somewhere for the log lines to go


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
    """Damage the tiny database on purpose, and save the damage.

    Saved straight away so that it is part of the starting point. Otherwise the
    undo inside curate() would undo the damage as well.
    """
    conn.execute(sql)
    conn.commit()


def count(conn, table):
    """How many rows a table holds."""
    return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


# ---------------------------------------------------------------- a clean build

def test_a_clean_build_fills_all_four_tables():
    conn = tiny_database()
    build_curated(conn, "t", LOG)
    assert count(conn, "dim_period") == 2
    assert count(conn, "dim_asset") == 2
    assert count(conn, "dim_cost_type") == 4
    assert count(conn, "fact_expense") == 16


def test_amounts_arrive_as_numbers_and_add_up():
    conn = tiny_database()
    build_curated(conn, "t", LOG)
    totals = dict(conn.execute(
        "SELECT scenario, SUM(amount) FROM fact_expense GROUP BY scenario").fetchall())
    assert totals == {"budget": 800.0, "actual": 1200.0}


def test_quarters_either_side_of_a_year_end_are_one_apart():
    conn = tiny_database()
    build_curated(conn, "t", LOG)
    seq = dict(conn.execute("SELECT period, period_seq FROM dim_period").fetchall())
    assert seq["2026Q1"] - seq["2025Q4"] == 1


def test_a_blank_in_the_register_stays_blank():
    # A machine has no seats and software has no replacement cycle.
    # Without NULLIF both would arrive as 0.
    conn = tiny_database()
    build_curated(conn, "t", LOG)
    seats = dict(conn.execute("SELECT asset_id, seats FROM dim_asset").fetchall())
    cycle = dict(conn.execute("SELECT asset_id, replacement_cycle_years FROM dim_asset").fetchall())
    assert seats["CNC-01"] is None
    assert cycle["SW-CADCAM"] is None
    assert seats["SW-CADCAM"] == 6          # and a real value still gets through


def test_building_twice_leaves_the_same_rows():
    conn = tiny_database()
    build_curated(conn, "t", LOG)
    build_curated(conn, "t", LOG)
    assert count(conn, "fact_expense") == 16


# ------------------------------------------------- rows the tables must refuse

def test_an_expense_for_an_unknown_asset_stops_the_build():
    conn = tiny_database()
    spoil(conn, "UPDATE raw_actual SET asset_id = 'CNC-99' WHERE rowid = 1")
    with pytest.raises(sqlite3.IntegrityError):       # the test passes only if this error happens
        build_curated(conn, "t", LOG)


def test_a_blank_capitalized_cost_stops_the_build():
    conn = tiny_database()
    spoil(conn, "UPDATE ref_assets SET capitalized_cost = '' WHERE asset_id = 'CNC-01'")
    with pytest.raises(sqlite3.IntegrityError):
        build_curated(conn, "t", LOG)


def test_a_register_line_with_no_asset_id_stops_the_build():
    # SQLite lets a text primary key be empty unless the column also says NOT NULL.
    conn = tiny_database()
    spoil(conn, """INSERT INTO ref_assets VALUES
                   ('', 'tangible', 'COPY_ROUTER', '2019', '8', '65000', '', '', '', 't', 't')""")
    with pytest.raises(sqlite3.IntegrityError):
        build_curated(conn, "t", LOG)


def test_one_cost_type_with_two_units_stops_the_build():
    conn = tiny_database()
    spoil(conn, "UPDATE raw_actual SET uom = 'HOURS' WHERE rowid = 1")
    with pytest.raises(sqlite3.IntegrityError):
        build_curated(conn, "t", LOG)


def test_a_duplicated_raw_row_stops_the_build():
    # UNION would have merged the two rows quietly. UNION ALL keeps both,
    # and the primary key refuses the second.
    conn = tiny_database()
    spoil(conn, "INSERT INTO raw_actual SELECT * FROM raw_actual WHERE rowid = 1")
    with pytest.raises(sqlite3.IntegrityError):
        build_curated(conn, "t", LOG)


# -------------------------------------------------------------------------- R2

def test_r2_passes_on_a_clean_build():
    conn = tiny_database()
    build_curated(conn, "t", LOG)
    result = reconcile_r2(conn, LOG)
    assert result["status"] == "PASS"
    assert result["differ"] == []


def test_r2_catches_a_lost_row():
    conn = tiny_database()
    build_curated(conn, "t", LOG)
    conn.execute("""DELETE FROM fact_expense WHERE period = '2026Q1' AND asset_id = 'CNC-01'
                    AND cost_type = 'PM' AND scenario = 'actual'""")
    result = reconcile_r2(conn, LOG)
    assert result["status"] == "FAIL"
    assert len(result["differ"]) == 1
    assert result["differ"][0][0] == "2026Q1"        # and it names the right quarter


def test_r2_catches_a_changed_amount_when_the_row_count_still_agrees():
    conn = tiny_database()
    build_curated(conn, "t", LOG)
    conn.execute("""UPDATE fact_expense SET amount = amount + 5 WHERE period = '2025Q4'
                    AND asset_id = 'CNC-01' AND cost_type = 'CM' AND scenario = 'budget'""")
    assert reconcile_r2(conn, LOG)["status"] == "FAIL"


def test_r2_still_shows_a_quarter_that_is_missing_from_curated():
    # The reason R2 stacks instead of joining: a join would drop this line
    # and the reconciliation would look clean.
    conn = tiny_database()
    build_curated(conn, "t", LOG)
    conn.execute("DELETE FROM fact_expense WHERE period = '2025Q4' AND scenario = 'budget'")
    result = reconcile_r2(conn, LOG)
    assert ("2025Q4", "budget: raw 4 rows / 400.00 vs curated 0 rows / 0.00") in result["differ"]


def test_r2_over_nothing_is_a_fail():
    conn = tiny_database()
    spoil(conn, "DELETE FROM raw_budget")
    spoil(conn, "DELETE FROM raw_actual")
    assert reconcile_r2(conn, LOG)["status"] == "FAIL"


# --------------------------------------------------- the whole thing, as one unit

def test_a_clean_run_saves_the_build_and_one_pass_line():
    conn = tiny_database()
    assert curate(conn, "t", LOG) == "PASS"
    assert count(conn, "fact_expense") == 16
    assert conn.execute(
        "SELECT status FROM control_results WHERE control_id = 'R2'").fetchall() == [("PASS",)]


def test_a_stopped_build_leaves_the_last_good_build_in_place():
    conn = tiny_database()
    curate(conn, "t", LOG)                                  # a good build first
    spoil(conn, "UPDATE raw_actual SET asset_id = 'CNC-99' WHERE rowid = 1")
    assert curate(conn, "t", LOG) == "STOPPED"
    assert count(conn, "fact_expense") == 16               # still the good build, not half of a new one
    assert count(conn, "dim_asset") == 2


def test_a_build_that_does_not_tie_is_undone_but_the_failure_is_recorded():
    conn = tiny_database()
    curate(conn, "t", LOG)                                  # a good build first

    # The build files are correct, so a build that goes wrong has to be planted.
    # A trigger is a rule the database runs by itself whenever a row is added.
    # This one deletes one particular row the moment it arrives, playing the
    # part of a transform that loses a row.
    spoil(conn, """CREATE TRIGGER lose_a_row AFTER INSERT ON fact_expense
                   WHEN NEW.period = '2026Q1' AND NEW.asset_id = 'CNC-01'
                    AND NEW.cost_type = 'PM' AND NEW.scenario = 'actual'
                   BEGIN
                       DELETE FROM fact_expense WHERE rowid = NEW.rowid;
                   END""")

    assert curate(conn, "t", LOG) == "FAIL"
    assert count(conn, "fact_expense") == 16               # the 15-row build was not kept
    assert conn.execute(
        "SELECT status FROM control_results WHERE control_id = 'R2' ORDER BY rowid"
    ).fetchall() == [("PASS",), ("FAIL",)]                 # both runs are in the control log
    assert count(conn, "exceptions") == 1                  # and the line that differed is listed