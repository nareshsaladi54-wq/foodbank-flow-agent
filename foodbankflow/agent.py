"""The FoodBankFlow agent - one operations agent for a small food bank."""
from __future__ import annotations

from strands import Agent
from strands.telemetry import StrandsTelemetry

from .config import bedrock_model
from .tools import TOOLS

# Wire spans to the OTLP endpoint the AgentCore Runtime provides (CloudWatch
# GenAI Observability / X-Ray Transaction Search). StrandsTelemetry() alone
# only sets up an in-memory tracer provider — it does nothing until an
# exporter is attached, so without this call no spans ever leave the process.
StrandsTelemetry().setup_otlp_exporter()

SYSTEM_PROMPT = """You are FoodBankFlow, the operations agent for a small food
bank run mostly by volunteers. Your job is to turn a pile of donations and a
list of families into a clear plan, and to raise the alarm on the real gaps.

On a run:
1. recall_notes(actor_id) for standing notes (recurring donors, families with a
   specific situation).
2. If a drop-off photo hasn't already been queued (the vision step usually runs
   before you do, via the deploy entrypoint's image_base64 field - the prompt
   will say so), and the volunteer separately hands you photo bytes to process,
   call intake_photo with them first.
3. log_donations to fold the intake queue into stock, and report what it added.
4. Then give the volunteer, in this order:
   - EXPIRING: what must go out or be redistributed this week (expiring_report).
     Be specific - units and days left.
   - SHORTAGES: where projected demand for this week's families beats what's on
     hand (shortage_report). Give the category, the gap, and which families that
     hits (families we can't fully stock, from plan_week).
   - SURPLUS: what we have well over a cycle of, that could be shared with another
     pantry.
5. Offer to draft_community_ask (the public "what we need / use this week"
   message) and to produce family_pick_list for pickup day.

All quantities come from the tools - never estimate stock or demand yourself.
Keep it practical and short. The shortages and the expiring list are the point.
"""


def build_agent(stream: bool = False) -> Agent:
    kw = {} if stream else {"callback_handler": None}
    return Agent(model=bedrock_model(), system_prompt=SYSTEM_PROMPT, tools=TOOLS,
                 name="foodbankflow", **kw)


def run_agent(prompt: str, actor_id: str = "volunteer") -> str:
    agent = build_agent()
    return str(agent(f"actor_id={actor_id}\n\n{prompt}"))


if __name__ == "__main__":
    print(run_agent("Log today's donations and tell me what's about to spoil and "
                    "what we're short for this week."))
