# FoodBankFlow — Architecture

## Overview

A **single Strands operations agent** over a deterministic inventory + allocation
core. The agent never counts stock or computes demand — it runs the plan and
writes the practical summary for a volunteer.

```mermaid
flowchart TD
    PHOTO[Drop-off photo\n→ vision step → line items] --> INTAKE
    SCHED[EventBridge Scheduler\nevery morning] -->|invoke_agent_runtime| APP
    subgraph RT["Amazon Bedrock AgentCore Runtime (ARM64)"]
        APP["agentcore_app.py — BedrockAgentCoreApp\n/invocations · /ping"]
        AGENT["Strands Agent 'foodbankflow'\nClaude Haiku 4.5\nprompt: the shortages and the expiring list are the point"]
        APP --> AGENT
        AGENT -->|tool calls| TOOLS
        subgraph TOOLS["foodbankflow/tools.py — @tool"]
            T1[log_donations]
            T2[expiring_report]
            T3[shortage_report]
            T4[family_pick_list]
            T5[plan_week]
            T6[draft_community_ask]
            T7[remember_note / recall_notes]
        end
        T1 --> CORE
        T2 --> CORE
        T3 --> CORE
        T5 --> CORE["foodbankflow/core.py (tested)\n• apply_donations (merge by sku, keep sooner expiry)\n• expiring_soon (window)\n• shortages (demand = allowance x household vs on-hand)\n• build_pick_list (household cap, constraints, expiring first)\n• plan_distribution / community_ask"]
        T7 --> MEM["memory.py — recurring donors, family notes\n(AgentCore Memory in prod)"]
    end
    CORE --> INV[("data/inventory.json → warehouse table")]
    CORE --> INTAKE[("data/donations_intake.json → vision intake")]
    CORE --> FAM[("data/families.json → client registration")]
    AGENT --> OUT["weekly plan · pick lists · community ask\n(to volunteers / public channel)"]
```

## Components

| File | Responsibility |
|---|---|
| `agentcore_app.py` | AgentCore Runtime contract. |
| `foodbankflow/agent.py` | System prompt: log, then expiring → shortages → surplus, then offer the ask and pick lists. |
| `foodbankflow/tools.py` | 11 `@tool` wrappers. Seed files immutable; reports run on inventory + logged donations. |
| `foodbankflow/core.py` | **The math.** Donation merge, expiry, demand-vs-stock, constraint-aware allocation, ask text. |
| `foodbankflow/memory.py` | Recurring donors, standing family notes. |
| `tests/test_core.py` | 10 tests: merge/expiry rules, the dairy shortage, produce surplus, gluten-free allocation, household caps, expiring-first. |
| `run_demo.py` | Offline weekly plan + community ask. |

## The allocation model (`core.py`)

- **Demand** per category = `per_person_per_cycle[cat] × Σ household_size` over
  the relevant families; infants add a hygiene unit.
- **`build_pick_list`** caps each category at `rate × household_size`, drops
  items banned by a family's constraints (`gluten_free` → no bread/pasta,
  `diabetic` → no bread, `no_pork` reserved for real data), and walks inventory
  **sorted by expiry** so the soonest-to-spoil goes out first.
- **`shortages`** reports a `deficit` where on-hand < demand, and `surplus` where
  on-hand exceeds a full extra cycle — the shareable stock.

## How it meets the three hackathon requirements

| Requirement | Where |
|---|---|
| **Built with Strands Agents SDK** | `foodbankflow/agent.py` — `strands.Agent` + `@tool`. |
| **Routine/repetitive work for a group** | The weekly count-donations / check-expiry / project-demand / build-pick-lists cycle that one volunteer does by hand for every registered family. |
| **Deployable on Amazon Bedrock AgentCore** | `agentcore_app.py` + `DEPLOY.md`; morning cron + photo intake. |

## Model

`us.anthropic.claude-haiku-4-5-20251001-v1:0` (`MODEL_ID` override), temp 0.2.
