# Deploying FoodBankFlow to Amazon Bedrock AgentCore

## 0. Prerequisites
- An AWS account with Amazon Bedrock model access enabled for the model in
  `foodbankflow/config.py` (`MODEL_ID`). In us-east-1 the default cross-region
  Claude Haiku profile is on by default for new accounts.
- `aws configure` complete (`aws sts get-caller-identity` works).
- Node.js 18+ and the AgentCore CLI: `npm install -g @aws/agentcore`.
  (The old `bedrock-agentcore-starter-toolkit` Python CLI is deprecated —
  this repo now deploys with the CLI's CodeZip build, so no Docker is
  needed.)
- Python 3.11+.

## 1. Local check
```bash
make venv
make test           # deterministic, no network
make demo           # no-model walkthrough
make agent          # one real Bedrock turn
make serve          # POST http://localhost:8080/invocations {"prompt": "..."}
```

## 2. Project config
The runtime is already registered as a "bring your own code" agent in
`agentcore/agentcore.json` (CodeZip build, entrypoint `agentcore_app.py`,
code location `.`). Dependencies are declared in `pyproject.toml` (kept in
sync with `requirements.txt`) since the CDK packaging step needs it. Install
the CDK app's own dependencies once:
```bash
npm install --prefix agentcore/cdk
```
Re-run `agentcore add agent` / edit `agentcore/agentcore.json` directly only
if you need to change the runtime name, memory, or network settings.

## 3. Deploy
```bash
make deploy      # agentcore deploy
```
Synthesizes and deploys a CDK stack that packages the code (CodeZip, no
container build), creates the execution role, and creates the AgentCore
Runtime. On first use in an account/region it will prompt to bootstrap CDK
(`agentcore deploy --yes` auto-bootstraps non-interactively).

## 4. Invoke
```bash
make invoke P="<a request in plain language>"    # agentcore invoke "$(P)"
```
Or from any app with the SDK:
```python
import boto3, json
c = boto3.client("bedrock-agentcore", region_name="us-east-1")
r = c.invoke_agent_runtime(
    agentRuntimeArn="<arn from `agentcore status`>",
    runtimeSessionId="s" * 40,
    payload=json.dumps({"prompt": "..."}),  # matches agentcore_app.py's payload.get("prompt")
)
print(json.loads(r["response"].read()))
```

## 5. Schedule it (the "runs in the background" part)
`make deploy` already provisions this: `agentcore/cdk/lib/cdk-stack.ts`
creates a small Lambda (`<project>-morning-run`) that calls
`invoke_agent_runtime` with a "log today's donations, report expiring /
shortages / surplus" prompt, and an EventBridge Scheduler rule
(`cron(0 8 * * ? *)`, `America/New_York`) that triggers it every morning.
Change the cron/timezone in that file and redeploy to adjust the time. The
agent is stateless per call; durable state lives in AgentCore Memory and the
seed/`data` files.

## 6. Tear down
```bash
make destroy     # agentcore remove agent --name foodbankflow --yes || true; agentcore deploy --yes
```

Repo: https://github.com/nareshsaladi54-wq/foodbank-flow-agent
