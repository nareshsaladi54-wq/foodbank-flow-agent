# FoodBankFlow — Devpost submission

## Elevator pitch
An operations agent for a small food bank: it logs donations, tracks inventory
and expiry, builds fair pick lists against family needs, and raises a targeted
community ask for the real gaps.

## Inspiration
A small food bank runs on volunteers and a clipboard: a pile of donations to
count, a fridge about to turn, a list of families with different sizes and diets,
and a guess at what to ask for. Get it wrong and produce rots while families go
without dairy.

## What it does
Logs the intake queue into stock, flags what's about to spoil with days left,
projects this week's demand against on-hand by category (and names the families a
gap hits), builds household-capped constraint-aware pick lists that hand out
expiring items first, and drafts the "what we need / use this week / surplus to
share" community message.

## How we built it
- **Strands Agents SDK** — one operations `Agent` with eleven `@tool`s.
- **Amazon Bedrock** — Claude Haiku 4.5.
- **Amazon Bedrock AgentCore** — `BedrockAgentCoreApp` entrypoint, morning cron;
  the donation intake queue is fed by a photo/vision step.
- **A deterministic core** (`core.py`, 10 tests): donation merge, expiry windows,
  demand-vs-stock math, the constraint-aware allocation, the ask text. Seed files
  are immutable so the demo is repeatable.

## Challenges
Fair allocation under scarcity: capping by household size, respecting diets, and
still emptying the soonest-to-spoil shelf first — all in tested code so the agent
can't quietly give one family five loaves of bread.

## Accomplishments
The whole weekly plan and the community ask run offline (`make demo`). The agent
turns the numbers into something a tired volunteer can act on in two minutes.

## What we learned
"What are we short?" only means something against real projected demand — you
need the household math in tested code before the model can be trusted to raise
an alarm.

## Built with
`strands-agents` · `amazon-bedrock` · `amazon-bedrock-agentcore` · `claude-haiku-4.5` ·
`python` · `boto3` · `eventbridge-scheduler` · `food-bank` · `community`

## Try it out
- Code: https://github.com/nareshsaladi54-wq/foodbank-flow-agent
- `make venv && make test && make demo`

## Checklist
- [x] Public GitHub repo, MIT license
- [x] README + architecture diagram
- [x] Built with Strands Agents SDK
- [x] Deployable on Amazon Bedrock AgentCore
- [ ] Demo video (≤5 min)
- [ ] AWS Builder ID
