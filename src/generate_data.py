"""Generate the ERP-style extracts the pipeline reads."""
"""Chunk 3a: the budget extract -- the modelled expectation, one row per asset, per period, per cost type.
 Acutals with planted anomalies come next"""

import csv

import numpy as np
import yaml 

from src.config import PROJECT_ROOT

from src.model import (
    load_assumptions,
    load_asset_register,
    expected_tangible,
    expected_intangible,
)

RAW_DIR = PROJECT_ROOT/"data"/"raw"
PRODUCER_PATH = PROJECT_ROOT/"config"/"producer.yml"


def load_producer_config():
    """Read the generator's private config.(producer.yml).  modle.py must never call this."""
    with open(PRODUCER_PATH,"r") as f:
        return yaml.safe_load(f)
    


def anomaly_multipliers(row, anomalies):
    """How much the planted problems change this row's volumn and its price.
    
    Returns two numbers, both 1.0 with nothing applies.
    
    Several anomalies can land on the same row, and then they mutiply together
    -- which is what really happens. A saw that is failing early is also paying the contractor's new rate.
    """

    quantity_multiplier = 1.0
    price_multiplier = 1.0

    for rule in anomalies: 
        # .get("assets") hands back None when the key is not in the rule at all. 
        # An absent key means "applies to everything", 

        if rule.get("assets") and row["asset_id"] not in rule["assets"]:
            continue
        if rule.get("periods") and row["period"] not in rule["periods"]:
            continue
        if rule.get("cost_types") and row["cost_type"] not in rule["cost_types"]:
            continue

        # the 2nd argument to .get() is what to use when the key is missing. 
        # 1.0 means "no effect", so a rule that only changes volume leaves price along. 
        quantity_multiplier *= rule.get("quantity_multiplier", 1.0)
        price_multiplier *= rule.get("price_multiplier", 1.0)

    return quantity_multiplier,price_multiplier

def print_planted(anomalies):
    """List what was planted. Generator-side only - for the README at M6."""
    print("Planted anomalies (the analyser is never told any of this):")
    for rule in anomalies:
        periods = rule.get("periods",["all periods"])
        span = periods[0] if len(periods) == 1 else f"{periods[0]}-{periods[-1]}"

        effects =[]
        if "quantity_multiplier" in rule:
            effects.append(f"volumn x{rule['quantity_multiplier']}")
        if "price_multiplier" in rule: 
            effects.append(f"price x{rule['price_multiplier']}")

        scope = ", ".join(rule.get("assets",["whole fleet"]))
        print(f" {rule['id']:<5}{span:<20}{' + '.join(effects):<18}{scope}")
    print()


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


def build_actual_rows(budget_rows,pro_cfg,rng):
    """Turn each budget row into what actually happened. 
    One budget row in, one actual row out, same grain -- so every expectation has exactly one 
    outcome to be mearured against. How much a line varies depends on what kind of sepnd it is: 

        LICENSE -- a acontract. Fixed seats at a fixed fee. No variations. 
        PM (Preventative Maintenance) -- scheduled. The count isthe plan; only the cost varies.
        CM (Corrective Maintenance) -- unscheduled. Count and cost both vary. 
        SUPPORT -- unscheduled. Count and cost both vary. 

    That distinction is the model, not a shortcut: scheduled work varies in price, unscheduled work varies 
    in price and volume.
    """
    noise = pro_cfg["noise"]
    anomalies = pro_cfg.get("anomalies",[])
    rows = []

    for b in budget_rows:
        qty_mult, price_mult = anomaly_multipliers(b,anomalies)

        if b["cost_type"]=="LICENSE":
            # a license is a contract. Nothing to draw. 
            quantity = b["quantity"]
            amount  = b["amount"]

        else:
            # Standard cost per unit, recovered from the budget row itself.
            # a quantity = 0 would crash.
            standard_cost=b["amount"]/b["quantity"] if b["quantity"] else 0.0
            expected_count = b["quantity"]*qty_mult

            if b["cost_type"] =="PM":
                # scheduled work: so no draw - but it must stay whole services. 
                quantity = float(round(expected_count))
            else:
                # Poisson distrution - Poisson draws a a whole number of events given an average rate. 
                # This is why actuals need their own shape and cannot just be budget multiplied by a percentage.
                quantity = float(rng.poisson(expected_count))

            multiplier = max(
                noise["price_floor"], rng.normal(1.0,noise["price_spread"])
            )
            amount = quantity * standard_cost * multiplier * price_mult

        rows.append(
            {
                "period":b["period"],
                "asset_id":b["asset_id"],
                "family": b["family"],
                "cost_type": b["cost_type"],
                "quantity": round(quantity,2),
                "uom": b["uom"],
                "amount":round(amount,2),
            }
        )

    return rows



def write_csv(path,rows):
    """Write a list of dictionaries to a CSV file."""
    # create a data/raw if it does not exist.
    path.parent.mkdir(parents=True,exist_ok=True)

    with open(path,"w",newline="") as f:
        writer = csv.DictWriter(f,fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)


def report_by_period(assumptions,budget_rows,actual_rows):
    """Budget against actual for every period -- the first sight of variance.
    Sign convention: variance = actual - budget. 
    These are expenses, so a POSITIVE variance is an overspend, and unfavourable.
    """
    print(f"{'PERIOD':<10}{'BUDGET':>14}{'ACTUAL':>14}{'VARIANCE':>14}{'%':>8}")
    print("-"*60)

    for period in assumptions["calendar"]["periods"]:
        budget = sum(r["amount"] for r in budget_rows if r["period"] == period)
        actual = sum(r["amount"] for r in actual_rows if r["period"]== period)
        variance = actual - budget
        percent = (variance/budget*100) if budget else 0.0

        print(
            f"{period:<10}{budget:>14,.0f}{actual:>14,.0f}"
            f"{variance:>14,.0f}{percent:>7.1f}%"
        )

    budget_total = sum(r["amount"] for r in budget_rows)
    actual_total = sum(r["amount"] for r in actual_rows)
    variance_total = actual_total - budget_total
    percent_total = (variance_total/budget_total*100) if budget_total else 0.0

    print("-"*60)
    print(
        f"{'TOTAL':<10}{budget_total:>14,.0f}{actual_total:>14,.0f}"
        f"{variance_total:>14,.0f}{percent_total:>7.1f}%"
    )


def main():
    """Build every extract and write it to data/raw."""
    assumptions =load_assumptions()
    register = load_asset_register()
    producer_cfg = load_producer_config()
    rng =np.random.default_rng(producer_cfg["seed"])

    budget_rows =build_budget_rows(assumptions,register)
    budget_path = RAW_DIR/"budget.csv"
    write_csv(budget_path,budget_rows)

    actual_rows = build_actual_rows(budget_rows,producer_cfg,rng)
    actual_path = RAW_DIR/"actual.csv"
    write_csv(actual_path,actual_rows)

    print_planted(producer_cfg.get("anomalies",[]))
    print(f"Wrote {len(budget_rows)} budget rows and {len(actual_rows)} actual rows")
    print()
    report_by_period(assumptions,budget_rows,actual_rows)



if __name__=="__main__":
    main()