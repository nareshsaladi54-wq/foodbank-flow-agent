"""Amazon Bedrock AgentCore entrypoint for FoodBankFlow.

Exposes the AgentCore Runtime contract (POST /invocations, GET /ping) via the
Bedrock AgentCore SDK. Deploy with the AgentCore CLI:

    agentcore configure -e agentcore_app.py -n foodbankflow
    agentcore deploy
    agentcore invoke '{"prompt": "..."}'
"""
from bedrock_agentcore.runtime import BedrockAgentCoreApp

from foodbankflow.agent import run_agent

app = BedrockAgentCoreApp()


@app.entrypoint
def invoke(payload, context=None):
    """payload = {"prompt": str, "actor_id": str?}. Returns {"result": str}."""
    prompt = (payload or {}).get("prompt", "").strip()
    if not prompt:
        return {"error": "payload.prompt must be a non-empty string"}
    actor_id = (payload or {}).get("actor_id", "demo")
    return {"result": run_agent(prompt, actor_id=actor_id)}


if __name__ == "__main__":
    app.run()
