"""The vision step: turn a photo of a donation drop-off into intake line
items (see the PHOTO -> INTAKE edge in ARCHITECTURE.md).

Calls Amazon Bedrock's Converse API directly with the photo and a
JSON-only instruction, using the same model as the agent
(config.MODEL_ID - Claude Haiku 4.5 is multimodal). Kept out of tools.py so
the JSON-parsing half is unit-testable without a live model call - see
tests/test_vision.py, which only exercises _parse_response."""
from __future__ import annotations

import json
import logging

from .config import MODEL_ID, REGION
from .core import CATEGORIES

logger = logging.getLogger(__name__)

# Bedrock Converse API image formats; media_type may arrive as "image/jpg"
# from a client that doesn't know the wire format is spelled "jpeg".
_FORMAT_ALIASES = {"jpg": "jpeg"}

PROMPT = f"""You are reading a photo of a food bank donation drop-off. List every
distinct item you can identify as a line item. For each item give:
- name: short human label (e.g. "Rice 5lb")
- sku: a short lowercase-hyphen id (e.g. "rice-5lb")
- category: one of {", ".join(CATEGORIES)} - pick the closest fit
- units: how many of that item are visible, as an integer (a case/bag/box counts
  as 1 unit unless individual items are clearly separated)
- perishable: true or false
- expiry: your best-guess ISO date (YYYY-MM-DD) - read a printed date if visible,
  otherwise a far-future date like "2027-01-01" for shelf-stable goods

Also give a `donor` guess if a name/logo/label is visible in the photo, else "".

Reply with ONLY a JSON object shaped {{"donor": "...", "items": [{{...}}, ...]}}.
No prose, no markdown code fences."""


def _parse_response(text: str) -> dict:
    """Pull the {donor, items} object out of a model reply, tolerating ```json
    fences and items missing/invalid fields (those are dropped, not fatal)."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[len("json"):]
    doc = json.loads(text)

    items = []
    for it in doc.get("items", []):
        name = (it.get("name") or "").strip()
        try:
            units = int(it.get("units", 0))
        except (TypeError, ValueError):
            units = 0
        if not name or units <= 0:
            continue
        items.append({
            "name": name,
            "sku": (it.get("sku") or name.lower().replace(" ", "-")).strip(),
            "category": it["category"] if it.get("category") in CATEGORIES else "grain",
            "units": units,
            "perishable": bool(it.get("perishable", False)),
            "expiry": it.get("expiry") or "2027-01-01",
        })
    return {"donor": (doc.get("donor") or "").strip(), "items": items}


def extract_donation(image_bytes: bytes, media_type: str = "image/jpeg") -> dict:
    """Read one drop-off photo. Returns {"donor": str, "items": [...]} in the
    shape core.append_intake_item expects. Makes a live Bedrock call - not
    exercised by the deterministic test suite."""
    import boto3

    fmt = media_type.split("/")[-1].lower()
    fmt = _FORMAT_ALIASES.get(fmt, fmt)
    client = boto3.client("bedrock-runtime", region_name=REGION)
    resp = client.converse(
        modelId=MODEL_ID,
        messages=[{
            "role": "user",
            "content": [
                {"image": {"format": fmt, "source": {"bytes": image_bytes}}},
                {"text": PROMPT},
            ],
        }],
        inferenceConfig={"temperature": 0.0, "maxTokens": 1500},
    )
    text = resp["output"]["message"]["content"][0]["text"]
    try:
        return _parse_response(text)
    except (json.JSONDecodeError, KeyError, IndexError, TypeError):
        logger.exception("vision step returned unparseable output: %r", text)
        return {"donor": "", "items": []}
