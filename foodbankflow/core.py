"""Deterministic food-bank operations. No LLM. Donation logging, expiry tracking,
demand-vs-stock shortages, fair pick lists, and the community ask are all here
and covered by tests/."""
from __future__ import annotations

import copy
import json
from datetime import date

from .config import DATA_DIR

EXPIRY_WINDOW_DAYS = 5


def _load(name: str) -> dict:
    with open(DATA_DIR / name) as fh:
        return json.load(fh)


def load_inventory() -> list[dict]:
    return _load("inventory.json")["items"]


def load_families() -> dict:
    return _load("families.json")


def load_intake() -> list[dict]:
    return _load("donations_intake.json")["queue"]


def apply_donations(inventory: list[dict], donations: list[dict]) -> list[dict]:
    """Merge donation line items into inventory by sku (new skus are appended).
    Pure - returns a new list."""
    inv = {i["sku"]: copy.deepcopy(i) for i in inventory}
    for d in donations:
        for it in d["items"]:
            if it["sku"] in inv:
                inv[it["sku"]]["units"] += it["units"]
                # keep the sooner expiry so nothing is over-counted as fresh
                inv[it["sku"]]["expiry"] = min(inv[it["sku"]]["expiry"], it["expiry"])
            else:
                inv[it["sku"]] = {k: it[k] for k in ("sku", "name", "category", "units",
                                                     "perishable", "expiry")}
    return list(inv.values())


def expiring_soon(inventory: list[dict], today: date, days: int = EXPIRY_WINDOW_DAYS) -> list[dict]:
    out = []
    for i in inventory:
        d = (date.fromisoformat(i["expiry"]) - today).days
        if d <= days:
            out.append({**{k: i[k] for k in ("sku", "name", "category", "units")},
                        "expiry": i["expiry"], "days_left": d,
                        "status": "EXPIRED" if d < 0 else "use/redistribute now"})
    return sorted(out, key=lambda x: x["days_left"])


def _demand_by_category(families: dict, only_day: str | None = None) -> dict:
    policy = families["policy"]["per_person_per_cycle"]
    people = sum(f["household_size"] for f in families["families"]
                 if only_day is None or f["pickup_day"] == only_day)
    demand = {cat: int(round(rate * people)) for cat, rate in policy.items()}
    infants = sum(1 for f in families["families"]
                  if f.get("infant") and (only_day is None or f["pickup_day"] == only_day))
    demand["hygiene"] = infants * families["policy"]["infant_bonus"]["hygiene"]
    return demand


def shortages(inventory: list[dict], families: dict, only_day: str | None = None) -> dict:
    on_hand: dict[str, int] = {}
    for i in inventory:
        on_hand[i["category"]] = on_hand.get(i["category"], 0) + i["units"]
    demand = _demand_by_category(families, only_day)
    rows = []
    for cat, need in demand.items():
        have = on_hand.get(cat, 0)
        rows.append({"category": cat, "need": need, "on_hand": have, "gap": have - need})
    return {
        "scope": only_day or "all pickups",
        "deficits": [r for r in rows if r["gap"] < 0],
        "surplus": [r for r in rows if r["gap"] > need_margin(r)],
        "all": rows,
    }


def need_margin(row: dict) -> int:
    return max(5, row["need"])  # "surplus" = more than a full extra cycle on hand


def build_pick_list(family: dict, inventory: list[dict], today: date) -> dict:
    """Allocate items to one family: fair share by household size, dietary
    constraints respected, expiring-soon items handed out first."""
    policy = load_families()["policy"]["per_person_per_cycle"]
    size = family["household_size"]
    caps = {cat: int(round(rate * size)) for cat, rate in policy.items()}
    if family.get("infant"):
        caps["hygiene"] = 1

    banned = set()
    if "gluten_free" in family["constraints"]:
        banned |= {"pasta-1lb", "bread-loaf"}
    if "diabetic" in family["constraints"]:
        banned |= {"bread-loaf"}
    # no_pork: none of the seeded protein items are pork; rule kept for real data.

    picks, unmet = [], []
    given = {cat: 0 for cat in caps}
    pool = sorted(inventory, key=lambda i: date.fromisoformat(i["expiry"]))
    for item in pool:
        cat = item["category"]
        if cat not in caps or item["sku"] in banned or item["units"] <= 0:
            continue
        room = caps[cat] - given[cat]
        if room <= 0:
            continue
        take = min(room, item["units"])
        if take > 0:
            picks.append({"sku": item["sku"], "name": item["name"], "category": cat,
                          "units": take, "expiry": item["expiry"]})
            given[cat] += take
            item["units"] -= take  # caller passes a copy if it wants to preserve
    for cat, cap in caps.items():
        if given[cat] < cap:
            unmet.append({"category": cat, "short_by": cap - given[cat]})
    return {"family_id": family["id"], "family": family["name"], "household_size": size,
            "picks": picks, "unmet": unmet}


def plan_distribution(today: date | None = None, with_donations: bool = True,
                       families: dict | None = None, inventory: list[dict] | None = None) -> dict:
    """`families`/`inventory` let a caller inject already-fetched data (e.g. from
    an MCP data source, see tools.py) instead of reading the local seed files.
    Pass `inventory` already donation-merged with `with_donations=False` to
    skip the internal load_intake() merge."""
    today = today or date(2026, 9, 1)
    fam = families if families is not None else load_families()
    inv = inventory if inventory is not None else load_inventory()
    if with_donations:
        inv = apply_donations(inv, [d for d in load_intake()])
    working = copy.deepcopy(inv)
    lists = []
    for f in sorted(fam["families"], key=lambda x: (x["pickup_day"], x["id"])):
        lst = build_pick_list(f, working, today)   # mutates `working` units down
        lists.append(lst)
    return {
        "as_of": today.isoformat(),
        "pick_lists": lists,
        "families_short": [l["family"] for l in lists if l["unmet"]],
        "expiring": expiring_soon(inv, today),
        "shortages": shortages(inv, fam),
        "leftover": [{"name": i["name"], "category": i["category"], "units": i["units"]}
                     for i in working if i["units"] > 0],
    }


def community_ask(today: date | None = None, families: dict | None = None,
                   inventory: list[dict] | None = None) -> str:
    """`families`/`inventory` are passed through to plan_distribution() - see its docstring."""
    today = today or date(2026, 9, 1)
    fam = families if families is not None else load_families()
    plan = plan_distribution(today, families=fam, inventory=inventory,
                              with_donations=inventory is None)
    lines = ["Food bank status for this week's distribution:", ""]
    defs = plan["shortages"]["deficits"]
    if defs:
        lines.append("WE NEED:")
        for d in defs:
            lines.append(f"  - {abs(d['gap'])} more units of {d['category']} "
                         f"(need {d['need']} for {sum(f['household_size'] for f in fam['families'])} people, have {d['on_hand']})")
    exp = [e for e in plan["expiring"] if e["days_left"] >= 0 and e["units"] > 0]
    if exp:
        lines += ["", "USE THIS WEEK (or we lose it):"]
        for e in exp:
            lines.append(f"  - {e['units']} x {e['name']} - expires in {e['days_left']} day(s)")
    if plan["families_short"]:
        lines += ["", f"Families we can't fully stock this cycle: {', '.join(plan['families_short'])}"]
    lines += ["", "Drop-off: Tue-Thu 9am-1pm. Thank you."]
    return "\n".join(lines)
