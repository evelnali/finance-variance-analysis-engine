"""Writing to the control log and exception listing.

These live here rather than in controls.py because load.py needs them too: 
C1 and R1 are tests with results, exactly like C2 to C5.

When two files need the same thing, that thing gets own home. 
If load.py imported from controls.py while controls.py already imports from
load.py, each would need the other before either hand finished loading. 
"""

from datetime import datetime


def now_stamp():
    """The time as text, in the same shape as loaded_at."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")



def record_results(conn, run_id, control_id, control_name, table, period, 
                   status, rows_tested, exceptions_found, detail=""):    # ="" --> a default: if the caller doesn't pass it, it's empty text
    """Write one line into the control log.
    
    Detail carries the figures a reconciliation tied, so thay are recorded when it passes and 
    hot only when it fails. It has a default, so every call written before this column existed 
    still works -- it just records an empty detail.
    """
    conn.execute(
        """INSERT INTO control_results 
        (run_id, control_id, control_name, target_table, period, status, rows_tested,
        exceptions_found, detail, checked_at)
        VALUES (?,?,?,?,?,?,?,?,?,?)""",              #10 blanks, ten values below 
        (run_id,control_id, control_name,table,period,status, rows_tested,
         exceptions_found, detail, now_stamp()),  
        )


def record_exception(conn, run_id, control_id, table, period, asset_id, cost_type, detail):
    """Write on line into the exception listing."""
    conn.execute(
        """INSERT INTO exceptions
        (run_id, control_id, target_table, period, asset_id, cost_type, detail, found_at)
        VALUES(?,?,?,?,?,?,?,?)""",        # 8 blanks, 8 values below
        (run_id, control_id,table, period, asset_id, cost_type, detail, now_stamp()),
    )