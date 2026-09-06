PY ?= .venv/bin/python
PIP ?= .venv/bin/pip

.PHONY: venv test demo agent serve deploy invoke destroy clean

venv:
	python3 -m venv .venv && $(PIP) install -U pip && $(PIP) install -r requirements.txt

test:            ## deterministic tests, no model, no network
	$(PY) -m pytest -q

demo:            ## no-model walkthrough of the deterministic core
	$(PY) run_demo.py

agent:           ## one real agent turn against Bedrock
	$(PY) -m foodbankflow.agent

serve:           ## local AgentCore contract on :8080
	$(PY) agentcore_app.py

deploy:          ## deploy via the AgentCore CLI (CDK); bootstraps the account on first run
	agentcore deploy

invoke:
	agentcore invoke "$(P)"

destroy:         ## tear down the deployed runtime (safe to re-run)
	agentcore remove agent --name foodbankflow --yes || true
	agentcore deploy --yes

clean:
	rm -rf .pytest_cache out artifacts_out **/__pycache__
