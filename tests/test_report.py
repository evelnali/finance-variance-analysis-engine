"""Tests for the workbook and R4.

Each test builds the small shared database from tiny_db.py and writes the
workbook into a throwaway folder. Nothing here touches data/variance.db or
data/output.

tmp_path is supplied by pytest: a test that names it as an input is handed a
new, empty folder of its own.
"""

from openpyxl import load_workbook

from src.curate import curate
from src.analyze import analyze, create_queries
from src.report import build_report, reconcile_r4, report
from tiny_db import tiny_database, LOG                # the shared throwaway database


def analysed():
    """A tiny database with the curated layer built and the saved queries created and tied."""
    conn = tiny_database()
    assert curate(conn, "t", LOG) == "PASS"
    assert analyze(conn, "t", LOG) == "PASS"
    return conn


def test_a_clean_report_passes_r4(tmp_path):
    conn = analysed()
    path = tmp_path / "report.xlsx"                   # a file name inside the throwaway folder
    build_report(conn, "t", path, LOG)
    result = reconcile_r4(conn, path, LOG)
    assert result["status"] == "PASS"
    assert result["differ"] == []


def test_r4_catches_a_figure_changed_in_the_saved_file(tmp_path):
    conn = analysed()
    path = tmp_path / "report.xlsx"
    build_report(conn, "t", path, LOG)

    # Open the saved file and overtype one figure, as someone might by hand.
    # Row 7 is the Total line (two quarters, then the total); column 5 is Variance.
    book = load_workbook(path)
    book["Summary"].cell(row=7, column=5).value = 999
    book.save(path)

    result = reconcile_r4(conn, path, LOG)
    assert result["status"] == "FAIL"
    assert "Summary: Variance total: expected 400.00, found 999.00" in result["differ"]


def test_r4_catches_a_line_removed_from_the_saved_file(tmp_path):
    conn = analysed()
    path = tmp_path / "report.xlsx"
    build_report(conn, "t", path, LOG)

    book = load_workbook(path)
    book["By class"].delete_rows(5)                   # remove the first line of figures
    book.save(path)

    result = reconcile_r4(conn, path, LOG)
    assert result["status"] == "FAIL"
    assert "By class: lines: expected 8.00, found 7.00" in result["differ"]


def test_a_report_over_an_empty_database_fails_and_is_deleted(tmp_path):
    conn = tiny_database()                            # the curated layer is never built
    create_queries(conn, LOG)
    path = tmp_path / "report.xlsx"
    assert report(conn, "t", path, LOG) == "FAIL"
    assert not path.exists()                          # nothing left that looks like a report


def test_a_clean_report_is_kept_and_records_one_pass_line(tmp_path):
    conn = analysed()
    path = tmp_path / "report.xlsx"
    assert report(conn, "t", path, LOG) == "PASS"
    assert path.exists()
    # 25 lines read back: Summary 3, Material 4, By class 8, By asset 8, Controls 2
    assert conn.execute(
        "SELECT status, rows_tested FROM control_results WHERE control_id = 'R4'").fetchall() == [("PASS", 25)]