"""Deterministic tests for the vision step's JSON parsing - no model, no network.
extract_donation() itself makes a live Bedrock call and isn't exercised here."""
import json

from foodbankflow import vision


def test_parse_response_extracts_items():
    reply = json.dumps({
        "donor": "Hillside Grocery",
        "items": [
            {"name": "Rice 5lb", "sku": "rice-5lb", "category": "grain",
             "units": 12, "perishable": False, "expiry": "2027-06-01"},
        ],
    })
    parsed = vision._parse_response(reply)
    assert parsed["donor"] == "Hillside Grocery"
    assert parsed["items"] == [{"name": "Rice 5lb", "sku": "rice-5lb", "category": "grain",
                                 "units": 12, "perishable": False, "expiry": "2027-06-01"}]


def test_parse_response_strips_markdown_fence():
    reply = "```json\n" + json.dumps({"donor": "", "items": []}) + "\n```"
    assert vision._parse_response(reply) == {"donor": "", "items": []}


def test_parse_response_drops_items_missing_name_or_units():
    reply = json.dumps({"donor": "", "items": [
        {"name": "", "units": 5, "category": "grain"},
        {"name": "Beans", "units": 0, "category": "protein"},
        {"name": "Bananas", "units": 3, "category": "produce"},
    ]})
    parsed = vision._parse_response(reply)
    assert [i["name"] for i in parsed["items"]] == ["Bananas"]


def test_parse_response_fills_defaults_and_rejects_bad_category():
    reply = json.dumps({"donor": "", "items": [
        {"name": "Mystery Box", "units": "4", "category": "electronics"},
    ]})
    item = vision._parse_response(reply)["items"][0]
    assert item["sku"] == "mystery-box"          # derived from name
    assert item["category"] == "grain"           # invalid category falls back
    assert item["units"] == 4                    # coerced from string
    assert item["perishable"] is False
    assert item["expiry"] == "2027-01-01"
