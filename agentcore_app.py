"""Amazon Bedrock AgentCore entrypoint for FoodBankFlow.

Exposes the AgentCore Runtime contract (POST /invocations, GET /ping) via the
Bedrock AgentCore SDK. Deploy with the AgentCore CLI:

    agentcore configure -e agentcore_app.py -n foodbankflow
    agentcore deploy
    agentcore invoke '{"prompt": "..."}'
"""
from bedrock_agentcore.runtime import BedrockAgentCoreApp

from foodbankflow.agent import run_agent
from foodbankflow.tools import queue_photo_intake

app = BedrockAgentCoreApp()


@app.entrypoint
def invoke(payload, context=None):
    """payload = {"prompt": str, "actor_id": str?, "image_base64": str?, "media_type": str?, "donor": str?}.
    image_base64 is an optional drop-off photo (the PHOTO -> vision step in
    ARCHITECTURE.md). It's read and queued here in plain Python, before the
    agent runs - not relayed through the model as a tool-call argument, which
    would mean asking it to retype a many-KB base64 blob verbatim (slow, and
    prone to stalling the stream on anything but a tiny photo). Returns
    {"result": str}."""
    payload = payload or {}
    prompt = payload.get("prompt", "").strip()
    if not prompt:
        return {"error": "payload.prompt must be a non-empty string"}
    actor_id = payload.get("actor_id", "demo")
    image_b64 = payload.get("image_base64")
    if image_b64:
        media_type = payload.get("media_type", "image/jpeg")
        queued = queue_photo_intake(image_b64, media_type, payload.get("donor", ""))
        if "error" in queued:
            prompt = f"{prompt}\n\n(The attached drop-off photo couldn't be read: {queued['error']})"
        else:
            prompt = (f"{prompt}\n\nA drop-off photo was already read by the vision step and queued "
                      f"as donor {queued['donor']!r} with {len(queued['items_queued'])} line item(s) - "
                      "no need to call intake_photo for it, just log_donations as usual.")
    return {"result": run_agent(prompt, actor_id=actor_id)}


if __name__ == "__main__":
    app.run()
