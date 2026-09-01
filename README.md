# FoodBankFlow

**An operations agent for a small food bank: it logs donations, tracks inventory
and expiry, builds fair pick lists against family needs, and raises a targeted
community ask for the real gaps.**

Track: **Good Neighbor Agents** · Built with the [Strands Agents SDK](https://strandsagents.com) · Deploys to **Amazon Bedrock AgentCore**

---

## The problem

A small food bank runs on volunteers and a clipboard. Every week: a pile of
donations to count and shelve, a fridge full of things about to turn, a list of
registered families with different household sizes and dietary needs, and a
guess at what to ask the community for. Get it wrong and produce rots while
families go without dairy. It's repetitive inventory math on a deadline — and
whoever does it is also running the actual distribution.

## What it does

1. **Logs donations** (`log_donations`) — folds the intake queue (what the
   drop-off photo/vision step returned: donor + line items) into stock and
   reports the per-category increase.
2. **Flags what's about to spoil** (`expiring_report`) — units and days left, so
   perishables go out or get redistributed first.
3. **Finds the real shortages** (`shortage_report`) — projected demand for this
   week's registered families (per-person allowance × household size) vs on-hand,
   by category, and **which families** a gap hits.
4. **Builds fair pick lists** (`plan_week`, `family_pick_list`) — capped by
   household size, respecting dietary constraints (gluten-free, diabetic,
   no-pork, infant), handing out expiring items first.
5. **Drafts the community ask** (`draft_community_ask`) — "we need 7 units of
   dairy this week; use these 16 loaves of bread before Thursday; we have surplus
   produce to share."

## Design principle: the agent never counts stock

Donation merging, expiry windows, demand-vs-stock math, the constraint-aware
allocation and the ask text are all in `foodbankflow/core.py` with 10 tests.
The seed files are immutable and every report works on "inventory + logged
donations", so the demo is repeatable and idempotent. `python run_demo.py` runs
the whole plan offline.

## Run it

```bash
make venv
make test    # 10 deterministic tests (merge, expiry, shortage, constraints, allocation)
make demo    # offline weekly plan + community ask
make agent   # one real Bedrock turn
make serve   # AgentCore contract on :8080
```

Sample: logs 3 donations, flags 4 perishables (bread in 2 days), finds a 7-unit
dairy shortage hitting the Booth and Diallo families, and drafts the ask.

## Deploy to Amazon Bedrock AgentCore

See [DEPLOY.md](DEPLOY.md).

```bash
.venv/bin/agentcore configure -e agentcore_app.py -n foodbankflow -rf requirements.txt
.venv/bin/agentcore deploy
.venv/bin/agentcore invoke '{"prompt": "Log today's donations. What is spoiling, what are we short?"}'
```

Schedule it each morning; point the donation-photo intake at the same runtime.

## Data

`foodbankflow/data/` is synthetic — 12 inventory SKUs, 6 families, a 3-donation
intake queue, an allocation policy. In production the readers back onto a
warehouse/inventory table and a client-registration system; the intake queue is
fed by the vision step that reads a photo of each drop-off (the same approach as
the author's `bills_scan` receipt tool).

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md).

## License

MIT — see [LICENSE](LICENSE).
