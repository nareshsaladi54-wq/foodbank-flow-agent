# Deploying FoodBankFlow to Amazon Bedrock AgentCore

## 0. Prerequisites
- An AWS account with Amazon Bedrock model access enabled for the model in
  `foodbankflow/config.py` (`MODEL_ID`). In us-east-1 the default cross-region
  Claude Haiku profile is on by default for new accounts.
- `aws configure` complete (`aws sts get-caller-identity` works).
- Docker running (AgentCore builds an ARM64 image).
- Python 3.11+.

## 1. Local check
```bash
make venv
make test           # deterministic, no network
make demo           # no-model walkthrough
make agent          # one real Bedrock turn
make serve          # POST http://localhost:8080/invocations {"prompt": "..."}
```

## 2. Configure the runtime
```bash
.venv/bin/agentcore configure -e agentcore_app.py -n foodbankflow -rf requirements.txt
```
This writes `.bedrock_agentcore.yaml`, creates an execution role and an ECR
repo. Accept the defaults; enable AgentCore Memory if prompted (used for the
long-term memory tools).

## 3. Deploy
```bash
.venv/bin/agentcore deploy
```
Builds the ARM64 container, pushes to ECR, creates the AgentCore Runtime.

## 4. Invoke
```bash
.venv/bin/agentcore invoke '{"prompt": "<a request in plain language>"}'
```
Or from any app with the SDK:
```python
import boto3, json
c = boto3.client("bedrock-agentcore", region_name="us-east-1")
r = c.invoke_agent_runtime(
    agentRuntimeArn="<arn from `agentcore status`>",
    runtimeSessionId="s" * 40,
    payload=json.dumps({"input": {"prompt": "..."}}),
)
print(json.loads(r["response"].read()))
```

## 5. Schedule it (the "runs in the background" part)
Point an EventBridge Scheduler rule at a tiny Lambda that calls
`invoke_agent_runtime` on a cron, or run the same call from your own
scheduler. The agent is stateless per call; durable state lives in
AgentCore Memory and the seed/`data` files.

## 6. Tear down
```bash
.venv/bin/agentcore destroy
```

Repo: https://github.com/nareshsaladi54-wq/foodbank-flow-agent
