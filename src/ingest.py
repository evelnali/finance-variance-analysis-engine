"""Read the ERP-style extracts and check their shape before anything else touches them. 

This is the first step of the pipeline proper, which makes it the first module to use
the logger instead of print().  generate_data.py is a tool that makes test data; that is the
pipeline, and the rule there is no print().
"""


import csv
import sys

from src.config import PROJECT_ROOT,load_settings
from src.logger import new_run_id,setup_logger


def read_extract(name,settings,log):
    """Read one extract and run control C1 on it.
    
    C1 is schema conformance: is the file there, does it have the columns we expect, and
    does it have any rows at all. It does not look at the values - that is C2 to C5,
    and those belong in SQL once the data has landed.
    """

    spec = settings["extracts"][name]
    path = PROJECT_ROOT/settings["paths"]["raw_data"]/spec["file"]
    expected = spec["columns"]

    result = {"control_id": "C1", "target": name,"status": "PASS","detail": ""}


    # ------- can it be read at all? ------------
    if not path.exists():
        result["status"]="FAIL"
        result["detail"]= f"file not found: {spec['file']}"
        log.error(f"C1 {name}: {result['detail']}")
        return [], result


    with open(path,"r",newline="") as f:
        reader = csv.DictReader(f)
        found = reader.fieldnames or []
        rows = list(reader)



    # ------- does it have the columns we expect? --------
    #[c for c in expected if c not in found] walks the expected list andk keeps only the ones
    # the file does not have. 
    missing = [c for c in expected if c not in found]
    unexpected = [c for c in found if c not in expected]

    problems = []
    if missing:
        problems.append(f"missing columns {missing}")
    if unexpected:
        problems.append(f"unexpected columns {unexpected}")
    if not rows:
        problems.append("header but no rows")


    if problems:
        result["status"] = "FAIL"
        result["detail"] = "; ".join(problems)
        log.error(f"C1 {name}: {result['detail']}")
    else:
        result["detail"] = f"{len(rows)} rows, {len(found)} columns"
        log.info(f"C1 {name}: PASS - {result['detail']}")

    return rows,result



def main():
    """Read every extract named in settings.yml and report control C1. """
    run_id = new_run_id()
    log = setup_logger(run_id)
    settings = load_settings()

    log.info("Ingest started.")

    results =[]
    for name in settings["extracts"]:
        rows, result = read_extract(name,settings,log)
        results.append(result)

    failed = [r for r in results if r["status"]=="FAIL"]

    if failed:
        log.error(f"C1 failed on {len(failed)} of {len(results)} extracts. Stopping.")
        sys.exit(1)

    log.info(f"Ingest finished. {len(results)} extracts passed C1.")




if __name__ == "__main__":
    main()




    