"""Tests for C5, the reasonability control. 

Five rows, chosen to cover every case the rule has to decide. Built in memory and
thrown away - nothing here touches data/variance.db

The first test is the important one: a zero-quantity, zero-amount row is LEGITIMATE, and 
a C5 that flags it would halt every clean run. 
"""

import sqlite3
from pathlib import Path

# test/ is one level down from the project folder, so two parents up. 
PROJECT_ROOT = Path(__file__).resolve().parent.parent
C5_SQL = (PROJECT_ROOT / "sql"/ "10_control_c5.sql").read_text()



def tiny_database():
    """One table, six rows, one for each thing the rule has to decide."""
    conn =sqlite3.connect(":memory:")     # lives in memory only, gone when the test ends
    conn.execute("""CREATE TABLE raw_budget(
        period TEXT, asset_id TEXT, family TEXT, cost_type TEXT,
        quantity TEXT, uom TEXT, amount TEXT, run_id TEXT, loaded_at TEXT)""")
    rows = [
        ("2026Q3", "SAW-04", "tangible", "CM", "0.0", "WORK_ORDER", "0.0",    "t", "t"),   #ok
        ("2026Q3", "CNC-01", "tangible", "PM", "2.0", "WORK_ORDER", "7000.0", "t","t"), #ok
        ("2026Q3", "SAW-CADCAM", "intangible", "LICENSE", "6.0", "SEAT", "3800.0", "t", "t"),  #ok
        ("2026Q3", "CNC-02", "tangible", "PM", "0.0", "WORK_ORDER", "5000.0", "t", "t"),    # has cost, but no work
        ("2026Q3", "CNC-03", "tangible","PM", "2.0", "WORK_ORDER", "0.0", "t","t"),      # has work, but no cost
        ("2026Q3", "SAW-01", "tangible", "CM", "-1.0", "WORK_ORDER", "500.0", "t", "t"),    # negative value
    ]
    conn.executemany("INSERT INTO raw_budget VALUES (?,?,?,?,?,?,?,?,?)", rows)
    return conn




def flagged():
    """Run C5 and hand back {asset_id: reason} for every row it objected to."""
    found = tiny_database().execute(C5_SQL.format(table="raw_budget"), ("2026Q3",)).fetchall()
    return {r[0]: r[4] for r in found}         #column 0 is asset_id, column 4 is the reason



def test_zero_quantity_and_zero_amount_is_allowed():
    # SAW-04 had a quiet quarter. No work, no cost. This must not be flagged. 
    assert "SAW-04" not in flagged()


def test_an_intangible_row_is_judged_the_same_way():
    # C5 reads only quantity and amount, so family must make no difference.
    # If someone gives it a family-specific rule later, this test objects.
    assert "SAW-CADCAM" not in flagged()


def test_work_with_no_cost_is_flagged():
    assert flagged()["CNC-03"] == "work recorded with no cost"


def test_an_ordinary_row_is_allowed():
    assert "CNC-01" not in flagged()


def test_cost_with_no_work_is_flagged():
    assert flagged()["CNC-02"] == "cost with no work behind it"


def test_negative_quantity_is_flagged():
    assert flagged()["SAW-01"] == "negative quantity"


def test_nothing_else_is_flagged():
    # Without this, C5 could start flagging everything and the tests above
    # would all still pass. 
    assert len(flagged()) == 3 