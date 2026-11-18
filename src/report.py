"""Write the variance report: one Excel workbook, built from the saved queries.

Every figure in the workbook is read from the database and written as a plain
value. Nothing is calculated here and nothing is a formula, so the workbook can
be read back and compared with the database (control R4).

The tool is openpyxl. It works like VBA from outside Excel:
    sheet.cell(row=2, column=3).value = 100      is      Cells(2, 3).Value = 100
"""

import sys
from pathlib import Path
from openpyxl import Workbook, load_workbook
from openpyxl.chart import BarChart, Reference
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

from src.config import PROJECT_ROOT, load_settings
from src.logger import new_run_id, setup_logger
from src.load import connect                          # borrowed rather than written twice
from src.results import record_results,record_exception


REPORT_NAME = "variance_report.xlsx"
R4_NAME = "Analysis to report reconciliation"
TOLERANCE = 0.01       # two figures agree when they are within a cent of each other

# R4 counts the lines and adds up the varn column on these three sheets. For each:
# the sheet, and where the same lines are in the database.
R4_SHEETS = [
    ("Material", "query_varn_by_class WHERE is_material = 1"),
    ("By class", "query_varn_by_class"),
    ("By asset", "query_varn_price_volume"),
]

# Every sheet has the same layout, so R4 knows where to find the figures.
TITLE_ROW = 1             # what the sheet is
NOTE_ROW = 2              # where its figures come from
HEADING_ROW = 4           # the column headings
FIRST_LINE_ROW = 5        # the first line of figures

BOLD = Font(bold=True)
HEADING_FILL = PatternFill("solid", start_color="D9E1F2")     # light blue behind the headings
LOOK_HERE_FILL = PatternFill("solid", start_color="FFF2CC")   # light yellow: a line to look at
AMOUNT_FORMAT = "#,##0.00"                                    # 1,234.50

# The Summary sheet. The same query is used twice: once with one line per
# quarter, once with everything added into a single total line. The two {gaps}
# are filled in when it is used. The text after AS becomes the column heading.
# The flexed budget is the budget plus the volume effect 
# (ie. the expected expense for the ACTUAL volume at the budgeted price),
# which is how the volume effect is defined (volume effect = flexed budget - budget).
# (flexed budget - budget) + (actual - flexed budget) = volume effect + price effect = variance = actual - budget
SUMMARY_SQL = """
    SELECT {first_column}                           AS "Quarter",
           SUM(budget_amount)                       AS "Budget",
           SUM(budget_amount) + SUM(volume_effect)  AS "Flexed budget",
           SUM(actual_amount)                       AS "Actual",
           SUM(varn)                                AS "Variance",
           100.0 * SUM(varn) / NULLIF(SUM(budget_amount), 0)  AS "Variance %",
           SUM(volume_effect)                       AS "Volume effect",
           SUM(price_effect)                        AS "Price effect",
           SUM(is_material)                         AS "Material lines"
    FROM query_varn_by_class
    {group_by}
"""
BY_QUARTER = "GROUP BY period, period_seq ORDER BY period_seq"

# The other four sheets: each is one query written out as it comes.
#   sheet name, title, the query, and which lines to shade: (column, value) or None
DETAIL_SHEETS = [
    ("Material",
     "Material variances: asset class lines over both thresholds",
     """SELECT period, family, asset_class, cost_type, uom, assets,
               budget_amount, actual_amount, varn, varn_pct, volume_effect, price_effect
        FROM query_varn_by_class
        WHERE is_material = 1
        ORDER BY period_seq, asset_class, cost_type""",
     None),

    ("By class",
     "Variance by asset class, cost type and quarter",
     "SELECT * FROM query_varn_by_class ORDER BY period_seq, asset_class, cost_type",
     ("is_material", 1)),                     # shade the material lines

    ("By asset",
     "Variance by asset, cost type and quarter, split into volume and price",
     "SELECT * FROM query_varn_price_volume ORDER BY period_seq, asset_id, cost_type",
     None),

    ("Controls",
     "Control log: every check the pipeline has run, newest first",
     """SELECT control_id, control_name, target_table, period, status,
               rows_tested, exceptions_found, detail, run_id, checked_at
        FROM control_results
        ORDER BY checked_at DESC, control_id, target_table""",
     ("status", "FAIL")),                     # shade any control that failed
]


def read_query(conn, sql):
    """Run a query. Hand back its column headings and its lines."""
    cursor = conn.execute(sql)
    # cursor.description holds one entry per column; the first item of each is the column's name
    headings = [column[0] for column in cursor.description]
    return headings, cursor.fetchall()


def write_table(sheet, title, note, headings, lines, shade_when=None, bold_last_line=False, filters=True):
    """Write a title, a note, a heading row and the lines of a query onto one sheet."""
    sheet.cell(row=TITLE_ROW, column=1).value = title
    sheet.cell(row=TITLE_ROW, column=1).font = Font(bold=True, size=14)
    sheet.cell(row=NOTE_ROW, column=1).value = note
    sheet.cell(row=NOTE_ROW, column=1).font = Font(italic=True, color="595959")

    # The heading row. enumerate(x, start=1) counts along with the loop: 1, 2, 3...
    for col, heading in enumerate(headings, start=1):
        cell = sheet.cell(row=HEADING_ROW, column=col)
        cell.value = heading
        cell.font = BOLD
        cell.fill = HEADING_FILL

    # Which column decides the shading, if any. index() gives its position in the list.
    shade_position = headings.index(shade_when[0]) if shade_when else None

    for row, line in enumerate(lines, start=FIRST_LINE_ROW):
        shade = shade_when is not None and line[shade_position] == shade_when[1]
        for col, value in enumerate(line, start=1):
            cell = sheet.cell(row=row, column=col)
            cell.value = value                         # an empty value (None) leaves the cell empty
            if isinstance(value, float):               # a number with decimals: show 1,234.50
                cell.number_format = AMOUNT_FORMAT
            if shade:
                cell.fill = LOOK_HERE_FILL

    last_row = HEADING_ROW + len(lines)
    last_column = get_column_letter(len(headings))     # 3 becomes "C"

    if bold_last_line:                                 # the total line
        for col in range(1, len(headings) + 1):
            sheet.cell(row=last_row, column=col).font = BOLD

    # Column widths: wide enough for the heading and the longest text, up to a limit.
    for col, heading in enumerate(headings, start=1):
        longest = len(heading)
        for line in lines:
            value = line[col - 1]
            longest = max(longest, 14 if isinstance(value, float) else len(str(value)))
        sheet.column_dimensions[get_column_letter(col)].width = min(longest + 2, 60)

    sheet.freeze_panes = f"A{FIRST_LINE_ROW}"          # the headings stay in view when scrolling
    if filters:                                        # the filter buttons on the heading row
        sheet.auto_filter.ref = f"A{HEADING_ROW}:{last_column}{last_row}"


def add_chart(sheet, quarters):
    """Under the Summary table: budget, flexed budget and actual, three columns per quarter."""
    last_quarter_row = HEADING_ROW + quarters          # stops before the total line

    chart = BarChart()
    chart.type = "col"                                 # upright columns
    chart.grouping = "clustered"                       # side by side, not stacked
    chart.title = "Budget, flexed budget and actual by quarter"
    chart.y_axis.title = "CAD"
    chart.y_axis.number_format = "#,##0"
    chart.x_axis.delete = False                        # without these two lines
    chart.y_axis.delete = False                        # Excel hides both axes

    # Columns 2 to 4 are Budget, Flexed budget and Actual. The range starts on
    # the heading row so the chart can take the three names from it.
    figures = Reference(sheet, min_col=2, max_col=4, min_row=HEADING_ROW, max_row=last_quarter_row)
    quarter_names = Reference(sheet, min_col=1, min_row=FIRST_LINE_ROW, max_row=last_quarter_row)
    chart.add_data(figures, titles_from_data=True)
    chart.set_categories(quarter_names)

    # Keep the title and the list of colours outside the area where the columns
    # are drawn. Left alone, Excel draws both on top of the columns.
    chart.title.overlay = False
    chart.legend.overlay = False
    chart.legend.position = "b"                        # b for bottom: under the quarter names

    chart.width = 26                                   # in centimetres
    chart.height = 12
    sheet.add_chart(chart, f"A{last_quarter_row + 4}") # top left corner, below the total line


def build_report(conn, run_id, path, log):
    """Write the whole workbook to path.

    The connection and the path come in as inputs, so a test can hand this
    function a small throwaway database and a throwaway folder.
    """
    book = Workbook()                                  # a new workbook comes with one empty sheet

    # Summary: the quarters, then one total line under them.
    summary = book.active
    summary.title = "Summary"
    headings, quarters = read_query(
        conn, SUMMARY_SQL.format(first_column="period", group_by=BY_QUARTER))
    _, total = read_query(                             # _ : the headings again, not needed twice
        conn, SUMMARY_SQL.format(first_column="'Total'", group_by=""))
    write_table(summary,
                "Maintenance and support expense: budget against actual",
                f"Canadian dollars. Variance = actual - budget, so a positive is over budget. "
                f"Volume effect = flexed budget - budget. Price effect = actual - flexed budget. "
                f"Every figure is a value read from the database by run {run_id}, not a formula.",
                headings, quarters + total, bold_last_line=True, filters=False)
    add_chart(summary, len(quarters))
    log.info(f"Summary: {len(quarters)} quarters and a total line")

    for name, title, sql, shade_when in DETAIL_SHEETS:
        sheet = book.create_sheet(name)
        headings, lines = read_query(conn, sql)
        write_table(sheet, title, "Column meanings are in docs/data_dictionary.md.",
                    headings, lines, shade_when=shade_when)
        log.info(f"{name}: {len(lines)} lines")

    book.save(path)
    log.info(f"Report written to {path}")
    return path


def read_sheet(sheet):
    """Read one sheet back from a saved workbook. Hand back its headings and its lines."""
    headings = [cell.value for cell in sheet[HEADING_ROW]]          # sheet[4] is the whole of row 4
    # values_only=True gives the figures in the cells, not the cells themselves
    lines = list(sheet.iter_rows(min_row=FIRST_LINE_ROW, values_only=True))
    return headings, lines


def column_total(headings, lines, name):
    """Add up one column of a sheet that was read back, found by its heading."""
    position = headings.index(name)
    return sum(line[position] for line in lines)


def reconcile_r4(conn, path, log):
    """R4: the saved workbook holds the same figures as the database.

    The workbook is opened again from disk, so what is checked is the file a
    reader will open. The database is asked again with its own plain SUM and
    COUNT, not with the queries that wrote the sheets.
    """
    book = load_workbook(path)
    checks = []               # one entry per check: (name, expected, found)
    lines_read = 0            # how many lines were read back from the file

    # Summary. Expected comes from query_varn_by_asset; the sheet was written
    # from query_varn_by_class. Two routes to the same three totals.
    headings, lines = read_sheet(book["Summary"])
    lines_read += len(lines)
    quarters, total = lines[:-1], lines[-1]          # every line but the last, and the last
    expected = conn.execute(
        """SELECT SUM(budget_amount), SUM(actual_amount), SUM(varn)
           FROM query_varn_by_asset""").fetchone()

    # zip pairs the two lists up: "Budget" with the first figure, "Actual" with the second...
    for heading, figure in zip(["Budget", "Actual", "Variance"], expected):
        position = headings.index(heading)
        checks.append((f"Summary: {heading} total", figure, total[position]))
        # The sheet foots: the quarter lines add up to the Total line.
        checks.append((f"Summary: quarters add up to the {heading} total",
                       total[position], column_total(headings, quarters, heading)))

    # Material, By class, By asset: the number of lines, and the varn column added up.
    for name, source in R4_SHEETS:
        headings, lines = read_sheet(book[name])
        lines_read += len(lines)
        count, varn = conn.execute(f"SELECT COUNT(*), SUM(varn) FROM {source}").fetchone()
        checks.append((f"{name}: lines", count, len(lines)))
        # "or 0.0": a sheet with no lines is allowed, and its total is zero
        checks.append((f"{name}: variance total", varn or 0.0, column_total(headings, lines, "varn")))

    # Controls: every line of the control log is on the sheet.
    headings, lines = read_sheet(book["Controls"])
    lines_read += len(lines)
    count = conn.execute("SELECT COUNT(*) FROM control_results").fetchone()[0]
    checks.append(("Controls: lines", count, len(lines)))

    differ = []               # one sentence per check that does not tie
    for check_name, expected, found in checks:
        if expected is None or found is None:
            # No total at all. A PASS over nothing is not a pass.
            differ.append(f"{check_name}: nothing to compare")
        elif abs(expected - found) >= TOLERANCE:
            differ.append(f"{check_name}: expected {expected:,.2f}, found {found:,.2f}")

    result = {
        "control_id": "R4",
        "status": "FAIL" if differ else "PASS",
        "rows_tested": lines_read,
        "differ": differ,
        "detail": f"{len(checks)} checks, {len(differ)} differ - {lines_read} lines read back from the workbook",
    }

    if result["status"] == "PASS":
        log.info(f"R4 report: PASS - {result['detail']}")
    else:
        log.error(f"R4 report: FAIL - {result['detail']}")
        for what in differ:
            log.error(f"    {what}")

    return result


def record_r4(conn, run_id, result):
    """Write R4's line into the control log, and one exception per check that differed."""
    for what in result["differ"]:
        # None, None: the objection is about the workbook, not one asset or cost type
        record_exception(conn, run_id, "R4", REPORT_NAME, "ALL", None, None, what)

    record_results(conn, run_id, "R4", R4_NAME, REPORT_NAME, "ALL",
                   result["status"], result["rows_tested"], len(result["differ"]),
                   result["detail"])


def report(conn, run_id, path, log):
    """Write the workbook, reconcile it and record the result. Hands back "PASS" or "FAIL".

    A workbook that fails R4 is deleted, so nothing that failed its tie-out is
    left looking finished. The reasons stay in the control log and the exceptions.
    """
    build_report(conn, run_id, path, log)

    result = reconcile_r4(conn, path, log)
    record_r4(conn, run_id, result)
    conn.commit()

    if result["status"] != "PASS":
        Path(path).unlink()                            # unlink is the word for deleting a file
        log.error(f"The workbook did not tie to the database and has been deleted: {path}")

    return result["status"]


def main():
    """Write the report from the real database into the output folder."""
    run_id = new_run_id()
    log = setup_logger(run_id)
    settings = load_settings()

    out_dir = PROJECT_ROOT / settings["paths"]["output"]
    out_dir.mkdir(parents=True, exist_ok=True)         # create the folder if it is missing

    log.info("Report started.")
    conn = connect(settings)
    outcome = report(conn, run_id, out_dir / REPORT_NAME, log)
    conn.close()

    if outcome != "PASS":
        log.error("Report failed. The workbook does not tie to the database; see the control log.")
        sys.exit(1)

    log.info("Report finished. The workbook ties to the database.")


if __name__ == "__main__":
    main()