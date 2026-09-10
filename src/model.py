"""The driver model: turn the assumptions and the asset register into expected volumns and costs."""

import csv
import yaml

from src.config import PROJECT_ROOT

ASSUMPTIONS_PATH = PROJECT_ROOT / "config"/"assumptions.yml"
REGISTER_PATH = PROJECT_ROOT / "config"/"asset_register.csv"

def load_assumptions():
    """Read assumptions .yml file and return it as a dictionary."""
    with open(ASSUMPTIONS_PATH, "r") as f:
        return yaml.safe_load(f) 

def load_asset_register():
    """Read asset register .csv file and return it as a list of dictionaries."""
    with open(REGISTER_PATH, "r") as f:
        reader = csv.DictReader(f)
        register = list(reader)

    # LEARN: the collection is "register", the one item is "asset". Two words
    #        that look nothing alike, so a typo in either one is obvious.
    for asset in register:
        asset["acquired_year"] = int(asset["acquired_year"])
        asset["capitalized_cost"] = float(asset["capitalized_cost"])
        asset["seats"]=int(asset["seats"]) if asset["seats"] else None

    return register

def parse_period(period):
    """Split a period lable like '2026Q3' into (year,quarter) as integers."""
    year_text,quarter_text = period.split("Q")
    return int(year_text),int(quarter_text)

def asset_age(acquired_year,period):
    """Age of an asset in whole years, as at the given period"""
    year,_ = parse_period(period)
    return year - acquired_year

def expected_tangible(asset,period,assumptions):
    """Expected work-order volumns and costs for one machine in one quarter"""
    t=assumptions["tangible"]
    cls = t["classes"][asset["asset_class"]]

    #driver 2, PM volumn comes from usage, not age. 
    pm_orders =(
        t["servicing"]["operating_hours_per_machine_per_quarter"]/
        t["servicing"]["pm_service_interval_hours"]
    )

    #driver 1, CM volumn rises with age, once past the grace period.
    age = asset_age(asset["acquired_year"],period)
    years_past_grace = max(0,age-t["failure"]["grace_years"])
    age_factor = 1+t["failure"]["age_sensitivity_per_year"]*years_past_grace
    cm_orders = t["failure"]["cm_base_rate_per_machine_per_quarter"]*age_factor

    pm_cost = pm_orders * cls["pm_cost_per_order"]
    cm_cost = cm_orders * cls["cm_cost_per_order"]

    return {
        "pm_orders": pm_orders,
        "cm_orders": cm_orders,
        "pm_cost": pm_cost,
        "cm_cost": cm_cost,
        "total_cost": pm_cost + cm_cost,
    }


def expected_intangible(asset,period,assumptions):
    """Expected licence and support costs for one software product in one quarter."""
    i = assumptions["intangible"]
    months = assumptions["calendar"]["months_per_period"]

    # Driver 5, licence fees. the anniversary uplift applies once a year.
    # counted from the first year in the reporting calendar: the fee in the register is today's rate
    # not the rate at acquisition. 
    first_year,_=parse_period(assumptions["calendar"]["periods"][0])
    year,_= parse_period(period)
    years_into_window = year -first_year

    base_fee = i["licensing"]["fee_per_seat_per_month"]
    fee = base_fee * (1+i["licensing"]["uplift_at_anniversary"])** years_into_window

    license_cost = asset["seats"]* fee * months

    # Driver 7,  remote/on-site delivery blend
    # support hours cost less delivered remotely. the Plan assumes a fixed share is remote, 
    # so we blend the two multipliers into one number. 
    delivery = i["service_rates"]["delivery_multiplier"]
    remote_share = i["service_rates"]["planned_remote_share"]
    blended_multiplier = (remote_share * delivery["remote"]+(1-remote_share)*delivery["onsite"])

    # Driver 6, support incidents
    # Three incident types, each with its own frequency, hours and skill level.
    incident_cost=0.0
    incident_counts ={}

    for incident_type,spec in i["incidents"].items():
        rate_per_hour = i["service_rates"]["rate_per_hour"][spec["expertise"]]

        cost_each= spec["hours_per_incident"] * rate_per_hour * blended_multiplier
        expected_count = spec["rate_per_instance_per_quarter"]

        incident_counts[incident_type]=expected_count
        incident_cost += expected_count * cost_each

    return {
        "license_cost":license_cost,
        "incident_counts": incident_counts,
        "incident_cost": incident_cost,
        "total_cost": license_cost + incident_cost,
    }



if __name__=="__main__":
    assumptions = load_assumptions()
    register = load_asset_register()
    period = "2026Q3"

    print(f"Expected maintenance cost by machine, {period}")
    print(f"{'asset':<12}{'class':<26}{'age':>4}{'PM':>6}{'CM':>6}{'cost':>12}")
    print("_"*72)

    total = 0.0
    for asset in register:
        if asset["family"]!= "tangible":
            continue

        e = expected_tangible(asset,period,assumptions)
        age = asset_age(asset["acquired_year"],period)
        total += e["total_cost"]

        print(
            f"{asset['asset_id']:<12}{asset['asset_class']:<26}{age:>4}"
            f"{e['pm_orders']:>6.1f}{e['cm_orders']:>6.2f}{e['total_cost']:>12,.0f}"
        )

    print("_"*72)
    print(f"{'Total':<54}{total:>12,.0f}")


    print()
    print(f"{'SOFTWARE':<12}{'SEATS':>6}{'LICENSE':>12}{'SUPPORT':>12}{'TOTAL':>12}")
    print("_" * 56)

    software_total = 0.0
    for asset in register:
        if asset["family"] != "intangible":
            continue

        result = expected_intangible(asset,period,assumptions)
        software_total += result["total_cost"]

        print(
            f"{asset['asset_id']:<12}"
            f"{asset['seats']:>6}"
            f"{result['license_cost']:>12,.0f}"
            f"{result['incident_cost']:>12,.0f}"
            f"{result['total_cost']:>12,.0f}"
        )

    print("_" * 56)
    print(f"{'TOTAL':<42}{software_total:>12,.0f}")


