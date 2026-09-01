#!/usr/bin/env python3
"""No-model demo: run the deterministic plan and print it. Zero Bedrock calls."""
from datetime import date

from foodbankflow import core

TODAY = date(2026, 9, 1)

if __name__ == "__main__":
    plan = core.plan_distribution(TODAY)

    print("== EXPIRING (hand out / redistribute now) ==")
    for e in plan["expiring"]:
        print(f"  {e['units']:>3} x {e['name']:<22} {e['status']:<22} ({e['days_left']}d)")

    print("\n== SHORTAGES for this week's families ==")
    for d in plan["shortages"]["deficits"]:
        print(f"  {d['category']:<9} need {d['need']:>3}  have {d['on_hand']:>3}  GAP {d['gap']}")
    print("  families we can't fully stock:", plan["families_short"] or "none")

    print("\n== SURPLUS (shareable with another pantry) ==")
    for s in plan["shortages"]["surplus"]:
        print(f"  {s['category']:<9} have {s['on_hand']:>3}  (need {s['need']})")

    print("\n== PICK LISTS ==")
    for l in plan["pick_lists"]:
        items = ", ".join(f"{p['units']}x {p['name']}" for p in l["picks"])
        print(f"  {l['family']:<9} (hh {l['household_size']}): {items}")
        if l["unmet"]:
            print(f"      SHORT: {l['unmet']}")

    print("\n== COMMUNITY ASK ==")
    print(core.community_ask(TODAY))
