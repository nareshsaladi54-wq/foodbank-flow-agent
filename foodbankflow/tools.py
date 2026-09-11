"""Strands tools for FoodBankFlow. Thin wrappers over the deterministic core.

Data access (inventory, families, intake queue) goes through data_client.py,
an MCP client - not a direct file read. core.py's own load_* stay in place
and unchanged (run_demo.py and tests/ use those directly), so the offline
demo and the deterministic test suite stay network-free; only the live
agent's tools reach data through MCP. See data_client.py for how to point
this at a real backend instead of the bundled demo MCP server.

Design note: every report works on 'inventory + logged donations', so tools
are idempotent and the demo is repeatable. log_donations reports what
logging the queue adds; a real deployment would persist to a warehouse
table here."""
from __future__ import annotations

import copy
from datetime import date

from strands import tool

from . import core, data_client, memory

TODAY = date(2026, 9, 1)


def _current_inventory() -> list[dict]:
    """Inventory with the intake queue's donations merged in."""
    return core.apply_donations(data_client.get_inventory(), data_client.get_intake_queue())


@tool
def get_inventory() -> list[dict]:
    """Current stock (donations included): item, category, units, perishable, expiry."""
    return _current_inventory()


@tool
def list_families() -> dict:
    """Registered families (household size, pickup day, dietary constraints) and the allocation policy."""
    return data_client.get_families()


@tool
def intake_queue() -> list[dict]:
    """Donations from the photo/vision step waiting to be logged: donor + line items."""
    return data_client.get_intake_queue()


def queue_photo_intake(image_base64: str, media_type: str = "image/jpeg", donor: str = "") -> dict:
    """The vision step's actual work: decode a photo, read it, queue its line
    items for log_donations. Plain function (not @tool) so callers can run it
    directly in Python - agentcore_app.py does, for any payload carrying
    image_base64, rather than asking the model to retype a many-KB base64
    blob as a tool-call argument (slow, and prone to stalling the stream).
    intake_photo below wraps this for the rarer case where the model itself
    already has the base64 in hand (e.g. a prior tool result) and decides to
    call it."""
    import base64

    from . import vision

    parsed = vision.extract_donation(base64.b64decode(image_base64), media_type)
    if not parsed["items"]:
        return {"error": "couldn't identify any items in that photo"}
    donor_name = donor.strip() or parsed["donor"] or "Unknown donor"
    data_client.add_intake_donation(donor_name, parsed["items"])
    return {"donor": donor_name, "items_queued": parsed["items"]}


@tool
def intake_photo(image_base64: str, media_type: str = "image/jpeg", donor: str = "") -> dict:
    """The vision step: read a photo of a donation drop-off and queue its line
    items for log_donations. `image_base64` is the photo, base64-encoded;
    `media_type` is its MIME type (image/jpeg, image/png, ...); pass `donor`
    to override the model's guess at who dropped it off. Prefer having the
    caller queue the photo before the agent runs (agentcore_app.py's
    image_base64 payload field does this) rather than pasting the base64
    into a prompt for the model to relay here."""
    return queue_photo_intake(image_base64, media_type, donor)


@tool
def log_donations() -> dict:
    """Log the intake queue into inventory. Returns the donors logged and the
    per-category unit increase."""
    before, after = {}, {}
    for i in data_client.get_inventory():
        before[i["category"]] = before.get(i["category"], 0) + i["units"]
    for i in _current_inventory():
        after[i["category"]] = after.get(i["category"], 0) + i["units"]
    return {
        "logged": [d["donor"] for d in data_client.get_intake_queue()],
        "category_increase": {c: after.get(c, 0) - before.get(c, 0)
                              for c in after if after.get(c, 0) != before.get(c, 0)},
        "new_total_units": sum(after.values()),
    }


@tool
def expiring_report(days: int = 5) -> list[dict]:
    """Items expiring within `days` (or already expired) - hand these out or redistribute first."""
    return core.expiring_soon(_current_inventory(), TODAY, days)


@tool
def shortage_report() -> dict:
    """Projected demand vs on-hand by category for this week's registered families: deficits and surplus."""
    return core.shortages(_current_inventory(), data_client.get_families())


@tool
def family_pick_list(family_id: str) -> dict:
    """A fair, constraint-aware pick list for one family (expiring items first)."""
    fam = next((f for f in data_client.get_families()["families"] if f["id"] == family_id), None)
    if not fam:
        return {"error": f"no family {family_id!r}"}
    return core.build_pick_list(fam, copy.deepcopy(_current_inventory()), TODAY)


@tool
def plan_week() -> dict:
    """Pick lists for every family for their pickup day, plus expiring items,
    shortages, families we can't fully stock, and leftover stock."""
    return core.plan_distribution(TODAY, with_donations=False,
                                   families=data_client.get_families(), inventory=_current_inventory())


@tool
def draft_community_ask() -> str:
    """Draft the public 'what we need / what to use this week' message (does not post)."""
    return core.community_ask(TODAY, families=data_client.get_families(), inventory=_current_inventory())


@tool
def remember_note(actor_id: str, note: str) -> str:
    """Save a standing ops note (recurring donor, a family's situation, what an ask brought in)."""
    return memory.remember(actor_id, note)


@tool
def recall_notes(actor_id: str, about: str = "") -> list[str]:
    """Recall standing ops notes, optionally filtered by topic."""
    return memory.recall(actor_id, about)


TOOLS = [get_inventory, list_families, intake_queue, intake_photo, log_donations,
         expiring_report, shortage_report, family_pick_list, plan_week,
         draft_community_ask, remember_note, recall_notes]
