"""Tests for the anomaly rules in generate_data.

A rule that lists assets applies only to those assets. A rule with no asset list applies to everything. 
A misspelled key destroyed that distinction in September -  .get("assets") came back empty, so every
rule looked like a whole-fleet fule, and the variance came out at +175% with no error anywhere.

The fourth test below is the one that would have failed immediately.
"""

from src.generate_data import rule_matches

# A rule naming three machines, four quarters, one kind of cost.  Same shape as A1.
A1 = {
    "id":"A1",
    "assets": ["ROUTER-01", "ROUTER-02", "ROUTER-03"],
    "periods": ["2026Q1", "2026Q2", "2026Q3", "2026Q4"],
    "cost_types": ["CM"],
}

def row(asset_id, period, cost_type):
    """The smallest row the rule needs to look at - not a real extract row."""
    return{"asset_id": asset_id, "period": period, "cost_type": cost_type}


def test_matches_a_row_the_rule_names():
    assert rule_matches(A1, row("ROUTER-01", "2026Q2", "CM"))


def test_ignores_a_period_the_rule_does_not_name():
    assert not rule_matches(A1, row("ROUTER-01", "2025Q2", "CM"))


def test_ignores_a_cost_type_the_rule_does_not_name():
    assert not rule_matches(A1, row("ROUTER-1", "2026Q2","PM"))


def test_ignores_an_asset_the_rule_does_not_name():
    # The one that matters. With a misspelled key this comes back True.
    assert not rule_matches(A1, row("CNC-01","2026Q2","CM"))


def test_a_rule_with_no_asset_list_applies_to_every_asset():
    fleet_wide = {"id": "A3", "periods": ["2026Q2"], "cost_types":["CM"]}
    assert rule_matches(fleet_wide, row("SAW-04", "2026Q2", "CM"))