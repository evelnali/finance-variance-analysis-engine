"""Generate the ERP-style extracts the pipeline reads."""
"""Chunk 3a: the budget extract -- the modelled expectation, one row per asset, per period, per cost type.
 Acutals with planted anomalies come next"""

import csv

from src.config import PROJECT_ROOT

from src.model import (
    load_assumptions,
    load_asset_register,
    expected_tangible,
    expected_intangible,
)

RAW_DIR = PROJECT_ROOT/"data"/"raw"


def make_row(period,asset,cost_type,quantity,uom,amount):
    """Build one extract row as a dictionary.
    quantity and uom (unit of measurment) travel together: a number means nothing until you know that it counts.
    work orders, seats and incidents all land in the same column, and uom is what keeps them from being added together by mistake."""

    return{
        "period":period,
        "asset_id":asset["asset_id"],
        "family":asset["family"],
        "cost_type":cost_type,
        "quantity":round(quantity,2),
        "uom":uom,
        "amount":round(amount,2),
    }

def build_budget_rows(assumptions,register):
    """Run the driver model over every asset in every period."""
    rows=[]

    for period in assumptions["calendar"]["periods"]:
        for asset in register:
            if asset["family"]=="tangible":
                e = expected_tangible(asset,period,assumptions)
                # two rows per machine -- PM and CM
                rows.append(
                    make_row(period,asset,"PM",e["pm_orders"],"WORK_ORDER",e["pm_cost"])
                )
                rows.append(
                    make_row(period,asset,"CM",e["cm_orders"],"WORK_ORDER",e["cm_cost"])
                )
            else:
                e = expected_intangible(asset,period,assumptions)

                incidents = sum(e["incident_counts"].values())

                rows.append(
                    make_row(period,asset,"LICENSE",asset["seats"],"SEAT",e["license_cost"])
                )
                rows.append(
                    make_row(period,asset,"SUPPORT",incidents,"INCIDENT",e["incident_cost"])
                )
    return rows



def write_csv(path,rows):
    """Write a list of dictionaries to a CSV file."""
    path.parent.mkdir(parents=True,exist_ok=True)

    with open(path,"w",newline="") as f:
        writer = csv.DictWriter(f,fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)



def main():
    """Build every extract and write it to data/raw."""
    assumptions =load_assumptions()
    register = load_asset_register()

    budget_rows =build_budget_rows(assumptions,register)
    budget_path = RAW_DIR/"budget.csv"
    write_csv(budget_path,budget_rows)

    total = sum(r["amount"] for r in budget_rows)

    print()
    for period in assumptions["calendar"]["periods"]:
        period_total = sum(r["amount"] for r in budget_rows if r["period"]==period)
        print(f"{period:<10}{period_total:>14,.0f}") 

    print(f"Wrote {len(budget_rows)} rows to {budget_path}")
    print(f"Total expected cost, all periods: {total:,.0f}")


if __name__=="__main__":
    main()