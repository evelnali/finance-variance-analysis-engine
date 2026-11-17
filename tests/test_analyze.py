"""Tests for the saved variance queries and R3.

Each test starts from the small shared database in tiny_db.py, changes one
thing in the raw data when it needs to, then builds the curated layer and
creates the queries. Nothing here touches data/variance.db.

In the starting data every line has budget 100.00 and actual 150.00, with the
same quantity on both sides. So every line is 50.00 over budget, and all of it
is price: the work was as planned, and each unit cost more.
"""

from src.curate import curate
from src.analyze import create_queries, reconcile_r3, analyze
from tiny_db import tiny_database, spoil, count, LOG      # the shared throwaway database


def built(conn):
    """Build the curated layer and create the saved queries on a tiny database."""
    assert curate(conn, "t", LOG) == "PASS"
    create_queries(conn, LOG)
    return conn


def one(conn, sql):
    """Run a query that gives back one line, and hand back that line."""
    return conn.execute(sql).fetchone()


CNC_PM_2026Q1 = "period = '2026Q1' AND asset_id = 'CNC-01' AND cost_type = 'PM'"


# ------------------------------------------------------- query_varn_by_asset

def test_budget_and_actual_sit_side_by_side_on_one_line():
    conn = built(tiny_database())
    assert count(conn, "query_varn_by_asset") == 8        # 2 assets x 2 cost types x 2 quarters
    line = one(conn, f"""SELECT budget_amount, actual_amount, varn, varn_pct
                         FROM query_varn_by_asset WHERE {CNC_PM_2026Q1}""")
    assert line == (100.0, 150.0, 50.0, 50.0)


def test_an_underspend_is_a_negative_variance():
    conn = tiny_database()
    spoil(conn, f"UPDATE raw_actual SET amount = '60.00' WHERE {CNC_PM_2026Q1}")
    built(conn)
    assert one(conn, f"SELECT varn FROM query_varn_by_asset WHERE {CNC_PM_2026Q1}") == (-40.0,)


def test_descriptions_are_looked_up_from_the_dimension_tables():
    conn = built(tiny_database())
    line = one(conn, f"""SELECT family, asset_class, uom, period_seq
                         FROM query_varn_by_asset WHERE {CNC_PM_2026Q1}""")
    assert line == ("tangible", "CNC_MACHINING_CENTRE", "WORK_ORDER", 8105)


# --------------------------------------------------- query_varn_price_volume

def test_same_quantity_means_the_whole_variance_is_price():
    conn = built(tiny_database())
    line = one(conn, f"""SELECT volume_effect, price_effect
                         FROM query_varn_price_volume WHERE {CNC_PM_2026Q1}""")
    assert line == (0.0, 50.0)


def test_volume_and_price_on_a_line_worked_out_by_hand():
    # Budget: 2 work orders at 50.00 = 100.00.  Actual: 4 work orders, 300.00.
    #   flexed budget = 4 x 50.00       = 200.00
    #   volume effect = 200.00 - 100.00 = 100.00
    #   price effect  = 300.00 - 200.00 = 100.00
    conn = tiny_database()
    spoil(conn, f"UPDATE raw_actual SET quantity = '4.0', amount = '300.00' WHERE {CNC_PM_2026Q1}")
    built(conn)
    line = one(conn, f"""SELECT budget_price, flexed_budget, volume_effect, price_effect, varn
                         FROM query_varn_price_volume WHERE {CNC_PM_2026Q1}""")
    assert line == (50.0, 200.0, 100.0, 100.0, 200.0)


def test_a_line_where_nothing_happened_is_all_volume():
    conn = tiny_database()
    spoil(conn, f"UPDATE raw_actual SET quantity = '0.0', amount = '0.00' WHERE {CNC_PM_2026Q1}")
    built(conn)
    line = one(conn, f"""SELECT volume_effect, price_effect, actual_price
                         FROM query_varn_price_volume WHERE {CNC_PM_2026Q1}""")
    assert line == (-100.0, 0.0, None)                    # no actual price when nothing was done


def test_work_that_was_not_budgeted_is_counted_as_volume():
    # No budget quantity means no budget price to flex with, so the whole
    # variance is volume and none of it is price.
    conn = tiny_database()
    spoil(conn, f"UPDATE raw_budget SET quantity = '0.0', amount = '0.00' WHERE {CNC_PM_2026Q1}")
    built(conn)
    line = one(conn, f"""SELECT budget_price, volume_effect, price_effect
                         FROM query_varn_price_volume WHERE {CNC_PM_2026Q1}""")
    assert line == (None, 150.0, 0.0)


def test_volume_plus_price_is_the_variance_on_every_line():
    conn = tiny_database()
    spoil(conn, f"UPDATE raw_actual SET quantity = '4.0', amount = '300.00' WHERE {CNC_PM_2026Q1}")
    built(conn)
    out = one(conn, """SELECT COUNT(*) FROM query_varn_price_volume
                       WHERE ABS(volume_effect + price_effect - varn) > 0.005""")
    assert out == (0,)


# ------------------------------------------------------- query_varn_by_class

def add_a_second_cnc(conn):
    """Give the CNC class a second machine, CNC-02, with the same rows as CNC-01."""
    spoil(conn, """INSERT INTO ref_assets
                   SELECT 'CNC-02', family, asset_class, acquired_year, replacement_cycle_years,
                          capitalized_cost, seats, runs_on, notes, run_id, loaded_at
                   FROM ref_assets WHERE asset_id = 'CNC-01'""")
    for table in ["raw_budget", "raw_actual"]:
        spoil(conn, f"""INSERT INTO {table}
                        SELECT period, 'CNC-02', family, cost_type, quantity, uom, amount, run_id, loaded_at
                        FROM {table} WHERE asset_id = 'CNC-01'""")


def test_assets_of_one_class_are_added_together():
    conn = tiny_database()
    add_a_second_cnc(conn)
    built(conn)
    line = one(conn, """SELECT assets, budget_amount, actual_amount, varn, varn_pct
                        FROM query_varn_by_class
                        WHERE period = '2026Q1' AND asset_class = 'CNC_MACHINING_CENTRE' AND cost_type = 'PM'""")
    assert line == (2, 200.0, 300.0, 100.0, 50.0)         # the percent is worked out again, not added


def test_the_threshold_depends_on_the_family():
    # Every line is 50.00 over. The limit is 40 for software and 75 for machines.
    conn = built(tiny_database())
    flags = dict(conn.execute(
        "SELECT family, SUM(is_material) FROM query_varn_by_class GROUP BY family").fetchall())
    assert flags == {"intangible": 4, "tangible": 0}


def test_a_large_underspend_is_material_too():
    conn = tiny_database()
    spoil(conn, f"UPDATE raw_actual SET amount = '10.00' WHERE {CNC_PM_2026Q1}")      # 90.00 under
    built(conn)
    line = one(conn, """SELECT varn, is_material FROM query_varn_by_class
                        WHERE period = '2026Q1' AND asset_class = 'CNC_MACHINING_CENTRE' AND cost_type = 'PM'""")
    assert line == (-90.0, 1)


def test_over_the_dollar_limit_but_under_the_percent_limit_is_not_material():
    # 100.00 over on a budget of 10,000.00: over the 75 dollar limit, but only 1%.
    conn = tiny_database()
    spoil(conn, f"UPDATE raw_budget SET amount = '10000.00' WHERE {CNC_PM_2026Q1}")
    spoil(conn, f"UPDATE raw_actual SET amount = '10100.00' WHERE {CNC_PM_2026Q1}")
    built(conn)
    line = one(conn, """SELECT varn, varn_pct, is_material FROM query_varn_by_class
                        WHERE period = '2026Q1' AND asset_class = 'CNC_MACHINING_CENTRE' AND cost_type = 'PM'""")
    assert line == (100.0, 1.0, 0)


# ------------------------------------------------------------------------ R3

def test_r3_passes_on_a_clean_build():
    conn = built(tiny_database())
    result = reconcile_r3(conn, LOG)
    assert result["status"] == "PASS"
    assert result["differ"] == []


def test_r3_catches_a_family_with_no_threshold():
    # Without a threshold the software lines drop out of query_varn_by_class.
    conn = tiny_database()
    spoil(conn, "DELETE FROM ref_materiality WHERE family = 'intangible'")
    built(conn)
    result = reconcile_r3(conn, LOG)
    assert result["status"] == "FAIL"
    assert "query_varn_by_class: budget total: expected 800.00, found 400.00" in result["differ"]


def test_r3_over_an_empty_expense_table_is_a_fail():
    conn = tiny_database()                                # the curated layer is never built
    create_queries(conn, LOG)
    assert reconcile_r3(conn, LOG)["status"] == "FAIL"


# --------------------------------------------------------- the whole step

def test_a_clean_analysis_records_one_pass_line():
    conn = tiny_database()
    curate(conn, "t", LOG)
    assert analyze(conn, "t", LOG) == "PASS"
    assert conn.execute(
        "SELECT status, rows_tested FROM control_results WHERE control_id = 'R3'").fetchall() == [("PASS", 8)]


def test_a_failed_r3_is_recorded_with_its_exceptions():
    conn = tiny_database()
    spoil(conn, "DELETE FROM ref_materiality WHERE family = 'intangible'")
    curate(conn, "t", LOG)
    assert analyze(conn, "t", LOG) == "FAIL"
    assert one(conn, "SELECT status FROM control_results WHERE control_id = 'R3'") == ("FAIL",)
    assert count(conn, "exceptions") == 4                 # the four checks on query_varn_by_class


def test_a_saved_query_follows_the_data_without_being_created_again():
    # A saved query stores no rows. Change the expense table and the next read shows it.
    conn = built(tiny_database())
    conn.execute(f"UPDATE fact_expense SET amount = 175.0 WHERE scenario = 'actual' AND {CNC_PM_2026Q1}")
    assert one(conn, f"SELECT varn FROM query_varn_by_asset WHERE {CNC_PM_2026Q1}") == (75.0,)