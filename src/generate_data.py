"""Generate the ERP-style extracts the pipeline reads.

Two extracts, same grain: budget.csv is the modelled expectation, actual.csv
is what happened - noise, plus the problems planted in producer.yml. One
budget row and one actual row for every asset, period and cost type, so every
expectation has exactly one outcome to be measured against.

Nothing in src/model.py may read producer.yml. That separation is what makes
the variance analysis a test rather than a mirror.
"""

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
    

# ---- the Planted anomalies ----------
def rule_matches(rule,row):
    """Does this rule apply to this row? 
    An absent key means "applies to everything", so a rule only fails to match when the key 
    IS there and this row is not named in it. 
    That is what lets A3 and A4 hit the whole fleet without listing all 16 assets.

    Defined once and used in two places - by anomaly_multipliers when writting the data, and
    by check_planted wen proving it landed. If the test lived in both, the two could drift apart. 
    """
    if rule.get("assets") and row["asset_id"] not in rule["assets"]:
        return False
    if rule.get("periods") and row["period"] not in rule["periods"]:
        return False
    if rule.get("cost_types") and row["cost_type"] not in rule["cost_types"]:
        return False
    return True



def anomaly_multipliers(row, anomalies):
    """How much the planted problems change this row's volumn and its price.
    
    Returns two numbers, both 1.0 with nothing applies.
    
    Several anomalies can land on the same row, and then they mutiply together
    -- which is what really happens. A saw that is failing early is also paying the contractor's new rate.
    """

    quantity_multiplier = 1.0
    price_multiplier = 1.0
    for rule in anomalies:
        if not rule_matches(rule,row):
            continue

        # the 2nd argument to .get() is what to use when the key is missing. 
        # 1.0 means "no effect".

        quantity_multiplier *= rule.get("quantity_multiplier",1.0)
        price_multiplier *= rule.get("price_multiplier",1.0)

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

def check_planted(budget_rows,actual_rows,anomalies):
    """Prove each rule landed on the rows it was aimed at.
    
    The generator's own time-out. Without it, "the anomalies are planted" is a claim;
    with it, it is a figure printed on every run.
    
    A4a should tie exactly, because scheduled servicing is not drawn at random.
    The drawn ones land near expectation, not on it. A price-only rule must show expected equal
    to budget - if its actual has moved, prices and volume are getting mixed up.
    """

    print("Planting check - work orders on the rows each rule targets:")
    print(f"{'RULE':<6}{'BUDGET':>11}{'EXPECTED':>11}{'ACTUAL':>11}")

    for rule in anomalies:
        # [x for x in things if ...] builds a new list of just ones that pass the test
        budget_hit = [r for r in budget_rows if rule_matches(rule,r)]
        actual_hit = [r for r in actual_rows if rule_matches(rule,r)]

        budget_qty = sum(float(r["quantity"]) for r in budget_hit)
        actual_qty = sum(float(r["quantity"]) for r in actual_hit)
        # Expected has to account for EVERY rule that touches these rows, not
        # just this one. A3's rows are also hit by A1, A2 and A4b, so judging
        # A3 against its own multiplier alone makes a correct result look wrong.
        expected_qty = sum(
            float(r["quantity"]) * anomaly_multipliers(r, anomalies)[0]
            for r in budget_hit
        )

        print(
            f"  {rule['id']:<6}{budget_qty:>9.1f}"
            f"{expected_qty:>10.1f}{actual_qty:>9.0f}"
        )


# ----------------------------------------------------------------------------------
# Building the two extracts.
# ---------------------------------------------------------------------------------

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

            # An anomaly changes the RATE at which things happen, so it is
            # applied to the expected count BEFORE the draw - never to the
            # drawn number afterwards. Raising 1.04 to 1.66 and then drawing
            # gives whole work orders with the right spread; drawing first and
            # multiplying after would give 1.6 work orders, which do not
            # exist, and would hide how lumpy the result should be.
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




# ------------------------------------------------------
# Outputs
# ------------------------------------------------------

def write_csv(path,rows):
    """Write a list of dictionaries to a CSV file."""
    # create a data/raw if it does not exist.
    path.parent.mkdir(parents=True,exist_ok=True)

    # newline="" is required when writing CSV. without it would get a blank line
    # between every row on some systems.
    with open(path,"w",newline="") as f:   
        writer = csv.DictWriter(f,fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)


def report_by_period(assumptions,budget_rows,actual_rows):
    """Budget against actual for every period -- the first sight of variance.
    Sign convention: variance = actual - budget. 
    These are expenses, so a POSITIVE variance is an overspend, and unfavourable. vice versa.
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
    anomalies = producer_cfg.get("anomalies",[])

    budget_rows =build_budget_rows(assumptions,register)
    budget_path = RAW_DIR/"budget.csv"
    write_csv(budget_path,budget_rows)

    actual_rows = build_actual_rows(budget_rows,producer_cfg,rng)
    actual_path = RAW_DIR/"actual.csv"
    write_csv(actual_path,actual_rows)

    print_planted(anomalies)
    check_planted(budget_rows,actual_rows,anomalies)

    print(f"Wrote {len(budget_rows)} budget rows and {len(actual_rows)} actual rows")
    print()
    report_by_period(assumptions,budget_rows,actual_rows)



if __name__=="__main__":
    main()