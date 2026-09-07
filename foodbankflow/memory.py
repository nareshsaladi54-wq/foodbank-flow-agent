"""Ops memory: recurring donors, standing family notes, what the last ask
pulled in.

Backed by Amazon Bedrock AgentCore Memory (SEMANTIC strategy) when deployed -
`agentcore add memory` provisions the resource and CDK auto-injects its id as
MEMORY_FOODBANKFLOW_NOTES_ID on every agent runtime in the project, with full
read/write IAM already granted (see agentcore/agentcore.json's "memories").
Falls back to a local Markdown file when that env var isn't set, so local
dev, tests and the offline demo stay deterministic and network-free.
"""
from __future__ import annotations

import datetime
import logging
import os
import pathlib

from .config import DATA_DIR, REGION

logger = logging.getLogger(__name__)

MEM_FILE = pathlib.Path(DATA_DIR) / "memory.md"

# Matches the namespaceTemplates on the "foodbankflow_notes" SEMANTIC strategy
# in agentcore/agentcore.json - each actor's extracted facts land under here.
NAMESPACE = "/users/{actor_id}/facts"
# One running session per actor: notes accumulate as events feeding SEMANTIC
# extraction; we read back the extracted facts, not the raw turn history.
SESSION_ID = "ops-notes"

MEMORY_ID = os.environ.get("MEMORY_FOODBANKFLOW_NOTES_ID")

_manager = None


def _session(actor_id: str):
    """Lazily build a MemorySessionManager and hand back an actor-scoped session."""
    global _manager
    if _manager is None:
        from bedrock_agentcore.memory import MemorySessionManager

        _manager = MemorySessionManager(memory_id=MEMORY_ID, region_name=REGION)
    return _manager.create_memory_session(actor_id=actor_id, session_id=SESSION_ID)


def remember(actor_id: str, note: str) -> str:
    """Save a standing ops note (recurring donor, a family's situation, what an ask brought in)."""
    note = note.strip()
    if MEMORY_ID:
        try:
            from bedrock_agentcore.memory.constants import ConversationalMessage, MessageRole

            _session(actor_id).add_turns([ConversationalMessage(note, MessageRole.USER)])
            return "noted"
        except Exception:
            logger.exception("AgentCore Memory write failed; falling back to local notes file")
    return _remember_local(actor_id, note)


def recall(actor_id: str, query: str = "") -> list[str]:
    """Recall standing ops notes, optionally filtered by topic."""
    if MEMORY_ID:
        try:
            records = _session(actor_id).search_long_term_memories(
                query=query or "standing notes for this food bank",
                namespace_path=NAMESPACE.format(actor_id=actor_id),
                top_k=15,
            )
            return [text for r in records if (text := r.get("content", {}).get("text", "").strip())]
        except Exception:
            logger.exception("AgentCore Memory read failed; falling back to local notes file")
    return _recall_local(actor_id, query)


def _remember_local(actor_id: str, note: str) -> str:
    MEM_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(MEM_FILE, "a") as fh:
        fh.write(f"- [{datetime.date.today().isoformat()}] ({actor_id}) {note}\n")
    return "noted"


def _recall_local(actor_id: str, query: str = "") -> list[str]:
    if not MEM_FILE.exists():
        return []
    lines = [ln.strip() for ln in MEM_FILE.read_text().splitlines() if ln.strip()]
    hits = [ln for ln in lines if f"({actor_id})" in ln]
    if query:
        terms = [t for t in query.lower().split() if len(t) > 2]
        hits = [ln for ln in hits if any(t in ln.lower() for t in terms)] or hits
    return hits[-15:]
