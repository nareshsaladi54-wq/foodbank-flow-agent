"""Deterministic tests - no model, no network."""
import copy
import json
from datetime import date

from foodbankflow import core

TODAY = date(2026, 9, 1)


def test_apply_donations_merges_and_appends():
    inv = core.load_inventory()
    merged = core.apply_donations(inv, core.load_intake())
    beans = next(i for i in merged if i["sku"] == "beans-can")
    assert beans["units"] == 6 + 24           # seed 6 + Hillside 24
    assert any(i["sku"] == "zucchini" for i in merged)  # new sku appended


def test_donation_keeps_sooner_expiry():
    inv = [{"sku": "x", "name": "X", "category": "grain", "units": 1,
            "perishable": False, "expiry": "2027-01-01"}]
    merged = core.apply_donations(inv, [{"donor": "d", "items": [
        {"sku": "x", "name": "X", "category": "grain", "units": 1,
         "perishable": False, "expiry": "2026-10-01"}]}])
    assert merged[0]["expiry"] == "2026-10-01"


def test_expiring_soon_flags_bread_eggs_milk():
    merged = core.apply_donations(core.load_inventory(), core.load_intake())
    soon = {e["sku"] for e in core.expiring_soon(merged, TODAY, 5)}
    assert {"bread-loaf", "eggs-dozen", "milk-shelf"}.issubset(soon)
    assert "rice-5lb" not in soon


def test_dairy_is_a_shortage_even_after_donations():
    merged = core.apply_donations(core.load_inventory(), core.load_intake())
    sh = core.shortages(merged, core.load_families())
    cats = {d["category"] for d in sh["deficits"]}
    assert "dairy" in cats


def test_produce_is_surplus_after_donations():
    merged = core.apply_donations(core.load_inventory(), core.load_intake())
    sh = core.shortages(merged, core.load_families())
    assert any(s["category"] == "produce" for s in sh["surplus"])


def test_gluten_free_family_gets_no_bread_or_pasta():
    fam = next(f for f in core.load_families()["families"] if f["id"] == "f-03")
    merged = core.apply_donations(core.load_inventory(), core.load_intake())
    pl = core.build_pick_list(fam, copy.deepcopy(merged), TODAY)
    skus = {p["sku"] for p in pl["picks"]}
    assert "bread-loaf" not in skus and "pasta-1lb" not in skus


def test_pick_list_respects_household_cap():
    fam = next(f for f in core.load_families()["families"] if f["id"] == "f-06")  # size 1
    merged = core.apply_donations(core.load_inventory(), core.load_intake())
    pl = core.build_pick_list(fam, copy.deepcopy(merged), TODAY)
    grain = sum(p["units"] for p in pl["picks"] if p["category"] == "grain")
    assert grain <= 1  # 1.0 per person * 1 person


def test_pick_list_prefers_expiring_items():
    fam = next(f for f in core.load_families()["families"] if f["id"] == "f-02")
    merged = core.apply_donations(core.load_inventory(), core.load_intake())
    pl = core.build_pick_list(fam, copy.deepcopy(merged), TODAY)
    dairy = [p for p in pl["picks"] if p["category"] == "dairy"]
    # eggs (expiry 09-04) should be taken before shelf milk (09-06)
    if len(dairy) >= 1:
        assert dairy[0]["sku"] == "eggs-dozen"


def test_plan_distribution_runs_and_reports():
    plan = core.plan_distribution(TODAY)
    assert len(plan["pick_lists"]) == 6
    assert "dairy" in {d["category"] for d in plan["shortages"]["deficits"]}


def test_community_ask_names_the_dairy_gap():
    text = core.community_ask(TODAY)
    assert "dairy" in text and "WE NEED" in text


def test_append_intake_item_queues_a_new_donation(tmp_path):
    scratch = tmp_path / "donations_intake.json"
    scratch.write_text(json.dumps({"queue": list(core.load_intake())}))
    items = [{"name": "Canned corn", "sku": "corn-can", "category": "produce",
              "units": 8, "perishable": False, "expiry": "2027-01-01"}]
    before = len(core.load_intake())

    queue = core.append_intake_item("Photo Donor", items, path=scratch)

    assert len(queue) == before + 1
    assert queue[-1] == {"donor": "Photo Donor", "logged": False, "items": items}
    # the real seed file is untouched
    assert len(core.load_intake()) == before
    # and the write round-trips through disk
    assert json.loads(scratch.read_text())["queue"][-1]["donor"] == "Photo Donor"
